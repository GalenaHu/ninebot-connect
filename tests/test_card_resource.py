"""Local card delivery through HA's real HTTP and resource collections."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.http import HomeAssistantHTTP
from homeassistant.components.http.const import SSL_MODERN
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import (
    ResourceStorageCollection,
    ResourceYAMLCollection,
)
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers.http import KEY_ALLOW_CONFIGURED_CORS

from custom_components.ninebot_connect.card import (
    CARD_URL,
    async_register_card_resource,
    async_setup_card,
)


async def test_integration_waits_for_http_and_registers_when_lovelace_becomes_ready(
    hass, aiohttp_client
):
    from custom_components.ninebot_connect import async_setup

    hass.http = HomeAssistantHTTP(hass, None, None, None, ["127.0.0.1"], 0, [], SSL_MODERN)
    hass.http.app[KEY_ALLOW_CONFIGURED_CORS] = lambda route: None
    config = MagicMock()
    config.async_load = AsyncMock(return_value={})
    resources = ResourceStorageCollection(hass, config)
    hass.data[LOVELACE_DATA] = SimpleNamespace(resources=resources, resource_mode="storage")
    assert await async_setup(hass, {})
    hass.config.components.update({"http", "lovelace"})
    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "http"})
    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "lovelace"})
    await hass.async_block_till_done()
    http = await aiohttp_client(hass.http.app)
    assert (await http.get(CARD_URL)).status == 200
    assert len(resources.async_items()) == 1
    assert resources.async_items()[0]["url"].startswith(CARD_URL + "?v=")


async def test_only_card_js_is_served_and_registration_is_idempotent(hass, aiohttp_client):
    hass.http = HomeAssistantHTTP(hass, None, None, None, ["127.0.0.1"], 0, [], SSL_MODERN)
    hass.http.app[KEY_ALLOW_CONFIGURED_CORS] = lambda route: None
    await async_setup_card(hass)
    await async_setup_card(hass)
    http = await aiohttp_client(hass.http.app)
    response = await http.get(CARD_URL)
    assert response.status == 200
    assert "customElements.define" in await response.text()
    for path in (
        "/ninebot_connect/manifest.json",
        "/ninebot_connect/../api.py",
        "/ninebot_connect/.storage",
    ):
        assert (await http.get(path)).status == 404


async def test_resource_update_preserves_other_resources_and_yaml_is_untouched(hass):
    config = MagicMock()
    config.async_load = AsyncMock(return_value={})
    resources = ResourceStorageCollection(hass, config)
    old = await resources.async_create_item({"url": CARD_URL + "?v=old", "res_type": "module"})
    other = await resources.async_create_item({"url": "/local/other.js", "res_type": "module"})
    hass.data[LOVELACE_DATA] = SimpleNamespace(resources=resources, resource_mode="storage")
    await async_register_card_resource(hass, "lovelace")
    await async_register_card_resource(hass, "lovelace")
    items = resources.async_items()
    assert len(items) == 2
    own = next(item for item in items if item["id"] == old["id"])
    assert own["url"] != old["url"] and own["type"] == "module"
    assert next(item for item in items if item["id"] == other["id"]) == other
    yaml = ResourceYAMLCollection([{"url": "/local/user.js", "type": "module"}])
    hass.data[LOVELACE_DATA] = SimpleNamespace(resources=yaml, resource_mode="yaml")
    await async_register_card_resource(hass, "lovelace")
    assert yaml.async_items() == [{"url": "/local/user.js", "type": "module"}]
