"""Minimal actual-HA fixtures; no mocks of the HA entity/config frameworks."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pytest
from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
async def hass(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config.components.add("logger")
    hass.config.components.add("frontend")
    hass.config.skip_pip = True
    loader.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    # Discover this workspace's custom_components under HA's config directory.
    (tmp_path / "custom_components").symlink_to(
        Path(__file__).resolve().parents[1] / "custom_components"
    )
    await async_load_base_functionality(hass)
    await async_setup_component(hass, "homeassistant", {})
    async with aiohttp.ClientSession() as http:
        with (
            patch("custom_components.ninebot_connect.async_get_clientsession", return_value=http),
            patch(
                "custom_components.ninebot_connect.config_flow.async_get_clientsession",
                return_value=http,
            ),
        ):
            yield hass
    await hass.async_stop(force=True)
    await asyncio.sleep(0)
