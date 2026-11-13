"""The snapshot adapter for the wear filter (PAC-03, D-03, D-06 to D-09, D-19)."""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from f1si import paths
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, RaceSnapshot
from f1si.data.loader import load_races
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.pace.kalman import (
    GENERIC_SIGMA_S,
    FilterSnapshot,
    StintFilterResult,
    current_stint_snapshots,
    filter_stints,
    resolve_priors,
)
from f1si.pace.linear import LinearPaceFit, _classify, fit_linear_pace
from f1si.rng import make_rng
from f1si.synthetic import SyntheticRaceSpec, SyntheticTruth, generate_dataset
from tests.conftest import LONG_RACE_ID

DEVIATION_SEED = 4242
DEVIATION_SD = 0.03


def _spec() -> SyntheticRaceSpec:
    dev_rng = make_rng(DEVIATION_SEED)
    devs = {i: float(v) for i, v in enumerate(dev_rng.normal(0.0, DEVIATION_SD, size=20))}
    return SyntheticRaceSpec(
        2023,
        1,
        "Long Grand Prix",
        n_drivers=20,
        n_laps=57,
        start_tyre_age=3,
        wear_rate_deviation_s_per_lap=devs,
    )


@pytest.fixture(scope="module")
def deviation_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("deviation_db")
    load_races(
        SyntheticSource((_spec(),), rng=make_rng(7)),
        paths.db_path(folder),
        (2023,),
        now=datetime(2026, 10, 22, tzinfo=UTC),
        echo=lambda _line: None,
    )
    return paths.db_path(folder)


@pytest.fixture(scope="module")
def deviation_truth() -> SyntheticTruth:
    return generate_dataset((_spec(),), rng=make_rng(7))[0].truth


def _run(
    db: Path, lap: int | None
) -> tuple[RaceSnapshot, LinearPaceFit, tuple[StintFilterResult, ...]]:
    snap = AsOfAccessor(db).snapshot(AsOf(LONG_RACE_ID, RACE_END if lap is None else lap))
    fit = fit_linear_pace(snap)
    return snap, fit, filter_stints(snap, fit)


def test_cutoff_zero_is_empty(deviation_db: Path) -> None:
    _, fit, results = _run(deviation_db, 0)
    assert results == ()
    assert current_stint_snapshots(results) == {}
    assert not fit.is_identified


def test_early_cutoff_uses_prior_only_sources(deviation_db: Path) -> None:
    _, fit, results = _run(deviation_db, 12)
    assert not fit.is_identified
    assert results
    for r in results:
        assert r.priors.rate_source.startswith("prior only")
        assert r.priors.fuel_source.startswith("prior only")
        assert r.priors.noise_source.startswith("prior only")
        assert r.priors.prior.sigma == GENERIC_SIGMA_S


def test_late_cutoff_uses_fit_sources(deviation_db: Path) -> None:
    _, fit, results = _run(deviation_db, None)
    assert fit.is_identified
    assert {r.priors.fuel_source for r in results} == {"fit"}
    assert {r.priors.noise_source for r in results} == {"fit"}
    assert {r.priors.rate_source for r in results} == {"fit"}
    assert fit.report.sigma_s == results[0].priors.prior.sigma


def test_fitted_compound_with_unfitted_other_falls_back_alone(deviation_db: Path) -> None:
    _, fit, _ = _run(deviation_db, None)
    soft = resolve_priors(fit, "SOFT")
    assert soft.rate_source == "prior only: compound not fitted yet"
    assert soft.fuel_source == "fit"
    assert soft.noise_source == "fit"
    assert resolve_priors(fit, "HARD").rate_source == "fit"


def test_rows_follow_the_clean_lap_rule(deviation_db: Path) -> None:
    snap, _, results = _run(deviation_db, None)
    table = _classify(snap.laps)
    reasons = {
        (int(d), int(lap)): r
        for d, lap, r in zip(table["driver"], table["lap"], table["reason"], strict=True)
    }
    assert results
    for r in results:
        assert r.n_used == sum(row.used for row in r.rows)
        for row in r.rows:
            expected = reasons[(r.driver_number, row.race_lap)]
            if row.used:
                assert expected is None
                assert row.reason is None
            elif row.reason != "outlier gate":
                assert row.reason == expected
            else:
                assert expected is None
        assert r.n_gate_rejections == sum(row.reason == "outlier gate" for row in r.rows)


def test_stints_are_separate_filters(deviation_db: Path) -> None:
    _, _, results = _run(deviation_db, None)
    by_driver: dict[int, list[StintFilterResult]] = {}
    for r in results:
        by_driver.setdefault(r.driver_number, []).append(r)
    assert len(by_driver) == 20
    for stints in by_driver.values():
        assert [s.stint for s in stints] == [1, 2]
        assert [s.is_current for s in stints] == [False, True]
        assert [s.compound for s in stints] == ["MEDIUM", "HARD"]
        first, second = stints
        assert first.rows[0].reason == "lap 1"
        assert second.rows[0].reason == "pit out"
        assert second.rows[0].rate_mean == second.priors.prior.rate_mean


def test_driver_filter_and_current_snapshots(deviation_db: Path) -> None:
    snap, fit, results = _run(deviation_db, None)
    only = filter_stints(snap, fit, driver_numbers=[11])
    assert {r.driver_number for r in only} == {11}
    current = current_stint_snapshots(results)
    assert set(current) == set(range(10, 30))
    one = current[11]
    assert isinstance(one, FilterSnapshot)
    assert not one.prior_only
    assert one.cutoff_lap == results[0].cutoff_lap == 57


def test_cutoff_lap_is_the_snapshot_lap(deviation_db: Path) -> None:
    _, _, results = _run(deviation_db, 30)
    assert {r.cutoff_lap for r in results} == {30}


def test_deterministic(deviation_db: Path) -> None:
    assert _run(deviation_db, 40)[2] == _run(deviation_db, 40)[2]


def test_end_to_end_final_interval_covers_truth_loosely(
    deviation_db: Path, deviation_truth: SyntheticTruth
) -> None:
    """Sanity only (about 40 stints); the calibrated 1,000-stint test is test_kalman_recovery."""
    _, _, results = _run(deviation_db, None)
    hits = []
    for r in results:
        truth = deviation_truth.driver_wear_rate_s_per_lap[r.driver_number][r.compound]
        last = r.rows[-1]
        hits.append(last.rate_lo <= truth <= last.rate_hi)
    assert np.mean(hits) >= 0.8
