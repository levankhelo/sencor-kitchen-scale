from __future__ import annotations

from typing import Any
import asyncio

import voluptuous as vol
from homeassistant import config_entries
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from .const import (
    CONF_DEVICES,
    CONF_MAC_ADDRESS,
    CONF_OFF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_OFF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DEVICE_NAME,
)


class SencorScaleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Sencor scale integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if not hasattr(self, "_discovered"):
            self._discovered = await self._discover_devices()

        if user_input is not None:
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            off_scan_interval = user_input[CONF_OFF_SCAN_INTERVAL]
            devices: dict[str, str] = {}

            # Include selected discovered devices
            for device in getattr(self, "_discovered", []):
                use_key = f"use_{device.address}"
                name_key = f"name_{device.address}"
                if user_input.get(use_key, True):
                    devices[device.address] = user_input.get(name_key, device.address)

            # Optional manual MAC entry
            extra_mac = user_input.get(CONF_MAC_ADDRESS, "").strip()
            if extra_mac:
                devices[extra_mac] = user_input.get("extra_name", extra_mac)

            if not devices:
                errors["base"] = "no_devices_found"
            elif scan_interval < 0 or off_scan_interval < 0:
                errors["base"] = "invalid_scan_interval"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Sencor Kitchen Scales",
                    data={
                        CONF_SCAN_INTERVAL: scan_interval,
                        CONF_OFF_SCAN_INTERVAL: off_scan_interval,
                        CONF_DEVICES: devices,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.Coerce(int),
                vol.Required(
                    CONF_OFF_SCAN_INTERVAL, default=DEFAULT_OFF_SCAN_INTERVAL
                ): vol.Coerce(int),
            }
        )
        # Add discovered devices with include toggles and names
        for device in getattr(self, "_discovered", []):
            data_schema = data_schema.extend(
                {
                    vol.Optional(f"use_{device.address}", default=True): bool,
                    vol.Optional(
                        f"name_{device.address}", default=device.name or device.address
                    ): str,
                }
            )

        # Optional manual entry
        data_schema = data_schema.extend(
            {
                vol.Optional(CONF_MAC_ADDRESS, default=""): str,
                vol.Optional("extra_name", default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def _discover_devices(self) -> list[BLEDevice]:
        """Scan briefly for Sencor devices."""
        found: list[BLEDevice] = []

        def detection_callback(device: BLEDevice, adv_data: AdvertisementData) -> None:
            if device.name and DEVICE_NAME.lower() in device.name.lower():
                if all(device.address != d.address for d in found):
                    found.append(device)

        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        await asyncio.sleep(8)
        await scanner.stop()
        return found


class SencorScaleOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for the Sencor scale integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        devices = self.config_entry.options.get(
            CONF_DEVICES, self.config_entry.data.get(CONF_DEVICES, {})
        )
        mac, current_name = next(iter(devices.items())) if devices else ("", "")

        if user_input is not None:
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            off_scan_interval = user_input[CONF_OFF_SCAN_INTERVAL]
            new_name = user_input.get("name", current_name or mac)
            if scan_interval < 0 or off_scan_interval < 0:
                errors["base"] = "invalid_scan_interval"
            else:
                updated_devices = {mac: new_name} if mac else devices
                return self.async_create_entry(
                    title=self.config_entry.title,
                    data={
                        CONF_SCAN_INTERVAL: scan_interval,
                        CONF_OFF_SCAN_INTERVAL: off_scan_interval,
                        CONF_DEVICES: updated_devices or devices,
                    },
                )

        base_data = self.config_entry.options or self.config_entry.data
        current_interval = base_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_off_interval = base_data.get(CONF_OFF_SCAN_INTERVAL, DEFAULT_OFF_SCAN_INTERVAL)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.Coerce(int),
                vol.Required(CONF_OFF_SCAN_INTERVAL, default=current_off_interval): vol.Coerce(int),
                vol.Optional("name", default=current_name or mac): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)


async def async_get_options_flow(
    config_entry: config_entries.ConfigEntry,
) -> config_entries.OptionsFlow:
    return SencorScaleOptionsFlowHandler(config_entry)
