"""Tests for Pentair light entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.light import ATTR_EFFECT

from custom_components.pentair_easytouch.const import DOMAIN
from custom_components.pentair_easytouch.coordinator import PentairCoordinator
from custom_components.pentair_easytouch.light import (
    _THEME_NAME_TO_VALUE,
    PentairLight,
    async_setup_entry,
)
from custom_components.pentair_easytouch.model import Circuit, PoolState
from custom_components.pentair_easytouch.protocol.valuemaps import LightTheme


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
    state.circuits = [
        Circuit(
            id=7,
            name="Pool Light",
            is_on=True,
            is_light=True,
            lighting_theme=LightTheme.PARTY,
        ),
        Circuit(id=1, name="Filter Pump", is_on=True, is_light=False),
    ]
    return state


def test_light_properties() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairLight(coordinator, circuit_id=7)

    assert entity.name == "Pool Light"
    assert entity.is_on is True
    assert entity.effect == "party"
    assert entity.effect_list == list(_THEME_NAME_TO_VALUE)
    assert entity.available is True
    assert entity.device_info == {
        "identifiers": {(DOMAIN, "test_entry_id")},
        "name": "Pentair EasyTouch",
        "manufacturer": "Pentair",
        "model": "EasyTouch",
    }


def test_light_fallbacks() -> None:
    entity = PentairLight(_make_coordinator(_make_state()), circuit_id=99)

    assert entity.name == "Light 99"
    assert entity.is_on is False
    assert entity.effect is None

    unavailable = PentairLight(_make_coordinator(None), circuit_id=7)
    assert unavailable.name == "Light 7"
    assert unavailable.is_on is False
    assert unavailable.effect is None
    assert unavailable.available is False


@pytest.mark.asyncio
async def test_light_turn_on_with_effect() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairLight(coordinator, circuit_id=7)

    await entity.async_turn_on(**{ATTR_EFFECT: "caribbean"})

    coordinator.command_manager.set_light_theme.assert_awaited_once_with(LightTheme.CARIBBEAN.value)
    coordinator.command_manager.set_circuit_state.assert_awaited_once_with(7, True)


@pytest.mark.asyncio
async def test_light_turn_on_without_effect() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairLight(coordinator, circuit_id=7)

    await entity.async_turn_on()

    coordinator.command_manager.set_light_theme.assert_not_called()
    coordinator.command_manager.set_circuit_state.assert_awaited_once_with(7, True)


@pytest.mark.asyncio
async def test_light_turn_off() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairLight(coordinator, circuit_id=7)

    await entity.async_turn_off()

    coordinator.command_manager.set_circuit_state.assert_awaited_once_with(7, False)


@pytest.mark.asyncio
async def test_async_setup_entry_adds_only_light_circuits() -> None:
    coordinator = _make_coordinator(_make_state())
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], PentairLight)
    assert entities[0].name == "Pool Light"

    # Listener should be registered for dynamic discovery
    coordinator.async_add_listener.assert_called_once()
    coordinator.config_entry.async_on_unload.assert_called_once()


@pytest.mark.asyncio
async def test_dynamic_discovery_adds_new_light_entities() -> None:
    state = PoolState()
    coordinator = _make_coordinator(state)
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    # No light circuits initially
    async_add_entities.assert_not_called()

    # Simulate a light circuit arriving
    state.circuits = [
        Circuit(id=7, name="Pool Light", is_on=True, is_light=True),
    ]

    discover_cb = coordinator.async_add_listener.call_args.args[0]
    discover_cb()

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], PentairLight)

    # Call again - should not add duplicates
    async_add_entities.reset_mock()
    discover_cb()
    async_add_entities.assert_not_called()
