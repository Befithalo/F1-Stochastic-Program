"""Seeded Bayesian pace fit contract and PaceModel conformance."""

import numpy as np
import pytest
from numpy.typing import NDArray

from f1si.pace.bayesian import BayesianPaceFit, PaceFitError, fit_bayesian_pace
from tests.conformance.suites import PaceProbe, check_pace_model

TrainingArrays = tuple[
    NDArray[np.int64],
    NDArray[np.str_],
    NDArray[np.int64],
    NDArray[np.int64],
    NDArray[np.float64],
]


@pytest.fixture(scope="module")
def training_data() -> TrainingArrays:
    rng = np.random.default_rng(319)
    n = 360
    driver = rng.integers(1, 9, size=n, dtype=np.int64)
    compound = rng.choice(np.array(["SOFT", "MEDIUM", "HARD"], dtype=np.str_), size=n)
    lap = rng.integers(1, 58, size=n, dtype=np.int64)
    tire_age = rng.integers(1, 19, size=n, dtype=np.int64)
    offsets = {number: (number - 4.5) * 0.12 for number in range(1, 9)}
    wear = {"SOFT": 0.09, "MEDIUM": 0.06, "HARD": 0.04}
    fresh = {"SOFT": -0.1, "MEDIUM": 0.0, "HARD": 0.22}
    lap_time = np.array(
        [
            91.0
            + offsets[int(d)]
            + fresh[str(c)]
            - 0.045 * (int(lap_no) - 1)
            + wear[str(c)] * int(a)
            + rng.normal(0.0, 0.16)
            for d, c, lap_no, a in zip(driver, compound, lap, tire_age, strict=True)
        ],
        dtype=np.float64,
    )
    return driver, compound, tire_age, lap, lap_time


def _fit(data: TrainingArrays) -> BayesianPaceFit:
    driver, compound, tire_age, lap, lap_time = data
    return fit_bayesian_pace(
        driver=driver,
        compound=compound,
        tire_age=tire_age,
        lap=lap,
        lap_time_s=lap_time,
        seed=191,
        iterations=1_500,
        draws=96,
    )


@pytest.fixture(scope="module")
def fitted(training_data: TrainingArrays) -> BayesianPaceFit:
    return _fit(training_data)


def test_seeded_fit_returns_finite_shape_matched_predictions(
    fitted: BayesianPaceFit, training_data: TrainingArrays
) -> None:
    driver, compound, tire_age, lap, _ = training_data
    mean, sd = fitted.predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)
    assert mean.shape == sd.shape == driver.shape
    assert np.isfinite(mean).all()
    assert np.isfinite(sd).all()
    assert (sd > 0.0).all()


def test_fit_satisfies_shared_pace_model_conformance(fitted: BayesianPaceFit) -> None:
    numbers = np.arange(1, 9, dtype=np.int64)
    probe = PaceProbe(
        driver=numbers,
        compound=np.array(["SOFT", "MEDIUM", "HARD", "SOFT", "MEDIUM", "HARD", "SOFT", "HARD"]),
        tire_age=np.arange(1, 9, dtype=np.int64),
        lap=np.arange(20, 28, dtype=np.int64),
    )
    check_pace_model(fitted, probe)


def test_repeated_seed_has_identical_posterior_summaries(
    training_data: TrainingArrays,
) -> None:
    first = _fit(training_data)
    second = _fit(training_data)
    assert first.report.driver_offsets == second.report.driver_offsets
    assert first.report.fuel_s_per_lap == second.report.fuel_s_per_lap
    assert first.report.sigma_s == second.report.sigma_s


def test_missing_or_degenerate_training_rows_raise_fit_error() -> None:
    driver = np.ones(20, dtype=np.int64)
    compound = np.full(20, "HARD", dtype=np.str_)
    age = np.arange(20, dtype=np.int64)
    lap = np.arange(1, 21, dtype=np.int64)
    time = np.full(20, np.nan, dtype=np.float64)
    with pytest.raises(PaceFitError, match=r"finite|identif|training"):
        fit_bayesian_pace(
            driver=driver, compound=compound, tire_age=age, lap=lap, lap_time_s=time, seed=1
        )
