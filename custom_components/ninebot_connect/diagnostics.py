"""Strictly allowlisted diagnostics: no account, vehicle or location identifiers."""

from homeassistant.core import HomeAssistant

from . import NinebotConfigEntry
from .const import VERSION


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NinebotConfigEntry
) -> dict:
    coordinator = entry.runtime_data
    states = coordinator.data or {}
    return {
        "integration_version": VERSION,
        "poll_interval_seconds": coordinator.update_interval.total_seconds()
        if coordinator.update_interval
        else None,
        "vehicle_count": len(coordinator.vehicles),
        "available_vehicle_count": sum(state.available for state in states.values()),
        "last_update_success": coordinator.last_update_success,
        "has_refresh_token": bool(
            coordinator.client.session and coordinator.client.session.refresh_token
        ),
    }
