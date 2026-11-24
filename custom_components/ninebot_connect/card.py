"""Serve the bundled card and register only this project's dashboard resource."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_when_setup

from .const import DOMAIN, VERSION

CARD_URL = f"/{DOMAIN}/ninebot-vehicle-card.js"
CARD_RESOURCE_URL = f"{CARD_URL}?v={VERSION}"
_CARD_FILE = Path(__file__).parent / "frontend" / "ninebot-vehicle-card.js"
_LOCK = f"{DOMAIN}_card_lock"
_REGISTERED = f"{DOMAIN}_card_registered"
_LOGGER = logging.getLogger(__name__)


async def async_setup_card(hass: HomeAssistant, _component: str | None = None) -> None:
    """Register one exact file, once per HA instance, independently of accounts."""
    lock = hass.data.setdefault(_LOCK, asyncio.Lock())
    async with lock:
        if hass.data.get(_REGISTERED):
            return
        try:
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(CARD_URL, str(_CARD_FILE), False),
                ]
            )
        except OSError, RuntimeError, HomeAssistantError:
            _LOGGER.warning(
                "Unable to serve the bundled dashboard card; vehicle entities are unaffected"
            )
            return
        hass.data[_REGISTERED] = True
        async_when_setup(hass, "lovelace", async_register_card_resource)


async def async_register_card_resource(hass: HomeAssistant, _component: str) -> None:
    """Storage mode can be managed here; never rewrite a user's YAML resources."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None:
        return
    resources = lovelace.resources
    if not isinstance(resources, ResourceStorageCollection):
        _LOGGER.info("Add dashboard module resource %s to your YAML resources", CARD_RESOURCE_URL)
        return
    try:
        await resources.async_get_info()
        own = []
        for item in resources.async_items():
            parsed = urlsplit(item.get("url", ""))
            if not parsed.scheme and not parsed.netloc and parsed.path == CARD_URL:
                own.append(item)
        if own:
            first = own[0]
            if first["url"] != CARD_RESOURCE_URL or first["type"] != "module":
                await resources.async_update_item(
                    first["id"], {"url": CARD_RESOURCE_URL, "res_type": "module"}
                )
            for duplicate in own[1:]:
                await resources.async_delete_item(duplicate["id"])
        else:
            await resources.async_create_item({"url": CARD_RESOURCE_URL, "res_type": "module"})
    except OSError, HomeAssistantError, ValueError:
        _LOGGER.warning(
            "Unable to register the dashboard card; add module resource %s manually",
            CARD_RESOURCE_URL,
        )
