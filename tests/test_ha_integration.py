"""Exercise real HA flows, entity registration, unload and saved-token restart."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ninebot_connect.const import DOMAIN
from custom_components.ninebot_connect.models import AccountSession, Vehicle, VehicleState

SESSION = AccountSession(
    "synthetic-access",
    "synthetic-refresh",
    "synthetic-account",
    "synthetic-business",
    "synthetic-device",
)
CAR = Vehicle("SYNTHETIC-SN", "Synthetic vehicle", "Test model", "118")


def client_patches():
    return patch.multiple(
        "custom_components.ninebot_connect.api.NinebotClient",
        async_login=AsyncMock(return_value=SESSION),
        async_list_vehicles=AsyncMock(return_value=[CAR]),
        async_vehicle_state=AsyncMock(
            return_value=VehicleState(
                battery=93,
                range_km=36.7,
                charging=False,
                main_battery_online=True,
                lock_status=1,
                mileage_km=123.4,
                latitude=39.9,
                longitude=116.4,
            )
        ),
    )


async def setup_flow(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "synthetic-name", CONF_PASSWORD: "PRIVATE-PASSWORD"},
    )


async def test_config_entities_unload_and_restart_from_tokens(hass):
    # async_login is patched here, so retain its public contract: client.session set.
    async def login(client, username, password, device_id=None):
        client.session = SESSION
        return SESSION

    with (
        client_patches(),
        patch("custom_components.ninebot_connect.api.NinebotClient.async_login", login),
    ):
        result = await setup_flow(hass)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = result["result"]
        await hass.async_block_till_done()
        assert entry.data == SESSION.to_storage()
        assert "PRIVATE" not in str(entry.data)
        assert entry.unique_id == SESSION.uuid
        assert entry.runtime_data.data[CAR.sn].battery == 93
        states = hass.states.async_all()
        battery = next(s for s in states if s.attributes.get("device_class") == "battery")
        assert battery.state == "93"
        tracker = next(s for s in states if s.domain == "device_tracker")
        assert tracker.attributes["latitude"] == 39.9
        assert tracker.attributes["longitude"] == 116.4
        assert tracker.attributes["source_type"] == "gps"
        assert not hass.states.async_all("lock")
        assert not hass.services.has_service(DOMAIN, "unlock")
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        # Reload uses only saved tokens; password authentication must not be called.
        with patch(
            "custom_components.ninebot_connect.api.NinebotClient.async_login",
            side_effect=AssertionError("Password login on restart"),
        ):
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
        assert entry.runtime_data.client.session == SESSION
        from custom_components.ninebot_connect.diagnostics import async_get_config_entry_diagnostics

        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        for secret in ("synthetic", "SYNTHETIC", "39.9", "116.4", "PRIVATE"):
            assert secret not in str(diagnostics)
        assert diagnostics["vehicle_count"] == 1


async def test_duplicate_account_aborts(hass):
    with client_patches():
        first = await setup_flow(hass)
        await hass.async_block_till_done()
        second = await setup_flow(hass)
        assert first["type"] is FlowResultType.CREATE_ENTRY
        assert second["type"] is FlowResultType.ABORT
        assert second["reason"] == "already_configured"


async def test_reauth_rejects_different_identity(hass):
    with client_patches():
        created = await setup_flow(hass)
        await hass.async_block_till_done()
        entry = created["result"]
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        wrong = AccountSession("other-access", "other-refresh", "OTHER", "other-uid", "device")
        with patch(
            "custom_components.ninebot_connect.api.NinebotClient.async_login",
            AsyncMock(return_value=wrong),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "wrong",
                    CONF_PASSWORD: "PRIVATE",
                },
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "wrong_account"}
        assert entry.data == SESSION.to_storage()


async def test_reauth_replaces_tokens_and_reloads(hass):
    with client_patches():
        created = await setup_flow(hass)
        await hass.async_block_till_done()
        entry = created["result"]
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        renewed = AccountSession(
            "new-access", "new-refresh", SESSION.uuid, SESSION.business_uid, SESSION.device_id
        )
        with patch(
            "custom_components.ninebot_connect.api.NinebotClient.async_login",
            AsyncMock(return_value=renewed),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "original",
                    CONF_PASSWORD: "PRIVATE",
                },
            )
            await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data == renewed.to_storage()


async def test_rotated_token_storage_does_not_reload_entry(hass):
    with client_patches():
        created = await setup_flow(hass)
        await hass.async_block_till_done()
        entry = created["result"]
        renewed = AccountSession(
            "new-access", "new-refresh", SESSION.uuid, SESSION.business_uid, SESSION.device_id
        )
        with patch.object(hass.config_entries, "async_reload", AsyncMock()) as reload:
            await entry.runtime_data.client._on_session_changed(renewed)
            await hass.async_block_till_done()
            reload.assert_not_awaited()
        assert entry.data == renewed.to_storage()


async def test_options_changes_poll_interval_and_reload(hass):
    with client_patches():
        created = await setup_flow(hass)
        await hass.async_block_till_done()
        entry = created["result"]
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "poll_interval": 300,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.runtime_data.update_interval.total_seconds() == 300


async def test_saved_tokens_survive_new_ha_instance_and_delete_clears_storage(hass, tmp_path):
    import json

    from homeassistant import loader
    from homeassistant.bootstrap import async_load_base_functionality
    from homeassistant.config_entries import ConfigEntries
    from homeassistant.core import HomeAssistant
    from homeassistant.setup import async_setup_component

    with client_patches():
        created = await setup_flow(hass)
        await hass.async_block_till_done()
        entry_id = created["result"].entry_id
        await hass.async_stop(force=True)
        saved = json.loads((tmp_path / ".storage" / "core.config_entries").read_text())
        stored = next(e for e in saved["data"]["entries"] if e["entry_id"] == entry_id)
        assert stored["data"] == SESSION.to_storage()
        assert "PRIVATE-PASSWORD" not in str(saved)
        restarted = HomeAssistant(str(tmp_path))
        restarted.config.components.update({"logger", "frontend"})
        restarted.config.skip_pip = True
        loader.async_setup(restarted)
        restarted.config_entries = ConfigEntries(restarted, {})
        try:
            await async_load_base_functionality(restarted)
            await async_setup_component(restarted, "homeassistant", {})
            with patch(
                "custom_components.ninebot_connect.api.NinebotClient.async_login",
                side_effect=AssertionError("Password login after HA restart"),
            ):
                assert await restarted.config_entries.async_setup(entry_id)
                await restarted.async_block_till_done()
            entry = restarted.config_entries.async_get_entry(entry_id)
            assert entry.runtime_data.client.session == SESSION
            await restarted.config_entries.async_remove(entry_id)
            assert restarted.config_entries.async_get_entry(entry_id) is None
        finally:
            await restarted.async_stop(force=True)
        saved = (tmp_path / ".storage" / "core.config_entries").read_text()
        assert SESSION.access_token not in saved
        assert SESSION.refresh_token not in saved
