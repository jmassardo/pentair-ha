"""Additional tests for PoolState helper accessors."""

import pytest

from custom_components.pentair_easytouch.model import (
    Feature,
    Heater,
    PoolState,
    Pump,
    Schedule,
    Valve,
)


@pytest.mark.parametrize(
    ("getter_name", "collection_name", "cls"),
    [
        ("get_heater", "heaters", Heater),
        ("get_valve", "valves", Valve),
        ("get_schedule", "schedules", Schedule),
    ],
)
def test_getter_creates_missing_object(getter_name: str, collection_name: str, cls: type) -> None:
    state = PoolState()

    item = getattr(state, getter_name)(3)

    assert isinstance(item, cls)
    assert item.id == 3
    assert getattr(state, collection_name) == [item]


@pytest.mark.parametrize(
    ("getter_name", "collection_name", "existing"),
    [
        ("get_feature", "features", Feature(id=3, name="Waterfall")),
        ("get_pump", "pumps", Pump(id=3, name="Pump 3")),
        ("get_heater", "heaters", Heater(id=3, name="Gas Heater")),
        ("get_valve", "valves", Valve(id=3, name="Waterfall Valve")),
        ("get_schedule", "schedules", Schedule(id=3, circuit=6)),
    ],
)
def test_getter_returns_existing_object(
    getter_name: str,
    collection_name: str,
    existing: Feature | Pump | Heater | Valve | Schedule,
) -> None:
    state = PoolState()
    getattr(state, collection_name).append(existing)

    found = getattr(state, getter_name)(3)

    assert found is existing
    assert len(getattr(state, collection_name)) == 1
