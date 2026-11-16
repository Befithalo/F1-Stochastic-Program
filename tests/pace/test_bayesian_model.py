"""Seeded Bayesian pace fit contract and PaceModel conformance."""

from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from f1si.pace.bayesian import (
    BayesianPaceFit,
    PaceFitError,
    fit_bayesian_pace,
    fit_bayesian_panel,
)
from f1si.pace.training import BayesianTrainingPanel
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
        iterations=10_000,
        draws=96,
    )


def _hierarchical_panel() -> BayesianTrainingPanel:
    rng = np.random.default_rng(902)
    n = 720
    drivers = np.array([f"D{number:02d}" for number in range(1, 9)], dtype=np.str_)
    teams = np.array([f"TEAM{(number - 1) // 2 + 1}" for number in range(1, 9)], dtype=np.str_)
    driver_id = rng.choice(drivers, size=n)
    driver_team = {str(driver): str(team) for driver, team in zip(drivers, teams, strict=True)}
    team_name = np.array([driver_team[str(driver)] for driver in driver_id], dtype=np.str_)
    race_id = rng.choice(np.array(["RACE1", "RACE2", "RACE3", "RACE4"], dtype=np.str_), size=n)
    race_era = {"RACE1": "ERA_A", "RACE2": "ERA_A", "RACE3": "ERA_B", "RACE4": "ERA_B"}
    era = np.array([race_era[str(race)] for race in race_id], dtype=np.str_)
    compound = rng.choice(np.array(["SOFT", "MEDIUM", "HARD"], dtype=np.str_), size=n)
    lap = rng.integers(1, 58, size=n, dtype=np.int64)
    tire_age = rng.integers(1, 19, size=n, dtype=np.int64)
    team_effect = {"TEAM1": -0.30, "TEAM2": -0.10, "TEAM3": 0.10, "TEAM4": 0.30}
    driver_effect = {
        "D01": -0.12,
        "D02": 0.12,
        "D03": -0.08,
        "D04": 0.08,
        "D05": -0.06,
        "D06": 0.06,
        "D07": -0.10,
        "D08": 0.10,
    }
    event_effect = {"RACE1": -0.15, "RACE2": 0.15, "RACE3": 0.10, "RACE4": -0.10}
    era_effect = {"ERA_A": -0.18, "ERA_B": 0.18}
    fresh = {"SOFT": -0.15, "MEDIUM": 0.0, "HARD": 0.15}
    wear = {"SOFT": 0.09, "MEDIUM": 0.06, "HARD": 0.04}
    lap_time = np.array(
        [
            91.0
            + team_effect[str(team)]
            + driver_effect[str(driver)]
            + event_effect[str(event)]
            + era_effect[str(regulation)]
            + fresh[str(tire)]
            - 0.045 * (int(lap_no) - 1)
            + wear[str(tire)] * int(age)
            + rng.normal(0.0, 0.14)
            for team, driver, event, regulation, tire, lap_no, age in zip(
                team_name, driver_id, race_id, era, compound, lap, tire_age, strict=True
            )
        ],
        dtype=np.float64,
    )
    rows = pd.DataFrame(
        {
            "race_id": race_id,
            "season": np.where(np.isin(race_id, ["RACE1", "RACE2"]), 2023, 2024),
            "era": era,
            "driver_number": np.ones(n, dtype=np.int64),
            "driver_id": driver_id,
            "team_name": team_name,
            "lap_number": lap,
            "compound": compound,
            "tire_age": tire_age,
            "lap_time_s": lap_time,
        }
    )

    def indexes(column: str) -> MappingProxyType[str, int]:
        values = sorted(set(rows[column].astype(str)))
        return MappingProxyType({value: index for index, value in enumerate(values)})

    return BayesianTrainingPanel(
        rows=rows,
        category_indexes=MappingProxyType(
            {
                column: indexes(column)
                for column in ("driver_id", "team_name", "race_id", "era", "compound")
            }
        ),
        current_driver_id_by_number=MappingProxyType(
            {number: str(driver) for number, driver in enumerate(drivers, start=1)} | {99: "ROOKIE"}
        ),
        current_team_by_number=MappingProxyType(
            {number: str(team) for number, team in enumerate(teams, start=1)} | {99: "TEAM_NEW"}
        ),
        current_event_id="RACE4",
        current_era="ERA_B",
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
    assert fitted.report.converged
    assert fitted.report.loss_relative_change <= 0.1


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


def test_hierarchical_fit_exposes_centered_effects_and_shrinks_new_groups() -> None:
    panel = _hierarchical_panel()
    fitted = fit_bayesian_panel(panel, seed=47, iterations=10_000, draws=96)

    assert set(fitted.report.effect_names) == {
        "team/car",
        "driver",
        "fresh compound",
        "compound wear",
        "fuel proxy",
        "regulation era",
        "race/event",
    }
    for effects in (
        fitted.report.team_offsets,
        fitted.report.driver_identity_offsets,
        fitted.report.fresh_offsets_s,
        fitted.report.era_offsets,
        fitted.report.race_offsets,
    ):
        assert abs(float(np.mean(list(effects.values())))) < 1e-8
    assert "ROOKIE" in fitted.report.prior_driven_driver_ids
    assert "TEAM_NEW" in fitted.report.prior_driven_team_names
    assert fitted.pace_offset(99) is not None
    assert abs(fitted.pace_offset(99) or 0.0) < 0.5
    assert list(fitted.report.category_indexes["team_name"]) == sorted(
        fitted.report.category_indexes["team_name"]
    )


class _UnusableApproximation:
    def __init__(self, loss: NDArray[np.float64]) -> None:
        self.hist = loss

    def sample(self, *, draws: int, random_seed: int) -> object:
        raise AssertionError("posterior sampling must not follow a failed ADVI diagnostic")


@pytest.mark.parametrize(
    "loss",
    [
        np.full(10_000, np.nan, dtype=np.float64),
        np.concatenate(
            (np.full(9_900, 1_000.0, dtype=np.float64), np.full(100, 1_500.0, dtype=np.float64))
        ),
    ],
    ids=["non-finite", "not-stable"],
)
def test_non_finite_or_non_stable_advi_raises_named_fit_error(
    training_data: TrainingArrays, loss: NDArray[np.float64], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "f1si.pace.bayesian.pm.fit",
        lambda *args, **kwargs: _UnusableApproximation(loss),
    )
    driver, compound, tire_age, lap, lap_time = training_data
    with pytest.raises(PaceFitError, match=r"loss|converg"):
        fit_bayesian_pace(
            driver=driver,
            compound=compound,
            tire_age=tire_age,
            lap=lap,
            lap_time_s=lap_time,
            seed=191,
            iterations=10_000,
            draws=96,
        )


def test_fit_refuses_an_iteration_budget_below_the_convergence_minimum(
    training_data: TrainingArrays,
) -> None:
    driver, compound, tire_age, lap, lap_time = training_data
    with pytest.raises(PaceFitError, match="at least 10000"):
        fit_bayesian_pace(
            driver=driver,
            compound=compound,
            tire_age=tire_age,
            lap=lap,
            lap_time_s=lap_time,
            seed=191,
            iterations=9_999,
            draws=96,
        )
