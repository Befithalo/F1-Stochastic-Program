"""Synthetic truth recovery and a bounded NUTS comparison for the pace hierarchy."""

from types import MappingProxyType
from typing import TypedDict

import arviz as az  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
import pymc as pm  # type: ignore[import-untyped]

from f1si.pace.bayesian import BayesianFitReport, _build_pymc_model, fit_bayesian_panel
from f1si.pace.training import BayesianTrainingPanel


class SyntheticTruth(TypedDict):
    intercept: float
    team: dict[str, float]
    driver: dict[str, float]
    event: dict[str, float]
    era: dict[str, float]
    fresh: dict[str, float]
    wear: dict[str, float]
    fuel: float


def _synthetic_panel(*, compact: bool = False) -> tuple[BayesianTrainingPanel, SyntheticTruth]:
    rng = np.random.default_rng(8_771 if compact else 8_770)
    driver_names = [f"D{number:02d}" for number in range(1, 5 if compact else 9)]
    team_names = ["TEAM1", "TEAM2"] if compact else [f"TEAM{i}" for i in range(1, 5)]
    races = ["RACE1", "RACE2", "RACE3", "RACE4"]
    compounds = ["SOFT", "MEDIUM"] if compact else ["SOFT", "MEDIUM", "HARD"]
    driver_truth = (
        {"D01": -0.12, "D02": 0.12, "D03": -0.08, "D04": 0.08}
        if compact
        else {
            "D01": -0.12,
            "D02": 0.12,
            "D03": -0.08,
            "D04": 0.08,
            "D05": -0.06,
            "D06": 0.06,
            "D07": -0.10,
            "D08": 0.10,
        }
    )
    team_truth = (
        {"TEAM1": -0.12, "TEAM2": 0.12}
        if compact
        else {"TEAM1": -0.30, "TEAM2": -0.10, "TEAM3": 0.10, "TEAM4": 0.30}
    )
    fresh_truth = (
        {"SOFT": -0.10, "MEDIUM": 0.10}
        if compact
        else {
            "SOFT": -0.15,
            "MEDIUM": 0.0,
            "HARD": 0.15,
        }
    )
    wear_truth = (
        {"SOFT": 0.09, "MEDIUM": 0.05}
        if compact
        else {
            "SOFT": 0.09,
            "MEDIUM": 0.06,
            "HARD": 0.04,
        }
    )
    event_truth = {"RACE1": -0.15, "RACE2": 0.15, "RACE3": -0.10, "RACE4": 0.10}
    era_truth = {"ERA_A": -0.20, "ERA_B": 0.20}
    age_count = 6 if compact else 12
    repetitions = 2
    values: list[dict[str, object]] = []
    for race_index, race in enumerate(races):
        era = "ERA_A" if race_index < 2 else "ERA_B"
        for driver_index, driver_id in enumerate(driver_names):
            # Drivers change teams across synthetic events so team and driver effects are
            # separately identifiable rather than perfectly nested.
            team = team_names[(driver_index + race_index) % len(team_names)]
            for compound in compounds:
                for age in range(1, age_count + 1):
                    for _ in range(repetitions):
                        lap = int(rng.integers(1, 58))
                        lap_time = (
                            91.5
                            + team_truth[team]
                            + driver_truth[driver_id]
                            + event_truth[race]
                            + era_truth[era]
                            + fresh_truth[compound]
                            - 0.045 * (lap - 1)
                            + wear_truth[compound] * age
                            + rng.normal(0.0, 0.14)
                        )
                        values.append(
                            {
                                "race_id": race,
                                "season": 2023 if era == "ERA_A" else 2024,
                                "era": era,
                                "driver_number": int(driver_id[1:]),
                                "driver_id": driver_id,
                                "team_name": team,
                                "lap_number": lap,
                                "compound": compound,
                                "tire_age": age,
                                "lap_time_s": lap_time,
                            }
                        )
    rows = pd.DataFrame(values)
    category_indexes = {
        column: MappingProxyType(
            {value: index for index, value in enumerate(sorted(rows[column].astype(str).unique()))}
        )
        for column in ("driver_id", "team_name", "race_id", "era", "compound")
    }
    current_team = {
        int(driver[1:]): team_names[(index + 3) % len(team_names)]
        for index, driver in enumerate(driver_names)
    }
    panel = BayesianTrainingPanel(
        rows=rows,
        category_indexes=MappingProxyType(category_indexes),
        current_driver_id_by_number=MappingProxyType(
            {int(driver[1:]): driver for driver in driver_names}
        ),
        current_team_by_number=MappingProxyType(current_team),
        current_event_id="RACE4",
        current_era="ERA_B",
    )
    truth: SyntheticTruth = {
        "intercept": 91.5,
        "team": team_truth,
        "driver": driver_truth,
        "event": event_truth,
        "era": era_truth,
        "fresh": fresh_truth,
        "wear": wear_truth,
        "fuel": -0.045,
    }
    return panel, truth


