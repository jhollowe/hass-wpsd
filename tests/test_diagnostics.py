"""Tests for WPSD diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import CALLSIGN, MODES, NETWORKS


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_wpsd,
) -> None:
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["entry"] == {"url": "http://wpsd.local"}
    assert result["callsign"] == CALLSIGN
    assert result["modes"] == {"modes": MODES, "networks": NETWORKS}
    assert result["system"]["firmware"] == "MMDVM_HS_Hat-v1.6.1"
