"""Score a frozen fixed-sample prediction trace against final race outcomes."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from f1si.backtest.metrics import (
    brier_scores,
    grid_position_probability,
    race_cluster_interval,
    summarize_by_race,
)
from f1si.backtest.strategy import match_team_stops, summarize_team_calls
from f1si.backtest.walk_forward import (
    REGISTERED_RACE_IDS,
    PredictionRow,
    WalkForwardTrace,
    _predict_from_accessor,
    _preflight_database,
    _race_laps_total,
    run_walk_forward,
)
from f1si.backtest.wear_diagnostic import wear_proxy_diagnostic
from f1si.data import asof
from f1si.rng import make_rng

BOOTSTRAP_RESAMPLES = 2_000
BOOTSTRAP_SEED_OFFSET = 61_409
STRATEGY_BOOTSTRAP_SEED_OFFSET = 71_633


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
        laps_total = _race_laps_total(accessor, race_id, first)
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
            rng=make_rng(seed + BOOTSTRAP_SEED_OFFSET + offset),
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
        rng=make_rng(seed + BOOTSTRAP_SEED_OFFSET + 2),
        n_resamples=n_resamples,
    )
    return {
        "covered": int(covered["covered"].sum()),
        "classified_finishers": len(covered),
        "coverage": summary,
        "race_cluster_95": interval,
        "convention": "inclusive empirical inverted-CDF P05/P95 endpoints",
    }


def _strategy_comparison(
    db_path: Path,
    predictions: tuple[PredictionRow, ...],
    *,
    seed: int,
) -> dict[str, Any]:
    """Compare one frozen recommendation per cutoff with each observed stop event once."""
    recommendations: list[dict[str, Any]] = []
    cutoff_keys: set[tuple[str, int]] = set()
    for row in predictions:
        cutoff_keys.add((row.race_id, int(row.cutoff_lap)))
        if row.analysis is None or not row.analysis.options:
            continue
        best = row.analysis.best
        planned = best.plan.stop_laps[0] if best.plan.stop_laps else None
        recommendations.append(
            {
                "race_id": row.race_id,
                "driver": row.driver.upper(),
                "cutoff_lap": row.cutoff_lap,
                "top_action": best.action,
                "planned_stop_lap": planned,
            }
        )

    accessor = asof.AsOfAccessor(db_path)
    stops: list[dict[str, Any]] = []
    visible_events: list[dict[str, Any]] = []
    for race_id, cutoff in sorted(cutoff_keys):
        snapshot = accessor.snapshot(asof.AsOf(race_id, cutoff))
        drivers = snapshot.entries.set_index("driver_number")["driver_code"]
        for event in snapshot.pit_events.itertuples(index=False):
            driver = drivers.get(int(float(cast(Any, event.driver_number))))
            if driver is not None:
                visible_events.append(
                    {
                        "race_id": race_id,
                        "driver": str(driver).upper(),
                        "in_lap": int(float(cast(Any, event.in_lap))),
                        "cutoff_lap": cutoff,
                    }
                )
    for race_id in REGISTERED_RACE_IDS:
        end = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
        drivers = end.entries.set_index("driver_number")["driver_code"]
        for event in end.pit_events.itertuples(index=False):
            driver = drivers.get(int(float(cast(Any, event.driver_number))))
            if driver is None:
                continue
            stops.append(
                {
                    "race_id": race_id,
                    "driver": str(driver).upper(),
                    "in_lap": int(float(cast(Any, event.in_lap))),
                }
            )

    stop_frame = pd.DataFrame(stops, columns=["race_id", "driver", "in_lap"])
    recommendation_frame = pd.DataFrame(
        recommendations,
        columns=["race_id", "driver", "cutoff_lap", "top_action", "planned_stop_lap"],
    )
    visibility_frame = pd.DataFrame(
        visible_events, columns=["race_id", "driver", "in_lap", "cutoff_lap"]
    )
    matched = match_team_stops(recommendation_frame, stop_frame, visible_events=visibility_frame)
    if not matched.empty and (matched["cutoff_lap"] >= matched["in_lap"]).any():
        raise ValueError("Strategy comparison included a recommendation visible at the stop event.")
    bootstrap_seed = seed + STRATEGY_BOOTSTRAP_SEED_OFFSET
    summary = summarize_team_calls(matched, rng=make_rng(bootstrap_seed))
    event_count = len(stop_frame.drop_duplicates(["race_id", "driver", "in_lap"]))
    summary.update(
        {
            "observed_stop_event_count": event_count,
            "matched_stop_event_count": len(matched),
            "unmatched_stop_event_count": event_count - len(matched),
            "visibility_verified_event_count": len(matched),
            "bootstrap_seed": bootstrap_seed,
            "bootstrap_resamples": 2_000,
            "matching": "latest recommendation cutoff strictly before the observed in-lap",
            "interpretation": "retrospective comparison with observed team behavior",
        }
    )
    return summary


def score_team_strategy_sample(
    db_path: Path,
    *,
    n_simulations: int = 1_000,
    risk: float = 0.5,
    seed: int = 0,
) -> dict[str, Any]:
    """Predict only event-adjacent cutoffs needed to extend an existing frozen report."""
    _preflight_database(db_path)
    accessor = asof.AsOfAccessor(db_path)
    horizons: dict[str, tuple[int, asof.RaceSnapshot]] = {}
    end_snapshots: dict[str, asof.RaceSnapshot] = {}
    for race_id in REGISTERED_RACE_IDS:
        first = accessor.snapshot(asof.AsOf(race_id, 0))
        horizons[race_id] = (_race_laps_total(accessor, race_id, first), first)
        end_snapshots[race_id] = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))

    selected: dict[tuple[str, str, int], int] = {}
    for race_id, end in end_snapshots.items():
        driver_codes = end.entries.set_index("driver_number")["driver_code"]
        for event in end.pit_events.itertuples(index=False):
            driver = driver_codes.get(int(float(cast(Any, event.driver_number))))
            if driver is None:
                continue
            in_lap = int(float(cast(Any, event.in_lap)))
            laps_total = horizons[race_id][0]
            for cutoff in range(min(in_lap - 1, laps_total - 1), -1, -1):
                snapshot = accessor.snapshot(asof.AsOf(race_id, cutoff))
                numbers = snapshot.entries.set_index("driver_number")["driver_code"]
                visible_numbers = set(
                    snapshot.pit_events.loc[
                        pd.to_numeric(snapshot.pit_events["in_lap"], errors="coerce") == in_lap,
                        "driver_number",
                    ].astype(int)
                )
                visible_codes = {str(numbers.get(number, "")).upper() for number in visible_numbers}
                if str(driver).upper() not in visible_codes:
                    selected[(race_id, str(driver).upper(), cutoff)] = laps_total
                    break

    by_cutoff: dict[tuple[str, int], list[tuple[str, int]]] = {}
    for (race_id, driver, cutoff), laps_total in selected.items():
        by_cutoff.setdefault((race_id, cutoff), []).append((driver, laps_total))
    from f1si.cli import _prepare_replay_context

    predictions: list[PredictionRow] = []
    for (race_id, cutoff), drivers in sorted(by_cutoff.items()):
        snapshot = accessor.snapshot(asof.AsOf(race_id, cutoff))
        laps_total = drivers[0][1]
        prepared = _prepare_replay_context(accessor, race_id, laps_total, cutoff, snapshot=snapshot)
        for driver, _ in sorted(set(drivers)):
            predictions.append(
                _predict_from_accessor(
                    accessor,
                    race_id,
                    driver,
                    cutoff,
                    n_simulations=n_simulations,
                    risk=risk,
                    seed=seed,
                    laps_total=laps_total,
                    prepared_context=prepared,
                )
            )
    return _strategy_comparison(db_path, tuple(predictions), seed=seed)


def extend_existing_report(
    db_path: Path,
    report: dict[str, Any],
    *,
    n_simulations: int,
    risk: float,
    seed: int,
) -> dict[str, Any]:
    """Add the task 06-05 diagnostics to a matching measured Phase 6 probability report."""

    def finite_in_range(value: object, low: float, high: float) -> bool:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        try:
            number = float(value)
        except (OverflowError, ValueError):
            return False
        return math.isfinite(number) and low <= number <= high

    def positive_int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    metadata_value = report.get("metadata")
    metadata = metadata_value if isinstance(metadata_value, dict) else {}
    expected = {
        "base_seed": seed,
        "n_simulations_per_prediction": n_simulations,
        "risk_aversion": risk,
    }
    mismatches = [
        f"{name}={metadata.get(name)!r} (expected {value!r})"
        for name, value in expected.items()
        if metadata.get(name) != value
    ]
    if report.get("race_ids") != list(REGISTERED_RACE_IDS):
        mismatches.append("race_ids do not match the registered ten-race sample")
    if not isinstance(metadata_value, dict):
        mismatches.append("metadata section is missing")
    if report.get("schema_version") != 1:
        mismatches.append("schema_version is missing or unsupported")
    metrics = report.get("metrics")
    if not isinstance(metrics, dict):
        mismatches.append("metrics section is missing")
    else:
        required_metrics = (
            "podium_brier",
            "top10_brier",
            "brier_observation_count",
            "finish_interval_90",
        )
        missing_metrics = [name for name in required_metrics if name not in metrics]
        if missing_metrics:
            mismatches.append(
                "required probability metrics are missing: " + ", ".join(missing_metrics)
            )
        for name in ("podium_brier", "top10_brier"):
            score = metrics.get(name)
            if not isinstance(score, dict):
                mismatches.append(f"{name} score structure is incomplete")
                continue
            for part in ("model", "baseline"):
                component = score.get(part)
                if not isinstance(component, dict) or not all(
                    field in component for field in ("mean", "per_race", "race_count")
                ):
                    mismatches.append(f"{name}.{part} probability summary is incomplete")
                    continue
                per_race = component.get("per_race")
                if (
                    not isinstance(per_race, dict)
                    or set(per_race) != set(REGISTERED_RACE_IDS)
                    or component.get("race_count") != len(REGISTERED_RACE_IDS)
                ):
                    mismatches.append(f"{name}.{part} race denominator is incomplete")
                if isinstance(component, dict):
                    if not finite_in_range(component.get("mean"), 0.0, 1.0):
                        mismatches.append(f"{name}.{part}.mean must be finite and within [0, 1]")
                    if isinstance(per_race, dict) and any(
                        not finite_in_range(value, 0.0, 1.0) for value in per_race.values()
                    ):
                        mismatches.append(
                            f"{name}.{part}.per_race values must be finite and within [0, 1]"
                        )
                    if component.get("race_count") != len(REGISTERED_RACE_IDS):
                        mismatches.append(f"{name}.{part}.race_count is inconsistent")
            paired = score.get("model_minus_baseline_95")
            if not isinstance(paired, dict) or not all(
                field in paired for field in ("mean", "low", "high", "cluster_count")
            ):
                mismatches.append(f"{name} paired uncertainty summary is incomplete")
            elif (
                any(
                    not finite_in_range(paired.get(field), -1.0, 1.0)
                    for field in ("mean", "low", "high")
                )
                or paired["low"] > paired["high"]
                or paired.get("cluster_count") != len(REGISTERED_RACE_IDS)
            ):
                mismatches.append(f"{name} paired uncertainty values or denominator are invalid")
        count = metrics.get("brier_observation_count")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            mismatches.append("brier_observation_count is missing or invalid")
        interval = metrics.get("finish_interval_90")
        if not isinstance(interval, dict) or not isinstance(interval.get("coverage"), dict):
            mismatches.append("finish_interval_90 structure is incomplete")
        elif not all(
            field in interval.get("coverage", {}) for field in ("mean", "per_race", "race_count")
        ):
            mismatches.append("finish_interval_90 coverage summary is incomplete")
        else:
            coverage = interval["coverage"]
            per_race = coverage.get("per_race")
            if not finite_in_range(coverage.get("mean"), 0.0, 1.0):
                mismatches.append(
                    "finish_interval_90 coverage mean must be finite and within [0, 1]"
                )
            if (
                not isinstance(per_race, dict)
                or not per_race
                or not set(per_race).issubset(REGISTERED_RACE_IDS)
                or coverage.get("race_count") != len(per_race)
                or not positive_int(coverage.get("race_count"))
                or any(not finite_in_range(value, 0.0, 1.0) for value in per_race.values())
            ):
                mismatches.append(
                    "finish_interval_90 coverage race values or denominator are invalid"
                )
            cluster = interval.get("race_cluster_95")
            if not isinstance(cluster, dict) or not all(
                field in cluster for field in ("mean", "low", "high", "cluster_count")
            ):
                mismatches.append("finish_interval_90 uncertainty summary is incomplete")
            elif (
                any(
                    not finite_in_range(cluster.get(field), 0.0, 1.0)
                    for field in ("mean", "low", "high")
                )
                or cluster["low"] > cluster["high"]
                or cluster.get("cluster_count") != coverage.get("race_count")
            ):
                mismatches.append(
                    "finish_interval_90 uncertainty values or denominator are invalid"
                )
        if isinstance(interval, dict) and any(
            field not in interval for field in ("covered", "classified_finishers")
        ):
            mismatches.append("finish_interval_90 denominator fields are incomplete")
        elif isinstance(interval, dict):
            covered = interval.get("covered")
            classified = interval.get("classified_finishers")
            if (
                not isinstance(covered, int)
                or isinstance(covered, bool)
                or covered < 0
                or not positive_int(classified)
                or covered > classified
            ):
                mismatches.append(
                    "finish_interval_90 counts must have a positive consistent denominator"
                )
    if mismatches:
        detail = "; ".join(mismatches)
        raise ValueError("Existing report does not match diagnostic inputs: " + detail)
    report["metrics"]["team_strategy_comparison"] = score_team_strategy_sample(
        db_path, n_simulations=n_simulations, risk=risk, seed=seed
    )
    report["metrics"]["wear_band_retrospective_proxy"] = wear_proxy_diagnostic(db_path, None)
    return report


def score_registered_sample(
    db_path: Path,
    *,
    n_simulations: int = 1_000,
    risk: float = 0.5,
    seed: int = 0,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    workers: int = 1,
) -> dict[str, Any]:
    """Preflight, freeze all predictions, then open outcomes and calculate the report."""
    _preflight_database(db_path)
    trace = run_walk_forward(
        db_path,
        n_simulations=n_simulations,
        risk=risk,
        seed=seed,
        workers=workers,
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
    strategy = _strategy_comparison(db_path, frozen, seed=seed)
    wear_proxy = wear_proxy_diagnostic(db_path, frozen)
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
            "team_strategy_comparison": strategy,
            "wear_band_retrospective_proxy": wear_proxy,
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
