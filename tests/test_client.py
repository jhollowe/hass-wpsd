"""Tests for the WPSD HTML/JSON client."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import aiohttp
import pytest

from custom_components.wpsd.client import WpsdClient, _convert_to_gb
from custom_components.wpsd.const import (
    ENDPOINT_API,
    ENDPOINT_HOMEPAGE,
    ENDPOINT_HW_INFO,
    ENDPOINT_RADIOINFO,
    ENDPOINT_REPEATERINFO,
)

# Markup below mirrors what the WPSD-WebCode PHP renders (radioinfo.php,
# repeaterinfo.php, includes/hw_info.php, config/version.php, index.php).

RADIOINFO_HTML = """
<div class="divTableRow center">
  <div class="divTableCell middle cell_content" style="font-weight:bold;">IDLE</div>
  <div class="divTableCell cell_content middle noMob">438.800 MHz</div>
  <div class="divTableCell cell_content middle noMob">439.800 MHz</div>
  <div class="divTableCell cell_content middle noMob">Duplex</div>
  <div class="divTableCell cell_content middle noMob">/dev/ttyAMA0</div>
  <div class="divTableCell cell_content middle noMob">115,200 bps</div>
  <div class="divTableCell cell_content middle noMob">12.2880 MHz</div>
  <div class="divTableCell cell_content middle noMob">MMDVM_HS_Hat-v1.6.1</div>
</div>
"""

HOMEPAGE_HTML = """
<html><head><title>W4DW - Dashboard</title></head><body>
<span title='WPSD Dashboard Version # abc1234def'>WPSD Dashboard Ver.# abc1234def</span>
<div id="hwInfoTable" class="dashboard-header-stats">
  <div class="stat-card">
    <span class="stat-label">CPU Load</span>
    <div class="stat-value"><a class="tooltip" href="#">38%<span>
    <strong>Hardware:</strong> Pi 4 (1 of 4)</span></a></div>
  </div>
  <div class="stat-card">
    <span class="stat-label">CPU Temp</span>
    <div class="stat-value"><a class="tooltip" href="#">135&deg;F / 57&deg;C<span>
    <strong>CPU Temperature</strong></span></a></div>
  </div>
  <div class="stat-card">
    <span class="stat-label">Disk Usage</span>
    <div class="stat-value"><a class="tooltip" href="#">4.37 GB / 219.56 GB<span>
    <strong>Used:</strong> 1.99%<br>
    <strong>/var/log (tmpfs):</strong> 12 MB / 256 MB</span></a></div>
  </div>
</div>
</body></html>
"""

HW_INFO_HTML = """
<html><body>
<div id="hwInfoTable" class="dashboard-header-stats">
  <div class="stat-card">
    <span class="stat-label">CPU Load</span>
    <div class="stat-value"><a class="tooltip" href="#">38%<span>
    <strong>Hardware:</strong> Pi 4 (1 of 4)</span></a></div>
  </div>
  <div class="stat-card">
    <span class="stat-label">CPU Temp</span>
    <div class="stat-value"><a class="tooltip" href="#">135&deg;F / 57&deg;C<span>
    <strong>CPU Temperature</strong></span></a></div>
  </div>
  <div class="stat-card">
    <span class="stat-label">Disk Usage</span>
    <div class="stat-value"><a class="tooltip" href="#">4.37 GB / 219.56 GB<span>
    <strong>Used:</strong> 1.99%<br>
    <strong>/var/log (tmpfs):</strong> 12 MB / 256 MB</span></a></div>
  </div>
