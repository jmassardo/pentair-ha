"""Pump status decode for the Pentair Intelliflo protocol.

Pumps communicate using the same RS485 framing but with source/dest
addresses in the 96-111 range.  The primary status response is
Action 7, which reports watts, RPM, flow, mode, drive state, and
error codes.

Ported from PumpStateMessage.ts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from custom_components.pentair_easytouch.const import PUMP_ADDR_START

if TYPE_CHECKING:
    from custom_components.pentair_easytouch.model import PoolState

_LOGGER = logging.getLogger(__name__)


def decode_pump_status(
    source: int,
    dest: int,
    action: int,
    payload: bytes,
    state: PoolState,
) -> None:
    """Decode a pump status message and update *state* in-place.

    We only process messages **from** a pump (source >= 96).  Messages
    **to** a pump are requests from the controller that we ignore.

    Parameters
    ----------
    source:
        Source address of the message.
    dest:
        Destination address of the message.
    action:
        Action code (we handle action 7 = status response).
    payload:
        Raw payload bytes.
    state:
        The ``PoolState`` to update.
    """
    # Only process responses from pumps (source >= 96)
    if source < PUMP_ADDR_START:
        return

    pump = state.get_pump_by_address(source)
    if pump is None:
        # Auto-discover pump by address
        pump_number = source - PUMP_ADDR_START + 1
        pump = state.get_pump(pump_number)
        pump.address = source
        pump.name = f"Pump {pump_number}"
        pump.is_active = True

    if action == 7:
        _decode_action7(payload, pump, state)
    elif action in (1, 9, 10):
        # Type detection only - set pump type if not already known
        _detect_pump_type(action, payload, pump)


def _decode_action7(payload: bytes, pump: object, state: PoolState) -> None:
    """Decode a pump Action 7 status response.

    Payload layout (15 bytes):
    [0]  command
    [1]  mode
    [2]  driveState
    [3]  watts high byte
    [4]  watts low byte
    [5]  RPM high byte
    [6]  RPM low byte
    [7]  flow (GPM)
    [8]  ppc
    [9]  (reserved)
    [10] (reserved)
    [11] status high byte
    [12] status low byte
    [13] time high byte (hours portion)
    [14] time low byte (minutes portion)
    """
    from custom_components.pentair_easytouch.model import Pump

    if not isinstance(pump, Pump):
        return

    if len(payload) < 7:
        _LOGGER.warning(
            "Pump action 7 payload too short (%d bytes) - skipping",
            len(payload),
        )
        return

    pump.command = payload[0]
    pump.mode = payload[1]
    pump.drive_state = payload[2]
    pump.watts = (payload[3] << 8) | payload[4]
    pump.rpm = (payload[5] << 8) | payload[6]

    if len(payload) > 7:
        pump.flow = payload[7]
    if len(payload) > 8:
        pump.ppc = payload[8]
    if len(payload) > 12:
        pump.status = (payload[11] << 8) | payload[12]
    if len(payload) > 14:
        pump.time = payload[13] * 60 + payload[14]

    pump.is_active = True


def _detect_pump_type(action: int, payload: bytes, pump: object) -> None:
    """Detect pump type from action code and speed data.

    Action 1 with speed > 0:
      - speed < 300 → VF (variable flow)
      - speed >= 300 → VS (variable speed)
    Action 9 or 10 → VSF (variable speed + flow)
    """
    from custom_components.pentair_easytouch.model import Pump
    from custom_components.pentair_easytouch.protocol.valuemaps import PumpType

    if not isinstance(pump, Pump):
        return

    if pump.type != 0:
        # Type already known
        return

    if action == 1 and len(payload) >= 4:
        speed = (payload[2] << 8) | payload[3]
        if speed > 0:
            pump.type = PumpType.VF if speed < 300 else PumpType.VS
    elif action in (9, 10):
        pump.type = PumpType.VSF
