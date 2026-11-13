"""HTTP allowlist, redirects, byte limits and sanitized errors."""
import json

import aiohttp
from aioresponses import aioresponses
import pytest

from custom_components.ninebot_connect.api import ApiError, CannotConnect, NinebotClient, RateLimited
from custom_components.ninebot_connect.const import LOGIN_PATH, PASSPORT, MAX_RESPONSE_BYTES


async def test_redirect_is_refused_and_credentials_never_forwarded():
    async with aiohttp.ClientSession() as http:
        with aioresponses() as mock:
            mock.post(PASSPORT + LOGIN_PATH, status=302,
                      headers={"Location": "https://attacker.example/collect"})
            with pytest.raises(CannotConnect):
                await NinebotClient(http)._post(PASSPORT, LOGIN_PATH, {"password": "PRIVATE"}, {})
            assert len(mock.requests) == 1


async def test_large_decoded_response_is_rejected():
    async with aiohttp.ClientSession() as http:
        with aioresponses() as mock:
            mock.post(PASSPORT + LOGIN_PATH, body="x" * (MAX_RESPONSE_BYTES + 1))
            with pytest.raises(ApiError, match="Response too large"):
                await NinebotClient(http)._post(PASSPORT, LOGIN_PATH, {}, {})


async def test_http_rate_limit_honors_bounded_retry_after():
    async with aiohttp.ClientSession() as http:
        with aioresponses() as mock:
            mock.post(PASSPORT + LOGIN_PATH, status=429, headers={"Retry-After": "600"})
            with pytest.raises(RateLimited) as error:
                await NinebotClient(http)._post(PASSPORT, LOGIN_PATH, {}, {})
            assert error.value.retry_after == 600


async def test_malformed_private_response_never_enters_error_text():
    async with aiohttp.ClientSession() as http:
        with aioresponses() as mock:
            mock.post(PASSPORT + LOGIN_PATH, body="PRIVATE-token")
            with pytest.raises(ApiError) as error:
                await NinebotClient(http)._post(PASSPORT, LOGIN_PATH, {}, {})
            assert "PRIVATE" not in str(error.value)
