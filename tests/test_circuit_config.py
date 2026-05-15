"""Tests for the Action 11 circuit configuration decoder."""

import pytest

from custom_components.pentair_easytouch.model import PoolState
from custom_components.pentair_easytouch.protocol.circuit_config import (
    decode_circuit_config,
)
from custom_components.pentair_easytouch.protocol.valuemaps import CircuitFunction


class TestDecodeCircuitConfig:
    """Tests for decode_circuit_config."""

    def test_basic_generic_circuit(self) -> None:
        """A generic circuit with a valid name_id should be active."""
        state = PoolState()
        # circuit_id=3, function=GENERIC(0), name_id=3 (AUX 1), reserved, reserved
        payload = bytes([3, 0, 3, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(3)
        assert circuit.id == 3
        assert circuit.name == "AUX 1"
        assert circuit.name_id == 3
        assert circuit.type == CircuitFunction.GENERIC
        assert circuit.is_active is True
        assert circuit.is_light is False
        assert circuit.freeze_protect is False

    def test_light_circuit_intellibrite(self) -> None:
        """An IntelliBrite circuit should be marked as a light."""
        state = PoolState()
        # circuit_id=7, function=INTELLIBRITE(16), name_id=63 (Pool Light)
        payload = bytes([7, 16, 63, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(7)
        assert circuit.id == 7
        assert circuit.name == "Pool Light"
        assert circuit.type == CircuitFunction.INTELLIBRITE
        assert circuit.is_active is True
        assert circuit.is_light is True

    def test_light_circuit_sam_light(self) -> None:
        """A SAM Light circuit should be marked as a light."""
        state = PoolState()
        # circuit_id=5, function=SAM_LIGHT(9), name_id=74 (Spa Light)
        payload = bytes([5, 9, 74, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(5)
        assert circuit.is_light is True
        assert circuit.is_active is True
        assert circuit.name == "Spa Light"

    def test_not_used_circuit(self) -> None:
        """A circuit with function=NOT_USED should be inactive."""
        state = PoolState()
        # circuit_id=10, function=NOT_USED(19), name_id=53 (Not Used)
        payload = bytes([10, 19, 53, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(10)
        assert circuit.is_active is False
        assert circuit.type == CircuitFunction.NOT_USED
        assert circuit.is_light is False

    def test_not_used_zero_name_id(self) -> None:
        """A circuit with name_id=0 should be inactive even if function is not NOT_USED."""
        state = PoolState()
        # circuit_id=8, function=GENERIC(0), name_id=0
        payload = bytes([8, 0, 0, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(8)
        assert circuit.is_active is False

    def test_freeze_protect_flag(self) -> None:
        """Bit 6 of function byte should set freeze_protect."""
        state = PoolState()
        # circuit_id=2, function=0x40 | GENERIC(0) = 0x40, name_id=17 (Booster Pump)
        payload = bytes([2, 0x40, 17, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(2)
        assert circuit.freeze_protect is True
        assert circuit.type == CircuitFunction.GENERIC
        assert circuit.is_active is True
        assert circuit.name == "Booster Pump"

    def test_freeze_protect_with_light(self) -> None:
        """Freeze protect flag combined with a light function."""
        state = PoolState()
        # circuit_id=4, function=0x40 | LIGHT(7) = 0x47, name_id=47 (Lights)
        payload = bytes([4, 0x47, 47, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(4)
        assert circuit.freeze_protect is True
        assert circuit.type == CircuitFunction.LIGHT
        assert circuit.is_light is True
        assert circuit.is_active is True
        assert circuit.name == "Lights"

    def test_spa_circuit(self) -> None:
        """A spa body circuit should be identified correctly."""
        state = PoolState()
        # circuit_id=1, function=SPA(1), name_id=72 (Spa)
        payload = bytes([1, 1, 72, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(1)
        assert circuit.type == CircuitFunction.SPA
        assert circuit.is_active is True
        assert circuit.is_light is False
        assert circuit.name == "Spa"

    def test_pool_circuit(self) -> None:
        """A pool body circuit should be identified correctly."""
        state = PoolState()
        # circuit_id=6, function=POOL(2), name_id=61 (Pool)
        payload = bytes([6, 2, 61, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(6)
        assert circuit.type == CircuitFunction.POOL
        assert circuit.is_active is True
        assert circuit.name == "Pool"

    def test_custom_name_id_fallback(self) -> None:
        """name_id >= 200 (custom names) should fall back to 'Circuit {id}'."""
        state = PoolState()
        # circuit_id=5, function=GENERIC(0), name_id=201 (custom name slot 1)
        payload = bytes([5, 0, 201, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(5)
        assert circuit.name == "Circuit 5"
        assert circuit.is_active is True

    def test_unknown_name_id_fallback(self) -> None:
        """An unrecognized name_id (not in table, not custom) should fall back."""
        state = PoolState()
        # circuit_id=9, function=GENERIC(0), name_id=150 (not in table)
        payload = bytes([9, 0, 150, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(9)
        assert circuit.name == "Circuit 9"
        assert circuit.is_active is True

    def test_payload_too_short(self) -> None:
        """Payloads shorter than 5 bytes should be ignored."""
        state = PoolState()
        payload = bytes([3, 0, 3, 0])  # Only 4 bytes
        decode_circuit_config(payload, state)

        # No circuit should have been created
        assert len(state.circuits) == 0

    def test_empty_payload(self) -> None:
        """Empty payload should be ignored."""
        state = PoolState()
        decode_circuit_config(b"", state)
        assert len(state.circuits) == 0

    def test_updates_existing_circuit(self) -> None:
        """Decoding should update an existing circuit, not duplicate."""
        state = PoolState()
        # Pre-create the circuit from a status message
        circuit = state.get_circuit(3)
        circuit.is_on = True

        # Now decode its config
        payload = bytes([3, 0, 3, 0, 0])
        decode_circuit_config(payload, state)

        # Should still be the same circuit
        assert len(state.circuits) == 1
        result = state.get_circuit(3)
        assert result.is_on is True  # Preserved from before
        assert result.name == "AUX 1"  # Updated by config
        assert result.is_active is True

    def test_magicstream_is_light(self) -> None:
        """MagicStream should be classified as a light."""
        state = PoolState()
        # circuit_id=8, function=MAGICSTREAM(17), name_id=81 (Stream)
        payload = bytes([8, 17, 81, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(8)
        assert circuit.is_light is True
        assert circuit.type == CircuitFunction.MAGICSTREAM

    def test_valve_not_light(self) -> None:
        """Valve circuits should not be lights."""
        state = PoolState()
        # circuit_id=9, function=VALVE(13), name_id=79 (Spillway)
        payload = bytes([9, 13, 79, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(9)
        assert circuit.is_light is False
        assert circuit.type == CircuitFunction.VALVE
        assert circuit.is_active is True

    def test_spillway_not_light(self) -> None:
        """Spillway circuits should not be lights."""
        state = PoolState()
        # circuit_id=4, function=SPILLWAY(14), name_id=79 (Spillway)
        payload = bytes([4, 14, 79, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(4)
        assert circuit.is_light is False
        assert circuit.type == CircuitFunction.SPILLWAY


class TestCircuitConfigRouting:
    """Tests that Action 11 is properly routed through the MessageRouter."""

    def test_action11_routed_to_decoder(self) -> None:
        """Action 11 should be dispatched to decode_circuit_config."""
        from custom_components.pentair_easytouch.protocol.framing import PentairPacket
        from custom_components.pentair_easytouch.protocol.messages import MessageRouter

        state = PoolState()
        router = MessageRouter(state)

        # circuit_id=6, function=POOL(2), name_id=61 (Pool)
        payload = bytes([6, 2, 61, 0, 0])
        packet = PentairPacket(
            version=1,
            dest=15,
            source=16,
            action=11,
            payload=payload,
        )
        router.dispatch(packet)

        circuit = state.get_circuit(6)
        assert circuit.name == "Pool"
        assert circuit.type == CircuitFunction.POOL
        assert circuit.is_active is True

    def test_action11_triggers_callback(self) -> None:
        """Action 11 should trigger the on_state_updated callback."""
        from custom_components.pentair_easytouch.protocol.framing import PentairPacket
        from custom_components.pentair_easytouch.protocol.messages import MessageRouter

        state = PoolState()
        callback_count = [0]

        def on_update() -> None:
            callback_count[0] += 1

        router = MessageRouter(state, on_state_updated=on_update)

        payload = bytes([3, 0, 3, 0, 0])
        packet = PentairPacket(version=1, dest=15, source=16, action=11, payload=payload)
        router.dispatch(packet)

        assert callback_count[0] == 1


class TestCircuitActiveFiltering:
    """Tests that is_active filtering works correctly for entity creation."""

    def test_inactive_circuit_not_in_switch_discovery(self) -> None:
        """Inactive circuits should not be discovered as switches."""
        from custom_components.pentair_easytouch.model import Circuit

        state = PoolState()
        state.circuits = [
            Circuit(id=1, name="Spa", is_on=False, is_light=False, is_active=True),
            Circuit(id=2, name="Not Used", is_on=False, is_light=False, is_active=False),
            Circuit(id=3, name="AUX 1", is_on=True, is_light=False, is_active=True),
        ]

        # Simulate the switch discovery filter
        active_non_light_circuits = [c for c in state.circuits if not c.is_light and c.is_active]
        assert len(active_non_light_circuits) == 2
        assert all(c.id != 2 for c in active_non_light_circuits)

    def test_inactive_light_not_in_light_discovery(self) -> None:
        """Inactive light circuits should not be discovered as lights."""
        from custom_components.pentair_easytouch.model import Circuit

        state = PoolState()
        state.circuits = [
            Circuit(id=7, name="Pool Light", is_light=True, is_active=True),
            Circuit(id=8, name="Not Used", is_light=True, is_active=False),
        ]

        active_lights = [c for c in state.circuits if c.is_light and c.is_active]
        assert len(active_lights) == 1
        assert active_lights[0].id == 7

    @pytest.mark.parametrize(
        ("function_id", "expected_light"),
        [
            (CircuitFunction.GENERIC, False),
            (CircuitFunction.SPA, False),
            (CircuitFunction.POOL, False),
            (CircuitFunction.MASTER_CLEANER, False),
            (CircuitFunction.LIGHT, True),
            (CircuitFunction.SAM_LIGHT, True),
            (CircuitFunction.SAL_LIGHT, True),
            (CircuitFunction.PHOTON_GEN, True),
            (CircuitFunction.COLOR_WHEEL, True),
            (CircuitFunction.VALVE, False),
            (CircuitFunction.SPILLWAY, False),
            (CircuitFunction.FLOOR_CLEANER, False),
            (CircuitFunction.INTELLIBRITE, True),
            (CircuitFunction.MAGICSTREAM, True),
            (CircuitFunction.NOT_USED, False),
        ],
    )
    def test_is_light_for_all_function_types(self, function_id: int, expected_light: bool) -> None:
        """Verify is_light is correctly set for all known function types."""
        state = PoolState()
        # Use a valid name_id so the circuit is active (unless NOT_USED)
        payload = bytes([1, function_id, 61, 0, 0])
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(1)
        assert circuit.is_light is expected_light
