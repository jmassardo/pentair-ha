"""Tests for pump status decode."""

from custom_components.pentair_easytouch.model import PoolState
from custom_components.pentair_easytouch.protocol.pump import decode_pump_status
from custom_components.pentair_easytouch.protocol.valuemaps import PumpType


class TestDecodePumpAction7:
    """Test pump status response (action 7) decoding."""

    def _make_pump_payload(
        self,
        command: int = 10,
        mode: int = 2,
        drive_state: int = 2,
        watts_hi: int = 1,
        watts_lo: int = 71,
        rpm_hi: int = 7,
        rpm_lo: int = 58,
        flow: int = 0,
        ppc: int = 0,
        reserved9: int = 0,
        reserved10: int = 0,
        status_hi: int = 0,
        status_lo: int = 0,
        time_hi: int = 1,
        time_lo: int = 15,
    ) -> bytes:
        """Build a 15-byte pump action 7 payload."""
        return bytes(
            [
                command,
                mode,
                drive_state,
                watts_hi,
                watts_lo,
                rpm_hi,
                rpm_lo,
                flow,
                ppc,
                reserved9,
                reserved10,
                status_hi,
                status_lo,
                time_hi,
                time_lo,
            ]
        )

    def test_basic_decode(self) -> None:
        state = PoolState()
        # Pre-register pump at address 96
        pump = state.get_pump(1)
        pump.address = 96

        payload = self._make_pump_payload(watts_hi=1, watts_lo=71, rpm_hi=7, rpm_lo=58)
        decode_pump_status(source=96, dest=16, action=7, payload=payload, state=state)

        assert pump.command == 10
        assert pump.mode == 2
        assert pump.drive_state == 2
        assert pump.watts == (1 << 8) | 71  # 327
        assert pump.rpm == (7 << 8) | 58  # 1850
        assert pump.is_active is True

    def test_flow_field(self) -> None:
        state = PoolState()
        pump = state.get_pump(1)
        pump.address = 96

        payload = self._make_pump_payload(flow=45)
        decode_pump_status(source=96, dest=16, action=7, payload=payload, state=state)
        assert pump.flow == 45

    def test_status_error_code(self) -> None:
        state = PoolState()
        pump = state.get_pump(1)
        pump.address = 96

        payload = self._make_pump_payload(status_hi=0x01, status_lo=0x00)
        decode_pump_status(source=96, dest=16, action=7, payload=payload, state=state)
        assert pump.status == 256

    def test_time_field(self) -> None:
        state = PoolState()
        pump = state.get_pump(1)
        pump.address = 96

        payload = self._make_pump_payload(time_hi=2, time_lo=30)
        decode_pump_status(source=96, dest=16, action=7, payload=payload, state=state)
        assert pump.time == 2 * 60 + 30  # 150 minutes

    def test_ppc_field(self) -> None:
        state = PoolState()
        pump = state.get_pump(1)
        pump.address = 96

        payload = self._make_pump_payload(ppc=5)
        decode_pump_status(source=96, dest=16, action=7, payload=payload, state=state)
        assert pump.ppc == 5

    def test_auto_discover_pump(self) -> None:
        """A pump not yet registered should be auto-discovered."""
        state = PoolState()
        payload = self._make_pump_payload()
        decode_pump_status(source=96, dest=16, action=7, payload=payload, state=state)

        assert len(state.pumps) == 1
        pump = state.pumps[0]
        assert pump.id == 1
        assert pump.address == 96
        assert pump.name == "Pump 1"
        assert pump.is_active is True

    def test_auto_discover_pump2(self) -> None:
        """Pump at address 97 = pump #2."""
        state = PoolState()
        payload = self._make_pump_payload()
        decode_pump_status(source=97, dest=16, action=7, payload=payload, state=state)

        pump = state.pumps[0]
        assert pump.id == 2
        assert pump.address == 97
        assert pump.name == "Pump 2"

    def test_ignore_messages_to_pump(self) -> None:
        """Messages FROM controller TO pump (source < 96) should be ignored."""
        state = PoolState()
        payload = self._make_pump_payload()
        decode_pump_status(source=16, dest=96, action=7, payload=payload, state=state)
        assert len(state.pumps) == 0

    def test_short_payload(self) -> None:
        """Short payload should not crash."""
        state = PoolState()
        pump = state.get_pump(1)
        pump.address = 96
        decode_pump_status(source=96, dest=16, action=7, payload=bytes(3), state=state)
        # Should not crash, no update


class TestPumpTypeDetection:
    """Test pump type detection from action 1, 9, 10."""

    def test_detect_vs_pump(self) -> None:
        state = PoolState()
        pump = state.get_pump(1)
        pump.address = 96
        # Action 1 with speed > 300 -> VS
        payload = bytes([0, 0, 0x03, 0xE8])  # speed = 1000
        decode_pump_status(source=96, dest=16, action=1, payload=payload, state=state)
        assert pump.type == PumpType.VS

    def test_detect_vf_pump(self) -> None:
        state = PoolState()
        pump = state.get_pump(1)
        pump.address = 96
        # Action 1 with speed < 300 -> VF
        payload = bytes([0, 0, 0x00, 0x64])  # speed = 100
        decode_pump_status(source=96, dest=16, action=1, payload=payload, state=state)
        assert pump.type == PumpType.VF

    def test_detect_vsf_pump_action9(self) -> None:
        state = PoolState()
        pump = state.get_pump(1)
        pump.address = 96
        payload = bytes([0, 0, 0, 0])
        decode_pump_status(source=96, dest=16, action=9, payload=payload, state=state)
        assert pump.type == PumpType.VSF

    def test_detect_vsf_pump_action10(self) -> None:
        state = PoolState()
        pump = state.get_pump(1)
        pump.address = 96
        payload = bytes([0, 0, 0, 0])
        decode_pump_status(source=96, dest=16, action=10, payload=payload, state=state)
        assert pump.type == PumpType.VSF

    def test_no_overwrite_known_type(self) -> None:
        """Once pump type is known, don't overwrite it."""
        state = PoolState()
        pump = state.get_pump(1)
        pump.address = 96
        pump.type = PumpType.VS
        payload = bytes([0, 0, 0x00, 0x64])  # Would normally detect VF
        decode_pump_status(source=96, dest=16, action=1, payload=payload, state=state)
        assert pump.type == PumpType.VS  # unchanged
