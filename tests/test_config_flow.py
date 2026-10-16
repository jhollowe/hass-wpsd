"""Tests for the WPSD config and options flows."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wpsd.const import (
    CONF_MODE_SCAN_INTERVAL,
    CONF_SYSTEM_SCAN_INTERVAL,
    DEFAULT_MODE_SCAN_INTERVAL,
    DEFAULT_SYSTEM_SCAN_INTERVAL,
    DOMAIN,
)

LAST_HEARD = "custom_components.wpsd.config_flow.WpsdClient.async_get_last_heard"
SETUP_ENTRY = "custom_components.wpsd.async_setup_entry"

USER_INPUT = {CONF_HOST: "wpsd.local", CONF_PORT: 8080}


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(LAST_HEARD, AsyncMock(return_value=[])),
        patch(SETUP_ENTRY, AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "wpsd.local"
    assert result["data"] == USER_INPUT


async def test_user_flow_port_defaults_to_80(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with (
        patch(LAST_HEARD, AsyncMock(return_value=[])),
        patch(SETUP_ENTRY, AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "wpsd.local"}
        )
    assert result["data"][CONF_PORT] == 80


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (aiohttp.ClientConnectionError("down"), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors_then_recovers(
    hass: HomeAssistant, error: Exception, expected: str
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(LAST_HEARD, AsyncMock(side_effect=error)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    with (
        patch(LAST_HEARD, AsyncMock(return_value=[])),
        patch(SETUP_ENTRY, AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_aborts_for_duplicate_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(LAST_HEARD, AsyncMock(return_value=[])):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "wpsd.local", CONF_PORT: 80}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"




async def test_options_flow_defaults(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    defaults = {str(k): k.default() for k in result["data_schema"].schema}
    assert defaults == {
        CONF_MODE_SCAN_INTERVAL: DEFAULT_MODE_SCAN_INTERVAL,
        CONF_SYSTEM_SCAN_INTERVAL: DEFAULT_SYSTEM_SCAN_INTERVAL,
    }


async def test_options_flow_shows_saved_values(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "slow.local", CONF_PORT: 80},
        options={CONF_MODE_SCAN_INTERVAL: 20, CONF_SYSTEM_SCAN_INTERVAL: 120},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    defaults = {str(k): k.default() for k in result["data_schema"].schema}
    assert defaults == {CONF_MODE_SCAN_INTERVAL: 20, CONF_SYSTEM_SCAN_INTERVAL: 120}


async def test_options_flow_saves_values(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_MODE_SCAN_INTERVAL: 15, CONF_SYSTEM_SCAN_INTERVAL: 90},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_MODE_SCAN_INTERVAL: 15,
        CONF_SYSTEM_SCAN_INTERVAL: 90,
    }


@pytest.mark.parametrize("value", [0, -1, 3601])
@pytest.mark.parametrize("key", [CONF_MODE_SCAN_INTERVAL, CONF_SYSTEM_SCAN_INTERVAL])
async def test_options_flow_rejects_out_of_range(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, key: str, value: int
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    data = {CONF_MODE_SCAN_INTERVAL: 5, CONF_SYSTEM_SCAN_INTERVAL: 30, key: value}
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(result["flow_id"], data)
