"""IntelliChlor chlorinator status decode.

The chlorinator communicates using a different sub-protocol framed with
``[16, 2, …, 16, 3]``.  However, in the context of this integration we
receive chlorinator data through the broadcast protocol — the OCP relays
chlorinator state in its own RS485 messages.

This module decodes chlorinator-related payloads observed on the main
RS485 bus (Action 25 IntelliChlor broadcast) as well as the raw
chlorinator sub-protocol actions (0-22) when they are intercepted.

Ported from ChlorinatorStateMessage.ts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_components.pentair_easytouch.model import PoolState

_LOGGER = logging.getLogger(__name__)


def decode_chlorinator_broadcast(payload: bytes, state: PoolState) -> None:
    """Decode an Action 25 IntelliChlor broadcast message.

    The OCP periodically broadcasts chlorinator configuration:
    - Pool setpoint
    - Spa setpoint
    - Super chlorinate flag
    - Status

    The exact byte layout varies, but the common approach is:
    [0] installed (0/1)
    [1] pool setpoint %
    [2] spa setpoint %
    [3] super chlor hours
    [4] status

    NOTE: Salt level is typically NOT in this broadcast — it comes from
    the chlorinator sub-protocol action 18 response.
    """
    if len(payload) < 2:
        _LOGGER.warning(
            "Chlorinator broadcast payload too short (%d bytes) - skipping",
            len(payload),
        )
        return

    chlor = state.get_chlorinator(1)
    chlor.is_active = True

    if len(payload) > 1:
        chlor.pool_setpoint = payload[1]
    if len(payload) > 2:
        chlor.spa_setpoint = payload[2]
    if len(payload) > 3:
        chlor.super_chlor_hours = payload[3]
        chlor.super_chlor = payload[3] > 0
    if len(payload) > 4:
        chlor.status = payload[4] & 0x7F


def decode_chlorinator_action(
    action: int,
    payload: bytes,
    dest: int,
    state: PoolState,
) -> None:
    """Decode a chlorinator sub-protocol action.

    This handles the individual chlorinator actions (0-22) that may be
    intercepted on the RS485 bus.

    Parameters
    ----------
    action:
        The chlorinator sub-protocol action code.
    payload:
        Raw payload bytes.
    dest:
        Destination address (80-83 means OCP → chlorinator).
    state:
        The ``PoolState`` to update.
    """
    chlor = state.get_chlorinator(1)

    if action == 3:
        # Model/name response from chlorinator
        # payload[0] = address, payload[1:17] = ASCII name
        if len(payload) > 1:
            name_bytes = payload[1:17]
            name = bytes(name_bytes).decode("ascii", errors="replace").rstrip()
            if name and not chlor.name:
                chlor.name = name
            chlor.is_active = True

    elif action == 17:
        # OCP → Chlorinator: set output percentage
        if len(payload) > 0:
            chlor.target_output = payload[0]

    elif action == 18:
        # Chlorinator → OCP: salt level + status response
        if len(payload) > 0:
            salt = payload[0] * 50
            if salt > 0:
                chlor.salt_level = salt
        if len(payload) > 1:
            chlor.status = payload[1] & 0x7F
        # When chlorinator responds, we know it's active and communicating
        chlor.is_active = True

    elif action == 20:
        # OCP → Chlorinator: get model request
        if len(payload) > 0:
            chlor.model = payload[0]

    elif action == 21:
        # OCP → Chlorinator: set output (fractional, /10)
        if len(payload) > 0:
            chlor.target_output = payload[0] / 10.0  # type: ignore[assignment]
            # NOTE: target_output is int in the model but fractional values
            # are rare (< 25.6%).  We store as int (truncated) for simplicity.
            chlor.target_output = int(payload[0] / 10)

    elif action == 22:
        # iChlor → OCP: current output + temp
        if len(payload) > 1:
            chlor.current_output = payload[1]
        chlor.is_active = True

    elif action in (0, 1, 19):
        # Control / ack / keep-alive - minimal processing
        chlor.is_active = True
