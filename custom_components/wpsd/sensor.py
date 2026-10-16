"""Sensors for WPSD active mode, firmware, frequencies, and system stats."""

from __future__ import annotations

import logging
import re
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

from . import WpsdData

from .const import (
    ALL_MODES,
    DOMAIN,
    MODE_STATES,
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

# Sensor definitions: (key, icon, device_class, unit, state_class)
# Names come from translations (entity.sensor.<key>.name)
SENSOR_TYPES: list[dict[str, Any]] = [
    {
        "key": SENSOR_ACTIVE_MODE,
        "icon": "mdi:radio",
        "device_class": SensorDeviceClass.ENUM,
        "unit": None,
        "state_class": None,
    },
    {
        "key": SENSOR_FIRMWARE,
        "icon": "mdi:information",
        "device_class": None,
        "unit": None,
        "state_class": None,
    },
    {
        "key": SENSOR_DISK_USAGE_ROOT,
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_DISK_USED_ROOT,
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": UnitOfInformation.GIGABYTES,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    {
        "key": SENSOR_DISK_TOTAL_ROOT,
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": UnitOfInformation.GIGABYTES,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    {
        "key": SENSOR_DISK_USAGE_VARLOG,
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_DISK_USED_VARLOG,
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": UnitOfInformation.GIGABYTES,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    {
        "key": SENSOR_DISK_TOTAL_VARLOG,
        "icon": "mdi:harddisk",
        "device_class": None,
        "unit": UnitOfInformation.GIGABYTES,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    {
        "key": SENSOR_TX_FREQ,
        "icon": "mdi:radio-tower",
        "device_class": SensorDeviceClass.FREQUENCY,
        "unit": UnitOfFrequency.MEGAHERTZ,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_RX_FREQ,
        "icon": "mdi:radio-tower",
        "device_class": SensorDeviceClass.FREQUENCY,
        "unit": UnitOfFrequency.MEGAHERTZ,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_CPU_LOAD,
        "icon": "mdi:cpu-monitor",
        "device_class": None,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": SENSOR_CPU_TEMP,
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
    data: WpsdData = hass.data[DOMAIN][entry.entry_id]
    callsign = data.client.callsign

    entities: list[SensorEntity] = [
        WpsdSensor(data.system_coordinator, sensor_def, entry.entry_id, callsign)
        for sensor_def in SENSOR_TYPES
    ]
    entities.extend(
        WpsdModeStatusSensor(data.mode_coordinator, mode, entry.entry_id, callsign)
        for mode in ALL_MODES
    )
    async_add_entities(entities)


class WpsdSensor(CoordinatorEntity, SensorEntity):
    """Generic sensor for WPSD data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_def: dict[str, Any],
        entry_id: str,
        device_name: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._callsign = device_name
        self._sensor_def = sensor_def
        self._attr_unique_id = f"{entry_id}_{sensor_def['key']}"
        self._attr_translation_key = sensor_def["key"]
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
            identifiers={(DOMAIN, self._entry_id)},
            translation_key="hotspot" if self._callsign else "hotspot_unknown",
            translation_placeholders={"callsign": self._callsign or ""},
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


class WpsdModeStatusSensor(CoordinatorEntity, SensorEntity):
    """Status of a WPSD mode (active, inactive, error or paused).

    The mode's network status is exposed as an attribute.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = MODE_STATES

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        mode: str,
        entry_id: str,
        device_name: str | None = None,
    ) -> None:
        """Initialize the mode status sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._callsign = device_name
        self._mode = mode
        slug = re.sub(r"\W+", "_", mode.lower())
        self._attr_unique_id = f"{entry_id}_{slug}_status"
        self._attr_translation_key = slug

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            translation_key="hotspot" if self._callsign else "hotspot_unknown",
            translation_placeholders={"callsign": self._callsign or ""},
            manufacturer="WPSD",
            model="WPSD Hotspot",
        )

    @property
    def native_value(self) -> str | None:
        """Return the mode status, or None if WPSD reports an unrecognised one."""
        data: dict[str, Any] | None = self.coordinator.data
        if data is None:
            return None
        status = data.get("modes", {}).get(self._mode)
        return status if status in MODE_STATES else None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the mode's network status, if WPSD reports one."""
        data: dict[str, Any] | None = self.coordinator.data
        if data is None:
            return {}
        network_status = data.get("networks", {}).get(f"{self._mode} Net")
        return {"network_status": network_status} if network_status else {}
