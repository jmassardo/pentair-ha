"""Data model for Pentair EasyTouch pool equipment state.

All classes are plain dataclasses with no Home Assistant dependency.
Fields use ``Optional`` where the value may not be populated from the
protocol (e.g. solar temp when no solar heater is installed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# ---------------------------------------------------------------------------
# Sub-equipment models
# ---------------------------------------------------------------------------


@dataclass
class PumpCircuit:
    """A circuit assignment on a variable-speed pump."""

    circuit_id: int = 0
    speed: int = 0  # RPM (VS) or 0
    flow: int = 0  # GPM (VF/VSF) or 0


@dataclass
class PoolBody:
    """State of a pool or spa body."""

    id: int = 0
    name: str = ""
    type: int = 0  # BodyType value (0=pool, 1=spa)
    temp: int = 0
    set_point: int = 0
    cool_set_point: int = 0
    heat_mode: int = 0  # HeatMode enum value
    heat_status: int = 0  # HeatStatus enum value
    is_on: bool = False
    circuit: int = 0  # Linked circuit id (6=pool, 1=spa)


@dataclass
class Circuit:
    """State of a circuit (relay output)."""

    id: int = 0
    name: str = ""
    name_id: int = 0
    type: int = 0  # CircuitFunction value
    is_on: bool = False
    freeze_protect: bool = False
    show_in_features: bool = False
    is_light: bool = False
    lighting_theme: int = 0  # LightTheme value


@dataclass
class Feature:
    """State of a feature circuit."""

    id: int = 0
    name: str = ""
    name_id: int = 0
    type: int = 0  # FeatureFunction value
    is_on: bool = False
    freeze_protect: bool = False
    show_in_features: bool = True


@dataclass
class Pump:
    """Runtime state of a pump."""

    id: int = 0
    name: str = ""
    address: int = 0
    type: int = 0  # PumpType value
    is_active: bool = False
    rpm: int = 0
    watts: int = 0
    flow: int = 0
    mode: int = 0
    drive_state: int = 0
    command: int = 0
    ppc: int = 0
    status: int = 0  # 16-bit error codes
    time: int = 0  # Run time in minutes
    circuits: list[PumpCircuit] = field(default_factory=list)


@dataclass
class Valve:
    """State of a valve."""

    id: int = 0
    name: str = ""
    type: int = 0
    is_diverted: bool = False


@dataclass
class Heater:
    """State of a heater."""

    id: int = 0
    name: str = ""
    type: int = 0  # HeaterType value
    is_on: bool = False
    body_id: int = 0


@dataclass
class Chlorinator:
    """State of an IntelliChlor chlorinator."""

    id: int = 0
    name: str = ""
    model: int = 0
    pool_setpoint: int = 0
    spa_setpoint: int = 0
    salt_level: int = 0
    current_output: int = 0
    target_output: int = 0
    status: int = 0
    super_chlor: bool = False
    super_chlor_hours: int = 0
    is_active: bool = False
    body: int = 0


@dataclass
class Schedule:
    """A schedule entry."""

    id: int = 0
    circuit: int = 0
    start_time: int = 0  # Minutes from midnight
    end_time: int = 0  # Minutes from midnight
    schedule_days: int = 0  # Bitmask of ScheduleDay values
    schedule_type: int = 0  # ScheduleType value
    is_active: bool = False
    heat_source: int = 0
    heat_set_point: int = 0


@dataclass
class TemperatureState:
    """Temperature sensor readings."""

    air: int = 0
    water_sensor1: int = 0
    water_sensor2: int = 0
    water_sensor3: int = 0
    water_sensor4: int = 0
    solar: int = 0
    solar_sensor2: int = 0
    solar_sensor3: int = 0
    solar_sensor4: int = 0
    units: int = 0  # TempUnits value (0=F, 4=C)


@dataclass
class EquipmentConfig:
    """Equipment configuration (semi-static, learned from config messages)."""

    model: int = 0
    model_name: str = ""
    software_version: str = ""
    bootloader_version: str = ""
    max_bodies: int = 2
    max_circuits: int = 8
    max_features: int = 8
    max_pumps: int = 8
    max_schedules: int = 12
    max_heaters: int = 2
    max_valves: int = 2
    max_chlorinators: int = 1
    max_light_groups: int = 1
    max_circuit_groups: int = 0
    shared: bool = True
    single: bool = False
    dual: bool = False


@dataclass
class ControllerTime:
    """Time as reported by the controller."""

    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    day_of_week: int = 0
    date: int = 0
    month: int = 0
    year: int = 0
    adjust_dst: bool = False

    def as_datetime(self) -> datetime | None:
        """Return as a datetime object if date fields are populated."""
        if self.year == 0 or self.month == 0 or self.date == 0:
            return None
        try:
            return datetime(
                year=2000 + self.year,
                month=self.month,
                day=self.date,
                hour=self.hours,
                minute=self.minutes,
                second=self.seconds,
            )
        except (ValueError, OverflowError):
            return None


# ---------------------------------------------------------------------------
# Top-level pool state - everything the integration tracks
# ---------------------------------------------------------------------------


@dataclass
class PoolState:
    """Complete runtime state of the pool system.

    Updated incrementally as status messages arrive.
    """

    equipment: EquipmentConfig = field(default_factory=EquipmentConfig)
    temps: TemperatureState = field(default_factory=TemperatureState)
    time: ControllerTime = field(default_factory=ControllerTime)
    bodies: list[PoolBody] = field(default_factory=list)
    circuits: list[Circuit] = field(default_factory=list)
    features: list[Feature] = field(default_factory=list)
    pumps: list[Pump] = field(default_factory=list)
    valves: list[Valve] = field(default_factory=list)
    heaters: list[Heater] = field(default_factory=list)
    chlorinators: list[Chlorinator] = field(default_factory=list)
    schedules: list[Schedule] = field(default_factory=list)
    mode: int = 0  # PanelMode value
    status: int = 0
    delay: int = 0
    freeze: bool = False
    valve_byte: int = 0

    # ------------------------------------------------------------------
    # Helper accessors
    # ------------------------------------------------------------------

    def get_body(self, body_id: int) -> PoolBody:
        """Get or create a body by id."""
        for b in self.bodies:
            if b.id == body_id:
                return b
        body = PoolBody(id=body_id)
        self.bodies.append(body)
        return body

    def get_circuit(self, circuit_id: int) -> Circuit:
        """Get or create a circuit by id."""
        for c in self.circuits:
            if c.id == circuit_id:
                return c
        circuit = Circuit(id=circuit_id)
        self.circuits.append(circuit)
        return circuit

    def get_feature(self, feature_id: int) -> Feature:
        """Get or create a feature by id."""
        for f in self.features:
            if f.id == feature_id:
                return f
        feat = Feature(id=feature_id)
        self.features.append(feat)
        return feat

    def get_pump(self, pump_id: int) -> Pump:
        """Get or create a pump by id."""
        for p in self.pumps:
            if p.id == pump_id:
                return p
        pump = Pump(id=pump_id)
        self.pumps.append(pump)
        return pump

    def get_pump_by_address(self, address: int) -> Pump | None:
        """Find a pump by its RS485 address."""
        for p in self.pumps:
            if p.address == address:
                return p
        return None

    def get_chlorinator(self, chlor_id: int) -> Chlorinator:
        """Get or create a chlorinator by id."""
        for c in self.chlorinators:
            if c.id == chlor_id:
                return c
        chlor = Chlorinator(id=chlor_id)
        self.chlorinators.append(chlor)
        return chlor

    def get_heater(self, heater_id: int) -> Heater:
        """Get or create a heater by id."""
        for h in self.heaters:
            if h.id == heater_id:
                return h
        heater = Heater(id=heater_id)
        self.heaters.append(heater)
        return heater

    def get_valve(self, valve_id: int) -> Valve:
        """Get or create a valve by id."""
        for v in self.valves:
            if v.id == valve_id:
                return v
        valve = Valve(id=valve_id)
        self.valves.append(valve)
        return valve

    def get_schedule(self, schedule_id: int) -> Schedule:
        """Get or create a schedule by id."""
        for s in self.schedules:
            if s.id == schedule_id:
                return s
        sched = Schedule(id=schedule_id)
        self.schedules.append(sched)
        return sched
