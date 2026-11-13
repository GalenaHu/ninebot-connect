"""Public state projection expectations; synthetic records only."""
from datetime import UTC, datetime

from custom_components.ninebot_connect.models import AccountSession, project_vehicle_state


def test_projection_keeps_verified_units_and_wgs84_and_discards_private_fields():
    state = project_vehicle_state({
        "dump_energy": 93, "precise_estimate_mileage": 36.7,
        "charging": 0, "pwr": 1, "lock_status": 1, "total_mileage": 123.4,
        "latitude": 39.9, "longitude": 116.4, "gnss_time": 1_700_000_000,
        "lastupdatetime": 1_700_000_001_000,
        "owner_phone": "PRIVATE", "blue_secret": "PRIVATE",
    })
    assert state.battery == 93
    assert state.range_km == 36.7
    assert state.charging is False
    assert state.main_battery_online is True
    assert state.lock_status == 1
    assert (state.latitude, state.longitude) == (39.9, 116.4)
    assert state.location_at == datetime.fromtimestamp(1_700_000_000, UTC)
    assert state.reported_at == datetime.fromtimestamp(1_700_000_001, UTC)
    assert "PRIVATE" not in repr(state)


def test_invalid_fields_stay_unknown_and_never_make_fake_location():
    state = project_vehicle_state({
        "dump_energy": 101, "precise_estimate_mileage": "nan",
        "charging": 2, "pwr": -1, "lock_status": 3,
        "latitude": 0, "longitude": 0,
    })
    assert state.battery is state.range_km is state.charging is None
    assert state.main_battery_online is state.lock_status is None
    assert state.latitude is state.longitude is None


def test_session_storage_is_an_allowlist():
    session = AccountSession("access", "refresh", "account", "uid", "device")
    assert AccountSession.from_storage({**session.to_storage(), "password": "secret"}) == session
    assert "password" not in session.to_storage()
    assert "access" not in repr(session)