def _build_model_for_panel(panel: BayesianTrainingPanel) -> tuple[pm.Model, float]:
    rows = panel.rows
    columns = {
        name: tuple(sorted(set(rows[name].astype(str)) | set(extra)))
        for name, extra in (
            ("driver_id", panel.current_driver_id_by_number.values()),
            ("team_name", panel.current_team_by_number.values()),
            ("race_id", (panel.current_event_id,)),
            ("era", (panel.current_era,)),
            ("compound", ()),
        )
    }

    def encode(column: str) -> np.ndarray:
        return np.searchsorted(
            np.asarray(columns[column], dtype=np.str_),
            rows[column].astype(str).to_numpy(dtype=np.str_),
        ).astype(np.int64)

    lap = rows["lap_number"].to_numpy(dtype=np.float64) - 1.0
    age = rows["tire_age"].to_numpy(dtype=np.float64)
    lap_scale = float(np.std(lap)) or 1.0
    age_scale = float(np.std(age)) or 1.0
    model = _build_pymc_model(
        driver_idx=encode("driver_id"),
        team_idx=encode("team_name"),
        event_idx=encode("race_id"),
        era_idx=encode("era"),
        compound_idx=encode("compound"),
        driver_count=len(columns["driver_id"]),
        team_count=len(columns["team_name"]),
        event_count=len(columns["race_id"]),
        era_count=len(columns["era"]),
        compound_count=len(columns["compound"]),
        lap_x=lap / lap_scale,
        age_x=age / age_scale,
        lap_time_s=rows["lap_time_s"].to_numpy(dtype=np.float64),
    )
    return model, lap_scale


