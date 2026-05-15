"""Tests for Pentair climate entities."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.const import UnitOfTemperature

from custom_components.pentair_easytouch.climate import PentairBodyClimate, async_setup_entry
from custom_components.pentair_easytouch.const import DOMAIN
from custom_components.pentair_easytouch.coordinator import PentairCoordinator
from custom_components.pentair_easytouch.model import PoolBody, PoolState
from custom_components.pentair_easytouch.protocol.valuemaps import HeatMode, HeatStatus, TempUnits


def _make_coordinator(state: PoolState | None = None) -> MagicMock:
    coordinator = MagicMock(spec=PentairCoordinator)
    coordinator.data = state
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.command_manager = MagicMock()
    coordinator.command_manager.set_circuit_state = AsyncMock()
    coordinator.command_manager.set_heat_mode = AsyncMock()
    coordinator.command_manager.set_heat_setpoint = AsyncMock()
    coordinator.command_manager.set_light_theme = AsyncMock()
    coordinator.command_manager.set_chlorinator = AsyncMock()
    coordinator.last_update_success = True
    return coordinator


def _make_state() -> PoolState:
    state = PoolState()
    state.temps.units = TempUnits.CELSIUS
    state.bodies = [
        PoolBody(
            id=1,
            name="Pool",
            temp=82,
            set_point=84,
            heat_mode=HeatMode.HEATER,
            heat_status=HeatStatus.HEATER,
            is_on=True,
        ),
        PoolBody(
            id=2,
            name="Spa",
            temp=100,
            set_point=102,
            heat_mode=HeatMode.SOLAR_ONLY,
            heat_status=HeatStatus.OFF,
            is_on=True,
        ),
    ]
    return state


def test_body_climate_properties() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairBodyClimate(coordinator, body_id=1)

    assert entity.name == "Pool"
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.current_temperature == 82.0
    assert entity.target_temperature == 84.0
    assert entity.hvac_mode == HVACMode.HEAT
    assert entity.hvac_action == HVACAction.HEATING
    assert entity.preset_mode == "heater"
    assert entity.preset_modes == ["off", "heater", "solar_preferred", "solar_only"]
    assert entity.extra_state_attributes == {"heat_status": "heater"}
    assert entity.available is True
    assert entity.device_info == {
        "identifiers": {(DOMAIN, "test_entry_id")},
        "name": "Pentair EasyTouch",
        "manufacturer": "Pentair",
        "model": "EasyTouch",
    }


def test_body_climate_hvac_action_states() -> None:
    state = _make_state()
    entity = PentairBodyClimate(_make_coordinator(state), body_id=1)
    body = state.get_body(1)

    body.heat_mode = HeatMode.OFF
    body.heat_status = HeatStatus.OFF
    assert entity.hvac_mode == HVACMode.OFF
    assert entity.hvac_action == HVACAction.OFF

    body.heat_mode = HeatMode.HEATER
    assert entity.hvac_mode == HVACMode.HEAT
    assert entity.hvac_action == HVACAction.IDLE

    body.heat_status = HeatStatus.HEATER
    assert entity.hvac_action == HVACAction.HEATING


def test_body_climate_fallbacks() -> None:
    missing = PentairBodyClimate(_make_coordinator(PoolState()), body_id=1)

    assert missing.name == "Pool"
    assert missing.current_temperature is None
    assert missing.target_temperature is None
    assert missing.hvac_mode == HVACMode.OFF
    assert missing.hvac_action is None
    assert missing.preset_mode is None
    assert missing.extra_state_attributes is None

    unavailable = PentairBodyClimate(_make_coordinator(None), body_id=1)
    assert unavailable.available is False


@pytest.mark.asyncio
async def test_set_temperature_calls_command_manager() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairBodyClimate(coordinator, body_id=1)

    await entity.async_set_temperature(temperature=86)

    coordinator.command_manager.set_heat_setpoint.assert_awaited_once_with(
        body_id=0,
        temp=86,
        current_pool_setpoint=84,
        current_spa_setpoint=102,
        current_pool_mode=HeatMode.HEATER,
        current_spa_mode=HeatMode.SOLAR_ONLY,
    )


@pytest.mark.asyncio
async def test_set_temperature_uses_default_other_body_values() -> None:
    state = PoolState()
    state.bodies = [
        PoolBody(
            id=1,
            name="Pool",
            set_point=84,
            heat_mode=HeatMode.HEATER,
            is_on=True,
        )
    ]
    coordinator = _make_coordinator(state)
    entity = PentairBodyClimate(coordinator, body_id=1)

    await entity.async_set_temperature(temperature=85)

    coordinator.command_manager.set_heat_setpoint.assert_awaited_once_with(
        body_id=0,
        temp=85,
        current_pool_setpoint=84,
        current_spa_setpoint=100,
        current_pool_mode=HeatMode.HEATER,
        current_spa_mode=0,
    )


@pytest.mark.asyncio
async def test_set_hvac_mode_calls_command_manager() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairBodyClimate(coordinator, body_id=1)

    await entity.async_set_hvac_mode(HVACMode.HEAT)

    coordinator.command_manager.set_heat_mode.assert_awaited_once_with(
        body_id=0,
        mode=HeatMode.HEATER,
        current_pool_setpoint=84,
        current_spa_setpoint=102,
        current_pool_mode=HeatMode.HEATER,
        current_spa_mode=HeatMode.SOLAR_ONLY,
    )


@pytest.mark.asyncio
async def test_set_preset_mode_calls_command_manager() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairBodyClimate(coordinator, body_id=1)

    await entity.async_set_preset_mode("solar_only")

    coordinator.command_manager.set_heat_mode.assert_awaited_once_with(
        body_id=0,
        mode=HeatMode.SOLAR_ONLY,
        current_pool_setpoint=84,
        current_spa_setpoint=102,
        current_pool_mode=HeatMode.HEATER,
        current_spa_mode=HeatMode.SOLAR_ONLY,
    )


@pytest.mark.asyncio
async def test_set_preset_mode_unknown_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairBodyClimate(coordinator, body_id=1)

    with caplog.at_level(logging.WARNING):
        await entity.async_set_preset_mode("unknown_option")

    assert "Unknown preset mode: unknown_option" in caplog.text
    coordinator.command_manager.set_heat_mode.assert_not_called()


@pytest.mark.asyncio
async def test_async_methods_noop_when_body_missing_or_temperature_missing() -> None:
    coordinator = _make_coordinator(PoolState())
    entity = PentairBodyClimate(coordinator, body_id=1)

    await entity.async_set_temperature()
    await entity.async_set_temperature(temperature=85)
    await entity.async_set_hvac_mode(HVACMode.OFF)
    await entity.async_set_preset_mode("heater")

    coordinator.command_manager.set_heat_setpoint.assert_not_called()
    coordinator.command_manager.set_heat_mode.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_adds_body_climates() -> None:
    coordinator = _make_coordinator(_make_state())
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert [entity.name for entity in entities] == ["Pool", "Spa"]

    # Listener should be registered for dynamic discovery
    coordinator.async_add_listener.assert_called_once()
    coordinator.config_entry.async_on_unload.assert_called_once()


@pytest.mark.asyncio
async def test_dynamic_discovery_adds_new_body_climates() -> None:
    state = PoolState()
    coordinator = _make_coordinator(state)
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    # No bodies initially
    async_add_entities.assert_not_called()

    # Simulate bodies arriving
    state.bodies = [PoolBody(id=1, name="Pool", is_on=True)]

    discover_cb = coordinator.async_add_listener.call_args.args[0]
    discover_cb()

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 1
    assert entities[0].name == "Pool"

    # Call again - should not add duplicates
    async_add_entities.reset_mock()
    discover_cb()
    async_add_entities.assert_not_called()
