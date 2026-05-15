"""Tests for outbound command builders in ``protocol.commands``."""

from __future__ import annotations

import pytest

from custom_components.pentair_easytouch.const import (
    ACTION_CANCEL_DELAY,
    ACTION_GET_CIRCUITS,
    ACTION_INTELLIBRITE,
    ACTION_SET_CHLORINATOR,
    ACTION_SET_CIRCUIT,
    ACTION_SET_HEAT_SETPOINT,
    ACTION_SET_SCHEDULE,
    CONTROLLER_ADDR,
    PUMP_ACTION_SET_SPEED,
    REMOTE_ADDR,
)
from custom_components.pentair_easytouch.protocol.commands import CommandManager
from custom_components.pentair_easytouch.protocol.framing import PacketFramer, PentairPacket
from custom_components.pentair_easytouch.protocol.transport import BaseTransport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeTransport(BaseTransport):
    """A minimal transport that captures written bytes."""

    def __init__(self) -> None:
        super().__init__()
        self._connected = True
        self.written: list[bytes] = []

    async def _do_connect(self) -> None:
        pass  # pragma: no cover

    async def _do_disconnect(self) -> None:
        pass  # pragma: no cover

    async def _do_read(self) -> bytes:
        return b""  # pragma: no cover

    async def _do_write(self, data: bytes) -> None:
        self.written.append(data)


def _parse_last_packet(transport: FakeTransport) -> PentairPacket:
    """Feed the last written bytes through PacketFramer and return the packet."""
    packets: list[PentairPacket] = []
    framer = PacketFramer(on_packet=packets.append)
    framer.feed(transport.written[-1])
    assert len(packets) == 1, f"Expected 1 packet, got {len(packets)}"
    return packets[0]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture()
def cmd(transport: FakeTransport) -> CommandManager:
    return CommandManager(transport)


# ---------------------------------------------------------------------------
# set_circuit_state
# ---------------------------------------------------------------------------


