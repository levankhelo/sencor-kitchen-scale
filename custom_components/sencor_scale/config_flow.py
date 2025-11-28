from __future__ import annotations

from typing import Any
import asyncio

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from .const import (
    CONF_DEVICES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_NAME,
    DOMAIN,
)


class SencorScaleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Sencor scale integration."""

    VERSION = 1
    _discovered: list[BLEDevice]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            if scan_interval < 0:
                errors["base"] = "invalid_scan_interval"
            else:
                devices: dict[str, str] = {}
                for device in getattr(self, "_discovered", []):
                    field = f"name_{device.address}"
                    devices[device.address] = user_input.get(field, device.address)
                return self.async_create_entry(
                    title="Sencor Kitchen Scales",
                    data={
                        CONF_SCAN_INTERVAL: scan_interval,
                        CONF_DEVICES: devices,
                    },
                )

        # Discover devices for this flow
        self._discovered = await self._discover_devices()
        if not self._discovered:
            errors["base"] = "no_devices_found"

        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.Coerce(int)
        }
        for device in self._discovered:
            schema_dict[vol.Optional(f"name_{device.address}", default=device.address)] = str

        data_schema = vol.Schema(schema_dict)
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def _discover_devices(self) -> list[BLEDevice]:
        """Scan for Sencor devices for a short window."""
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

        if user_input is not None:
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            if scan_interval < 0:
                errors["base"] = "invalid_scan_interval"
            else:
                devices = self.config_entry.data.get(CONF_DEVICES, {})
                updated_devices = {}
                for address in devices:
                    updated_devices[address] = user_input.get(
                        f"name_{address}", devices[address]
                    )
                return self.async_create_entry(
                    title=self.config_entry.title,
                    data={
                        CONF_SCAN_INTERVAL: scan_interval,
                        CONF_DEVICES: updated_devices or devices,
                    },
                )

        current_interval = (
            self.config_entry.options.get(
                CONF_SCAN_INTERVAL, self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )
        )
        devices = self.config_entry.options.get(
            CONF_DEVICES, self.config_entry.data.get(CONF_DEVICES, {})
        )

        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.Coerce(int)
        }
        for address, name in devices.items():
            schema_dict[vol.Optional(f"name_{address}", default=name)] = str

        data_schema = vol.Schema(schema_dict)
        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)


async def async_get_options_flow(
    config_entry: config_entries.ConfigEntry,
) -> config_entries.OptionsFlow:
    return SencorScaleOptionsFlowHandler(config_entry)
