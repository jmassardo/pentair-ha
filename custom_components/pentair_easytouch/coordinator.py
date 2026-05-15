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
from .const import DOMAIN
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

        Pushes the updated state to all listening entities.
        """
        self.async_set_updated_data(self._state)
        if not self._first_update_event.is_set():
            self._first_update_event.set()

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
