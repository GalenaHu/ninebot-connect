"""Account polling with independent per-vehicle availability."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, AuthenticationError, NinebotClient, RateLimited
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
from .models import Vehicle, VehicleState

_LOGGER = logging.getLogger(__name__)


class NinebotCoordinator(DataUpdateCoordinator[dict[str, VehicleState]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: NinebotClient) -> None:
        self.client = client
        self.vehicles: dict[str, Vehicle] = {}
        self._listed_at = 0.0
        self.fetched_at: float | None = None
        self._backoff_until = 0.0
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN,
            update_interval=timedelta(seconds=entry.options.get(
                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL,
            )),
        )

    async def _async_update_data(self) -> dict[str, VehicleState]:
        now = time.monotonic()
        if now < self._backoff_until:
            raise UpdateFailed("Server requested a polling pause")
        try:
            active = set(self.vehicles)
            if not self.vehicles or now - self._listed_at >= 3600:
                listed = await self.client.async_list_vehicles()
                active = {vehicle.sn for vehicle in listed}
                self.vehicles.update((vehicle.sn, vehicle) for vehicle in listed)
                self._listed_at = now
            else:
                active = set(getattr(self, "_active", self.vehicles))
            self._active = active
            old = self.data or {}
            # Bound both concurrent requests and account pressure for large fleets.
            semaphore = asyncio.Semaphore(3)

            async def fetch(sn: str) -> tuple[str, VehicleState]:
                if sn not in active:
                    return sn, old.get(sn, VehicleState()).unavailable()
                try:
                    async with semaphore:
                        state = await self.client.async_vehicle_state(self.vehicles[sn])
                    return sn, state
                except (AuthenticationError, RateLimited):
                    raise
                except ApiError:
                    return sn, old.get(sn, VehicleState()).unavailable()

            # gather(return_exceptions) ensures requests finish before reload/unload.
            results = await asyncio.gather(*(fetch(sn) for sn in self.vehicles),
                                           return_exceptions=True)
            states: dict[str, VehicleState] = {}
            for result in results:
                if isinstance(result, BaseException):
                    raise result
                sn, state = result
                states[sn] = state
            self.fetched_at = time.time()
            return states
        except AuthenticationError:
            raise ConfigEntryAuthFailed("九号账号需要重新认证") from None
        except RateLimited as err:
            self._backoff_until = time.monotonic() + err.retry_after
            raise UpdateFailed("Server requested a polling pause") from None
        except ApiError:
            raise UpdateFailed("Unable to update Ninebot vehicle list") from None
