"""Data update coordinators for the WPSD integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import WpsdClient
from .const import (
    CONF_MODE_SCAN_INTERVAL,
    CONF_SYSTEM_SCAN_INTERVAL,
    DEFAULT_MODE_SCAN_INTERVAL,
    DEFAULT_SYSTEM_SCAN_INTERVAL,
    DOMAIN,
    SENSOR_ACTIVE_MODE,
    SENSOR_CPU_LOAD,
    SENSOR_CPU_TEMP,
    SENSOR_DISK_TOTAL_ROOT,
    SENSOR_DISK_TOTAL_VARLOG,
    SENSOR_DISK_USAGE_ROOT,
    SENSOR_DISK_USAGE_VARLOG,
    SENSOR_DISK_USED_ROOT,
    SENSOR_DISK_USED_VARLOG,
    SENSOR_FIRMWARE,
    SENSOR_RX_FREQ,
    SENSOR_TX_FREQ,
)

_LOGGER = logging.getLogger(__name__)


class WpsdSystemCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls radio and dashboard data (frequencies, firmware, system stats)."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: WpsdClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_system",
            update_interval=timedelta(
                seconds=entry.options.get(
                    CONF_SYSTEM_SCAN_INTERVAL, DEFAULT_SYSTEM_SCAN_INTERVAL
                )
            ),
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from WPSD."""
        # Fetch each unique endpoint once, concurrently, to avoid repeated
        # sequential HTTP requests that make setup take over 10 seconds.
        radio_data, homepage_data = await asyncio.gather(
            self._client.async_get_radio_data(),
            self._client.async_get_homepage_data(),
        )

        data: dict[str, Any] = {
            SENSOR_ACTIVE_MODE: radio_data["radio_status"],
            SENSOR_FIRMWARE: radio_data["firmware"],
            "dashboard_version": homepage_data["dashboard_version"],
            SENSOR_TX_FREQ: radio_data["tx_freq"],
            SENSOR_RX_FREQ: radio_data["rx_freq"],
            SENSOR_CPU_LOAD: homepage_data["cpu_load"],
            SENSOR_CPU_TEMP: homepage_data["cpu_temp"],
        }

        disk_root = homepage_data["disk_root"]
        if disk_root:
            data[SENSOR_DISK_USAGE_ROOT] = disk_root.get("percent")
            data[SENSOR_DISK_USED_ROOT] = disk_root.get("used_gb")
            data[SENSOR_DISK_TOTAL_ROOT] = disk_root.get("total_gb")

        disk_varlog = homepage_data["disk_varlog"]
        if disk_varlog:
            data[SENSOR_DISK_USAGE_VARLOG] = disk_varlog.get("percent")
            data[SENSOR_DISK_USED_VARLOG] = disk_varlog.get("used_gb")
            data[SENSOR_DISK_TOTAL_VARLOG] = disk_varlog.get("total_gb")

        return data


class WpsdModeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the status of each mode and its network."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: WpsdClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_modes",
            update_interval=timedelta(
                seconds=entry.options.get(
                    CONF_MODE_SCAN_INTERVAL, DEFAULT_MODE_SCAN_INTERVAL
                )
            ),
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch mode and network status from WPSD."""
        modes, networks = await self._client.async_get_modes_with_network()
        return {"modes": modes, "networks": networks}
