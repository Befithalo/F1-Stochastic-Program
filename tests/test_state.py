"""RaceState and CarState: frozen plain data, JSON round trip, validation (INT-03)."""

import dataclasses
import json
import math
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

import f1si.state
from f1si.interfaces import PitDecision, Plan
from f1si.state import CarState, RaceState

CAR_KEYS = {
    "driver",
    "position",
    "gap_ahead_s",
    "gap_behind_s",
    "compound",
    "tire_age",
    "wear_rate_s_per_lap",
    "wear_sd",
    "pace_offset_s",
    "stops_done",
    "compounds_used",
    "driver_number",
}


def _car(code: str = "ALO", number: int = 14, **over: Any) -> CarState:
    fields: dict[str, Any] = {
        "driver": code,
        "driver_number": number,
        "position": 2,
        "gap_ahead_s": 1.5,
        "gap_behind_s": None,
        "compound": "MEDIUM",
        "tire_age": 9,
        "wear_rate_s_per_lap": 0.07,
        "wear_sd": 0.01,
        "pace_offset_s": -0.2,
        "stops_done": 0,
        "compounds_used": ("MEDIUM",),
    }
    fields.update(over)
    return CarState(**fields)


def _state(**over: Any) -> RaceState:
    fields: dict[str, Any] = {
        "lap": 10,
        "laps_total": 57,
        "regime": {"green": 1.0},
        "pit_loss_s": {"green": 22.0},
        "cars": (_car(), _car("VER", 1, position=1, gap_ahead_s=None, gap_behind_s=1.5)),
    }
    fields.update(over)
    return RaceState(**fields)


def test_frozen_and_read_only_containers() -> None:
    state = _state()
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.lap = 3  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.cars[0].tire_age = 3  # type: ignore[misc]
    with pytest.raises(TypeError):
        state.regime["green"] = 0.5  # type: ignore[index]
    with pytest.raises(TypeError):
        state.pit_loss_s["green"] = 1.0  # type: ignore[index]
    assert isinstance(state.cars, tuple)


def test_json_keys_match_build_plan_plus_driver_number() -> None:
    data = _state().to_json_dict()
    assert set(data) == {"lap", "laps_total", "regime", "pit_loss_s", "cars"}
    for car in data["cars"]:
        assert set(car) == CAR_KEYS


def test_round_trip_hand_built() -> None:
    state = _state()
    assert RaceState.from_json(state.to_json()) == state
    assert RaceState.from_json_dict(state.to_json_dict()) == state


_opt_float = st.none() | st.floats(min_value=-1e6, max_value=1e6, allow_nan=False)


@st.composite
def _cars(draw: st.DrawFn) -> tuple[CarState, ...]:
    n = draw(st.integers(0, 5))
    codes = draw(
        st.lists(st.text("ABCDEFGHIJ", min_size=3, max_size=3), min_size=n, max_size=n, unique=True)
    )
    return tuple(
        CarState(
            driver=code,
            driver_number=draw(st.integers(1, 99)),
            position=draw(st.none() | st.integers(1, 20)),
            gap_ahead_s=draw(_opt_float),
            gap_behind_s=draw(_opt_float),
            compound=draw(st.none() | st.sampled_from(["SOFT", "MEDIUM", "HARD"])),
            tire_age=draw(st.integers(0, 60)),
            wear_rate_s_per_lap=draw(_opt_float),
            wear_sd=draw(_opt_float),
            pace_offset_s=draw(_opt_float),
            stops_done=draw(st.integers(0, 3)),
            compounds_used=tuple(draw(st.lists(st.sampled_from(["SOFT", "HARD"]), max_size=3))),
        )
        for code in codes
    )


@given(cars=_cars(), laps_total=st.integers(1, 80), data=st.data())
def test_round_trip_hypothesis(
    cars: tuple[CarState, ...], laps_total: int, data: st.DataObject
) -> None:
    lap = data.draw(st.integers(0, laps_total))
    state = RaceState(
        lap=lap,
        laps_total=laps_total,
        regime={"green": 1.0},
        pit_loss_s={"green": 22.5},
        cars=cars,
    )
    assert RaceState.from_json(state.to_json()) == state


