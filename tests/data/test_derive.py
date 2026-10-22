"""Lap cutoffs and per-lap track status derivations."""

import math

import pandas as pd
import pytest

from f1si.data.derive import annotate_lap_track_status, derive_lap_cutoffs

NAN = float("nan")


def _laps(rows: list[tuple[int, int, float, float]]) -> pd.DataFrame:
    """Rows of (driver, lap_number, lap_start_s, lap_end_s)."""
    return pd.DataFrame(
        {
            "driver_number": [r[0] for r in rows],
            "lap_number": [r[1] for r in rows],
            "lap_start_s": [r[2] for r in rows],
            "lap_end_s": [r[3] for r in rows],
        }
    )


def _status(rows: list[tuple[float, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "seq": list(range(len(rows))),
            "t_s": [r[0] for r in rows],
            "status": [r[1] for r in rows],
        }
    )


def test_cutoffs_take_the_leader_end_per_lap() -> None:
    laps = _laps(
        [
            (1, 1, 0.0, 90.0),
            (2, 1, 0.0, 93.0),
            (1, 2, 90.0, 180.0),
            (2, 2, 93.0, 185.0),
        ]
    )
    out = derive_lap_cutoffs("R", laps)
    assert list(out.columns) == ["race_id", "lap", "cutoff_s"]
    assert out["lap"].tolist() == [0, 1, 2]
    assert out["cutoff_s"].tolist() == [0.0, 90.0, 180.0]
    assert set(out["race_id"]) == {"R"}


def test_missing_lap_end_takes_the_next_lap_value() -> None:
    laps = _laps([(1, 1, 0.0, 90.0), (1, 2, 90.0, NAN), (1, 3, 180.0, 270.0)])
    out = derive_lap_cutoffs("R", laps)
    assert out["cutoff_s"].tolist() == [0.0, 90.0, 270.0, 270.0]
    assert out["lap"].tolist() == [0, 1, 2, 3]


def test_trailing_laps_without_an_end_are_dropped() -> None:
    laps = _laps([(1, 1, 0.0, 90.0), (1, 2, 90.0, NAN)])
    out = derive_lap_cutoffs("R", laps)
    assert out["lap"].tolist() == [0, 1]
    assert all(math.isfinite(v) for v in out["cutoff_s"])


def test_anomaly_lowers_the_earlier_cutoff_and_never_raises() -> None:
    # lap 3's earliest end (150) is before lap 2's earliest end (180): reverse cumulative minimum
    laps = _laps([(1, 1, 0.0, 90.0), (1, 2, 90.0, 180.0), (2, 3, 100.0, 150.0)])
    out = derive_lap_cutoffs("R", laps)
    assert out["cutoff_s"].tolist() == [0.0, 90.0, 150.0, 150.0]
    raw_min = laps.groupby("lap_number")["lap_end_s"].min()
    for lap, value in zip(out["lap"], out["cutoff_s"], strict=True):
        if lap in raw_min.index:
            assert value <= raw_min[lap]


def test_cutoffs_are_non_decreasing() -> None:
    laps = _laps([(1, n, 0.0, float(v)) for n, v in [(1, 90), (2, 70), (3, 200), (4, 100)]])
    out = derive_lap_cutoffs("R", laps)
    assert out["cutoff_s"].is_monotonic_increasing


def test_track_status_all_green_lap() -> None:
    laps = _laps([(1, 1, 0.0, 90.0)])
    out = annotate_lap_track_status(laps, _status([(0.0, "1")]))
    assert out.tolist() == ["1"]


def test_track_status_changes_inside_a_lap() -> None:
    laps = _laps([(1, 1, 0.0, 90.0), (1, 2, 90.0, 180.0), (1, 3, 180.0, 270.0)])
    status = _status([(0.0, "1"), (100.0, "6"), (150.0, "7"), (200.0, "1")])
    out = annotate_lap_track_status(laps, status)
    assert out.tolist() == ["1", "167", "71"]


def test_track_status_lap_starting_under_vsc_without_change() -> None:
    laps = _laps([(1, 1, 100.0, 120.0)])
    out = annotate_lap_track_status(laps, _status([(0.0, "1"), (50.0, "6"), (200.0, "1")]))
    assert out.tolist() == ["6"]


def test_track_status_collapses_consecutive_duplicates() -> None:
    laps = _laps([(1, 1, 0.0, 90.0)])
    out = annotate_lap_track_status(laps, _status([(10.0, "2"), (20.0, "2"), (30.0, "1")]))
    assert out.tolist() == ["121"]


def test_track_status_na_when_lap_start_or_end_is_missing() -> None:
    laps = _laps([(1, 1, 0.0, NAN), (1, 2, NAN, 10.0), (1, 3, 0.0, 5.0)])
    out = annotate_lap_track_status(laps, _status([(0.0, "1")]))
    assert out.isna().tolist() == [True, True, False]


def test_track_status_defaults_to_green_without_rows() -> None:
    laps = _laps([(1, 1, 0.0, 90.0)])
    out = annotate_lap_track_status(laps, _status([]))
    assert out.tolist() == ["1"]


def test_track_status_uses_only_rows_up_to_the_lap_end() -> None:
    """A change after the lap end must not leak into the lap's value (knowable at lap end)."""
    laps = _laps([(1, 1, 0.0, 90.0)])
    with_future = annotate_lap_track_status(laps, _status([(0.0, "1"), (91.0, "4")]))
    without = annotate_lap_track_status(laps, _status([(0.0, "1")]))
    assert with_future.tolist() == without.tolist() == ["1"]


@pytest.mark.parametrize("t", [0.0, 90.0])
def test_status_exactly_at_lap_boundaries(t: float) -> None:
    """A change at lap_start counts as the starting status; at lap_end it is inside the lap."""
    laps = _laps([(1, 1, 0.0, 90.0)])
    out = annotate_lap_track_status(laps, _status([(t, "2")]))
    assert out.tolist() == (["2"] if t == 0.0 else ["12"])
