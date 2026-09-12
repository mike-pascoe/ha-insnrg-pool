"""Config flow for Insnrg Pool."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    InsnrgAuthError,
    InsnrgClient,
    InsnrgConnectionError,
    InsnrgError,
    InsnrgVoiceControlDisabled,
)
from .const import (
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class InsnrgConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Insnrg Pool config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: ConfigEntry | None = None

    async def _async_validate(self, username: str, password: str) -> tuple[str, str]:
        """Log in and confirm the account exposes devices. Returns (id, address)."""
        client = InsnrgClient(async_get_clientsession(self.hass), username, password)
        await client.async_login()
        if not client.system_id:
            raise InsnrgVoiceControlDisabled("No pool system on this account")
        # Confirms Voice Control is on; raises InsnrgVoiceControlDisabled if not.
        await client.async_get_devices()
        return client.system_id, client.address or "Insnrg Pool"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                system_id, address = await self._async_validate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except InsnrgAuthError:
                errors["base"] = "invalid_auth"
            except InsnrgVoiceControlDisabled:
                errors["base"] = "voice_control_disabled"
            except InsnrgConnectionError:
                errors["base"] = "cannot_connect"
            except InsnrgError:
                _LOGGER.exception("Unexpected error validating Insnrg credentials")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(system_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=address, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm new credentials."""
        errors: dict[str, str] = {}
        if user_input is not None and self._reauth_entry is not None:
            try:
                await self._async_validate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except InsnrgAuthError:
                errors["base"] = "invalid_auth"
            except InsnrgVoiceControlDisabled:
                errors["base"] = "voice_control_disabled"
            except InsnrgConnectionError:
                errors["base"] = "cannot_connect"
            except InsnrgError:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry, data=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return InsnrgOptionsFlow()


class InsnrgOptionsFlow(OptionsFlow):
    """Let the user tune how often the cloud is polled."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES, default=current
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120))
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
