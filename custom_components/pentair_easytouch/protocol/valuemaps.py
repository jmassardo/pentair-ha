"""Enums and lookup tables for Pentair EasyTouch protocol values.

Ported from SystemBoard.ts and EasyTouchBoard.ts valueMaps.
"""

from __future__ import annotations

from enum import IntEnum


# ---------------------------------------------------------------------------
# Panel modes  (payload[9] & 0x81 for *Touch)
# ---------------------------------------------------------------------------
class PanelMode(IntEnum):
    """Operating mode of the control panel."""

    AUTO = 0
    SERVICE = 1
    FREEZE = 8
    TIMEOUT = 128
    SERVICE_TIMEOUT = 129
    ERROR = 255


PANEL_MODE_NAMES: dict[int, str] = {
    PanelMode.AUTO: "auto",
    PanelMode.SERVICE: "service",
    PanelMode.FREEZE: "freeze",
    PanelMode.TIMEOUT: "timeout",
    PanelMode.SERVICE_TIMEOUT: "service-timeout",
    PanelMode.ERROR: "error",
}


# ---------------------------------------------------------------------------
# Heat modes  (EasyTouch uses 0-3 for body heat mode)
# ---------------------------------------------------------------------------
class HeatMode(IntEnum):
    """Heat mode for a body (pool/spa)."""

    OFF = 0
    HEATER = 1
    SOLAR_PREFERRED = 2
    SOLAR_ONLY = 3


HEAT_MODE_NAMES: dict[int, str] = {
    HeatMode.OFF: "off",
    HeatMode.HEATER: "heater",
    HeatMode.SOLAR_PREFERRED: "solar_preferred",
    HeatMode.SOLAR_ONLY: "solar_only",
}


# ---------------------------------------------------------------------------
# Heat status  (derived from byte 10 bit analysis)
# ---------------------------------------------------------------------------
class HeatStatus(IntEnum):
    """Current heat status for a body."""

    OFF = 0
    HEATER = 1
    COOLING = 2
    SOLAR = 3
    HEATPUMP = 4
    DUAL = 5


HEAT_STATUS_NAMES: dict[int, str] = {
    HeatStatus.OFF: "off",
    HeatStatus.HEATER: "heater",
    HeatStatus.COOLING: "cooling",
    HeatStatus.SOLAR: "solar",
    HeatStatus.HEATPUMP: "heatpump",
    HeatStatus.DUAL: "dual",
}


# ---------------------------------------------------------------------------
# Circuit functions  (from SystemBoard.ts circuitFunctions)
# ---------------------------------------------------------------------------
class CircuitFunction(IntEnum):
    """Functional type of a circuit."""

    GENERIC = 0
    SPA = 1
    POOL = 2
    MASTER_CLEANER = 5
    LIGHT = 7
    SAM_LIGHT = 9
    SAL_LIGHT = 10
    PHOTON_GEN = 11
    COLOR_WHEEL = 12
    VALVE = 13
    SPILLWAY = 14
    FLOOR_CLEANER = 15
    INTELLIBRITE = 16
    MAGICSTREAM = 17
    NOT_USED = 19
    LO_TEMP = 65
    HI_TEMP = 66


CIRCUIT_FUNCTION_NAMES: dict[int, str] = {
    CircuitFunction.GENERIC: "generic",
    CircuitFunction.SPA: "spa",
    CircuitFunction.POOL: "pool",
    CircuitFunction.MASTER_CLEANER: "master_cleaner",
    CircuitFunction.LIGHT: "light",
    CircuitFunction.SAM_LIGHT: "sam_light",
    CircuitFunction.SAL_LIGHT: "sal_light",
    CircuitFunction.PHOTON_GEN: "photon_gen",
    CircuitFunction.COLOR_WHEEL: "color_wheel",
    CircuitFunction.VALVE: "valve",
    CircuitFunction.SPILLWAY: "spillway",
    CircuitFunction.FLOOR_CLEANER: "floor_cleaner",
    CircuitFunction.INTELLIBRITE: "intellibrite",
    CircuitFunction.MAGICSTREAM: "magicstream",
    CircuitFunction.NOT_USED: "not_used",
    CircuitFunction.LO_TEMP: "lo_temp",
    CircuitFunction.HI_TEMP: "hi_temp",
}

