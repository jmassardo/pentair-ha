"""DataUpdateCoordinator for Pentair EasyTouch.

Bridges the protocol layer with Home Assistant entities.  The coordinator
owns the transport, framer, message router, and command manager.

EasyTouch broadcasts status every ~1-2 seconds, so this coordinator uses
a *push* model (``async_set_updated_data``) rather than polling.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .config_flow import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_TYPE,
    CONF_SERIAL_PORT,
    CONNECTION_TCP,
)
from .const import ACTION_GET_CIRCUITS, DOMAIN
from .model import PoolState
from .protocol.commands import CommandManager
from .protocol.framing import PacketFramer
from .protocol.messages import MessageRouter
from .protocol.transport import BaseTransport, SerialTransport, TcpTransport

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .protocol.framing import PentairPacket

_LOGGER = logging.getLogger(__name__)

# Delay between config requests to avoid flooding the RS485 bus (seconds).
_CONFIG_REQUEST_DELAY = 0.05  # 50ms, matching nodejs-poolController

# Range of circuit IDs to request config for.
_CONFIG_CIRCUIT_MIN = 1
_CONFIG_CIRCUIT_MAX = 20


class PentairCoordinator(DataUpdateCoordinator[PoolState]):
    """Coordinator that manages the RS485 connection and pool state.

    The coordinator is the single owner of the protocol pipeline:
    transport → framer → router → state.  Entities read from
    ``self.data`` (a ``PoolState`` instance) and send commands via
    ``self.command_manager``.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN)

        self._entry = entry
        self._state = PoolState()

        # Build protocol pipeline
        self._transport: BaseTransport = self._create_transport(entry)
        self._framer = PacketFramer(on_packet=self._on_packet)
        self._router = MessageRouter(
            state=self._state,
            on_state_updated=self._on_state_updated,
        )
        self._command_manager = CommandManager(self._transport)

        # Wire transport data callback
        self._transport.set_on_data(self._on_data)

        # Expose initial data so entities have something before first broadcast
        self.data = self._state

        # Signals when the first status broadcast has been received and processed
        self._first_update_event = asyncio.Event()

        # Dual-gate flags: entity discovery waits for BOTH status and config
        self._status_received = False
        self._config_received = False

        # Reference to the config request background task
        self._config_request_task: asyncio.Task[None] | None = None

    @property
    def command_manager(self) -> CommandManager:
        """Return the command manager for entities to send commands."""
        return self._command_manager

    @property
    def pool_state(self) -> PoolState:
        """Return the current pool state."""
        return self._state

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the transport connection and begin listening."""
        _LOGGER.info("Starting Pentair EasyTouch coordinator")
        await self._transport.connect()
        # Request circuit configuration from the controller.
        # The controller only broadcasts Action 11 during power-up, so we
        # must actively request it if we start after the controller.
        self._config_request_task = asyncio.create_task(self._async_request_config())

    async def stop(self) -> None:
        """Disconnect transport and clean up."""
        _LOGGER.info("Stopping Pentair EasyTouch coordinator")
        await self._transport.disconnect()

    async def wait_for_first_update(self, timeout: float = 10.0) -> None:
        """Wait for the first status broadcast to populate equipment state.

        Parameters
        ----------
        timeout:
            Maximum seconds to wait for the first status broadcast.
            If the timeout expires entities will be added as equipment is
            discovered dynamically.
        """
        try:
            await asyncio.wait_for(self._first_update_event.wait(), timeout)
        except TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for first status broadcast after %.1fs. "
                "Entities will be added as equipment is discovered.",
                timeout,
            )
            # Fallback: if config never arrived (e.g. read-only RS485 adapter),
            # activate all circuits in the valid range so entities appear.
            # On EasyTouch: circuits 1-10, features 11-18/20.
            # Without config we can't distinguish which are truly configured,
            # so we activate them all — unused ones will just show as OFF.
            if not self._config_received and self._status_received:
                _LOGGER.info(
                    "No circuit config received; activating all circuits "
                    "%d-%d as fallback",
                    _CONFIG_CIRCUIT_MIN,
                    _CONFIG_CIRCUIT_MAX,
                )
                for circuit in self._state.circuits:
                    if _CONFIG_CIRCUIT_MIN <= circuit.id <= _CONFIG_CIRCUIT_MAX:
                        circuit.is_active = True
                        if not circuit.name:
                            circuit.name = f"Circuit {circuit.id}"
                self._first_update_event.set()
                self.async_set_updated_data(self._state)
    # ------------------------------------------------------------------
    # Protocol pipeline callbacks
    # ------------------------------------------------------------------

    def _on_data(self, data: bytes) -> None:
        """Called when transport receives raw data. Feed to framer."""
        self._framer.feed(data)

    def _on_packet(self, packet: PentairPacket) -> None:
        """Called when framer produces a complete packet. Route to handlers."""
        self._router.dispatch(packet)

    @callback
    def _on_state_updated(self) -> None:
        """Called when the router updates the pool state.

        Pushes the updated state to all listening entities.  The first-update
        event is held until **both** a status broadcast (Action 2) and circuit
        configuration (Action 11) have been received, so that entities are
        registered with their proper names.
        """
        self.async_set_updated_data(self._state)
        if not self._first_update_event.is_set():
            # Check for status: any circuit existing means Action 2 arrived
            if self._state.circuits and not self._status_received:
                self._status_received = True
                _LOGGER.debug("First status broadcast received")
            # Check for config: any circuit with a non-empty name means
            # Action 11 data has been processed
            if not self._config_received:
                for circuit in self._state.circuits:
                    if circuit.name:
                        self._config_received = True
                        _LOGGER.debug("Circuit config received")
                        break
            if self._status_received and self._config_received:
                self._first_update_event.set()

    async def _async_request_config(self) -> None:
        """Send GET_CIRCUITS requests for circuits 1-20.

        The controller responds with Action 11 (circuit name/function) for
        each requested circuit.  A 50ms delay is inserted between requests
        to avoid flooding the RS485 bus, matching the reference
        implementation (nodejs-poolController).
        """
        _LOGGER.debug(
            "Requesting circuit config for circuits %d-%d",
            _CONFIG_CIRCUIT_MIN,
            _CONFIG_CIRCUIT_MAX,
        )
        for circuit_id in range(_CONFIG_CIRCUIT_MIN, _CONFIG_CIRCUIT_MAX + 1):
            try:
                await self._command_manager.request_config(ACTION_GET_CIRCUITS, circuit_id)
            except Exception:
                _LOGGER.debug(
                    "Failed to request config for circuit %d",
                    circuit_id,
                    exc_info=True,
                )
            await asyncio.sleep(_CONFIG_REQUEST_DELAY)
        _LOGGER.debug("Circuit config requests complete")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_transport(entry: ConfigEntry) -> BaseTransport:
        """Create the appropriate transport based on config entry data."""
        connection_type = entry.data[CONF_CONNECTION_TYPE]
        if connection_type == CONNECTION_TCP:
            return TcpTransport(
                host=entry.data[CONF_HOST],
                port=entry.data[CONF_PORT],
            )
        return SerialTransport(
            port=entry.data[CONF_SERIAL_PORT],
            baudrate=entry.data[CONF_BAUD_RATE],
        )
