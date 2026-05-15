"""Climate platform for Pentair EasyTouch pool/spa bodies."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PentairCoordinator
from .protocol.valuemaps import (
    HEAT_MODE_NAMES,
    HEAT_STATUS_NAMES,
    HeatMode,
    HeatStatus,
    TempUnits,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .model import PoolBody

_LOGGER = logging.getLogger(__name__)

# Map HeatMode values to preset names
_PRESET_MODE_MAP: dict[int, str] = {
    HeatMode.OFF: "off",
    HeatMode.HEATER: "heater",
    HeatMode.SOLAR_PREFERRED: "solar_preferred",
    HeatMode.SOLAR_ONLY: "solar_only",
}

_PRESET_NAME_TO_VALUE: dict[str, int] = {v: k for k, v in _PRESET_MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pentair climate entities."""
    coordinator: PentairCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ClimateEntity] = []
    if coordinator.data is not None:
        for body in coordinator.data.bodies:
            entities.append(PentairBodyClimate(coordinator, body.id))

    async_add_entities(entities)


class PentairBodyClimate(CoordinatorEntity[PentairCoordinator], ClimateEntity):
    """Climate entity for a Pentair pool or spa body."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_target_temperature_step = 1.0
    _attr_min_temp = 40
    _attr_max_temp = 104
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: PentairCoordinator, body_id: int) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._body_id = body_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_climate_{body_id}"
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]

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
        if body and body.name:
            return body.name
        return "Pool" if self._body_id == 1 else "Spa"

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit."""
        if (
            self.coordinator.data is not None
            and self.coordinator.data.temps.units == TempUnits.CELSIUS
        ):
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def current_temperature(self) -> float | None:
        """Return the current body temperature."""
        body = self._find_body()
        if body is None or not body.is_on:
            return None
        return float(body.temp) if body.temp > 0 else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature (setpoint)."""
        body = self._find_body()
        if body is None:
            return None
        return float(body.set_point) if body.set_point > 0 else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        body = self._find_body()
        if body is None or body.heat_mode == HeatMode.OFF:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action (heating/idle/off)."""
        body = self._find_body()
        if body is None:
            return None
        if body.heat_status == HeatStatus.OFF:
            if body.heat_mode == HeatMode.OFF:
                return HVACAction.OFF
            return HVACAction.IDLE
        return HVACAction.HEATING

    @property
    def preset_mode(self) -> str | None:
        """Return the current heat mode as a preset."""
        body = self._find_body()
        if body is None:
            return None
        return HEAT_MODE_NAMES.get(body.heat_mode, "off")

    @property
    def preset_modes(self) -> list[str]:
        """Return the list of available preset modes."""
        return list(_PRESET_MODE_MAP.values())

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        body = self._find_body()
        if body is None:
            return None
        return {
            "heat_status": HEAT_STATUS_NAMES.get(body.heat_status, "unknown"),
        }

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

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        body = self._find_body()
        if body is None:
            return

        # Gather current values for the other body
        other_body = self._find_other_body()
        other_setpoint = other_body.set_point if other_body else 100
        other_mode = other_body.heat_mode if other_body else 0

        # Determine which body is pool (id=1) and which is spa (id=2)
        body_idx = 0 if self._body_id == 1 else 1

        await self.coordinator.command_manager.set_heat_setpoint(
            body_id=body_idx,
            temp=int(temperature),
            current_pool_setpoint=body.set_point if body_idx == 0 else other_setpoint,
            current_spa_setpoint=body.set_point if body_idx == 1 else other_setpoint,
            current_pool_mode=body.heat_mode if body_idx == 0 else other_mode,
            current_spa_mode=body.heat_mode if body_idx == 1 else other_mode,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode (off or heat)."""
        body = self._find_body()
        if body is None:
            return

        mode = HeatMode.OFF if hvac_mode == HVACMode.OFF else HeatMode.HEATER

        await self._set_heat_mode(mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the heat mode preset."""
        mode_value = _PRESET_NAME_TO_VALUE.get(preset_mode)
        if mode_value is None:
            _LOGGER.warning("Unknown preset mode: %s", preset_mode)
            return

        await self._set_heat_mode(mode_value)

    async def _set_heat_mode(self, mode: int) -> None:
        """Send the heat mode command."""
        body = self._find_body()
        if body is None:
            return

        other_body = self._find_other_body()
        other_setpoint = other_body.set_point if other_body else 100
        other_mode = other_body.heat_mode if other_body else 0

        body_idx = 0 if self._body_id == 1 else 1

        await self.coordinator.command_manager.set_heat_mode(
            body_id=body_idx,
            mode=mode,
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
