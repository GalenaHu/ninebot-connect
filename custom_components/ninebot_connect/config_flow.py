"""Password in, tokens out: HA setup, options and account-bound reauthentication."""

from __future__ import annotations

from typing import Any

import probatio
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import (
    ApiError,
    AuthenticationError,
    CannotConnect,
    NinebotClient,
    RateLimited,
    VerificationRequired,
)
from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    NAME,
)

CREDENTIALS = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_USERNAME)): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class NinebotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        return await self._credentials(user_input, reauth=False)

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        return await self._credentials(user_input, reauth=True)

    async def _credentials(self, user_input: dict[str, Any] | None, *, reauth: bool):
        errors: dict[str, str] = {}
        step = "reauth_confirm" if reauth else "user"
        if user_input is not None:
            client = NinebotClient(async_get_clientsession(self.hass))
            old_entry = self._get_reauth_entry() if reauth else None
            try:
                session = await client.async_login(
                    user_input[CONF_USERNAME].strip(),
                    user_input[CONF_PASSWORD],
                    old_entry.data.get("device_id") if old_entry else None,
                )
                if old_entry and (
                    session.uuid != old_entry.data.get("uuid")
                    or session.business_uid != old_entry.data.get("business_uid")
                ):
                    errors["base"] = "wrong_account"
                else:
                    # Validate usable account access, but do not store any vehicle responses.
                    vehicles = await client.async_list_vehicles()
                    if not vehicles and not reauth:
                        return self.async_abort(reason="no_vehicles")
                    await self.async_set_unique_id(session.uuid)
                    if old_entry:
                        return self.async_update_reload_and_abort(
                            old_entry,
                            data=session.to_storage(),
                        )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=NAME, data=session.to_storage())
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except RateLimited:
                errors["base"] = "rate_limited"
            except VerificationRequired:
                errors["base"] = "verification_required"
            except ApiError:
                errors["base"] = "protocol_error"
            finally:
                # Never keep the submitted credential dict on the flow instance.
                user_input = None
        return self.async_show_form(step_id=step, data_schema=CREDENTIALS, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NinebotOptionsFlow()


class NinebotOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_POLL_INTERVAL,
                            DEFAULT_POLL_INTERVAL,
                        ),
                    ): probatio.All(
                        probatio.Coerce(int),
                        probatio.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                    ),
                }
            ),
        )
