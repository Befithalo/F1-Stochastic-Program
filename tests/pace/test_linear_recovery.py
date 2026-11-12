"""The joint fit recovers known synthetic fuel and wear (PAC-01, D-01), and pit loss (D-05)."""

from pathlib import Path

import numpy as np
import pytest

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.pace.linear import (
    DEFAULT_PIT_LOSS_S,
    LinearPaceFit,
    fit_linear_pace,
    measure_pit_loss,
)
from f1si.synthetic import SyntheticTruth
from tests.conftest import LONG_RACE_ID, build_long_db


def _fit(db: Path, lap: int | None = None) -> LinearPaceFit:
    at = AsOf(LONG_RACE_ID, RACE_END if lap is None else lap)
    return fit_linear_pace(AsOfAccessor(db).snapshot(at))


def test_recovers_fuel_and_wear_within_three_se(
    long_synthetic_db: Path, long_synthetic_truth: SyntheticTruth
) -> None:
    fit = _fit(long_synthetic_db)
    r = fit.report
    assert fit.is_identified
    assert r.fuel_s_per_lap is not None
    assert r.fuel_se is not None
    assert abs(r.fuel_s_per_lap - long_synthetic_truth.fuel_effect_s_per_lap) < 3 * r.fuel_se
    for comp in ("MEDIUM", "HARD"):
        est, se = fit.wear_rate(comp), fit.wear_se(comp)
        assert est is not None
        assert se is not None
        assert abs(est - long_synthetic_truth.wear_rate_s_per_lap[comp]) < 3 * se
    assert fit.wear_rate("SOFT") is None
    assert r.df_resid >= 30


def test_interval_covers_truth_in_most_seeds(
    tmp_path: Path, long_synthetic_truth: SyntheticTruth
) -> None:
    hits = {"fuel": 0, "MEDIUM": 0, "HARD": 0}
    for seed in range(10):
        db = build_long_db(tmp_path / f"seed{seed}", seed)
        r = _fit(db).report
        assert r.fuel_ci_low is not None
        assert r.fuel_ci_high is not None
        truth_fuel = long_synthetic_truth.fuel_effect_s_per_lap
        hits["fuel"] += int(r.fuel_ci_low <= truth_fuel <= r.fuel_ci_high)
        for c in r.compounds:
            truth = long_synthetic_truth.wear_rate_s_per_lap[c.compound]
            hits[c.compound] += int(c.ci_low <= truth <= c.ci_high)
    assert all(v >= 8 for v in hits.values()), hits


def test_pit_loss_close_to_truth(
    long_synthetic_db: Path, long_synthetic_truth: SyntheticTruth
) -> None:
    acc = AsOfAccessor(long_synthetic_db)
    snap = acc.snapshot(AsOf(LONG_RACE_ID, RACE_END))
    est = measure_pit_loss(snap, fit_linear_pace(snap))
    assert not est.is_default
    assert est.n_stops == 20
    assert abs(est.median_s - long_synthetic_truth.pit_loss_s) < 1.0
    early = acc.snapshot(AsOf(LONG_RACE_ID, 20))
    default = measure_pit_loss(early, fit_linear_pace(early))
    assert default.is_default
    assert default.median_s == DEFAULT_PIT_LOSS_S


def test_predict_matches_hand_computation(long_synthetic_db: Path) -> None:
    fit = _fit(long_synthetic_db)
    r = fit.report
    assert r.fuel_s_per_lap is not None
    assert r.sigma_s is not None
    mean, sd = fit.predict(
        driver=np.array([10, 15], dtype=np.int64),
        compound=np.array(["HARD", "MEDIUM"], dtype=np.str_),
        tire_age=np.array([7, 12], dtype=np.int64),
        lap=np.array([40, 15], dtype=np.int64),
    )
    hard, medium = fit.wear_rate("HARD"), fit.wear_rate("MEDIUM")
    assert hard is not None
    assert medium is not None
    expected = [
        r.driver_offsets[10] + r.fuel_s_per_lap * 39 + hard * 7,
        r.driver_offsets[15] + r.fuel_s_per_lap * 14 + medium * 12,
    ]
    assert mean.dtype == np.float64
    assert np.allclose(mean, expected, rtol=0, atol=1e-12)
    assert np.allclose(sd, r.sigma_s)


def test_predict_refuses_unknown_inputs(long_synthetic_db: Path) -> None:
    fit = _fit(long_synthetic_db)
    one = np.array([1], dtype=np.int64)
    with pytest.raises(ValueError, match="Driver number 999"):
        fit.predict(
            driver=np.array([999], dtype=np.int64),
            compound=np.array(["HARD"], dtype=np.str_),
            tire_age=one,
            lap=one,
        )
    with pytest.raises(ValueError, match="SOFT"):
        fit.predict(
            driver=np.array([10], dtype=np.int64),
            compound=np.array(["SOFT"], dtype=np.str_),
            tire_age=one,
            lap=one,
        )


def test_pace_offsets_are_centred(long_synthetic_db: Path) -> None:
    fit = _fit(long_synthetic_db)
    offsets = [fit.pace_offset(10 + i) for i in range(20)]
    assert all(o is not None for o in offsets)
    assert abs(float(np.mean([o for o in offsets if o is not None]))) < 1e-9
    assert fit.pace_offset(999) is None


def test_fit_is_deterministic(long_synthetic_db: Path) -> None:
    assert _fit(long_synthetic_db).report == _fit(long_synthetic_db).report


def test_empty_snapshot_never_raises(long_synthetic_db: Path) -> None:
    fit = _fit(long_synthetic_db, lap=0)
    assert not fit.is_identified
    assert fit.report.message
    assert fit.report.fuel_s_per_lap is None
