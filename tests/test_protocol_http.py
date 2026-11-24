"""Entire encrypted protocol over HTTP with a synthetic gateway and RSA key."""

import base64
import hashlib
import json

import aiohttp
from aiohttp import web
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from custom_components.ninebot_connect import api, crypto
from custom_components.ninebot_connect.const import (
    BATTERY_PATH,
    BUSINESS_LOGIN_PATH,
    DYNAMIC_PATH,
    LIST_PATH,
    LOGIN_PATH,
    STATUS_PATH,
)


async def test_password_to_encrypted_vehicle_query(aiohttp_server, monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    monkeypatch.setattr(
        crypto,
        "RSA_PUBLIC_KEY_PEM",
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
    )
    observed = []

    async def gateway(request):
        observed.append(request.path)
        body = await request.json()
        if request.path == LOGIN_PATH:
            assert body == {
                "areaCode": "86",
                "device": "ANDROID",
                "username": "synthetic-user",
                "password": "synthetic-password",
            }
            assert request.headers["Clientid"] == "vehicle_app_prod"
            assert len(request.headers["Sign"]) == 64
            return web.json_response(
                {
                    "resultCode": "90000",
                    "data": {
                        "access_token": "synthetic-access",
                        "refresh_token": "synthetic-refresh",
                        "uuid": "synthetic-account",
                    },
                }
            )
        # The test server independently recovers the request AES key using RSA.
        key = private_key.decrypt(base64.b64decode(body["k"]), padding.PKCS1v15())
        plain = crypto._aes_cbc_decrypt(key, base64.b64decode(body["d"]))
        assert hashlib.md5(plain).hexdigest() == body["h"]
        wrapper = json.loads(plain)
        inner = json.loads(base64.b64decode(wrapper["data"]))
        checkcode = inner.pop("checkcode")
        assert (
            hashlib.md5(json.dumps(inner, separators=(",", ":")).encode()).hexdigest().upper()
            == checkcode
        )
        assert inner["access_token"] == "synthetic-access"
        assert inner["device_id"] == "synthetic-device"
        if request.path == BUSINESS_LOGIN_PATH:
            assert request.headers["Business-Type"] == "0"
            assert "Access-Token" not in request.headers
            assert inner["uuid"] == "synthetic-account"
            data = {"uid": "synthetic-business"}
        else:
            assert request.headers["Access-Token"] == "synthetic-access"
            assert request.headers["Access_token"] == "synthetic-access"
            assert request.headers["Uid"] == "synthetic-business"
            if request.path == LIST_PATH:
                data = [
                    {
                        "wnumber": "SYNTHETIC-SN",
                        "vehicle_type": 118,
                        "device_name": "Synthetic",
                        "owner_phone": "PRIVATE",
                    }
                ]
            else:
                assert inner["wnumber"] == "SYNTHETIC-SN"
                assert inner["vehicle_type"] == "118"
                data = {
                    "dump_energy": 93,
                    "precise_estimate_mileage": 36.7,
                    "charging": 0,
                    "pwr": 1,
                    "latitude": 39.9,
                    "longitude": 116.4,
                }
                if request.path == STATUS_PATH:
                    data = {"power_status": 0}
                elif request.path == BATTERY_PATH:
                    data = {
                        "battery_list": [{"bms_volt": 53.2, "bat_temp": 25}],
                        "charging_power": 0,
                    }
        response = json.dumps(
            {
                "data": base64.b64encode(
                    json.dumps(
                        {
                            "code": 1,
                            "data": data,
                        }
                    ).encode()
                ).decode()
            }
        ).encode()
        response_key = crypto.derive_key(
            *(
                wrapper[k].encode()
                for k in (
                    "keyDataOne",
                    "keyDataTwo",
                    "keyDataThree",
                    "keyDataFour",
                )
            )
        )
        return web.json_response(
            {
                "r": base64.b64encode(
                    crypto._aes_cbc_encrypt(
                        response_key,
                        response,
                    )
                ).decode()
            }
        )

    app = web.Application()
    for path in (
        LOGIN_PATH,
        BUSINESS_LOGIN_PATH,
        LIST_PATH,
        DYNAMIC_PATH,
        STATUS_PATH,
        BATTERY_PATH,
    ):
        app.router.add_post(path, gateway)
    server = await aiohttp_server(app)
    host = str(server.make_url("")).rstrip("/")
    for name in ("PASSPORT", "BUSINESS", "VEHICLES"):
        monkeypatch.setattr(api, name, host)
    monkeypatch.setattr(
        api,
        "ALLOWED_ROUTES",
        frozenset(
            (host, p)
            for p in (
                LOGIN_PATH,
                BUSINESS_LOGIN_PATH,
                LIST_PATH,
                DYNAMIC_PATH,
                STATUS_PATH,
                BATTERY_PATH,
            )
        ),
    )
    async with aiohttp.ClientSession() as http:
        client = api.NinebotClient(http)
        session = await client.async_login(
            "synthetic-user", "synthetic-password", "synthetic-device"
        )
        assert session.uuid == "synthetic-account"
        vehicles = await client.async_list_vehicles()
        state = await client.async_vehicle_state(vehicles[0])
        assert await client.async_power_state(vehicles[0]) is False
        details = await client.async_battery_details(vehicles[0])
        assert details.packs[0].voltage == 53.2
        assert details.charging_power == 0
    assert (state.battery, state.range_km, state.charging) == (93, 36.7, False)
    assert observed == [
        LOGIN_PATH,
        BUSINESS_LOGIN_PATH,
        LIST_PATH,
        DYNAMIC_PATH,
        STATUS_PATH,
        BATTERY_PATH,
    ]
    assert "PRIVATE" not in repr(vehicles)