def test_seeded_multiera_panel_recovers_pace_effects_and_predictive_coverage() -> None:
    panel, truth = _synthetic_panel()
    fit = fit_bayesian_panel(panel, seed=5_019, iterations=50_000, draws=500)
    report = fit.report

    assert abs(report.intercept_s - float(truth["intercept"])) < 0.10
    assert abs(report.fuel_s_per_lap - float(truth["fuel"])) < 0.01
    for actual, expected in truth["team"].items():
        assert abs(report.team_offsets[actual] - expected) < 0.10
    for actual, expected in truth["driver"].items():
        assert abs(report.driver_identity_offsets[actual] - expected) < 0.10
    for actual, expected in truth["event"].items():
        assert abs(report.race_offsets[actual] - expected) < 0.10
    for actual, expected in truth["era"].items():
        assert abs(report.era_offsets[actual] - expected) < 0.10
    for actual, expected in truth["fresh"].items():
        assert abs(report.fresh_offsets_s[actual] - expected) < 0.10
    for actual, expected in truth["wear"].items():
        assert abs(report.wear_s_per_lap[actual] - expected) < 0.02

    included = (
        ("intercept", float(truth["intercept"])),
        ("fuel_s_per_lap", float(truth["fuel"])),
        ("team:TEAM1", truth["team"]["TEAM1"]),
        ("driver:D01", truth["driver"]["D01"]),
        ("event:RACE1", truth["event"]["RACE1"]),
        ("era:ERA_A", truth["era"]["ERA_A"]),
        ("fresh:HARD", truth["fresh"]["HARD"]),
        ("wear:SOFT", truth["wear"]["SOFT"]),
    )
    for name, expected in included:
        low, high = report.effect_intervals_90[name]
        assert low <= expected <= high, name

    rows = panel.rows
    prediction = (
        report.intercept_s
        + rows["team_name"].map(report.team_offsets).to_numpy(dtype=np.float64)
        + rows["driver_id"].map(report.driver_identity_offsets).to_numpy(dtype=np.float64)
        + rows["race_id"].map(report.race_offsets).to_numpy(dtype=np.float64)
        + rows["era"].map(report.era_offsets).to_numpy(dtype=np.float64)
        + rows["compound"].map(report.fresh_offsets_s).to_numpy(dtype=np.float64)
        + report.fuel_s_per_lap * (rows["lap_number"].to_numpy(dtype=np.float64) - 1.0)
        + rows["compound"].map(report.wear_s_per_lap).to_numpy(dtype=np.float64)
        * rows["tire_age"].to_numpy(dtype=np.float64)
    )
    residual = rows["lap_time_s"].to_numpy(dtype=np.float64) - prediction
    coverage = float(np.mean(np.abs(residual) <= 1.645 * report.sigma_s))
    assert 0.80 <= coverage <= 0.96
    print(f"synthetic predictive coverage within 90% residual interval: {coverage:.3%}")


def test_four_chain_nuts_reference_is_converged_and_compared_with_advi() -> None:
    panel, _ = _synthetic_panel(compact=True)
    advi = fit_bayesian_panel(panel, seed=6_113, iterations=50_000, draws=500).report
    model, lap_scale = _build_model_for_panel(panel)
    with model:
        reference = pm.sample(
            draws=400,
            tune=1_000,
            chains=4,
            cores=1,
            random_seed=[6_121, 6_122, 6_123, 6_124],
            nuts={"target_accept": 0.99, "max_treedepth": 12},
            progressbar=False,
            return_inferencedata=True,
            init="adapt_diag",
        )
    diagnostics = az.summary(
        reference,
        var_names=["intercept", "fuel_scaled", "residual_sd", "team_effect_scale"],
        kind="diagnostics",
    )
    max_rhat = float(diagnostics["r_hat"].max())
    min_ess = float(diagnostics["ess_bulk"].min())
    divergences = int(reference.sample_stats["diverging"].values.sum())
    max_depth_hits = int((reference.sample_stats["tree_depth"].values >= 12).sum())
    assert max_rhat <= 1.05
    assert min_ess >= 100.0
    assert divergences <= 16

    nuts_intercept = np.asarray(reference.posterior["intercept"].values).reshape(-1)
    nuts_fuel = np.asarray(reference.posterior["fuel_scaled"].values).reshape(-1) / lap_scale
    nuts_residual = np.asarray(reference.posterior["residual_sd"].values).reshape(-1)
    comparisons = {
        "intercept_mean_delta": float(np.mean(nuts_intercept) - advi.intercept_s),
        "fuel_mean_delta": float(np.mean(nuts_fuel) - advi.fuel_s_per_lap),
        "residual_sd_mean_delta": float(np.mean(nuts_residual) - advi.sigma_s),
        "fuel_sd_delta": float(np.std(nuts_fuel, ddof=1) - _interval_sd(advi, "fuel_s_per_lap")),
    }
    assert all(np.isfinite(value) for value in comparisons.values())
    print(
        f"NUTS diagnostics: max R-hat={max_rhat:.3f}, "
        f"min bulk ESS={min_ess:.1f}, divergences={divergences}, "
        f"max-depth hits={max_depth_hits}"
    )
    print(f"ADVI minus NUTS reference summary deltas: {comparisons}")


def _interval_sd(report: BayesianFitReport, name: str) -> float:
    low, high = report.effect_intervals_90[name]
    return float((high - low) / (2.0 * 1.645))
