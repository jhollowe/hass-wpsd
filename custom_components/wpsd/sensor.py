"""Sensors for WPSD active mode, firmware, frequencies, and system stats."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .client import WpsdClient
from .const import (
    CONF_SYSTEM_SCAN_INTERVAL,
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
        "name": "Modem Firmware Version",
        "icon": "mdi:information",
        "device_class": None,
        "unit": None,
        "state_class": None,
    },
    {
        "key": SENSOR_DISK_USAGE_ROOT,
        "name": "/ Disk Usage",
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_DISK_USED_ROOT,
        "name": "/ Disk Used",
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": UnitOfInformation.GIGABYTES,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    {
        "key": SENSOR_DISK_TOTAL_ROOT,
        "name": "/ Disk Total",
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": UnitOfInformation.GIGABYTES,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    {
        "key": SENSOR_DISK_USAGE_VARLOG,
        "name": "/var/log Disk Usage",
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_DISK_USED_VARLOG,
        "name": "/var/log Disk Used",
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": UnitOfInformation.GIGABYTES,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    {
        "key": SENSOR_DISK_TOTAL_VARLOG,
        "name": "/var/log Disk Total",
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": UnitOfInformation.GIGABYTES,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
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
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
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
        # Fetch each unique endpoint once, concurrently, to avoid repeated
        # sequential HTTP requests that make setup take over 10 seconds.
        radio_data, homepage_data = await asyncio.gather(
            client.async_get_radio_data(),
            client.async_get_homepage_data(),
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

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(
            seconds=entry.options.get(
                CONF_SYSTEM_SCAN_INTERVAL, DEFAULT_SYSTEM_SCAN_INTERVAL
            )
        ),
    )

    await coordinator.async_config_entry_first_refresh()

    entities = [WpsdSensor(coordinator, sensor_def, client.callsign) for sensor_def in SENSOR_TYPES]
    async_add_entities(entities)


class WpsdSensor(CoordinatorEntity, SensorEntity):
    """Generic sensor for WPSD data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_def: dict[str, Any],
        device_name: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_name = device_name or "WPSD"
        self._sensor_def = sensor_def
        self._attr_unique_id = f"{DOMAIN}_{sensor_def['key']}"
        self._attr_name = sensor_def["name"]
        self._attr_icon = sensor_def.get("icon")
        self._attr_device_class = sensor_def.get("device_class")
        self._attr_native_unit_of_measurement = sensor_def.get("unit")
        self._attr_state_class = sensor_def.get("state_class")
        self._attr_entity_registry_enabled_default = sensor_def.get(
            "entity_registry_enabled_default", True
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this sensor."""
        data: dict[str, Any] | None = self.coordinator.data
        version = data.get("dashboard_version") if data else None
        return DeviceInfo(
            identifiers={(DOMAIN, "wpsd_device")},
            name=self._device_name,
            manufacturer="WPSD",
            model="WPSD Hotspot",
            sw_version=version,
        )

    @property
    def native_value(self) -> str | None:
        """Return the sensor value."""
        data: dict[str, Any] | None = self.coordinator.data
        if data is None:
            return None
        value = data.get(self._sensor_def["key"])
        if value is None:
            return None

        key = self._sensor_def["key"]

        # Parse numeric values for measurement sensors
        if key == SENSOR_TX_FREQ or key == SENSOR_RX_FREQ:
            # Value like "440.525 MHz" -> return float
            import re

            match = re.search(r"([\d.]+)", value)
            if match:
                return float(match.group(1))
            return None

        if key == SENSOR_CPU_TEMP:
            # Value like "135°F / 57°C" -> extract Celsius value
            import re

            match = re.search(r"([\d.]+)°C", value)
            if match:
                return float(match.group(1))
            return None

        if key == SENSOR_CPU_LOAD:
            # Value like "38%" -> return float
            import re

            match = re.search(r"([\d.]+)", value)
            if match:
                return float(match.group(1))
            return None

        return value
