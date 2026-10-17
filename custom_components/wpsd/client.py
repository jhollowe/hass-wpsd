"""Client for interacting with WPSD."""

from __future__ import annotations

import asyncio
import re
from typing import Any, TypedDict

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    ENDPOINT_API,
    ENDPOINT_CHECKUPDATES,
    ENDPOINT_HOMEPAGE,
    ENDPOINT_HW_INFO,
    ENDPOINT_RADIOINFO,
    ENDPOINT_REPEATERINFO,
    LOGGER,
)

REQUEST_TIMEOUT = 10

_FAHRENHEIT_TEMP = re.compile(r"([\d.]+)°F")
_DASHBOARD_VERSION_RE = re.compile(r"(?:Version #|Ver\.#)\s*([\w]+)")


class DiskUsage(TypedDict):
    """Usage of one filesystem, as shown on the dashboard."""

    percent: float | None
    used_gb: float
    total_gb: float


class RadioData(TypedDict):
    """Values parsed from radioinfo.php."""

    radio_status: str
    modem_firmware: str | None
    tx_freq: str | None
    rx_freq: str | None


class HWInfoData(TypedDict):
    """Values parsed from includes/hw_info.php."""

    cpu_load: int | None
    cpu_temp: int | None
    disk_root: DiskUsage | None
    disk_varlog: DiskUsage | None


def _normalize_url(url: str) -> str:
    """Normalize a URL, adding http:// scheme if missing."""
    # TODO is there a lib to do this?
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url.rstrip("/")


