"""Sensor platform for Pentair EasyTouch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PentairCoordinator
from .protocol.valuemaps import PANEL_MODE_NAMES, TempUnits

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .model import Chlorinator, Pump

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pentair sensor entities."""
    coordinator: PentairCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        PentairAirTempSensor(coordinator),
        PentairWaterSensor(coordinator, sensor_index=1),
        PentairWaterSensor(coordinator, sensor_index=2),
        PentairSolarTempSensor(coordinator),
        PentairSystemStatusSensor(coordinator),
    ]

    if coordinator.data is not None:
        for pump in coordinator.data.pumps:
            entities.append(PentairPumpRpmSensor(coordinator, pump.id))
            entities.append(PentairPumpWattsSensor(coordinator, pump.id))
            entities.append(PentairPumpFlowSensor(coordinator, pump.id))

        for chlor in coordinator.data.chlorinators:
            entities.append(PentairSaltLevelSensor(coordinator, chlor.id))
            entities.append(PentairChlorOutputSensor(coordinator, chlor.id))

    async_add_entities(entities)


class PentairSensorBase(CoordinatorEntity[PentairCoordinator], SensorEntity):
    """Base class for Pentair sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PentairCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the Pentair controller."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name="Pentair EasyTouch",
            manufacturer="Pentair",
            model="EasyTouch",
        )

    def _temp_unit(self) -> str:
        """Return the temperature unit based on controller setting."""
        if (
            self.coordinator.data is not None
            and self.coordinator.data.temps.units == TempUnits.CELSIUS
        ):
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT


class PentairAirTempSensor(PentairSensorBase):
    """Sensor for air temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PentairCoordinator) -> None:
        """Initialize the air temperature sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_air_temp"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Air Temperature"

    @property
    def native_value(self) -> int | None:
        """Return the air temperature."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.temps.air

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._temp_unit()


class PentairWaterSensor(PentairSensorBase):
    """Sensor for water temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PentairCoordinator, sensor_index: int) -> None:
        """Initialize the water temperature sensor."""
        super().__init__(coordinator)
        self._sensor_index = sensor_index
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_water_temp_{sensor_index}"

    @property
    def name(self) -> str:
        """Return the name."""
        return f"Water Temperature {self._sensor_index}"

    @property
    def native_value(self) -> int | None:
        """Return the water temperature."""
        if self.coordinator.data is None:
            return None
        if self._sensor_index == 1:
            return self.coordinator.data.temps.water_sensor1
        return self.coordinator.data.temps.water_sensor2

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._temp_unit()


class PentairSolarTempSensor(PentairSensorBase):
    """Sensor for solar temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PentairCoordinator) -> None:
        """Initialize the solar temperature sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_solar_temp"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Solar Temperature"

    @property
    def native_value(self) -> int | None:
        """Return the solar temperature."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.temps.solar

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._temp_unit()


class PentairPumpRpmSensor(PentairSensorBase):
    """Sensor for pump RPM."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "RPM"
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator: PentairCoordinator, pump_id: int) -> None:
        """Initialize the pump RPM sensor."""
        super().__init__(coordinator)
        self._pump_id = pump_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_pump_{pump_id}_rpm"

    def _find_pump(self) -> Pump | None:
        """Find this pump in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for pump in self.coordinator.data.pumps:
            if pump.id == self._pump_id:
                return pump
        return None

    @property
    def name(self) -> str:
        """Return the name."""
        pump = self._find_pump()
        pump_name = pump.name if pump and pump.name else f"Pump {self._pump_id}"
        return f"{pump_name} RPM"

    @property
    def native_value(self) -> int | None:
        """Return the pump RPM."""
        pump = self._find_pump()
        return pump.rpm if pump else None


