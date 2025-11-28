from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from homeassistant.core import HomeAssistant

from .const import DEVICE_NAME, LISTEN_WINDOW

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
    """Manage BLE discovery and streaming for Sencor scales."""

    def __init__(self, hass: HomeAssistant, scan_interval: int) -> None:
        self.hass = hass
        self.scan_interval = scan_interval
        self._stop_event = asyncio.Event()
        self._tasks: set[asyncio.Task] = set()
        self._weights: dict[str, float] = {}
        self._device_names: dict[str, str] = {}
        self._callbacks: dict[str, set[WeightCallback]] = {}

    async def start(self) -> None:
        """Start background tasks."""
        self._stop_event.clear()
        task = self.hass.loop.create_task(self._run())
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

    async def _run(self) -> None:
        """Main loop to scan and connect."""
        while not self._stop_event.is_set():
            devices = await self._discover_devices()
            if not devices:
                _LOGGER.debug("No Sencor scales found in this scan.")
            else:
                _LOGGER.debug("Found %d Sencor scales", len(devices))

            connect_tasks = [
                self.hass.loop.create_task(self._connect_and_listen(device))
                for device in devices
            ]
            for task in connect_tasks:
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

            if self.scan_interval == 0:
                # Continuous streaming: just wait until stop is requested.
                await self._stop_event.wait()
            else:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.scan_interval)
                except asyncio.TimeoutError:
                    # Time to scan again
                    continue

    async def _discover_devices(self) -> list[BLEDevice]:
        """Discover nearby Sencor devices."""
        found: list[BLEDevice] = []

        def detection_callback(device: BLEDevice, adv_data: AdvertisementData) -> None:
            if device.name and DEVICE_NAME.lower() in device.name.lower():
                if device not in found:
                    found.append(device)
                    self._device_names[device.address] = device.name

        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        await asyncio.sleep(5)
        await scanner.stop()
        return found

    async def _connect_and_listen(self, device: BLEDevice) -> None:
        """Connect to a device and read/stream weight."""
        try:
            async with BleakClient(device.address) as client:
                if not client.is_connected:
                    _LOGGER.warning("Failed to connect to %s", device.address)
                    return

                services = client.services
                notify_chars = [
                    char
                    for svc in services
                    for char in svc.characteristics
                    if "notify" in char.properties or "indicate" in char.properties
                ]

                if not notify_chars:
                    _LOGGER.debug("No notify characteristics on %s", device.address)
                    return

                done_event = asyncio.Event()

                def notification_handler(sender: int, data: bytearray) -> None:
                    weight, details = parse_weight(data)
                    if weight is None:
                        return
                    _LOGGER.debug("Payload from %s: %s", device.address, format_payload(data))
                    self._notify(device.address, weight, details)
                    if self.scan_interval > 0:
                        # For periodic mode, stop after first useful reading.
                        self.hass.loop.call_soon_threadsafe(done_event.set)

                for char in notify_chars:
                    try:
                        await client.start_notify(char.uuid, notification_handler)
                        _LOGGER.debug("Subscribed to %s on %s", char.uuid, device.address)
                    except Exception as err:  # pylint: disable=broad-except
                        _LOGGER.debug("Failed to subscribe %s: %s", char.uuid, err)

                if self.scan_interval == 0:
                    await asyncio.wait(
                        [self._stop_event.wait()],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                else:
                    try:
                        await asyncio.wait_for(done_event.wait(), timeout=LISTEN_WINDOW)
                    except asyncio.TimeoutError:
                        _LOGGER.debug("No data from %s within window", device.address)

                for char in notify_chars:
                    try:
                        await client.stop_notify(char.uuid)
                    except Exception:  # pylint: disable=broad-except
                        pass

        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Error connecting to %s: %s", device.address, err)
