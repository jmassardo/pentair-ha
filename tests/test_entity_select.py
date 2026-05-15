"""Tests for Pentair select entities."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pentair_easytouch.const import DOMAIN
from custom_components.pentair_easytouch.coordinator import PentairCoordinator
from custom_components.pentair_easytouch.model import PoolBody, PoolState
from custom_components.pentair_easytouch.protocol.valuemaps import HeatMode
from custom_components.pentair_easytouch.select import PentairHeatModeSelect, async_setup_entry


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
    state.bodies = [
        PoolBody(id=1, name="Pool", set_point=84, heat_mode=HeatMode.HEATER),
        PoolBody(id=2, name="Spa", set_point=102, heat_mode=HeatMode.SOLAR_ONLY),
    ]
    return state


def test_heat_mode_select_properties() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairHeatModeSelect(coordinator, body_id=1)

    assert entity.name == "Pool Heat Mode"
    assert entity.current_option == "heater"
    assert entity.options == ["off", "heater", "solar_preferred", "solar_only"]
    assert entity.available is True
    assert entity.device_info == {
        "identifiers": {(DOMAIN, "test_entry_id")},
        "name": "Pentair EasyTouch",
        "manufacturer": "Pentair",
        "model": "EasyTouch",
    }


def test_heat_mode_select_fallbacks() -> None:
    entity = PentairHeatModeSelect(_make_coordinator(PoolState()), body_id=1)

    assert entity.name == "Pool Heat Mode"
    assert entity.current_option is None

    unavailable = PentairHeatModeSelect(_make_coordinator(None), body_id=1)
    assert unavailable.available is False


@pytest.mark.asyncio
async def test_select_option_calls_command_manager() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairHeatModeSelect(coordinator, body_id=1)

    await entity.async_select_option("solar_preferred")

    coordinator.command_manager.set_heat_mode.assert_awaited_once_with(
        body_id=0,
        mode=HeatMode.SOLAR_PREFERRED,
        current_pool_setpoint=84,
        current_spa_setpoint=102,
        current_pool_mode=HeatMode.HEATER,
        current_spa_mode=HeatMode.SOLAR_ONLY,
    )


@pytest.mark.asyncio
async def test_select_option_unknown_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairHeatModeSelect(coordinator, body_id=1)

    with caplog.at_level(logging.WARNING):
        await entity.async_select_option("unknown")

    assert "Unknown heat mode option: unknown" in caplog.text
    coordinator.command_manager.set_heat_mode.assert_not_called()


@pytest.mark.asyncio
async def test_select_option_noops_when_body_missing() -> None:
    coordinator = _make_coordinator(PoolState())
    entity = PentairHeatModeSelect(coordinator, body_id=1)

    await entity.async_select_option("heater")

    coordinator.command_manager.set_heat_mode.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_adds_heat_mode_selects() -> None:
    coordinator = _make_coordinator(_make_state())
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert [entity.name for entity in entities] == ["Pool Heat Mode", "Spa Heat Mode"]