class PentairPumpWattsSensor(PentairSensorBase):
    """Sensor for pump power consumption."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: PentairCoordinator, pump_id: int) -> None:
        """Initialize the pump watts sensor."""
        super().__init__(coordinator)
        self._pump_id = pump_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_pump_{pump_id}_watts"

    def _find_pump(self) -> Pump | None:
        """Find this pump in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for pump in self.coordinator.data.pumps:
            if pump.id == self._pump_id:
                return pump
        return None

    @property
    def name(self) -> str:
        """Return the name."""
        pump = self._find_pump()
        pump_name = pump.name if pump and pump.name else f"Pump {self._pump_id}"
        return f"{pump_name} Power"

    @property
    def native_value(self) -> int | None:
        """Return the pump watts."""
        pump = self._find_pump()
        return pump.watts if pump else None


class PentairPumpFlowSensor(PentairSensorBase):
    """Sensor for pump flow rate."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "GPM"
    _attr_icon = "mdi:water-pump"

    def __init__(self, coordinator: PentairCoordinator, pump_id: int) -> None:
        """Initialize the pump flow sensor."""
        super().__init__(coordinator)
        self._pump_id = pump_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_pump_{pump_id}_flow"

    def _find_pump(self) -> Pump | None:
        """Find this pump in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for pump in self.coordinator.data.pumps:
            if pump.id == self._pump_id:
                return pump
        return None

    @property
    def name(self) -> str:
        """Return the name."""
        pump = self._find_pump()
        pump_name = pump.name if pump and pump.name else f"Pump {self._pump_id}"
        return f"{pump_name} Flow"

    @property
    def native_value(self) -> int | None:
        """Return the pump flow in GPM."""
        pump = self._find_pump()
        return pump.flow if pump else None


class PentairSaltLevelSensor(PentairSensorBase):
    """Sensor for chlorinator salt level."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "PPM"
    _attr_icon = "mdi:shaker-outline"

    def __init__(self, coordinator: PentairCoordinator, chlor_id: int) -> None:
        """Initialize the salt level sensor."""
        super().__init__(coordinator)
        self._chlor_id = chlor_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_chlorinator_{chlor_id}_salt"

    def _find_chlorinator(self) -> Chlorinator | None:
        """Find this chlorinator in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for chlor in self.coordinator.data.chlorinators:
            if chlor.id == self._chlor_id:
                return chlor
        return None

    @property
    def name(self) -> str:
        """Return the name."""
        chlor = self._find_chlorinator()
        chlor_name = chlor.name if chlor and chlor.name else "Chlorinator"
        return f"{chlor_name} Salt Level"

    @property
    def native_value(self) -> int | None:
        """Return the salt level in PPM."""
        chlor = self._find_chlorinator()
        return chlor.salt_level if chlor else None


class PentairChlorOutputSensor(PentairSensorBase):
    """Sensor for chlorinator current output percentage."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator: PentairCoordinator, chlor_id: int) -> None:
        """Initialize the chlorinator output sensor."""
        super().__init__(coordinator)
        self._chlor_id = chlor_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_chlorinator_{chlor_id}_output"

    def _find_chlorinator(self) -> Chlorinator | None:
        """Find this chlorinator in the coordinator data."""
        if self.coordinator.data is None:
            return None
        for chlor in self.coordinator.data.chlorinators:
            if chlor.id == self._chlor_id:
                return chlor
        return None

    @property
    def name(self) -> str:
        """Return the name."""
        chlor = self._find_chlorinator()
        chlor_name = chlor.name if chlor and chlor.name else "Chlorinator"
        return f"{chlor_name} Output"

    @property
    def native_value(self) -> int | None:
        """Return the current output percentage."""
        chlor = self._find_chlorinator()
        return chlor.current_output if chlor else None


class PentairSystemStatusSensor(PentairSensorBase):
    """Sensor for system panel mode/status."""

    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator: PentairCoordinator) -> None:
        """Initialize the system status sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_system_status"

    @property
    def name(self) -> str:
        """Return the name."""
        return "System Status"

    @property
    def native_value(self) -> str | None:
        """Return the system status as a human-readable string."""
        if self.coordinator.data is None:
            return None
        mode = self.coordinator.data.mode
        return PANEL_MODE_NAMES.get(mode, f"unknown ({mode})")
