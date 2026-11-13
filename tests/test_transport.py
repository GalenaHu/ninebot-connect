"""Real aiohttp transport against local test servers; never hits Ninebot."""

import gzip

import aiohttp
import pytest
from aiohttp import web

from custom_components.ninebot_connect import api
from custom_components.ninebot_connect.api import (
    ApiError,
    CannotConnect,
    NinebotClient,
    RateLimited,
)
from custom_components.ninebot_connect.const import LOGIN_PATH, MAX_RESPONSE_BYTES


@pytest.fixture
async def endpoint(aiohttp_server, monkeypatch):
    async def make(handler):
        app = web.Application()
        app.router.add_post(LOGIN_PATH, handler)
        server = await aiohttp_server(app)
        host = str(server.make_url("")).rstrip("/")
        monkeypatch.setattr(api, "ALLOWED_ROUTES", frozenset({(host, LOGIN_PATH)}))
        return host

    return make


async def test_redirect_is_refused_and_credentials_never_forwarded(endpoint):
    called = []

    async def handler(request):
        called.append(request.path)
        return web.Response(status=302, headers={"Location": "/collect"})

    host = await endpoint(handler)
    async with aiohttp.ClientSession() as http:
        with pytest.raises(CannotConnect):
            await NinebotClient(http)._post(host, LOGIN_PATH, {"password": "PRIVATE"}, {})
    assert called == [LOGIN_PATH]


async def test_large_decompressed_response_is_rejected(endpoint):
    async def handler(request):
        return web.Response(
            body=gzip.compress(b"x" * (MAX_RESPONSE_BYTES + 1)),
            headers={"Content-Encoding": "gzip"},
        )

    host = await endpoint(handler)
    async with aiohttp.ClientSession() as http:
        with pytest.raises(ApiError, match="Response too large"):
            await NinebotClient(http)._post(host, LOGIN_PATH, {}, {})


async def test_http_rate_limit_honors_bounded_retry_after(endpoint):
    async def handler(request):
        return web.Response(status=429, headers={"Retry-After": "600"})

    host = await endpoint(handler)
    async with aiohttp.ClientSession() as http:
        with pytest.raises(RateLimited) as error:
            await NinebotClient(http)._post(host, LOGIN_PATH, {}, {})
    assert error.value.retry_after == 600


async def test_malformed_private_response_never_enters_error_text(endpoint):
    async def handler(request):
        return web.Response(body=b"PRIVATE-token")

    host = await endpoint(handler)
    async with aiohttp.ClientSession() as http:
        with pytest.raises(ApiError) as error:
            await NinebotClient(http)._post(host, LOGIN_PATH, {}, {})
    assert "PRIVATE" not in str(error.value)
