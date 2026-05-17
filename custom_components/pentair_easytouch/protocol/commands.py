"""Outbound command builders for the Pentair EasyTouch RS485 protocol.

Builds and sends control messages to the EasyTouch controller.  Each
public method constructs a payload for a specific action code, wraps it
with ``build_packet()``, and sends it via the transport.

Commands are fire-and-forget: no response matching is performed.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from custom_components.pentair_easytouch.const import (
    ACTION_CANCEL_DELAY,
    ACTION_INTELLIBRITE,
    ACTION_SET_CHLORINATOR,
    ACTION_SET_CIRCUIT,
    ACTION_SET_HEAT_SETPOINT,
    ACTION_SET_SCHEDULE,
    CONTROLLER_ADDR,
    PUMP_ACTION_SET_SPEED,
    PUMP_ADDR_END,
    PUMP_ADDR_START,
    REMOTE_ADDR,
)
from custom_components.pentair_easytouch.protocol.framing import build_packet

# Valid action codes for config requests (ACTION_GET_* range)
_MIN_CONFIG_ACTION = 197
_MAX_CONFIG_ACTION = 253

# Valid item IDs for config requests
_MIN_ITEM_ID = 0
_MAX_ITEM_ID = 255

if TYPE_CHECKING:
    from custom_components.pentair_easytouch.model import PoolState
    from custom_components.pentair_easytouch.protocol.transport import BaseTransport

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------
_MIN_CIRCUIT_ID = 1
_MAX_CIRCUIT_ID = 50

_MIN_BODY_ID = 0
_MAX_BODY_ID = 1

_MIN_HEAT_MODE = 0
_MAX_HEAT_MODE = 3

_MIN_TEMP_F = 40
_MAX_TEMP_F = 104

_MIN_CHLOR_PCT = 0
_MAX_CHLOR_PCT = 100

_MIN_SCHEDULE_ID = 1
_MAX_SCHEDULE_ID = 12

_MIN_DAYS_MASK = 0
_MAX_DAYS_MASK = 0x7F  # Sun-Sat

_MIN_TIME = 0
_MAX_TIME = 1439  # 23:59 in minutes-since-midnight

_MIN_RPM = 450
_MAX_RPM = 3450

_MIN_LIGHT_THEME = 0
_MAX_LIGHT_THEME = 255

# Pump speed sub-command markers (from njsPC pump protocol)
_PUMP_RPM_REGISTER = 196


def _validate_range(value: int, low: int, high: int, name: str) -> None:
    """Raise ``ValueError`` if *value* is outside [low, high]."""
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}, got {value}")


class CommandManager:
    """Builds and sends outbound commands to the EasyTouch controller.

    Parameters
    ----------
    transport:
        An open ``BaseTransport`` instance whose ``write()`` method
        will be called with raw packet bytes.
    source_addr:
        RS-485 source address for outbound packets.  Defaults to
        ``REMOTE_ADDR`` (33).
    """

    def __init__(
        self,
        transport: BaseTransport,
        source_addr: int = REMOTE_ADDR,
        state: PoolState | None = None,
    ) -> None:
        self._transport = transport
        self._source_addr = source_addr
        self._state = state

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_controller_version(self) -> int:
        """Return the version byte learned from the controller, or 33 as default."""
        if self._state and self._state.controller_version_byte:
            return self._state.controller_version_byte
        return 33

    _RETRY_COUNT = 2  # Total of 3 attempts (1 initial + 2 retries)
    _RETRY_DELAY = 1.0  # seconds between retries

    async def _send(
        self,
        action: int,
        payload: list[int],
        dest: int = CONTROLLER_ADDR,
        version: int | None = None,
        retries: int | None = None,
    ) -> None:
        """Build a packet and write it to the transport.

        Retries up to ``retries`` additional times with a delay between
        each attempt to handle RS-485 bus collisions.
        """
        if version is None:
            version = self._get_controller_version()
        if retries is None:
            retries = self._RETRY_COUNT
        packet = build_packet(
            dest=dest,
            source=self._source_addr,
            action=action,
            payload=payload,
            version=version,
        )
        _LOGGER.debug(
            "TX packet: dest=%d action=%d version=%d payload=%s",
            dest, action, version, list(payload),
        )
        await self._transport.write(packet)
        for attempt in range(retries):
            await asyncio.sleep(self._RETRY_DELAY)
            _LOGGER.debug(
                "TX retry %d/%d: action=%d",
                attempt + 1, retries, action,
            )
            await self._transport.write(packet)

    # ------------------------------------------------------------------
    # Config requests
    # ------------------------------------------------------------------

    async def request_config(self, action: int, item_id: int) -> None:
        """Request configuration data from the controller.

        Sends a GET request to the controller for a specific config item.
        The controller responds with the corresponding config broadcast
        (e.g. action 203 → response action 11 for circuit config).

        Parameters
        ----------
        action:
            Config request action code (197-253, e.g.
            ``ACTION_GET_CIRCUITS`` = 203).
        item_id:
            Item identifier to request (0-255, e.g. circuit number 1-20).
        """
        _validate_range(action, _MIN_CONFIG_ACTION, _MAX_CONFIG_ACTION, "action")
        _validate_range(item_id, _MIN_ITEM_ID, _MAX_ITEM_ID, "item_id")
        _LOGGER.debug("CMD request_config action=%d item_id=%d", action, item_id)
        await self._send(action, [item_id], retries=0)

    # ------------------------------------------------------------------
    # Circuit control
    # ------------------------------------------------------------------

    async def set_circuit_state(self, circuit_id: int, state: bool) -> None:
        """Turn a circuit on or off.

        Parameters
        ----------
        circuit_id:
            Circuit number (1-50).
        state:
            ``True`` to turn the circuit on, ``False`` to turn it off.
        """
        _validate_range(circuit_id, _MIN_CIRCUIT_ID, _MAX_CIRCUIT_ID, "circuit_id")
        payload = [circuit_id, 1 if state else 0]
        _LOGGER.debug("CMD set_circuit_state circuit=%d state=%s", circuit_id, state)
        await self._send(ACTION_SET_CIRCUIT, payload)

    # ------------------------------------------------------------------
    # Heat control
    # ------------------------------------------------------------------

    async def set_heat_mode(
        self,
        body_id: int,
        mode: int,
        *,
        current_pool_setpoint: int = 100,
        current_spa_setpoint: int = 100,
        current_pool_mode: int = 0,
        current_spa_mode: int = 0,
        cool_setpoint: int = 0,
    ) -> None:
        """Set the heat mode for a body (pool or spa).

        The EasyTouch protocol requires *both* bodies' setpoints and
        modes in a single packet (action 136).  Pass the current values
        for the body you are **not** changing so they are preserved.

        Parameters
        ----------
        body_id:
            ``0`` for pool, ``1`` for spa.
        mode:
            Heat mode: 0=off, 1=heater, 2=solar preferred, 3=solar only.
        current_pool_setpoint:
            Current pool temperature setpoint (°F).
        current_spa_setpoint:
            Current spa temperature setpoint (°F).
        current_pool_mode:
            Current pool heat mode (0-3).
        current_spa_mode:
            Current spa heat mode (0-3).
        cool_setpoint:
            Cool setpoint for UltraTemp (default 0).
        """
        _validate_range(body_id, _MIN_BODY_ID, _MAX_BODY_ID, "body_id")
        _validate_range(mode, _MIN_HEAT_MODE, _MAX_HEAT_MODE, "mode")

        pool_mode = mode if body_id == 0 else current_pool_mode
        spa_mode = mode if body_id == 1 else current_spa_mode

        mode_byte = (spa_mode << 2) | pool_mode
        payload = [
            current_pool_setpoint,
            current_spa_setpoint,
            mode_byte,
            cool_setpoint,
        ]
        _LOGGER.debug(
            "CMD set_heat_mode body=%d mode=%d payload=%s",
            body_id,
            mode,
            payload,
        )
        # Both heat mode and heat setpoint use action 136 per the EasyTouch
        # protocol -- the controller reads the composite 4-byte payload.
        await self._send(ACTION_SET_HEAT_SETPOINT, payload)

    async def set_heat_setpoint(
        self,
        body_id: int,
        temp: int,
        *,
        current_pool_setpoint: int = 100,
        current_spa_setpoint: int = 100,
        current_pool_mode: int = 0,
        current_spa_mode: int = 0,
        cool_setpoint: int = 0,
    ) -> None:
        """Set the target temperature for a body (pool or spa).

        Like ``set_heat_mode``, the protocol packs both bodies into one
        packet, so current values for the other body must be supplied.

        Parameters
        ----------
        body_id:
            ``0`` for pool, ``1`` for spa.
        temp:
            Target temperature in °F (40-104).
        current_pool_setpoint:
            Current pool temperature setpoint (°F).
        current_spa_setpoint:
            Current spa temperature setpoint (°F).
        current_pool_mode:
            Current pool heat mode (0-3).
        current_spa_mode:
            Current spa heat mode (0-3).
        cool_setpoint:
            Cool setpoint for UltraTemp (default 0).
        """
        _validate_range(body_id, _MIN_BODY_ID, _MAX_BODY_ID, "body_id")
        _validate_range(temp, _MIN_TEMP_F, _MAX_TEMP_F, "temp")

        pool_setpoint = temp if body_id == 0 else current_pool_setpoint
        spa_setpoint = temp if body_id == 1 else current_spa_setpoint

        mode_byte = (current_spa_mode << 2) | current_pool_mode
        payload = [pool_setpoint, spa_setpoint, mode_byte, cool_setpoint]
        _LOGGER.debug(
            "CMD set_heat_setpoint body=%d temp=%d payload=%s",
            body_id,
            temp,
            payload,
        )
        await self._send(ACTION_SET_HEAT_SETPOINT, payload)

    # ------------------------------------------------------------------
    # Light control
    # ------------------------------------------------------------------

    async def set_light_theme(self, theme: int) -> None:
        """Set the IntelliBrite light group theme.

        The EasyTouch protocol broadcasts the theme to *all* lights in
        the light group with action 96.  Individual circuit control is
        done via ``set_circuit_state``.

        Parameters
        ----------
        theme:
            Light theme value (see ``LightTheme`` enum in valuemaps).
        """
        _validate_range(theme, _MIN_LIGHT_THEME, _MAX_LIGHT_THEME, "theme")
        payload = [theme, 0]
        _LOGGER.debug("CMD set_light_theme theme=%d", theme)
        await self._send(ACTION_INTELLIBRITE, payload)

    # ------------------------------------------------------------------
    # Chlorinator control
    # ------------------------------------------------------------------

    async def set_chlorinator(
        self,
        pool_pct: int,
        spa_pct: int,
        *,
        super_chlor_hours: int = 0,
    ) -> None:
        """Set chlorinator output percentages.

        Parameters
        ----------
        pool_pct:
            Pool chlorinator output (0-100 %).
        spa_pct:
            Spa chlorinator output (0-100 %).
        super_chlor_hours:
            Hours for super-chlorination (0 = disabled).
        """
        _validate_range(pool_pct, _MIN_CHLOR_PCT, _MAX_CHLOR_PCT, "pool_pct")
        _validate_range(spa_pct, _MIN_CHLOR_PCT, _MAX_CHLOR_PCT, "spa_pct")
        _validate_range(super_chlor_hours, 0, 72, "super_chlor_hours")

        # Byte 0: (spa_pct << 1) + 1  (the +1 signals "enabled")
        # Byte 1: pool_pct
        # Byte 2: super_chlor_hours + 128 if active, else 0
        byte0 = (spa_pct << 1) + 1
        byte2 = (super_chlor_hours + 128) if super_chlor_hours > 0 else 0
        payload = [byte0, pool_pct, byte2, 0, 0, 0, 0, 0, 0, 0]
        _LOGGER.debug(
            "CMD set_chlorinator pool=%d%% spa=%d%% super_hours=%d",
            pool_pct,
            spa_pct,
            super_chlor_hours,
        )
        await self._send(ACTION_SET_CHLORINATOR, payload)

    # ------------------------------------------------------------------
    # Schedule control
    # ------------------------------------------------------------------

    async def set_schedule(
        self,
        schedule_id: int,
        circuit_id: int,
        start_time: int,
        end_time: int,
        days: int,
    ) -> None:
        """Configure a schedule entry.

        Parameters
        ----------
        schedule_id:
            Schedule slot (1-12).
        circuit_id:
            Circuit to control (1-50).
        start_time:
            Start time in minutes since midnight (0-1439).
        end_time:
            End time in minutes since midnight (0-1439).
        days:
            Day-of-week bitmask (bit 0=Sun .. bit 6=Sat, max 0x7F).
        """
        _validate_range(schedule_id, _MIN_SCHEDULE_ID, _MAX_SCHEDULE_ID, "schedule_id")
        _validate_range(circuit_id, _MIN_CIRCUIT_ID, _MAX_CIRCUIT_ID, "circuit_id")
        _validate_range(start_time, _MIN_TIME, _MAX_TIME, "start_time")
        _validate_range(end_time, _MIN_TIME, _MAX_TIME, "end_time")
        _validate_range(days, _MIN_DAYS_MASK, _MAX_DAYS_MASK, "days")

        start_hr = start_time // 60
        start_min = start_time % 60
        end_hr = end_time // 60
        end_min = end_time % 60

        payload = [schedule_id, circuit_id, start_hr, start_min, end_hr, end_min, days]
        _LOGGER.debug(
            "CMD set_schedule id=%d circuit=%d start=%02d:%02d end=%02d:%02d days=0x%02x",
            schedule_id,
            circuit_id,
            start_hr,
            start_min,
            end_hr,
            end_min,
            days,
        )
        await self._send(ACTION_SET_SCHEDULE, payload)

    # ------------------------------------------------------------------
    # Delay control
    # ------------------------------------------------------------------

    async def cancel_delay(self) -> None:
        """Cancel any active delay."""
        _LOGGER.debug("CMD cancel_delay")
        await self._send(ACTION_CANCEL_DELAY, [0])

    # ------------------------------------------------------------------
    # Pump control (pump mini-protocol)
    # ------------------------------------------------------------------

    async def set_pump_speed(self, pump_address: int, speed_rpm: int) -> None:
        """Set pump speed in RPM via the pump mini-protocol.

        The command is sent directly to the pump address (96-111)
        using action 1 (``PUMP_ACTION_SET_SPEED``).

        Parameters
        ----------
        pump_address:
            Pump RS-485 address (96-111 for pumps 1-16).
        speed_rpm:
            Target speed in RPM (450-3450).  Use 0 to stop.
        """
        _validate_range(pump_address, PUMP_ADDR_START, PUMP_ADDR_END, "pump_address")
        if speed_rpm != 0:
            _validate_range(speed_rpm, _MIN_RPM, _MAX_RPM, "speed_rpm")

        rpm_hi = (speed_rpm >> 8) & 0xFF
        rpm_lo = speed_rpm & 0xFF
        payload = [2, _PUMP_RPM_REGISTER, rpm_hi, rpm_lo]
        _LOGGER.debug(
            "CMD set_pump_speed addr=%d rpm=%d",
            pump_address,
            speed_rpm,
        )
        await self._send(PUMP_ACTION_SET_SPEED, payload, dest=pump_address, version=0)
