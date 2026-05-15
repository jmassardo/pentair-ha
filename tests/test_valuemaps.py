"""Tests for value maps and enums."""

from custom_components.pentair_easytouch.protocol.valuemaps import (
    BODY_TYPE_NAMES,
    CIRCUIT_FUNCTION_NAMES,
    CIRCUIT_NAMES,
    EASYTOUCH_MODEL_NAMES,
    HEAT_MODE_NAMES,
    HEAT_STATUS_NAMES,
    LIGHT_THEME_NAMES,
    PANEL_MODE_NAMES,
    PUMP_TYPE_NAMES,
    SCHEDULE_DAY_NAMES,
    SCHEDULE_TYPE_NAMES,
    VIRTUAL_CIRCUITS,
    BodyType,
    CircuitFunction,
    EasyTouchModel,
    FeatureFunction,
    HeaterType,
    HeatMode,
    HeatStatus,
    LightTheme,
    PanelMode,
    PumpType,
    ScheduleDay,
    ScheduleType,
    TempUnits,
    decode_chlorinator_status,
    decode_schedule_days,
    get_circuit_name,
    is_light_function,
    is_shared_body,
)


class TestHeatMode:
    def test_values(self) -> None:
        assert int(HeatMode.OFF) == 0
        assert int(HeatMode.HEATER) == 1
        assert int(HeatMode.SOLAR_PREFERRED) == 2
        assert int(HeatMode.SOLAR_ONLY) == 3

    def test_names(self) -> None:
        assert HEAT_MODE_NAMES[0] == "off"
        assert HEAT_MODE_NAMES[3] == "solar_only"


class TestHeatStatus:
    def test_values(self) -> None:
        assert int(HeatStatus.OFF) == 0
        assert int(HeatStatus.HEATER) == 1
        assert int(HeatStatus.COOLING) == 2
        assert int(HeatStatus.SOLAR) == 3
        assert int(HeatStatus.HEATPUMP) == 4
        assert int(HeatStatus.DUAL) == 5

    def test_names(self) -> None:
        assert HEAT_STATUS_NAMES[0] == "off"
        assert HEAT_STATUS_NAMES[5] == "dual"


class TestPanelMode:
    def test_values(self) -> None:
        assert int(PanelMode.AUTO) == 0
        assert int(PanelMode.SERVICE) == 1
        assert int(PanelMode.FREEZE) == 8
        assert int(PanelMode.TIMEOUT) == 128
        assert int(PanelMode.SERVICE_TIMEOUT) == 129
        assert int(PanelMode.ERROR) == 255

    def test_names(self) -> None:
        assert PANEL_MODE_NAMES[0] == "auto"
        assert PANEL_MODE_NAMES[129] == "service-timeout"


class TestCircuitFunction:
    def test_key_values(self) -> None:
        assert int(CircuitFunction.GENERIC) == 0
        assert int(CircuitFunction.SPA) == 1
        assert int(CircuitFunction.POOL) == 2
        assert int(CircuitFunction.INTELLIBRITE) == 16
        assert int(CircuitFunction.MAGICSTREAM) == 17

    def test_names(self) -> None:
        assert CIRCUIT_FUNCTION_NAMES[0] == "generic"
        assert CIRCUIT_FUNCTION_NAMES[16] == "intellibrite"

    def test_is_light(self) -> None:
        assert is_light_function(CircuitFunction.LIGHT)
        assert is_light_function(CircuitFunction.INTELLIBRITE)
        assert is_light_function(CircuitFunction.MAGICSTREAM)
        assert not is_light_function(CircuitFunction.GENERIC)
        assert not is_light_function(CircuitFunction.POOL)
        assert not is_light_function(CircuitFunction.SPA)


class TestPumpType:
    def test_values(self) -> None:
        assert int(PumpType.VF) == 1
        assert int(PumpType.VS) == 128
        assert int(PumpType.VSF) == 64
        assert int(PumpType.SS) == 257

    def test_names(self) -> None:
        assert PUMP_TYPE_NAMES[PumpType.VF] == "vf"
        assert PUMP_TYPE_NAMES[PumpType.VS] == "vs"


class TestLightTheme:
    def test_values(self) -> None:
        assert int(LightTheme.PARTY) == 177
        assert int(LightTheme.ROMANCE) == 178
        assert int(LightTheme.CARIBBEAN) == 179
        assert int(LightTheme.AMERICAN) == 180
        assert int(LightTheme.BLUE) == 193
        assert int(LightTheme.GREEN) == 194
        assert int(LightTheme.COLOR_SYNC) == 128
        assert int(LightTheme.COLOR_SWIM) == 144

    def test_names(self) -> None:
        assert LIGHT_THEME_NAMES[177] == "party"
        assert LIGHT_THEME_NAMES[193] == "blue"


