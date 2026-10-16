"""Client for interacting with WPSD."""

from __future__ import annotations

import asyncio
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
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
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
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
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

    async def async_get_disk_usage(self) -> str | None:
        """Get the disk usage from the homepage."""
        html = await self._async_get_text(ENDPOINT_HOMEPAGE)
        return self._parse_disk_usage(html)

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
            status = next((c for c in classes if c !=
                          "status-pill"), "unknown")
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
        freq_cells = [c.get_text(strip=True)
                      for c in cells if "MHz" in c.get_text()]
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
    def _parse_disk_usage(html: str) -> str | None:
        """Parse the disk usage from homepage HTML."""
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("div.stat-card"):
            label = card.select_one("span.stat-label")
            if label and "Disk Usage" in label.get_text():
                value = card.select_one("div.stat-value")
                if value:
                    return value.get_text(strip=True)
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