</div>
</body></html>
"""

REPEATERINFO_HTML = """
<div class='status-pill active'><span>D-Star</span>
<div class='pill-data'><i class='fa'></i></div></div>
<div class='status-pill inactive'><span>DMR</span>
<div class='pill-data'><i class='fa'></i></div></div>
<div class='status-pill paused'><span>YSF</span>
<div class='pill-data'><i class='fa'></i></div></div>
<div class='status-pill error'><span>P25</span>
<div class='pill-data'><i class='fa'></i></div></div>
<div class='status-pill active'><span>D-Star Net</span>
<div class='pill-data'><i class='fa'></i></div></div>
<div class='status-pill paused'><span>DMR Net</span>
<div class='pill-data'><i class='fa'></i></div></div>
<div class='status-pill bogus'><span>YSF Net</span>
<div class='pill-data'><i class='fa'></i></div></div>
"""


class FakeResponse:
    """Minimal aiohttp response."""

    def __init__(self, *, text: str = "", json_data=None, error=None) -> None:
        self._text = text
        self._json = json_data
        self._error = error

    def raise_for_status(self) -> None:
        if self._error:
            raise self._error

    async def text(self) -> str:
        return self._text

    async def json(self):
        return self._json

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *exc) -> None:
        return None


def make_client(response: FakeResponse | Exception) -> tuple[WpsdClient, MagicMock]:
    """Return a client whose session returns ``response`` (or raises it)."""
    session = MagicMock()
    if isinstance(response, Exception):
        session.get.side_effect = response
    else:
        session.get.return_value = response
    return WpsdClient("http://wpsd.local:8080", session), session


def test_parse_radio_status() -> None:
    assert WpsdClient._parse_radio_status(RADIOINFO_HTML) == "IDLE"


def test_parse_radio_status_missing() -> None:
    assert WpsdClient._parse_radio_status("<div></div>") == "unknown"


def test_parse_firmware() -> None:
    assert WpsdClient._parse_firmware(RADIOINFO_HTML) == "MMDVM_HS_Hat-v1.6.1"


def test_parse_firmware_missing() -> None:
    assert WpsdClient._parse_firmware("<div></div>") is None


def test_parse_tx_and_rx_freq() -> None:
    assert WpsdClient._parse_tx_freq(RADIOINFO_HTML) == "438.800 MHz"
    assert WpsdClient._parse_rx_freq(RADIOINFO_HTML) == "439.800 MHz"


def test_parse_single_freq_for_tx_and_rx() -> None:
    """Hosts using one frequency for both RX and TX (e.g. proton.org.uk)."""
    html = '<div class="divTableCell cell_content middle noMob">438.800 MHz</div>'
    assert WpsdClient._parse_tx_freq(html) == "438.800 MHz"
    assert WpsdClient._parse_rx_freq(html) == "438.800 MHz"


def test_parse_freq_with_extra_decimal_point() -> None:
    """Frequencies like 431.962.500 MHz should normalize to 431.9625 MHz."""
    html = '<div class="divTableCell cell_content middle noMob">431.962.500 MHz</div>'
    assert WpsdClient._parse_tx_freq(html) == "431.9625 MHz"
    assert WpsdClient._parse_rx_freq(html) == "431.9625 MHz"


def test_parse_freq_with_extra_decimal_point_duplex() -> None:
    """Duplex hosts with extra decimal points on both frequencies."""
    html = (
        '<div class="divTableCell cell_content middle noMob">431.962.500 MHz</div>'
        '<div class="divTableCell cell_content middle noMob">433.962.500 MHz</div>'
    )
    assert WpsdClient._parse_tx_freq(html) == "431.9625 MHz"
    assert WpsdClient._parse_rx_freq(html) == "433.9625 MHz"


def test_parse_freq_normal_decimal_unchanged() -> None:
    """Normal frequencies with a single decimal point are unchanged."""
    html = '<div class="divTableCell cell_content middle noMob">438.800 MHz</div>'
    assert WpsdClient._parse_tx_freq(html) == "438.800 MHz"


def test_parse_freq_missing() -> None:
    assert WpsdClient._parse_tx_freq("<div></div>") is None
    assert WpsdClient._parse_rx_freq("<div></div>") is None


def test_parse_cpu_load() -> None:
    assert WpsdClient._parse_cpu_load(HOMEPAGE_HTML) == "38"


def test_parse_cpu_temp() -> None:
    assert WpsdClient._parse_cpu_temp(HOMEPAGE_HTML).startswith("135°F / 57°C")


def test_parse_cpu_missing() -> None:
    assert WpsdClient._parse_cpu_load("<div></div>") is None
    assert WpsdClient._parse_cpu_temp("<div></div>") is None


def test_parse_callsign() -> None:
    assert WpsdClient._parse_callsign(HOMEPAGE_HTML) == "W4DW"


@pytest.mark.parametrize(
    "html",
    [
        "<html></html>",
        "<title></title>",
        "<title> - Dashboard</title>",
    ],
)
def test_parse_callsign_missing(html: str) -> None:
    assert WpsdClient._parse_callsign(html) is None


def test_parse_callsign_without_separator() -> None:
    assert WpsdClient._parse_callsign("<title>N0CALL</title>") == "N0CALL"


def test_parse_dashboard_version_is_git_hash() -> None:
    assert WpsdClient._parse_dashboard_version(HOMEPAGE_HTML) == "abc1234def"


def test_parse_dashboard_version_ignores_branch_suffix() -> None:
    html = (
        "<span title='WPSD Dashboard Version # abc1234def'>"
        "WPSD Dashboard Ver.# abc1234def</span> / Branch: dev"
    )
    assert WpsdClient._parse_dashboard_version(html) == "abc1234def"


@pytest.mark.parametrize(
    "html",
    [
        "<span>something else</span>",
        "<span>WPSD Dashboard Ver.#</span>",
        "",
    ],
)
def test_parse_dashboard_version_missing(html: str) -> None:
    assert WpsdClient._parse_dashboard_version(html) is None


def test_parse_disk_usage_root() -> None:
    assert WpsdClient._parse_disk_usage_stats(HOMEPAGE_HTML, "/") == {
        "percent": 1.99,
        "used_gb": 4.37,
        "total_gb": 219.56,
    }


def test_parse_disk_usage_missing() -> None:
    assert WpsdClient._parse_disk_usage_stats("<div></div>", "/") is None


def test_parse_disk_usage_converts_units() -> None:
    html = """
    <div class="stat-card"><span class="stat-label">Disk Usage</span>
    <div class="stat-value"><a href="#">512 MB / 2 GB</a></div></div>
    """
    stats = WpsdClient._parse_disk_usage_stats(html, "/")
    assert stats == {"percent": 25.0, "used_gb": 0.5, "total_gb": 2}


def test_parse_disk_usage_varlog_comes_from_tooltip() -> None:
    stats = WpsdClient._parse_disk_usage_stats(HOMEPAGE_HTML, "/var/log")
    assert stats == {"percent": 4.69, "used_gb": 12 / 1024, "total_gb": 0.25}


def test_parse_disk_usage_varlog_missing_from_tooltip() -> None:
    html = """
    <div class="stat-card"><span class="stat-label">Disk Usage</span>
    <div class="stat-value">
    <a href="#">4.37 GB / 219.56 GB<span>no varlog</span></a>
    </div></div>
    """
    assert WpsdClient._parse_disk_usage_stats(html, "/var/log") is None
    assert WpsdClient._parse_disk_usage_stats(html, "/") is not None


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (1, "GB", 1),
        (1, "gb", 1),
        (1024, "MB", 1),
        (1, "TB", 1024),
        (1024**2, "KB", 1),
        (1024**3, "B", 1),
        (5, "weird", 5),
    ],
)
def test_convert_to_gb(value: float, unit: str, expected: float) -> None:
    assert _convert_to_gb(value, unit) == pytest.approx(expected)


def test_parse_modes_enabled() -> None:
    modes = WpsdClient._parse_modes_enabled(REPEATERINFO_HTML)
    assert modes["D-Star"] == "active"
    assert modes["DMR"] == "inactive"
    assert modes["YSF"] == "paused"
    assert modes["P25"] == "error"


def test_parse_modes_enabled_pill_without_status_class() -> None:
    html = "<div class='status-pill'><span>DMR</span></div>"
    assert WpsdClient._parse_modes_enabled(html) == {"DMR": "unknown"}


def test_parse_modes_enabled_empty() -> None:
    assert WpsdClient._parse_modes_enabled("") == {}


def test_parse_network_status_only_net_pills() -> None:
    networks = WpsdClient._parse_network_status(REPEATERINFO_HTML)
    assert networks["D-Star Net"] == "active"
    assert networks["DMR Net"] == "paused"
    assert "D-Star" not in networks


def test_parse_network_status_invalid_defaults_to_inactive(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        networks = WpsdClient._parse_network_status(REPEATERINFO_HTML)
    assert networks["YSF Net"] == "inactive"
    assert "Invalid network status 'bogus' for 'YSF Net'" in caplog.text


async def test_base_url_uses_host_and_port() -> None:
    client, session = make_client(FakeResponse(text="x"))
    await client.async_get_callsign()
    session.get.assert_called_once_with(f"http://wpsd.local:8080{ENDPOINT_HOMEPAGE}")


async def test_get_last_heard() -> None:
    client, session = make_client(FakeResponse(json_data=[{"callsign": "W4DW"}]))
    assert await client.async_get_last_heard(limit=3) == [{"callsign": "W4DW"}]
    url = session.get.call_args.args[0]
    assert url == (
        f"http://wpsd.local:8080{ENDPOINT_API}?limit=3&names=false&country=false"
    )


async def test_get_last_heard_non_list_is_empty() -> None:
    client, _ = make_client(FakeResponse(json_data={"error": "nope"}))
    assert await client.async_get_last_heard() == []


async def test_get_radio_data_fetches_once() -> None:
    client, session = make_client(FakeResponse(text=RADIOINFO_HTML))
    assert await client.async_get_radio_data() == {
        "radio_status": "IDLE",
        "firmware": "MMDVM_HS_Hat-v1.6.1",
        "tx_freq": "438.800 MHz",
        "rx_freq": "439.800 MHz",
    }
    session.get.assert_called_once_with(f"http://wpsd.local:8080{ENDPOINT_RADIOINFO}")


async def test_get_homepage_data_fetches_once() -> None:
    client, session = make_client(FakeResponse(text=HOMEPAGE_HTML))
    data = await client.async_get_homepage_data()
    assert data["dashboard_version"] == "abc1234def"
    assert data["cpu_load"] == "38"
    assert data["cpu_temp"].startswith("135°F / 57°C")
    assert data["disk_root"]["total_gb"] == 219.56
    session.get.assert_called_once()


async def test_parse_hw_info_data() -> None:
    data = WpsdClient.parse_hw_info_data(HW_INFO_HTML)
    assert data["cpu_load"] == "38"
    assert data["cpu_temp"].startswith("135°F / 57°C")
    assert data["disk_root"] == {
        "percent": 1.99,
        "used_gb": 4.37,
        "total_gb": 219.56,
    }


async def test_parse_hw_info_data_missing() -> None:
    data = WpsdClient.parse_hw_info_data("<div></div>")
    assert data["cpu_load"] is None
    assert data["cpu_temp"] is None
    assert data["disk_root"] is None
    assert data["disk_varlog"] is None


async def test_get_hw_info_data_fetches_once() -> None:
    client, session = make_client(FakeResponse(text=HW_INFO_HTML))
    data = await client.async_get_hw_info_data()
    assert data["cpu_load"] == "38"
    assert data["cpu_temp"].startswith("135°F / 57°C")
    assert data["disk_root"]["total_gb"] == 219.56
    session.get.assert_called_once_with(f"http://wpsd.local:8080{ENDPOINT_HW_INFO}")


async def test_get_modes_with_network_fetches_once() -> None:
    client, session = make_client(FakeResponse(text=REPEATERINFO_HTML))
    modes, networks = await client.async_get_modes_with_network()
    assert modes["DMR"] == "inactive"
    assert networks["DMR Net"] == "paused"
    session.get.assert_called_once_with(
        f"http://wpsd.local:8080{ENDPOINT_REPEATERINFO}"
    )


async def test_get_callsign() -> None:
    client, _ = make_client(FakeResponse(text=HOMEPAGE_HTML))
    assert await client.async_get_callsign() == "W4DW"


@pytest.mark.parametrize("method", ["_async_get_text", "_async_get_json"])
async def test_http_error_status_is_raised(method: str) -> None:
    error = aiohttp.ClientResponseError(MagicMock(), (), status=500)
    client, _ = make_client(FakeResponse(error=error))
    with pytest.raises(aiohttp.ClientResponseError):
        await getattr(client, method)("/x")


@pytest.mark.parametrize("method", ["_async_get_text", "_async_get_json"])
async def test_connection_error_is_raised(method: str) -> None:
    client, _ = make_client(aiohttp.ClientConnectionError("down"))
    with pytest.raises(aiohttp.ClientError):
        await getattr(client, method)("/x")
