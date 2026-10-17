"""Tests for the WPSD sensors."""

from __future__ import annotations

from datetime import timedelta

import aiohttp
import pytest
from homeassistant.const import CONF_URL, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.wpsd.const import (
    ALL_MODES,
    CONF_MODE_SCAN_INTERVAL,
    CONF_SYSTEM_SCAN_INTERVAL,
    DOMAIN,
    MODE_STATES,
)

from .conftest import HOMEPAGE_DATA, MODES, NETWORKS, RADIO_DATA


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def entity_id(hass: HomeAssistant, entry: MockConfigEntry, suffix: str) -> str:
    found = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{suffix}"
    )
    assert found is not None, f"no sensor with unique id suffix {suffix}"
    return found


@pytest.mark.parametrize(
    ("suffix", "expected"),
    [
        ("active_mode", "IDLE"),
        ("firmware", "MMDVM_HS_Hat-v1.6.1"),
        ("tx_freq", "438.8"),
        ("rx_freq", "438.8"),
        ("cpu_load", "38"),
        ("cpu_temp", "57.2222222222222"),
        ("disk_usage_root", "1.99"),
        ("disk_usage_varlog", "4.69"),
    ],
)
async def test_system_sensor_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wpsd,
    suffix: str,
    expected: str,
) -> None:
    await setup_entry(hass, mock_config_entry)
    state = hass.states.get(entity_id(hass, mock_config_entry, suffix))
    assert state is not None
    assert state.state == expected


async def test_sensor_names_come_from_translations(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    state = hass.states.get(entity_id(hass, mock_config_entry, "cpu_temp"))
    assert state.attributes["friendly_name"] == "W4DW CPU Temperature"


@pytest.mark.parametrize(
    "suffix",
    ["disk_used_root", "disk_total_root", "disk_used_varlog", "disk_total_varlog"],
)
async def test_disk_size_sensors_disabled_by_default(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd, suffix: str
) -> None:
    await setup_entry(hass, mock_config_entry)
    eid = entity_id(hass, mock_config_entry, suffix)
    entry = er.async_get(hass).async_get(eid)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(eid) is None


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("tx_freq", "no number here"),
        ("tx_freq", "1.2.3 MHz"),
        ("cpu_temp", None),
    ],
)
async def test_unparseable_numeric_value_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wpsd,
    key: str,
    value: str,
) -> None:
    mock_wpsd["parse_radio_data"].return_value = {**RADIO_DATA, key: value}
    mock_wpsd["parse_hw_info_data"].return_value = {**HOMEPAGE_DATA, key: value}
    await setup_entry(hass, mock_config_entry)
    state = hass.states.get(entity_id(hass, mock_config_entry, key))
    assert state.state == STATE_UNKNOWN


async def test_cpu_temp_when_unparseable_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wpsd,
) -> None:
    mock_wpsd["parse_hw_info_data"].return_value = {
        **HOMEPAGE_DATA,
        "cpu_temp": None,
    }
    await setup_entry(hass, mock_config_entry)
    state = hass.states.get(entity_id(hass, mock_config_entry, "cpu_temp"))
    assert state.state == STATE_UNKNOWN


async def test_missing_disk_data_gives_unknown(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    mock_wpsd["parse_hw_info_data"].return_value = {
        **HOMEPAGE_DATA,
        "disk_root": None,
        "disk_varlog": None,
    }
    await setup_entry(hass, mock_config_entry)
    for suffix in ("disk_usage_root", "disk_usage_varlog"):
        state = hass.states.get(entity_id(hass, mock_config_entry, suffix))
        assert state.state == STATE_UNKNOWN


async def test_one_sensor_per_mode_and_no_binary_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    assert len(hass.states.async_all("binary_sensor")) == 0
    for mode in ALL_MODES:
        slug = mode.lower().replace("-", "_")
        assert hass.states.get(entity_id(hass, mock_config_entry, f"{slug}_status"))


@pytest.mark.parametrize(("mode", "status"), list(MODES.items()))
async def test_mode_sensor_state_is_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wpsd,
    mode: str,
    status: str,
) -> None:
    await setup_entry(hass, mock_config_entry)
    slug = mode.lower().replace("-", "_")
    state = hass.states.get(entity_id(hass, mock_config_entry, f"{slug}_status"))
    assert state.state == status


