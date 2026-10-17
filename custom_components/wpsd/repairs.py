"""Repairs support for WPSD."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

ISSUE_UNREACHABLE = "hotspot_unreachable"


async def async_create_unreachable_issue(
    hass: HomeAssistant, entry_id: str, url: str
) -> None:
    """Create a repair issue when the hotspot is unreachable."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_UNREACHABLE,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="hotspot_unreachable",
        translation_placeholders={"url": url},
        learn_more_url="https://github.com/jhollowe/hass-wpsd",
        data={"entry_id": entry_id},
    )


async def async_delete_unreachable_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the unreachable hotspot repair issue."""
    ir.async_delete_issue(hass, DOMAIN, ISSUE_UNREACHABLE)
