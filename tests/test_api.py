"""Authentication/transport seams, with synthetic server responses only."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from custom_components.ninebot_connect.api import (
    ApiError,
    AuthenticationError,
    NinebotClient,
    _TokenExpired,
    passport_signature,
)
from custom_components.ninebot_connect.const import (
    BUSINESS_LOGIN_PATH,
    DYNAMIC_PATH,
    LIST_PATH,
    LOGIN_PATH,
    REFRESH_PATH,
)
from custom_components.ninebot_connect.models import AccountSession, Vehicle

SESSION = AccountSession("access-old", "refresh-old", "account", "business", "device")


@pytest.mark.parametrize("code", [90000, "90000"])
async def test_password_login_uses_sdk_success_and_stores_no_password(code):
    client = NinebotClient(None)
    client._post = AsyncMock(
        return_value={
            "resultCode": code,
            "data": {
                "access_token": "access",
                "refresh_token": "refresh",
                "uuid": "account",
            },
        }
    )
    client._business = AsyncMock(return_value={"uid": "business"})
    session = await client.async_login("account-name", "password", "device")
    assert session.uuid == "account"
    assert "password" not in session.to_storage()
    body = client._post.call_args.args[2]
    assert body == {
        "areaCode": "86",
        "device": "ANDROID",
        "password": "password",
        "username": "account-name",
    }
    assert client._post.call_args.args[1] == LOGIN_PATH
    assert client._business.call_args.args[1] == BUSINESS_LOGIN_PATH


@pytest.mark.parametrize("code", [0, 1, "1", None])
async def test_business_success_is_not_passport_success(code):
    client = NinebotClient(None)
    client._post = AsyncMock(return_value={"resultCode": code, "data": "private error"})
    with pytest.raises(AuthenticationError, match="Login rejected"):
        await client.async_login("account", "private-password")


async def test_refresh_rotates_tokens_once_under_concurrent_expiry_and_persists_identity():
    save = AsyncMock()
    client = NinebotClient(None, SESSION, save)
    client._passport = AsyncMock(
        return_value={
            "access_token": "access-new",
            "refresh_token": "refresh-new",
            "uuid": "account",
        }
    )

    async def business(session, path, vehicle=None):
        await asyncio.sleep(0)
        if path == BUSINESS_LOGIN_PATH:
            return {"uid": "business"}
        if session.access_token == "access-old":
            raise _TokenExpired("Expired")
        return []

    client._business = AsyncMock(side_effect=business)
    await asyncio.gather(client.async_list_vehicles(), client.async_list_vehicles())
    client._passport.assert_awaited_once_with(
        REFRESH_PATH,
        {
            "access_token": "access-old",
            "refresh_token": "refresh-old",
            "device": "ANDROID",
        },
    )
    save.assert_awaited_once()
    assert client.session.access_token == "access-new"
    assert client.session.device_id == SESSION.device_id
    assert client.session.refresh_token == "refresh-new"


async def test_failed_refresh_latches_reauth_instead_of_retry_storm():
    client = NinebotClient(None, SESSION)
    client._business = AsyncMock(side_effect=_TokenExpired("Expired"))
    client._passport = AsyncMock(side_effect=AuthenticationError("Rejected"))
    for _ in range(2):
        with pytest.raises(AuthenticationError):
            await client.async_list_vehicles()
    assert client._passport.await_count == 1


async def test_refresh_never_switches_accounts_or_persists_partial_pair():
    save = AsyncMock()
    client = NinebotClient(None, SESSION, save)
    client._business = AsyncMock(side_effect=_TokenExpired("Expired"))
    client._passport = AsyncMock(return_value={"access_token": "new", "uuid": "OTHER"})
    with pytest.raises(AuthenticationError):
        await client.async_list_vehicles()
    save.assert_not_called()
    assert client.session == SESSION


async def test_vehicle_list_projects_only_allowed_metadata():
    client = NinebotClient(None, SESSION)
    client._query = AsyncMock(
        return_value=[
            {
                "wnumber": "SN-test",
                "vehicle_type": 118,
                "device_name": "Synthetic vehicle",
                "vehicle_name": "Test model",
                "owner_phone": "PRIVATE",
                "blue_secret": "PRIVATE",
            }
        ]
    )
    assert await client.async_list_vehicles() == [
        Vehicle("SN-test", "Synthetic vehicle", "Test model", "118")
    ]
    client._query.assert_awaited_once_with(LIST_PATH)


async def test_dynamic_projection_uses_only_query_route():
    client = NinebotClient(None, SESSION)
    client._query = AsyncMock(return_value={"dump_energy": 93, "precise_estimate_mileage": 36.7})
    vehicle = Vehicle("SN-test", "Test", "Model", "118")
    state = await client.async_vehicle_state(vehicle)
    assert (state.battery, state.range_km) == (93, 36.7)
    client._query.assert_awaited_once_with(DYNAMIC_PATH, vehicle)


async def test_arbitrary_route_rejected_before_network():
    client = NinebotClient(None)
    with pytest.raises(ApiError, match="Route refused"):
        await client._post("https://attacker.example", LOGIN_PATH, {}, {})


def test_signature_is_fixed_sorted_raw_android_sha256():
    # Independent SHA256 fixture, deliberately containing characters not URL encoded.
    import hashlib

    from custom_components.ninebot_connect.const import CLIENT_KEY

    expected = hashlib.sha256(
        f"a=x&y&clientKey={CLIENT_KEY}&url=/v3/user/refresh&z=1".encode()
    ).hexdigest()
    assert passport_signature("/v3/user/refresh", {"z": "1", "a": "x&y"}) == expected
