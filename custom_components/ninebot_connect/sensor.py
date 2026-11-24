"""Vehicle measurements and cloud timestamps."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NinebotConfigEntry
from .entity import NinebotEntity


@dataclass(frozen=True, kw_only=True)
class NinebotSensorDescription(SensorEntityDescription):
    field: str
    group: str = "basic"
    slot: int | None = None


SENSORS = (
    NinebotSensorDescription(
        key="estimated_range",
        translation_key="estimated_range",
        field="estimated_range_km",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NinebotSensorDescription(
        key="ai_range",
        translation_key="ai_range",
        field="ai_range_km",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NinebotSensorDescription(
        key="service_remaining_days",
        translation_key="service_remaining_days",
        field="service_remaining_days",
        group="vehicle",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:calendar-clock",
    ),
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

BATTERY_SENSORS = (
    NinebotSensorDescription(
        key="charging_power",
        translation_key="charging_power",
        field="charging_power",
        group="battery",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NinebotSensorDescription(
        key="backup_battery",
        translation_key="backup_battery",
        field="backup_battery",
        group="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NinebotSensorDescription(
        key="battery_details_at",
        translation_key="battery_details_at",
        field="battery_details_at",
        group="battery",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)

PACK_SENSORS = (
    NinebotSensorDescription(
        key="voltage",
        translation_key="pack_voltage",
        field="voltage",
        group="battery",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NinebotSensorDescription(
        key="temperature",
        translation_key="pack_temperature",
        field="temperature",
        group="battery",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NinebotSensorDescription(
        key="electricity",
        translation_key="pack_electricity",
        field="electricity",
        group="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NinebotSensorDescription(
        key="cycles",
        translation_key="pack_cycles",
        field="cycles",
        group="battery",
        icon="mdi:counter",
    ),
    NinebotSensorDescription(
        key="score",
        translation_key="pack_score",
        field="score",
        group="battery",
        icon="mdi:star",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: NinebotConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    known: set[tuple[str, str]] = set()

    @callback
    def add_new() -> None:
        coordinator = entry.runtime_data
        entities = []
        for sn in coordinator.vehicles:
            descriptions = list(SENSORS)
            if not coordinator.show_location:
                descriptions = [d for d in descriptions if d.key != "location_at"]
            if coordinator.battery_enabled:
                descriptions.extend(BATTERY_SENSORS)
                state = (coordinator.data or {}).get(sn)
                if state and state.battery_details:
                    for slot in range(len(state.battery_details.packs)):
                        descriptions.extend(
                            replace(
                                d,
                                key=f"battery_{slot + 1}_{d.key}",
                                slot=slot,
                                translation_placeholders={"slot": str(slot + 1)},
                            )
                            for d in PACK_SENSORS
                        )
            for description in descriptions:
                key = (sn, description.key)
                if key not in known:
                    known.add(key)
                    entities.append(NinebotSensor(coordinator, sn, description))
        async_add_entities(entities)

    add_new()
    entry.async_on_unload(entry.runtime_data.async_add_listener(add_new))


class NinebotSensor(NinebotEntity, SensorEntity):
    entity_description: NinebotSensorDescription

    def __init__(self, coordinator, sn: str, description: NinebotSensorDescription) -> None:
        super().__init__(coordinator, sn, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        description = self.entity_description
        field = description.field
        if description.group == "vehicle":
            return getattr(self.coordinator.vehicles[self.sn], field)
        if description.group == "battery":
            if field == "battery_details_at":
                return self.vehicle_state.battery_details_at
            details = self.vehicle_state.battery_details
            if details is None:
                return None
            if description.slot is not None:
                if description.slot >= len(details.packs):
                    return None
                return getattr(details.packs[description.slot], field)
            return getattr(details, field)
        return getattr(self.vehicle_state, field)

    @property
    def available(self) -> bool:
        if self.entity_description.group != "battery":
            return super().available
        state = self.vehicle_state
        slot = self.entity_description.slot
        return (
            self.coordinator.last_update_success
            and state.battery_details_available
            and state.battery_details is not None
            and (slot is None or slot < len(state.battery_details.packs))
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        slot = self.entity_description.slot
        details = self.vehicle_state.battery_details
        if slot is None or details is None or slot >= len(details.packs):
            return super().extra_state_attributes
        return {
            **super().extra_state_attributes,
            "battery_slot": slot + 1,
            "cycle_count_supported": details.packs[slot].cycle_supported,
        }