# Which circuit functions are lights?
LIGHT_FUNCTIONS: frozenset[int] = frozenset(
    {
        CircuitFunction.LIGHT,
        CircuitFunction.SAM_LIGHT,
        CircuitFunction.SAL_LIGHT,
        CircuitFunction.PHOTON_GEN,
        CircuitFunction.COLOR_WHEEL,
        CircuitFunction.INTELLIBRITE,
        CircuitFunction.MAGICSTREAM,
    }
)


def is_light_function(func_id: int) -> bool:
    """Return True if the circuit function represents a light."""
    return func_id in LIGHT_FUNCTIONS


# ---------------------------------------------------------------------------
# Feature functions  (EasyTouch)
# ---------------------------------------------------------------------------
class FeatureFunction(IntEnum):
    """Functional type of a feature circuit."""

    GENERIC = 0
    SPILLWAY = 14


FEATURE_FUNCTION_NAMES: dict[int, str] = {
    FeatureFunction.GENERIC: "generic",
    FeatureFunction.SPILLWAY: "spillway",
}


# ---------------------------------------------------------------------------
# Pump types  (EasyTouchBoard.ts)
# ---------------------------------------------------------------------------
class PumpType(IntEnum):
    """Type of pump hardware."""

    VF = 1  # Intelliflo VF
    VSF = 64  # Intelliflo VSF
    DS = 65  # Two-speed
    VS = 128  # Intelliflo VS
    VSSVRS = 169  # IntelliFlo VS+SVRS
    SF = 256  # SuperFlo VS
    SS = 257  # Single speed
    HWRLY = 258  # Hayward relay VS
    HWVS = 259  # Hayward Eco/TriStar VS


PUMP_TYPE_NAMES: dict[int, str] = {
    PumpType.VF: "vf",
    PumpType.VSF: "vsf",
    PumpType.DS: "ds",
    PumpType.VS: "vs",
    PumpType.VSSVRS: "vssvrs",
    PumpType.SF: "sf",
    PumpType.SS: "ss",
    PumpType.HWRLY: "hwrly",
    PumpType.HWVS: "hwvs",
}


# ---------------------------------------------------------------------------
# Light themes  (SystemBoard.ts lightThemes)
# ---------------------------------------------------------------------------
class LightTheme(IntEnum):
    """IntelliBrite / MagicStream light themes."""

    OFF = 0
    ON = 1
    COLOR_SYNC = 128
    COLOR_SWIM = 144
    COLOR_SET = 160
    PARTY = 177
    ROMANCE = 178
    CARIBBEAN = 179
    AMERICAN = 180
    SUNSET = 181
    ROYAL = 182
    SAVE = 190
    RECALL = 191
    BLUE = 193
    GREEN = 194
    RED = 195
    WHITE = 196
    MAGENTA = 197
    THUMPER = 208
    HOLD = 209
    RESET = 210
    MODE = 211
    UNKNOWN = 254
    NONE = 255


