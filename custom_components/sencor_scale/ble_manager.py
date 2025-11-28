from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection
from homeassistant.core import HomeAssistant

from .const import LISTEN_WINDOW, RESOLVE_TIMEOUT

_LOGGER = logging.getLogger(__name__)

WeightCallback = Callable[[str, float, dict], None]


def parse_weight(payload: bytes | bytearray) -> tuple[int | None, dict[str, int]]:
    """Parse weight and details from payload."""
    details = {}
    if len(payload) < 4:
        return None, details

    raw_weight = (payload[2] << 8) | payload[3]
    sign_flag = payload[7] if len(payload) > 7 else 0
    sign = -1 if sign_flag == 1 else 1
    weight = sign * raw_weight

    details.update(
        {
            "raw_high": payload[2],
            "raw_low": payload[3],
            "sign_flag": sign_flag,
        }
    )
    return weight, details


def format_payload(payload: bytes | bytearray) -> str:
    """Return a human-readable string for debug logging."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    hex_str = payload.hex()
    parts = [f"[{timestamp}] HEX: {hex_str}", f"RAW: {list(payload)}"]
    weight, _ = parse_weight(payload)
    if weight is not None:
        parts.append(f"WEIGHT: {weight}")
    return " | ".join(parts)


class SencorScaleManager:
    """Manage BLE connections and streaming for Sencor scales."""

    def __init__(
        self,
        hass: HomeAssistant,
        scan_interval: int,
        off_scan_interval: int,
        device_names: dict[str, str],
    ) -> None:
        self.hass = hass
        self.scan_interval = scan_interval
        self.off_scan_interval = off_scan_interval
        self._stop_event = asyncio.Event()
        self._tasks: set[asyncio.Task] = set()
        self._weights: dict[str, float] = {}
        self._device_names: dict[str, str] = dict(device_names)
        self._callbacks: dict[str, set[WeightCallback]] = {}
        self._zero_reported: dict[str, bool] = {}
        self._known_devices: set[str] = set(device_names.keys())

    async def start(self) -> None:
        """Start background tasks."""
        self._stop_event.clear()
        for address, name in self._device_names.items():
            task = self.hass.loop.create_task(self._run_device(address, name))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        """Stop background tasks."""
        self._stop_event.set()
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    def register_callback(self, address: str, callback: WeightCallback) -> None:
        """Register a callback for weight updates for a device."""
        self._callbacks.setdefault(address, set()).add(callback)

    def unregister_callback(self, address: str, callback: WeightCallback) -> None:
        """Unregister a callback."""
        if address in self._callbacks:
            self._callbacks[address].discard(callback)
            if not self._callbacks[address]:
                self._callbacks.pop(address)

    def get_devices(self) -> dict[str, str]:
        """Return known devices {address: name}."""
        return dict(self._device_names)

    def get_weight(self, address: str) -> float | None:
        """Return last known weight for a device."""
        return self._weights.get(address)

    def _notify(self, address: str, weight: float, details: dict[str, int]) -> None:
        self._weights[address] = weight
        for cb in self._callbacks.get(address, set()):
            cb(address, weight, details)

    async def _run_device(self, address: str, name: str) -> None:
        """Maintain connection/retries for a single device indefinitely."""
        while not self._stop_event.is_set():
            try:
                ble_device = await self._resolve_device(address, name)
                if ble_device is None:
                    _LOGGER.debug("Failed to resolve %s; will retry", address)
                    await self._wait_with_stop(self.off_scan_interval)
                    continue

                client = await establish_connection(
                    BleakClient, ble_device, address, ble_device_callback=None
                )
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.debug("Failed to establish connection to %s: %s", address, err)
                await self._wait_with_stop(self.off_scan_interval)
                continue

            try:
                async with client:
                    if not client.is_connected:
                        _LOGGER.debug("Client not connected to %s", address)
                        await self._wait_with_stop(self.off_scan_interval)
                        continue

                    services = client.services
                    notify_chars = [
                        char
                        for svc in services
                        for char in svc.characteristics
                        if "notify" in char.properties or "indicate" in char.properties
                    ]

                    if not notify_chars:
                        _LOGGER.debug("No notify characteristics on %s", address)
                        await self._wait_with_stop(self.off_scan_interval)
                        continue

                    done_event = asyncio.Event()

                    def notification_handler(sender: int, data: bytearray) -> None:
                        weight, details = parse_weight(data)
                        if weight is None:
                            return
                        zero_seen = self._zero_reported.get(address, False)
                        if weight == 0:
                            if zero_seen:
                                return  # ignore repeated zeros
                            self._zero_reported[address] = True
                            _LOGGER.debug(
                                "Zero payload (suppressed for HA stats) from %s: %s",
                                address,
                                format_payload(data),
                            )
                            return

                        # Non-zero reading: reset zero suppression and propagate.
                        self._zero_reported[address] = False
                        _LOGGER.debug("Payload from %s: %s", address, format_payload(data))
                        self._notify(address, weight, details)
                        if self.scan_interval > 0:
                            self.hass.loop.call_soon_threadsafe(done_event.set)

                    for char in notify_chars:
                        try:
                            await client.start_notify(char.uuid, notification_handler)
                            _LOGGER.debug("Subscribed to %s on %s", char.uuid, address)
                        except Exception as err:  # pylint: disable=broad-except
                            _LOGGER.debug("Failed to subscribe %s: %s", char.uuid, err)

                    if self.scan_interval == 0:
                        # Stay connected indefinitely unless stopped or disconnected.
                        while not self._stop_event.is_set() and client.is_connected:
                            await asyncio.sleep(1)
                    else:
                        try:
                            await asyncio.wait_for(done_event.wait(), timeout=LISTEN_WINDOW)
                        except asyncio.TimeoutError:
                            _LOGGER.debug("No data from %s within window", address)

                    for char in notify_chars:
                        try:
                            await client.stop_notify(char.uuid)
                        except Exception:  # pylint: disable=broad-except
                            pass

            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.debug("Error while connected to %s: %s", address, err)

            if self._stop_event.is_set():
                break

            # Decide wait time before next attempt
            wait_time = self.scan_interval if self.scan_interval > 0 else self.off_scan_interval
            await self._wait_with_stop(wait_time)

    async def _wait_with_stop(self, timeout: int) -> None:
        """Wait for timeout or stop event, whichever comes first."""
        if timeout <= 0:
            return
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return

    async def _resolve_device(self, address: str, name: str) -> BLEDevice | None:
        """Scan briefly to resolve the BLEDevice before connecting."""
        device = await BleakScanner.find_device_by_address(
            address, timeout=RESOLVE_TIMEOUT, cb=None
        )
        if device:
            return device
        # Fallback to manual BLEDevice construction
        return BLEDevice(address=address, name=name, metadata={}, details=None)

    async def refresh_devices(self, devices: dict[str, str]) -> None:
        """Add new devices from config without dropping current tasks."""
        new_devices = set(devices.keys()) - self._known_devices
        self._device_names.update(devices)
        self._known_devices.update(devices.keys())

        for address in new_devices:
            name = devices[address]
            task = self.hass.loop.create_task(self._run_device(address, name))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
