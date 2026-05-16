"""Number platform for Pentair EasyTouch chlorinator setpoints and pump speed."""

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

    from .model import Chlorinator, Pump

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
        """Discover and add new chlorinator setpoint and pump speed number entities."""
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

        for pump in coordinator.data.pumps:
            uid_speed = f"pump_{pump.id}_speed"
            if uid_speed not in known_ids and pump.is_active:
                known_ids.add(uid_speed)
                new_entities.append(PentairPumpSpeedNumber(coordinator, pump.id))

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


class PentairPumpSpeedNumber(CoordinatorEntity[PentairCoordinator], NumberEntity):
    """Number entity for setting pump speed in RPM."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 3450
    _attr_native_step = 50
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "RPM"
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator: PentairCoordinator, pump_id: int) -> None:
        """Initialize the pump speed number entity."""
        super().__init__(coordinator)
        self._pump_id = pump_id
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_pump_{pump_id}_speed"
        )

    def _find_pump(self) -> Pump | None:
        """Find this pump in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for pump in self.coordinator.data.pumps:
            if pump.id == self._pump_id:
                return pump
        return None

    @property
    def name(self) -> str:
        """Return the name."""
        pump = self._find_pump()
        pump_name = pump.name if pump and pump.name else f"Pump {self._pump_id}"
        return f"{pump_name} Speed"

    @property
    def native_value(self) -> float | None:
        """Return the current pump speed in RPM."""
        pump = self._find_pump()
        if pump is None:
            return None
        return float(pump.rpm)

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
        """Set the pump speed in RPM."""
        pump = self._find_pump()
        if pump is None:
            return

        pump_address = pump.address
        if pump_address == 0:
            # Default address: 96 + (pump_id - 1)
            pump_address = 95 + self._pump_id

        await self.coordinator.command_manager.set_pump_speed(
            pump_address=pump_address,
            speed_rpm=int(value),
        )
