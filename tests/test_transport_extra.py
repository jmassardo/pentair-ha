"""Additional tests for transport reconnect paths."""

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pentair_easytouch.protocol.transport import (
    RECONNECT_MIN_DELAY,
    BaseTransport,
    SerialTransport,
    TcpTransport,
)


class ReconnectMockTransport(BaseTransport):
    def __init__(self) -> None:
        super().__init__()
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.fail_connect_times = 0
        self.raise_read_error = False
        self.stop_before_read_error = False
        self.read_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def _do_connect(self) -> None:
        self.connect_calls += 1
        if self.fail_connect_times:
            self.fail_connect_times -= 1
            raise ConnectionError("connect failed")

    async def _do_disconnect(self) -> None:
        self.disconnect_calls += 1

    async def _do_read(self) -> bytes:
        if self.raise_read_error:
            if self.stop_before_read_error:
                self._stop_event.set()
            raise ConnectionError("read failed")
        return await self.read_queue.get()

    async def _do_write(self, data: bytes) -> None:
        return None


@pytest.mark.asyncio
async def test_read_loop_empty_data_starts_reconnect() -> None:
    transport = ReconnectMockTransport()
    await transport.connect()

    transport.read_queue.put_nowait(b"")
    await asyncio.sleep(0.05)

    assert transport.connected is False
    assert transport._reconnect_task is not None

    await transport.disconnect()


@pytest.mark.asyncio
async def test_read_loop_error_starts_reconnect() -> None:
    transport = ReconnectMockTransport()
    transport.raise_read_error = True
    await transport.connect()

    await asyncio.sleep(0.05)

    assert transport.connected is False
    assert transport._reconnect_task is not None

    await transport.disconnect()


@pytest.mark.asyncio
async def test_read_loop_error_with_stop_event_does_not_reconnect() -> None:
    transport = ReconnectMockTransport()
    transport.raise_read_error = True
    transport.stop_before_read_error = True
    await transport.connect()

    await asyncio.sleep(0.05)

    assert transport.connected is False
    assert transport._reconnect_task is None

    await transport.disconnect()


@pytest.mark.asyncio
async def test_reconnect_loop_recovers_and_restarts_reading() -> None:
    transport = ReconnectMockTransport()
    transport._retry_delay = 0.01

    await transport._reconnect_loop()

    assert transport.connect_calls == 1
    assert transport.connected is True
    assert transport._retry_delay == RECONNECT_MIN_DELAY
    assert transport._read_task is not None

    await transport.disconnect()


@pytest.mark.asyncio
async def test_reconnect_loop_backs_off_after_failure() -> None:
    transport = ReconnectMockTransport()
    transport.fail_connect_times = 1
    transport._retry_delay = 0.01

    task = asyncio.create_task(transport._reconnect_loop())
    await asyncio.sleep(0.03)
    transport._stop_event.set()
    await task

    assert transport.connect_calls >= 1
    assert transport._retry_delay > 0.01


@pytest.mark.asyncio
async def test_tcp_transport_do_methods() -> None:
    reader = MagicMock()
    reader.read = AsyncMock(return_value=b"abc")
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()

    transport = TcpTransport(host="localhost")
    transport._reader = reader
    transport._writer = writer

    assert await transport._do_read() == b"abc"

    await transport._do_write(b"123")
    writer.write.assert_called_once_with(b"123")
    writer.drain.assert_awaited_once()

    await transport._do_disconnect()
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()
    assert transport._reader is None
    assert transport._writer is None


@pytest.mark.asyncio
async def test_tcp_transport_raises_without_reader_or_writer() -> None:
    transport = TcpTransport(host="localhost")

    with pytest.raises(ConnectionError):
        await transport._do_read()

    with pytest.raises(ConnectionError):
        await transport._do_write(b"123")


@pytest.mark.asyncio
async def test_tcp_transport_connect_uses_open_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = MagicMock()
    writer = MagicMock()

    async def fake_open_connection(host: str, port: int) -> tuple[MagicMock, MagicMock]:
        assert host == "pool-controller"
        assert port == 9801
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)

    transport = TcpTransport(host="pool-controller")
    await transport._do_connect()

    assert transport._reader is reader
    assert transport._writer is writer


@pytest.mark.asyncio
async def test_serial_transport_do_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = MagicMock()
    reader.read = AsyncMock(return_value=b"xyz")
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()

    async def fake_open_serial_connection(**kwargs: object) -> tuple[MagicMock, MagicMock]:
        assert kwargs["url"] == "/dev/ttyUSB0"
        assert kwargs["baudrate"] == 9600
        return reader, writer

    monkeypatch.setitem(
        sys.modules,
        "serial_asyncio",
        SimpleNamespace(open_serial_connection=fake_open_serial_connection),
    )

    transport = SerialTransport(port="/dev/ttyUSB0")
    await transport._do_connect()
    assert transport._reader is reader
    assert transport._writer is writer
    assert await transport._do_read() == b"xyz"

    await transport._do_write(b"123")
    writer.write.assert_called_once_with(b"123")
    writer.drain.assert_awaited_once()

    await transport._do_disconnect()
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
async def test_serial_transport_handles_missing_wait_closed_and_unset_io() -> None:
    class WriterWithoutWaitClosed:
        def __init__(self) -> None:
            self.closed = False
            self.writes: list[bytes] = []

        def close(self) -> None:
            self.closed = True

        def write(self, data: bytes) -> None:
            self.writes.append(data)

        async def drain(self) -> None:
            return None

    transport = SerialTransport(port="/dev/ttyUSB0")

    with pytest.raises(ConnectionError):
        await transport._do_read()

    with pytest.raises(ConnectionError):
        await transport._do_write(b"123")

    writer = WriterWithoutWaitClosed()
    transport._writer = writer
    await transport._do_disconnect()

    assert writer.closed is True
    assert transport._reader is None
    assert transport._writer is None
