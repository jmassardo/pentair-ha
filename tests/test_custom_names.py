"""Tests for the Action 10 custom name decoder."""

import pytest

from custom_components.pentair_easytouch.model import Circuit, PoolState
from custom_components.pentair_easytouch.protocol.custom_names import (
    decode_custom_names,
)


class TestDecodeCustomNames:
    """Tests for decode_custom_names."""

    def test_basic_custom_name(self) -> None:
        """A standard custom name should be stored and stripped."""
        state = PoolState()
        # name_index=0, name="Waterfall" + null padding
        payload = bytes([0]) + b"Waterfall\x00\x00"
        decode_custom_names(payload, state)

        assert state.custom_names[0] == "Waterfall"

    def test_name_with_space_padding(self) -> None:
        """Trailing spaces should be stripped."""
        state = PoolState()
        # name_index=2, name="Pool Lt" + spaces
        payload = bytes([2]) + b"Pool Lt    "
        decode_custom_names(payload, state)

        assert state.custom_names[2] == "Pool Lt"

    def test_full_length_name(self) -> None:
        """An 11-character name should be stored without truncation."""
        state = PoolState()
        payload = bytes([1]) + b"Spa Waterfl"
        decode_custom_names(payload, state)

        assert state.custom_names[1] == "Spa Waterfl"

    def test_empty_name_skipped(self) -> None:
        """An all-null/space name should not be stored."""
        state = PoolState()
        payload = bytes([3]) + b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        decode_custom_names(payload, state)

        assert 3 not in state.custom_names

    def test_payload_too_short(self) -> None:
        """Payloads shorter than 2 bytes should be ignored."""
        state = PoolState()
        decode_custom_names(bytes([0]), state)
        assert len(state.custom_names) == 0

    def test_empty_payload(self) -> None:
        """Empty payload should be ignored."""
        state = PoolState()
        decode_custom_names(b"", state)
        assert len(state.custom_names) == 0

    def test_resolves_existing_circuit_names(self) -> None:
        """When a custom name arrives, circuits referencing it should be updated."""
        state = PoolState()
        # Pre-create a circuit with name_id=201 (custom name slot 1)
        circuit = state.get_circuit(5)
        circuit.name_id = 201
        circuit.name = "Circuit 5"

        # Now decode custom name slot 1
        payload = bytes([1]) + b"Spa Jets\x00\x00\x00"
        decode_custom_names(payload, state)

        assert state.custom_names[1] == "Spa Jets"
        assert circuit.name == "Spa Jets"

    def test_does_not_affect_non_matching_circuits(self) -> None:
        """Circuits with different name_ids should not be affected."""
        state = PoolState()
        # Circuit using built-in name_id=61 (Pool)
        circuit = state.get_circuit(6)
        circuit.name_id = 61
        circuit.name = "Pool"

        # Decode custom name slot 0
        payload = bytes([0]) + b"Fountain\x00\x00\x00"
        decode_custom_names(payload, state)

        assert circuit.name == "Pool"  # Unchanged

    def test_multiple_custom_names(self) -> None:
        """Multiple custom names can be stored independently."""
        state = PoolState()

        decode_custom_names(bytes([0]) + b"Waterfall\x00\x00", state)
        decode_custom_names(bytes([1]) + b"Spa Jets\x00\x00\x00", state)
        decode_custom_names(bytes([5]) + b"Fire Bowls\x00", state)

        assert state.custom_names[0] == "Waterfall"
        assert state.custom_names[1] == "Spa Jets"
        assert state.custom_names[5] == "Fire Bowls"

    def test_updates_multiple_circuits(self) -> None:
        """If multiple circuits reference the same custom name, all are updated."""
        state = PoolState()
        c1 = state.get_circuit(3)
        c1.name_id = 200
        c1.name = "Circuit 3"
        c2 = state.get_circuit(7)
        c2.name_id = 200
        c2.name = "Circuit 7"

        payload = bytes([0]) + b"Deck Light\x00"
        decode_custom_names(payload, state)

        assert c1.name == "Deck Light"
        assert c2.name == "Deck Light"

    def test_short_name(self) -> None:
        """A very short custom name should work."""
        state = PoolState()
        payload = bytes([4]) + b"SPA\x00\x00\x00\x00\x00\x00\x00\x00"
        decode_custom_names(payload, state)

        assert state.custom_names[4] == "SPA"


class TestCustomNamesRouting:
    """Tests that Action 10 is properly routed through the MessageRouter."""

    def test_action10_routed_to_decoder(self) -> None:
        """Action 10 should be dispatched to decode_custom_names."""
        from custom_components.pentair_easytouch.protocol.framing import PentairPacket
        from custom_components.pentair_easytouch.protocol.messages import MessageRouter

        state = PoolState()
        router = MessageRouter(state)

        payload = bytes([0]) + b"Waterfall\x00\x00"
        packet = PentairPacket(
            version=1,
            dest=15,
            source=16,
            action=10,
            payload=payload,
        )
        router.dispatch(packet)

        assert state.custom_names[0] == "Waterfall"

    def test_action10_triggers_callback(self) -> None:
        """Action 10 should trigger the on_state_updated callback."""
        from custom_components.pentair_easytouch.protocol.framing import PentairPacket
        from custom_components.pentair_easytouch.protocol.messages import MessageRouter

        state = PoolState()
        callback_count = [0]

        def on_update() -> None:
            callback_count[0] += 1

        router = MessageRouter(state, on_state_updated=on_update)

        payload = bytes([0]) + b"Waterfall\x00\x00"
        packet = PentairPacket(version=1, dest=15, source=16, action=10, payload=payload)
        router.dispatch(packet)

        assert callback_count[0] == 1


class TestCustomNamesIntegration:
    """End-to-end tests: custom names + circuit config working together."""

    def test_custom_names_before_circuit_config(self) -> None:
        """Custom names loaded first, then circuit config uses them."""
        from custom_components.pentair_easytouch.protocol.circuit_config import (
            decode_circuit_config,
        )

        state = PoolState()

        # Custom name arrives first
        decode_custom_names(bytes([3]) + b"Fire Bowls\x00", state)

        # Circuit config arrives referencing custom name slot 3
        payload = bytes([4, 0, 203, 0, 0])  # name_id=203 -> slot 3
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(4)
        assert circuit.name == "Fire Bowls"

    def test_circuit_config_before_custom_names(self) -> None:
        """Circuit config arrives first (fallback), then custom name updates it."""
        from custom_components.pentair_easytouch.protocol.circuit_config import (
            decode_circuit_config,
        )

        state = PoolState()

        # Circuit config arrives first — no custom name yet
        payload = bytes([4, 0, 203, 0, 0])  # name_id=203 -> slot 3
        decode_circuit_config(payload, state)

        circuit = state.get_circuit(4)
        assert circuit.name == "Circuit 4"  # Fallback

        # Custom name arrives later — circuit should be updated
        decode_custom_names(bytes([3]) + b"Fire Bowls\x00", state)

        assert circuit.name == "Fire Bowls"
