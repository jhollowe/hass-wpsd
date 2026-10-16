"""Shared fixtures for the WPSD tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wpsd.const import DOMAIN

CLIENT = "custom_components.wpsd.client.WpsdClient"

CALLSIGN = "W1AW"

RADIO_DATA: dict[str, Any] = {
    "radio_status": "IDLE",
    "firmware": "MMDVM_HS_Hat-v1.6.1",
    "tx_freq": "438.800 MHz",
    "rx_freq": "438.800 MHz",
}

HOMEPAGE_DATA: dict[str, Any] = {
    "dashboard_version": "abc1234def",
    "cpu_load": "38",
    "cpu_temp": "135°F / 57°C",
    "disk_root": {"percent": 1.99, "used_gb": 4.37, "total_gb": 219.56},
    "disk_varlog": {"percent": 4.69, "used_gb": 0.01, "total_gb": 0.25},
}

MODES: dict[str, str] = {
    "D-Star": "inactive",
    "DMR": "active",
    "YSF": "paused",
    "P25": "error",
    "NXDN": "inactive",
    "POCSAG": "inactive",
}

NETWORKS: dict[str, str] = {
    "DMR Net": "active",
    "YSF Net": "paused",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load the custom integration under test."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for a hotspot."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="wpsd.local",
        data={CONF_HOST: "wpsd.local", CONF_PORT: 80},
    )


@pytest.fixture
def mock_wpsd() -> Generator[dict[str, AsyncMock]]:
    """Patch every WpsdClient method the integration calls."""
    mocks = {
        "async_get_callsign": AsyncMock(return_value=CALLSIGN),
        "async_get_radio_data": AsyncMock(return_value=dict(RADIO_DATA)),
        "async_get_homepage_data": AsyncMock(return_value=dict(HOMEPAGE_DATA)),
        "async_get_modes_with_network": AsyncMock(
            return_value=(dict(MODES), dict(NETWORKS))
        ),
    }
    with patch.multiple(CLIENT, **mocks):
        yield mocks
