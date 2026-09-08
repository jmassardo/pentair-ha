"""Tests for Pentair switch entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pentair_easytouch.const import CONF_SUPER_CHLOR_HOURS, DOMAIN
from custom_components.pentair_easytouch.coordinator import PentairCoordinator
from custom_components.pentair_easytouch.model import Chlorinator, Circuit, Feature, PoolState
from custom_components.pentair_easytouch.switch import (
    PentairCircuitSwitch,
    PentairFeatureSwitch,
    PentairSuperChlorinateSwitch,
    async_setup_entry,
)


def _make_coordinator(state: PoolState | None = None) -> MagicMock:
    coordinator = MagicMock(spec=PentairCoordinator)
    coordinator.data = state
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.config_entry.options = {}
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
        Circuit(id=1, name="Filter Pump", is_on=True, is_light=False, is_active=True),
        Circuit(id=2, name="Pool Light", is_on=False, is_light=True, is_active=True),
    ]
    state.features = [Feature(id=11, name="Waterfall", is_on=True)]
    return state


def test_circuit_switch_properties() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairCircuitSwitch(coordinator, circuit_id=1)

    assert entity.name == "Filter Pump"
    assert entity.is_on is True
    assert entity.available is True
    assert entity.device_info == {
        "identifiers": {(DOMAIN, "test_entry_id")},
        "name": "Pentair EasyTouch",
        "manufacturer": "Pentair",
        "model": "EasyTouch",
    }


def test_circuit_switch_fallbacks() -> None:
    entity = PentairCircuitSwitch(_make_coordinator(_make_state()), circuit_id=99)

    assert entity.name == "Circuit 99"
    assert entity.is_on is False

    unavailable = PentairCircuitSwitch(_make_coordinator(None), circuit_id=1)
    assert unavailable.name == "Circuit 1"
    assert unavailable.is_on is False
    assert unavailable.available is False


@pytest.mark.asyncio
async def test_circuit_switch_turn_on_and_off() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairCircuitSwitch(coordinator, circuit_id=1)

    await entity.async_turn_on()
    await entity.async_turn_off()

    coordinator.command_manager.set_circuit_state.assert_any_call(1, True)
    coordinator.command_manager.set_circuit_state.assert_any_call(1, False)


def test_feature_switch_properties() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairFeatureSwitch(coordinator, feature_id=11)

    assert entity.name == "Waterfall"
    assert entity.is_on is True
    assert entity.available is True
    assert entity.device_info == {
        "identifiers": {(DOMAIN, "test_entry_id")},
        "name": "Pentair EasyTouch",
        "manufacturer": "Pentair",
        "model": "EasyTouch",
    }


def test_feature_switch_fallbacks() -> None:
    entity = PentairFeatureSwitch(_make_coordinator(_make_state()), feature_id=99)

    assert entity.name == "Feature 99"
    assert entity.is_on is False

    unavailable = PentairFeatureSwitch(_make_coordinator(None), feature_id=11)
    assert unavailable.name == "Feature 11"
    assert unavailable.is_on is False
    assert unavailable.available is False


@pytest.mark.asyncio
async def test_feature_switch_turn_on_and_off() -> None:
    coordinator = _make_coordinator(_make_state())
    entity = PentairFeatureSwitch(coordinator, feature_id=11)

    await entity.async_turn_on()
    await entity.async_turn_off()

    coordinator.command_manager.set_circuit_state.assert_any_call(11, True)
    coordinator.command_manager.set_circuit_state.assert_any_call(11, False)


def test_super_chlorinate_switch_properties() -> None:
    state = _make_state()
    state.chlorinators = [
        Chlorinator(
            id=1,
            name="IntelliChlor",
            pool_setpoint=40,
            spa_setpoint=10,
            super_chlor=True,
            super_chlor_hours=6,
            is_active=True,
        )
    ]
    coordinator = _make_coordinator(state)
    entity = PentairSuperChlorinateSwitch(coordinator, chlor_id=1)

    assert entity.name == "IntelliChlor Super Chlorinate"
    assert entity.is_on is True
    assert entity.available is True
    assert entity.device_info == {
        "identifiers": {(DOMAIN, "test_entry_id")},
        "name": "Pentair EasyTouch",
        "manufacturer": "Pentair",
        "model": "EasyTouch",
    }


@pytest.mark.asyncio
async def test_super_chlorinate_switch_turn_on_updates_state() -> None:
    state = _make_state()
    chlor = Chlorinator(
        id=1,
        pool_setpoint=40,
        spa_setpoint=10,
        is_active=True,
    )
    state.chlorinators = [chlor]
    coordinator = _make_coordinator(state)
    coordinator.config_entry.options = {CONF_SUPER_CHLOR_HOURS: 12}
    entity = PentairSuperChlorinateSwitch(coordinator, chlor_id=1)

    await entity.async_turn_on()

    coordinator.command_manager.set_chlorinator.assert_awaited_once_with(
        pool_pct=40,
        spa_pct=10,
        super_chlor_hours=12,
    )
    assert chlor.super_chlor is True
    assert chlor.super_chlor_hours == 12
    assert entity.is_on is True
    coordinator.async_set_updated_data.assert_called_once_with(state)


@pytest.mark.asyncio
async def test_super_chlorinate_switch_turn_off_updates_state() -> None:
    state = _make_state()
    chlor = Chlorinator(
        id=1,
        pool_setpoint=40,
        spa_setpoint=10,
        super_chlor=True,
        super_chlor_hours=6,
        is_active=True,
    )
    state.chlorinators = [chlor]
    coordinator = _make_coordinator(state)
    entity = PentairSuperChlorinateSwitch(coordinator, chlor_id=1)

    await entity.async_turn_off()

    coordinator.command_manager.set_chlorinator.assert_awaited_once_with(
        pool_pct=40,
        spa_pct=10,
        super_chlor_hours=0,
    )
    assert chlor.super_chlor is False
    assert chlor.super_chlor_hours == 0
    assert entity.is_on is False
    coordinator.async_set_updated_data.assert_called_once_with(state)


@pytest.mark.asyncio
async def test_super_chlorinate_switch_does_not_update_state_on_command_failure() -> None:
    state = _make_state()
    chlor = Chlorinator(
        id=1,
        pool_setpoint=40,
        spa_setpoint=10,
        is_active=True,
    )
    state.chlorinators = [chlor]
    coordinator = _make_coordinator(state)
    coordinator.command_manager.set_chlorinator.side_effect = ConnectionError
    entity = PentairSuperChlorinateSwitch(coordinator, chlor_id=1)

    with pytest.raises(ConnectionError):
        await entity.async_turn_on()

    assert chlor.super_chlor is False
    assert chlor.super_chlor_hours == 0
    coordinator.async_set_updated_data.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_filters_out_light_circuits() -> None:
    coordinator = _make_coordinator(_make_state())
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    # Initial discovery should add non-light circuits and features
    entities = async_add_entities.call_args.args[0]
    assert [type(entity) for entity in entities] == [
        PentairCircuitSwitch,
        PentairFeatureSwitch,
    ]
    assert [entity.name for entity in entities] == ["Filter Pump", "Waterfall"]

    # Listener should be registered for dynamic discovery
    coordinator.async_add_listener.assert_called_once()
    coordinator.config_entry.async_on_unload.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup_entry_skips_when_no_data() -> None:
    coordinator = _make_coordinator(None)
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    # No entities should be added when data is None
    async_add_entities.assert_not_called()

    # Listener should still be registered for later discovery
    coordinator.async_add_listener.assert_called_once()


@pytest.mark.asyncio
async def test_dynamic_discovery_adds_new_entities() -> None:
    state = PoolState()
    coordinator = _make_coordinator(state)
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    # No entities initially
    async_add_entities.assert_not_called()

    # Simulate equipment arriving via coordinator update
    state.circuits = [
        Circuit(id=3, name="Spa Jets", is_on=False, is_light=False, is_active=True),
    ]
    state.features = [Feature(id=12, name="Spillover", is_on=False)]
    state.chlorinators = [Chlorinator(id=1, name="IntelliChlor", is_active=True)]

    # Call the registered listener callback
    discover_cb = coordinator.async_add_listener.call_args.args[0]
    discover_cb()

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 3
    assert [entity.name for entity in entities] == [
        "Spa Jets",
        "Spillover",
        "IntelliChlor Super Chlorinate",
    ]

    # Call again - should not add duplicates
    async_add_entities.reset_mock()
    discover_cb()
    async_add_entities.assert_not_called()
