"""Tests for protocol constants."""

from custom_components.pentair_easytouch.const import (
    ACTION_CANCEL_DELAY,
    ACTION_DATETIME,
    ACTION_HEAT_STATUS,
    ACTION_INTELLIBRITE,
    ACTION_INTELLICHLOR,
    ACTION_SET_CHLORINATOR,
    ACTION_SET_CIRCUIT,
    ACTION_SET_HEAT_MODE,
    ACTION_SET_HEAT_SETPOINT,
    ACTION_SET_LIGHT_GROUP,
    ACTION_SET_SCHEDULE,
    ACTION_STATUS,
    BROADCAST_ADDR,
    CHLOR_ACTION_MODEL,
    CHLOR_ACTION_SET_OUTPUT,
    CHLOR_ACTION_STATUS,
    CONTROLLER_ADDR,
    DEFAULT_BAUD_RATE,
    DEFAULT_TCP_PORT,
    DOMAIN,
    MSG_START,
    PREAMBLE,
    PUMP_ACTION_STATUS,
    PUMP_ADDR_END,
    PUMP_ADDR_START,
    RECONNECT_BACKOFF_FACTOR,
    RECONNECT_MAX_DELAY,
    RECONNECT_MIN_DELAY,
    REMOTE_ADDR,
)


class TestConstants:
    """Test protocol constants are defined correctly."""

    def test_domain(self) -> None:
        assert DOMAIN == "pentair_easytouch"

    def test_addresses(self) -> None:
        assert BROADCAST_ADDR == 15
        assert CONTROLLER_ADDR == 16
        assert REMOTE_ADDR == 33

    def test_preamble(self) -> None:
        assert bytes([255, 0, 255]) == PREAMBLE
        assert bytes([165]) == MSG_START

    def test_action_codes(self) -> None:
        assert ACTION_STATUS == 2
        assert ACTION_DATETIME == 5
        assert ACTION_HEAT_STATUS == 8
        assert ACTION_INTELLICHLOR == 25
        assert ACTION_INTELLIBRITE == 96
        assert ACTION_CANCEL_DELAY == 131
        assert ACTION_SET_CIRCUIT == 134
        assert ACTION_SET_HEAT_SETPOINT == 136
        assert ACTION_SET_SCHEDULE == 145
        assert ACTION_SET_CHLORINATOR == 153
        assert ACTION_SET_LIGHT_GROUP == 167
        assert ACTION_SET_HEAT_MODE == 168

    def test_pump_addresses(self) -> None:
        assert PUMP_ADDR_START == 96
        assert PUMP_ADDR_END == 111
        assert PUMP_ACTION_STATUS == 7

    def test_chlorinator_actions(self) -> None:
        assert CHLOR_ACTION_MODEL == 3
        assert CHLOR_ACTION_SET_OUTPUT == 17
        assert CHLOR_ACTION_STATUS == 18

    def test_defaults(self) -> None:
        assert DEFAULT_BAUD_RATE == 9600
        assert DEFAULT_TCP_PORT == 9801
        assert RECONNECT_MIN_DELAY == 1.0
        assert RECONNECT_MAX_DELAY == 60.0
        assert RECONNECT_BACKOFF_FACTOR == 2.0
