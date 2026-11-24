"""Account polling with independent per-vehicle availability."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, AuthenticationError, NinebotClient, RateLimited
from .const import (
    CONF_ADAPTIVE,
    CONF_BATTERY_DETAILS,
    CONF_POLL_INTERVAL,
    CONF_SHOW_LOCATION,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .models import Vehicle, VehicleState

_LOGGER = logging.getLogger(__name__)


class NinebotCoordinator(DataUpdateCoordinator[dict[str, VehicleState]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: NinebotClient) -> None:
        self.client = client
        self.vehicles: dict[str, Vehicle] = {}
        self._listed_at: float | None = None
        self._active: set[str] = set()
        self.fetched_at: float | None = None
        self._backoff_until = 0.0
        self.configured_options = dict(entry.options)
        self.adaptive = bool(entry.options.get(CONF_ADAPTIVE, False))
        self.battery_enabled = bool(entry.options.get(CONF_BATTERY_DETAILS, True))
        self.show_location = bool(entry.options.get(CONF_SHOW_LOCATION, True))
        self.fixed_interval = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        self._due: dict[tuple[str, str], float] = {}
        self._failures: dict[tuple[str, str], int] = {}
        self._battery_checked: dict[str, float] = {}
        self._fast_until: dict[str, float] = {}
        self._force_refresh = False
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.fixed_interval),
        )

    async def async_request_refresh(self) -> None:
        """HA's manual update requests refresh groups without bypassing failure pauses."""
        self._force_refresh = True
        await super().async_request_refresh()

    def _periods(self, sn: str, state: VehicleState, now: float) -> tuple[int, int]:
        if not self.adaptive:
            return self.fixed_interval, max(600, self.fixed_interval)
        age = (datetime.now(UTC) - state.reported_at).total_seconds() if state.reported_at else None
        fresh = state.available and age is not None and -30 <= age <= 180
        if not fresh:
            return 120, 600
        charging = state.charging is True
        active = charging or state.acc_on is True or state.power_on is True
        transition = now < self._fast_until.get(sn, 0)
        return (
            30 if active or transition else 120,
            60 if charging else 120 if active or transition else 600,
        )

    def _failed(self, sn: str, group: str) -> None:
        key = (sn, group)
        count = self._failures[key] = min(7, self._failures.get(key, 0) + 1)
        base = 600 if group == "battery" else 120
        if not self.adaptive:
            base = max(base, self.fixed_interval)
        self._due[key] = time.monotonic() + min(3600, base * 2 ** (count - 1))

    def _succeeded(self, sn: str, group: str, interval: int) -> None:
        key = (sn, group)
        self._failures.pop(key, None)
        self._due[key] = time.monotonic() + interval

    async def _async_update_data(self) -> dict[str, VehicleState]:
        now = time.monotonic()
        if now < self._backoff_until:
            raise UpdateFailed("Server requested a polling pause")
        force, self._force_refresh = self._force_refresh, False
        try:
            active = set(self._active)
            if self._listed_at is None or now - self._listed_at >= 3600:
                listed = await self.client.async_list_vehicles()
                active = {vehicle.sn for vehicle in listed}
                self.vehicles.update((vehicle.sn, vehicle) for vehicle in listed)
                self._listed_at = now
            self._active = active
            old = self.data or {}
            # Bound both concurrent requests and account pressure for large fleets.
            semaphore = asyncio.Semaphore(3)
            batch_failure: AuthenticationError | RateLimited | None = None

            async def fetch(sn: str) -> tuple[str, VehicleState]:
                nonlocal batch_failure
                if sn not in active:
                    return sn, replace(
                        old.get(sn, VehicleState()).unavailable(), battery_details_available=False
                    )

                def due(group: str) -> bool:
                    if force and not self._failures.get((sn, group)):
                        # BMS data must not be repeatedly fetched by dashboard updates.
                        if group != "battery" or now - self._battery_checked.get(sn, -3600) >= 30:
                            return True
                    return now >= self._due.get((sn, group), 0)

                def check_batch() -> None:
                    if batch_failure is not None:
                        raise batch_failure

                try:
                    async with semaphore:
                        check_batch()
                        state = previous = old.get(sn, VehicleState())
                        basic_updated = power_updated = False
                        if due("basic"):
                            try:
                                basic = await self.client.async_vehicle_state(self.vehicles[sn])
                                state = replace(
                                    basic,
                                    power_on=state.power_on,
                                    fetched_at=datetime.now(UTC),
                                    battery_details=state.battery_details,
                                    battery_details_at=state.battery_details_at,
                                    battery_details_available=state.battery_details_available,
                                )
                                basic_updated = True
                            except AuthenticationError, RateLimited:
                                raise
                            except ApiError:
                                state = state.unavailable()
                                self._failed(sn, "basic")
                        check_batch()
                        if due("power"):
                            try:
                                power = await self.client.async_power_state(self.vehicles[sn])
                                state = replace(state, power_on=power)
                                power_updated = True
                            except AuthenticationError, RateLimited:
                                raise
                            except ApiError:
                                state = replace(state, power_on=None)
                                self._failed(sn, "power")
                        if basic_updated:
                            before = (previous.acc_on, previous.power_on, previous.charging)
                            after = (state.acc_on, state.power_on, state.charging)
                            if any(
                                a is not None and b is not None and a != b
                                for a, b in zip(before, after, strict=True)
                            ):
                                self._fast_until[sn] = time.monotonic() + 90
                        basic_interval, battery_interval = self._periods(sn, state, now)
                        if basic_updated:
                            self._succeeded(sn, "basic", basic_interval)
                        if power_updated:
                            self._succeeded(sn, "power", basic_interval)
                        # A newly observed charge/start transition advances the BMS deadline.
                        if self.battery_enabled and (sn, "battery") not in self._failures:
                            self._due[(sn, "battery")] = min(
                                self._due.get((sn, "battery"), 0),
                                self._battery_checked.get(sn, -3600) + battery_interval,
                            )
                        check_batch()
                        if self.battery_enabled and due("battery"):
                            self._battery_checked[sn] = time.monotonic()
                            try:
                                details = await self.client.async_battery_details(self.vehicles[sn])
                                state = replace(
                                    state,
                                    battery_details=details,
                                    battery_details_at=datetime.now(UTC),
                                    battery_details_available=True,
                                )
                                self._succeeded(sn, "battery", battery_interval)
                            except AuthenticationError, RateLimited:
                                raise
                            except ApiError:
                                state = replace(state, battery_details_available=False)
                                self._failed(sn, "battery")
                        if not self.show_location:
                            state = replace(state, latitude=None, longitude=None, location_at=None)
                    return sn, state
                except (AuthenticationError, RateLimited) as err:
                    batch_failure = err
                    raise

            # gather(return_exceptions) ensures requests finish before reload/unload.
            results = await asyncio.gather(
                *(fetch(sn) for sn in self.vehicles), return_exceptions=True
            )
            states: dict[str, VehicleState] = {}
            for result in results:
                if isinstance(result, BaseException):
                    raise result
                sn, state = result
                states[sn] = state
            self.fetched_at = time.time()
            deadlines = [self._listed_at + 3600] if self._listed_at is not None else []
            deadlines.extend(
                deadline
                for (sn, group), deadline in self._due.items()
                if sn in active and (group != "battery" or self.battery_enabled)
            )
            self.update_interval = timedelta(
                seconds=max(1, math.ceil(min(deadlines, default=now + 3600) - time.monotonic()))
            )
            return states
        except AuthenticationError:
            raise ConfigEntryAuthFailed("九号账号需要重新认证") from None
        except RateLimited as err:
            self._backoff_until = time.monotonic() + err.retry_after
            # This update wasn't committed: successful groups must be queried again
            # after the account pause instead of leaving their old values until a later deadline.
            self._due = {
                key: deadline for key, deadline in self._due.items() if key in self._failures
            }
            self.update_interval = timedelta(seconds=err.retry_after)
            raise UpdateFailed("Server requested a polling pause") from None
        except ApiError:
            raise UpdateFailed("Unable to update Ninebot vehicle list") from None
