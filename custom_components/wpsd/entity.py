"""Base class for WPSD entities."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WpsdCoordinator


class WpsdEntity[CoordinatorT: WpsdCoordinator[Any]](CoordinatorEntity[CoordinatorT]):
    """Base entity attached to the hotspot's device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: CoordinatorT, sw_version: str | None = None
    ) -> None:
        """Initialize the entity and describe the hotspot's device."""
        super().__init__(coordinator)
        callsign = coordinator.client.callsign
        device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            translation_key="hotspot" if callsign else "hotspot_unknown",
            translation_placeholders={"callsign": callsign or ""},
            manufacturer="WPSD",
            model="WPSD Hotspot",
            configuration_url=coordinator.config_entry.data[CONF_URL],
        )
        if sw_version:
            device_info["sw_version"] = sw_version
        self._attr_device_info = device_info