LIGHT_THEME_NAMES: dict[int, str] = {
    LightTheme.OFF: "off",
    LightTheme.ON: "on",
    LightTheme.COLOR_SYNC: "color_sync",
    LightTheme.COLOR_SWIM: "color_swim",
    LightTheme.COLOR_SET: "color_set",
    LightTheme.PARTY: "party",
    LightTheme.ROMANCE: "romance",
    LightTheme.CARIBBEAN: "caribbean",
    LightTheme.AMERICAN: "american",
    LightTheme.SUNSET: "sunset",
    LightTheme.ROYAL: "royal",
    LightTheme.SAVE: "save",
    LightTheme.RECALL: "recall",
    LightTheme.BLUE: "blue",
    LightTheme.GREEN: "green",
    LightTheme.RED: "red",
    LightTheme.WHITE: "white",
    LightTheme.MAGENTA: "magenta",
    LightTheme.THUMPER: "thumper",
    LightTheme.HOLD: "hold",
    LightTheme.RESET: "reset",
    LightTheme.MODE: "mode",
    LightTheme.UNKNOWN: "unknown",
    LightTheme.NONE: "none",
}


# ---------------------------------------------------------------------------
# Body type  (pool = body 1, spa = body 2)
# ---------------------------------------------------------------------------
class BodyType(IntEnum):
    """Pool/spa body type."""

    POOL = 0
    SPA = 1


BODY_TYPE_NAMES: dict[int, str] = {
    BodyType.POOL: "pool",
    BodyType.SPA: "spa",
}


# ---------------------------------------------------------------------------
# Schedule types  (EasyTouchBoard.ts)
# ---------------------------------------------------------------------------
class ScheduleType(IntEnum):
    """Schedule execution type."""

    REPEAT = 0
    RUN_ONCE = 26


SCHEDULE_TYPE_NAMES: dict[int, str] = {
    ScheduleType.REPEAT: "repeat",
    ScheduleType.RUN_ONCE: "run_once",
}


# ---------------------------------------------------------------------------
# Schedule days bitmask  (EasyTouchBoard.ts scheduleDays)
# EasyTouch uses individual bit positions for each day.
# ---------------------------------------------------------------------------
class ScheduleDay(IntEnum):
    """Bitmask values for schedule days (EasyTouch)."""

    SUNDAY = 1
    MONDAY = 2
    TUESDAY = 4
    WEDNESDAY = 8
    THURSDAY = 16
    FRIDAY = 32
    SATURDAY = 64


SCHEDULE_DAY_NAMES: dict[int, str] = {
    ScheduleDay.SUNDAY: "sunday",
    ScheduleDay.MONDAY: "monday",
    ScheduleDay.TUESDAY: "tuesday",
    ScheduleDay.WEDNESDAY: "wednesday",
    ScheduleDay.THURSDAY: "thursday",
    ScheduleDay.FRIDAY: "friday",
    ScheduleDay.SATURDAY: "saturday",
}

ALL_DAYS_MASK = 0x7F  # Sun-Sat


def decode_schedule_days(bitmask: int) -> list[str]:
    """Return a list of day names from a schedule day bitmask."""
    days: list[str] = []
    for bit, name in SCHEDULE_DAY_NAMES.items():
        if bitmask & bit:
            days.append(name)
    return days


# ---------------------------------------------------------------------------
# Schedule time types
# ---------------------------------------------------------------------------
class ScheduleTimeType(IntEnum):
    """How a schedule start/end time is specified."""

    MANUAL = 0
    SUNRISE = 1
    SUNSET = 2


SCHEDULE_TIME_TYPE_NAMES: dict[int, str] = {
    ScheduleTimeType.MANUAL: "manual",
    ScheduleTimeType.SUNRISE: "sunrise",
    ScheduleTimeType.SUNSET: "sunset",
}


# ---------------------------------------------------------------------------
# Heater types  (EasyTouchBoard.ts)
# ---------------------------------------------------------------------------
class HeaterType(IntEnum):
    """Heater hardware type."""

    NONE = 0
    GAS = 1
    SOLAR = 2
    HEATPUMP = 3
    ULTRATEMP = 4
    HYBRID = 5
    MAXETHERM = 6
    MASTERTEMP = 7


