"""The as-of door: cutoffs, rebuilt fields, history, RACE_END and input checks (D-01..D-04)."""

import dataclasses
import inspect
from pathlib import Path

import pandas as pd
import pytest

from f1si.data import _db, asof
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, RaceSnapshot, resolve_slug
from f1si.data.errors import LapOutOfRangeError, UnknownRaceError

FORBIDDEN_COLUMNS = {
    "final_position",
    "classified_position",
    "points",
    "laps_completed",
    "total_time_s",
    "last_lap",
    "n_laps",
    "stint_length",
}
FRAMES = ("entries", "laps", "track_status", "race_control", "weather", "stints", "pit_events")


@pytest.fixture(scope="module")
def accessor(synthetic_db: Path) -> AsOfAccessor:
    return AsOfAccessor(synthetic_db)


@pytest.fixture(scope="module")
def cutoffs(synthetic_db: Path) -> pd.DataFrame:
    return _db.read_table(synthetic_db, "lap_cutoffs", race_id="2023-01")


@pytest.mark.parametrize("lap", range(1, 13))
def test_cutoff_rule_every_lap(accessor: AsOfAccessor, cutoffs: pd.DataFrame, lap: int) -> None:
    snap = accessor.snapshot(AsOf("2023-01", lap))
    expected = float(cutoffs.loc[cutoffs["lap"] == lap, "cutoff_s"].iloc[0])
    assert snap.cutoff_s == expected
    assert bool((snap.laps["lap_end_s"] <= expected).all())
    done = snap.cars["laps_done"].astype(int)
    assert sorted(done.tolist()) == [lap - 1] * 5 + [lap]


def test_lap_zero_shows_only_pre_race_facts(accessor: AsOfAccessor) -> None:
    snap = accessor.snapshot(AsOf("2023-01", 0))
    assert snap.cutoff_s == 0.0
    assert len(snap.laps) == 0
    assert len(snap.entries) == 6
    assert snap.entries["grid_position"].notna().all()
    assert snap.entries["start_compound"].notna().all()
    assert len(snap.weather) >= 1
    assert bool((snap.weather["t_s"] <= 0).all())
    assert bool((snap.race_control["t_s"] <= 0).all())
    assert snap.cars["position"].isna().all()
    assert snap.stints.empty
    assert snap.pit_events.empty


def test_race_end_shows_every_row_without_results(
    accessor: AsOfAccessor, synthetic_db: Path
) -> None:
    snap = accessor.snapshot(AsOf("2023-01", RACE_END))
    assert snap.cutoff_s is None
    total = len(_db.read_table(synthetic_db, "laps", race_id="2023-01"))
    assert len(snap.laps) == total == 6 * 12
    for name in FRAMES:
        assert not FORBIDDEN_COLUMNS & set(getattr(snap, name).columns), name
    assert not FORBIDDEN_COLUMNS & set(snap.cars.columns)
    assert "visible_at_s" not in snap.laps.columns


def test_snapshot_fields_are_exactly_the_documented_ones() -> None:
    names = [f.name for f in dataclasses.fields(RaceSnapshot)]
    assert names == [
        "race",
        "at",
        "cutoff_s",
        "entries",
        "laps",
        "track_status",
        "race_control",
        "weather",
        "stints",
        "pit_events",
        "cars",
    ]


def test_rebuilt_stints_for_driver_10(accessor: AsOfAccessor) -> None:
    snap = accessor.snapshot(AsOf("2023-01", RACE_END))
    rows = snap.stints[snap.stints["driver_number"] == 10].to_dict("records")
    assert rows == [
        {
            "driver_number": 10,
            "stint": 1,
            "compound": "MEDIUM",
            "first_lap": 1,
            "last_visible_lap": 6,
            "laps_so_far": 6,
            "tyre_life_now": 6,
        },
        {
            "driver_number": 10,
            "stint": 2,
            "compound": "HARD",
            "first_lap": 7,
            "last_visible_lap": 12,
            "laps_so_far": 6,
            "tyre_life_now": 6,
        },
    ]


