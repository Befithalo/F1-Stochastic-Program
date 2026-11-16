"""Bayesian pace summaries use the existing state and simulator uncertainty paths."""

from pathlib import Path

import numpy as np
import pytest

from f1si.data.asof import AsOf, AsOfAccessor
from f1si.pace.bayesian import BayesianPaceFit, fit_bayesian_pace
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import RaceState, build_race_state
from tests.conftest import LONG_RACE_ID


@pytest.fixture(scope="module")
def bayesian_fit(long_synthetic_db: Path) -> BayesianPaceFit:
    accessor = AsOfAccessor(long_synthetic_db)
    snapshot = accessor.snapshot(AsOf(LONG_RACE_ID, 0))
    rng = np.random.default_rng(230)
    numbers = snapshot.entries["driver_number"].astype(int).to_numpy(dtype=np.int64)
    driver = np.repeat(numbers, 24).astype(np.int64)
    lap = rng.integers(1, 58, size=driver.size, dtype=np.int64)
    tire_age = rng.integers(1, 19, size=driver.size, dtype=np.int64)
    compound = rng.choice(np.array(["SOFT", "MEDIUM", "HARD"]), size=driver.size)
    effect = (driver.astype(np.float64) - 10.5) * 0.035
    wear = np.select(
        [compound == "SOFT", compound == "MEDIUM", compound == "HARD"], [0.09, 0.06, 0.04]
    )
    lap_time = (
        91.0
        + effect
        - 0.045 * (lap.astype(np.float64) - 1.0)
        + wear * tire_age.astype(np.float64)
        + rng.normal(0.0, 0.18, size=driver.size)
    )
    return fit_bayesian_pace(
        driver=driver,
        compound=compound.astype(np.str_),
        tire_age=tire_age,
        lap=lap,
        lap_time_s=lap_time.astype(np.float64),
        seed=73,
        iterations=10_000,
        draws=80,
    )


@pytest.fixture(scope="module")
def bayesian_state(long_synthetic_db: Path, bayesian_fit: BayesianPaceFit) -> RaceState:
    accessor = AsOfAccessor(long_synthetic_db)
    snapshot = accessor.snapshot(AsOf(LONG_RACE_ID, 0))
    state = build_race_state(
        snapshot,
        bayesian_fit,
        laps_total=57,
        pit_loss_s=22.0,
    )
    return state


def test_bayesian_fit_builds_state_with_shared_posterior_uncertainty(
    bayesian_state: RaceState, bayesian_fit: BayesianPaceFit
) -> None:
    known = [
        car
        for car in bayesian_state.cars
        if car.driver_number in bayesian_fit.report.driver_offsets
    ]
    assert len(known) == len(bayesian_state.cars)
    assert all(car.pace_offset_sd is not None and car.pace_offset_sd > 0.0 for car in known)
    assert all(car.wear_sd is not None and car.wear_sd > 0.0 for car in known)


def test_existing_simulator_repeats_bayesian_fit_with_same_seed(
    bayesian_state: RaceState, bayesian_fit: BayesianPaceFit
) -> None:
    simulator = NumpySimulator(
        bayesian_fit,
        sc=SafetyCarModel(0.0, 4),
        compounds=bayesian_fit.fitted_compounds,
        wear_sd_by_compound={
            name: bayesian_fit.wear_se(name) for name in bayesian_fit.fitted_compounds
        },
    )
    first = simulator.simulate(bayesian_state, n_races=12, rng=make_rng(17))
    second = simulator.simulate(bayesian_state, n_races=12, rng=make_rng(17))
    assert np.array_equal(first.finish_positions, second.finish_positions)
    assert np.array_equal(first.total_time_s, second.total_time_s)


def test_pace_noise_contains_only_residual_uncertainty(bayesian_fit: BayesianPaceFit) -> None:
    driver = np.array(sorted(bayesian_fit.report.driver_offsets)[:8], dtype=np.int64)
    compound = np.repeat(np.array(["HARD"], dtype=np.str_), driver.size)
    age = np.arange(1, 9, dtype=np.int64)
    lap = np.arange(10, 18, dtype=np.int64)
    _, residual_sd = bayesian_fit.predict(driver=driver, compound=compound, tire_age=age, lap=lap)
    assert np.array_equal(residual_sd, np.full(driver.shape, bayesian_fit.report.sigma_s))
    assert bayesian_fit.wear_se("HARD") is not None
    assert bayesian_fit.pace_offset_se(int(driver[0])) is not None
