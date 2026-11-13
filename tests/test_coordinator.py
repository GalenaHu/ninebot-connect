"""Account polling contracts, including removal and per-car failures."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ninebot_connect.api import ApiError, AuthenticationError, RateLimited
from custom_components.ninebot_connect.coordinator import NinebotCoordinator
from custom_components.ninebot_connect.models import Vehicle, VehicleState

CAR_A = Vehicle("TEST-A", "Vehicle A", "Model", "118")
CAR_B = Vehicle("TEST-B", "Vehicle B", "Model", "118")


def coordinator(hass):
    entry = MagicMock(options={})
    entry.pref_disable_polling = False
    client = MagicMock()
    client.async_list_vehicles = AsyncMock(return_value=[CAR_A, CAR_B])
    client.async_vehicle_state = AsyncMock(return_value=VehicleState(battery=93))
    return NinebotCoordinator(hass, entry, client)


async def test_per_vehicle_failure_does_not_hide_other_vehicle(hass):
    c = coordinator(hass)
    async def state(vehicle):
        if vehicle == CAR_B:
            raise ApiError("Unavailable")
        return VehicleState(battery=93)
    c.client.async_vehicle_state.side_effect = state
    result = await c._async_update_data()
    assert result[CAR_A.sn].available and result[CAR_A.sn].battery == 93
    assert result[CAR_B.sn].available is False


async def test_removed_vehicle_retained_unavailable_and_list_cached(hass):
    c = coordinator(hass)
    c.data = await c._async_update_data()
    await c._async_update_data()
    assert c.client.async_list_vehicles.await_count == 1
    c._listed_at = 0
    c.client.async_list_vehicles.return_value = [CAR_A]
    result = await c._async_update_data()
    assert CAR_B.sn in c.vehicles
    assert result[CAR_B.sn].available is False
    assert result[CAR_A.sn].available


async def test_authentication_failure_requires_ha_reauth(hass):
    c = coordinator(hass)
    c.client.async_list_vehicles.side_effect = AuthenticationError("Expired")
    with pytest.raises(ConfigEntryAuthFailed):
        await c._async_update_data()


async def test_rate_limit_backoff_prevents_extra_requests(hass):
    c = coordinator(hass)
    c.client.async_list_vehicles.side_effect = RateLimited(300)
    for _ in range(2):
        with pytest.raises(UpdateFailed):
            await c._async_update_data()
    assert c.client.async_list_vehicles.await_count == 1
