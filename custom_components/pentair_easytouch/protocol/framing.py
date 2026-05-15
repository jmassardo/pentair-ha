"""Packet framing for the Pentair RS485 broadcast protocol.

Implements a byte-level state machine that:

1. Scans incoming bytes for the preamble ``[255, 0, 255]``.
2. Reads the 6-byte header ``[165, sub, dest, src, action, datalen]``.
3. Reads ``datalen`` payload bytes.
4. Validates the 2-byte big-endian checksum (sum of header + payload).
5. Emits complete, validated packets via a callback.

Also detects IntelliChlor chlorinator sub-protocol frames ``[16, 2, …, 16, 3]``
on the same RS485 bus and emits them as ``PentairPacket`` with ``version=0``.

Also provides ``build_packet`` to construct outbound packets.
"""

from __future__ import annotations

import enum
import logging
from collections.abc import Callable
from dataclasses import dataclass

from custom_components.pentair_easytouch.const import (
    CHLORINATOR_ADDR_START,
    CONTROLLER_ADDR,
)

_LOGGER = logging.getLogger(__name__)

# Minimum valid datalen we'll accept (0 is fine for acks)
_MIN_DATALEN = 0
# Maximum sane datalen - the reference code caps at 75
_MAX_DATALEN = 75

# Header is always 6 bytes: [165, sub, dest, src, action, datalen]
_HEADER_LEN = 6
# Checksum is 2 bytes (big-endian)
_CHECKSUM_LEN = 2

# Chlorinator sub-protocol constants
_CHLOR_START_0 = 0x10  # 16
_CHLOR_START_1 = 0x02  # 2
_CHLOR_TERM_1 = 0x03  # 3
_CHLOR_VALID_DESTS: frozenset[int] = frozenset({0, 16, 80, 81, 82, 83})
_CHLOR_MAX_PAYLOAD_LEN = 25


@dataclass(frozen=True, slots=True)
class PentairPacket:
    """A validated Pentair RS485 packet."""

    version: int  # header[1] (sub byte)
    dest: int  # header[2]
    source: int  # header[3]
    action: int  # header[4]
    payload: bytes  # datalen bytes

    def __repr__(self) -> str:
        payload_hex = self.payload.hex(" ") if self.payload else "(empty)"
        return (
            f"PentairPacket(ver={self.version}, dst={self.dest}, "
            f"src={self.source}, act={self.action}, "
            f"len={len(self.payload)}, payload={payload_hex})"
        )


PacketCallback = Callable[[PentairPacket], None]


class _FramerState(enum.Enum):
    """Internal state of the framing state machine."""

    WAIT_PREAMBLE = "wait_preamble"
    WAIT_HEADER = "wait_header"
    WAIT_PAYLOAD = "wait_payload"
    WAIT_CHECKSUM = "wait_checksum"


