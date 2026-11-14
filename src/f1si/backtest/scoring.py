"""Score a frozen fixed-sample prediction trace against final race outcomes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from f1si.backtest.metrics import (
    brier_scores,
    grid_position_probability,
    race_cluster_interval,
    summarize_by_race,
)
from f1si.backtest.walk_forward import (
    REGISTERED_RACE_IDS,
    PredictionRow,
    WalkForwardTrace,
    _preflight_database,
    run_walk_forward,
)
from f1si.data import asof

BOOTSTRAP_RESAMPLES = 2_000
BOOTSTRAP_SEED_OFFSET = 61_409


def _new_results_accessor(db_path: Path) -> Any:
    """Open the final-results capability inside the scoring boundary only."""
    from f1si.data.results import ResultsAccessor

    return ResultsAccessor(db_path)


def _expected_prediction_keys(db_path: Path) -> set[tuple[str, int, str]]:
    """Read only cutoff-safe entrant metadata to define the complete prediction key set."""
    accessor = asof.AsOfAccessor(db_path)
    expected: set[tuple[str, int, str]] = set()
    for race_id in REGISTERED_RACE_IDS:
        first = accessor.snapshot(asof.AsOf(race_id, 0))
        laps_total = first.race.scheduled_laps
        if not laps_total:
            raise ValueError(f"No scheduled race distance available for {race_id}.")
        for lap in range(int(laps_total)):
            snapshot = first if lap == 0 else accessor.snapshot(asof.AsOf(race_id, lap))
            for driver in snapshot.entries["driver_code"]:
                expected.add((race_id, lap, str(driver).upper()))
    return expected


def _validate_frozen_trace(
    trace: WalkForwardTrace, expected: set[tuple[str, int, str]]
) -> tuple[PredictionRow, ...]:
    predictions = tuple(trace.predictions)
    actual: set[tuple[str, int, str]] = set()
    duplicates: set[tuple[str, int, str]] = set()
    for row in predictions:
        key = (str(row.race_id), int(row.cutoff_lap), str(row.driver).upper())
        if key in actual:
            duplicates.add(key)
        actual.add(key)
    if duplicates or actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        detail = []
        if missing:
            detail.append(f"missing {len(missing)} keys (first: {missing[:3]})")
        if extra:
            detail.append(f"unexpected {len(extra)} keys (first: {extra[:3]})")
        if duplicates:
            detail.append(f"duplicate keys (first: {sorted(duplicates)[:3]})")
        raise ValueError("Incomplete or invalid prediction trace: " + "; ".join(detail))
    return predictions


def _prediction_frame(predictions: tuple[PredictionRow, ...]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for prediction in predictions:
        option = prediction.analysis.best if prediction.analysis is not None else None
        rows.append(
            {
                "race_id": prediction.race_id,
                "driver_code": prediction.driver.upper(),
                "cutoff_lap": int(prediction.cutoff_lap),
                "predicted_podium": option.podium_probability if option is not None else np.nan,
                "predicted_top10": option.top10_probability if option is not None else np.nan,
                "finish_p05": option.finish_p05 if option is not None else np.nan,
                "finish_p95": option.finish_p95 if option is not None else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _join_results_and_baseline(
    db_path: Path,
    predictions: pd.DataFrame,
    results: Any,
) -> pd.DataFrame:
    """Join final outcomes and past-only grid probabilities to frozen prediction rows."""
    final_by_race = {
        race_id: results.final_classification(race_id) for race_id in REGISTERED_RACE_IDS
    }
    accessor = asof.AsOfAccessor(db_path)
    entries_by_race: dict[str, pd.DataFrame] = {}
    for race_id in REGISTERED_RACE_IDS:
        snapshot = accessor.snapshot(asof.AsOf(race_id, 0))
        entries_by_race[race_id] = snapshot.entries[["driver_code", "grid_position"]].copy()

    outcome_rows: list[pd.DataFrame] = []
    for race_id in REGISTERED_RACE_IDS:
        classification = final_by_race[race_id]
        if classification["driver_code"].duplicated().any():
            raise ValueError(f"Final classification has duplicate drivers for {race_id}.")
        entries = entries_by_race[race_id]
        joined = entries.merge(
            classification[["driver_code", "final_position"]],
            on="driver_code",
            how="left",
            validate="one_to_one",
            indicator=True,
        )
        if (joined["_merge"] != "both").any():
            raise ValueError(f"Final classification is incomplete for registered race {race_id}.")
        earlier = accessor.history(asof.AsOf(race_id, 0))
        history = earlier.entries.merge(
            earlier.results[["race_id", "driver_number", "final_position"]],
            on=["race_id", "driver_number"],
            how="inner",
            validate="one_to_one",
        )[["grid_position", "final_position"]].rename(columns={"final_position": "finish_position"})
        history["grid_position"] = pd.to_numeric(history["grid_position"], errors="coerce")
        history["finish_position"] = pd.to_numeric(history["finish_position"], errors="coerce")
        field_size = len(entries)
        base = joined[["driver_code", "grid_position"]].copy()
        base["race_id"] = race_id
        base["baseline_podium"] = [
            grid_position_probability(
                history,
                grid_position=grid,
                field_size=field_size,
            )["podium"]
            for grid in base["grid_position"]
        ]
        base["baseline_top10"] = [
            grid_position_probability(
                history,
                grid_position=grid,
                field_size=field_size,
            )["top10"]
            for grid in base["grid_position"]
        ]
        base["finish_position"] = pd.to_numeric(joined["final_position"], errors="coerce")
        outcome_rows.append(base)

    outcomes = pd.concat(outcome_rows, ignore_index=True)
    scored = predictions.merge(
        outcomes,
        on=["race_id", "driver_code"],
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    if (scored["_merge"] != "both").any():
        raise ValueError("Final outcomes did not join to every frozen prediction.")
    scored = scored.drop(columns=["_merge"])
    return scored


def _summarize_brier(rows: pd.DataFrame, *, seed: int, n_resamples: int) -> dict[str, Any]:
    race_losses: list[pd.DataFrame] = []
    observation_count = 0
    for _race_id, group in rows.groupby("race_id", sort=False):
        result = brier_scores(group, paired=True)
        if not result["model_mask"].equals(result["baseline_mask"]):
            raise ValueError("Model and baseline Brier scores do not share one mask.")
        mask = result["model_mask"].to_numpy(dtype=bool)
        observation_count += int(mask.sum())
        available = group.loc[mask, ["race_id"]].reset_index(drop=True)
        available["model_podium"] = result["model_podium_losses"]
        available["baseline_podium"] = result["baseline_podium_losses"]
        available["difference_podium"] = (
            result["model_podium_losses"] - result["baseline_podium_losses"]
        )
        available["model_top10"] = result["model_top10_losses"]
        available["baseline_top10"] = result["baseline_top10_losses"]
        available["difference_top10"] = (
            result["model_top10_losses"] - result["baseline_top10_losses"]
        )
        race_losses.append(available)
    if not race_losses:
        raise ValueError("No shared observed prediction rows are available for Brier scoring.")
    losses = pd.concat(race_losses, ignore_index=True)

    def metric(name: str, offset: int) -> dict[str, Any]:
        model = summarize_by_race(losses, value=f"model_{name}")
        baseline = summarize_by_race(losses, value=f"baseline_{name}")
        difference = race_cluster_interval(
            losses,
            value=f"difference_{name}",
            rng=np.random.default_rng(seed + BOOTSTRAP_SEED_OFFSET + offset),
            n_resamples=n_resamples,
        )
        return {
            "model": model,
            "baseline": baseline,
            "model_minus_baseline_95": difference,
        }

    return {
        "observation_count": observation_count,
        "podium": metric("podium", 0),
        "top10": metric("top10", 1),
    }


def _summarize_interval_coverage(
    rows: pd.DataFrame, *, seed: int, n_resamples: int
) -> dict[str, Any]:
    finish = pd.to_numeric(rows["finish_position"], errors="coerce")
    low = pd.to_numeric(rows["finish_p05"], errors="coerce")
    high = pd.to_numeric(rows["finish_p95"], errors="coerce")
    valid = finish.notna() & low.notna() & high.notna()
    if not valid.any():
        raise ValueError("No classified finishers have a frozen finishing interval.")
    covered = rows.loc[valid, ["race_id"]].copy()
    covered["covered"] = (
        (finish.loc[valid] >= low.loc[valid]) & (finish.loc[valid] <= high.loc[valid])
    ).astype(float)
    summary = summarize_by_race(covered, value="covered")
    interval = race_cluster_interval(
        covered,
        value="covered",
        rng=np.random.default_rng(seed + BOOTSTRAP_SEED_OFFSET + 2),
        n_resamples=n_resamples,
    )
    return {
        "covered": int(covered["covered"].sum()),
        "classified_finishers": len(covered),
        "coverage": summary,
        "race_cluster_95": interval,
        "convention": "inclusive empirical inverted-CDF P05/P95 endpoints",
    }


def score_registered_sample(
    db_path: Path,
    *,
    n_simulations: int = 1_000,
    risk: float = 0.5,
    seed: int = 0,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, Any]:
    """Preflight, freeze all predictions, then open outcomes and calculate the report."""
    _preflight_database(db_path)
    trace = run_walk_forward(
        db_path,
        n_simulations=n_simulations,
        risk=risk,
        seed=seed,
    )
    expected = _expected_prediction_keys(db_path)
    frozen = _validate_frozen_trace(trace, expected)
    predictions = _prediction_frame(frozen)

    # The first result capability construction occurs only after the complete prediction trace
    # is validated and frozen.
    results = _new_results_accessor(db_path)
    joined = _join_results_and_baseline(db_path, predictions, results)
    metrics = _summarize_brier(joined, seed=seed, n_resamples=n_resamples)
    coverage = _summarize_interval_coverage(joined, seed=seed, n_resamples=n_resamples)
    reference = joined.loc[(joined["race_id"] == "2023-01") & (joined["driver_code"] == "ALO")]
    reference_outcome = reference["finish_position"].dropna()
    diagnostic = {
        "race_id": "2023-01",
        "driver": "ALO",
        "observed_finish": int(reference_outcome.iloc[0]) if not reference_outcome.empty else None,
        "historical_phase_03_interval": [4, 6],
        "historical_phase_03_observed_finish": 3,
        "tunes_interval_endpoints": False,
        "note": "Carry-forward reference miss; it is not used to adjust the empirical endpoints.",
    }
    return {
        "schema_version": 1,
        "race_ids": list(REGISTERED_RACE_IDS),
        "metrics": {
            "podium_brier": metrics["podium"],
            "top10_brier": metrics["top10"],
            "brier_observation_count": metrics["observation_count"],
            "finish_interval_90": coverage,
        },
        "metadata": {
            "base_seed": seed,
            "bootstrap_seed": seed + BOOTSTRAP_SEED_OFFSET,
            "bootstrap_resamples": n_resamples,
            "risk_aversion": risk,
            "n_simulations_per_prediction": n_simulations,
            "aggregation": "equal race weight after within-race observation means",
            "baseline": "past-only grid-position event rates with five neutral pseudo-starts",
            "first_race_baseline": "neutral podium and top-10 rates based on field size",
            "paired_model_baseline_mask": "same finite model and baseline probabilities per row",
            "uncertainty": "paired 95% percentile bootstrap resampling whole races",
        },
        "carry_forward_diagnostic": diagnostic,
    }
