"""Tests for packet framing: preamble detection, header/payload parsing,
checksum validation, and outbound packet building.
"""

from custom_components.pentair_easytouch.protocol.framing import (
    PacketFramer,
    PentairPacket,
    build_packet,
)


def _make_raw_packet(
    dest: int = 15,
    source: int = 16,
    action: int = 2,
    payload: bytes = b"",
    version: int = 33,
) -> bytes:
    """Build a raw packet with preamble and checksum for testing."""
    return build_packet(dest, source, action, payload, version)


class TestBuildPacket:
    """Test outbound packet construction."""

    def test_basic_structure(self) -> None:
        pkt = build_packet(dest=16, source=33, action=134, payload=b"\x06\x01")
        # Preamble: FF 00 FF
        assert pkt[:3] == bytes([0xFF, 0x00, 0xFF])
        # Header start
        assert pkt[3] == 0xA5  # 165
        assert pkt[4] == 33  # version (headerSubByte for EasyTouch)
        assert pkt[5] == 16  # dest
        assert pkt[6] == 33  # source
        assert pkt[7] == 134  # action
        assert pkt[8] == 2  # datalen
        # Payload
        assert pkt[9] == 0x06
        assert pkt[10] == 0x01
        # Checksum (2 bytes)
        assert len(pkt) == 3 + 6 + 2 + 2  # preamble + header + payload + checksum

    def test_checksum_correct(self) -> None:
        payload = bytes([0x06, 0x01])
        pkt = build_packet(dest=16, source=33, action=134, payload=payload)
        header = pkt[3:9]  # 6-byte header
        expected_sum = sum(header) + sum(payload)
        chk_hi = pkt[-2]
        chk_lo = pkt[-1]
        actual_sum = (chk_hi << 8) | chk_lo
        assert actual_sum == expected_sum

    def test_empty_payload(self) -> None:
        pkt = build_packet(dest=15, source=16, action=131)
        assert len(pkt) == 3 + 6 + 0 + 2  # preamble + header + 0 payload + checksum
        assert pkt[8] == 0  # datalen = 0

    def test_payload_as_list(self) -> None:
        pkt = build_packet(dest=16, source=33, action=134, payload=[6, 1])
        assert pkt[9] == 6
        assert pkt[10] == 1


