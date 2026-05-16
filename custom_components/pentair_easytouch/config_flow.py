"""Config flow for Pentair EasyTouch integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONF_SUPER_CHLOR_HOURS, DEFAULT_SUPER_CHLOR_HOURS, DEFAULT_TCP_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_CONNECTION_TYPE = "connection_type"
CONF_SERIAL_PORT = "serial_port"
CONF_BAUD_RATE = "baud_rate"
CONNECTION_TCP = "tcp"
CONNECTION_SERIAL = "serial"

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TCP): vol.In(
            {CONNECTION_TCP: "TCP / Ethernet", CONNECTION_SERIAL: "Serial / RS-485"}
        ),
    }
)

STEP_TCP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_TCP_PORT): vol.Coerce(int),
    }
)

STEP_SERIAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): str,
        vol.Required(CONF_BAUD_RATE, default=9600): vol.Coerce(int),
    }
)

_CONNECT_TIMEOUT = 5


class PentairEasyTouchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pentair EasyTouch."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._connection_type: str = CONNECTION_TCP

    @staticmethod
    def async_get_options_flow(config_entry):  # noqa: ANN001, ANN205
        """Return the options flow handler."""
        return PentairOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step: choose connection type."""
        if user_input is not None:
            self._connection_type = user_input[CONF_CONNECTION_TYPE]
            if self._connection_type == CONNECTION_TCP:
                return await self.async_step_tcp()
            return await self.async_step_serial()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

    async def async_step_tcp(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle TCP connection configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            error = await self._test_tcp_connection(host, port)
            if error is not None:
                errors["base"] = error
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{host}_{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Pentair EasyTouch ({host}:{port})",
                    data={
                        CONF_CONNECTION_TYPE: CONNECTION_TCP,
                        CONF_HOST: host,
                        CONF_PORT: port,
                    },
                )

        return self.async_show_form(step_id="tcp", data_schema=STEP_TCP_SCHEMA, errors=errors)

    async def async_step_serial(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle serial connection configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            serial_port = user_input[CONF_SERIAL_PORT]
            baud_rate = user_input[CONF_BAUD_RATE]

            error = self._validate_serial_input(serial_port, baud_rate)
            if error is not None:
                errors["base"] = error
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{serial_port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Pentair EasyTouch ({serial_port})",
                    data={
                        CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
                        CONF_SERIAL_PORT: serial_port,
                        CONF_BAUD_RATE: baud_rate,
                    },
                )

        return self.async_show_form(step_id="serial", data_schema=STEP_SERIAL_SCHEMA, errors=errors)

    @staticmethod
    async def _test_tcp_connection(host: str, port: int) -> str | None:
        """Test that we can open a TCP connection to the host.

        Returns an error key on failure, or ``None`` on success.
        """
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=_CONNECT_TIMEOUT
            )
            writer.close()
            await writer.wait_closed()
        except TimeoutError:
            _LOGGER.warning("TCP connection to %s:%d timed out", host, port)
            return "cannot_connect"
        except OSError as exc:
            _LOGGER.warning("TCP connection to %s:%d failed: %s", host, port, exc)
            return "cannot_connect"
        return None

    @staticmethod
    def _validate_serial_input(serial_port: str, baud_rate: int) -> str | None:
        """Validate serial port input values.

        Returns an error key on failure, or ``None`` on success.
        """
        if not serial_port.strip():
            return "invalid_serial_port"
        if baud_rate <= 0:
            return "invalid_baud_rate"
        return None


class PentairOptionsFlowHandler(OptionsFlow):
    """Handle options for Pentair EasyTouch."""

    def __init__(self, config_entry) -> None:  # noqa: ANN001
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_hours = self.config_entry.options.get(
            CONF_SUPER_CHLOR_HOURS, DEFAULT_SUPER_CHLOR_HOURS
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SUPER_CHLOR_HOURS, default=current_hours): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=72)
                    ),
                }
            ),
        )
