"""Number platform for Pentair EasyTouch chlorinator setpoints."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PentairCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .model import Chlorinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pentair number entities."""
    coordinator: PentairCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_ids: set[str] = set()

    @callback
    def _async_discover_entities() -> None:
        """Discover and add new chlorinator setpoint number entities."""
        new_entities: list[NumberEntity] = []
        if coordinator.data is None:
            return

        for chlor in coordinator.data.chlorinators:
            uid_pool = f"chlor_{chlor.id}_pool"
            if uid_pool not in known_ids:
                known_ids.add(uid_pool)
                new_entities.append(PentairChlorSetpointNumber(coordinator, chlor.id, "pool"))
            uid_spa = f"chlor_{chlor.id}_spa"
            if uid_spa not in known_ids:
                known_ids.add(uid_spa)
                new_entities.append(PentairChlorSetpointNumber(coordinator, chlor.id, "spa"))

        if new_entities:
            async_add_entities(new_entities)

    # Add initial entities from current state
    _async_discover_entities()

    # Listen for coordinator updates to discover new entities
    entry.async_on_unload(coordinator.async_add_listener(_async_discover_entities))


class PentairChlorSetpointNumber(CoordinatorEntity[PentairCoordinator], NumberEntity):
    """Number entity for a chlorinator setpoint (pool or spa)."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:pool"

    def __init__(
        self,
        coordinator: PentairCoordinator,
        chlor_id: int,
        body_type: str,
    ) -> None:
        """Initialize the chlorinator setpoint number.

        Parameters
        ----------
        coordinator:
            The Pentair coordinator.
        chlor_id:
            Chlorinator equipment ID.
        body_type:
            ``"pool"`` or ``"spa"``.
        """
        super().__init__(coordinator)
        self._chlor_id = chlor_id
        self._body_type = body_type
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_chlorinator_{chlor_id}_{body_type}"
        )

    def _find_chlorinator(self) -> Chlorinator | None:
        """Find this chlorinator in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for chlor in self.coordinator.data.chlorinators:
            if chlor.id == self._chlor_id:
                return chlor
        return None

    @property
    def name(self) -> str:
        """Return the name."""
        chlor = self._find_chlorinator()
        chlor_name = chlor.name if chlor and chlor.name else "Chlorinator"
        label = "Pool" if self._body_type == "pool" else "Spa"
        return f"{chlor_name} {label} Setpoint"

    @property
    def native_value(self) -> float | None:
        """Return the current setpoint percentage."""
        chlor = self._find_chlorinator()
        if chlor is None:
            return None
        if self._body_type == "pool":
            return float(chlor.pool_setpoint)
        return float(chlor.spa_setpoint)

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

    async def async_set_native_value(self, value: float) -> None:
        """Set the chlorinator setpoint percentage."""
        chlor = self._find_chlorinator()
        if chlor is None:
            return

        pool_pct = chlor.pool_setpoint
        spa_pct = chlor.spa_setpoint

        if self._body_type == "pool":
            pool_pct = int(value)
        else:
            spa_pct = int(value)

        await self.coordinator.command_manager.set_chlorinator(
            pool_pct=pool_pct,
            spa_pct=spa_pct,
        )