class TestSetCircuitState:
    """Tests for ``set_circuit_state``."""

    async def test_turn_on(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_circuit_state(6, True)
        pkt = _parse_last_packet(transport)
        assert pkt.action == ACTION_SET_CIRCUIT
        assert pkt.dest == CONTROLLER_ADDR
        assert pkt.source == REMOTE_ADDR
        assert pkt.payload == bytes([6, 1])

    async def test_turn_off(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_circuit_state(6, False)
        pkt = _parse_last_packet(transport)
        assert pkt.payload == bytes([6, 0])

    async def test_circuit_id_boundaries(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        await cmd.set_circuit_state(1, True)
        pkt = _parse_last_packet(transport)
        assert pkt.payload[0] == 1

        await cmd.set_circuit_state(50, False)
        pkt = _parse_last_packet(transport)
        assert pkt.payload[0] == 50

    async def test_invalid_circuit_id_low(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="circuit_id must be between"):
            await cmd.set_circuit_state(0, True)

    async def test_invalid_circuit_id_high(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="circuit_id must be between"):
            await cmd.set_circuit_state(51, True)


# ---------------------------------------------------------------------------
# set_heat_mode
# ---------------------------------------------------------------------------


class TestSetHeatMode:
    """Tests for ``set_heat_mode``."""

    async def test_pool_heater(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_heat_mode(
            body_id=0,
            mode=1,
            current_pool_setpoint=85,
            current_spa_setpoint=100,
            current_spa_mode=0,
        )
        pkt = _parse_last_packet(transport)
        assert pkt.action == ACTION_SET_HEAT_SETPOINT  # Both use 136
        assert pkt.dest == CONTROLLER_ADDR
        # payload: [pool_sp, spa_sp, (spa_mode<<2)|pool_mode, cool]
        assert pkt.payload[0] == 85  # pool setpoint
        assert pkt.payload[1] == 100  # spa setpoint
        assert pkt.payload[2] == 1  # (0<<2)|1 = pool heater on
        assert pkt.payload[3] == 0  # cool setpoint

    async def test_spa_solar_preferred(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_heat_mode(
            body_id=1,
            mode=2,
            current_pool_setpoint=82,
            current_spa_setpoint=102,
            current_pool_mode=1,
        )
        pkt = _parse_last_packet(transport)
        # mode byte: (2<<2)|1 = 8+1 = 9
        assert pkt.payload[2] == 9

    async def test_invalid_body_id(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="body_id must be between"):
            await cmd.set_heat_mode(body_id=2, mode=0)

    async def test_invalid_mode(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="mode must be between"):
            await cmd.set_heat_mode(body_id=0, mode=4)


# ---------------------------------------------------------------------------
# set_heat_setpoint
# ---------------------------------------------------------------------------


class TestSetHeatSetpoint:
    """Tests for ``set_heat_setpoint``."""

    async def test_pool_setpoint(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_heat_setpoint(
            body_id=0,
            temp=88,
            current_pool_setpoint=85,
            current_spa_setpoint=102,
            current_pool_mode=1,
            current_spa_mode=3,
        )
        pkt = _parse_last_packet(transport)
        assert pkt.action == ACTION_SET_HEAT_SETPOINT
        assert pkt.payload[0] == 88  # new pool setpoint
        assert pkt.payload[1] == 102  # spa unchanged
        # mode byte: (3<<2)|1 = 13
        assert pkt.payload[2] == 13

    async def test_spa_setpoint(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_heat_setpoint(
            body_id=1,
            temp=104,
            current_pool_setpoint=85,
            current_spa_setpoint=100,
        )
        pkt = _parse_last_packet(transport)
        assert pkt.payload[0] == 85  # pool unchanged
        assert pkt.payload[1] == 104  # new spa setpoint

    async def test_temp_too_low(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="temp must be between"):
            await cmd.set_heat_setpoint(body_id=0, temp=39)

    async def test_temp_too_high(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="temp must be between"):
            await cmd.set_heat_setpoint(body_id=0, temp=105)

    async def test_temp_boundary_low(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_heat_setpoint(body_id=0, temp=40)
        pkt = _parse_last_packet(transport)
        assert pkt.payload[0] == 40

    async def test_temp_boundary_high(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_heat_setpoint(body_id=0, temp=104)
        pkt = _parse_last_packet(transport)
        assert pkt.payload[0] == 104


# ---------------------------------------------------------------------------
# set_light_theme
# ---------------------------------------------------------------------------


class TestSetLightTheme:
    """Tests for ``set_light_theme``."""

    async def test_party_theme(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_light_theme(177)  # PARTY
        pkt = _parse_last_packet(transport)
        assert pkt.action == ACTION_INTELLIBRITE  # 96
        assert pkt.dest == CONTROLLER_ADDR
        assert pkt.payload == bytes([177, 0])

    async def test_off_theme(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_light_theme(0)
        pkt = _parse_last_packet(transport)
        assert pkt.payload == bytes([0, 0])

    async def test_max_theme(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_light_theme(255)
        pkt = _parse_last_packet(transport)
        assert pkt.payload == bytes([255, 0])

    async def test_invalid_theme(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="theme must be between"):
            await cmd.set_light_theme(256)

    async def test_negative_theme(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="theme must be between"):
            await cmd.set_light_theme(-1)


# ---------------------------------------------------------------------------
# set_chlorinator
# ---------------------------------------------------------------------------


class TestSetChlorinator:
    """Tests for ``set_chlorinator``."""

    async def test_basic_output(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_chlorinator(pool_pct=50, spa_pct=10)
        pkt = _parse_last_packet(transport)
        assert pkt.action == ACTION_SET_CHLORINATOR
        assert pkt.dest == CONTROLLER_ADDR
        # byte0 = (10<<1)+1 = 21, byte1 = 50, byte2 = 0 (no super chlor)
        assert pkt.payload[0] == 21
        assert pkt.payload[1] == 50
        assert pkt.payload[2] == 0
        assert len(pkt.payload) == 10
        # Remaining bytes should be zeros
        assert pkt.payload[3:] == bytes(7)

    async def test_super_chlorination(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_chlorinator(pool_pct=100, spa_pct=0, super_chlor_hours=8)
        pkt = _parse_last_packet(transport)
        assert pkt.payload[0] == (0 << 1) + 1  # 1
        assert pkt.payload[1] == 100
        assert pkt.payload[2] == 8 + 128  # 136

    async def test_zero_output(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_chlorinator(pool_pct=0, spa_pct=0)
        pkt = _parse_last_packet(transport)
        assert pkt.payload[0] == 1  # (0<<1)+1
        assert pkt.payload[1] == 0

    async def test_invalid_pool_pct(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="pool_pct must be between"):
            await cmd.set_chlorinator(pool_pct=101, spa_pct=0)

    async def test_invalid_spa_pct(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="spa_pct must be between"):
            await cmd.set_chlorinator(pool_pct=0, spa_pct=-1)

    async def test_invalid_super_chlor_hours(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="super_chlor_hours must be between"):
            await cmd.set_chlorinator(pool_pct=50, spa_pct=10, super_chlor_hours=73)


# ---------------------------------------------------------------------------
# set_schedule
# ---------------------------------------------------------------------------


class TestSetSchedule:
    """Tests for ``set_schedule``."""

    async def test_basic_schedule(self, transport: FakeTransport, cmd: CommandManager) -> None:
        # 8:00 AM = 480 min, 5:00 PM = 1020 min, Mon-Fri = 0x3E
        await cmd.set_schedule(
            schedule_id=1,
            circuit_id=6,
            start_time=480,
            end_time=1020,
            days=0x3E,
        )
        pkt = _parse_last_packet(transport)
        assert pkt.action == ACTION_SET_SCHEDULE
        assert pkt.dest == CONTROLLER_ADDR
        # [id, circuit, start_hr, start_min, end_hr, end_min, days]
        assert pkt.payload == bytes([1, 6, 8, 0, 17, 0, 0x3E])

    async def test_schedule_with_minutes(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        # 6:30 AM = 390, 9:45 PM = 21*60+45 = 1305, All days = 0x7F
        await cmd.set_schedule(
            schedule_id=3,
            circuit_id=2,
            start_time=390,
            end_time=1305,
            days=0x7F,
        )
        pkt = _parse_last_packet(transport)
        assert pkt.payload == bytes([3, 2, 6, 30, 21, 45, 0x7F])

    async def test_invalid_schedule_id(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="schedule_id must be between"):
            await cmd.set_schedule(0, 6, 480, 1020, 0x7F)

    async def test_schedule_id_max(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_schedule(12, 6, 0, 0, 1)
        pkt = _parse_last_packet(transport)
        assert pkt.payload[0] == 12

    async def test_invalid_circuit_id(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="circuit_id must be between"):
            await cmd.set_schedule(1, 0, 480, 1020, 0x7F)

    async def test_invalid_start_time(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="start_time must be between"):
            await cmd.set_schedule(1, 6, 1440, 1020, 0x7F)

    async def test_invalid_end_time(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="end_time must be between"):
            await cmd.set_schedule(1, 6, 480, -1, 0x7F)

    async def test_invalid_days(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="days must be between"):
            await cmd.set_schedule(1, 6, 480, 1020, 0x80)


# ---------------------------------------------------------------------------
# cancel_delay
# ---------------------------------------------------------------------------


class TestCancelDelay:
    """Tests for ``cancel_delay``."""

    async def test_payload(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.cancel_delay()
        pkt = _parse_last_packet(transport)
        assert pkt.action == ACTION_CANCEL_DELAY
        assert pkt.dest == CONTROLLER_ADDR
        assert pkt.payload == bytes([0])


# ---------------------------------------------------------------------------
# set_pump_speed
# ---------------------------------------------------------------------------


class TestSetPumpSpeed:
    """Tests for ``set_pump_speed``."""

    async def test_set_rpm(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_pump_speed(pump_address=96, speed_rpm=2750)
        pkt = _parse_last_packet(transport)
        assert pkt.action == PUMP_ACTION_SET_SPEED
        assert pkt.dest == 96
        assert pkt.source == REMOTE_ADDR
        # payload: [2, 196, rpm_hi, rpm_lo]
        assert pkt.payload[0] == 2
        assert pkt.payload[1] == 196
        rpm_hi = 2750 >> 8  # 10
        rpm_lo = 2750 & 0xFF  # 190
        assert pkt.payload[2] == rpm_hi
        assert pkt.payload[3] == rpm_lo

    async def test_stop_pump(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_pump_speed(pump_address=96, speed_rpm=0)
        pkt = _parse_last_packet(transport)
        assert pkt.payload[2] == 0
        assert pkt.payload[3] == 0

    async def test_min_rpm(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_pump_speed(pump_address=96, speed_rpm=450)
        pkt = _parse_last_packet(transport)
        assert pkt.payload[2] == (450 >> 8)
        assert pkt.payload[3] == (450 & 0xFF)

    async def test_max_rpm(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_pump_speed(pump_address=96, speed_rpm=3450)
        pkt = _parse_last_packet(transport)
        assert pkt.payload[2] == (3450 >> 8)
        assert pkt.payload[3] == (3450 & 0xFF)

    async def test_invalid_address_low(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="pump_address must be between"):
            await cmd.set_pump_speed(pump_address=95, speed_rpm=1000)

    async def test_invalid_address_high(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="pump_address must be between"):
            await cmd.set_pump_speed(pump_address=112, speed_rpm=1000)

    async def test_invalid_rpm_low(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="speed_rpm must be between"):
            await cmd.set_pump_speed(pump_address=96, speed_rpm=100)

    async def test_invalid_rpm_high(self, cmd: CommandManager) -> None:
        with pytest.raises(ValueError, match="speed_rpm must be between"):
            await cmd.set_pump_speed(pump_address=96, speed_rpm=4000)

    async def test_pump_16_address(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_pump_speed(pump_address=111, speed_rpm=1000)
        pkt = _parse_last_packet(transport)
        assert pkt.dest == 111


# ---------------------------------------------------------------------------
# Custom source address
# ---------------------------------------------------------------------------


class TestCustomSourceAddress:
    """Verify that a custom source address is used in all packets."""

    async def test_custom_source(self, transport: FakeTransport) -> None:
        cmd = CommandManager(transport, source_addr=34)
        await cmd.set_circuit_state(6, True)
        pkt = _parse_last_packet(transport)
        assert pkt.source == 34

    async def test_default_source(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.cancel_delay()
        pkt = _parse_last_packet(transport)
        assert pkt.source == REMOTE_ADDR


# ---------------------------------------------------------------------------
# Packet structure integrity
# ---------------------------------------------------------------------------


class TestPacketIntegrity:
    """Verify that all commands produce valid, parseable packets."""

    async def test_circuit_packet_roundtrip(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        await cmd.set_circuit_state(1, True)
        raw = transport.written[-1]
        # Must start with preamble
        assert raw[:3] == bytes([0xFF, 0x00, 0xFF])
        # Must be parseable
        pkt = _parse_last_packet(transport)
        assert pkt.action == ACTION_SET_CIRCUIT

    async def test_schedule_packet_length(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        await cmd.set_schedule(1, 6, 480, 1020, 0x7F)
        pkt = _parse_last_packet(transport)
        assert len(pkt.payload) == 7

    async def test_chlorinator_packet_length(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        await cmd.set_chlorinator(50, 10)
        pkt = _parse_last_packet(transport)
        assert len(pkt.payload) == 10

    async def test_heat_packet_length(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_heat_mode(body_id=0, mode=1)
        pkt = _parse_last_packet(transport)
        assert len(pkt.payload) == 4

    async def test_pump_packet_length(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_pump_speed(96, 2000)
        pkt = _parse_last_packet(transport)
        assert len(pkt.payload) == 4

    async def test_light_theme_packet_length(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        await cmd.set_light_theme(177)
        pkt = _parse_last_packet(transport)
        assert len(pkt.payload) == 2

    async def test_cancel_delay_packet_length(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        await cmd.cancel_delay()
        pkt = _parse_last_packet(transport)
        assert len(pkt.payload) == 1


# ---------------------------------------------------------------------------
# Transport interaction
# ---------------------------------------------------------------------------


class TestTransportInteraction:
    """Verify transport write is called correctly."""

    async def test_write_called_once_per_command(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        await cmd.set_circuit_state(6, True)
        assert len(transport.written) == 1

    async def test_multiple_commands(self, transport: FakeTransport, cmd: CommandManager) -> None:
        await cmd.set_circuit_state(6, True)
        await cmd.set_circuit_state(7, False)
        await cmd.cancel_delay()
        assert len(transport.written) == 3

    async def test_disconnected_transport_raises(self) -> None:
        transport = FakeTransport()
        transport._connected = False
        cmd = CommandManager(transport)
        with pytest.raises(ConnectionError):
            await cmd.set_circuit_state(6, True)


# ---------------------------------------------------------------------------
# request_config
# ---------------------------------------------------------------------------


class TestRequestConfig:
    """Tests for ``request_config``."""

    async def test_request_circuit_config(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        """request_config builds correct packet for GET_CIRCUITS."""
        await cmd.request_config(ACTION_GET_CIRCUITS, 1)
        pkt = _parse_last_packet(transport)
        assert pkt.action == ACTION_GET_CIRCUITS
        assert pkt.dest == CONTROLLER_ADDR
        assert pkt.source == REMOTE_ADDR
        assert pkt.payload == bytes([1])

    async def test_request_config_various_item_ids(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        """request_config sends correct item_id in payload."""
        for item_id in [1, 5, 10, 20]:
            await cmd.request_config(ACTION_GET_CIRCUITS, item_id)
            pkt = _parse_last_packet(transport)
            assert pkt.payload == bytes([item_id])

    async def test_request_config_invalid_action_low(self, cmd: CommandManager) -> None:
        """request_config rejects action codes below valid range."""
        with pytest.raises(ValueError, match="action must be between"):
            await cmd.request_config(100, 1)

    async def test_request_config_invalid_action_high(self, cmd: CommandManager) -> None:
        """request_config rejects action codes above valid range."""
        with pytest.raises(ValueError, match="action must be between"):
            await cmd.request_config(254, 1)

    async def test_request_config_invalid_item_id_low(self, cmd: CommandManager) -> None:
        """request_config rejects negative item_id."""
        with pytest.raises(ValueError, match="item_id must be between"):
            await cmd.request_config(ACTION_GET_CIRCUITS, -1)

    async def test_request_config_invalid_item_id_high(self, cmd: CommandManager) -> None:
        """request_config rejects item_id above 255."""
        with pytest.raises(ValueError, match="item_id must be between"):
            await cmd.request_config(ACTION_GET_CIRCUITS, 256)

    async def test_request_config_boundary_action_values(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        """request_config accepts boundary action codes 197 and 253."""
        await cmd.request_config(197, 0)
        pkt = _parse_last_packet(transport)
        assert pkt.action == 197

        await cmd.request_config(253, 0)
        pkt = _parse_last_packet(transport)
        assert pkt.action == 253

    async def test_request_config_boundary_item_ids(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        """request_config accepts boundary item IDs 0 and 255."""
        await cmd.request_config(ACTION_GET_CIRCUITS, 0)
        pkt = _parse_last_packet(transport)
        assert pkt.payload == bytes([0])

        await cmd.request_config(ACTION_GET_CIRCUITS, 255)
        pkt = _parse_last_packet(transport)
        assert pkt.payload == bytes([255])


# ---------------------------------------------------------------------------
# Protocol version / sub-byte
# ---------------------------------------------------------------------------


class TestProtocolVersionByte:
    """Verify correct version byte (headerSubByte) per protocol type."""

    async def test_controller_commands_use_version_33(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        """Controller commands (set_circuit, heat, config) use version=33."""
        await cmd.set_circuit_state(1, True)
        pkt = _parse_last_packet(transport)
        assert pkt.version == 33

    async def test_config_request_uses_version_33(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        """Config requests to controller use version=33."""
        await cmd.request_config(ACTION_GET_CIRCUITS, 1)
        pkt = _parse_last_packet(transport)
        assert pkt.version == 33

    async def test_pump_commands_use_version_0(
        self, transport: FakeTransport, cmd: CommandManager
    ) -> None:
        """Pump commands (direct to pump address) use version=0."""
        await cmd.set_pump_speed(96, 2000)
        pkt = _parse_last_packet(transport)
        assert pkt.version == 0
