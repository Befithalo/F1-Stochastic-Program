"""The lap clock is validated before cutoffs are derived (WR-03).

One bad `lap_end_s` used to pull every earlier cutoff down to it (the reverse cumulative minimum
only ever lowers a cutoff). The loader now drops ends that cannot be right, says so, and keeps
look-ahead safe: a dropped end makes its lap visible only at the race end.
"""

import itertools
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from f1si import paths
from f1si.data import _db
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.data.derive import (
    MAX_LAP_END_S,
    _longest_increasing,
    cutoff_repairs,
    derive_lap_cutoffs,
    sanitize_lap_ends,
)
from f1si.data.loader import load_races
from f1si.data.sources import NormalizedRace, RaceRef
from f1si.rng import DEFAULT_SEED, make_rng
from f1si.synthetic import default_specs, generate_dataset

NOW = datetime(2026, 10, 22, tzinfo=UTC)
RACE_ID = "2023-01"


def _laps(rows: list[tuple[int, int, float]]) -> pd.DataFrame:
    """Rows of (driver, lap_number, lap_end_s)."""
    return pd.DataFrame(
        {
            "driver_number": [r[0] for r in rows],
            "lap_number": [r[1] for r in rows],
            "lap_end_s": [r[2] for r in rows],
        }
    )


def _grid_laps(n_drivers: int = 3, n_laps: int = 12) -> list[tuple[int, int, float]]:
    return [
        (d, lap, 90.0 * lap + 2.0 * d)
        for d in range(1, n_drivers + 1)
        for lap in range(1, n_laps + 1)
    ]


# ---- the sanitizer ----------------------------------------------------------------------------


def test_clean_laps_are_untouched() -> None:
    laps = _laps(_grid_laps())
    out, notes = sanitize_lap_ends(laps)
    pd.testing.assert_series_equal(out["lap_end_s"].astype("float64"), laps["lap_end_s"])
    assert notes == []


def test_one_early_outlier_no_longer_collapses_earlier_cutoffs() -> None:
    """The reviewer's case: lap 10 of one car ends at 100 s."""
    rows = _grid_laps()
    clean = derive_lap_cutoffs("R", _laps(rows))
    broken = [(d, n, 100.0 if (d, n) == (2, 10) else t) for d, n, t in rows]
    # without the fix the earlier cutoffs collapse, as the review showed
    collapsed = derive_lap_cutoffs("R", _laps(broken))
    assert collapsed["cutoff_s"].iloc[2:11].eq(100.0).all()
    out, notes = sanitize_lap_ends(_laps(broken))
    assert out["lap_end_s"].isna().sum() == 1
    assert (
        out.loc[(out["driver_number"] == 2) & (out["lap_number"] == 10), "lap_end_s"].isna().all()
    )
    assert any("driver 2 lap 10" in n for n in notes)
    fixed = derive_lap_cutoffs("R", out)
    pd.testing.assert_frame_equal(fixed, clean)  # the others still end lap 10 at the right time


def test_one_late_outlier_is_the_one_dropped() -> None:
    rows = _grid_laps()
    broken = [(d, n, 5000.0 if (d, n) == (1, 5) else t) for d, n, t in rows]
    out, _ = sanitize_lap_ends(_laps(broken))
    dropped = out[out["lap_end_s"].isna()]
    assert dropped[["driver_number", "lap_number"]].to_numpy().tolist() == [[1, 5]]


@pytest.mark.parametrize("bad", [-1327.2, float("inf"), float("-inf"), MAX_LAP_END_S + 1.0])
def test_values_outside_the_race_clock_are_dropped(bad: float) -> None:
    rows = _grid_laps()
    broken = [(d, n, bad if (d, n) == (3, 4) else t) for d, n, t in rows]
    out, notes = sanitize_lap_ends(_laps(broken))
    assert out["lap_end_s"].isna().sum() == 1
    assert len(notes) == 1


def test_missing_ends_are_left_alone_and_ties_are_dropped() -> None:
    laps = _laps([(1, 1, 90.0), (1, 2, float("nan")), (1, 3, 270.0), (2, 1, 90.0), (2, 2, 90.0)])
    out, _ = sanitize_lap_ends(laps)
    assert out["lap_end_s"].isna().sum() == 2  # the original NaN and one of the tied pair


def test_only_a_note_limit_is_listed() -> None:
    rows = [(1, n, float(100 - n)) for n in range(1, 21)]  # strictly decreasing: 19 must go
    out, notes = sanitize_lap_ends(_laps(rows))
    assert out["lap_end_s"].notna().sum() == 1
    assert len(notes) == 6
    assert notes[-1].startswith("and ")


@given(st.lists(st.floats(0, 1000, allow_nan=False), max_size=9))
def test_longest_increasing_is_increasing_and_maximal(values: list[float]) -> None:
    arr = np.array(values, dtype="float64")
    keep = _longest_increasing(arr)
    kept = arr[keep]
    assert bool(np.all(np.diff(kept) > 0))
    best = max(
        (
            len(sub)
            for r in range(len(values) + 1)
            for sub in itertools.combinations(values, r)
            if all(a < b for a, b in itertools.pairwise(sub))
        ),
        default=0,
    )
    assert len(kept) == best


