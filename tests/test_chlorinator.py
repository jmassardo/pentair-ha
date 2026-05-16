"""Tests for chlorinator decode."""

from custom_components.pentair_easytouch.model import PoolState
from custom_components.pentair_easytouch.protocol.chlorinator import (
    decode_chlorinator_action,
    decode_chlorinator_broadcast,
)


class TestDecodeChlorinatorBroadcast:
    """Test Action 25 chlorinator broadcast decode."""

    def test_basic_decode(self) -> None:
        state = PoolState()
        # byte[0] = (spa_setpoint << 1) | active_flag = (30 << 1) | 1 = 61
        # byte[1] = pool_setpoint = 50
        payload = bytes([61, 50, 0, 0, 0, 0])
        decode_chlorinator_broadcast(payload, state)

        chlor = state.get_chlorinator(1)
        assert chlor.is_active is True
        assert chlor.pool_setpoint == 50
        assert chlor.spa_setpoint == 30
        assert chlor.super_chlor is False

    def test_super_chlor(self) -> None:
        state = PoolState()
        # byte[0] = (30 << 1) | 1 = 61, byte[1] = 50, byte[5] = 8 (hours)
        payload = bytes([61, 50, 0, 0, 0, 8])
        decode_chlorinator_broadcast(payload, state)

        chlor = state.get_chlorinator(1)
        assert chlor.super_chlor is True
        assert chlor.super_chlor_hours == 8

    def test_status(self) -> None:
        state = PoolState()
        # byte[4] = status = 0x82, high bit stripped → 0x02
        payload = bytes([61, 50, 0, 0, 0x82, 0])
        decode_chlorinator_broadcast(payload, state)

        chlor = state.get_chlorinator(1)
        assert chlor.status == 0x02  # high bit stripped (& 0x7F)

    def test_short_payload(self) -> None:
        state = PoolState()
        decode_chlorinator_broadcast(bytes(1), state)
        # Should not crash


class TestDecodeChlorinatorAction:
    """Test chlorinator sub-protocol action decode."""

    def test_action_3_model(self) -> None:
        state = PoolState()
        # Action 3: model name (address byte + 16 ASCII chars)
        name_bytes = b"Intellichlor--40"
        payload = bytes([0]) + name_bytes
        decode_chlorinator_action(3, payload, dest=0, state=state)

        chlor = state.get_chlorinator(1)
        assert chlor.name == "Intellichlor--40"
        assert chlor.is_active is True

    def test_action_3_no_overwrite_name(self) -> None:
        state = PoolState()
        chlor = state.get_chlorinator(1)
        chlor.name = "My Chlorinator"
        payload = bytes([0]) + b"Intellichlor--40"
        decode_chlorinator_action(3, payload, dest=0, state=state)
        assert chlor.name == "My Chlorinator"  # not overwritten

    def test_action_17_set_output(self) -> None:
        state = PoolState()
        payload = bytes([50])  # 50%
        decode_chlorinator_action(17, payload, dest=80, state=state)

        chlor = state.get_chlorinator(1)
        assert chlor.target_output == 50

    def test_action_18_salt_and_status(self) -> None:
        state = PoolState()
        payload = bytes([60, 0x04])  # salt = 60*50 = 3000, status = 4
        decode_chlorinator_action(18, payload, dest=0, state=state)

        chlor = state.get_chlorinator(1)
        assert chlor.salt_level == 3000
        assert chlor.status == 4
        assert chlor.is_active is True

    def test_action_18_zero_salt_preserved(self) -> None:
        """Salt level of 0 should not overwrite existing value."""
        state = PoolState()
        chlor = state.get_chlorinator(1)
        chlor.salt_level = 3200
        payload = bytes([0, 0])
        decode_chlorinator_action(18, payload, dest=0, state=state)
        assert chlor.salt_level == 3200  # preserved

    def test_action_20_model_type(self) -> None:
        state = PoolState()
        payload = bytes([2])  # model type
        decode_chlorinator_action(20, payload, dest=80, state=state)

        chlor = state.get_chlorinator(1)
        assert chlor.model == 2

    def test_action_21_fractional_output(self) -> None:
        state = PoolState()
        payload = bytes([15])  # 15/10 = 1.5% -> int = 1
        decode_chlorinator_action(21, payload, dest=80, state=state)

        chlor = state.get_chlorinator(1)
        assert chlor.target_output == 1

    def test_action_22_ichlor_output(self) -> None:
        state = PoolState()
        payload = bytes([0, 15, 73, 0, 5])
        decode_chlorinator_action(22, payload, dest=0, state=state)

        chlor = state.get_chlorinator(1)
        assert chlor.current_output == 15
        assert chlor.is_active is True

    def test_control_actions(self) -> None:
        """Actions 0, 1, 19 should just mark active."""
        for action in (0, 1, 19):
            state = PoolState()
            decode_chlorinator_action(action, bytes([0]), dest=80, state=state)
            chlor = state.get_chlorinator(1)
            assert chlor.is_active is True
