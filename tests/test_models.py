"""Public state projection expectations; synthetic records only."""

from datetime import UTC, datetime

from custom_components.ninebot_connect.models import AccountSession, project_vehicle_state


def test_projection_keeps_verified_units_and_wgs84_and_discards_private_fields():
    state = project_vehicle_state(
        {
            "dump_energy": 93,
            "precise_estimate_mileage": 36.7,
            "charging": 0,
            "pwr": 1,
            "lock_status": 1,
            "total_mileage": 123.4,
            "latitude": 39.9,
            "longitude": 116.4,
            "gnss_time": 1_700_000_000,
            "lastupdatetime": 1_700_000_001_000,
            "owner_phone": "PRIVATE",
            "blue_secret": "PRIVATE",
        }
    )
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
    state = project_vehicle_state(
        {
            "dump_energy": 101,
            "precise_estimate_mileage": "nan",
            "charging": 2,
            "pwr": -1,
            "lock_status": 3,
            "latitude": 0,
            "longitude": 0,
        }
    )
    assert state.battery is state.range_km is state.charging is None
    assert state.main_battery_online is state.lock_status is None
    assert state.latitude is state.longitude is None


def test_session_storage_is_an_allowlist():
    session = AccountSession("access", "refresh", "account", "uid", "device")
    assert AccountSession.from_storage({**session.to_storage(), "password": "secret"}) == session
    assert "password" not in session.to_storage()
    assert "access" not in repr(session)


def test_extended_vehicle_fields_have_distinct_meanings():
    state = project_vehicle_state(
        {
            "estimate_mileage": 42.5,
            "ai_estimate_mileage": 40,
            "acc_status": 0,
            "pwr": 1,
            "battery_exist": 1,
        },
        {"power_status": 0},
    )
    assert state.estimated_range_km == 42.5
    assert state.ai_range_km == 40
    assert state.acc_on is False
    assert state.power_on is False
    assert state.main_battery_online is True
    assert state.battery_present is True
    # An unknown enum or absent power reply never means off.
    other = project_vehicle_state({"acc_status": 3, "estimate_mileage": -1})
    assert other.acc_on is other.power_on is other.estimated_range_km is None


def test_battery_details_keep_slot_positions_and_require_cycle_support():
    from custom_components.ninebot_connect.models import project_battery_details

    details = project_battery_details(
        {
            "charging_power": 180,
            "battery_main": {"electricity": 67},
            "have_bms_cycle_support": 0,
            "battery_list": [
                {
                    "bms_volt": 53.2,
                    "bat_temp": 25,
                    "bms_cycle": 0,
                    "have_bms_cycle_support": 1,
                    "score": 98,
                    "battery_sn": "PRIVATE",
                },
                None,
                {"bms_volt": 999, "bat_temp": "nan"},
            ],
        }
    )
    assert details.charging_power == 180
    assert details.backup_battery == 67
    assert details.packs[0].voltage == 53.2
    assert details.packs[0].temperature == 25
    assert details.packs[0].cycle_supported is False
    assert details.packs[0].cycles is None
    assert details.packs[0].score == 98
    assert details.packs[1].voltage is None
    assert details.packs[2].voltage is details.packs[2].temperature is None
    assert "PRIVATE" not in repr(details)
    supported = project_battery_details(
        {
            "have_bms_cycle_support": 1,
            "battery_list": [{"bms_cycle": 37}],
        }
    )
    assert supported.packs[0].cycles == 37
    unknown = project_battery_details({"battery_list": [{"bms_cycle": 0}]})
    assert unknown.packs[0].cycles is None


def test_boolean_support_flags_and_slot_limit():
    from custom_components.ninebot_connect.models import project_battery_details

    details = project_battery_details(
        {
            "have_bms_cycle_support": True,
            "battery_list": [{"bms_cycle": 0, "have_bms_cycle_support": "true"}] * 100,
        }
    )
    assert len(details.packs) == 8
    assert details.packs[0].cycles == 0
    assert details.packs[0].cycle_supported is True
