"""Binary sensors for WPSD mode enabled states."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .client import WpsdClient
from .const import (
    ALL_MODES,
    CONF_MODE_SCAN_INTERVAL,
    DEFAULT_MODE_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WPSD binary sensors."""
    client: WpsdClient = hass.data[DOMAIN][entry.entry_id]

    async def async_update_data() -> dict[str, Any]:
        """Fetch mode data and network status from WPSD."""
        modes, networks = await client.async_get_modes_with_network()
        return {"modes": modes, "networks": networks}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(
            seconds=entry.options.get(
                CONF_MODE_SCAN_INTERVAL, DEFAULT_MODE_SCAN_INTERVAL
            )
        ),
    )

    await coordinator.async_config_entry_first_refresh()

    entities = [WpsdModeBinarySensor(coordinator, mode, client.callsign) for mode in ALL_MODES]
    async_add_entities(entities)


class WpsdModeBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for a WPSD mode enabled state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        mode: str,
        device_name: str | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._device_name = device_name or "WPSD"
        self._mode = mode
        self._attr_unique_id = f"{DOMAIN}_{mode.lower().replace(' ', '_')}_enabled"
        self._attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this binary sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, "wpsd_device")},
            name=self._device_name,
            manufacturer="WPSD",
            model="WPSD Hotspot",
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._mode

    @property
    def is_on(self) -> bool:
        """Return true if the mode is active."""
        data: dict[str, Any] | None = self.coordinator.data
        if data is None:
            return False
        modes = data.get("modes", {})
        status = modes.get(self._mode, "inactive")
        return status in ("active", "error")

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return extra state attributes."""
        data: dict[str, Any] | None = self.coordinator.data
        if data is None:
            return {}
        modes = data.get("modes", {})
        networks = data.get("networks", {})
        attrs: dict[str, str] = {"status": modes.get(self._mode, "unknown")}
        # Add network status as attribute for each mode
        network_name = f"{self._mode} Net"
        if network_name in networks:
            attrs["network_status"] = networks[network_name]
        return attrs
