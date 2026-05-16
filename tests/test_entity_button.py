"""Tests for Pentair button entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pentair_easytouch.button import (
    PentairCancelDelayButton,
    async_setup_entry,
)
from custom_components.pentair_easytouch.const import DOMAIN
from custom_components.pentair_easytouch.coordinator import PentairCoordinator


def _make_coordinator() -> MagicMock:
    coordinator = MagicMock(spec=PentairCoordinator)
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.command_manager = MagicMock()
    coordinator.command_manager.cancel_delay = AsyncMock()
    coordinator.last_update_success = True
    return coordinator


def test_cancel_delay_button_properties() -> None:
    coordinator = _make_coordinator()
    entity = PentairCancelDelayButton(coordinator)

    assert entity.name == "Cancel Delay"
    assert entity.icon == "mdi:timer-off"
    assert entity.unique_id == "test_entry_id_cancel_delay"
    assert entity.device_info == {
        "identifiers": {(DOMAIN, "test_entry_id")},
        "name": "Pentair EasyTouch",
        "manufacturer": "Pentair",
        "model": "EasyTouch",
    }


@pytest.mark.asyncio
async def test_cancel_delay_button_press() -> None:
    coordinator = _make_coordinator()
    entity = PentairCancelDelayButton(coordinator)

    await entity.async_press()

    coordinator.command_manager.cancel_delay.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_entry_adds_button() -> None:
    coordinator = _make_coordinator()
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], PentairCancelDelayButton)