class WpsdClient:
    """Client for WPSD API and HTML endpoints."""

    def __init__(
        self,
        url: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the WPSD client."""
        self._session = session
        self._base_url = _normalize_url(url)
        self.callsign: str | None = None
        self.dashboard_version: str | None = None

    async def _async_get_json(self, endpoint: str) -> Any:
        """Fetch JSON from an endpoint."""
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with self._session.get(f"{self._base_url}{endpoint}") as resp:
                resp.raise_for_status()
                return await resp.json()

    async def _async_get_text(self, endpoint: str) -> str:
        """Fetch text/HTML from an endpoint."""
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with self._session.get(f"{self._base_url}{endpoint}") as resp:
                resp.raise_for_status()
                return await resp.text()

    async def async_get_last_heard(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get last-heard transmissions from the JSON API."""
        data = await self._async_get_json(
            f"{ENDPOINT_API}?limit={limit}&names=false&country=false"
        )
        return data if isinstance(data, list) else []

    async def async_get_radio_html(self) -> str:
        """Fetch radioinfo.php HTML."""
        return await self._async_get_text(ENDPOINT_RADIOINFO)

    async def async_get_repeater_html(self) -> str:
        """Fetch repeaterinfo.php HTML."""
        return await self._async_get_text(ENDPOINT_REPEATERINFO)

    @staticmethod
    def parse_radio_data(html: str) -> RadioData:
        """Parse radioinfo.php HTML into a RadioData dict.

        Runs in the executor because BeautifulSoup parsing is CPU-bound.
        """
        return {
            "radio_status": WpsdClient._parse_radio_status(html),
            "modem_firmware": WpsdClient._parse_modem_firmware(html),
            "tx_freq": WpsdClient._parse_tx_freq(html),
            "rx_freq": WpsdClient._parse_rx_freq(html),
        }

    @staticmethod
    def parse_modes_with_network(
        html: str,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Parse repeaterinfo.php HTML into modes and networks dicts.

        Runs in the executor because BeautifulSoup parsing is CPU-bound.
        """
        return WpsdClient._parse_modes_enabled(html), WpsdClient._parse_network_status(
            html
        )

    async def async_get_radio_data(self) -> RadioData:
        """Fetch radioinfo.php once and return all parsed radio data.

        Returns a dict with keys: radio_status, firmware, tx_freq, rx_freq.
        """
        html = await self.async_get_radio_html()
        return self.parse_radio_data(html)

    async def async_get_hw_info_html(self) -> str:
        """Fetch hw_info.php HTML."""
        return await self._async_get_text(ENDPOINT_HW_INFO)

    @staticmethod
    def parse_hw_info_data(html: str) -> HWInfoData:
        """Parse hw_info.php HTML into an HWInfoData dict.

        Runs in the executor because BeautifulSoup parsing is CPU-bound.
        """
        return {
            "cpu_load": WpsdClient._parse_cpu_load(html),
            "cpu_temp": WpsdClient._parse_cpu_temp(html),
            "disk_root": WpsdClient._parse_disk_usage_stats(html, "/"),
            "disk_varlog": WpsdClient._parse_disk_usage_stats(html, "/var/log"),
        }

    async def async_get_hw_info_data(self) -> HWInfoData:
        """Fetch hw_info.php once and return all parsed hardware data.

        Returns a dict with keys: cpu_load, cpu_temp, disk_root, disk_varlog.
        """
        html = await self.async_get_hw_info_html()
        return self.parse_hw_info_data(html)

    async def async_get_modes_with_network(
        self,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Get mode enabled states and network status from repeaterinfo.php.

        Fetches repeaterinfo.php once and returns both mode states and
        network statuses.

        Returns a tuple of (modes_dict, networks_dict).
        """
        html = await self.async_get_repeater_html()
        return self.parse_modes_with_network(html)

    async def async_get_callsign(self) -> str | None:
        """Get the hotspot callsign from the homepage title."""
        return self._parse_callsign(await self._async_get_text(ENDPOINT_HOMEPAGE))

    @staticmethod
    def _parse_radio_status(html: str) -> str:
        """Parse the active mode / radio status from radioinfo.php HTML."""
        soup = BeautifulSoup(html, "html.parser")
        # Look for the status cell in the data row
        cells = soup.select("div.divTableCell.middle.cell_content")
        if cells:
            return cells[0].get_text(strip=True)
        return "unknown"

    @staticmethod
    def _parse_modem_firmware(html: str) -> str | None:
        """Parse the modem firmware version from radioinfo.php HTML.

        The firmware is in the last cell of the radio status row.
        """
        soup = BeautifulSoup(html, "html.parser")
        cells = soup.select("div.divTableCell.cell_content.middle.noMob")
        for cell in reversed(cells):
            text = cell.get_text(strip=True)
            if any(k in text for k in ("MMDVM", "RB_", "DVM", "dvmega")):
                return text
        return None

    @staticmethod
    def _parse_dmr_id(html: str) -> str | None:
        """Parse the DMR ID from repeaterinfo.php HTML.

        The DMR ID is rendered as a status-pill with span text "DMR ID"
        and the value in a .pill-value span.
        """
        soup = BeautifulSoup(html, "html.parser")
        for pill in soup.select("div.status-pill"):
            span = pill.find("span")
            if span and span.get_text(strip=True) == "DMR ID":
                value_span = pill.select_one("span.pill-value")
                if value_span:
                    return value_span.get_text(strip=True) or None
        return None

    @staticmethod
    def _parse_dmr_cc(html: str) -> str | None:
        """Parse the DMR Color Code (CC) from repeaterinfo.php HTML.

        The CC is rendered as a status-pill with span text "CC"
        and the value in a .pill-value span.
        """
        soup = BeautifulSoup(html, "html.parser")
        for pill in soup.select("div.status-pill"):
            span = pill.find("span")
            if span and span.get_text(strip=True) == "CC":
                value_span = pill.select_one("span.pill-value")
                if value_span:
                    return value_span.get_text(strip=True) or None
        return None

    @staticmethod
    def _normalize_frequency(text: str) -> str:
        """Normalize a frequency string, collapsing extra decimal points.

        Some WPSD hosts render frequencies with an extra dot, e.g.
        ``431.962.500 MHz`` instead of ``431.9625 MHz``. This keeps the
        first dot as the decimal separator, drops subsequent dots, and
        strips trailing zeros from the fractional part.
        """
        match = re.match(r"([\d.]+)(\s*.*)", text)
        if not match:
            return text
        number_part, rest = match.groups()
        parts = number_part.split(".")
        if len(parts) <= 2:
            return text
        normalized = parts[0] + "." + "".join(parts[1:])
        # Drop trailing zeros from the fractional part (e.g. 431.962500 -> 431.9625)
        integer_part, _, fractional = normalized.partition(".")
        fractional = fractional.rstrip("0") or "0"
        normalized = f"{integer_part}.{fractional}"
        return f"{normalized}{rest}"

    @staticmethod
    def _parse_tx_freq(html: str) -> str | None:
        """Parse the TX frequency from radioinfo.php HTML.

        When a host uses a single frequency for both RX and TX (simplex),
        that frequency is returned as the TX frequency.
        """
        soup = BeautifulSoup(html, "html.parser")
        cells = soup.select("div.divTableCell.cell_content.middle.noMob")
        freq_cells = [c.get_text(strip=True) for c in cells if "MHz" in c.get_text()]
        if freq_cells:
            return WpsdClient._normalize_frequency(freq_cells[0])
        return None

    @staticmethod
    def _parse_rx_freq(html: str) -> str | None:
        """Parse the RX frequency from radioinfo.php HTML.

        When a host uses a single frequency for both RX and TX (simplex),
        that frequency is returned as the RX frequency.
        """
        soup = BeautifulSoup(html, "html.parser")
        cells = soup.select("div.divTableCell.cell_content.middle.noMob")
        freq_cells = [c.get_text(strip=True) for c in cells if "MHz" in c.get_text()]
        if len(freq_cells) >= 2:
            return WpsdClient._normalize_frequency(freq_cells[1])
        if freq_cells:
            return WpsdClient._normalize_frequency(freq_cells[0])
        return None

    @staticmethod
    def _parse_modes_enabled(html: str) -> dict[str, str]:
        """Parse mode pills from repeaterinfo.php HTML.

        Returns a dict mapping mode name to status: active, paused, error, inactive.
        """
        soup = BeautifulSoup(html, "html.parser")
        modes: dict[str, str] = {}
        for pill in soup.select("div.status-pill"):
            classes = pill.get_attribute_list("class")
            status = next((c for c in classes if c != "status-pill"), "unknown")
            span = pill.find("span")
            if span:
                mode = span.get_text(strip=True)
                modes[mode] = status
        return modes

    @staticmethod
    def _parse_network_status(html: str) -> dict[str, str]:
        """Parse network status pills from repeaterinfo.php HTML.

        Returns a dict mapping network name (e.g. "D-Star Net") to status:
        active, paused, error, inactive.
        """
        VALID_STATUSES = {"active", "paused", "error", "inactive"}
        soup = BeautifulSoup(html, "html.parser")
        networks: dict[str, str] = {}
        for pill in soup.select("div.status-pill"):
            classes = pill.get_attribute_list("class")
            status = next((c for c in classes if c != "status-pill"), "inactive")
            span = pill.find("span")
            if span:
                name = span.get_text(strip=True)
                if name.endswith(" Net"):
                    if status not in VALID_STATUSES:
                        LOGGER.warning(
                            "Invalid network status '%s' for '%s', "
                            "defaulting to 'inactive'",
                            status,
                            name,
                        )
                        status = "inactive"
                    networks[name] = status
        return networks

    @staticmethod
    def _parse_cpu_load(html: str) -> int | None:
        """Parse the CPU load percentage from hw_info HTML."""
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("div.stat-card"):
            label = card.select_one("span.stat-label")
            if label and "CPU Load" in label.get_text():
                value = card.select_one("div.stat-value")
                if value:
                    text = value.get_text(strip=True)
                    # Extract the percentage (e.g. "38%" -> 38)
                    match = re.search(r"(\d+)%", text)
                    if match:
                        return int(match.group(1))
        return None

    @staticmethod
    def _parse_cpu_temp(html: str) -> int | None:
        """Parse the CPU temperature in Fahrenheit from hw_info HTML.

        The value is rendered like ``135°F / 57°C``. Returns the Fahrenheit
        value as an integer, or None if it cannot be parsed.
        """
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("div.stat-card"):
            label = card.select_one("span.stat-label")
            if label and "CPU Temp" in label.get_text():
                value = card.select_one("div.stat-value")
                if value:
                    text = value.get_text(strip=True)
                    match = _FAHRENHEIT_TEMP.search(text)
                    if match:
                        return int(float(match.group(1)))
        return None

    @staticmethod
    def _parse_callsign(html: str) -> str | None:
        """Parse the callsign from the homepage title.

        The title has the form "<CALLSIGN> - Dashboard".
        """
        title = BeautifulSoup(html, "html.parser").title
        if title is None:
            return None
        callsign = title.get_text().split(" - ", 1)[0].strip()
        return callsign or None

    async def async_get_dashboard_version(self) -> str | None:
        """Get the WPSD dashboard version from includes/checkupdates.php.

        This endpoint returns HTML like
        ``<span title='WPSD Dashboard Version # 1e76fbbfa8'>
        WPSD Dashboard Ver.# 1e76fbbfa8</span>``.
        Only the git short hash is extracted.
        """
        text = await self._async_get_text(ENDPOINT_CHECKUPDATES)
        if not text:
            return None
        soup = BeautifulSoup(text, "html.parser")
        span = soup.find("span")
        if span is not None:
            text = span.get_text(strip=True)
        match = _DASHBOARD_VERSION_RE.search(text)
        if match:
            return match.group(1)
        return text.strip() or None

    @staticmethod
    def _parse_disk_usage_stats(html: str, mount: str) -> DiskUsage | None:
        """Parse disk usage stats for a given mount point from hw_info HTML.

        The "Disk Usage" card shows the root filesystem as "<used> / <total>".
        Its tooltip lists /var/log as "<strong>/var/log (tmpfs):</strong>
        <used> / <total> (...)".

        Returns a dict with keys: 'percent', 'used_gb', 'total_gb'.
        """
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("div.stat-card"):
            label = card.select_one("span.stat-label")
            if not label or "Disk Usage" not in label.get_text():
                continue
            anchor = card.select_one("div.stat-value a")
            if anchor is None:
                continue

            if mount == "/":
                # The anchor's first text node is the main value
                text = next(
                    (c.strip() for c in anchor.contents if isinstance(c, str)), ""
                )
            else:
                text = ""
                for strong in anchor.find_all("strong"):
                    if strong.get_text(strip=True).startswith(mount):
                        sibling = strong.next_sibling
                        text = sibling.strip() if isinstance(sibling, str) else ""
                        break

            match = _SIZE_PAIR.search(text)
            if not match:
                return None
            used_gb = _convert_to_gb(float(match.group(1)), match.group(2))
            total_gb = _convert_to_gb(float(match.group(3)), match.group(4))
            return {
                "percent": round(used_gb / total_gb * 100, 2) if total_gb > 0 else None,
                "used_gb": used_gb,
                "total_gb": total_gb,
            }
        return None


_SIZE_PAIR = re.compile(r"([\d.]+)\s*(\w+)\s*/\s*([\d.]+)\s*(\w+)")


def _convert_to_gb(value: float, unit: str) -> float:
    """Convert a size value to GB."""
    unit = unit.upper()
    multipliers = {
        "B": 1 / (1024**3),
        "KB": 1 / (1024**2),
        "MB": 1 / 1024,
        "GB": 1,
        "TB": 1024,
        "PB": 1024**2,
    }
    return value * multipliers.get(unit, 1)
