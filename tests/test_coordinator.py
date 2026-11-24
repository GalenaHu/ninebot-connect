"""Account polling contracts, including removal and per-car failures."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ninebot_connect.api import ApiError, AuthenticationError, RateLimited
from custom_components.ninebot_connect.coordinator import NinebotCoordinator
from custom_components.ninebot_connect.models import BatteryDetails, Vehicle, VehicleState

CAR_A = Vehicle("TEST-A", "Vehicle A", "Model", "118")
CAR_B = Vehicle("TEST-B", "Vehicle B", "Model", "118")


def coordinator(hass, options=None):
    entry = MagicMock(options=options or {})
    entry.pref_disable_polling = False
    client = MagicMock()
    client.async_list_vehicles = AsyncMock(return_value=[CAR_A, CAR_B])
    client.async_vehicle_state = AsyncMock(return_value=VehicleState(battery=93))
    client.async_power_state = AsyncMock(return_value=None)
    client.async_battery_details = AsyncMock(return_value=BatteryDetails())
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


async def test_rate_limit_stops_queued_vehicle_requests_immediately(hass):
    c = coordinator(hass)
    c.client.async_list_vehicles.return_value = [
        Vehicle(f"CAR-{i}", "Synthetic", "Model", "118") for i in range(12)
    ]
    c.client.async_vehicle_state.side_effect = RateLimited(300)
    with pytest.raises(UpdateFailed):
        await c._async_update_data()
    # The first synchronous mock failure latches the pause before others start.
    assert c.client.async_vehicle_state.await_count == 1


async def test_successfully_empty_list_is_still_cached_hourly(hass):
    c = coordinator(hass)
    c.client.async_list_vehicles.return_value = []
    assert await c._async_update_data() == {}
    assert await c._async_update_data() == {}
    assert c.client.async_list_vehicles.await_count == 1


async def test_adaptive_polling_is_per_vehicle_and_keeps_independent_battery_due_times(
    hass, monkeypatch
):
    from custom_components.ninebot_connect import coordinator as module

    clock = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    c = coordinator(hass, {"adaptive_polling": True, "battery_details": True})

    async def state(vehicle):
        return VehicleState(battery=93, charging=vehicle == CAR_A, reported_at=datetime.now(UTC))

    c.client.async_vehicle_state.side_effect = state
    c.data = await c._async_update_data()
    first_b_time = c.data[CAR_B.sn].fetched_at
    assert c.update_interval.total_seconds() == 30
    assert c.client.async_battery_details.await_count == 2
    clock[0] += 30
    c.data = await c._async_update_data()
    assert c.client.async_vehicle_state.await_count == 3  # only charging vehicle due
    assert c.client.async_battery_details.await_count == 2
    assert c.data[CAR_B.sn].fetched_at == first_b_time
    clock[0] += 30
    c.data = await c._async_update_data()
    assert c.client.async_battery_details.await_count == 3  # charging BMS at 60s


async def test_battery_failure_backs_off_without_hiding_basic_data(hass, monkeypatch):
    from custom_components.ninebot_connect import coordinator as module

    clock = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    c = coordinator(hass, {"adaptive_polling": True})
    c.client.async_list_vehicles.return_value = [CAR_A]
    c.client.async_vehicle_state.return_value = VehicleState(
        battery=93,
        charging=True,
        reported_at=datetime.now(UTC),
    )
    c.client.async_battery_details.side_effect = ApiError("Unsupported")
    c.data = await c._async_update_data()
    assert c.data[CAR_A.sn].available and c.data[CAR_A.sn].battery == 93
    assert not c.data[CAR_A.sn].battery_details_available
    clock[0] += 60
    c.data = await c._async_update_data()
    assert c.client.async_vehicle_state.await_count == 2
    assert c.client.async_battery_details.await_count == 1  # no fast retry of unsupported BMS


async def test_rate_limit_after_partial_success_requeries_unsaved_groups_after_pause(
    hass, monkeypatch
):
    from custom_components.ninebot_connect import coordinator as module

    clock = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    c = coordinator(hass, {"poll_interval": 3600})
    c.client.async_list_vehicles.return_value = [CAR_A]
    c.data = {CAR_A.sn: VehicleState(battery=50)}
    c.client.async_battery_details.side_effect = [RateLimited(300), BatteryDetails()]
    with pytest.raises(UpdateFailed):
        await c._async_update_data()
    with pytest.raises(UpdateFailed):
        await c._async_update_data()
    assert c.client.async_vehicle_state.await_count == 1
    clock[0] += 300
    result = await c._async_update_data()
    assert result[CAR_A.sn].battery == 93
    assert c.client.async_vehicle_state.await_count == 2


@pytest.mark.parametrize("auto,age", [(False, 0), (True, None), (True, 600), (True, -300)])
async def test_old_configuration_or_stale_report_does_not_enable_fast_polling(hass, auto, age):
    c = coordinator(hass, {"adaptive_polling": auto})
    c.client.async_list_vehicles.return_value = [CAR_A]
    c.client.async_vehicle_state.return_value = VehicleState(
        acc_on=True,
        charging=True,
        reported_at=datetime.now(UTC) - timedelta(seconds=age) if age is not None else None,
    )
    await c._async_update_data()
    assert c.update_interval.total_seconds() == 120


async def test_power_failure_does_not_hide_basic_and_location_option_discards_coordinates(hass):
    c = coordinator(hass, {"show_location": False, "battery_details": False})
    c.client.async_list_vehicles.return_value = [CAR_A]
    c.client.async_vehicle_state.return_value = VehicleState(
        battery=93,
        latitude=39.9,
        longitude=116.4,
    )
    c.client.async_power_state.side_effect = ApiError("Unsupported")
    result = await c._async_update_data()
    assert result[CAR_A.sn].available
    assert result[CAR_A.sn].battery == 93
    assert result[CAR_A.sn].power_on is None
    assert result[CAR_A.sn].latitude is result[CAR_A.sn].longitude is None
    c.client.async_battery_details.assert_not_awaited()


async def test_stopping_vehicle_has_bounded_transition_window(hass, monkeypatch):
    from custom_components.ninebot_connect import coordinator as module

    clock = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    c = coordinator(hass, {"adaptive_polling": True})
    c.client.async_list_vehicles.return_value = [CAR_A]
    c.client.async_power_state.return_value = None
    c.client.async_vehicle_state.return_value = VehicleState(
        acc_on=True,
        reported_at=datetime.now(UTC),
    )
    c.data = await c._async_update_data()
    clock[0] += 30
    c.client.async_vehicle_state.return_value = VehicleState(
        acc_on=False,
        reported_at=datetime.now(UTC),
    )
    c.data = await c._async_update_data()
    assert c.update_interval.total_seconds() == 30
    clock[0] += 90
    await c._async_update_data()
    assert c.update_interval.total_seconds() == 120
