"""Review fix WR-03: laps with no stint number are dropped, not merged (DEC-070)."""

from dataclasses import replace
from pathlib import Path

import numpy as np

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, RaceSnapshot
from f1si.pace.linear import fit_linear_pace
from tests.conftest import LONG_RACE_ID


def _snap(db: Path) -> RaceSnapshot:
    return AsOfAccessor(db).snapshot(AsOf(LONG_RACE_ID, RACE_END))


def test_laps_without_stint_are_dropped_with_a_reason(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db)
    laps = snap.laps.copy()
    laps["stint"] = np.nan
    fit = fit_linear_pace(replace(snap, laps=laps))
    assert fit.report.dropped.get("no stint", 0) > 100
    assert not fit.is_identified  # nothing is left to fit; before the fix every lap sat in stint 0


def test_missing_stint_laps_do_not_inflate_stint_counts(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db)
    base = fit_linear_pace(snap).report
    laps = snap.laps.copy()
    hit = laps["driver_number"].astype(int).isin([10, 11, 12]).to_numpy()
    laps["stint"] = laps["stint"].astype("Float64")
    laps.loc[hit, "stint"] = np.nan
    report = fit_linear_pace(replace(snap, laps=laps)).report
    assert report.dropped.get("no stint", 0) > 0
    assert report.n_clean < base.n_clean
    # the three drivers' laps left the fit; they did not become one pseudo-stint each
    assert not {10, 11, 12} & set(report.driver_offsets)
    base_stints = {c.compound: c.n_stints for c in base.compounds}
    for c in report.compounds:
        assert c.n_stints <= base_stints[c.compound] - 3
