"""Config flow for the WPSD integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import probatio
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .client import WpsdClient
from .const import (
    CONF_MODE_SCAN_INTERVAL,
    CONF_SYSTEM_SCAN_INTERVAL,
    DEFAULT_MODE_SCAN_INTERVAL,
    DEFAULT_SYSTEM_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import WpsdConfigEntry

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): str,
    }
)


class WpsdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WPSD."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: WpsdConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return WpsdOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            if not (errors := await self._async_test_connection(user_input)):
                return self.async_create_entry(
                    title=user_input[CONF_URL], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle changing the hotspot's host or port."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            if not (errors := await self._async_test_connection(user_input)):
                return self.async_update_reload_and_abort(
                    entry, title=user_input[CONF_URL], data=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def _async_test_connection(
        self, user_input: dict[str, Any]
    ) -> dict[str, str]:
        """Return form errors if the dashboard can't be reached."""
        client = WpsdClient(
            url=user_input[CONF_URL],
            session=async_create_clientsession(self.hass),
        )
        try:
            await client.async_get_last_heard(limit=1)
        except aiohttp.ClientError, TimeoutError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error")
            return {"base": "unknown"}
        return {}


class WpsdOptionsFlow(OptionsFlowWithReload):
    """Handle WPSD options (polling intervals)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the polling interval options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        interval = probatio.All(
            probatio.Coerce(int),
            probatio.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
        )
        options = self.config_entry.options
        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_MODE_SCAN_INTERVAL,
                    default=options.get(
                        CONF_MODE_SCAN_INTERVAL, DEFAULT_MODE_SCAN_INTERVAL
                    ),
                ): interval,
                probatio.Required(
                    CONF_SYSTEM_SCAN_INTERVAL,
                    default=options.get(
                        CONF_SYSTEM_SCAN_INTERVAL, DEFAULT_SYSTEM_SCAN_INTERVAL
                    ),
                ): interval,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
