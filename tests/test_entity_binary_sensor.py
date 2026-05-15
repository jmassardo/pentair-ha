"""Tests for Pentair binary sensor entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pentair_easytouch.binary_sensor import (
    PentairDelaySensor,
    PentairFreezeProtectSensor,
    PentairHeaterActiveSensor,
    PentairPumpRunningSensor,
    PentairValveDivertedSensor,
    async_setup_entry,
)
from custom_components.pentair_easytouch.const import DOMAIN
from custom_components.pentair_easytouch.coordinator import PentairCoordinator
from custom_components.pentair_easytouch.model import PoolBody, PoolState, Pump, Valve
from custom_components.pentair_easytouch.protocol.valuemaps import HeatMode, HeatStatus


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
    state.freeze = True
    state.delay = 5
    state.bodies = [
        PoolBody(
            id=1,
            name="Pool",
            heat_mode=HeatMode.HEATER,
            heat_status=HeatStatus.HEATER,
            is_on=True,
        )
    ]
    state.pumps = [Pump(id=1, name="Filter Pump", is_active=True)]
    state.valves = [Valve(id=1, name="Waterfall Valve", is_diverted=True)]
    return state


def test_base_binary_sensor_properties() -> None:
    sensor = PentairFreezeProtectSensor(_make_coordinator(_make_state()))

    assert sensor.name == "Freeze Protection"
    assert sensor.is_on is True
    assert sensor.available is True
    assert sensor.device_info == {
        "identifiers": {(DOMAIN, "test_entry_id")},
        "name": "Pentair EasyTouch",
        "manufacturer": "Pentair",
        "model": "EasyTouch",
    }


def test_delay_sensor_properties() -> None:
    sensor = PentairDelaySensor(_make_coordinator(_make_state()))

    assert sensor.name == "Delay Active"
    assert sensor.is_on is True
    assert sensor.available is True


def test_equipment_binary_sensor_properties() -> None:
    coordinator = _make_coordinator(_make_state())

    heater = PentairHeaterActiveSensor(coordinator, body_id=1)
    pump = PentairPumpRunningSensor(coordinator, pump_id=1)
    valve = PentairValveDivertedSensor(coordinator, valve_id=1)

    assert heater.name == "Pool Heater Active"
    assert heater.is_on is True
    assert pump.name == "Filter Pump Running"
    assert pump.is_on is True
    assert valve.name == "Waterfall Valve Diverted"
    assert valve.is_on is True


def test_binary_sensor_fallbacks() -> None:
    coordinator = _make_coordinator(_make_state())

    heater = PentairHeaterActiveSensor(coordinator, body_id=99)
    pump = PentairPumpRunningSensor(coordinator, pump_id=99)
    valve = PentairValveDivertedSensor(coordinator, valve_id=99)

    assert heater.name == "Body 99 Heater Active"
    assert heater.is_on is False
    assert pump.name == "Pump 99 Running"
    assert pump.is_on is False
    assert valve.name == "Valve 99 Diverted"
    assert valve.is_on is False

    unavailable = PentairFreezeProtectSensor(_make_coordinator(None))
    assert unavailable.is_on is False
    assert unavailable.available is False


@pytest.mark.asyncio
async def test_async_setup_entry_adds_expected_entities() -> None:
    coordinator = _make_coordinator(_make_state())
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    # First call: static sensors (2)
    # Second call: dynamic equipment sensors (3)
    assert async_add_entities.call_count == 2

    static_entities = async_add_entities.call_args_list[0].args[0]
    assert len(static_entities) == 2

    dynamic_entities = async_add_entities.call_args_list[1].args[0]
    assert len(dynamic_entities) == 3

    all_names = {e.name for e in static_entities} | {e.name for e in dynamic_entities}
    assert "Freeze Protection" in all_names
    assert "Delay Active" in all_names
    assert "Pool Heater Active" in all_names
    assert "Filter Pump Running" in all_names
    assert "Waterfall Valve Diverted" in all_names

    # Listener should be registered for dynamic discovery
    coordinator.async_add_listener.assert_called_once()
    coordinator.config_entry.async_on_unload.assert_called_once()


@pytest.mark.asyncio
async def test_binary_sensor_dynamic_discovery_adds_new_equipment() -> None:
    state = PoolState()
    state.freeze = False
    state.delay = 0
    coordinator = _make_coordinator(state)
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    # Only static sensors initially (1 call)
    assert async_add_entities.call_count == 1

    # Simulate a pump arriving
    state.pumps = [Pump(id=2, name="Booster Pump", is_active=True)]

    discover_cb = coordinator.async_add_listener.call_args.args[0]
    discover_cb()

    # Second call with dynamic pump running sensor
    assert async_add_entities.call_count == 2
    dynamic_entities = async_add_entities.call_args.args[0]
    assert len(dynamic_entities) == 1
    assert dynamic_entities[0].name == "Booster Pump Running"

    # Call again - should not add duplicates
    async_add_entities.reset_mock()
    discover_cb()
    async_add_entities.assert_not_called()
