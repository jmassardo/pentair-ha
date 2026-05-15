"""Tests for Pentair sensor entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import UnitOfPower, UnitOfTemperature

from custom_components.pentair_easytouch.const import DOMAIN
from custom_components.pentair_easytouch.coordinator import PentairCoordinator
from custom_components.pentair_easytouch.model import Chlorinator, PoolState, Pump
from custom_components.pentair_easytouch.protocol.valuemaps import TempUnits
from custom_components.pentair_easytouch.sensor import (
    PentairAirTempSensor,
    PentairChlorOutputSensor,
    PentairPumpFlowSensor,
    PentairPumpRpmSensor,
    PentairPumpWattsSensor,
    PentairSaltLevelSensor,
    PentairSolarTempSensor,
    PentairSystemStatusSensor,
    PentairWaterSensor,
    async_setup_entry,
)


def _make_coordinator(state: PoolState | None = None) -> MagicMock:
    coordinator = MagicMock(spec=PentairCoordinator)
    coordinator.data = state
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.command_manager = MagicMock()
    coordinator.command_manager.set_circuit_state = AsyncMock()
    coordinator.command_manager.set_heat_mode = AsyncMock()
    coordinator.command_manager.set_heat_setpoint = AsyncMock()
    coordinator.command_manager.set_light_theme = AsyncMock()
    coordinator.command_manager.set_chlorinator = AsyncMock()
    coordinator.last_update_success = True
    return coordinator


def _make_state() -> PoolState:
    state = PoolState()
    state.temps.units = TempUnits.CELSIUS
    state.temps.air = 75
    state.temps.water_sensor1 = 80
    state.temps.water_sensor2 = 81
    state.temps.solar = 90
    state.mode = 1
    state.pumps = [Pump(id=1, name="Filter Pump", rpm=3000, watts=1500, flow=45)]
    state.chlorinators = [
        Chlorinator(
            id=1,
            name="IC40",
            salt_level=3400,
            current_output=55,
        )
    ]
    return state


@pytest.mark.parametrize(
    ("sensor_cls", "kwargs", "expected_name", "expected_value"),
    [
        (PentairAirTempSensor, {}, "Air Temperature", 75),
        (PentairWaterSensor, {"sensor_index": 1}, "Water Temperature 1", 80),
        (PentairWaterSensor, {"sensor_index": 2}, "Water Temperature 2", 81),
        (PentairSolarTempSensor, {}, "Solar Temperature", 90),
    ],
)
def test_temperature_sensor_properties(
    sensor_cls: type,
    kwargs: dict[str, int],
    expected_name: str,
    expected_value: int,
) -> None:
    coordinator = _make_coordinator(_make_state())
    sensor = sensor_cls(coordinator, **kwargs)

    assert sensor.name == expected_name
    assert sensor.native_value == expected_value
    assert sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert sensor.available is True


def test_sensor_base_device_info() -> None:
    sensor = PentairAirTempSensor(_make_coordinator(_make_state()))

    assert sensor.device_info == {
        "identifiers": {(DOMAIN, "test_entry_id")},
        "name": "Pentair EasyTouch",
        "manufacturer": "Pentair",
        "model": "EasyTouch",
    }


@pytest.mark.parametrize(
    ("sensor_cls", "expected_name", "expected_value", "expected_unit"),
    [
        (PentairPumpRpmSensor, "Filter Pump RPM", 3000, "RPM"),
        (PentairPumpWattsSensor, "Filter Pump Power", 1500, UnitOfPower.WATT),
        (PentairPumpFlowSensor, "Filter Pump Flow", 45, "GPM"),
    ],
)
def test_pump_sensor_properties(
    sensor_cls: type,
    expected_name: str,
    expected_value: int,
    expected_unit: str,
) -> None:
    coordinator = _make_coordinator(_make_state())
    sensor = sensor_cls(coordinator, pump_id=1)

    assert sensor.name == expected_name
    assert sensor.native_value == expected_value
    assert sensor.native_unit_of_measurement == expected_unit
    assert sensor.available is True


@pytest.mark.parametrize(
    ("sensor_cls", "expected_name", "expected_value", "expected_unit"),
    [
        (PentairSaltLevelSensor, "IC40 Salt Level", 3400, "PPM"),
        (PentairChlorOutputSensor, "IC40 Output", 55, "%"),
    ],
)
def test_chlorinator_sensor_properties(
    sensor_cls: type,
    expected_name: str,
    expected_value: int,
    expected_unit: str,
) -> None:
    coordinator = _make_coordinator(_make_state())
    sensor = sensor_cls(coordinator, chlor_id=1)

    assert sensor.name == expected_name
    assert sensor.native_value == expected_value
    assert sensor.native_unit_of_measurement == expected_unit
    assert sensor.available is True


def test_system_status_sensor_properties() -> None:
    coordinator = _make_coordinator(_make_state())
    sensor = PentairSystemStatusSensor(coordinator)

    assert sensor.name == "System Status"
    assert sensor.native_value == "service"
    assert sensor.available is True


def test_sensor_fallbacks() -> None:
    rpm_sensor = PentairPumpRpmSensor(_make_coordinator(_make_state()), pump_id=99)
    assert rpm_sensor.name == "Pump 99 RPM"
    assert rpm_sensor.native_value is None

    salt_sensor = PentairSaltLevelSensor(_make_coordinator(_make_state()), chlor_id=99)
    assert salt_sensor.name == "Chlorinator Salt Level"
    assert salt_sensor.native_value is None

    unavailable = PentairAirTempSensor(_make_coordinator(None))
    assert unavailable.native_value is None
    assert unavailable.available is False


@pytest.mark.asyncio
async def test_async_setup_entry_adds_base_and_dynamic_sensors() -> None:
    coordinator = _make_coordinator(_make_state())
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id": coordinator}}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, coordinator.config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 10
    names = {entity.name for entity in entities}
    assert "Air Temperature" in names
    assert "Water Temperature 1" in names
    assert "Filter Pump RPM" in names
    assert "IC40 Salt Level" in names
    assert "System Status" in names
