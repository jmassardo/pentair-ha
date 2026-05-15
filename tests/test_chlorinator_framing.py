"""Tests for chlorinator sub-protocol frame parsing and end-to-end routing."""

from custom_components.pentair_easytouch.const import (
    CHLORINATOR_ADDR_START,
    CONTROLLER_ADDR,
)
from custom_components.pentair_easytouch.model import PoolState
from custom_components.pentair_easytouch.protocol.framing import (
    PacketFramer,
    PentairPacket,
    build_packet,
)
from custom_components.pentair_easytouch.protocol.messages import MessageRouter


def _build_chlor_frame(
    dest: int,
    action: int,
    payload: bytes = b"",
) -> bytes:
    """Build a valid chlorinator sub-protocol frame with correct checksum.

    Format: [16, 2, dest, action, ...payload..., checksum, 16, 3]
    """
    checksum = (16 + 2 + dest + action + sum(payload)) % 256
    return bytes([16, 2, dest, action]) + payload + bytes([checksum, 16, 3])


class TestChlorinatorFrameParsing:
    """Test the framer's ability to parse chlorinator sub-protocol frames."""

    def test_action18_salt_response(self) -> None:
        """Parse a salt level response from chlorinator (action 18)."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        # Salt = 3200 PPM → salt_level_div50 = 64, status = 0
        frame = _build_chlor_frame(dest=0, action=18, payload=bytes([64, 0]))
        framer.feed(frame)

        assert len(received) == 1
        pkt = received[0]
        assert pkt.version == 0
        assert pkt.dest == 0
        assert pkt.source == CHLORINATOR_ADDR_START
        assert pkt.action == 18
        assert pkt.payload == bytes([64, 0])

    def test_action17_set_output(self) -> None:
        """Parse a set output command from OCP to chlorinator (action 17)."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        # OCP → Chlorinator: set 50% output
        frame = _build_chlor_frame(dest=80, action=17, payload=bytes([50]))
        framer.feed(frame)

        assert len(received) == 1
        pkt = received[0]
        assert pkt.version == 0
        assert pkt.dest == 80
        assert pkt.source == CONTROLLER_ADDR
        assert pkt.action == 17
        assert pkt.payload == bytes([50])

    def test_empty_payload_frame(self) -> None:
        """A chlorinator frame with no payload bytes is valid."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        # Action 19 keep-alive, no payload
        frame = _build_chlor_frame(dest=80, action=19, payload=b"")
        framer.feed(frame)

        assert len(received) == 1
        assert received[0].action == 19
        assert received[0].payload == b""

    def test_broadcast_dest_16(self) -> None:
        """Dest=16 (broadcast) from chlorinator is valid."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        frame = _build_chlor_frame(dest=16, action=1, payload=bytes([0]))
        framer.feed(frame)

        assert len(received) == 1
        assert received[0].dest == 16
        assert received[0].source == CHLORINATOR_ADDR_START

    def test_all_valid_dest_addresses(self) -> None:
        """All valid chlorinator dest addresses should parse."""
        for dest in [0, 16, 80, 81, 82, 83]:
            received: list[PentairPacket] = []
            framer = PacketFramer(on_packet=received.append)
            frame = _build_chlor_frame(dest=dest, action=1, payload=bytes([0]))
            framer.feed(frame)
            assert len(received) == 1, f"Failed for dest={dest}"

    def test_invalid_dest_rejected(self) -> None:
        """A frame with an invalid dest byte should not parse as chlorinator."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        # dest=5 is not valid for chlorinator
        bad_frame = bytes([16, 2, 5, 18, 64, 0])
        # Add checksum and terminator even though it won't matter
        checksum = (16 + 2 + 5 + 18 + 64 + 0) % 256
        bad_frame += bytes([checksum, 16, 3])
        framer.feed(bad_frame)

        # Should NOT be parsed as a chlorinator frame
        assert len(received) == 0

    def test_checksum_validation(self) -> None:
        """Frame with incorrect checksum should be dropped."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        # Valid frame but corrupt the checksum
        frame = bytes([16, 2, 0, 18, 64, 0, 99, 16, 3])  # checksum should be 100
        framer.feed(frame)

        assert len(received) == 0

    def test_correct_checksum_calculation(self) -> None:
        """Verify the specific checksum example from the spec."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        # [16, 2, 0, 18, 64, 0, 100, 16, 3]
        # Checksum = (16 + 2 + 0 + 18 + 64 + 0) % 256 = 100
        frame = bytes([16, 2, 0, 18, 64, 0, 100, 16, 3])
        framer.feed(frame)

        assert len(received) == 1
        assert received[0].payload == bytes([64, 0])

    def test_byte_by_byte_feeding(self) -> None:
        """Feeding chlorinator frame one byte at a time should work."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        frame = _build_chlor_frame(dest=0, action=18, payload=bytes([64, 0]))
        for byte in frame:
            framer.feed(bytes([byte]))

        assert len(received) == 1
        assert received[0].action == 18

    def test_multiple_chlorinator_frames(self) -> None:
        """Multiple chlorinator frames in sequence."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        frame1 = _build_chlor_frame(dest=0, action=18, payload=bytes([64, 0]))
        frame2 = _build_chlor_frame(dest=80, action=17, payload=bytes([50]))
        framer.feed(frame1 + frame2)

        assert len(received) == 2
        assert received[0].action == 18
        assert received[1].action == 17

    def test_garbage_before_chlorinator_frame(self) -> None:
        """Garbage bytes before a chlorinator frame should be skipped."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        garbage = bytes([0x42, 0x99, 0x00, 0x55])
        frame = _build_chlor_frame(dest=0, action=18, payload=bytes([64, 0]))
        framer.feed(garbage + frame)

        assert len(received) == 1
        assert received[0].action == 18

    def test_frame_too_long_discarded(self) -> None:
        """A frame with payload exceeding 25 bytes should be discarded."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        # 26-byte payload (too long)
        long_payload = bytes(26)
        checksum = (16 + 2 + 0 + 18 + sum(long_payload)) % 256
        frame = bytes([16, 2, 0, 18]) + long_payload + bytes([checksum, 16, 3])
        framer.feed(frame)

        assert len(received) == 0

    def test_partial_frame_then_complete(self) -> None:
        """A partial chlorinator frame followed by rest should parse."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        frame = _build_chlor_frame(dest=0, action=18, payload=bytes([64, 0]))
        # Feed first 4 bytes, then the rest
        framer.feed(frame[:4])
        assert len(received) == 0
        framer.feed(frame[4:])
        assert len(received) == 1


