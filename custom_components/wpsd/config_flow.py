"""Config flow for the WPSD integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from .const import DEFAULT_PORT, DEFAULT_USERNAME, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class WpsdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WPSD."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # TODO: test host and credentials against WPSD once the client exists.
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            return self.async_create_entry(
                title=user_input[CONF_HOST], data=user_input
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
