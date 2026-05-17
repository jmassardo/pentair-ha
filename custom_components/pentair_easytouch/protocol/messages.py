"""Message router for the Pentair RS485 protocol.

Maps action codes to handler functions and dispatches decoded packets
into the shared ``PoolState``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from custom_components.pentair_easytouch.const import (
    ACTION_CIRCUIT_NAMES,
    ACTION_DATETIME,
    ACTION_HEAT_STATUS,
    ACTION_INTELLIBRITE,
    ACTION_INTELLICHLOR,
    ACTION_STATUS,
    CHLORINATOR_ADDR_END,
    CHLORINATOR_ADDR_START,
    CONTROLLER_ADDR,
    PUMP_ACTION_SET_SPEED,
    PUMP_ACTION_STATUS,
    PUMP_ACTION_VSF_1,
    PUMP_ACTION_VSF_2,
    PUMP_ADDR_END,
    PUMP_ADDR_START,
)
from custom_components.pentair_easytouch.model import PoolState
from custom_components.pentair_easytouch.protocol.chlorinator import (
    decode_chlorinator_action,
    decode_chlorinator_broadcast,
)
from custom_components.pentair_easytouch.protocol.circuit_config import (
    decode_circuit_config,
)
from custom_components.pentair_easytouch.protocol.pump import decode_pump_status
from custom_components.pentair_easytouch.protocol.status import (
    decode_datetime,
    decode_heat_status,
    decode_intellibrite,
    decode_status,
)

if TYPE_CHECKING:
    from custom_components.pentair_easytouch.protocol.framing import PentairPacket

_LOGGER = logging.getLogger(__name__)

# Type alias for a handler function
Handler = Callable[[bytes, PoolState], None]

# Action codes that we actively decode for EasyTouch
_HANDLED_ACTIONS: frozenset[int] = frozenset(
    {
        ACTION_STATUS,
        ACTION_DATETIME,
        ACTION_HEAT_STATUS,
        ACTION_CIRCUIT_NAMES,
        ACTION_INTELLIBRITE,
        ACTION_INTELLICHLOR,
    }
)


class MessageRouter:
    """Dispatch incoming packets to the correct decoder.

    Usage::

        router = MessageRouter(state)
        framer.set_on_packet(router.dispatch)
    """

    def __init__(
        self,
        state: PoolState,
        on_state_updated: Callable[[], None] | None = None,
    ) -> None:
        self._state = state
        self._on_state_updated = on_state_updated

        # Build the handler registry
        self._handlers: dict[int, Handler] = {
            ACTION_STATUS: decode_status,
            ACTION_DATETIME: decode_datetime,
            ACTION_HEAT_STATUS: decode_heat_status,
            ACTION_CIRCUIT_NAMES: decode_circuit_config,
            ACTION_INTELLIBRITE: decode_intellibrite,
            ACTION_INTELLICHLOR: decode_chlorinator_broadcast,
        }

    @property
    def state(self) -> PoolState:
        """Return the current pool state."""
        return self._state

    def register_handler(self, action: int, handler: Handler) -> None:
        """Register a custom handler for an action code.

        The handler signature is ``handler(payload, state)``.
        """
        self._handlers[action] = handler

    def dispatch(self, packet: PentairPacket) -> None:
        """Route a decoded packet to the appropriate handler.

        Called by the ``PacketFramer`` for each complete packet.
        Unknown action codes are logged at DEBUG level and ignored.
        """
        action = packet.action
        source = packet.source
        dest = packet.dest
        payload = packet.payload

        # Learn the controller's version byte from its broadcasts so we
        # can mirror it in outbound commands (the controller may reject
        # packets with a mismatched version byte).
        if source == CONTROLLER_ADDR and packet.version != 0:
            if self._state.controller_version_byte != packet.version:
                _LOGGER.info(
                    "Learned controller version byte: %d (was %d)",
                    packet.version,
                    self._state.controller_version_byte,
                )
                self._state.controller_version_byte = packet.version

        # ---- Chlorinator sub-protocol (version=0) ----
        if packet.version == 0 and self._is_chlorinator_packet(packet):
            try:
                decode_chlorinator_action(
                    action=action,
                    payload=payload,
                    dest=dest,
                    state=self._state,
                )
            except Exception:
                _LOGGER.exception(
                    "Error decoding chlorinator sub-protocol (action=%d, dst=%d)",
                    action,
                    dest,
                )
            self._notify()
            return

        # ---- Pump protocol (source or dest in 96-111) ----
        if PUMP_ADDR_START <= source <= PUMP_ADDR_END or (PUMP_ADDR_START <= dest <= PUMP_ADDR_END):
            pump_actions = {
                PUMP_ACTION_SET_SPEED,
                PUMP_ACTION_STATUS,
                PUMP_ACTION_VSF_1,
                PUMP_ACTION_VSF_2,
            }
            if action in pump_actions:
                try:
                    decode_pump_status(
                        source=source,
                        dest=dest,
                        action=action,
                        payload=payload,
                        state=self._state,
                    )
                except Exception:
                    _LOGGER.exception(
                        "Error decoding pump message (action=%d, src=%d)",
                        action,
                        source,
                    )
                self._notify()
                return

        # ---- Standard broadcast actions ----
        handler = self._handlers.get(action)
        if handler is not None:
            try:
                handler(payload, self._state)
            except Exception:
                _LOGGER.exception(
                    "Error in handler for action %d",
                    action,
                )
            self._notify()
            return

        # ---- Unknown action - log and skip ----
        _LOGGER.debug(
            "Unhandled action %d (src=%d, dst=%d, len=%d)",
            action,
            source,
            dest,
            len(payload),
        )

    def _notify(self) -> None:
        """Call the state-updated callback if registered."""
        if self._on_state_updated:
            try:
                self._on_state_updated()
            except Exception:
                _LOGGER.exception("Error in on_state_updated callback")

    def _is_chlorinator_packet(self, packet: PentairPacket) -> bool:
        """Determine if a version=0 packet is a chlorinator sub-protocol frame.

        Returns True if the packet destination or source matches chlorinator
        addressing conventions.
        """
        dest = packet.dest
        source = packet.source
        # Chlorinator responses have dest=0 or dest=16 with source=80
        # OCP commands have dest=80-83 with source=16
        if CHLORINATOR_ADDR_START <= dest <= CHLORINATOR_ADDR_END:
            return True
        return dest in (0, 16) and source == CHLORINATOR_ADDR_START
