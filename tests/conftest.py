"""Minimal actual-HA fixtures; no mocks of the HA entity/config frameworks."""
import asyncio
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
async def hass(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config.components.add("logger")
    hass.config.components.add("frontend")
    hass.config.skip_pip = True
    # Discover this workspace's custom_components under HA's config directory.
    (tmp_path / "custom_components").symlink_to(Path(__file__).resolve().parents[1] / "custom_components")
    await async_setup_component(hass, "homeassistant", {})
    yield hass
    await hass.async_stop(force=True)
    await asyncio.sleep(0)
