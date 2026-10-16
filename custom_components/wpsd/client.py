"""Client for interacting with WPSD."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import async_timeout
from bs4 import BeautifulSoup

from .const import (
    DEFAULT_PORT,
    ENDPOINT_API,
    ENDPOINT_HOMEPAGE,
    ENDPOINT_RADIOINFO,
    ENDPOINT_REPEATERINFO,
)

_LOGGER = logging.getLogger(__name__)


class WpsdClient:
    """Client for WPSD API and HTML endpoints."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the WPSD client."""
        self._host = host
        self._port = port
        self._session = session
        self._base_url = f"http://{host}:{port}"

    async def _async_get_json(self, endpoint: str) -> Any:
        """Fetch JSON from an endpoint."""
        session = self._session or aiohttp.ClientSession()
        close_session = self._session is None
        try:
            async with async_timeout.timeout(10):
                async with session.get(f"{self._base_url}{endpoint}") as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error fetching %s: %s", endpoint, err)
            raise
        finally:
            if close_session:
                await session.close()

    async def _async_get_text(self, endpoint: str) -> str:
        """Fetch text/HTML from an endpoint."""
        session = self._session or aiohttp.ClientSession()
        close_session = self._session is None
        try:
            async with async_timeout.timeout(10):
                async with session.get(f"{self._base_url}{endpoint}") as resp:
                    resp.raise_for_status()
                    return await resp.text()
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error fetching %s: %s", endpoint, err)
            raise
        finally:
            if close_session:
                await session.close()

    async def async_get_last_heard(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get last-heard transmissions from the JSON API."""
        data = await self._async_get_json(
            f"{ENDPOINT_API}?limit={limit}&names=false&country=false"
        )
        return data if isinstance(data, list) else []

    async def async_get_radio_status(self) -> str:
        """Get the radio status text from radioinfo.php."""
        html = await self._async_get_text(ENDPOINT_RADIOINFO)
        return self._parse_radio_status(html)

    async def async_get_modes_enabled(self) -> dict[str, str]:
        """Get the enabled/paused/inactive state of each mode from repeaterinfo.php."""
        html = await self._async_get_text(ENDPOINT_REPEATERINFO)
        return self._parse_modes_enabled(html)

    async def async_get_firmware(self) -> str | None:
        """Get the modem firmware version from radioinfo.php."""
        html = await self._async_get_text(ENDPOINT_RADIOINFO)
        return self._parse_firmware(html)

    async def async_get_homepage(self) -> str:
        """Get the WPSD dashboard homepage HTML."""
        return await self._async_get_text(ENDPOINT_HOMEPAGE)

    async def async_get_radio_data(self) -> dict[str, Any]:
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

    async def async_get_homepage_data(self) -> dict[str, Any]:
        """Fetch the homepage once and return all parsed dashboard data.

        Returns a dict with keys: dashboard_version, cpu_load, cpu_temp,
        net_traffic, disk_root, disk_varlog.
        """
        html = await self._async_get_text(ENDPOINT_HOMEPAGE)
        disk_root = self._parse_disk_usage_stats(html, "/")
        disk_varlog = self._parse_disk_usage_stats(html, "/var/log")
        return {
            "dashboard_version": self._parse_dashboard_version(html),
            "cpu_load": self._parse_cpu_load(html),
            "cpu_temp": self._parse_cpu_temp(html),
            "net_traffic": self._parse_net_traffic(html),
            "disk_root": disk_root,
            "disk_varlog": disk_varlog,
        }

    async def async_get_dashboard_version(self) -> str | None:
        """Get the WPSD dashboard version from homepage HTML."""
        html = await self._async_get_text(ENDPOINT_HOMEPAGE)
        return self._parse_dashboard_version(html)

    async def async_get_disk_usage_root(self) -> dict[str, float | None] | None:
        """Get root disk usage stats from homepage HTML."""
        html = await self._async_get_text(ENDPOINT_HOMEPAGE)
        return self._parse_disk_usage_stats(html, "/")

    async def async_get_disk_usage_varlog(self) -> dict[str, float | None] | None:
        """Get /var/log disk usage stats from homepage HTML."""
        html = await self._async_get_text(ENDPOINT_HOMEPAGE)
        return self._parse_disk_usage_stats(html, "/var/log")

    async def async_get_tx_freq(self) -> str | None:
        """Get the TX frequency from radioinfo.php."""
        html = await self._async_get_text(ENDPOINT_RADIOINFO)
        return self._parse_tx_freq(html)

    async def async_get_rx_freq(self) -> str | None:
        """Get the RX frequency from radioinfo.php."""
        html = await self._async_get_text(ENDPOINT_RADIOINFO)
        return self._parse_rx_freq(html)

    async def async_get_cpu_load(self) -> str | None:
        """Get the CPU load percentage from the homepage."""
        html = await self._async_get_text(ENDPOINT_HOMEPAGE)
        return self._parse_cpu_load(html)

    async def async_get_cpu_temp(self) -> str | None:
        """Get the CPU temperature from the homepage."""
        html = await self._async_get_text(ENDPOINT_HOMEPAGE)
        return self._parse_cpu_temp(html)

    async def async_get_net_traffic(self) -> str | None:
        """Get the network traffic from the homepage."""
        html = await self._async_get_text(ENDPOINT_HOMEPAGE)
        return self._parse_net_traffic(html)

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
            classes = pill.get("class", [])
            status = next((c for c in classes if c != "status-pill"), "unknown")
            span = pill.find("span")
            if span:
                mode = span.get_text(strip=True)
                modes[mode] = status
        return modes

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
                    import re

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
    def _parse_dashboard_version(html: str) -> str | None:
        """Parse the WPSD dashboard version from homepage HTML.

        Looks for text like "WPSD Dashboard Ver.# 1.2.3" in the page.
        """
        import re

        match = re.search(r"WPSD Dashboard Ver\.#\s*([\d.]+)", html)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _parse_disk_usage_stats(
        html: str, mount: str
    ) -> dict[str, float | None] | None:
        """Parse disk usage stats for a given mount point from homepage HTML.

        Returns a dict with keys: 'percent', 'used_gb', 'total_gb'.
        """
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("div.stat-card"):
            label = card.select_one("span.stat-label")
            if label and "Disk Usage" in label.get_text():
                value = card.select_one("div.stat-value")
                if value:
                    anchor = value.find("a")
                    if anchor:
                        # Get the main text (e.g. "4.37 GB / 219.56 GB")
                        # The anchor's first text node is the main value
                        main_text = ""
                        for content in anchor.contents:
                            if isinstance(content, str):
                                main_text = content.strip()
                                break
                        if not main_text:
                            main_text = (
                                anchor.get_text(strip=True).split("Used:")[0].strip()
                            )

                        # Parse "X GB / Y GB" or "X MB / Y MB" etc.
                        import re

                        match = re.search(
                            r"([\d.]+)\s*(\w+)\s*/\s*([\d.]+)\s*(\w+)", main_text
                        )
                        if match:
                            used_val = float(match.group(1))
                            used_unit = match.group(2)
                            total_val = float(match.group(3))
                            total_unit = match.group(4)

                            # Convert to GB
                            used_gb = _convert_to_gb(used_val, used_unit)
                            total_gb = _convert_to_gb(total_val, total_unit)
                            percent = (
                                round((used_gb / total_gb) * 100, 2)
                                if total_gb > 0
                                else None
                            )

                            return {
                                "percent": percent,
                                "used_gb": used_gb,
                                "total_gb": total_gb,
                            }
        return None

    @staticmethod
    def _parse_net_traffic(html: str) -> str | None:
        """Parse the network traffic from homepage HTML."""
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("div.stat-card"):
            label = card.select_one("span.stat-label")
            if label and "Net Traffic" in label.get_text():
                value = card.select_one("div.stat-value")
                if value:
                    return value.get_text(strip=True)
        return None


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
