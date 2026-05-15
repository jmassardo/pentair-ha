"""Select platform for Pentair EasyTouch heat mode selectors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PentairCoordinator
from .protocol.valuemaps import HEAT_MODE_NAMES, HeatMode

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .model import PoolBody

_LOGGER = logging.getLogger(__name__)

# Map option names to HeatMode values
_OPTION_TO_MODE: dict[str, int] = {
    "off": HeatMode.OFF,
    "heater": HeatMode.HEATER,
    "solar_preferred": HeatMode.SOLAR_PREFERRED,
    "solar_only": HeatMode.SOLAR_ONLY,
}

_OPTIONS: list[str] = list(_OPTION_TO_MODE.keys())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pentair select entities."""
    coordinator: PentairCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SelectEntity] = []
    if coordinator.data is not None:
        for body in coordinator.data.bodies:
            entities.append(PentairHeatModeSelect(coordinator, body.id))

    async_add_entities(entities)


class PentairHeatModeSelect(CoordinatorEntity[PentairCoordinator], SelectEntity):
    """Select entity for a body's heat mode."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: PentairCoordinator, body_id: int) -> None:
        """Initialize the heat mode select."""
        super().__init__(coordinator)
        self._body_id = body_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_heat_mode_{body_id}"
        self._attr_options = list(_OPTIONS)

    def _find_body(self) -> PoolBody | None:
        """Find this body in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for body in self.coordinator.data.bodies:
            if body.id == self._body_id:
                return body
        return None

    @property
    def name(self) -> str:
        """Return the name."""
        body = self._find_body()
        body_name = body.name if body and body.name else ("Pool" if self._body_id == 1 else "Spa")
        return f"{body_name} Heat Mode"

    @property
    def current_option(self) -> str | None:
        """Return the current heat mode option."""
        body = self._find_body()
        if body is None:
            return None
        return HEAT_MODE_NAMES.get(body.heat_mode, "off")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the Pentair controller."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name="Pentair EasyTouch",
            manufacturer="Pentair",
            model="EasyTouch",
        )

    async def async_select_option(self, option: str) -> None:
        """Set the heat mode."""
        mode_value = _OPTION_TO_MODE.get(option)
        if mode_value is None:
            _LOGGER.warning("Unknown heat mode option: %s", option)
            return

        body = self._find_body()
        if body is None:
            return

        other_body = self._find_other_body()
        other_setpoint = other_body.set_point if other_body else 100
        other_mode = other_body.heat_mode if other_body else 0

        body_idx = 0 if self._body_id == 1 else 1

        await self.coordinator.command_manager.set_heat_mode(
            body_id=body_idx,
            mode=mode_value,
            current_pool_setpoint=body.set_point if body_idx == 0 else other_setpoint,
            current_spa_setpoint=body.set_point if body_idx == 1 else other_setpoint,
            current_pool_mode=body.heat_mode if body_idx == 0 else other_mode,
            current_spa_mode=body.heat_mode if body_idx == 1 else other_mode,
        )

    def _find_other_body(self) -> PoolBody | None:
        """Find the other body (pool↔spa) in the coordinator data."""
        if self.coordinator.data is None:
            return None
        other_id = 2 if self._body_id == 1 else 1
        for body in self.coordinator.data.bodies:
            if body.id == other_id:
                return body
        return None
