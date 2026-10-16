"""Sensors for WPSD active mode, firmware, frequencies, and system stats."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfFrequency, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .client import WpsdClient
from .const import (
    DOMAIN,
    SENSOR_ACTIVE_MODE,
    SENSOR_CPU_LOAD,
    SENSOR_CPU_TEMP,
    SENSOR_DISK_USAGE,
    SENSOR_FIRMWARE,
    SENSOR_NET_TRAFFIC,
    SENSOR_RX_FREQ,
    SENSOR_TX_FREQ,
)

_LOGGER = logging.getLogger(__name__)

# Sensor definitions: (key, name, icon, device_class, unit, state_class)
SENSOR_TYPES: list[dict[str, Any]] = [
    {
        "key": SENSOR_ACTIVE_MODE,
        "name": "Active Mode",
        "icon": "mdi:radio",
        "device_class": SensorDeviceClass.ENUM,
        "unit": None,
        "state_class": None,
    },
    {
        "key": SENSOR_FIRMWARE,
        "name": "Firmware Version",
        "icon": "mdi:information",
        "device_class": None,
        "unit": None,
        "state_class": None,
    },
    {
        "key": SENSOR_TX_FREQ,
        "name": "TX Frequency",
        "icon": "mdi:radio-tower",
        "device_class": SensorDeviceClass.FREQUENCY,
        "unit": UnitOfFrequency.MEGAHERTZ,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_RX_FREQ,
        "name": "RX Frequency",
        "icon": "mdi:radio-tower",
        "device_class": SensorDeviceClass.FREQUENCY,
        "unit": UnitOfFrequency.MEGAHERTZ,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_CPU_LOAD,
        "name": "CPU Load",
        "icon": "mdi:cpu-monitor",
        "device_class": None,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_CPU_TEMP,
        "name": "CPU Temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": None,  # Parsed from HTML like "133°F / 56°C"
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_DISK_USAGE,
        "name": "Disk Usage",
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": None,  # Parsed from HTML like "4.37 GB / 219.56 GB"
        "state_class": None,
    },
    {
        "key": SENSOR_NET_TRAFFIC,
        "name": "Network Traffic",
        "icon": "mdi:network",
        "device_class": None,
        "unit": None,  # Parsed from HTML like "50.63MiB ↓ | 54.54MiB ↑"
        "state_class": None,
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WPSD sensors."""
    client: WpsdClient = hass.data[DOMAIN][entry.entry_id]

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from WPSD."""
        radio_status = await client.async_get_radio_status()
        firmware = await client.async_get_firmware()
        tx_freq = await client.async_get_tx_freq()
        rx_freq = await client.async_get_rx_freq()
        cpu_load = await client.async_get_cpu_load()
        cpu_temp = await client.async_get_cpu_temp()
        disk_usage = await client.async_get_disk_usage()
        net_traffic = await client.async_get_net_traffic()
        return {
            SENSOR_ACTIVE_MODE: radio_status,
            SENSOR_FIRMWARE: firmware,
            SENSOR_TX_FREQ: tx_freq,
            SENSOR_RX_FREQ: rx_freq,
            SENSOR_CPU_LOAD: cpu_load,
            SENSOR_CPU_TEMP: cpu_temp,
            SENSOR_DISK_USAGE: disk_usage,
            SENSOR_NET_TRAFFIC: net_traffic,
        }

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    await coordinator.async_config_entry_first_refresh()

    entities = [
        WpsdSensor(coordinator, sensor_def) for sensor_def in SENSOR_TYPES
    ]
    async_add_entities(entities)


class WpsdSensor(CoordinatorEntity, SensorEntity):
    """Generic sensor for WPSD data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_def: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_def = sensor_def
        self._attr_unique_id = f"{DOMAIN}_{sensor_def['key']}"
        self._attr_name = sensor_def["name"]
        self._attr_icon = sensor_def.get("icon")
        self._attr_device_class = sensor_def.get("device_class")
        self._attr_native_unit_of_measurement = sensor_def.get("unit")
        self._attr_state_class = sensor_def.get("state_class")

    @property
    def native_value(self) -> str | None:
        """Return the sensor value."""
        data: dict[str, Any] | None = self.coordinator.data
        if data is None:
            return None
        return data.get(self._sensor_def["key"])