@given(
    st.lists(
        st.tuples(
            st.integers(1, 3), st.integers(1, 8), st.floats(-50, 1000) | st.just(float("nan"))
        ),
        max_size=24,
        unique_by=lambda r: (r[0], r[1]),
    )
)
def test_sanitize_only_removes_values_and_leaves_a_monotone_clock(
    rows: list[tuple[int, int, float]],
) -> None:
    laps = _laps(rows)
    out, _ = sanitize_lap_ends(laps)
    before, after = laps["lap_end_s"].to_numpy(), out["lap_end_s"].to_numpy(dtype="float64")
    kept = ~np.isnan(after)
    assert np.array_equal(before[kept], after[kept])  # nothing was changed, only removed
    for _, group in out.sort_values("lap_number").groupby("driver_number"):
        ends = group["lap_end_s"].dropna().to_numpy(dtype="float64")
        assert bool(np.all(np.diff(ends) > 0))
        assert bool(np.all(ends >= 0))
    derived = derive_lap_cutoffs("R", out.assign(lap_start_s=0.0))
    assert derived["cutoff_s"].is_monotonic_increasing


def test_cutoff_repairs_reports_laps_lowered_by_a_missing_leader_end() -> None:
    laps = _laps([(1, 1, 90.0), (1, 2, 180.0), (2, 3, 150.0)])
    assert cutoff_repairs(laps) == [2]
    assert cutoff_repairs(_laps(_grid_laps())) == []


# ---- through the loader and the as-of door ----------------------------------------------------


class _OneRaceSource:
    """A source that serves the first synthetic race with its laps table replaced."""

    name = "synthetic"
    version = "clock-test"
    default_seasons = (2023,)

    def __init__(self, laps: pd.DataFrame) -> None:
        base = generate_dataset(default_specs(), rng=make_rng(DEFAULT_SEED))[0].race
        self._race = NormalizedRace(ref=base.ref, tables={**base.tables, "laps": laps})

    def list_races(self, season: int, *, now: datetime) -> list[RaceRef]:
        return [self._race.ref] if season == self._race.ref.season else []

    def fetch(self, ref: RaceRef) -> NormalizedRace:
        return self._race


def _base_laps() -> pd.DataFrame:
    return (
        generate_dataset(default_specs(), rng=make_rng(DEFAULT_SEED))[0].race.tables["laps"].copy()
    )


def _load(laps: pd.DataFrame, folder: Path) -> tuple[Path, list[str], int]:
    lines: list[str] = []
    db = paths.db_path(folder)
    report = load_races(
        _OneRaceSource(laps), db, (2023,), now=NOW, echo=lines.append, sleep=lambda _s: None
    )
    return db, lines, len(report.failed)


def test_loader_drops_the_glitch_keeps_cutoffs_and_stays_look_ahead_safe(tmp_path: Path) -> None:
    clean_db, _, failed = _load(_base_laps(), tmp_path / "clean")
    assert failed == 0
    glitched = _base_laps()
    victim = glitched.index[(glitched["driver_number"] == 12) & (glitched["lap_number"] == 10)][0]
    glitched.loc[victim, ["lap_start_s", "lap_end_s"]] = [10.0, 100.0]  # a feed glitch
    db, lines, failed = _load(glitched, tmp_path / "glitched")
    assert failed == 0
    assert any("note: dropped 1 lap end time(s)" in line and "lap 10" in line for line in lines)

    clean_cut = _db.read_table(clean_db, "lap_cutoffs", race_id=RACE_ID)
    cut = _db.read_table(db, "lap_cutoffs", race_id=RACE_ID)
    pd.testing.assert_frame_equal(cut, clean_cut)

    laps = _db.read_table(db, "laps", race_id=RACE_ID)
    row = laps[(laps["driver_number"] == 12) & (laps["lap_number"] == 10)]
    assert row["visible_at_s"].isna().all()  # visible only at the race end

    accessor = AsOfAccessor(db)
    for lap in (9, 10, 12):
        snap = accessor.snapshot(AsOf(RACE_ID, lap))
        assert not ((snap.laps["driver_number"] == 12) & (snap.laps["lap_number"] == 10)).any()
        assert snap.cutoff_s == float(clean_cut.loc[clean_cut["lap"] == lap, "cutoff_s"].iloc[0])
    end = accessor.snapshot(AsOf(RACE_ID, RACE_END))
    assert ((end.laps["driver_number"] == 12) & (end.laps["lap_number"] == 10)).any()


def test_loader_rejects_a_race_whose_clock_is_mostly_broken(tmp_path: Path) -> None:
    laps = _base_laps()
    laps["lap_end_s"] = laps["lap_end_s"].astype("float64")
    laps.loc[laps["driver_number"] != laps["driver_number"].iloc[0], "lap_end_s"] = 1e9
    _, lines, failed = _load(laps, tmp_path)
    assert failed == 1
    assert any("break the race clock" in line and "looks corrupt" in line for line in lines)
