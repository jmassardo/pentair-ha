"""Tests for Action 2 status decode (status.py) plus Action 5, 8, 96."""

from custom_components.pentair_easytouch.model import PoolState
from custom_components.pentair_easytouch.protocol.status import (
    decode_datetime,
    decode_heat_status,
    decode_intellibrite,
    decode_status,
)
from custom_components.pentair_easytouch.protocol.valuemaps import HeatStatus


def _make_status_payload(
    hour: int = 15,
    minute: int = 34,
    circuits_1_8: int = 0x20,  # Pool on (bit 5)
    circuits_9_16: int = 0,
    circuits_17_24: int = 0,
    circuits_25_32: int = 0,
    circuits_33_40: int = 0,
    reserved7: int = 0,
    reserved8: int = 0,
    mode_flags: int = 0,
    valve_heat: int = 0,
    heat_status: int = 0,
    delay: int = 0,
    reserved13: int = 0,
    water_sensor1: int = 81,
    water_sensor2: int = 81,
    reserved16: int = 0,
    solar_sensor: int = 91,
    air_temp: int = 82,
    solar_sensor2: int = 91,
    water_sensor3: int = 0,
    water_sensor4: int = 0,
    heat_modes: int = 0x07,
    heat_modes_34: int = 0,
    reserved24: int = 0,
    unknown25: int = 0,
    unknown26: int = 0,
    model_byte2: int = 1,
    model_byte1: int = 0,
) -> bytes:
    """Build a 29-byte Action 2 payload with given values."""
    return bytes(
        [
            hour,
            minute,
            circuits_1_8,
            circuits_9_16,
            circuits_17_24,
            circuits_25_32,
            circuits_33_40,
            reserved7,
            reserved8,
            mode_flags,
            valve_heat,
            heat_status,
            delay,
            reserved13,
            water_sensor1,
            water_sensor2,
            reserved16,
            solar_sensor,
            air_temp,
            solar_sensor2,
            water_sensor3,
            water_sensor4,
            heat_modes,
            heat_modes_34,
            reserved24,
            unknown25,
            unknown26,
            model_byte2,
            model_byte1,
        ]
    )


