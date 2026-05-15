"""Switch platform for Pentair EasyTouch circuits and features."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PentairCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .model import Circuit, Feature

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pentair circuit and feature switches."""
    coordinator: PentairCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []
    if coordinator.data is not None:
        for circuit in coordinator.data.circuits:
            if not circuit.is_light:
                entities.append(PentairCircuitSwitch(coordinator, circuit.id))

        for feature in coordinator.data.features:
            entities.append(PentairFeatureSwitch(coordinator, feature.id))

    async_add_entities(entities)


class PentairCircuitSwitch(CoordinatorEntity[PentairCoordinator], SwitchEntity):
    """Switch entity for a Pentair circuit."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PentairCoordinator, circuit_id: int) -> None:
        """Initialize the circuit switch."""
        super().__init__(coordinator)
        self._circuit_id = circuit_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_circuit_{circuit_id}"

    def _find_circuit(self) -> Circuit | None:
        """Find this circuit in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for circuit in self.coordinator.data.circuits:
            if circuit.id == self._circuit_id:
                return circuit
        return None

    @property
    def name(self) -> str:
        """Return the name of the circuit."""
        circuit = self._find_circuit()
        if circuit and circuit.name:
            return circuit.name
        return f"Circuit {self._circuit_id}"

    @property
    def is_on(self) -> bool:
        """Return True if the circuit is on."""
        circuit = self._find_circuit()
        return circuit.is_on if circuit else False

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the circuit on."""
        await self.coordinator.command_manager.set_circuit_state(self._circuit_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the circuit off."""
        await self.coordinator.command_manager.set_circuit_state(self._circuit_id, False)


class PentairFeatureSwitch(CoordinatorEntity[PentairCoordinator], SwitchEntity):
    """Switch entity for a Pentair feature circuit."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PentairCoordinator, feature_id: int) -> None:
        """Initialize the feature switch."""
        super().__init__(coordinator)
        self._feature_id = feature_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_feature_{feature_id}"

    def _find_feature(self) -> Feature | None:
        """Find this feature in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for feature in self.coordinator.data.features:
            if feature.id == self._feature_id:
                return feature
        return None

    @property
    def name(self) -> str:
        """Return the name of the feature."""
        feature = self._find_feature()
        if feature and feature.name:
            return feature.name
        return f"Feature {self._feature_id}"

    @property
    def is_on(self) -> bool:
        """Return True if the feature is on."""
        feature = self._find_feature()
        return feature.is_on if feature else False

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the feature on."""
        await self.coordinator.command_manager.set_circuit_state(self._feature_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the feature off."""
        await self.coordinator.command_manager.set_circuit_state(self._feature_id, False)
