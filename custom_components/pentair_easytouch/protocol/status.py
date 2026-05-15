"""Action 2 status decode for the Pentair EasyTouch protocol.

Action 2 is the main status broadcast sent by the EasyTouch OCP every
~1-2 seconds.  It contains circuit on/off states, temperatures, heat
mode/status, panel mode, and delay flags.

This module also handles:
- Action 5: Date/time broadcast
- Action 8: Heat/temperature status
- Action 96: IntelliBrite light theme

Byte map for the EasyTouch Action 2 payload (~29 bytes):
-------------------------------------------------------
Byte | Field
0    | Hours
1    | Minutes
2    | Circuits 1-8 (bit 0 = circuit 1, bit 5 = circuit 6/pool)
3    | Circuits 9-16
4    | Circuits 17-24
5    | Circuits 25-32
6    | Circuits 33-40
7    | (reserved)
8    | (reserved)
9    | Panel mode/flags (& 0x81 = mode, & 0x04 = units, & 0x08 = freeze)
10   | Valve / heat status bits
11   | Body heat status nibbles (low = body1, high = body2)
12   | Delay (& 0x3F)
13   | (reserved)
14   | Water sensor 1 temperature
15   | Water sensor 2 temperature
16   | (reserved)
17   | Solar sensor 1 temperature (EasyTouch)
18   | Air temperature
19   | Solar sensor 1 temperature (IntelliCenter) / Solar 2 (ET)
20   | Water sensor 3
21   | Water sensor 4
22   | Body 1 & 2 heat mode (body1 = & 0x33, body2 = (& 0xCC) >> 2)
23   | Body 3 & 4 heat mode / DST
24   | (reserved)
25-26| (reserved / unknown)
27   | OCP model byte 2
28   | OCP model byte 1

Ported from EquipmentStateMessage.ts ``process()`` method.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from custom_components.pentair_easytouch.protocol.valuemaps import (
    HeatStatus,
)

if TYPE_CHECKING:
    from custom_components.pentair_easytouch.model import PoolState

_LOGGER = logging.getLogger(__name__)

# Circuit id that corresponds to pool body (circuit 6 on EasyTouch)
_POOL_CIRCUIT = 6
# Circuit id that corresponds to spa body (circuit 1 on EasyTouch)
_SPA_CIRCUIT = 1


def decode_status(payload: bytes, state: PoolState) -> None:
    """Decode an Action 2 status broadcast and update *state* in-place.

    Parameters
    ----------
    payload:
        The raw payload bytes from the Action 2 message.
    state:
        The ``PoolState`` to update.
    """
    if len(payload) < 14:
        _LOGGER.warning(
            "Action 2 payload too short (%d bytes, need >=14) - skipping",
            len(payload),
        )
        return

    # ---- Time ----
    state.time.hours = payload[0]
    state.time.minutes = payload[1]

    # ---- Panel mode / flags ----
    mode_byte = _safe_byte(payload, 9)
    state.mode = mode_byte & 0x81
    state.temps.units = mode_byte & 0x04
    state.freeze = (mode_byte & 0x08) == 0x08

    # ---- Valve byte ----
    state.valve_byte = _safe_byte(payload, 10)

    # ---- Delay ----
    state.delay = _safe_byte(payload, 12) & 0x3F

    # ---- Temperatures ----
    state.temps.water_sensor1 = _safe_byte(payload, 14)
    state.temps.air = _safe_byte(payload, 18)

    # Water sensor 2 (meaningful on dual/i10d systems)
    state.temps.water_sensor2 = _safe_byte(payload, 15)

    # Solar sensor
    state.temps.solar = _safe_byte(payload, 19)
    # Secondary solar (mirrors primary on single-body systems)
    state.temps.solar_sensor2 = _safe_byte(payload, 17)

    # Additional water sensors (bodies 3-4, if present)
    state.temps.water_sensor3 = _safe_byte(payload, 20)
    state.temps.water_sensor4 = _safe_byte(payload, 21)

    # ---- OCP model identification ----
    model_byte1 = _safe_byte(payload, 28)
    model_byte2 = _safe_byte(payload, 27)
    _update_equipment_model(model_byte1, model_byte2, state)

    # ---- Circuit states (bitmask) ----
    _decode_circuit_states(payload, state)

    # ---- Body states ----
    _decode_body_states(payload, state)


def decode_datetime(payload: bytes, state: PoolState) -> None:
    """Decode an Action 5 date/time broadcast.

    Payload layout (8 bytes):
    [0] hours, [1] minutes, [2] day-of-week, [3] date,
    [4] month, [5] year, [6] (reserved), [7] adjustDST (1=yes)
    """
    if len(payload) < 6:
        _LOGGER.warning(
            "Action 5 payload too short (%d bytes) - skipping",
            len(payload),
        )
        return

    state.time.hours = payload[0]
    state.time.minutes = payload[1]
    state.time.day_of_week = payload[2]
    state.time.date = payload[3]
    state.time.month = payload[4]
    state.time.year = payload[5]
    if len(payload) > 7:
        state.time.adjust_dst = payload[7] == 0x01


def decode_heat_status(payload: bytes, state: PoolState) -> None:
    """Decode an Action 8 heat/temperature status message.

    Payload layout (>=13 bytes):
    [0] water sensor 1, [1] water sensor 2, [2] air sensor,
    [3] body 1 setpoint, [4] body 2 setpoint,
    [5] body 1 & 2 heat mode (low nibble = body1, bits 2-3 = body2),
    [6] water sensor 3, [7] water sensor 4, [8] reserved air sensor,
    [9] body 3 setpoint, [10] body 4 setpoint,
    [11] body 3 & 4 heat mode, [12] reserved
    """
    if len(payload) < 6:
        _LOGGER.warning(
            "Action 8 payload too short (%d bytes) - skipping",
            len(payload),
        )
        return

    state.temps.water_sensor1 = payload[0]
    state.temps.air = payload[2]

    # Body 1 (pool)
    body1 = state.get_body(1)
    body1.heat_mode = payload[5] & 0x33
    body1.set_point = payload[3]
    if body1.is_on:
        body1.temp = state.temps.water_sensor1

    # Body 1 cool setpoint (if available)
    if len(payload) > 9:
        body1.cool_set_point = payload[9]

    # Body 2 (spa)
    body2 = state.get_body(2)
    body2.heat_mode = (payload[5] & 0xCC) >> 2
    body2.set_point = payload[4]
    if body2.is_on:
        body2.temp = payload[1]
        state.temps.water_sensor2 = payload[1]


def decode_intellibrite(payload: bytes, state: PoolState) -> None:
    """Decode an Action 96 IntelliBrite light theme message.

    Payload: [0] theme byte, [1] (reserved)

    We store the theme on all active light circuits.
    """
    if len(payload) < 1:
        return

    theme = payload[0]
    # Themes 0 (off), 1 (on), and 190 (save) don't change stored theme
    if theme in (0, 1, 190):
        return

    for circuit in state.circuits:
        if circuit.is_light and circuit.is_on:
            circuit.lighting_theme = theme


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_byte(payload: bytes, index: int, default: int = 0) -> int:
    """Safely read a byte from the payload, returning *default* if out of range."""
    if index < len(payload):
        return payload[index]
    return default


def _update_equipment_model(model_byte1: int, model_byte2: int, state: PoolState) -> None:
    """Set the equipment model from the OCP identification bytes.

    From EasyTouchBoard.ts ``initExpansionModules``:
    - ``model_byte2 == 14`` indicates an EasyTouch 1 (add 128 offset).
    - Otherwise ``model_byte1`` is the raw model id.
    """
    from custom_components.pentair_easytouch.protocol.valuemaps import (
        EASYTOUCH_MODEL_NAMES,
    )

    model_id = model_byte1 + 128 if model_byte2 == 14 else model_byte1

    state.equipment.model = model_id
    state.equipment.model_name = EASYTOUCH_MODEL_NAMES.get(model_id, f"Unknown ({model_id})")

    # Derive shared/single from model
    shared_models = {0, 3, 6, 128, 130}
    state.equipment.shared = model_id in shared_models
    state.equipment.single = model_id not in shared_models


def _decode_circuit_states(payload: bytes, state: PoolState) -> None:
    """Extract circuit on/off states from the bitmask in the payload.

    Bytes 2-6 carry 5 bytes x 8 bits = 40 possible circuits.
    Circuit IDs start at 1.  The first byte (payload[2]) holds circuits
    1-8, where bit 0 = circuit 1.
    """
    circuit_id = 1
    for byte_idx in range(2, 7):
        byte_val = _safe_byte(payload, byte_idx)
        for bit in range(8):
            is_on = bool((byte_val >> bit) & 1)
            circuit = state.get_circuit(circuit_id)
            circuit.is_on = is_on
            circuit_id += 1


def _decode_body_states(payload: bytes, state: PoolState) -> None:
    """Decode body (pool/spa) temperature and heat status from Action 2.

    Body 1 = Pool (circuit 6), on when payload[2] & 0x20.
    Body 2 = Spa  (circuit 1), on when payload[2] & 0x01.
    """
    byte2 = _safe_byte(payload, 2)
    byte10 = _safe_byte(payload, 10)
    byte22 = _safe_byte(payload, 22)

    # ---- Body 1 (Pool) ----
    body1 = state.get_body(1)
    body1.circuit = _POOL_CIRCUIT
    pool_on = (byte2 & 0x20) == 0x20
    body1.is_on = pool_on
    if pool_on:
        body1.temp = state.temps.water_sensor1
    body1.heat_mode = byte22 & 0x33

    # Heat status for body 1
    body1.heat_status = _compute_heat_status_body1(byte10, body1)

    # ---- Body 2 (Spa) ----
    body2 = state.get_body(2)
    body2.circuit = _SPA_CIRCUIT
    spa_on = (byte2 & 0x01) == 0x01
    body2.is_on = spa_on
    if spa_on:
        # In shared systems the spa uses water sensor 1; in separate
        # systems it uses water sensor 2.
        body2.temp = state.temps.water_sensor1
    body2.heat_mode = (byte22 & 0xCC) >> 2

    # Heat status for body 2
    body2.heat_status = _compute_heat_status_body2(byte10, body2)


def _compute_heat_status_body1(byte10: int, body: object) -> int:
    """Derive pool body heat status from byte 10 bit flags.

    Standard (non-hybrid):
    - bit 2 (0x04) = heater active
    - bit 4 (0x10) = solar active
    """
    from custom_components.pentair_easytouch.model import PoolBody

    if not isinstance(body, PoolBody) or not body.is_on or body.heat_mode == 0:
        return HeatStatus.OFF

    heater_active = (byte10 & 0x04) == 0x04
    solar_active = (byte10 & 0x10) == 0x10

    if heater_active and solar_active:
        return HeatStatus.DUAL
    if heater_active:
        return HeatStatus.HEATER
    if solar_active:
        cooling = body.temp > body.set_point
        return HeatStatus.COOLING if cooling else HeatStatus.SOLAR

    return HeatStatus.OFF


def _compute_heat_status_body2(byte10: int, body: object) -> int:
    """Derive spa body heat status from byte 10 bit flags.

    Standard (non-hybrid):
    - bit 3 (0x08) = heater active
    - bit 5 (0x20) = solar active
    """
    from custom_components.pentair_easytouch.model import PoolBody

    if not isinstance(body, PoolBody) or not body.is_on or body.heat_mode == 0:
        return HeatStatus.OFF

    heater_active = (byte10 & 0x08) == 0x08
    solar_active = (byte10 & 0x20) == 0x20

    if heater_active and solar_active:
        return HeatStatus.DUAL
    if heater_active:
        return HeatStatus.HEATER
    if solar_active:
        cooling = body.temp > body.set_point
        return HeatStatus.COOLING if cooling else HeatStatus.SOLAR

    return HeatStatus.OFF
