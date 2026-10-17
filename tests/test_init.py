"""Tests for WPSD integration setup, unload and device registration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wpsd.const import (
    CONF_MODE_SCAN_INTERVAL,
    CONF_SYSTEM_SCAN_INTERVAL,
    DOMAIN,
)


def device_for(hass: HomeAssistant, entry: MockConfigEntry):
    """Return the single device registered for a config entry (or None)."""
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    return devices[0] if devices else None


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_callsign_fetched_once_at_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    mock_wpsd["async_get_callsign"].assert_awaited_once()
    assert mock_config_entry.runtime_data.client.callsign == "W4DW"


async def test_setup_retries_when_host_unreachable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    mock_wpsd["async_get_callsign"].side_effect = aiohttp.ClientConnectionError("down")
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_on_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    mock_wpsd["async_get_callsign"].side_effect = TimeoutError()
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_platform_data_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    mock_wpsd["parse_modes_with_network"].side_effect = aiohttp.ClientError()
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_is_named_after_callsign(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    device = device_for(hass, mock_config_entry)
    assert device is not None
    assert device.name == "W4DW"
    assert device.manufacturer == "WPSD"
    assert device.model == "WPSD Hotspot"
    assert device.sw_version == "abc1234def"


async def test_device_named_wpsd_without_callsign(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    mock_wpsd["async_get_callsign"].return_value = None
    await setup_entry(hass, mock_config_entry)
    device = device_for(hass, mock_config_entry)
    assert device is not None
    assert device.name == "WPSD"


async def test_two_hotspots_get_separate_devices(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    other = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://other.local"})
    await setup_entry(hass, mock_config_entry)
    await setup_entry(hass, other)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert other.state is ConfigEntryState.LOADED

    first = device_for(hass, mock_config_entry)
    second = device_for(hass, other)
    assert first is not None
    assert second is not None
    assert first.id != second.id
    assert first.identifiers == {(DOMAIN, mock_config_entry.entry_id)}
    assert second.identifiers == {(DOMAIN, other.entry_id)}


async def test_changing_options_reloads_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    callsign: AsyncMock = mock_wpsd["async_get_callsign"]
    assert callsign.await_count == 1

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_MODE_SCAN_INTERVAL: 20, CONF_SYSTEM_SCAN_INTERVAL: 30},
    )
    await hass.async_block_till_done()

    assert callsign.await_count == 2
    assert mock_config_entry.state is ConfigEntryState.LOADED