def test_nan_and_inf_are_rejected_with_field_name() -> None:
    with pytest.raises(ValueError, match="wear_sd"):
        _car(wear_sd=math.nan)
    with pytest.raises(ValueError, match="gap_ahead_s"):
        _car(gap_ahead_s=math.inf)


def test_to_json_never_writes_nan() -> None:
    text = _state().to_json()
    assert "NaN" not in text
    assert json.loads(text)["cars"][0]["gap_behind_s"] is None
    with pytest.raises(ValueError, match="NaN"):
        RaceState.from_json(text.replace("null", "NaN", 1))


@pytest.mark.parametrize(
    ("over", "needle"),
    [
        ({"lap": -1}, "-1"),
        ({"laps_total": 0}, "0"),
        ({"lap": 60}, "60"),
        ({"regime": {"green": 0.5}}, "0.5"),
        ({"pit_loss_s": {"green": 0.0}}, "0.0"),
        ({"pit_loss_s": {"green": -3.0}}, "-3.0"),
        ({"cars": (_car(), _car())}, "ALO"),
        ({"lap": True}, "True"),
    ],
)
def test_race_state_validation(over: dict[str, Any], needle: str) -> None:
    with pytest.raises(ValueError, match=needle):
        _state(**over)


@pytest.mark.parametrize(
    ("over", "needle"),
    [({"tire_age": -2}, "-2"), ({"tire_age": True}, "True"), ({"driver": "al"}, "'al'")],
)
def test_car_validation(over: dict[str, Any], needle: str) -> None:
    with pytest.raises(ValueError, match=needle):
        _car(**over)


def test_from_json_dict_errors_name_the_key() -> None:
    data = _state().to_json_dict()
    del data["lap"]
    with pytest.raises(ValueError, match="RaceState JSON: missing key 'lap'"):
        RaceState.from_json_dict(data)
    data = _state().to_json_dict()
    data["extra"] = 1
    with pytest.raises(ValueError, match="unknown key"):
        RaceState.from_json_dict(data)
    data = _state().to_json_dict()
    data["cars"][0]["tire_age"] = True
    with pytest.raises(ValueError, match="tire_age"):
        RaceState.from_json_dict(data)
    with pytest.raises(ValueError, match="not valid JSON"):
        RaceState.from_json("{")


def test_to_arrays_read_only_and_ordered() -> None:
    state = _state(cars=(_car(), _car("VER", 1, position=None, compound=None)))
    arrays = state.to_arrays()
    assert arrays.driver_number.tolist() == [14, 1]
    assert arrays.position.dtype == np.int64
    assert arrays.position.tolist() == [2, -1]
    assert math.isnan(arrays.gap_behind_s[0])
    assert arrays.compound.tolist() == ["MEDIUM", ""]
    for arr in (
        arrays.driver_number,
        arrays.position,
        arrays.gap_ahead_s,
        arrays.gap_behind_s,
        arrays.tire_age,
        arrays.wear_rate_s_per_lap,
        arrays.wear_sd,
        arrays.pace_offset_s,
        arrays.stops_done,
        arrays.compound,
    ):
        assert arr.flags.writeable is False
        assert len(arr) == 2


def test_car_lookup() -> None:
    state = _state()
    assert state.car("ALO").driver_number == 14
    with pytest.raises(ValueError, match="ALO, VER"):
        state.car("XXX")


def test_placeholders_are_named_in_module_docstring() -> None:
    doc = f1si.state.__doc__ or ""
    assert "regime" in doc
    assert doc.lower().count("placeholder") >= 2
    assert "pit_loss_s" in doc


def test_plan_validation() -> None:
    assert Plan((10, 30), ("HARD", "SOFT"), 5000.0).n_stops == 2
    with pytest.raises(ValueError, match="strictly increasing"):
        Plan((10, 10), ("HARD", "SOFT"), 1.0)
    with pytest.raises(ValueError, match="strictly increasing"):
        Plan((0,), ("HARD",), 1.0)
    with pytest.raises(ValueError, match="same length"):
        Plan((10,), (), 1.0)


def test_pit_decision_best_plan_is_first() -> None:
    a, b = Plan((10,), ("HARD",), 1.0), Plan((), (), 2.0)
    assert PitDecision("ALO", 10, False, None, a, (a, b)).best_plan == a
    with pytest.raises(ValueError, match="best_plan"):
        PitDecision("ALO", 10, False, None, b, (a, b))