def test_stints_at_lap_3_are_truncated(accessor: AsOfAccessor) -> None:
    snap = accessor.snapshot(AsOf("2023-01", 3))
    assert snap.stints.groupby("driver_number").size().eq(1).all()
    assert bool((snap.stints["last_visible_lap"] <= 3).all())


def test_pit_lane_starter_and_retiree(accessor: AsOfAccessor) -> None:
    snap = accessor.snapshot(AsOf("2023-02", RACE_END))
    cars = snap.cars.set_index("driver_number")
    assert cars.loc[14, "stops_done"] == 1
    assert cars.loc[15, "stops_done"] == 0
    assert cars.loc[15, "laps_done"] == 4
    assert len(snap.pit_events) == 5
    assert (snap.pit_events["in_lap"] == snap.pit_events["out_lap"] - 1).all()
    assert 15 not in set(snap.pit_events["driver_number"])


def test_history_contains_only_earlier_races(accessor: AsOfAccessor) -> None:
    hist = accessor.history(AsOf("2023-02", 5))
    assert hist.races == ["2023-01"]
    assert len(hist.results) == 6
    for name in ("entries", "laps", "track_status", "race_control", "weather", "lap_cutoffs"):
        frame = getattr(hist, name)
        assert set(frame["race_id"]) == {"2023-01"}, name
        assert "visible_at_s" not in frame.columns
    assert set(hist.results["race_id"]) == {"2023-01"}


def test_history_of_first_race_of_a_season_has_both_2023_races(accessor: AsOfAccessor) -> None:
    hist = accessor.history(AsOf("2024-01", 0))
    assert hist.races == ["2023-01", "2023-02"]
    assert set(hist.results["race_id"]) == {"2023-01", "2023-02"}


def test_history_of_first_race_is_empty(accessor: AsOfAccessor) -> None:
    hist = accessor.history(AsOf("2023-01", 3))
    assert hist.races == []
    assert hist.results.empty


def test_unknown_race_and_slug_hints(synthetic_db: Path, accessor: AsOfAccessor) -> None:
    with pytest.raises(UnknownRaceError):
        accessor.snapshot(AsOf("1999-01", 1))
    with pytest.raises(UnknownRaceError, match="alpha-2023"):
        resolve_slug(synthetic_db, "alpah-2023")
    assert resolve_slug(synthetic_db, "alpha-2023") == "2023-01"
    assert resolve_slug(synthetic_db, "2023-01") == "2023-01"


def test_bad_laps_are_rejected(accessor: AsOfAccessor) -> None:
    with pytest.raises(ValueError, match="lap"):
        AsOf("2023-01", -1)
    with pytest.raises(ValueError, match="lap"):
        AsOf("2023-01", True)
    with pytest.raises(LapOutOfRangeError, match="RACE_END"):
        accessor.snapshot(AsOf("2023-01", 13))


def test_injection_string_is_just_an_unknown_race(
    synthetic_db: Path, accessor: AsOfAccessor
) -> None:
    evil = "x'; DROP TABLE laps; --"
    with pytest.raises(UnknownRaceError):
        accessor.snapshot(AsOf(evil, 1))
    with pytest.raises(UnknownRaceError):
        accessor.history(AsOf(evil, 1))
    assert len(_db.read_table(synthetic_db, "laps")) > 0


def test_race_end_repr() -> None:
    assert repr(RACE_END) == "RACE_END"
    assert repr(AsOf("2023-01", RACE_END)).endswith("lap=RACE_END)")


def test_accessor_surface_has_no_flags() -> None:
    assert list(inspect.signature(AsOfAccessor.snapshot).parameters) == ["self", "at"]
    public = [n for n, _ in inspect.getmembers(AsOfAccessor, inspect.isfunction) if n[0] != "_"]
    assert sorted(public) == ["history", "snapshot"]
    assert callable(asof.catalog)