class TestPacketFramer:
    """Test the streaming packet parser."""

    def test_single_complete_packet(self) -> None:
        """Feed a complete packet and verify it's parsed."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        raw = _make_raw_packet(dest=15, source=16, action=2, payload=bytes(29))
        framer.feed(raw)

        assert len(received) == 1
        pkt = received[0]
        assert pkt.dest == 15
        assert pkt.source == 16
        assert pkt.action == 2
        assert len(pkt.payload) == 29

    def test_two_packets_in_stream(self) -> None:
        """Feed two packets back-to-back."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        raw1 = _make_raw_packet(action=2, payload=bytes(5))
        raw2 = _make_raw_packet(action=5, payload=bytes(8))
        framer.feed(raw1 + raw2)

        assert len(received) == 2
        assert received[0].action == 2
        assert received[1].action == 5

    def test_byte_by_byte(self) -> None:
        """Feed one byte at a time."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        raw = _make_raw_packet(action=2, payload=bytes(10))
        for byte in raw:
            framer.feed(bytes([byte]))

        assert len(received) == 1
        assert received[0].action == 2

    def test_garbage_before_preamble(self) -> None:
        """Garbage bytes before the preamble should be skipped."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        garbage = bytes([0x00, 0x42, 0x99, 0x12, 0x00])
        raw = _make_raw_packet(action=2, payload=bytes(5))
        framer.feed(garbage + raw)

        assert len(received) == 1
        assert received[0].action == 2

    def test_invalid_checksum_dropped(self) -> None:
        """A packet with a bad checksum should be dropped."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        raw = bytearray(_make_raw_packet(action=2, payload=bytes(5)))
        # Corrupt the checksum
        raw[-1] ^= 0xFF
        framer.feed(bytes(raw))

        assert len(received) == 0

    def test_partial_then_complete(self) -> None:
        """Feed a packet in two halves."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        raw = _make_raw_packet(action=8, payload=bytes(13))
        mid = len(raw) // 2
        framer.feed(raw[:mid])
        assert len(received) == 0
        framer.feed(raw[mid:])
        assert len(received) == 1

    def test_datalen_too_large_skipped(self) -> None:
        """A packet with datalen > 75 should be rejected."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        # Manually craft a packet with datalen = 80
        preamble = bytes([0xFF, 0x00, 0xFF, 0xA5])
        header_rest = bytes([1, 15, 16, 2, 80])  # version, dest, src, action, datalen=80
        # Feed preamble + header but this should be rejected
        framer.feed(preamble + header_rest)
        assert len(received) == 0

    def test_reset(self) -> None:
        """Reset should discard partial packet state."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        raw = _make_raw_packet(action=2, payload=bytes(10))
        framer.feed(raw[:5])
        framer.reset()
        framer.feed(raw)  # Feed complete from scratch
        assert len(received) == 1

    def test_set_on_packet(self) -> None:
        """Test changing the callback."""
        received1: list[PentairPacket] = []
        received2: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received1.append)

        raw = _make_raw_packet(action=2, payload=bytes(5))
        framer.feed(raw)
        assert len(received1) == 1

        framer.set_on_packet(received2.append)
        framer.feed(raw)
        assert len(received2) == 1
        assert len(received1) == 1  # unchanged

    def test_version_preserved(self) -> None:
        """Protocol version byte should be preserved."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        raw = _make_raw_packet(version=63, action=2, payload=bytes(5))
        framer.feed(raw)
        assert received[0].version == 63

    def test_repr(self) -> None:
        """PentairPacket repr should be readable."""
        pkt = PentairPacket(version=1, dest=15, source=16, action=2, payload=b"\x01\x02")
        r = repr(pkt)
        assert "act=2" in r
        assert "01 02" in r

    def test_repr_empty_payload(self) -> None:
        pkt = PentairPacket(version=1, dest=15, source=16, action=131, payload=b"")
        r = repr(pkt)
        assert "(empty)" in r

    def test_false_preamble_start(self) -> None:
        """0xFF bytes before the real preamble should not confuse the framer."""
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)

        # Some 0xFF bytes then a valid packet
        noise = bytes([0xFF, 0xFF, 0x42])
        raw = _make_raw_packet(action=2, payload=bytes(5))
        framer.feed(noise + raw)
        assert len(received) == 1

    def test_real_world_status_packet(self) -> None:
        """Parse a realistic status broadcast packet."""
        # Simulated Action 2 status broadcast (29 bytes payload)
        payload = bytes(
            [
                15,  # hour
                34,  # minute
                0x20,  # circuits 1-8 (bit 5 = pool on)
                0,  # circuits 9-16
                0,
                0,
                0,  # circuits 17-40
                0,
                0,  # reserved
                0,  # mode (auto)
                0x43,  # valve/heat byte
                0,  # heat status
                0,  # delay
                0,  # reserved
                81,  # water sensor 1 (81F)
                81,  # water sensor 2
                32,  # reserved
                91,  # solar sensor
                82,  # air temp
                91,  # solar sensor 2
                0,
                0,  # water 3, 4
                7,  # heat modes body 1&2
                4,  # heat modes body 3&4
                0,  # reserved
                77,  # unknown
                163,  # unknown
                1,  # model byte 2
                0,  # model byte 1
            ]
        )
        raw = _make_raw_packet(dest=15, source=16, action=2, payload=payload)
        received: list[PentairPacket] = []
        framer = PacketFramer(on_packet=received.append)
        framer.feed(raw)

        assert len(received) == 1
        pkt = received[0]
        assert pkt.action == 2
        assert pkt.payload[0] == 15  # hour
        assert pkt.payload[14] == 81  # water temp
        assert pkt.payload[18] == 82  # air temp
