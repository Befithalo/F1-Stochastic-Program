"""The standard error of the driver offsets is exposed and honest (D-12 plumbing)."""

from pathlib import Path

import numpy as np

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.pace.linear import FitReport, LinearPaceFit, fit_linear_pace
from f1si.rng import make_rng
from f1si.synthetic import SyntheticTruth, generate_dataset
from tests.conftest import LONG_RACE_ID, build_long_db, long_specs


def _fit(db: Path) -> LinearPaceFit:
    snap = AsOfAccessor(db).snapshot(AsOf(LONG_RACE_ID, RACE_END))
    return fit_linear_pace(snap)


def test_offset_se_per_driver(long_synthetic_db: Path) -> None:
    fit = _fit(long_synthetic_db)
    r = fit.report
    assert set(r.driver_offset_se) == set(r.driver_offsets)
    assert r.driver_offsets
    for number, se in r.driver_offset_se.items():
        assert np.isfinite(se)
        assert se > 0
        assert fit.pace_offset_se(number) == se
    assert fit.pace_offset_se(9999) is None


def test_offset_se_empty_when_unidentified() -> None:
    report = FitReport(None, None, None, None, (), (), (), {}, None, 0, 0, 0, {}, "x")
    fit = LinearPaceFit(report)
    assert report.driver_offset_se == {}
    assert fit.pace_offset_se(1) is None


def test_offset_se_covers_truth_in_most_pairs(tmp_path: Path) -> None:
    hits = 0
    total = 0
    for seed in range(6):
        db = build_long_db(tmp_path / f"seed{seed}", seed)
        fit = _fit(db)
        truth: SyntheticTruth = generate_dataset(long_specs(), rng=make_rng(seed))[0].truth
        mean_true = float(np.mean(list(truth.driver_pace_offset_s.values())))
        r = fit.report
        mean_fit = float(np.mean(list(r.driver_offsets.values())))
        for number, est in r.driver_offsets.items():
            diff = (est - mean_fit) - (truth.driver_pace_offset_s[number] - mean_true)
            total += 1
            hits += abs(diff) <= 1.96 * r.driver_offset_se[number]
    assert total > 0
    assert hits / total >= 0.9
