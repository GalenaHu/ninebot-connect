"""Cloud GPS position in WGS84, with the cloud fix time attached."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NinebotConfigEntry
from .entity import NinebotEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: NinebotConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    known: set[str] = set()

    @callback
    def add_new() -> None:
        fresh = set(entry.runtime_data.vehicles) - known
        known.update(fresh)
        async_add_entities(NinebotTracker(entry.runtime_data, sn, "location") for sn in fresh)

    add_new()
    entry.async_on_unload(entry.runtime_data.async_add_listener(add_new))


class NinebotTracker(NinebotEntity, TrackerEntity):
    _attr_translation_key = "location"
    _attr_source_type = SourceType.GPS
    _attr_icon = "mdi:moped-electric"

    @property
    def latitude(self) -> float | None:
        return self.vehicle_state.latitude

    @property
    def longitude(self) -> float | None:
        return self.vehicle_state.longitude

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        time = self.vehicle_state.location_at
        return {
            "location_reported_at": time.isoformat() if time else None,
            "coordinate_system": "WGS84",
        }