class TestDecodeStatus:
    """Test the main Action 2 status decode."""

    def test_time(self) -> None:
        state = PoolState()
        payload = _make_status_payload(hour=15, minute=34)
        decode_status(payload, state)
        assert state.time.hours == 15
        assert state.time.minutes == 34

    def test_temperatures(self) -> None:
        state = PoolState()
        payload = _make_status_payload(water_sensor1=81, air_temp=82, solar_sensor=91)
        decode_status(payload, state)
        assert state.temps.water_sensor1 == 81
        assert state.temps.air == 82
        assert state.temps.solar == 91

    def test_mode_auto(self) -> None:
        state = PoolState()
        payload = _make_status_payload(mode_flags=0x00)
        decode_status(payload, state)
        assert state.mode == 0  # auto

    def test_mode_service(self) -> None:
        state = PoolState()
        payload = _make_status_payload(mode_flags=0x01)
        decode_status(payload, state)
        assert state.mode == 1  # service

    def test_mode_timeout(self) -> None:
        state = PoolState()
        payload = _make_status_payload(mode_flags=0x80)
        decode_status(payload, state)
        assert state.mode == 128  # timeout

    def test_units_fahrenheit(self) -> None:
        state = PoolState()
        payload = _make_status_payload(mode_flags=0x00)
        decode_status(payload, state)
        assert state.temps.units == 0

    def test_units_celsius(self) -> None:
        state = PoolState()
        payload = _make_status_payload(mode_flags=0x04)
        decode_status(payload, state)
        assert state.temps.units == 4

    def test_freeze_active(self) -> None:
        state = PoolState()
        payload = _make_status_payload(mode_flags=0x08)
        decode_status(payload, state)
        assert state.freeze is True

    def test_freeze_inactive(self) -> None:
        state = PoolState()
        payload = _make_status_payload(mode_flags=0x00)
        decode_status(payload, state)
        assert state.freeze is False

    def test_delay(self) -> None:
        state = PoolState()
        payload = _make_status_payload(delay=0x05)
        decode_status(payload, state)
        assert state.delay == 5

    def test_delay_masking(self) -> None:
        state = PoolState()
        # Upper bits should be masked off (& 0x3F)
        payload = _make_status_payload(delay=0xC5)  # 0xC5 & 0x3F = 5
        decode_status(payload, state)
        assert state.delay == 5

    def test_pool_on(self) -> None:
        state = PoolState()
        payload = _make_status_payload(circuits_1_8=0x20)  # bit 5 = pool
        decode_status(payload, state)
        body1 = state.get_body(1)
        assert body1.is_on is True
        assert body1.circuit == 6

    def test_pool_off(self) -> None:
        state = PoolState()
        payload = _make_status_payload(circuits_1_8=0x00)
        decode_status(payload, state)
        body1 = state.get_body(1)
        assert body1.is_on is False

    def test_spa_on(self) -> None:
        state = PoolState()
        payload = _make_status_payload(circuits_1_8=0x01)  # bit 0 = spa
        decode_status(payload, state)
        body2 = state.get_body(2)
        assert body2.is_on is True
        assert body2.circuit == 1

    def test_spa_off(self) -> None:
        state = PoolState()
        payload = _make_status_payload(circuits_1_8=0x00)
        decode_status(payload, state)
        body2 = state.get_body(2)
        assert body2.is_on is False

    def test_circuit_bitmask(self) -> None:
        """Verify all 40 circuit slots are populated from the bitmask."""
        state = PoolState()
        # Set all circuits on (bytes 2-6 = 0xFF each)
        payload = _make_status_payload(
            circuits_1_8=0xFF,
            circuits_9_16=0xFF,
            circuits_17_24=0xFF,
            circuits_25_32=0xFF,
            circuits_33_40=0xFF,
        )
        decode_status(payload, state)
        # Should have 40 circuits
        assert len(state.circuits) == 40
        for c in state.circuits:
            assert c.is_on is True

    def test_circuit_specific_bits(self) -> None:
        state = PoolState()
        # Only circuit 1 (bit 0 of byte 2) and circuit 6 (bit 5 of byte 2)
        payload = _make_status_payload(circuits_1_8=0x21)
        decode_status(payload, state)
        c1 = state.get_circuit(1)
        c6 = state.get_circuit(6)
        c2 = state.get_circuit(2)
        assert c1.is_on is True
        assert c6.is_on is True
        assert c2.is_on is False

    def test_heat_mode_pool(self) -> None:
        state = PoolState()
        # heat_modes byte: pool = 0x03 (solar only), spa = 0x00
        payload = _make_status_payload(heat_modes=0x03)
        decode_status(payload, state)
        body1 = state.get_body(1)
        assert body1.heat_mode == 3  # solar only

    def test_heat_mode_spa(self) -> None:
        state = PoolState()
        # heat_modes byte: pool = 0x00, spa = 0x04 (>> 2 = 1, heater)
        payload = _make_status_payload(heat_modes=0x04)
        decode_status(payload, state)
        body2 = state.get_body(2)
        assert body2.heat_mode == 1  # heater

    def test_heat_status_heater_active_body1(self) -> None:
        """Pool is on, heater active (bit 2 of byte 10)."""
        state = PoolState()
        payload = _make_status_payload(
            circuits_1_8=0x20,  # pool on
            valve_heat=0x04,  # bit 2 = heater
            heat_modes=0x01,  # heater mode on
        )
        decode_status(payload, state)
        body1 = state.get_body(1)
        assert body1.heat_status == HeatStatus.HEATER

    def test_heat_status_solar_active_body1(self) -> None:
        state = PoolState()
        # Need set_point > temp so it's not "cooling"
        body1 = state.get_body(1)
        body1.set_point = 85
        payload = _make_status_payload(
            circuits_1_8=0x20,
            valve_heat=0x10,  # bit 4 = solar
            heat_modes=0x03,  # solar mode
            water_sensor1=80,
        )
        decode_status(payload, state)
        body1 = state.get_body(1)
        assert body1.heat_status == HeatStatus.SOLAR

    def test_heat_status_off_when_pool_off(self) -> None:
        state = PoolState()
        payload = _make_status_payload(
            circuits_1_8=0x00,  # pool off
            valve_heat=0x04,  # heater bit on but pool is off
            heat_modes=0x01,
        )
        decode_status(payload, state)
        body1 = state.get_body(1)
        assert body1.heat_status == HeatStatus.OFF

    def test_heat_status_body2_heater(self) -> None:
        state = PoolState()
        payload = _make_status_payload(
            circuits_1_8=0x01,  # spa on
            valve_heat=0x08,  # bit 3 = spa heater
            heat_modes=0x04,  # spa heat mode = heater (0x04 >> 2 = 1)
        )
        decode_status(payload, state)
        body2 = state.get_body(2)
        assert body2.heat_status == HeatStatus.HEATER

    def test_model_easytouch2_8(self) -> None:
        state = PoolState()
        payload = _make_status_payload(model_byte2=1, model_byte1=0)
        decode_status(payload, state)
        assert state.equipment.model == 0  # ET28
        assert "EasyTouch2 8" in state.equipment.model_name

    def test_model_easytouch1(self) -> None:
        """EasyTouch 1 models have model_byte2 == 14."""
        state = PoolState()
        payload = _make_status_payload(model_byte2=14, model_byte1=0)
        decode_status(payload, state)
        assert state.equipment.model == 128  # ET8
        assert "EasyTouch 8" in state.equipment.model_name

    def test_short_payload_handled(self) -> None:
        """Payload shorter than 14 bytes should not crash."""
        state = PoolState()
        decode_status(bytes(10), state)
        # State should be unchanged
        assert state.time.hours == 0

    def test_valve_byte(self) -> None:
        state = PoolState()
        payload = _make_status_payload(valve_heat=0x55)
        decode_status(payload, state)
        assert state.valve_byte == 0x55

    def test_water_sensor2(self) -> None:
        state = PoolState()
        payload = _make_status_payload(water_sensor2=85)
        decode_status(payload, state)
        assert state.temps.water_sensor2 == 85

    def test_additional_sensors(self) -> None:
        state = PoolState()
        payload = _make_status_payload(water_sensor3=70, water_sensor4=65)
        decode_status(payload, state)
        assert state.temps.water_sensor3 == 70
        assert state.temps.water_sensor4 == 65


