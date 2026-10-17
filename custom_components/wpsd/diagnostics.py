"""Diagnostics support for WPSD."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import WpsdConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WpsdConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    return {
        "entry": dict(entry.data),
        "options": dict(entry.options),
        "callsign": data.client.callsign,
        "system": asdict(data.system_coordinator.data),
        "modes": asdict(data.mode_coordinator.data),
    }
