"""Async, bounded client for verified Ninebot routes.

Never retain passwords, raw vehicle responses or arbitrary server messages.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
import hashlib
import json
import secrets
import time
from typing import Any

import aiohttp

from . import crypto
from .const import (
    ALLOWED_ROUTES, BUSINESS, BUSINESS_LOGIN_PATH, CLIENT_KEY, CLIENT_VERSION,
    DYNAMIC_PATH, LIST_PATH, LOGIN_PATH, MAX_RESPONSE_BYTES, PASSPORT,
    REFRESH_PATH, VEHICLES,
)
from .models import AccountSession, Vehicle, VehicleState, project_vehicle_state


class ApiError(Exception):
    """Sanitized protocol error; no server text or request included."""


class AuthenticationError(ApiError):
    """Session is no longer usable; human reauthentication required."""


class CannotConnect(ApiError):
    """Network/TLS/HTTP transport failed."""


class VerificationRequired(ApiError):
    """Login requires additional verification in the official app."""


class RateLimited(ApiError):
    """Honor the bounded Retry-After header without an immediate retry."""

    def __init__(self, retry_after: int = 300) -> None:
        super().__init__("Request rate limited")
        self.retry_after = retry_after


class _TokenExpired(ApiError):
    """Internal signal for the one supported automatic refresh attempt."""


def code_of(value: Any) -> int | None:
    if type(value) is int:
        return value
    if isinstance(value, str) and len(value) < 12:
        try:
            return int(value)
        except ValueError:
            pass
    return None


def passport_signature(path: str, fields: dict[str, Any]) -> str:
    values = {**fields, "clientKey": CLIENT_KEY, "url": path}
    canonical = "&".join(f"{key}={value}" for key, value in sorted(values.items()))
    return hashlib.sha256(canonical.encode()).hexdigest()


class NinebotClient:
    """Owns one session and serializes refresh, not the shared HTTP session."""

    def __init__(
        self, http: aiohttp.ClientSession, session: AccountSession | None = None,
        on_session_changed: Callable[[AccountSession], Awaitable[None]] | None = None,
    ) -> None:
        self.http = http
        self.session = session
        self._on_session_changed = on_session_changed
        self._refresh_lock = asyncio.Lock()
        self._auth_failed = False

    async def _post(
        self, host: str, path: str, body: dict, headers: dict[str, str],
    ) -> dict[str, Any]:
        if (host, path) not in ALLOWED_ROUTES:
            raise ApiError("Route refused")
        try:
            async with self.http.post(
                host + path, data=json.dumps(body, separators=(",", ":")).encode(),
                headers=headers, allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as response:
                if response.status == 429:
                    retry = response.headers.get("Retry-After", "300")
                    delay = int(retry) if retry.isdigit() and len(retry) < 8 else 300
                    raise RateLimited(min(3600, max(30, delay)))
                if response.status == 401:
                    raise _TokenExpired("Session expired")
                if response.status != 200:
                    raise CannotConnect("Unexpected HTTP status")
                raw = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise ApiError("Response too large")
        except (aiohttp.ClientError, TimeoutError, OSError):
            raise CannotConnect("Network or TLS request failed") from None
        try:
            decoded = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ApiError("Invalid JSON response") from None
        if not isinstance(decoded, dict):
            raise ApiError("Unexpected response structure")
        return decoded

    async def _passport(self, path: str, body: dict[str, str]) -> dict[str, Any]:
        timestamp = str(int(time.time() * 1000))
        signed = {**body, "app_version": CLIENT_VERSION, "os": "Android",
                  "os_language": "zh-hans-cn", "os_version": "13", "timestamp": timestamp}
        headers = {
            "App_version": CLIENT_VERSION, "Clientid": "vehicle_app_prod",
            "Content-Type": "application/json; charset=UTF-8", "Os": "Android",
            "Os_language": "zh-hans-cn", "Os_version": "13", "Timestamp": timestamp,
            "Sign": passport_signature(path, signed),
        }
        response = await self._post(PASSPORT, path, body, headers)
        code = code_of(response.get("resultCode", response.get("code")))
        if code != 90000:
            if code == 90016:
                raise _TokenExpired("Session expired")
            # SDK messages are used only for classification, never surfaced or stored.
            desc = response.get("resultDesc", response.get("desc", ""))
            desc = desc.lower() if isinstance(desc, str) else ""
            if any(term in desc for term in ("captcha", "验证码", "风控", "verification")):
                raise VerificationRequired("Additional verification required")
            if path == LOGIN_PATH:
                raise AuthenticationError("Login rejected")
            raise AuthenticationError("Session renewal rejected")
        data = response.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("access_token"), str):
            raise ApiError("Incomplete authentication response")
        if not data["access_token"]:
            raise ApiError("Empty authentication token")
        return data

    @staticmethod
    def _common(session: AccountSession) -> dict[str, Any]:
        return {"sys_language": "zh-hans-cn", "client_ver": CLIENT_VERSION,
                "device_id": session.device_id, "regionx": "bj", "language": "zh",
                "ostype": "and", "lang": "zh", "platform_ver": "13 Xiaomi",
                "platform": "android", "login_country": "CN"}

    @staticmethod
    def _headers(session: AccountSession, login: bool) -> dict[str, str]:
        result = {
            "User-Agent": "okhttp/4.9.1", "Business-Type": "0" if login else "2",
            "Client-Ver": CLIENT_VERSION, "Content-Type": "text/html;charset=UTF-8",
            "Debug": "0", "Device-Id": session.device_id, "Language": "zh",
            "Login-Country": "CN", "Need_decrypt": "1", "Ninebot-Version": "2",
            "Platform": "Android", "Platform-Ver": "13", "Regionx": "bj",
            "Request-Id": secrets.token_hex(16), "Service-Time": str(int(time.time() * 1000)),
            "Sys-Language": "zh-hans-cn", "Accept": "application/json",
        }
        if not login:
            result.update({"Access_token": session.access_token, "Access-Token": session.access_token,
                           "Uid": session.business_uid, "Rn-Module": "Track",
                           "Rn-Ver": "743", "Rn-Version": "0"})
        return result

    async def _business(
        self, session: AccountSession, path: str, vehicle: Vehicle | None = None,
    ) -> Any:
        login = path == BUSINESS_LOGIN_PATH
        params = self._common(session)
        params["access_token"] = session.access_token
        if login:
            params.update({"uuid": session.uuid, "token": session.access_token,
                           "refresh_token": session.refresh_token, "region": "bj"})
        else:
            params["uid"] = session.business_uid
            if vehicle is not None:
                params["wnumber"] = vehicle.sn
            params["vehicle_type"] = vehicle.vehicle_type if vehicle else "64"
        params.update({"serviceTime": int(time.time() * 1000), "nonce": crypto.gen_nonce()})
        wire, material = await asyncio.to_thread(
            crypto.build_request, crypto.build_inner(params).encode(),
        )
        response = await self._post(
            BUSINESS if login else VEHICLES, path, wire, self._headers(session, login),
        )
        # Some gateway errors arrive as plain JSON instead of an encrypted envelope.
        if "r" in response:
            try:
                plain = await asyncio.to_thread(crypto.decrypt_wire_response, response, material)
                response = json.loads(plain)
            except (ValueError, KeyError, TypeError, UnicodeError):
                raise ApiError("Invalid encrypted response") from None
        if not isinstance(response, dict):
            raise ApiError("Unexpected business response")
        code = code_of(response.get("code"))
        if code == 90016:
            raise _TokenExpired("Session expired")
        if code not in (0, 1):
            raise ApiError("Business request rejected")
        return response.get("data")

    async def _business_session(self, pending: AccountSession) -> AccountSession:
        data = await self._business(pending, BUSINESS_LOGIN_PATH)
        uid = data.get("uid") if isinstance(data, dict) else None
        if type(uid) not in (str, int) or not str(uid):
            raise ApiError("Business identity missing")
        return replace(pending, business_uid=str(uid))

    async def async_login(
        self, username: str, password: str, device_id: str | None = None,
    ) -> AccountSession:
        try:
            data = await self._passport(LOGIN_PATH, {
                "areaCode": "86", "device": "ANDROID", "password": password, "username": username,
            })
            uuid = data.get("uuid")
            refresh = data.get("refresh_token")
            if not isinstance(uuid, str) or not uuid or not isinstance(refresh, str) or not refresh:
                raise ApiError("Incomplete account identity or renewal token")
            pending = AccountSession(data["access_token"], refresh, uuid, "",
                                     device_id or secrets.token_hex(16))
            session = await self._business_session(pending)
        except _TokenExpired:
            raise AuthenticationError("Login session rejected") from None
        self.session = session
        self._auth_failed = False
        return session

    async def _refresh(self, previous: AccountSession) -> None:
        async with self._refresh_lock:
            if self._auth_failed:
                raise AuthenticationError("Reauthentication required")
            if self.session is not previous:
                return
            if not previous.refresh_token:
                self._auth_failed = True
                raise AuthenticationError("Renewal token missing")
            try:
                data = await self._passport(REFRESH_PATH, {
                    "access_token": previous.access_token,
                    "refresh_token": previous.refresh_token, "device": "ANDROID",
                })
                uuid = data.get("uuid", previous.uuid)
                if uuid != previous.uuid:
                    raise AuthenticationError("Account identity changed")
                refresh = data.get("refresh_token", previous.refresh_token)
                if not isinstance(refresh, str) or not refresh:
                    raise ApiError("Invalid renewal response")
                updated = await self._business_session(replace(
                    previous, access_token=data["access_token"], refresh_token=refresh,
                ))
                if updated.business_uid != previous.business_uid:
                    raise AuthenticationError("Business account identity changed")
            except (CannotConnect, RateLimited):
                raise
            except ApiError:
                self._auth_failed = True
                raise AuthenticationError("Reauthentication required") from None
            # Persist a complete pair atomically before queries see the new session.
            if self._on_session_changed:
                await self._on_session_changed(updated)
            self.session = updated

    async def _query(self, path: str, vehicle: Vehicle | None = None) -> Any:
        if self.session is None or self._auth_failed:
            raise AuthenticationError("Reauthentication required")
        previous = self.session
        try:
            return await self._business(previous, path, vehicle)
        except _TokenExpired:
            await self._refresh(previous)
        assert self.session is not None
        try:
            return await self._business(self.session, path, vehicle)
        except _TokenExpired:
            self._auth_failed = True
            raise AuthenticationError("Renewed session rejected") from None

    async def async_list_vehicles(self) -> list[Vehicle]:
        data = await self._query(LIST_PATH)
        if not isinstance(data, list):
            raise ApiError("Vehicle list missing")
        vehicles: dict[str, Vehicle] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            sn = item.get("wnumber")
            if not isinstance(sn, str) or not sn:
                continue
            name = item.get("device_name") or item.get("ble_name")
            model = item.get("vehicle_name") or item.get("vehicle_name_en")
            kind = item.get("vehicle_type")
            if type(kind) not in (str, int) or not str(kind):
                continue
            vehicles[sn] = Vehicle(sn, name if isinstance(name, str) else "九号电动车",
                                   model if isinstance(model, str) else "Ninebot", str(kind))
        return list(vehicles.values())

    async def async_vehicle_state(self, vehicle: Vehicle) -> VehicleState:
        data = await self._query(DYNAMIC_PATH, vehicle)
        if not isinstance(data, dict):
            raise ApiError("Vehicle state missing")
        return project_vehicle_state(data)
