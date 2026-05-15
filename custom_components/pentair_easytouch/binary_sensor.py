"""Binary sensor platform for Pentair EasyTouch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PentairCoordinator
from .protocol.valuemaps import HeatStatus

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .model import PoolBody, Pump, Valve

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pentair binary sensor entities."""
    coordinator: PentairCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Static binary sensors are always created (unconditionally available)
    static_entities: list[BinarySensorEntity] = [
        PentairFreezeProtectSensor(coordinator),
        PentairDelaySensor(coordinator),
    ]
    async_add_entities(static_entities)

    # Dynamic binary sensors discovered from equipment lists
    known_ids: set[str] = set()

    @callback
    def _async_discover_entities() -> None:
        """Discover and add new equipment binary sensor entities."""
        new_entities: list[BinarySensorEntity] = []
        if coordinator.data is None:
            return

        for body in coordinator.data.bodies:
            uid = f"heater_{body.id}"
            if uid not in known_ids:
                known_ids.add(uid)
                new_entities.append(PentairHeaterActiveSensor(coordinator, body.id))

        for pump in coordinator.data.pumps:
            uid = f"pump_{pump.id}_running"
            if uid not in known_ids:
                known_ids.add(uid)
                new_entities.append(PentairPumpRunningSensor(coordinator, pump.id))

        for valve in coordinator.data.valves:
            uid = f"valve_{valve.id}_diverted"
            if uid not in known_ids:
                known_ids.add(uid)
                new_entities.append(PentairValveDivertedSensor(coordinator, valve.id))

        if new_entities:
            async_add_entities(new_entities)

    # Add initial dynamic entities from current state
    _async_discover_entities()

    # Listen for coordinator updates to discover new entities
    entry.async_on_unload(coordinator.async_add_listener(_async_discover_entities))


class PentairBinarySensorBase(CoordinatorEntity[PentairCoordinator], BinarySensorEntity):
    """Base class for Pentair binary sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PentairCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)

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


class PentairHeaterActiveSensor(PentairBinarySensorBase):
    """Binary sensor for whether a body's heater is active."""

    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(self, coordinator: PentairCoordinator, body_id: int) -> None:
        """Initialize the heater active sensor."""
        super().__init__(coordinator)
        self._body_id = body_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_heater_active_{body_id}"

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
        body_name = body.name if body and body.name else f"Body {self._body_id}"
        return f"{body_name} Heater Active"

    @property
    def is_on(self) -> bool:
        """Return True if the heater is active."""
        body = self._find_body()
        if body is None:
            return False
        return body.heat_status != HeatStatus.OFF


class PentairFreezeProtectSensor(PentairBinarySensorBase):
    """Binary sensor for freeze protection active."""

    _attr_device_class = BinarySensorDeviceClass.COLD
    _attr_icon = "mdi:snowflake-alert"

    def __init__(self, coordinator: PentairCoordinator) -> None:
        """Initialize the freeze protect sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_freeze_protect"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Freeze Protection"

    @property
    def is_on(self) -> bool:
        """Return True if freeze protection is active."""
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.freeze


class PentairDelaySensor(PentairBinarySensorBase):
    """Binary sensor for delay active."""

    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: PentairCoordinator) -> None:
        """Initialize the delay sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_delay_active"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Delay Active"

    @property
    def is_on(self) -> bool:
        """Return True if a delay is active."""
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.delay > 0


class PentairPumpRunningSensor(PentairBinarySensorBase):
    """Binary sensor for pump running state."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: PentairCoordinator, pump_id: int) -> None:
        """Initialize the pump running sensor."""
        super().__init__(coordinator)
        self._pump_id = pump_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_pump_{pump_id}_running"

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
        return f"{pump_name} Running"

    @property
    def is_on(self) -> bool:
        """Return True if the pump is running."""
        pump = self._find_pump()
        return pump.is_active if pump else False


class PentairValveDivertedSensor(PentairBinarySensorBase):
    """Binary sensor for valve diverted state."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_icon = "mdi:pipe-valve"

    def __init__(self, coordinator: PentairCoordinator, valve_id: int) -> None:
        """Initialize the valve diverted sensor."""
        super().__init__(coordinator)
        self._valve_id = valve_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_valve_{valve_id}_diverted"

    def _find_valve(self) -> Valve | None:
        """Find this valve in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for valve in self.coordinator.data.valves:
            if valve.id == self._valve_id:
                return valve
        return None

    @property
    def name(self) -> str:
        """Return the name."""
        valve = self._find_valve()
        valve_name = valve.name if valve and valve.name else f"Valve {self._valve_id}"
        return f"{valve_name} Diverted"

    @property
    def is_on(self) -> bool:
        """Return True if the valve is diverted."""
        valve = self._find_valve()
        return valve.is_diverted if valve else False
