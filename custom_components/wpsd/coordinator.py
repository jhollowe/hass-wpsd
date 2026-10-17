"""Data update coordinators for the WPSD integration."""

from __future__ import annotations

import asyncio
from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import DiskUsage, WpsdClient
from .const import (
    CONF_MODE_SCAN_INTERVAL,
    CONF_SYSTEM_SCAN_INTERVAL,
    DEFAULT_MODE_SCAN_INTERVAL,
    DEFAULT_SYSTEM_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .repairs import (
    async_create_unreachable_issue,
    async_delete_unreachable_issue,
)

type WpsdConfigEntry = ConfigEntry[WpsdData]


@dataclass
class WpsdSystemData:
    """Radio and dashboard data as shown by WPSD (raw text values)."""

    active_mode: str
    modem_firmware: str | None
    dashboard_version: str | None
    tx_freq: str | None
    rx_freq: str | None
    cpu_load: int | None
    cpu_temp: int | None
    disk_root: DiskUsage | None
    disk_varlog: DiskUsage | None


@dataclass
class WpsdModeData:
    """Status of each mode and of its network, keyed by WPSD's names."""

    modes: dict[str, str]
    networks: dict[str, str]


class WpsdCoordinator[DataT](DataUpdateCoordinator[DataT]):
    """Base coordinator for polling one group of WPSD pages."""

    config_entry: WpsdConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WpsdConfigEntry,
        client: WpsdClient,
        *,
        name: str,
        interval_option: str,
        default_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{name}",
            update_interval=timedelta(
                seconds=config_entry.options.get(interval_option, default_interval)
            ),
        )
        self.client = client

    async def _async_update_data(self) -> DataT:
        """Fetch data from WPSD."""
        try:
            data = await self._async_fetch()
        except (TimeoutError, aiohttp.ClientError) as err:
            await async_create_unreachable_issue(
                self.hass,
                self.config_entry.entry_id,
                self.config_entry.data.get("url", ""),
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err
        await async_delete_unreachable_issue(self.hass, self.config_entry.entry_id)
        return data

    @abstractmethod
    async def _async_fetch(self) -> DataT:
        """Fetch and parse the pages this coordinator polls."""


class WpsdSystemCoordinator(WpsdCoordinator[WpsdSystemData]):
    """Polls radio and dashboard data (frequencies, firmware, system stats)."""

    def __init__(
        self, hass: HomeAssistant, config_entry: WpsdConfigEntry, client: WpsdClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            config_entry,
            client,
            name="system",
            interval_option=CONF_SYSTEM_SCAN_INTERVAL,
            default_interval=DEFAULT_SYSTEM_SCAN_INTERVAL,
        )

    async def _async_fetch(self) -> WpsdSystemData:
        """Fetch each page once, concurrently, parsing HTML in the executor."""
        radio_html, hw_info_html = await asyncio.gather(
            self.client.async_get_radio_html(),
            self.client.async_get_hw_info_html(),
        )
        radio_data, hw_info_data = await asyncio.gather(
            self.hass.async_add_executor_job(self.client.parse_radio_data, radio_html),
            self.hass.async_add_executor_job(
                self.client.parse_hw_info_data, hw_info_html
            ),
        )
        return WpsdSystemData(
            active_mode=radio_data["radio_status"],
            modem_firmware=radio_data["modem_firmware"],
            dashboard_version=self.client.dashboard_version,
            tx_freq=radio_data["tx_freq"],
            rx_freq=radio_data["rx_freq"],
            cpu_load=hw_info_data["cpu_load"],
            cpu_temp=hw_info_data["cpu_temp"],
            disk_root=hw_info_data["disk_root"],
            disk_varlog=hw_info_data["disk_varlog"],
        )


class WpsdModeCoordinator(WpsdCoordinator[WpsdModeData]):
    """Polls the status of each mode and its network."""

    def __init__(
        self, hass: HomeAssistant, config_entry: WpsdConfigEntry, client: WpsdClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            config_entry,
            client,
            name="modes",
            interval_option=CONF_MODE_SCAN_INTERVAL,
            default_interval=DEFAULT_MODE_SCAN_INTERVAL,
        )

    async def _async_fetch(self) -> WpsdModeData:
        """Fetch mode and network status, parsing HTML in the executor."""
        html = await self.client.async_get_repeater_html()
        modes, networks = await self.hass.async_add_executor_job(
            self.client.parse_modes_with_network, html
        )
        return WpsdModeData(modes=modes, networks=networks)


@dataclass
class WpsdData:
    """Runtime data shared by the platforms of one config entry."""

    client: WpsdClient
    system_coordinator: WpsdSystemCoordinator
    mode_coordinator: WpsdModeCoordinator
