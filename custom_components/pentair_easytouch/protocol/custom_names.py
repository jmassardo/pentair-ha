"""Decoder for Action 10 — Custom Name Definitions (EasyTouch/IntelliTouch).

Each Action 10 message carries one user-defined circuit name.  The
controller stores up to 10 custom name slots (indices 0-9).  Circuits
reference these via ``name_id`` values 200-209 in Action 11 config.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_components.pentair_easytouch.model import PoolState

_LOGGER = logging.getLogger(__name__)

# Minimum payload: 1 byte index + at least 1 byte of name data
_MIN_PAYLOAD_LEN = 2

# Maximum characters in a custom name (Pentair uses 11-byte fixed fields)
_MAX_NAME_LEN = 11


def decode_custom_names(payload: bytes, state: PoolState) -> None:
    """Decode an Action 10 custom name definition message.

    Payload layout:
        byte 0:    name_index (0-9)
        bytes 1-11: ASCII characters, padded with 0x00 or spaces

    The decoded name is stored in ``state.custom_names[name_index]``.
    Any circuits already referencing this custom name (name_id = 200 +
    name_index) are updated to use the resolved name.
    """
    if len(payload) < _MIN_PAYLOAD_LEN:
        _LOGGER.debug(
            "Action 10 payload too short (%d bytes, need %d)",
            len(payload),
            _MIN_PAYLOAD_LEN,
        )
        return

    name_index = payload[0]
    name_bytes = payload[1 : 1 + _MAX_NAME_LEN]

    # Decode ASCII, strip padding (nulls and spaces)
    name = name_bytes.decode("ascii", errors="replace").rstrip("\x00 ")

    if not name:
        _LOGGER.debug("Action 10: custom name %d is empty, skipping", name_index)
        return

    state.custom_names[name_index] = name
    _LOGGER.debug("Custom name %d: %r", name_index, name)

    # Re-resolve any circuits that reference this custom name slot
    target_name_id = 200 + name_index
    for circuit in state.circuits:
        if circuit.name_id == target_name_id:
            circuit.name = name
            _LOGGER.debug(
                "Updated circuit %d name to custom name %r",
                circuit.id,
                name,
            )