class TestBodyType:
    def test_values(self) -> None:
        assert int(BodyType.POOL) == 0
        assert int(BodyType.SPA) == 1
        assert BODY_TYPE_NAMES[0] == "pool"
        assert BODY_TYPE_NAMES[1] == "spa"


class TestSchedule:
    def test_schedule_type(self) -> None:
        assert int(ScheduleType.REPEAT) == 0
        assert int(ScheduleType.RUN_ONCE) == 26
        assert SCHEDULE_TYPE_NAMES[0] == "repeat"
        assert SCHEDULE_TYPE_NAMES[26] == "run_once"

    def test_schedule_days(self) -> None:
        assert int(ScheduleDay.SUNDAY) == 1
        assert int(ScheduleDay.MONDAY) == 2
        assert int(ScheduleDay.SATURDAY) == 64

    def test_decode_schedule_days(self) -> None:
        # Monday + Wednesday + Friday = 2 + 8 + 32 = 42
        days = decode_schedule_days(42)
        assert "monday" in days
        assert "wednesday" in days
        assert "friday" in days
        assert len(days) == 3

    def test_decode_schedule_days_all(self) -> None:
        days = decode_schedule_days(0x7F)
        assert len(days) == 7

    def test_decode_schedule_days_none(self) -> None:
        days = decode_schedule_days(0)
        assert len(days) == 0


class TestHeaterType:
    def test_values(self) -> None:
        assert int(HeaterType.NONE) == 0
        assert int(HeaterType.GAS) == 1
        assert int(HeaterType.SOLAR) == 2
        assert int(HeaterType.HYBRID) == 5


class TestTempUnits:
    def test_values(self) -> None:
        assert int(TempUnits.FAHRENHEIT) == 0
        assert int(TempUnits.CELSIUS) == 4


class TestFeatureFunction:
    def test_values(self) -> None:
        assert int(FeatureFunction.GENERIC) == 0
        assert int(FeatureFunction.SPILLWAY) == 14


class TestChlorinatorStatus:
    def test_known_statuses(self) -> None:
        assert decode_chlorinator_status(0) == "ok"
        assert decode_chlorinator_status(128) == "no_comms"
        assert decode_chlorinator_status(8) == "clean_cell"

    def test_unknown_status(self) -> None:
        result = decode_chlorinator_status(99)
        assert result.startswith("unknown_")


class TestEasyTouchModel:
    def test_values(self) -> None:
        assert int(EasyTouchModel.ET28) == 0
        assert int(EasyTouchModel.ET8) == 128

    def test_names(self) -> None:
        assert EASYTOUCH_MODEL_NAMES[0] == "EasyTouch2 8"
        assert EASYTOUCH_MODEL_NAMES[128] == "EasyTouch 8"

    def test_is_shared_body(self) -> None:
        assert is_shared_body(EasyTouchModel.ET28)
        assert not is_shared_body(EasyTouchModel.ET28P)
        assert is_shared_body(EasyTouchModel.ET8)


class TestCircuitNames:
    def test_known_names(self) -> None:
        assert CIRCUIT_NAMES[61] == "Pool"
        assert CIRCUIT_NAMES[72] == "Spa"
        assert CIRCUIT_NAMES[63] == "Pool Light"

    def test_get_circuit_name_factory(self) -> None:
        assert get_circuit_name(61) == "Pool"

    def test_get_circuit_name_custom(self) -> None:
        custom = {0: "My Custom"}
        assert get_circuit_name(200, custom) == "My Custom"

    def test_get_circuit_name_unknown(self) -> None:
        result = get_circuit_name(999)
        assert result == "Circuit 999"


class TestVirtualCircuits:
    def test_known_values(self) -> None:
        assert VIRTUAL_CIRCUITS[128] == "Solar"
        assert VIRTUAL_CIRCUITS[132] == "Freeze"


class TestChlorinatorModelNames:
    def test_known_model(self) -> None:
        from custom_components.pentair_easytouch.protocol.valuemaps import (
            CHLORINATOR_MODEL_NAMES,
        )

        assert CHLORINATOR_MODEL_NAMES["intellichlor--40"] == 1
        assert CHLORINATOR_MODEL_NAMES["ichlor-ic30"] == 4


class TestScheduleDayNames:
    def test_all_days_present(self) -> None:
        assert len(SCHEDULE_DAY_NAMES) == 7
        assert 1 in SCHEDULE_DAY_NAMES
        assert 64 in SCHEDULE_DAY_NAMES
