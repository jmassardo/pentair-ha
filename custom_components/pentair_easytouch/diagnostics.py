"""Diagnostics support for Pentair EasyTouch integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import PentairCoordinator

TO_REDACT: set[str] = {"host", "serial_port"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: PentairCoordinator = hass.data[DOMAIN][entry.entry_id]

    data: dict[str, Any] = {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
    }

    if coordinator.data is not None:
        data["pool_state"] = asdict(coordinator.data)
    else:
        data["pool_state"] = None

    return data
