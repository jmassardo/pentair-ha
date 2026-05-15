"""Tests for Pentair number entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pentair_easytouch.const import DOMAIN
from custom_components.pentair_easytouch.coordinator import PentairCoordinator
from custom_components.pentair_easytouch.model import Chlorinator, PoolState
from custom_components.pentair_easytouch.number import PentairChlorSetpointNumber, async_setup_entry


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
