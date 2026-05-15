"""Additional protocol tests for remaining coverage gaps."""

import logging
from unittest.mock import patch

import pytest

from custom_components.pentair_easytouch.model import PoolBody, PoolState, Pump
from custom_components.pentair_easytouch.protocol.framing import PentairPacket
from custom_components.pentair_easytouch.protocol.messages import MessageRouter
from custom_components.pentair_easytouch.protocol.pump import _decode_action7, _detect_pump_type
from custom_components.pentair_easytouch.protocol.status import (
    _compute_heat_status_body2,
    _safe_byte,
    decode_heat_status,
    decode_status,
)
from custom_components.pentair_easytouch.protocol.valuemaps import HeatMode, HeatStatus, PumpType


def _make_status_payload(model_byte2: int = 1, model_byte1: int = 0) -> bytes:
    return bytes(
        [
            10,
            30,
            0x20,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            80,
            81,
            0,
            90,
            75,
            90,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            model_byte2,
            model_byte1,
        ]
    )


def test_notify_callback_exception_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    def bad_callback() -> None:
        raise RuntimeError("boom")

    router = MessageRouter(PoolState(), on_state_updated=bad_callback)

    with caplog.at_level(logging.ERROR):
        router._notify()

    assert "Error in on_state_updated callback" in caplog.text


def test_decode_action7_ignores_non_pump_object() -> None:
    state = PoolState()

    _decode_action7(bytes([1, 2, 3, 4, 5, 6, 7]), object(), state)

    assert state.pumps == []


def test_detect_pump_type_ignores_non_pump_object() -> None:
    _detect_pump_type(1, bytes([0, 0, 0x03, 0xE8]), object())


def test_detect_pump_type_preserves_known_type() -> None:
    pump = Pump(type=PumpType.VS)

    _detect_pump_type(1, bytes([0, 0, 0x00, 0x64]), pump)

    assert pump.type == PumpType.VS


def test_decode_heat_status_updates_body_temperatures_and_cool_setpoint() -> None:
    state = PoolState()
    state.get_body(1).is_on = True
    state.get_body(2).is_on = True
    payload = bytes([80, 104, 75, 84, 100, 0x05, 0, 0, 0, 60, 0, 0, 0])

    decode_heat_status(payload, state)

    body1 = state.get_body(1)
    body2 = state.get_body(2)
    assert body1.temp == 80
    assert body1.cool_set_point == 60
    assert body2.temp == 104
    assert state.temps.water_sensor2 == 104


def test_compute_heat_status_body2_handles_guard_and_dual_paths() -> None:
    assert _compute_heat_status_body2(0x20, object()) == HeatStatus.OFF

    dual = PoolBody(is_on=True, heat_mode=HeatMode.HEATER, temp=80, set_point=85)
    assert _compute_heat_status_body2(0x28, dual) == HeatStatus.DUAL


def test_compute_heat_status_body2_handles_cooling_and_solar_paths() -> None:
    cooling = PoolBody(is_on=True, heat_mode=HeatMode.SOLAR_ONLY, temp=96, set_point=90)
    solar = PoolBody(is_on=True, heat_mode=HeatMode.SOLAR_ONLY, temp=84, set_point=90)

    assert _compute_heat_status_body2(0x20, cooling) == HeatStatus.COOLING
    assert _compute_heat_status_body2(0x20, solar) == HeatStatus.SOLAR


def test_decode_status_applies_easytouch1_model_offset() -> None:
    state = PoolState()

    decode_status(_make_status_payload(model_byte2=14, model_byte1=2), state)

    assert state.equipment.model == 130
    assert state.equipment.shared is True


def test_dispatch_pump_decode_exception_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    router = MessageRouter(PoolState())
    packet = PentairPacket(version=1, dest=16, source=96, action=7, payload=b"\x00")

    with (
        patch(
            "custom_components.pentair_easytouch.protocol.messages.decode_pump_status",
            side_effect=ValueError("boom"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        router.dispatch(packet)

    assert "Error decoding pump message" in caplog.text


def test_safe_byte_returns_default_when_index_is_missing() -> None:
    assert _safe_byte(b"\x01", 5, 9) == 9