class TestDecodeDatetime:
    """Test Action 5 date/time decode."""

    def test_basic(self) -> None:
        state = PoolState()
        payload = bytes([15, 10, 3, 8, 6, 24, 0, 1])
        decode_datetime(payload, state)
        assert state.time.hours == 15
        assert state.time.minutes == 10
        assert state.time.day_of_week == 3
        assert state.time.date == 8
        assert state.time.month == 6
        assert state.time.year == 24
        assert state.time.adjust_dst is True

    def test_no_dst(self) -> None:
        state = PoolState()
        payload = bytes([12, 0, 1, 1, 1, 23, 0, 0])
        decode_datetime(payload, state)
        assert state.time.adjust_dst is False

    def test_short_payload(self) -> None:
        state = PoolState()
        decode_datetime(bytes(3), state)
        # Should not crash, state unchanged
        assert state.time.hours == 0


class TestDecodeHeatStatus:
    """Test Action 8 heat/temperature status decode."""

    def test_basic(self) -> None:
        state = PoolState()
        # [water1, water2, air, body1_sp, body2_sp, heat_modes, ...]
        payload = bytes([81, 81, 82, 85, 97, 0x07, 0, 0, 0, 100, 100, 4, 0])
        decode_heat_status(payload, state)
        assert state.temps.water_sensor1 == 81
        assert state.temps.air == 82
        body1 = state.get_body(1)
        assert body1.set_point == 85
        assert body1.heat_mode == (0x07 & 0x33)
        body2 = state.get_body(2)
        assert body2.set_point == 97

    def test_spa_heat_mode(self) -> None:
        state = PoolState()
        # heat_modes = 0x0C -> spa = (0x0C & 0xCC) >> 2 = 3 (solar only)
        payload = bytes([80, 80, 75, 84, 100, 0x0C, 0, 0, 0, 0, 0, 0, 0])
        decode_heat_status(payload, state)
        body2 = state.get_body(2)
        assert body2.heat_mode == 3

    def test_cool_setpoint(self) -> None:
        state = PoolState()
        payload = bytes([80, 80, 75, 84, 100, 0, 0, 0, 0, 88, 0, 0, 0])
        decode_heat_status(payload, state)
        body1 = state.get_body(1)
        assert body1.cool_set_point == 88

    def test_short_payload(self) -> None:
        state = PoolState()
        decode_heat_status(bytes(3), state)
        assert state.temps.water_sensor1 == 0


class TestDecodeIntellibrite:
    """Test Action 96 IntelliBrite theme decode."""

    def test_theme_set(self) -> None:
        state = PoolState()
        # Create a light circuit that is on
        c = state.get_circuit(7)
        c.is_light = True
        c.is_on = True
        decode_intellibrite(bytes([177, 0]), state)  # party theme
        assert c.lighting_theme == 177

    def test_theme_off_ignored(self) -> None:
        state = PoolState()
        c = state.get_circuit(7)
        c.is_light = True
        c.is_on = True
        c.lighting_theme = 177
        decode_intellibrite(bytes([0]), state)  # off - shouldn't change stored theme
        assert c.lighting_theme == 177

    def test_theme_on_ignored(self) -> None:
        state = PoolState()
        c = state.get_circuit(7)
        c.is_light = True
        c.is_on = True
        c.lighting_theme = 193
        decode_intellibrite(bytes([1]), state)  # on
        assert c.lighting_theme == 193

    def test_theme_save_ignored(self) -> None:
        state = PoolState()
        c = state.get_circuit(7)
        c.is_light = True
        c.is_on = True
        c.lighting_theme = 182
        decode_intellibrite(bytes([190]), state)  # save
        assert c.lighting_theme == 182

    def test_only_on_lights_updated(self) -> None:
        state = PoolState()
        c_on = state.get_circuit(7)
        c_on.is_light = True
        c_on.is_on = True
        c_off = state.get_circuit(8)
        c_off.is_light = True
        c_off.is_on = False
        decode_intellibrite(bytes([178]), state)  # romance
        assert c_on.lighting_theme == 178
        assert c_off.lighting_theme == 0  # unchanged

    def test_empty_payload(self) -> None:
        state = PoolState()
        decode_intellibrite(b"", state)
        # No crash

    def test_non_light_circuits_unaffected(self) -> None:
        state = PoolState()
        c = state.get_circuit(6)
        c.is_light = False
        c.is_on = True
        decode_intellibrite(bytes([177]), state)
        assert c.lighting_theme == 0
