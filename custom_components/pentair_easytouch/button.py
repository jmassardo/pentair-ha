"""Button platform for Pentair EasyTouch actions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PentairCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pentair button entities."""
    coordinator: PentairCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([PentairCancelDelayButton(coordinator)])


class PentairCancelDelayButton(CoordinatorEntity[PentairCoordinator], ButtonEntity):
    """Button to cancel any active equipment delay."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:timer-off"

    def __init__(self, coordinator: PentairCoordinator) -> None:
        """Initialize the cancel delay button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_cancel_delay"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Cancel Delay"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the Pentair controller."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name="Pentair EasyTouch",
            manufacturer="Pentair",
            model="EasyTouch",
        )

    async def async_press(self) -> None:
        """Handle button press — cancel the active delay."""
        await self.coordinator.command_manager.cancel_delay()
