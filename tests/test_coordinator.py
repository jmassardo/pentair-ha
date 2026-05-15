"""Tests for PentairCoordinator lifecycle and first-update wait."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.pentair_easytouch.const import ACTION_GET_CIRCUITS
from custom_components.pentair_easytouch.coordinator import (
    _CONFIG_CIRCUIT_MAX,
    _CONFIG_CIRCUIT_MIN,
    PentairCoordinator,
)
from custom_components.pentair_easytouch.model import Circuit, PoolState


def _make_coordinator_mock() -> MagicMock:
    """Create a mock coordinator with real _first_update_event and methods."""
    coordinator = MagicMock(spec=PentairCoordinator)
    coordinator._first_update_event = asyncio.Event()
    coordinator._state = PoolState()
    coordinator._status_received = False
    coordinator._config_received = False

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

    # Simulate both flags set
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
async def test_on_state_updated_does_not_fire_event_on_status_only() -> None:
    """_on_state_updated should NOT fire the event with only status (no config)."""
    coordinator = _make_coordinator_mock()

    # Simulate Action 2 arriving: circuits exist but have no names
    coordinator._state.circuits = [Circuit(id=1), Circuit(id=6)]

    coordinator._on_state_updated()

    assert coordinator._status_received is True
    assert coordinator._config_received is False
    assert not coordinator._first_update_event.is_set()
    # async_set_updated_data should still be called
    coordinator.async_set_updated_data.assert_called_once_with(coordinator._state)


@pytest.mark.asyncio
async def test_on_state_updated_does_not_fire_event_on_config_only() -> None:
    """_on_state_updated should NOT fire the event with only config (no status circuits)."""
    coordinator = _make_coordinator_mock()

    # Empty circuits list (no Action 2 yet) but somehow config arrives
    # This shouldn't happen in practice but tests the gate logic
    assert not coordinator._state.circuits

    coordinator._on_state_updated()

    assert coordinator._status_received is False
    assert coordinator._config_received is False
    assert not coordinator._first_update_event.is_set()


@pytest.mark.asyncio
async def test_on_state_updated_fires_event_when_both_status_and_config() -> None:
    """_on_state_updated should fire the event when both status AND config arrive."""
    coordinator = _make_coordinator_mock()

    # Simulate Action 2: circuits with no names
    coordinator._state.circuits = [Circuit(id=1), Circuit(id=6)]
    coordinator._on_state_updated()

    assert coordinator._status_received is True
    assert coordinator._config_received is False
    assert not coordinator._first_update_event.is_set()

    # Simulate Action 11: circuit gets a name
    coordinator._state.circuits[0].name = "Pool Pump"
    coordinator._on_state_updated()

    assert coordinator._config_received is True
    assert coordinator._first_update_event.is_set()


@pytest.mark.asyncio
async def test_on_state_updated_fires_on_single_update_with_both() -> None:
    """If both status and config arrive in one update, event fires immediately."""
    coordinator = _make_coordinator_mock()

    # Simulate circuits with names already populated
    coordinator._state.circuits = [Circuit(id=1, name="Spa Light")]

    coordinator._on_state_updated()

    assert coordinator._status_received is True
    assert coordinator._config_received is True
    assert coordinator._first_update_event.is_set()


@pytest.mark.asyncio
async def test_on_state_updated_only_sets_event_once() -> None:
    """Calling _on_state_updated multiple times after event is set is harmless."""
    coordinator = _make_coordinator_mock()

    # Set up state so event fires
    coordinator._state.circuits = [Circuit(id=1, name="Pool Pump")]

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
        coordinator._state.circuits = [Circuit(id=6, name="Pool")]
        coordinator._on_state_updated()

    # Start the set task and wait concurrently
    task = asyncio.create_task(set_event_after_delay())
    await coordinator.wait_for_first_update(timeout=1.0)
    await task

    assert coordinator._first_update_event.is_set()


@pytest.mark.asyncio
async def test_timeout_fallback_when_config_never_arrives(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If config never arrives but status did, fallback activates ON circuits."""
    coordinator = _make_coordinator_mock()

    # Only status, never config — circuit is ON
    coordinator._state.circuits = [Circuit(id=1, is_on=True)]
    coordinator._on_state_updated()

    assert coordinator._status_received is True
    assert coordinator._config_received is False

    with caplog.at_level(logging.WARNING):
        await coordinator.wait_for_first_update(timeout=0.05)

    assert "Timed out waiting for first status broadcast" in caplog.text
    # Fallback promotes ON circuits and fires the event
    assert coordinator._first_update_event.is_set()
    assert coordinator._state.circuits[0].is_active is True


@pytest.mark.asyncio
async def test_async_request_config_sends_requests() -> None:
    """_async_request_config sends GET_CIRCUITS for circuits 1-20."""
    coordinator = MagicMock(spec=PentairCoordinator)
    coordinator._command_manager = AsyncMock()
    coordinator._command_manager.request_config = AsyncMock()

    # Bind the real method
    coordinator._async_request_config = PentairCoordinator._async_request_config.__get__(
        coordinator, PentairCoordinator
    )

    with patch(
        "custom_components.pentair_easytouch.coordinator.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await coordinator._async_request_config()

    expected_count = _CONFIG_CIRCUIT_MAX - _CONFIG_CIRCUIT_MIN + 1
    assert coordinator._command_manager.request_config.call_count == expected_count

    # Verify each circuit ID was requested
    called_ids = [
        call.args[1] for call in coordinator._command_manager.request_config.call_args_list
    ]
    assert called_ids == list(range(_CONFIG_CIRCUIT_MIN, _CONFIG_CIRCUIT_MAX + 1))
    for call in coordinator._command_manager.request_config.call_args_list:
        assert call.args[0] == ACTION_GET_CIRCUITS


@pytest.mark.asyncio
async def test_async_request_config_handles_transport_errors() -> None:
    """_async_request_config continues if a single request fails."""
    coordinator = MagicMock(spec=PentairCoordinator)
    coordinator._command_manager = AsyncMock()

    call_count = 0

    async def side_effect(action: int, item_id: int) -> None:
        nonlocal call_count
        call_count += 1
        if item_id == 5:
            raise OSError("Transport error")

    coordinator._command_manager.request_config = AsyncMock(side_effect=side_effect)
    coordinator._async_request_config = PentairCoordinator._async_request_config.__get__(
        coordinator, PentairCoordinator
    )

    with patch(
        "custom_components.pentair_easytouch.coordinator.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await coordinator._async_request_config()

    # All 20 requests should have been attempted despite the error on circuit 5
    expected_count = _CONFIG_CIRCUIT_MAX - _CONFIG_CIRCUIT_MIN + 1
    assert call_count == expected_count


@pytest.mark.asyncio
async def test_start_sends_config_requests() -> None:
    """start() should create a task for config requests after connecting."""
    coordinator = MagicMock(spec=PentairCoordinator)
    coordinator._transport = AsyncMock()
    coordinator._async_request_config = AsyncMock()

    # Bind the real start method
    coordinator.start = PentairCoordinator.start.__get__(coordinator, PentairCoordinator)

    with patch(
        "custom_components.pentair_easytouch.coordinator.asyncio.create_task",
    ) as mock_create_task:
        await coordinator.start()

    coordinator._transport.connect.assert_called_once()
    # Verify a task was created for config requests
    mock_create_task.assert_called_once()
    # The argument should be the coroutine from _async_request_config
    coro = mock_create_task.call_args[0][0]
    # Clean up the coroutine to avoid RuntimeWarning
    coro.close()
