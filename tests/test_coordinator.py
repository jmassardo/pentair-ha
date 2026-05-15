"""Tests for PentairCoordinator lifecycle and first-update wait."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock

import pytest

from custom_components.pentair_easytouch.coordinator import PentairCoordinator


def _make_coordinator_mock() -> MagicMock:
    """Create a mock coordinator with real _first_update_event and methods."""
    coordinator = MagicMock(spec=PentairCoordinator)
    coordinator._first_update_event = asyncio.Event()
    coordinator._state = MagicMock()

    # Bind the real methods to the mock instance
    coordinator.wait_for_first_update = PentairCoordinator.wait_for_first_update.__get__(
        coordinator, PentairCoordinator
    )
    coordinator._on_state_updated = PentairCoordinator._on_state_updated.__get__(
        coordinator, PentairCoordinator
    )
    return coordinator


@pytest.mark.asyncio
async def test_wait_for_first_update_resolves_when_event_set() -> None:
    """wait_for_first_update returns immediately once the event is set."""
    coordinator = _make_coordinator_mock()

    # Simulate state update (sets the event)
    coordinator._first_update_event.set()

    # Should return immediately without timeout
    await coordinator.wait_for_first_update(timeout=0.1)


@pytest.mark.asyncio
async def test_wait_for_first_update_times_out_gracefully(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """wait_for_first_update logs a warning on timeout but does not raise."""
    coordinator = _make_coordinator_mock()

    with caplog.at_level(logging.WARNING):
        await coordinator.wait_for_first_update(timeout=0.05)

    assert "Timed out waiting for first status broadcast" in caplog.text


@pytest.mark.asyncio
async def test_on_state_updated_sets_first_update_event() -> None:
    """_on_state_updated should set the first update event."""
    coordinator = _make_coordinator_mock()

    assert not coordinator._first_update_event.is_set()

    # Simulate a state update
    coordinator._on_state_updated()

    assert coordinator._first_update_event.is_set()
    # async_set_updated_data should have been called
    coordinator.async_set_updated_data.assert_called_once_with(coordinator._state)


@pytest.mark.asyncio
async def test_on_state_updated_only_sets_event_once() -> None:
    """Calling _on_state_updated multiple times doesn't cause issues."""
    coordinator = _make_coordinator_mock()

    coordinator._on_state_updated()
    coordinator._on_state_updated()
    coordinator._on_state_updated()

    assert coordinator._first_update_event.is_set()
    # async_set_updated_data should be called each time
    assert coordinator.async_set_updated_data.call_count == 3


@pytest.mark.asyncio
async def test_wait_for_first_update_concurrent_set() -> None:
    """wait_for_first_update resolves when the event is set during the wait."""
    coordinator = _make_coordinator_mock()

    async def set_event_after_delay() -> None:
        await asyncio.sleep(0.02)
        coordinator._on_state_updated()

    # Start the set task and wait concurrently
    task = asyncio.create_task(set_event_after_delay())
    await coordinator.wait_for_first_update(timeout=1.0)
    await task

    assert coordinator._first_update_event.is_set()