async def test_mode_sensor_supports_all_four_states(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    state = hass.states.get(entity_id(hass, mock_config_entry, "dmr_status"))
    assert state.attributes["device_class"] == "enum"
    assert set(state.attributes["options"]) == {
        "active",
        "inactive",
        "error",
        "paused",
    }
    assert set(MODES.values()) == set(MODE_STATES)


async def test_mode_sensor_name_is_just_the_mode(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    state = hass.states.get(entity_id(hass, mock_config_entry, "d_star_status"))
    assert state.attributes["friendly_name"] == "W4DW D-Star"


async def test_mode_sensor_network_status_attribute(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    dmr = hass.states.get(entity_id(hass, mock_config_entry, "dmr_status"))
    assert dmr.attributes["network_status"] == NETWORKS["DMR Net"]
    ysf = hass.states.get(entity_id(hass, mock_config_entry, "ysf_status"))
    assert ysf.attributes["network_status"] == NETWORKS["YSF Net"]


async def test_mode_sensor_without_network_has_no_attribute(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    state = hass.states.get(entity_id(hass, mock_config_entry, "d_star_status"))
    assert "network_status" not in state.attributes


async def test_unrecognised_status_is_unknown(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    mock_wpsd["parse_modes_with_network"].return_value = (
        {**MODES, "DMR": "unknown"},
        NETWORKS,
    )
    await setup_entry(hass, mock_config_entry)
    state = hass.states.get(entity_id(hass, mock_config_entry, "dmr_status"))
    assert state.state == STATE_UNKNOWN


async def test_missing_mode_does_not_break_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    """A hotspot that only reports DMR must still set up all sensors."""
    mock_wpsd["parse_modes_with_network"].return_value = ({"DMR": "active"}, {})
    await setup_entry(hass, mock_config_entry)
    assert (
        hass.states.get(entity_id(hass, mock_config_entry, "dmr_status")).state
        == "active"
    )
    assert (
        hass.states.get(entity_id(hass, mock_config_entry, "p25_status")).state
        == STATE_UNKNOWN
    )


async def test_unique_ids_are_per_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    other = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://other.local"})
    await setup_entry(hass, mock_config_entry)
    await setup_entry(hass, other)
    assert entity_id(hass, mock_config_entry, "dmr_status") != entity_id(
        hass, other, "dmr_status"
    )


async def test_mode_sensors_poll_every_5s_by_default(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    mock_wpsd["parse_modes_with_network"].return_value = (
        {**MODES, "DMR": "paused"},
        NETWORKS,
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get(entity_id(hass, mock_config_entry, "dmr_status"))
    assert state.state == "paused"


async def test_system_sensors_poll_every_30s_by_default(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    mock_wpsd["parse_hw_info_data"].return_value = {
        **HOMEPAGE_DATA,
        "cpu_load": 77,
    }

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)
    eid = entity_id(hass, mock_config_entry, "cpu_load")
    assert hass.states.get(eid).state == "38"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(eid).state == "77"


async def test_slower_per_device_interval_is_respected(
    hass: HomeAssistant, mock_wpsd
) -> None:
    """A device configured for a longer interval is not polled at the default."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://slow.local"},
        options={CONF_MODE_SCAN_INTERVAL: 120, CONF_SYSTEM_SCAN_INTERVAL: 600},
    )
    await setup_entry(hass, entry)
    polls = mock_wpsd["parse_modes_with_network"]
    assert polls.call_count == 1

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert polls.call_count == 1

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=125))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert polls.call_count == 2


async def test_entities_unavailable_when_polling_fails_then_recover(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wpsd
) -> None:
    await setup_entry(hass, mock_config_entry)
    cpu = entity_id(hass, mock_config_entry, "cpu_load")
    dmr = entity_id(hass, mock_config_entry, "dmr_status")

    mock_wpsd["parse_hw_info_data"].side_effect = aiohttp.ClientError()
    mock_wpsd["parse_modes_with_network"].side_effect = TimeoutError()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(cpu).state == STATE_UNAVAILABLE
    assert hass.states.get(dmr).state == STATE_UNAVAILABLE

    mock_wpsd["parse_hw_info_data"].side_effect = None
    mock_wpsd["parse_modes_with_network"].side_effect = None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=62))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(cpu).state == "38"
    assert hass.states.get(dmr).state == "active"
