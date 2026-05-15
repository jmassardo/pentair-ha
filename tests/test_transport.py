"""Tests for the transport abstraction layer."""

import asyncio

import pytest

from custom_components.pentair_easytouch.protocol.transport import (
    BaseTransport,
    TcpTransport,
)


class MockTransport(BaseTransport):
    """A mock transport for testing the base class logic."""

    def __init__(self) -> None:
        super().__init__()
        self._connect_called = 0
        self._disconnect_called = 0
        self._written: list[bytes] = []
        self._read_data: asyncio.Queue[bytes] = asyncio.Queue()
        self._should_fail_connect = False
        self._should_fail_read = False

    async def _do_connect(self) -> None:
        self._connect_called += 1
        if self._should_fail_connect:
            raise ConnectionError("Mock connect failure")

    async def _do_disconnect(self) -> None:
        self._disconnect_called += 1

    async def _do_read(self) -> bytes:
        if self._should_fail_read:
            raise ConnectionError("Mock read failure")
        return await self._read_data.get()

    async def _do_write(self, data: bytes) -> None:
        self._written.append(data)


class TestBaseTransport:
    @pytest.mark.asyncio
    async def test_connect_disconnect(self) -> None:
        transport = MockTransport()
        await transport.connect()
        assert transport.connected is True
        assert transport._connect_called == 1

        await transport.disconnect()
        assert transport.connected is False
        assert transport._disconnect_called == 1

    @pytest.mark.asyncio
    async def test_write_when_connected(self) -> None:
        transport = MockTransport()
        await transport.connect()
        await transport.write(b"\x01\x02\x03")
        assert transport._written == [b"\x01\x02\x03"]
        await transport.disconnect()

    @pytest.mark.asyncio
    async def test_write_when_disconnected_raises(self) -> None:
        transport = MockTransport()
        with pytest.raises(ConnectionError):
            await transport.write(b"\x01")

    @pytest.mark.asyncio
    async def test_data_callback(self) -> None:
        received: list[bytes] = []
        transport = MockTransport()
        transport.set_on_data(received.append)

        await transport.connect()
        transport._read_data.put_nowait(b"\xaa\xbb")

        # Give the read loop a chance to process
        await asyncio.sleep(0.05)

        assert received == [b"\xaa\xbb"]
        await transport.disconnect()

    @pytest.mark.asyncio
    async def test_set_on_data(self) -> None:
        transport = MockTransport()
        cb_called = [False]

        def cb(data: bytes) -> None:
            cb_called[0] = True

        transport.set_on_data(cb)
        await transport.connect()
        transport._read_data.put_nowait(b"\x01")
        await asyncio.sleep(0.05)
        assert cb_called[0] is True
        await transport.disconnect()


class TestTcpTransport:
    def test_init(self) -> None:
        transport = TcpTransport(host="192.168.1.100", port=9801)
        assert transport.connected is False

    def test_init_defaults(self) -> None:
        transport = TcpTransport(host="localhost")
        assert transport._port == 9801

    def test_init_with_callback(self) -> None:
        calls: list[bytes] = []
        transport = TcpTransport(host="localhost", on_data=calls.append)
        assert transport._on_data is not None