class TestMixedProtocolFrames:
    """Test that standard and chlorinator frames coexist correctly."""

    def test_standard_then_chlorinator(self) -> None:
        """Standard Pentair frame followed by a chlorinator frame."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        std = build_packet(dest=15, source=16, action=2, payload=bytes(5))
        chlor = _build_chlor_frame(dest=0, action=18, payload=bytes([64, 0]))
        framer.feed(std + chlor)

        assert len(received) == 2
        assert received[0].version == 1  # standard
        assert received[0].action == 2
        assert received[1].version == 0  # chlorinator
        assert received[1].action == 18

    def test_chlorinator_then_standard(self) -> None:
        """Chlorinator frame followed by a standard Pentair frame."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        chlor = _build_chlor_frame(dest=80, action=17, payload=bytes([50]))
        std = build_packet(dest=15, source=16, action=5, payload=bytes(8))
        framer.feed(chlor + std)

        assert len(received) == 2
        assert received[0].version == 0
        assert received[0].action == 17
        assert received[1].version == 1
        assert received[1].action == 5

    def test_interleaved_frames(self) -> None:
        """Multiple interleaved standard and chlorinator frames."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        std1 = build_packet(dest=15, source=16, action=2, payload=bytes(5))
        chlor1 = _build_chlor_frame(dest=0, action=18, payload=bytes([60, 0]))
        std2 = build_packet(dest=15, source=16, action=8, payload=bytes(13))
        chlor2 = _build_chlor_frame(dest=80, action=17, payload=bytes([75]))

        framer.feed(std1 + chlor1 + std2 + chlor2)

        assert len(received) == 4
        assert received[0].action == 2
        assert received[0].version == 1
        assert received[1].action == 18
        assert received[1].version == 0
        assert received[2].action == 8
        assert received[2].version == 1
        assert received[3].action == 17
        assert received[3].version == 0

    def test_16_2_inside_standard_payload_not_confused(self) -> None:
        """Bytes [16, 2] inside a standard Pentair payload must not trigger chlorinator parsing.

        The framer should only look for chlorinator frames during WAIT_PREAMBLE state.
        """
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        # Standard packet with [16, 2, 0, 18] in its payload
        payload = bytes([16, 2, 0, 18, 64, 0, 100, 16, 3, 0, 0])
        std = build_packet(dest=15, source=16, action=2, payload=payload)
        framer.feed(std)

        # Should parse as exactly one standard frame, not a chlorinator frame
        assert len(received) == 1
        assert received[0].version == 1
        assert received[0].action == 2
        assert received[0].payload == payload


class TestChlorinatorMessageRouting:
    """Test that chlorinator sub-protocol packets are routed to decode_chlorinator_action."""

    def test_action18_updates_salt_level(self) -> None:
        """Action 18 chlorinator response should update salt_level in state."""
        state = PoolState()
        router = MessageRouter(state)

        # Simulate a chlorinator sub-protocol packet (version=0)
        pkt = PentairPacket(
            version=0,
            dest=0,
            source=CHLORINATOR_ADDR_START,
            action=18,
            payload=bytes([64, 0]),  # salt = 64*50 = 3200
        )
        router.dispatch(pkt)

        chlor = state.get_chlorinator(1)
        assert chlor.salt_level == 3200
        assert chlor.is_active is True

    def test_action17_updates_target_output(self) -> None:
        """Action 17 OCP → chlorinator should update target_output."""
        state = PoolState()
        router = MessageRouter(state)

        pkt = PentairPacket(
            version=0,
            dest=80,
            source=CONTROLLER_ADDR,
            action=17,
            payload=bytes([50]),
        )
        router.dispatch(pkt)

        chlor = state.get_chlorinator(1)
        assert chlor.target_output == 50

    def test_action3_updates_name(self) -> None:
        """Action 3 model response should update chlorinator name."""
        state = PoolState()
        router = MessageRouter(state)

        name_bytes = b"Intellichlor--40"
        pkt = PentairPacket(
            version=0,
            dest=0,
            source=CHLORINATOR_ADDR_START,
            action=3,
            payload=bytes([0]) + name_bytes,
        )
        router.dispatch(pkt)

        chlor = state.get_chlorinator(1)
        assert chlor.name == "Intellichlor--40"

    def test_callback_called_on_chlorinator_dispatch(self) -> None:
        """on_state_updated should fire when a chlorinator packet is dispatched."""
        state = PoolState()
        calls = [0]

        def on_update() -> None:
            calls[0] += 1

        router = MessageRouter(state, on_state_updated=on_update)

        pkt = PentairPacket(
            version=0,
            dest=0,
            source=CHLORINATOR_ADDR_START,
            action=18,
            payload=bytes([60, 0]),
        )
        router.dispatch(pkt)
        assert calls[0] == 1

    def test_exception_in_chlorinator_decode_caught(self) -> None:
        """Exceptions during chlorinator decode should not propagate."""
        state = PoolState()
        router = MessageRouter(state)

        # Empty payload for action 22 with dest=0 — should not crash
        pkt = PentairPacket(
            version=0,
            dest=0,
            source=CHLORINATOR_ADDR_START,
            action=22,
            payload=b"",
        )
        router.dispatch(pkt)  # should not raise

    def test_version0_non_chlorinator_not_routed(self) -> None:
        """A version=0 packet with non-chlorinator addressing should not route to chlor."""
        state = PoolState()
        router = MessageRouter(state)

        # version=0 but source/dest don't match chlorinator
        pkt = PentairPacket(
            version=0,
            dest=15,
            source=16,
            action=18,
            payload=bytes([64, 0]),
        )
        router.dispatch(pkt)

        # Should NOT have updated chlorinator state (salt_level stays at default 0)
        chlor = state.get_chlorinator(1)
        assert chlor.salt_level == 0
        assert chlor.is_active is False


class TestEndToEndChlorinatorPipeline:
    """Test full pipeline: raw chlorinator bytes → framer → router → PoolState."""

    def test_salt_level_end_to_end(self) -> None:
        """Feed raw chlorinator bytes and verify salt level appears in state."""
        state = PoolState()
        router = MessageRouter(state)
        framer = PacketFramer(on_packet=router.dispatch)

        # Action 18 response: salt=3200 (64*50), status=0
        frame = _build_chlor_frame(dest=0, action=18, payload=bytes([64, 0]))
        framer.feed(frame)

        chlor = state.get_chlorinator(1)
        assert chlor.salt_level == 3200
        assert chlor.is_active is True

    def test_set_output_end_to_end(self) -> None:
        """Feed raw OCP→chlorinator set output and verify target_output in state."""
        state = PoolState()
        router = MessageRouter(state)
        framer = PacketFramer(on_packet=router.dispatch)

        frame = _build_chlor_frame(dest=80, action=17, payload=bytes([50]))
        framer.feed(frame)

        chlor = state.get_chlorinator(1)
        assert chlor.target_output == 50

    def test_mixed_standard_and_chlorinator_end_to_end(self) -> None:
        """Standard status + chlorinator salt in one stream updates both."""
        state = PoolState()
        router = MessageRouter(state)
        framer = PacketFramer(on_packet=router.dispatch)

        # Standard status payload (29 bytes)
        status_payload = bytes(
            [
                10,
                30,  # hour, minute
                0x20,
                0,
                0,
                0,
                0,  # circuits
                0,
                0,  # reserved
                0,  # mode
                0,
                0,
                0,
                0,  # valve/heat/delay/reserved
                80,
                80,  # water sensors
                0,  # reserved
                90,
                75,
                90,  # solar, air, solar2
                0,
                0,  # water 3,4
                0,
                0,  # heat modes
                0,
                0,
                0,  # reserved
                1,
                0,  # model
            ]
        )
        std_packet = build_packet(dest=15, source=16, action=2, payload=status_payload)

        # Chlorinator salt response
        chlor_frame = _build_chlor_frame(dest=0, action=18, payload=bytes([64, 0]))

        framer.feed(std_packet + chlor_frame)

        # Standard status updated
        assert state.time.hours == 10
        assert state.temps.air == 75

        # Chlorinator updated
        chlor = state.get_chlorinator(1)
        assert chlor.salt_level == 3200
        assert chlor.is_active is True

    def test_ichlor_status_end_to_end(self) -> None:
        """Action 22 iChlor status updates current_output."""
        state = PoolState()
        router = MessageRouter(state)
        framer = PacketFramer(on_packet=router.dispatch)

        # Action 22 from chlorinator: [0, current_output, ...]
        frame = _build_chlor_frame(dest=0, action=22, payload=bytes([0, 15, 73, 0, 5]))
        framer.feed(frame)

        chlor = state.get_chlorinator(1)
        assert chlor.current_output == 15
        assert chlor.is_active is True
