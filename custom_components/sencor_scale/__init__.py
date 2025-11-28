from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .ble_manager import SencorScaleManager

PLATFORMS: list[str] = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration via YAML (not used, but kept for completeness)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sencor scale from a config entry."""
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    manager = SencorScaleManager(hass, scan_interval=scan_interval)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"manager": manager}

    await manager.start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, {})
    manager: SencorScaleManager | None = data.get("manager")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if manager:
        await manager.stop()

    return unload_ok
