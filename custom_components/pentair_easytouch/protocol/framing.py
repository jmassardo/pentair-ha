"""Packet framing for the Pentair RS485 broadcast protocol.

Implements a byte-level state machine that:

1. Scans incoming bytes for the preamble ``[255, 0, 255]``.
2. Reads the 6-byte header ``[165, sub, dest, src, action, datalen]``.
3. Reads ``datalen`` payload bytes.
4. Validates the 2-byte big-endian checksum (sum of header + payload).
5. Emits complete, validated packets via a callback.

Also provides ``build_packet`` to construct outbound packets.
"""

from __future__ import annotations

import enum
import logging
from collections.abc import Callable
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

# Minimum valid datalen we'll accept (0 is fine for acks)
_MIN_DATALEN = 0
# Maximum sane datalen - the reference code caps at 75
_MAX_DATALEN = 75

# Header is always 6 bytes: [165, sub, dest, src, action, datalen]
_HEADER_LEN = 6
# Checksum is 2 bytes (big-endian)
_CHECKSUM_LEN = 2


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
        """Scan for the preamble ``[255, 0, 255, 165]``.

        Consumes bytes from ``_buf`` until the preamble (including the
        0xA5 start byte) is found.  Returns True when the preamble is
        complete and we can begin reading the header.
        """
        # The preamble sequence we look for: 0xFF, 0x00, 0xFF, 0xA5
        preamble_seq = (0xFF, 0x00, 0xFF, 0xA5)

        while self._buf:
            byte = self._buf[0]
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
    version: int = 1,
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
        Protocol version / sub byte (default 1).
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
