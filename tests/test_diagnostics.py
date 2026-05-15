"""Tests for the diagnostics platform."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.pentair_easytouch.const import DOMAIN
from custom_components.pentair_easytouch.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)
from custom_components.pentair_easytouch.model import (
    Chlorinator,
    Circuit,
    PoolBody,
    PoolState,
    Pump,
    TemperatureState,
)


def _make_config_entry(data: dict[str, Any] | None = None) -> MagicMock:
    """Create a mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry_data = data or {
        "connection_type": "tcp",
        "host": "192.168.1.100",
        "port": 9801,
    }
    entry.data = entry_data
    entry.as_dict.return_value = {
        "entry_id": "test_entry_id",
        "domain": DOMAIN,
        "title": "Pentair EasyTouch (192.168.1.100:9801)",
        "data": entry_data,
        "options": {},
    }
    return entry


def _make_hass(coordinator: MagicMock) -> MagicMock:
    """Create a mock HomeAssistant object with the coordinator stored in hass.data."""
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    return hass


class TestDiagnostics:
    """Tests for async_get_config_entry_diagnostics."""

    @pytest.mark.asyncio
    async def test_diagnostics_with_pool_state(self) -> None:
        """Diagnostics should include full pool state when coordinator has data."""
        state = PoolState(
            bodies=[PoolBody(id=0, name="Pool", temp=82, is_on=True)],
            circuits=[Circuit(id=1, name="Spa", is_on=False)],
            pumps=[Pump(id=1, name="Main", rpm=2500, watts=300)],
            chlorinators=[Chlorinator(id=1, salt_level=3200, pool_setpoint=50)],
            temps=TemperatureState(air=95, water_sensor1=82),
        )

        coordinator = MagicMock()
        coordinator.data = state

        hass = _make_hass(coordinator)
        entry = _make_config_entry()

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert "config_entry" in result
        assert "pool_state" in result
        assert result["pool_state"] is not None

        # Verify pool state was serialised via asdict
        assert result["pool_state"] == asdict(state)

        # Verify connection details are redacted
        config_data = result["config_entry"]["data"]
        assert config_data["host"] == "**REDACTED**"
        assert config_data["port"] == 9801  # port is not redacted

    @pytest.mark.asyncio
    async def test_diagnostics_with_none_data(self) -> None:
        """Diagnostics should handle coordinator.data being None."""
        coordinator = MagicMock()
        coordinator.data = None

        hass = _make_hass(coordinator)
        entry = _make_config_entry()

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["pool_state"] is None
        assert "config_entry" in result

    @pytest.mark.asyncio
    async def test_diagnostics_redacts_serial_port(self) -> None:
        """Diagnostics should redact serial_port for serial connections."""
        coordinator = MagicMock()
        coordinator.data = PoolState()

        entry = _make_config_entry(
            data={
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0",
                "baud_rate": 9600,
            }
        )
        entry.as_dict.return_value = {
            "entry_id": "test_entry_id",
            "domain": DOMAIN,
            "title": "Pentair EasyTouch (/dev/ttyUSB0)",
            "data": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0",
                "baud_rate": 9600,
            },
            "options": {},
        }

        hass = _make_hass(coordinator)

        result = await async_get_config_entry_diagnostics(hass, entry)

        config_data = result["config_entry"]["data"]
        assert config_data["serial_port"] == "**REDACTED**"
        assert config_data["baud_rate"] == 9600  # baud_rate is not redacted

    def test_to_redact_keys(self) -> None:
        """TO_REDACT should contain expected keys."""
        assert "host" in TO_REDACT
        assert "serial_port" in TO_REDACT
