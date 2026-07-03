"""Tests for Pentair EasyTouch config flow."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.pentair_easytouch.config_flow import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_TYPE,
    CONF_SERIAL_PORT,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    PentairEasyTouchConfigFlow,
    PentairOptionsFlowHandler,
)
from custom_components.pentair_easytouch.const import (
    CONF_SUPER_CHLOR_HOURS,
    DEFAULT_SUPER_CHLOR_HOURS,
    DEFAULT_TCP_PORT,
    DOMAIN,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flow() -> PentairEasyTouchConfigFlow:
    """Create a config flow instance with mocked hass."""
    flow = PentairEasyTouchConfigFlow()
    flow.hass = MagicMock()
    # Mock async_set_unique_id and _abort_if_unique_id_configured
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    return flow


# ---------------------------------------------------------------------------
# User step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_shows_form() -> None:
    """User step with no input shows the connection type form."""
    flow = _make_flow()
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_user_step_tcp_forwards_to_tcp_step() -> None:
    """Selecting TCP forwards to the tcp step."""
    flow = _make_flow()

    with patch.object(flow, "async_step_tcp", new_callable=AsyncMock) as mock_tcp:
        mock_tcp.return_value = {"type": "form", "step_id": "tcp"}
        result = await flow.async_step_user({CONF_CONNECTION_TYPE: CONNECTION_TCP})

    mock_tcp.assert_awaited_once()
    assert result["step_id"] == "tcp"


@pytest.mark.asyncio
async def test_user_step_serial_forwards_to_serial_step() -> None:
    """Selecting serial forwards to the serial step."""
    flow = _make_flow()

    with patch.object(flow, "async_step_serial", new_callable=AsyncMock) as mock_serial:
        mock_serial.return_value = {"type": "form", "step_id": "serial"}
        result = await flow.async_step_user({CONF_CONNECTION_TYPE: CONNECTION_SERIAL})

    mock_serial.assert_awaited_once()
    assert result["step_id"] == "serial"


# ---------------------------------------------------------------------------
# TCP step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tcp_step_shows_form() -> None:
    """TCP step with no input shows the form."""
    flow = _make_flow()
    result = await flow.async_step_tcp(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "tcp"


@pytest.mark.asyncio
async def test_tcp_step_success() -> None:
    """TCP step creates entry on successful connection."""
    flow = _make_flow()

    with patch.object(flow, "_test_tcp_connection", return_value=None):
        result = await flow.async_step_tcp({"host": "192.168.1.100", "port": 9801})

    assert result["type"] == "create_entry"
    assert result["title"] == "Pentair EasyTouch (192.168.1.100:9801)"
    assert result["data"] == {
        CONF_CONNECTION_TYPE: CONNECTION_TCP,
        "host": "192.168.1.100",
        "port": 9801,
    }


@pytest.mark.asyncio
async def test_tcp_step_connection_failure() -> None:
    """TCP step shows error when connection fails."""
    flow = _make_flow()

    with patch.object(flow, "_test_tcp_connection", return_value="cannot_connect"):
        result = await flow.async_step_tcp({"host": "badhost", "port": 9801})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


# ---------------------------------------------------------------------------
# Serial step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_serial_step_shows_form() -> None:
    """Serial step with no input shows the form."""
    flow = _make_flow()
    result = await flow.async_step_serial(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "serial"


@pytest.mark.asyncio
async def test_serial_step_success() -> None:
    """Serial step creates entry on valid input."""
    flow = _make_flow()
    result = await flow.async_step_serial(
        {CONF_SERIAL_PORT: "/dev/ttyUSB0", CONF_BAUD_RATE: 9600}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Pentair EasyTouch (/dev/ttyUSB0)"
    assert result["data"] == {
        CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUD_RATE: 9600,
    }


@pytest.mark.asyncio
async def test_serial_step_empty_port() -> None:
    """Serial step rejects empty port."""
    flow = _make_flow()
    result = await flow.async_step_serial({CONF_SERIAL_PORT: "  ", CONF_BAUD_RATE: 9600})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_serial_port"}


@pytest.mark.asyncio
async def test_serial_step_invalid_baud() -> None:
    """Serial step rejects invalid baud rate."""
    flow = _make_flow()
    result = await flow.async_step_serial({CONF_SERIAL_PORT: "/dev/ttyUSB0", CONF_BAUD_RATE: 0})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_baud_rate"}


# ---------------------------------------------------------------------------
# TCP connection test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_tcp_connection_success() -> None:
    """_test_tcp_connection returns None on success."""
    writer = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_open:
        mock_open.return_value = (MagicMock(), writer)
        result = await PentairEasyTouchConfigFlow._test_tcp_connection("localhost", 9801)

    assert result is None
    writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_test_tcp_connection_timeout() -> None:
    """_test_tcp_connection returns error on timeout."""
    with patch("asyncio.open_connection", side_effect=asyncio.TimeoutError):
        # Patch wait_for to raise TimeoutError directly
        with patch("asyncio.wait_for", side_effect=TimeoutError):
            result = await PentairEasyTouchConfigFlow._test_tcp_connection("badhost", 9801)

    assert result == "cannot_connect"


@pytest.mark.asyncio
async def test_test_tcp_connection_refused() -> None:
    """_test_tcp_connection returns error on connection refused."""
    with patch("asyncio.wait_for", side_effect=OSError("Connection refused")):
        result = await PentairEasyTouchConfigFlow._test_tcp_connection("localhost", 1234)

    assert result == "cannot_connect"


# ---------------------------------------------------------------------------
# Serial validation
# ---------------------------------------------------------------------------


def test_validate_serial_input_valid() -> None:
    """Valid input passes validation."""
    assert PentairEasyTouchConfigFlow._validate_serial_input("/dev/ttyUSB0", 9600) is None


def test_validate_serial_input_empty_port() -> None:
    """Empty port fails validation."""
    assert PentairEasyTouchConfigFlow._validate_serial_input("", 9600) == "invalid_serial_port"


def test_validate_serial_input_zero_baud() -> None:
    """Zero baud rate fails validation."""
    assert PentairEasyTouchConfigFlow._validate_serial_input("/dev/tty0", 0) == "invalid_baud_rate"


def test_validate_serial_input_negative_baud() -> None:
    """Negative baud rate fails validation."""
    assert PentairEasyTouchConfigFlow._validate_serial_input("/dev/tty0", -1) == "invalid_baud_rate"


# ---------------------------------------------------------------------------
# Reconfigure steps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconfigure_tcp_shows_form() -> None:
    """Reconfigure TCP step shows form with current values."""
    flow = _make_flow()
    entry = MagicMock()
    entry.data = {
        CONF_CONNECTION_TYPE: CONNECTION_TCP,
        "host": "192.168.1.50",
        "port": 9801,
    }
    flow.context = {"entry_id": "test_entry"}
    flow.hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    result = await flow.async_step_reconfigure_tcp(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure_tcp"


@pytest.mark.asyncio
async def test_reconfigure_tcp_success() -> None:
    """Reconfigure TCP updates entry and triggers reload."""
    flow = _make_flow()
    entry = MagicMock()
    entry.data = {
        CONF_CONNECTION_TYPE: CONNECTION_TCP,
        "host": "192.168.1.50",
        "port": 9801,
    }
    flow.context = {"entry_id": "test_entry"}
    flow.hass.config_entries.async_get_entry = MagicMock(return_value=entry)
    flow.async_update_reload_and_abort = MagicMock(return_value={"type": "abort"})

    with patch.object(flow, "_test_tcp_connection", return_value=None):
        result = await flow.async_step_reconfigure_tcp({"host": "10.0.0.1", "port": 9802})

    flow.async_update_reload_and_abort.assert_called_once()
    call_kwargs = flow.async_update_reload_and_abort.call_args
    assert call_kwargs[1]["data"]["host"] == "10.0.0.1"
    assert call_kwargs[1]["data"]["port"] == 9802


@pytest.mark.asyncio
async def test_reconfigure_tcp_failure() -> None:
    """Reconfigure TCP shows error on connection failure."""
    flow = _make_flow()
    entry = MagicMock()
    entry.data = {CONF_CONNECTION_TYPE: CONNECTION_TCP, "host": "old", "port": 9801}
    flow.context = {"entry_id": "test_entry"}
    flow.hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    with patch.object(flow, "_test_tcp_connection", return_value="cannot_connect"):
        result = await flow.async_step_reconfigure_tcp({"host": "bad", "port": 9801})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_reconfigure_serial_shows_form() -> None:
    """Reconfigure serial step shows form with current values."""
    flow = _make_flow()
    entry = MagicMock()
    entry.data = {
        CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUD_RATE: 9600,
    }
    flow.context = {"entry_id": "test_entry"}
    flow.hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    result = await flow.async_step_reconfigure_serial(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure_serial"


@pytest.mark.asyncio
async def test_reconfigure_serial_success() -> None:
    """Reconfigure serial updates entry and triggers reload."""
    flow = _make_flow()
    entry = MagicMock()
    entry.data = {
        CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUD_RATE: 9600,
    }
    flow.context = {"entry_id": "test_entry"}
    flow.hass.config_entries.async_get_entry = MagicMock(return_value=entry)
    flow.async_update_reload_and_abort = MagicMock(return_value={"type": "abort"})

    result = await flow.async_step_reconfigure_serial(
        {CONF_SERIAL_PORT: "/dev/ttyUSB1", CONF_BAUD_RATE: 19200}
    )

    flow.async_update_reload_and_abort.assert_called_once()
    call_kwargs = flow.async_update_reload_and_abort.call_args
    assert call_kwargs[1]["data"][CONF_SERIAL_PORT] == "/dev/ttyUSB1"
    assert call_kwargs[1]["data"][CONF_BAUD_RATE] == 19200


@pytest.mark.asyncio
async def test_reconfigure_serial_invalid() -> None:
    """Reconfigure serial shows error on invalid input."""
    flow = _make_flow()
    entry = MagicMock()
    entry.data = {
        CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUD_RATE: 9600,
    }
    flow.context = {"entry_id": "test_entry"}
    flow.hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    result = await flow.async_step_reconfigure_serial(
        {CONF_SERIAL_PORT: "", CONF_BAUD_RATE: 9600}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_serial_port"}


@pytest.mark.asyncio
async def test_reconfigure_dispatches_to_tcp() -> None:
    """async_step_reconfigure dispatches to TCP step for TCP entries."""
    flow = _make_flow()
    entry = MagicMock()
    entry.data = {CONF_CONNECTION_TYPE: CONNECTION_TCP, "host": "h", "port": 9801}
    flow.context = {"entry_id": "test_entry"}
    flow.hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    with patch.object(flow, "async_step_reconfigure_tcp", new_callable=AsyncMock) as mock_tcp:
        mock_tcp.return_value = {"type": "form", "step_id": "reconfigure_tcp"}
        result = await flow.async_step_reconfigure()

    mock_tcp.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconfigure_dispatches_to_serial() -> None:
    """async_step_reconfigure dispatches to serial step for serial entries."""
    flow = _make_flow()
    entry = MagicMock()
    entry.data = {
        CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUD_RATE: 9600,
    }
    flow.context = {"entry_id": "test_entry"}
    flow.hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    with patch.object(
        flow, "async_step_reconfigure_serial", new_callable=AsyncMock
    ) as mock_serial:
        mock_serial.return_value = {"type": "form", "step_id": "reconfigure_serial"}
        result = await flow.async_step_reconfigure()

    mock_serial.assert_awaited_once()


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


def _make_options_handler(options: dict) -> PentairOptionsFlowHandler:
    """Create an options handler with a mocked config_entry."""
    handler = PentairOptionsFlowHandler.__new__(PentairOptionsFlowHandler)
    entry = MagicMock()
    entry.options = options
    # OptionsFlow.config_entry uses self.handler as entry_id and looks it up
    # via hass.config_entries.async_get_known_entry(self.handler)
    handler.handler = "test_entry"
    handler.hass = MagicMock()
    handler.hass.config_entries.async_get_known_entry = MagicMock(return_value=entry)
    return handler


@pytest.mark.asyncio
async def test_options_flow_shows_form() -> None:
    """Options flow shows form with current values."""
    handler = _make_options_handler({CONF_SUPER_CHLOR_HOURS: 8})

    result = await handler.async_step_init(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_options_flow_saves() -> None:
    """Options flow saves new values."""
    handler = _make_options_handler({CONF_SUPER_CHLOR_HOURS: 8})

    result = await handler.async_step_init({CONF_SUPER_CHLOR_HOURS: 12})

    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_SUPER_CHLOR_HOURS: 12}


@pytest.mark.asyncio
async def test_options_flow_uses_default_when_no_option_set() -> None:
    """Options flow uses default when no option is currently set."""
    handler = _make_options_handler({})

    result = await handler.async_step_init(user_input=None)

    assert result["type"] == "form"


def test_async_get_options_flow_returns_handler() -> None:
    """async_get_options_flow returns PentairOptionsFlowHandler."""
    entry = MagicMock()
    handler = PentairEasyTouchConfigFlow.async_get_options_flow(entry)
    assert isinstance(handler, PentairOptionsFlowHandler)