class PacketFramer:
    """Streaming packet parser for the Pentair RS485 protocol.

    Feed raw bytes via ``feed(data)``; complete packets are delivered
    to the ``on_packet`` callback.
    """

    def __init__(self, on_packet: PacketCallback | None = None) -> None:
        self._on_packet: PacketCallback | None = on_packet
        self._state: _FramerState = _FramerState.WAIT_PREAMBLE
        self._buf: bytearray = bytearray()
        self._header: bytes = b""
        self._datalen: int = 0
        self._payload: bytes = b""
        # Preamble tracking: we need to see [255, 0, 255] then [165]
        self._preamble_idx: int = 0

    def set_on_packet(self, callback: PacketCallback) -> None:
        """Set (or replace) the packet callback."""
        self._on_packet = callback

    def reset(self) -> None:
        """Reset the state machine, discarding any partial packet."""
        self._state = _FramerState.WAIT_PREAMBLE
        self._buf.clear()
        self._header = b""
        self._datalen = 0
        self._payload = b""
        self._preamble_idx = 0

    def feed(self, data: bytes) -> None:
        """Feed raw bytes into the framer.

        Any number of complete packets may be emitted during this call.
        Partial data is buffered internally.
        """
        self._buf.extend(data)
        while self._buf:
            if self._state == _FramerState.WAIT_PREAMBLE:
                if not self._scan_preamble():
                    break
            elif self._state == _FramerState.WAIT_HEADER:
                if not self._read_header():
                    break
            elif self._state == _FramerState.WAIT_PAYLOAD:
                if not self._read_payload():
                    break
            elif self._state == _FramerState.WAIT_CHECKSUM and not self._read_checksum():
                break

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _scan_preamble(self) -> bool:
        """Scan for a standard preamble or chlorinator frame start.

        Detects either:
        - Standard Pentair: ``[255, 0, 255, 165]``
        - Chlorinator sub-protocol: ``[16, 2, <valid_dest>, ...]``

        Consumes bytes from ``_buf`` until a valid frame start is found.
        Returns True when we can begin reading a frame.
        """
        # The preamble sequence we look for: 0xFF, 0x00, 0xFF, 0xA5
        preamble_seq = (0xFF, 0x00, 0xFF, 0xA5)

        while self._buf:
            byte = self._buf[0]

            # --- Check for chlorinator frame start [16, 2] ---
            if self._preamble_idx == 0 and byte == _CHLOR_START_0:
                # Might be start of a chlorinator frame; check next byte
                if len(self._buf) >= 2 and self._buf[1] == _CHLOR_START_1:
                    # Validate dest byte if available
                    if len(self._buf) >= 3:
                        dest_byte = self._buf[2]
                        if dest_byte in _CHLOR_VALID_DESTS:
                            # Attempt to parse the full chlorinator frame
                            return self._try_parse_chlorinator_frame()
                        else:
                            # Invalid dest — not a chlorinator frame
                            del self._buf[0]
                            continue
                    else:
                        # Need more data to check dest
                        return False
                elif len(self._buf) < 2:
                    # Need more data to check second byte
                    return False
                # else: second byte is not 0x02, fall through to preamble logic

            # --- Standard preamble detection ---
            expected = preamble_seq[self._preamble_idx]

            if byte == expected:
                self._preamble_idx += 1
                del self._buf[0]
                if self._preamble_idx == len(preamble_seq):
                    # Full preamble found (including 0xA5 start byte)
                    self._preamble_idx = 0
                    self._state = _FramerState.WAIT_HEADER
                    return True
            else:
                # Mismatch - check whether this byte could be the start
                # of a new preamble (0xFF).
                if self._preamble_idx > 0:
                    # Reset but don't consume this byte - it might
                    # be the first 0xFF of a new preamble.
                    self._preamble_idx = 0
                    if byte == 0xFF:
                        self._preamble_idx = 1
                        del self._buf[0]
                    # else: leave byte for next iteration
                    else:
                        del self._buf[0]
                else:
                    # Discard non-preamble byte
                    del self._buf[0]

        return False

    def _try_parse_chlorinator_frame(self) -> bool:
        """Attempt to parse a complete chlorinator sub-protocol frame.

        Expected format: ``[16, 2, dest, action, ...payload..., checksum, 16, 3]``

        Returns True if a complete valid frame was parsed and emitted,
        or if the frame was determined to be invalid (consumed and discarded).
        Returns False if more data is needed.
        """
        # We know buf starts with [16, 2, valid_dest]
        # Minimum frame: [16, 2, dest, action, checksum, 16, 3] = 7 bytes
        if len(self._buf) < 7:
            return False

        dest = self._buf[2]
        action = self._buf[3]

        # Scan for terminator [16, 3] starting after action byte
        # The byte immediately before [16, 3] is the checksum
        # So we look for pattern: [..., checksum_byte, 16, 3]
        # Starting search at index 4 (first possible payload/checksum byte)
        term_idx = None
        # Max frame length: 4 (header) + max_payload + 1 (checksum) + 2 (terminator)
        max_scan = min(len(self._buf), 4 + _CHLOR_MAX_PAYLOAD_LEN + 1 + 2)

        for i in range(4, max_scan - 1):
            if self._buf[i] == _CHLOR_START_0 and self._buf[i + 1] == _CHLOR_TERM_1:
                term_idx = i
                break

        if term_idx is None:
            # Check if we've scanned too far without finding terminator
            if len(self._buf) >= 4 + _CHLOR_MAX_PAYLOAD_LEN + 1 + 2:
                # Frame too long — discard the [16, 2] and move on
                _LOGGER.debug("Chlorinator frame too long — discarding start bytes")
                del self._buf[:2]
                return True  # Continue scanning
            # Need more data
            return False

        # term_idx points to the 16 in [checksum, 16, 3]
        # The checksum byte is at term_idx - 1
        checksum_idx = term_idx - 1
        if checksum_idx < 4:
            # No room for even an empty payload checksum position
            # Malformed — discard
            _LOGGER.debug("Chlorinator frame malformed — no checksum byte")
            del self._buf[:2]
            return True

        # Extract payload (between action and checksum)
        payload = bytes(self._buf[4:checksum_idx])
        received_checksum = self._buf[checksum_idx]

        # Validate checksum: sum of all bytes from first 16 through payload
        computed_checksum = (_CHLOR_START_0 + _CHLOR_START_1 + dest + action + sum(payload)) % 256

        if received_checksum != computed_checksum:
            _LOGGER.debug(
                "Chlorinator checksum mismatch: received=%d, computed=%d — dropping",
                received_checksum,
                computed_checksum,
            )
            # Discard the start bytes and continue scanning
            del self._buf[:2]
            return True

        # Valid chlorinator frame! Consume all bytes through terminator
        frame_end = term_idx + 2  # past the [16, 3]
        del self._buf[:frame_end]

        # Determine source based on dest
        source = CONTROLLER_ADDR if 80 <= dest <= 83 else CHLORINATOR_ADDR_START

        packet = PentairPacket(
            version=0,
            dest=dest,
            source=source,
            action=action,
            payload=payload,
        )

        if self._on_packet:
            self._on_packet(packet)

        return True

    def _read_header(self) -> bool:
        """Read the 5 remaining header bytes (165 already consumed).

        Header layout: [165, sub, dest, src, action, datalen]
        We already consumed 165 in the preamble scan, so we need 5 more.
        """
        remaining = _HEADER_LEN - 1  # 165 was already consumed
        if len(self._buf) < remaining:
            return False

        # Build full header including the 165 start byte
        self._header = bytes([0xA5]) + bytes(self._buf[:remaining])
        del self._buf[:remaining]

        self._datalen = self._header[5]
        if self._datalen > _MAX_DATALEN:
            _LOGGER.debug(
                "Datalen %d exceeds max %d - skipping packet",
                self._datalen,
                _MAX_DATALEN,
            )
            self._state = _FramerState.WAIT_PREAMBLE
            return True  # continue scanning

        self._state = _FramerState.WAIT_PAYLOAD
        return True

    def _read_payload(self) -> bool:
        """Read ``datalen`` payload bytes."""
        if len(self._buf) < self._datalen:
            return False

        self._payload = bytes(self._buf[: self._datalen])
        del self._buf[: self._datalen]

        self._state = _FramerState.WAIT_CHECKSUM
        return True

    def _read_checksum(self) -> bool:
        """Read and validate the 2-byte big-endian checksum."""
        if len(self._buf) < _CHECKSUM_LEN:
            return False

        chk_hi = self._buf[0]
        chk_lo = self._buf[1]
        del self._buf[:_CHECKSUM_LEN]

        received_checksum = (chk_hi << 8) | chk_lo
        computed_checksum = _compute_checksum(self._header, self._payload)

        if received_checksum != computed_checksum:
            _LOGGER.debug(
                "Checksum mismatch: received=%d, computed=%d - dropping packet",
                received_checksum,
                computed_checksum,
            )
            self._state = _FramerState.WAIT_PREAMBLE
            return True  # continue scanning

        # Valid packet!
        packet = PentairPacket(
            version=self._header[1],
            dest=self._header[2],
            source=self._header[3],
            action=self._header[4],
            payload=self._payload,
        )

        self._state = _FramerState.WAIT_PREAMBLE

        if self._on_packet:
            self._on_packet(packet)

        return True


