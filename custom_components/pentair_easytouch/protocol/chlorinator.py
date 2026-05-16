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
    """Decode an Action 25 IntelliChlor broadcast message (EasyTouch).

    Byte layout (from nodejs-poolController processTouch):
    [0] = (spaSetpoint << 1) | activeFlag  → spa_setpoint = byte >> 1
    [1] = poolSetpoint
    [2] = ? (flags/reserved, often 0x80)
    [3] = salt / 50
    [4] = status (bit 7 = generating flag, bits 0-6 = status code)
    [5] = super chlor hours (0 = not super-chlorinating)
    [6..21] = chlorinator name (ASCII, padded with spaces/nulls)
    """
    _LOGGER.debug(
        "CHLOR Action 25 raw payload (%d bytes): [%s]",
        len(payload),
        ", ".join(str(b) for b in payload),
    )

    if len(payload) < 2:
        _LOGGER.warning(
            "Chlorinator broadcast payload too short (%d bytes) - skipping",
            len(payload),
        )
        return

    chlor = state.get_chlorinator(1)
    chlor.is_active = (payload[0] & 0x01) == 1

    # Spa setpoint is encoded in bits 1-7 of byte 0
    chlor.spa_setpoint = payload[0] >> 1
    # Pool setpoint is byte 1
    chlor.pool_setpoint = payload[1]

    if len(payload) > 3:
        salt = payload[3] * 50
        if salt > 0:
            chlor.salt_level = salt
    if len(payload) > 4:
        chlor.status = payload[4] & 0x7F
    if len(payload) > 5:
        chlor.super_chlor_hours = payload[5]
        chlor.super_chlor = payload[5] > 0
    if len(payload) > 6:
        name = bytes(payload[6:22]).decode("ascii", errors="replace").rstrip("\x00 ")
        if name and not chlor.name:
            chlor.name = name

    _LOGGER.debug(
        "CHLOR Action 25 decoded: pool_sp=%d%% spa_sp=%d%% salt=%d super_hours=%d status=%d",
        chlor.pool_setpoint,
        chlor.spa_setpoint,
        chlor.salt_level,
        chlor.super_chlor_hours,
        chlor.status,
    )


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
    _LOGGER.debug(
        "CHLOR sub-protocol action=%d dest=%d raw payload (%d bytes): [%s]",
        action,
        dest,
        len(payload),
        ", ".join(str(b) for b in payload),
    )

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
        # This is the live command the OCP sends, representing the active
        # body's setpoint.  We use it to derive pool/spa setpoints based on
        # which body is currently running.
        if len(payload) > 0:
            chlor.target_output = payload[0]
            # Derive the active body's setpoint from the target output
            spa_on = any(
                c.id == 1 and c.is_on for c in state.circuits
            )
            if spa_on:
                chlor.spa_setpoint = payload[0]
            else:
                chlor.pool_setpoint = payload[0]

    elif action == 18:
        # Chlorinator → OCP: salt level + status response
        if len(payload) > 0:
            salt = payload[0] * 50
            if salt > 0:
                chlor.salt_level = salt
        if len(payload) > 1:
            chlor.status = payload[1] & 0x7F
        # Per reference: currentOutput = targetOutput when chlorinator responds.
        # The chlorinator doesn't report its own output; we derive from Action 17.
        chlor.current_output = chlor.target_output
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
