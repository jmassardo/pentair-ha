"""Async transport abstraction for TCP and serial RS485 connections.

Provides ``TcpTransport`` and ``SerialTransport`` as concrete
implementations of ``BaseTransport``.  Both deliver raw bytes to a
callback and support auto-reconnection with exponential backoff.

This module has **no** Home Assistant dependency.
"""

from __future__ import annotations

import abc
import asyncio
import contextlib
import logging
from collections.abc import Callable

from custom_components.pentair_easytouch.const import (
    DEFAULT_BAUD_RATE,
    DEFAULT_TCP_PORT,
    RECONNECT_BACKOFF_FACTOR,
    RECONNECT_MAX_DELAY,
    RECONNECT_MIN_DELAY,
)

_LOGGER = logging.getLogger(__name__)

OnDataCallback = Callable[[bytes], None]


class BaseTransport(abc.ABC):
    """Abstract async transport that delivers raw byte chunks via a callback."""

    def __init__(self, on_data: OnDataCallback | None = None) -> None:
        self._on_data: OnDataCallback | None = on_data
        self._connected: bool = False
        self._reconnect_task: asyncio.Task[None] | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._retry_delay: float = RECONNECT_MIN_DELAY

    @property
    def connected(self) -> bool:
        """Return True when the underlying transport is open."""
        return self._connected

    def set_on_data(self, callback: OnDataCallback) -> None:
        """Set (or replace) the data callback."""
        self._on_data = callback

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the transport.  May raise on first attempt."""
        self._stop_event.clear()
        await self._do_connect()
        self._connected = True
        self._retry_delay = RECONNECT_MIN_DELAY
        self._read_task = asyncio.ensure_future(self._read_loop())

    async def disconnect(self) -> None:
        """Close the transport and cancel background tasks."""
        self._stop_event.set()
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None

        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._read_task
            self._read_task = None

        await self._do_disconnect()
        self._connected = False

    async def write(self, data: bytes) -> None:
        """Write raw bytes to the transport.

        Raises ``ConnectionError`` if not connected.
        """
        if not self._connected:
            raise ConnectionError("Transport is not connected")
        await self._do_write(data)

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def _do_connect(self) -> None: ...

    @abc.abstractmethod
    async def _do_disconnect(self) -> None: ...

    @abc.abstractmethod
    async def _do_read(self) -> bytes:
        """Return at least 1 byte, or raise on failure."""
        ...

    @abc.abstractmethod
    async def _do_write(self, data: bytes) -> None: ...

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _read_loop(self) -> None:
        """Continuously read data and deliver to the callback."""
        try:
            while not self._stop_event.is_set():
                try:
                    data = await self._do_read()
                    if not data:
                        # EOF / connection closed by remote
                        _LOGGER.warning("Transport read returned empty - connection lost")
                        break
                    if self._on_data:
                        self._on_data(data)
                except (OSError, ConnectionError) as exc:
                    if self._stop_event.is_set():
                        return
                    _LOGGER.warning("Transport read error: %s", exc)
                    break
                except asyncio.CancelledError:
                    return
        finally:
            self._connected = False

        # Connection lost - attempt reconnect unless we were told to stop
        if not self._stop_event.is_set():
            self._reconnect_task = asyncio.ensure_future(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Reconnect with exponential backoff."""
        while not self._stop_event.is_set():
            _LOGGER.info(
                "Reconnecting in %.1f seconds …",
                self._retry_delay,
            )
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._retry_delay)
                # stop_event was set - exit
                return
            except TimeoutError:
                pass

            try:
                await self._do_connect()
                self._connected = True
                self._retry_delay = RECONNECT_MIN_DELAY
                _LOGGER.info("Reconnected successfully")
                self._read_task = asyncio.ensure_future(self._read_loop())
                return
            except (OSError, ConnectionError) as exc:
                _LOGGER.warning("Reconnect failed: %s", exc)
                self._retry_delay = min(
                    self._retry_delay * RECONNECT_BACKOFF_FACTOR,
                    RECONNECT_MAX_DELAY,
                )
            except asyncio.CancelledError:
                return


# ---------------------------------------------------------------------------
# TCP transport
# ---------------------------------------------------------------------------


class TcpTransport(BaseTransport):
    """Async TCP transport for Pentair RS485-to-Ethernet adapters.

    Typical usage with a ``socat`` bridge listening on port 9801.
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_TCP_PORT,
        on_data: OnDataCallback | None = None,
    ) -> None:
        super().__init__(on_data)
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def _do_connect(self) -> None:
        _LOGGER.debug("TCP connecting to %s:%d", self._host, self._port)
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        _LOGGER.info("TCP connected to %s:%d", self._host, self._port)

    async def _do_disconnect(self) -> None:
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except OSError:
                pass
            self._writer = None
        self._reader = None

    async def _do_read(self) -> bytes:
        if self._reader is None:
            raise ConnectionError("TCP reader not available")
        data = await self._reader.read(1024)
        return data

    async def _do_write(self, data: bytes) -> None:
        if self._writer is None:
            raise ConnectionError("TCP writer not available")
        self._writer.write(data)
        await self._writer.drain()


# ---------------------------------------------------------------------------
# Serial transport
# ---------------------------------------------------------------------------


class SerialTransport(BaseTransport):
    """Async serial transport for direct RS485 connections.

    Requires ``pyserial-asyncio`` (``serial_asyncio``).
    """

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUD_RATE,
        on_data: OnDataCallback | None = None,
    ) -> None:
        super().__init__(on_data)
        self._port = port
        self._baudrate = baudrate
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def _do_connect(self) -> None:
        # Import lazily so the module loads without pyserial-asyncio installed
        # (e.g. when only TCP is used).
        import serial_asyncio as _serial_asyncio

        _LOGGER.debug("Serial opening %s @ %d baud", self._port, self._baudrate)
        self._reader, self._writer = await _serial_asyncio.open_serial_connection(
            url=self._port,
            baudrate=self._baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
        )
        _LOGGER.info("Serial opened %s @ %d baud", self._port, self._baudrate)

    async def _do_disconnect(self) -> None:
        if self._writer:
            try:
                self._writer.close()
                # serial_asyncio writers may not have wait_closed
                if hasattr(self._writer, "wait_closed"):
                    await self._writer.wait_closed()
            except OSError:
                pass
            self._writer = None
        self._reader = None

    async def _do_read(self) -> bytes:
        if self._reader is None:
            raise ConnectionError("Serial reader not available")
        data = await self._reader.read(1024)
        return data

    async def _do_write(self, data: bytes) -> None:
        if self._writer is None:
            raise ConnectionError("Serial writer not available")
        self._writer.write(data)
        await self._writer.drain()