# ---------------------------------------------------------------------------
# Outbound packet builder
# ---------------------------------------------------------------------------


def build_packet(
    dest: int,
    source: int,
    action: int,
    payload: bytes | list[int] = b"",
    version: int = 33,
) -> bytes:
    """Build a complete Pentair RS485 packet ready for transmission.

    Returns the full byte sequence including preamble, header, payload,
    and checksum.

    Parameters
    ----------
    dest:
        Destination address (e.g. 16 for controller).
    source:
        Source address (e.g. 33 for this integration).
    action:
        Action code for the message.
    payload:
        Payload bytes.
    version:
        Protocol version / sub byte.  Use 33 for controller communication
        (EasyTouch standard), 0 for pump/valve/chem sub-protocols.
    """
    if isinstance(payload, list):
        payload = bytes(payload)

    header = bytes([0xA5, version, dest, source, action, len(payload)])
    checksum = _compute_checksum(header, payload)
    chk_hi = (checksum >> 8) & 0xFF
    chk_lo = checksum & 0xFF

    return bytes([0xFF, 0x00, 0xFF]) + header + payload + bytes([chk_hi, chk_lo])


# ---------------------------------------------------------------------------
# Checksum helper
# ---------------------------------------------------------------------------


def _compute_checksum(header: bytes, payload: bytes) -> int:
    """Compute the Pentair packet checksum.

    The checksum is the simple sum of all header bytes plus all payload
    bytes (no modular reduction - it's stored as a 16-bit value).
    """
    return sum(header) + sum(payload)
