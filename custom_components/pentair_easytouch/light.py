"""Light platform for Pentair EasyTouch IntelliBrite lights."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (
    ATTR_EFFECT,
    LightEntity,
)
from homeassistant.components.light.const import ColorMode, LightEntityFeature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PentairCoordinator
from .protocol.valuemaps import LIGHT_THEME_NAMES, LightTheme

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .model import Circuit

_LOGGER = logging.getLogger(__name__)

# Themes that are user-selectable effects (exclude control commands)
_SELECTABLE_THEMES: list[LightTheme] = [
    LightTheme.COLOR_SYNC,
    LightTheme.COLOR_SWIM,
    LightTheme.COLOR_SET,
    LightTheme.PARTY,
    LightTheme.ROMANCE,
    LightTheme.CARIBBEAN,
    LightTheme.AMERICAN,
    LightTheme.SUNSET,
    LightTheme.ROYAL,
    LightTheme.BLUE,
    LightTheme.GREEN,
    LightTheme.RED,
    LightTheme.WHITE,
    LightTheme.MAGENTA,
    LightTheme.THUMPER,
]

_THEME_NAME_TO_VALUE: dict[str, int] = {
    LIGHT_THEME_NAMES[theme]: theme.value for theme in _SELECTABLE_THEMES
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pentair light entities."""
    coordinator: PentairCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[LightEntity] = []
    if coordinator.data is not None:
        for circuit in coordinator.data.circuits:
            if circuit.is_light:
                entities.append(PentairLight(coordinator, circuit.id))

    async_add_entities(entities)


class PentairLight(CoordinatorEntity[PentairCoordinator], LightEntity):
    """Light entity for a Pentair IntelliBrite or compatible light circuit."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, coordinator: PentairCoordinator, circuit_id: int) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator)
        self._circuit_id = circuit_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_light_{circuit_id}"
        self._attr_supported_color_modes = {ColorMode.ONOFF}

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
        """Return the name of the light."""
        circuit = self._find_circuit()
        if circuit and circuit.name:
            return circuit.name
        return f"Light {self._circuit_id}"

    @property
    def is_on(self) -> bool:
        """Return True if the light is on."""
        circuit = self._find_circuit()
        return circuit.is_on if circuit else False

    @property
    def effect(self) -> str | None:
        """Return the current light effect/theme."""
        circuit = self._find_circuit()
        if circuit is None:
            return None
        return LIGHT_THEME_NAMES.get(circuit.lighting_theme)

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return [LIGHT_THEME_NAMES[theme] for theme in _SELECTABLE_THEMES]

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
        """Turn the light on, optionally setting an effect."""
        effect = kwargs.get(ATTR_EFFECT)
        if effect is not None:
            theme_value = _THEME_NAME_TO_VALUE.get(effect)
            if theme_value is not None:
                await self.coordinator.command_manager.set_light_theme(theme_value)

        await self.coordinator.command_manager.set_circuit_state(self._circuit_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.command_manager.set_circuit_state(self._circuit_id, False)
