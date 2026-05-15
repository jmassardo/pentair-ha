"""Decoder for Action 11 — Circuit Attributes (EasyTouch/IntelliTouch).

Each Action 11 message carries configuration for a single circuit:
circuit ID, function type, name index, and flags.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from custom_components.pentair_easytouch.protocol.valuemaps import (
    CIRCUIT_NAMES,
    CircuitFunction,
    is_light_function,
)

if TYPE_CHECKING:
    from custom_components.pentair_easytouch.model import PoolState

_LOGGER = logging.getLogger(__name__)

# Minimum payload length for a valid Action 11 message
_MIN_PAYLOAD_LEN = 5


def decode_circuit_config(payload: bytes, state: PoolState) -> None:
    """Decode an Action 11 circuit attributes message.

    Payload layout (5 bytes per circuit):
        byte 0: circuit_id (1-40)
        byte 1: function_id
            - lower 6 bits (& 0x3F): circuit function type
            - bit 6 (& 0x40): freeze protection enabled
        byte 2: name_id — index into the built-in circuit names table
        byte 3: unused/reserved
        byte 4: unused/reserved

    A circuit is considered ACTIVE (configured on the controller) when:
        - circuit function type != 19 (NOT_USED)
        - AND name_id != 0
    """
    if len(payload) < _MIN_PAYLOAD_LEN:
        _LOGGER.debug(
            "Action 11 payload too short (%d bytes, need %d)",
            len(payload),
            _MIN_PAYLOAD_LEN,
        )
        return

    circuit_id = payload[0]
    function_byte = payload[1]
    name_id = payload[2]

    # Extract function type (lower 6 bits) and freeze protect flag (bit 6)
    circuit_type = function_byte & 0x3F
    freeze_protect = (function_byte & 0x40) != 0

    # Determine if this circuit is active (configured on the controller)
    is_active = (circuit_type != CircuitFunction.NOT_USED) and (name_id != 0)

    # Resolve the circuit name from the built-in table
    # name_id >= 200 references custom names (Action 10); fall back to generic
    if name_id >= 200:
        circuit_name = f"Circuit {circuit_id}"
    else:
        circuit_name = CIRCUIT_NAMES.get(name_id, f"Circuit {circuit_id}")

    # Determine if this is a light-type circuit
    is_light = is_light_function(circuit_type)

    # Update the circuit in state
    circuit = state.get_circuit(circuit_id)
    circuit.name_id = name_id
    circuit.type = circuit_type
    circuit.freeze_protect = freeze_protect
    circuit.is_active = is_active
    circuit.name = circuit_name
    circuit.is_light = is_light

    _LOGGER.debug(
        "Circuit %d: name=%r, function=%d, is_light=%s, active=%s, freeze=%s",
        circuit_id,
        circuit_name,
        circuit_type,
        is_light,
        is_active,
        freeze_protect,
    )