HEATER_TYPE_NAMES: dict[int, str] = {
    HeaterType.NONE: "none",
    HeaterType.GAS: "gas",
    HeaterType.SOLAR: "solar",
    HeaterType.HEATPUMP: "heatpump",
    HeaterType.ULTRATEMP: "ultratemp",
    HeaterType.HYBRID: "hybrid",
    HeaterType.MAXETHERM: "maxetherm",
    HeaterType.MASTERTEMP: "mastertemp",
}


# ---------------------------------------------------------------------------
# Temperature units
# ---------------------------------------------------------------------------
class TempUnits(IntEnum):
    """Temperature unit as reported by the panel (payload[9] & 0x04)."""

    FAHRENHEIT = 0
    CELSIUS = 4


TEMP_UNIT_NAMES: dict[int, str] = {
    TempUnits.FAHRENHEIT: "F",
    TempUnits.CELSIUS: "C",
}


# ---------------------------------------------------------------------------
# Chlorinator status codes
# ---------------------------------------------------------------------------
CHLORINATOR_STATUS_NAMES: dict[int, str] = {
    0: "ok",
    1: "low_flow",
    2: "low_salt",
    4: "high_salt",
    8: "clean_cell",
    9: "turning_off",
    16: "high_current",
    32: "low_water_temp",
    64: "check_pcb",
    128: "no_comms",
}


def decode_chlorinator_status(status_byte: int) -> str:
    """Return a human-readable chlorinator status string."""
    return CHLORINATOR_STATUS_NAMES.get(status_byte, f"unknown_{status_byte}")


# ---------------------------------------------------------------------------
# Chlorinator model names
# ---------------------------------------------------------------------------
CHLORINATOR_MODEL_NAMES: dict[str, int] = {
    "intellichlor--40": 1,
    "intellichlor--30": 2,
    "intellichlor--20": 3,
    "ichlor-ic30": 4,
    "ichlor-ic40": 5,
    "ichlor-ic60": 6,
}


# ---------------------------------------------------------------------------
# EasyTouch model identification (from EasyTouchBoard.ts expansionBoards)
# ---------------------------------------------------------------------------
class EasyTouchModel(IntEnum):
    """EasyTouch controller model identifiers (from OCP bytes 27-28)."""

    ET28 = 0  # EasyTouch2 8 shared
    ET28P = 1  # EasyTouch2 8P single
    ET24 = 2  # EasyTouch2 4 shared
    ET24P = 3  # EasyTouch2 4P single
    ETPSL4 = 6  # EasyTouch PSL4 shared
    ETPL4 = 7  # EasyTouch PL4 single
    # EasyTouch 1 models (byte2 == 14 → add 128)
    ET8 = 128  # EasyTouch 8 shared
    ET8P = 129  # EasyTouch 8P single
    ET4 = 130  # EasyTouch 4 shared
    ET4P = 131  # EasyTouch 4P single


EASYTOUCH_MODEL_NAMES: dict[int, str] = {
    EasyTouchModel.ET28: "EasyTouch2 8",
    EasyTouchModel.ET28P: "EasyTouch2 8P",
    EasyTouchModel.ET24: "EasyTouch2 4",
    EasyTouchModel.ET24P: "EasyTouch2 4P",
    EasyTouchModel.ETPSL4: "EasyTouch PSL4",
    EasyTouchModel.ETPL4: "EasyTouch PL4",
    EasyTouchModel.ET8: "EasyTouch 8",
    EasyTouchModel.ET8P: "EasyTouch 8P",
    EasyTouchModel.ET4: "EasyTouch 4",
    EasyTouchModel.ET4P: "EasyTouch 4P",
}


def is_shared_body(model_id: int) -> bool:
    """Return True if the model has shared pool/spa plumbing."""
    return model_id in {
        EasyTouchModel.ET28,
        EasyTouchModel.ET24P,
        EasyTouchModel.ETPSL4,
        EasyTouchModel.ET8,
        EasyTouchModel.ET4,
    }


