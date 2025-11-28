from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .ble_manager import SencorScaleManager
from .const import DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for each discovered scale."""
    data = hass.data[DOMAIN][entry.entry_id]
    manager: SencorScaleManager = data["manager"]

    entities: list[SencorScaleSensor] = []
    for address, name in manager.get_devices().items():
        entities.append(SencorScaleSensor(manager, address, name))

    async_add_entities(entities)

    # Listen for new devices discovered after startup
    async def handle_new_devices() -> None:
        current = {entity.unique_id for entity in entities}
        for address, name in manager.get_devices().items():
            if address not in current:
                entity = SencorScaleSensor(manager, address, name)
                entities.append(entity)
                async_add_entities([entity])

    hass.data[DOMAIN][entry.entry_id]["refresh_entities"] = handle_new_devices


class SencorScaleSensor(SensorEntity):
    """Representation of a Sencor scale weight sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:scale"
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfMass.GRAM

    def __init__(self, manager: SencorScaleManager, address: str, name: str) -> None:
        self._manager = manager
        self._attr_name = name or DEVICE_NAME
        self._attr_unique_id = address
        self._address = address
        self._attr_native_value = manager.get_weight(address)
        self._unsub = None

    async def async_added_to_hass(self) -> None:
        @callback
        def handle_update(address: str, weight: float, details: dict[str, Any]) -> None:
            self._attr_native_value = weight
            self.async_write_ha_state()

        self._manager.register_callback(self._address, handle_update)
        self._unsub = lambda: self._manager.unregister_callback(self._address, handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            manufacturer="Sencor",
            model="Kitchen Scale",
            name=self.name,
        )
