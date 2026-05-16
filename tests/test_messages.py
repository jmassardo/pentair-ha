"""Tests for the message router."""

from custom_components.pentair_easytouch.model import PoolState
from custom_components.pentair_easytouch.protocol.framing import PentairPacket, build_packet
from custom_components.pentair_easytouch.protocol.messages import MessageRouter


def _make_packet(
    action: int,
    payload: bytes = b"",
    source: int = 16,
    dest: int = 15,
    version: int = 1,
) -> PentairPacket:
    """Create a PentairPacket for testing."""
    return PentairPacket(
        version=version,
        dest=dest,
        source=source,
        action=action,
        payload=payload,
    )


def _make_status_payload_29() -> bytes:
    """Build a minimal 29-byte Action 2 status payload."""
    return bytes(
        [
            10,  # hour
            30,  # minute
            0x20,  # circuits 1-8 (pool on)
            0,
            0,
            0,
            0,  # circuits 9-40
            0,
            0,  # reserved
            0,  # mode
            0,  # valve/heat
            0,  # heat status
            0,  # delay
            0,  # reserved
            80,  # water sensor 1
            80,  # water sensor 2
            0,  # reserved
            90,  # solar
            75,  # air
            90,  # solar 2
            0,
            0,  # water 3,4
            0,  # heat modes
            0,  # heat modes 3/4
            0,
            0,
            0,  # reserved
            1,  # model byte 2
            0,  # model byte 1
        ]
    )


