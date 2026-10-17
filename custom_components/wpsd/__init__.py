"""The WPSD integration."""

from __future__ import annotations

import aiohttp
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import WpsdClient
from .const import DOMAIN
from .coordinator import (
    WpsdConfigEntry,
    WpsdData,
    WpsdModeCoordinator,
    WpsdSystemCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WpsdConfigEntry) -> bool:
    """Set up WPSD from a config entry."""
    client = WpsdClient(
        url=entry.data[CONF_URL],
        session=async_get_clientsession(hass),
    )

    try:
        client.callsign = await client.async_get_callsign()
        client.dashboard_version = await client.async_get_dashboard_version()
    except (TimeoutError, aiohttp.ClientError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err), "url": entry.data[CONF_URL]},
        ) from err

    system_coordinator = WpsdSystemCoordinator(hass, entry, client)
    mode_coordinator = WpsdModeCoordinator(hass, entry, client)
    await system_coordinator.async_config_entry_first_refresh()
    await mode_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = WpsdData(client, system_coordinator, mode_coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WpsdConfigEntry) -> bool:
    """Unload a WPSD config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
