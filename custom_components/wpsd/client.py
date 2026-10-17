"""Client for interacting with WPSD."""

from __future__ import annotations

import asyncio
import re
from typing import Any, TypedDict

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    ENDPOINT_API,
    ENDPOINT_HOMEPAGE,
    ENDPOINT_RADIOINFO,
    ENDPOINT_REPEATERINFO,
    LOGGER,
)

REQUEST_TIMEOUT = 10


class DiskUsage(TypedDict):
    """Usage of one filesystem, as shown on the dashboard."""

    percent: float | None
    used_gb: float
    total_gb: float


class RadioData(TypedDict):
    """Values parsed from radioinfo.php."""

    radio_status: str
    firmware: str | None
    tx_freq: str | None
    rx_freq: str | None


class HomepageData(TypedDict):
    """Values parsed from the dashboard homepage."""

    dashboard_version: str | None
    cpu_load: str | None
    cpu_temp: str | None
    disk_root: DiskUsage | None
    disk_varlog: DiskUsage | None


class WpsdClient:
    """Client for WPSD API and HTML endpoints."""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the WPSD client."""
        self._session = session
        self._base_url = f"http://{host}:{port}"
        self.callsign: str | None = None

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

    async def async_get_radio_data(self) -> RadioData:
        """Fetch radioinfo.php once and return all parsed radio data.

        Returns a dict with keys: radio_status, firmware, tx_freq, rx_freq.
        """
        html = await self._async_get_text(ENDPOINT_RADIOINFO)
        return {
            "radio_status": self._parse_radio_status(html),
            "firmware": self._parse_firmware(html),
            "tx_freq": self._parse_tx_freq(html),
            "rx_freq": self._parse_rx_freq(html),
        }

    async def async_get_homepage_data(self) -> HomepageData:
        """Fetch the homepage once and return all parsed dashboard data.

        Returns a dict with keys: dashboard_version, cpu_load, cpu_temp,
        disk_root, disk_varlog.
        """
        html = await self._async_get_text(ENDPOINT_HOMEPAGE)
        disk_root = self._parse_disk_usage_stats(html, "/")
        disk_varlog = self._parse_disk_usage_stats(html, "/var/log")
        return {
            "dashboard_version": self._parse_dashboard_version(html),
            "cpu_load": self._parse_cpu_load(html),
            "cpu_temp": self._parse_cpu_temp(html),
            "disk_root": disk_root,
            "disk_varlog": disk_varlog,
        }

    async def async_get_callsign(self) -> str | None:
        """Get the hotspot callsign from the homepage title."""
        html = await self._async_get_text(ENDPOINT_HOMEPAGE)
        return self._parse_callsign(html)

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

    async def async_get_modes_with_network(
        self,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Get mode enabled states and network status from repeaterinfo.php.

        Fetches repeaterinfo.php once and returns both mode states and
        network statuses.

        Returns a tuple of (modes_dict, networks_dict).
        """
        html = await self._async_get_text(ENDPOINT_REPEATERINFO)
        return self._parse_modes_enabled(html), self._parse_network_status(html)

    @staticmethod
    def _parse_firmware(html: str) -> str | None:
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
    def _parse_tx_freq(html: str) -> str | None:
        """Parse the TX frequency from radioinfo.php HTML."""
        soup = BeautifulSoup(html, "html.parser")
        cells = soup.select("div.divTableCell.cell_content.middle.noMob")
        for cell in cells:
            text = cell.get_text(strip=True)
            if "MHz" in text:
                return text
        return None

    @staticmethod
    def _parse_rx_freq(html: str) -> str | None:
        """Parse the RX frequency from radioinfo.php HTML."""
        soup = BeautifulSoup(html, "html.parser")
        cells = soup.select("div.divTableCell.cell_content.middle.noMob")
        freq_cells = [c.get_text(strip=True) for c in cells if "MHz" in c.get_text()]
        if len(freq_cells) >= 2:
            return freq_cells[1]
        return None

    @staticmethod
    def _parse_cpu_load(html: str) -> str | None:
        """Parse the CPU load percentage from homepage HTML."""
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("div.stat-card"):
            label = card.select_one("span.stat-label")
            if label and "CPU Load" in label.get_text():
                value = card.select_one("div.stat-value")
                if value:
                    text = value.get_text(strip=True)
                    # Extract the percentage (e.g. "38%" -> "38")
                    match = re.search(r"(\d+)%", text)
                    if match:
                        return match.group(1)
        return None

    @staticmethod
    def _parse_cpu_temp(html: str) -> str | None:
        """Parse the CPU temperature from homepage HTML."""
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("div.stat-card"):
            label = card.select_one("span.stat-label")
            if label and "CPU Temp" in label.get_text():
                value = card.select_one("div.stat-value")
                if value:
                    return value.get_text(strip=True)
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

    @staticmethod
    def _parse_dashboard_version(html: str) -> str | None:
        """Parse the WPSD dashboard version (git short hash) from homepage HTML.

        The dashboard renders it as:
        <span title='WPSD Dashboard Version # abc1234def'>
        WPSD Dashboard Ver.# abc1234def
        </span>
        """
        prefix = "WPSD Dashboard Ver"
        soup = BeautifulSoup(html, "html.parser")
        for span in soup.find_all("span"):
            text = span.get_text(strip=True)
            if text.startswith(prefix) and "#" in text:
                version = text.split("#", 1)[1].strip()
                return version or None
        return None

    @staticmethod
    def _parse_disk_usage_stats(html: str, mount: str) -> DiskUsage | None:
        """Parse disk usage stats for a given mount point from homepage HTML.

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