# ---------------------------------------------------------------------------
# Circuit name table  (EasyTouchBoard.ts circuitNames - factory names)
# ---------------------------------------------------------------------------
CIRCUIT_NAMES: dict[int, str] = {
    1: "Aerator",
    2: "Air Blower",
    3: "AUX 1",
    4: "AUX 2",
    5: "AUX 3",
    6: "AUX 4",
    7: "AUX 5",
    8: "AUX 6",
    9: "AUX 7",
    10: "AUX 8",
    11: "AUX 9",
    12: "AUX 10",
    13: "Backwash",
    14: "Back Light",
    15: "BBQ Light",
    16: "Beach Light",
    17: "Booster Pump",
    18: "Bug Light",
    19: "Cabana Lights",
    20: "Chemical Feeder",
    21: "Chlorinator",
    22: "Cleaner",
    23: "Color Wheel",
    24: "Deck Light",
    25: "Drain Line",
    26: "Drive Light",
    27: "Edge Pump",
    28: "Entry Light",
    29: "Fan",
    30: "Fiber Optic",
    31: "Fiber Works",
    32: "Fill Line",
    33: "Floor Cleaner",
    34: "Fogger",
    35: "Fountain",
    36: "Fountain 1",
    37: "Fountain 2",
    38: "Fountain 3",
    39: "Fountains",
    40: "Front Light",
    41: "Garden Lights",
    42: "Gazebo Lights",
    43: "High Speed",
    44: "Hi-Temp",
    45: "House Light",
    46: "Jets",
    47: "Lights",
    48: "Low Speed",
    49: "Lo-Temp",
    50: "Malibu Lights",
    51: "Mist",
    52: "Music",
    53: "Not Used",
    54: "Ozonator",
    55: "Path Lights",
    56: "Patio Lights",
    57: "Perimeter Light",
    58: "PG2000",
    59: "Pond Light",
    60: "Pool Pump",
    61: "Pool",
    62: "Pool High",
    63: "Pool Light",
    64: "Pool Low",
    65: "SAM",
    66: "Pool SAM 1",
    67: "Pool SAM 2",
    68: "Pool SAM 3",
    69: "Security Light",
    70: "Slide",
    71: "Solar",
    72: "Spa",
    73: "Spa High",
    74: "Spa Light",
    75: "Spa Low",
    76: "Spa SAL",
    77: "Spa SAM",
    78: "Spa Waterfall",
    79: "Spillway",
    80: "Sprinklers",
    81: "Stream",
    82: "Statue Light",
    83: "Swim Jets",
    84: "Water Feature",
    85: "Water Feature Light",
    86: "Waterfall",
    87: "Waterfall 1",
    88: "Waterfall 2",
    89: "Waterfall 3",
    90: "Whirlpool",
    91: "Waterfall Light",
    92: "Yard Light",
    93: "AUX EXTRA",
    94: "Feature 1",
    95: "Feature 2",
    96: "Feature 3",
    97: "Feature 4",
    98: "Feature 5",
    99: "Feature 6",
    100: "Feature 7",
    101: "Feature 8",
}


def get_circuit_name(name_id: int, custom_names: dict[int, str] | None = None) -> str:
    """Return a circuit name from the factory table or custom names.

    Custom names are stored starting at index 200.
    """
    if name_id >= 200 and custom_names:
        return custom_names.get(name_id - 200, f"Custom {name_id - 200}")
    return CIRCUIT_NAMES.get(name_id, f"Circuit {name_id}")


# ---------------------------------------------------------------------------
# Virtual circuits  (SystemBoard.ts)
# ---------------------------------------------------------------------------
VIRTUAL_CIRCUITS: dict[int, str] = {
    128: "Solar",
    129: "Either Heater",
    130: "Pool Heater",
    131: "Spa Heater",
    132: "Freeze",
    133: "Heat Boost",
    134: "Heat Enable",
    135: "Pump Speed +",
    136: "Pump Speed -",
}