class TestMessageRouter:
    def test_dispatch_action2(self) -> None:
        """Action 2 status should update pool state."""
        state = PoolState()
        router = MessageRouter(state)

        payload = _make_status_payload_29()
        pkt = _make_packet(action=2, payload=payload)
        router.dispatch(pkt)

        assert state.time.hours == 10
        assert state.time.minutes == 30
        assert state.temps.water_sensor1 == 80
        assert state.temps.air == 75

    def test_dispatch_action5(self) -> None:
        """Action 5 datetime should update time."""
        state = PoolState()
        router = MessageRouter(state)

        payload = bytes([14, 30, 3, 15, 7, 24, 0, 1])
        pkt = _make_packet(action=5, payload=payload)
        router.dispatch(pkt)

        assert state.time.hours == 14
        assert state.time.minutes == 30
        assert state.time.date == 15
        assert state.time.month == 7

    def test_dispatch_action8(self) -> None:
        """Action 8 heat status should update body setpoints."""
        state = PoolState()
        router = MessageRouter(state)

        payload = bytes([80, 80, 75, 84, 100, 0x01, 0, 0, 0, 88, 0, 0, 0])
        pkt = _make_packet(action=8, payload=payload)
        router.dispatch(pkt)

        body1 = state.get_body(1)
        assert body1.set_point == 84

    def test_dispatch_action96(self) -> None:
        """Action 96 should update light themes."""
        state = PoolState()
        c = state.get_circuit(7)
        c.is_light = True
        c.is_on = True
        router = MessageRouter(state)

        pkt = _make_packet(action=96, payload=bytes([179, 0]))  # caribbean
        router.dispatch(pkt)
        assert c.lighting_theme == 179

    def test_dispatch_action25_chlorinator(self) -> None:
        """Action 25 should update chlorinator."""
        state = PoolState()
        router = MessageRouter(state)

        # byte[0] = (spa_setpoint << 1) | active = (20 << 1) | 1 = 41
        # byte[1] = pool_setpoint = 60
        payload = bytes([41, 60, 0, 0, 0, 0])
        pkt = _make_packet(action=25, payload=payload)
        router.dispatch(pkt)

        chlor = state.get_chlorinator(1)
        assert chlor.pool_setpoint == 60
        assert chlor.spa_setpoint == 20

    def test_dispatch_pump_action7(self) -> None:
        """Pump status from address 96 should update pump state."""
        state = PoolState()
        router = MessageRouter(state)

        # 15-byte pump status payload
        payload = bytes([10, 2, 2, 1, 71, 7, 58, 30, 0, 0, 0, 0, 0, 1, 15])
        pkt = _make_packet(action=7, source=96, dest=16, payload=payload)
        router.dispatch(pkt)

        assert len(state.pumps) == 1
        pump = state.pumps[0]
        assert pump.watts == (1 << 8) | 71
        assert pump.rpm == (7 << 8) | 58
        assert pump.flow == 30

    def test_dispatch_unknown_action(self) -> None:
        """Unknown action should not crash."""
        state = PoolState()
        router = MessageRouter(state)

        pkt = _make_packet(action=999, payload=bytes(5))
        router.dispatch(pkt)  # should not raise

    def test_on_state_updated_callback(self) -> None:
        """The callback should be called after state updates."""
        state = PoolState()
        callback_count = [0]

        def on_update() -> None:
            callback_count[0] += 1

        router = MessageRouter(state, on_state_updated=on_update)

        payload = _make_status_payload_29()
        pkt = _make_packet(action=2, payload=payload)
        router.dispatch(pkt)

        assert callback_count[0] == 1

    def test_register_custom_handler(self) -> None:
        """Custom handlers should work."""
        state = PoolState()
        custom_called = [False]

        def custom_handler(payload: bytes, s: PoolState) -> None:
            custom_called[0] = True

        router = MessageRouter(state)
        router.register_handler(42, custom_handler)

        pkt = _make_packet(action=42, payload=bytes(5))
        router.dispatch(pkt)

        assert custom_called[0] is True

    def test_state_property(self) -> None:
        state = PoolState()
        router = MessageRouter(state)
        assert router.state is state

    def test_handler_exception_caught(self) -> None:
        """Exceptions in handlers should be caught, not propagated."""
        state = PoolState()

        def bad_handler(payload: bytes, s: PoolState) -> None:
            raise ValueError("test error")

        router = MessageRouter(state)
        router.register_handler(42, bad_handler)

        pkt = _make_packet(action=42, payload=bytes(5))
        router.dispatch(pkt)  # should not raise

    def test_callback_exception_caught(self) -> None:
        """Exceptions in the on_state_updated callback should be caught."""
        state = PoolState()

        def bad_callback() -> None:
            raise RuntimeError("callback error")

        router = MessageRouter(state, on_state_updated=bad_callback)

        payload = _make_status_payload_29()
        pkt = _make_packet(action=2, payload=payload)
        router.dispatch(pkt)  # should not raise


class TestEndToEndFramingToRouter:
    """Test the full pipeline: raw bytes -> framer -> router -> state."""

    def test_full_pipeline(self) -> None:
        from custom_components.pentair_easytouch.protocol.framing import PacketFramer

        state = PoolState()
        router = MessageRouter(state)
        framer = PacketFramer(on_packet=router.dispatch)

        payload = _make_status_payload_29()
        raw = build_packet(dest=15, source=16, action=2, payload=payload)
        framer.feed(raw)

        assert state.time.hours == 10
        assert state.temps.water_sensor1 == 80
        assert state.temps.air == 75

    def test_multiple_messages_pipeline(self) -> None:
        from custom_components.pentair_easytouch.protocol.framing import PacketFramer

        state = PoolState()
        router = MessageRouter(state)
        framer = PacketFramer(on_packet=router.dispatch)

        # Status packet
        status_payload = _make_status_payload_29()
        raw1 = build_packet(dest=15, source=16, action=2, payload=status_payload)

        # DateTime packet
        dt_payload = bytes([20, 45, 5, 25, 12, 23, 0, 1])
        raw2 = build_packet(dest=15, source=16, action=5, payload=dt_payload)

        framer.feed(raw1 + raw2)

        # Status should have updated
        assert state.time.hours == 20  # Overwritten by action 5
        assert state.time.minutes == 45
        assert state.time.date == 25
