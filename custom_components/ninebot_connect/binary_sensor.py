"""Observed vehicle flags; no control entities or services."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NinebotConfigEntry
from .entity import NinebotEntity

FLAGS = (
    BinarySensorEntityDescription(key="charging", translation_key="charging",
                                  device_class=BinarySensorDeviceClass.BATTERY_CHARGING),
    BinarySensorEntityDescription(key="main_battery_online", translation_key="main_battery_online",
                                  device_class=BinarySensorDeviceClass.CONNECTIVITY),
)


async def async_setup_entry(hass: HomeAssistant, entry: NinebotConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    known: set[str] = set()

    @callback
    def add_new() -> None:
        fresh = set(entry.runtime_data.vehicles) - known
        known.update(fresh)
        async_add_entities(NinebotBinarySensor(entry.runtime_data, sn, description)
                           for sn in fresh for description in FLAGS)

    add_new()
    entry.async_on_unload(entry.runtime_data.async_add_listener(add_new))


class NinebotBinarySensor(NinebotEntity, BinarySensorEntity):
    def __init__(self, coordinator, sn: str, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator, sn, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return getattr(self.vehicle_state, self.entity_description.key)
