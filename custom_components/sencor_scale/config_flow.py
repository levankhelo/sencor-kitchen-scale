from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN


class SencorScaleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Sencor scale integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            if scan_interval < 0:
                errors["base"] = "invalid_scan_interval"
            else:
                return self.async_create_entry(
                    title="Sencor Kitchen Scales",
                    data={CONF_SCAN_INTERVAL: scan_interval},
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.Coerce(
                    int
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)


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
                return self.async_create_entry(
                    title=self.config_entry.title,
                    data={CONF_SCAN_INTERVAL: scan_interval},
                )

        current_interval = (
            self.config_entry.options.get(
                CONF_SCAN_INTERVAL, self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )
        )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.Coerce(
                    int
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)


async def async_get_options_flow(
    config_entry: config_entries.ConfigEntry,
) -> config_entries.OptionsFlow:
    return SencorScaleOptionsFlowHandler(config_entry)
