"""Tests for the data model."""

from custom_components.pentair_easytouch.model import (
    Chlorinator,
    Circuit,
    ControllerTime,
    EquipmentConfig,
    Feature,
    Heater,
    PoolBody,
    PoolState,
    Pump,
    PumpCircuit,
    Schedule,
    TemperatureState,
    Valve,
)


class TestPoolBody:
    def test_defaults(self) -> None:
        body = PoolBody()
        assert body.id == 0
        assert body.temp == 0
        assert body.is_on is False

    def test_fields(self) -> None:
        body = PoolBody(
            id=1,
            name="Pool",
            type=0,
            temp=82,
            set_point=84,
            heat_mode=1,
            heat_status=1,
            is_on=True,
            circuit=6,
        )
        assert body.name == "Pool"
        assert body.temp == 82
        assert body.set_point == 84


class TestCircuit:
    def test_defaults(self) -> None:
        c = Circuit()
        assert c.is_on is False
        assert c.is_light is False

    def test_fields(self) -> None:
        c = Circuit(id=6, name="Pool", type=2, is_on=True, is_light=False)
        assert c.id == 6
        assert c.is_on is True


class TestFeature:
    def test_defaults(self) -> None:
        f = Feature()
        assert f.show_in_features is True


class TestPump:
    def test_defaults(self) -> None:
        p = Pump()
        assert p.rpm == 0
        assert p.watts == 0
        assert p.circuits == []

    def test_with_circuits(self) -> None:
        pc = PumpCircuit(circuit_id=6, speed=2500, flow=0)
        p = Pump(id=1, circuits=[pc])
        assert len(p.circuits) == 1
        assert p.circuits[0].speed == 2500


class TestChlorinator:
    def test_defaults(self) -> None:
        c = Chlorinator()
        assert c.salt_level == 0
        assert c.super_chlor is False


class TestSchedule:
    def test_defaults(self) -> None:
        s = Schedule()
        assert s.is_active is False


class TestTemperatureState:
    def test_defaults(self) -> None:
        t = TemperatureState()
        assert t.air == 0
        assert t.units == 0


class TestControllerTime:
    def test_as_datetime_empty(self) -> None:
        ct = ControllerTime()
        assert ct.as_datetime() is None

    def test_as_datetime_valid(self) -> None:
        ct = ControllerTime(hours=15, minutes=30, seconds=0, date=1, month=6, year=24)
        dt = ct.as_datetime()
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 6
        assert dt.day == 1
        assert dt.hour == 15

    def test_as_datetime_invalid(self) -> None:
        ct = ControllerTime(hours=0, minutes=0, seconds=0, date=32, month=13, year=24)
        assert ct.as_datetime() is None


class TestEquipmentConfig:
    def test_defaults(self) -> None:
        eq = EquipmentConfig()
        assert eq.max_circuits == 8
        assert eq.shared is True


class TestPoolState:
    def test_defaults(self) -> None:
        state = PoolState()
        assert state.bodies == []
        assert state.circuits == []
        assert state.pumps == []
        assert state.freeze is False

    def test_get_body_creates(self) -> None:
        state = PoolState()
        body = state.get_body(1)
        assert body.id == 1
        assert len(state.bodies) == 1
        # Getting same id returns same object
        body2 = state.get_body(1)
        assert body is body2
        assert len(state.bodies) == 1

    def test_get_circuit_creates(self) -> None:
        state = PoolState()
        c = state.get_circuit(6)
        assert c.id == 6
        c2 = state.get_circuit(6)
        assert c is c2

    def test_get_feature_creates(self) -> None:
        state = PoolState()
        f = state.get_feature(11)
        assert f.id == 11

    def test_get_pump_creates(self) -> None:
        state = PoolState()
        p = state.get_pump(1)
        assert p.id == 1

    def test_get_pump_by_address(self) -> None:
        state = PoolState()
        p = state.get_pump(1)
        p.address = 96
        found = state.get_pump_by_address(96)
        assert found is p
        assert state.get_pump_by_address(97) is None

    def test_get_chlorinator_creates(self) -> None:
        state = PoolState()
        c = state.get_chlorinator(1)
        assert c.id == 1

    def test_get_heater_creates(self) -> None:
        state = PoolState()
        h = state.get_heater(1)
        assert h.id == 1

    def test_get_valve_creates(self) -> None:
        state = PoolState()
        v = state.get_valve(1)
        assert v.id == 1

    def test_get_schedule_creates(self) -> None:
        state = PoolState()
        s = state.get_schedule(1)
        assert s.id == 1


class TestDataclassDefaults:
    """Ensure all dataclasses can be created with no arguments."""

    def test_valve(self) -> None:
        v = Valve()
        assert v.is_diverted is False

    def test_heater(self) -> None:
        h = Heater()
        assert h.is_on is False
