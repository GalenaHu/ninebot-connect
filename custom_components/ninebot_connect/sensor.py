"""Vehicle measurements and cloud timestamps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NinebotConfigEntry
from .entity import NinebotEntity


@dataclass(frozen=True, kw_only=True)
class NinebotSensorDescription(SensorEntityDescription):
    field: str


SENSORS = (
    NinebotSensorDescription(
        key="lock_status",
        translation_key="lock_status",
        field="lock_status",
        icon="mdi:lock-question",
        entity_registry_enabled_default=False,
    ),
    NinebotSensorDescription(
        key="battery",
        translation_key="battery",
        field="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NinebotSensorDescription(
        key="range",
        translation_key="range",
        field="range_km",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NinebotSensorDescription(
        key="mileage",
        translation_key="mileage",
        field="mileage_km",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    NinebotSensorDescription(
        key="reported_at",
        translation_key="reported_at",
        field="reported_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    NinebotSensorDescription(
        key="location_at",
        translation_key="location_at",
        field="location_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    NinebotSensorDescription(
        key="fetched_at",
        translation_key="fetched_at",
        field="fetched_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: NinebotConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    known: set[str] = set()

    @callback
    def add_new() -> None:
        fresh = set(entry.runtime_data.vehicles) - known
        known.update(fresh)
        async_add_entities(
            NinebotSensor(entry.runtime_data, sn, description)
            for sn in fresh
            for description in SENSORS
        )

    add_new()
    entry.async_on_unload(entry.runtime_data.async_add_listener(add_new))


class NinebotSensor(NinebotEntity, SensorEntity):
    entity_description: NinebotSensorDescription

    def __init__(self, coordinator, sn: str, description: NinebotSensorDescription) -> None:
        super().__init__(coordinator, sn, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        field = self.entity_description.field
        if field == "fetched_at":
            value = self.coordinator.fetched_at
            return datetime.fromtimestamp(value, UTC) if value is not None else None
        return getattr(self.vehicle_state, field)
