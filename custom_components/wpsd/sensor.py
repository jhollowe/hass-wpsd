"""Sensors for WPSD active mode, firmware, frequencies, and system stats."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import DiskUsage
from .const import ALL_MODES, MODE_STATES
from .coordinator import (
    WpsdConfigEntry,
    WpsdModeCoordinator,
    WpsdSystemCoordinator,
    WpsdSystemData,
)
from .entity import WpsdEntity

PARALLEL_UPDATES = 0

_NUMBER = re.compile(r"[\d.]+")


def _first_number(value: str | None) -> float | None:
    """Return the first number in a value like "440.525 MHz" or "38"."""
    if value is None or (match := _NUMBER.search(value)) is None:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _disk_stat(
    disk: DiskUsage | None, stat: Literal["percent", "used_gb", "total_gb"]
) -> float | None:
    """Return one statistic of a parsed disk, if the dashboard showed it."""
    return disk[stat] if disk else None


@dataclass(frozen=True, kw_only=True)
class WpsdSensorEntityDescription(SensorEntityDescription):
    """Describes a WPSD system sensor."""

    value_fn: Callable[[WpsdSystemData], str | float | None]


SENSORS: tuple[WpsdSensorEntityDescription, ...] = (
    WpsdSensorEntityDescription(
        key="active_mode",
        translation_key="active_mode",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda data: data.active_mode,
    ),
    WpsdSensorEntityDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.modem_firmware,
    ),
    WpsdSensorEntityDescription(
        key="disk_usage_root",
        translation_key="disk_usage_root",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _disk_stat(data.disk_root, "percent"),
    ),
    WpsdSensorEntityDescription(
        key="disk_used_root",
        translation_key="disk_used_root",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _disk_stat(data.disk_root, "used_gb"),
    ),
    WpsdSensorEntityDescription(
        key="disk_total_root",
        translation_key="disk_total_root",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _disk_stat(data.disk_root, "total_gb"),
    ),
    WpsdSensorEntityDescription(
        key="disk_usage_varlog",
        translation_key="disk_usage_varlog",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _disk_stat(data.disk_varlog, "percent"),
    ),
    WpsdSensorEntityDescription(
        key="disk_used_varlog",
        translation_key="disk_used_varlog",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _disk_stat(data.disk_varlog, "used_gb"),
    ),
    WpsdSensorEntityDescription(
        key="disk_total_varlog",
        translation_key="disk_total_varlog",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _disk_stat(data.disk_varlog, "total_gb"),
    ),
    WpsdSensorEntityDescription(
        key="tx_freq",
        translation_key="tx_freq",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda data: _first_number(data.tx_freq),
    ),
    WpsdSensorEntityDescription(
        key="rx_freq",
        translation_key="rx_freq",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda data: _first_number(data.rx_freq),
    ),
    WpsdSensorEntityDescription(
        key="cpu_load",
        translation_key="cpu_load",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.cpu_load,
    ),
    WpsdSensorEntityDescription(
        key="cpu_temp",
        translation_key="cpu_temp",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.cpu_temp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WpsdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WPSD sensors."""
    data = entry.runtime_data
    entities: list[SensorEntity] = [
        WpsdSensor(data.system_coordinator, description) for description in SENSORS
    ]
    entities.extend(WpsdModeSensor(data.mode_coordinator, mode) for mode in ALL_MODES)
    async_add_entities(entities)


class WpsdSensor(WpsdEntity[WpsdSystemCoordinator], SensorEntity):
    """Sensor for one value from the radio or dashboard pages."""

    entity_description: WpsdSensorEntityDescription

    def __init__(
        self,
        coordinator: WpsdSystemCoordinator,
        description: WpsdSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, coordinator.data.dashboard_version)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> str | float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class WpsdModeSensor(WpsdEntity[WpsdModeCoordinator], SensorEntity):
    """Status of a WPSD mode (active, inactive, error or paused).

    The mode's network status is exposed as an attribute.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = MODE_STATES

    def __init__(self, coordinator: WpsdModeCoordinator, mode: str) -> None:
        """Initialize the mode status sensor."""
        super().__init__(coordinator)
        self._mode = mode
        slug = re.sub(r"\W+", "_", mode.lower())
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{slug}_status"
        self._attr_translation_key = slug

    @property
    def native_value(self) -> str | None:
        """Return the mode status, or None if WPSD reports an unrecognised one."""
        status = self.coordinator.data.modes.get(self._mode)
        return status if status in MODE_STATES else None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the mode's network status, if WPSD reports one."""
        network_status = self.coordinator.data.networks.get(f"{self._mode} Net")
        return {"network_status": network_status} if network_status else {}
