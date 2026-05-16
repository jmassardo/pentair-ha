"""Tests for Pentair number entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pentair_easytouch.const import DOMAIN
from custom_components.pentair_easytouch.coordinator import PentairCoordinator
from custom_components.pentair_easytouch.model import Chlorinator, PoolState, Pump
from custom_components.pentair_easytouch.number import (
    PentairChlorSetpointNumber,
    PentairPumpSpeedNumber,
    async_setup_entry,
)


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
    coordinator.command_manager.set_pump_speed = AsyncMock()
    coordinator.last_update_success = True
    return coordinator


def _make_state() -> PoolState:
    state = PoolState()
    state.chlorinators = [
        Chlorinator(
            id=1,
            name="IC40",
            pool_setpoint=40,
            spa_setpoint=10,
        )
    ]
    return state


def test_chlor_setpoint_number_properties() -> None:
    coordinator = _make_coordinator(_make_state())

    pool = PentairChlorSetpointNumber(coordinator, chlor_id=1, body_type="pool")
    spa = PentairChlorSetpointNumber(coordinator, chlor_id=1, body_type="spa")

    assert pool.name == "IC40 Pool Setpoint"
    assert pool.native_value == 40.0
    assert pool.available is True
    assert spa.name == "IC40 Spa Setpoint"
    assert spa.native_value == 10.0
    assert pool.device_info == {
        "identifiers": {(DOMAIN, "test_entry_id")},
        "name": "Pentair EasyTouch",
        "manufacturer": "Pentair",
        "model": "EasyTouch",
    }


def test_chlor_setpoint_number_fallbacks() -> None:
    coord = _make_coordinator(_make_state())
    entity = PentairChlorSetpointNumber(coord, chlor_id=99, body_type="pool")

    assert entity.name == "Chlorinator Pool Setpoint"
    assert entity.native_value is None

    unavailable = PentairChlorSetpointNumber(_make_coordinator(None), chlor_id=1, body_type="pool")
    assert unavailable.native_value is None
    assert unavailable.available is False


@pytest.mark.asyncio
async def test_set_pool_setpoint_calls_command_manager() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairChlorSetpointNumber(coordinator, chlor_id=1, body_type="pool")

    await entity.async_set_native_value(50.0)

    coordinator.command_manager.set_chlorinator.assert_awaited_once_with(pool_pct=50, spa_pct=10)


@pytest.mark.asyncio
async def test_set_spa_setpoint_calls_command_manager() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairChlorSetpointNumber(coordinator, chlor_id=1, body_type="spa")

    await entity.async_set_native_value(20.0)

    coordinator.command_manager.set_chlorinator.assert_awaited_once_with(pool_pct=40, spa_pct=20)


@pytest.mark.asyncio
async def test_set_native_value_noops_when_chlorinator_missing() -> None:
    coordinator = _make_coordinator(PoolState())
    entity = PentairChlorSetpointNumber(coordinator, chlor_id=1, body_type="pool")

    await entity.async_set_native_value(50.0)

    coordinator.command_manager.set_chlorinator.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_adds_pool_and_spa_numbers() -> None:
    coordinator = _make_coordinator(_make_state())
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert [entity.name for entity in entities] == ["IC40 Pool Setpoint", "IC40 Spa Setpoint"]

    # Listener should be registered for dynamic discovery
    coordinator.async_add_listener.assert_called_once()
    coordinator.config_entry.async_on_unload.assert_called_once()


@pytest.mark.asyncio
async def test_number_dynamic_discovery_adds_new_chlorinators() -> None:
    state = PoolState()
    coordinator = _make_coordinator(state)
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    # No chlorinators initially
    async_add_entities.assert_not_called()

    # Simulate a chlorinator arriving
    state.chlorinators = [Chlorinator(id=1, name="IC40", pool_setpoint=40, spa_setpoint=10)]

    discover_cb = coordinator.async_add_listener.call_args.args[0]
    discover_cb()

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 2
    assert [e.name for e in entities] == ["IC40 Pool Setpoint", "IC40 Spa Setpoint"]

    # Call again - should not add duplicates
    async_add_entities.reset_mock()
    discover_cb()
    async_add_entities.assert_not_called()


# --- Pump Speed Number Tests ---


def _make_state_with_pump() -> PoolState:
    state = PoolState()
    state.pumps = [Pump(id=1, name="IntelliFlo VS", address=96, is_active=True, rpm=2400, watts=150)]
    return state


def test_pump_speed_number_properties() -> None:
    state = _make_state_with_pump()
    coordinator = _make_coordinator(state)

    entity = PentairPumpSpeedNumber(coordinator, pump_id=1)

    assert entity.name == "IntelliFlo VS Speed"
    assert entity.native_value == 2400.0
    assert entity.available is True
    assert entity.native_min_value == 0
    assert entity.native_max_value == 3450
    assert entity.native_step == 50
    assert entity.native_unit_of_measurement == "RPM"


def test_pump_speed_number_fallback_name() -> None:
    state = PoolState()
    state.pumps = [Pump(id=2, name="", address=97, is_active=True, rpm=1200)]
    coordinator = _make_coordinator(state)

    entity = PentairPumpSpeedNumber(coordinator, pump_id=2)
    assert entity.name == "Pump 2 Speed"


def test_pump_speed_number_unavailable_when_data_none() -> None:
    coordinator = _make_coordinator(None)
    entity = PentairPumpSpeedNumber(coordinator, pump_id=1)

    assert entity.native_value is None
    assert entity.available is False


@pytest.mark.asyncio
async def test_pump_speed_set_calls_command_manager() -> None:
    state = _make_state_with_pump()
    coordinator = _make_coordinator(state)
    entity = PentairPumpSpeedNumber(coordinator, pump_id=1)

    await entity.async_set_native_value(3000.0)

    coordinator.command_manager.set_pump_speed.assert_awaited_once_with(
        pump_address=96, speed_rpm=3000
    )


@pytest.mark.asyncio
async def test_pump_speed_set_uses_default_address_when_zero() -> None:
    state = PoolState()
    state.pumps = [Pump(id=2, name="Pump 2", address=0, is_active=True, rpm=1200)]
    coordinator = _make_coordinator(state)
    entity = PentairPumpSpeedNumber(coordinator, pump_id=2)

    await entity.async_set_native_value(1500.0)

    # Default address = 95 + pump_id = 97
    coordinator.command_manager.set_pump_speed.assert_awaited_once_with(
        pump_address=97, speed_rpm=1500
    )


@pytest.mark.asyncio
async def test_pump_speed_set_noops_when_pump_missing() -> None:
    coordinator = _make_coordinator(PoolState())
    entity = PentairPumpSpeedNumber(coordinator, pump_id=1)

    await entity.async_set_native_value(2000.0)

    coordinator.command_manager.set_pump_speed.assert_not_called()


@pytest.mark.asyncio
async def test_setup_discovers_pump_speed_entities() -> None:
    state = _make_state_with_pump()
    state.chlorinators = [Chlorinator(id=1, name="IC40", pool_setpoint=40, spa_setpoint=10)]
    coordinator = _make_coordinator(state)
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    names = [e.name for e in entities]
    assert "IC40 Pool Setpoint" in names
    assert "IC40 Spa Setpoint" in names
    assert "IntelliFlo VS Speed" in names
    assert len(entities) == 3


@pytest.mark.asyncio
async def test_inactive_pump_not_discovered() -> None:
    state = PoolState()
    state.pumps = [Pump(id=1, name="Pump", address=96, is_active=False, rpm=0)]
    coordinator = _make_coordinator(state)
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    # No entities should be added since pump is inactive
    async_add_entities.assert_not_called()
