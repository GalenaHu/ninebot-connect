"""九号车联 integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NinebotClient
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, PLATFORMS
from .coordinator import NinebotCoordinator
from .models import AccountSession

type NinebotConfigEntry = ConfigEntry[NinebotCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NinebotConfigEntry) -> bool:
    try:
        session = AccountSession.from_storage(dict(entry.data))
    except ValueError:
        raise ConfigEntryAuthFailed("保存的九号会话不完整，请重新认证") from None

    async def save(updated: AccountSession) -> None:
        hass.config_entries.async_update_entry(entry, data=updated.to_storage())

    client = NinebotClient(async_get_clientsession(hass), session, save)
    coordinator = NinebotCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NinebotConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_options_updated(hass: HomeAssistant, entry: NinebotConfigEntry) -> None:
    interval = timedelta(seconds=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
    if entry.runtime_data.update_interval != interval:
        await hass.config_entries.async_reload(entry.entry_id)
