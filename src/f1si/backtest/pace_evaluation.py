"""One-shot chronological next-lap evaluation for the locked Phase 7 pace holdout.

The scorer makes all model predictions through cutoff snapshots first. It reads the target laps
through the as-of door only after those predictions exist, then applies the pre-registered clean
target mask and paired MAE calculation. It never imports the results or out-of-sample doors.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import multiprocessing
import os
import sys
import tempfile
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from f1si import paths
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, RaceSnapshot
from f1si.pace.linear import LinearPaceFit, _classify, fit_linear_pace
from f1si.pace.training import build_bayesian_training_panel

DEFAULT_LOCK = Path(".planning/phases/07-bayesian-pace-model/07-05-evaluation-lock.json")
DEFAULT_REPORT = Path("reports/pace/phase-07.json")
LOCKED_RACES = ("2025-01", "2025-02", "2025-03")
MODEL_CONFIG = {
    "model": "hierarchical-v1",
    "advi_iterations": 50_000,
    "posterior_draws": 256,
    "loss_window": 1_000,
    "maximum_relative_loss_change": 0.06,
}


@dataclass(frozen=True)
class _TargetFeatures:
    race_id: str
    cutoff_lap: int
    driver_number: int
    target_lap: int
    compound: str
    tire_age: int
    expected_stint: int | None


@dataclass(frozen=True)
class _Prediction:
    features: _TargetFeatures
    linear_mean_s: float
    bayesian_mean_s: float


@dataclass(frozen=True)
class _CutoffFitResult:
    prediction_means_s: tuple[float | None, ...]
    n_rows: int | None
    loss_relative_change: float | None
    final_loss: float | None
    error: str | None = None


def _read_lock(lock_path: Path) -> tuple[dict[str, Any], str]:
    """Read and validate the immutable score protocol without opening race outcomes."""
    raw = lock_path.read_bytes()
    try:
        lock = json.loads(raw)
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid evaluation lock JSON: {err.msg}") from err
    if not isinstance(lock, dict) or lock.get("schema_version") != 1:
        raise ValueError("Evaluation lock must be a schema-version 1 JSON object")
    if lock.get("registered_before_scoring") is not True:
        raise ValueError("Evaluation protocol must be marked as registered before scoring")
    split = lock.get("split")
    if not isinstance(split, dict) or tuple(split.get("race_ids", ())) != LOCKED_RACES:
        raise ValueError(f"Evaluation lock must use the fixed race order {LOCKED_RACES}")
    distances = split.get("scheduled_laps")
    cutoffs = split.get("eligible_cutoff_laps")
    if not isinstance(distances, dict) or not isinstance(cutoffs, dict):
        raise ValueError("Evaluation lock must specify scheduled laps and eligible cutoffs")
    for race_id in LOCKED_RACES:
        distance = distances.get(race_id)
        bounds = cutoffs.get(race_id)
        if (
            isinstance(distance, bool)
            or not isinstance(distance, int)
            or distance < 2
            or not isinstance(bounds, dict)
            or bounds.get("first") != 0
            or bounds.get("last_inclusive") != distance - 1
            or bounds.get("step") != 1
        ):
            raise ValueError(f"Evaluation lock has invalid cutoff coverage for {race_id}")
    metric = lock.get("metric")
    if (
        not isinstance(metric, dict)
        or metric.get("minimum_paired_targets") != 500
        or metric.get("name") != "paired_next_lap_mean_absolute_error_seconds"
    ):
        raise ValueError("Evaluation lock does not match the registered paired-MAE gate")
    training = lock.get("training")
    if (
        not isinstance(training, dict)
        or training.get("bayesian_iterations") != MODEL_CONFIG["advi_iterations"]
        or training.get("posterior_draws") != MODEL_CONFIG["posterior_draws"]
        or training.get("advi_loss_window") != MODEL_CONFIG["loss_window"]
        or training.get("advi_max_relative_change") != MODEL_CONFIG["maximum_relative_loss_change"]
    ):
        raise ValueError("Evaluation lock model configuration does not match this evaluator")
    randomness = lock.get("randomness")
    if (
        not isinstance(randomness, dict)
        or randomness.get("base_seed") != 0
        or randomness.get("shared_across_drivers_at_cutoff") is not True
        or randomness.get("fit_seed")
        != "(base_seed + crc32(f'{race_id}:pace:{cutoff_lap}')) & 0x7fffffff"
    ):
        raise ValueError("Evaluation lock seed derivation does not match this evaluator")
    return lock, hashlib.sha256(raw).hexdigest()


def _eligible_cutoffs(lock: dict[str, Any], race_id: str) -> tuple[int, ...]:
    """Expand a locked inclusive arithmetic range after validating its shape."""
    split = lock["split"]
    bounds = split["eligible_cutoff_laps"][race_id]
    return tuple(range(bounds["first"], bounds["last_inclusive"] + 1, bounds["step"]))


def _target_features(snapshot: RaceSnapshot) -> tuple[_TargetFeatures, ...]:
    """Build next-lap predictors only from cutoff-known car, entry and stint state."""
    entries = snapshot.entries.set_index("driver_number")
    stints = snapshot.stints.sort_values(["driver_number", "stint"], kind="stable")
    stint_by_driver = {
        int(str(number)): group.iloc[-1]
        for number, group in stints.groupby("driver_number", sort=True)
    }
    rows: list[_TargetFeatures] = []
    cutoff_lap = snapshot.at.lap
    if not isinstance(cutoff_lap, int):
        raise ValueError("Target predictors require an integer race cutoff")
    for car in snapshot.cars.itertuples(index=False):
        number = int(str(car.driver_number))
        if number not in entries.index:
            continue
        target_lap = int(str(car.laps_done)) + 1
        if target_lap > int(snapshot.race.scheduled_laps or 0):
            continue
        if not snapshot.laps.empty and bool(
            (
                snapshot.laps["driver_number"].astype(int).eq(number)
                & snapshot.laps["lap_number"].astype(int).eq(target_lap)
            ).any()
        ):
            # A target already present at the fit cutoff is ineligible, even if a malformed cache
            # makes laps_done and lap_number disagree.
            continue
        entry = entries.loc[number]
        current_stint = stint_by_driver.get(number)
        if current_stint is not None:
            compound_value = current_stint["compound"]
            age_value = current_stint["tyre_life_now"]
            stint_value = current_stint["stint"]
            expected_stint = None if pd.isna(stint_value) else int(str(stint_value))
        else:
            compound_value = entry["start_compound"]
            age_value = entry["start_tyre_age"]
            expected_stint = None
        if not isinstance(compound_value, str) or pd.isna(age_value):
            continue
        compound = compound_value.strip().upper()
        age = int(str(age_value))
        if compound not in ("SOFT", "MEDIUM", "HARD") or age < 0:
            continue
        rows.append(
            _TargetFeatures(
                race_id=str(snapshot.race.race_id),
                cutoff_lap=cutoff_lap,
                driver_number=number,
                target_lap=target_lap,
                compound=compound,
                tire_age=age + 1,
                expected_stint=expected_stint,
            )
        )
    return tuple(rows)


def _predict_one(fit: object, feature: _TargetFeatures) -> float | None:
    """Return a finite pace mean, omitting unsupported driver/compound rows."""
    try:
        mean, _sd = fit.predict(  # type: ignore[attr-defined]
            driver=np.asarray([feature.driver_number], dtype=np.int64),
            compound=np.asarray([feature.compound], dtype=np.str_),
            tire_age=np.asarray([feature.tire_age], dtype=np.int64),
            lap=np.asarray([feature.target_lap], dtype=np.int64),
        )
    except (KeyError, ValueError):
        return None
    value = float(mean[0])
    return value if math.isfinite(value) else None


def _fit_bayesian(panel: object, *, seed: int) -> object:
    """Import PyMC only when the locked evaluation is explicitly run."""
    from f1si.pace.bayesian import fit_bayesian_panel

    return fit_bayesian_panel(panel, seed=seed)  # type: ignore[arg-type]


def _fit_cutoff_worker(
    db_path: str,
    race_id: str,
    cutoff_lap: int,
    seed: int,
    features: tuple[_TargetFeatures, ...],
    connection: Connection,
) -> None:
    """Refit one cutoff in a short-lived process so PyTensor releases memory on exit."""
    try:
        accessor = AsOfAccessor(Path(db_path))
        at = AsOf(race_id, cutoff_lap)
        snapshot = accessor.snapshot(at)
        history = accessor.history(at)
        panel = build_bayesian_training_panel(snapshot, history)
        fit = _fit_bayesian(panel, seed=seed)
        means = tuple(_predict_one(fit, feature) for feature in features)
        report = fit.report  # type: ignore[attr-defined]
        result = _CutoffFitResult(
            prediction_means_s=means,
            n_rows=int(report.n_rows),
            loss_relative_change=float(report.loss_relative_change),
            final_loss=float(report.final_loss),
        )
    except Exception as err:
        result = _CutoffFitResult((), None, None, None, str(err))
    try:
        connection.send(result)
    finally:
        connection.close()


def _fit_cutoff_isolated(
    db_path: Path,
    race_id: str,
    cutoff_lap: int,
    seed: int,
    features: tuple[_TargetFeatures, ...],
) -> _CutoffFitResult:
    """Spawn and join one isolated Bayesian fit worker for a race/cutoff."""
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(
        target=_fit_cutoff_worker,
        args=(str(db_path), race_id, cutoff_lap, seed, features, send),
        name=f"f1si-pace-{race_id}-{cutoff_lap}",
    )
    process.start()
    send.close()
    try:
        result = receive.recv()
    except EOFError as err:
        process.join()
        exit_code = process.exitcode
        process.close()
        raise RuntimeError(
            f"Bayesian worker exited without a result (exit code {exit_code})"
        ) from err
    finally:
        receive.close()
    process.join()
    exit_code = process.exitcode
    process.close()
    if exit_code != 0:
        raise RuntimeError(f"Bayesian worker exited with code {exit_code}")
    if not isinstance(result, _CutoffFitResult):
        raise RuntimeError("Bayesian worker returned an invalid result")
    return result


def _fit_seed(lock: dict[str, Any], race_id: str, cutoff_lap: int) -> int:
    base_seed = int(lock["randomness"]["base_seed"])
    return (base_seed + zlib.crc32(f"{race_id}:pace:{cutoff_lap}".encode())) & 0x7FFFFFFF


def _pair_predictions(
    predictions: tuple[_Prediction, ...], final_laps: pd.DataFrame
) -> tuple[dict[str, float | int | str], ...]:
    """Apply the clean target mask and return one identical paired row per finite prediction."""
    if final_laps.empty or not predictions:
        return ()
    target_laps = final_laps.reset_index(drop=True)
    clean = _classify(target_laps)
    targets: dict[tuple[int, int], tuple[float, str, int | None, bool]] = {}
    for index in range(len(target_laps)):
        row = target_laps.iloc[index]
        classified = clean.iloc[index]
        driver_number = int(str(row["driver_number"]))
        lap_number = int(str(row["lap_number"]))
        compound = classified["compound"]
        stint_value = row["stint"]
        stint = None if pd.isna(stint_value) else int(str(stint_value))
        time_s = float(classified["time"])
        lap_end_s = pd.to_numeric(pd.Series([row["lap_end_s"]]), errors="coerce").iloc[0]
        is_clean = (
            classified["reason"] is None
            and math.isfinite(time_s)
            and pd.notna(lap_end_s)
            and math.isfinite(float(lap_end_s))
        )
        targets[(driver_number, lap_number)] = (time_s, str(compound), stint, is_clean)
    paired: list[dict[str, float | int | str]] = []
    for prediction in predictions:
        feature = prediction.features
        target = targets.get((feature.driver_number, feature.target_lap))
        if target is None:
            continue
        actual_s, compound, stint, is_clean = target
        if not is_clean or compound.upper() != feature.compound:
            continue
        if feature.expected_stint is not None and stint != feature.expected_stint:
            continue
        if not (
            math.isfinite(actual_s)
            and math.isfinite(prediction.linear_mean_s)
            and math.isfinite(prediction.bayesian_mean_s)
        ):
            continue
        paired.append(
            {
                "race_id": feature.race_id,
                "cutoff_lap": feature.cutoff_lap,
                "driver_number": feature.driver_number,
                "target_lap": feature.target_lap,
                "actual_s": actual_s,
                "linear_prediction_s": prediction.linear_mean_s,
                "bayesian_prediction_s": prediction.bayesian_mean_s,
            }
        )
    return tuple(paired)


def _absolute_errors(
    rows: tuple[dict[str, float | int | str], ...],
) -> tuple[list[float], list[float]]:
    linear = [abs(float(row["actual_s"]) - float(row["linear_prediction_s"])) for row in rows]
    bayesian = [abs(float(row["actual_s"]) - float(row["bayesian_prediction_s"])) for row in rows]
    return linear, bayesian


def _existing_report(report_path: Path, lock_sha256: str) -> dict[str, Any]:
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ValueError(f"Cannot verify existing evaluation report: {err}") from err
    if not isinstance(report, dict) or report.get("lock_sha256") != lock_sha256:
        raise ValueError("Existing report does not match the committed evaluation lock")
    if report.get("status") != "completed":
        raise ValueError("Existing evaluation report is not marked completed")
    return report


def run_locked_evaluation(
    *,
    db_path: Path,
    lock_path: Path = DEFAULT_LOCK,
    report_path: Path = DEFAULT_REPORT,
    verify_existing: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run the committed holdout once, or verify its report without refitting."""
    lock, lock_sha256 = _read_lock(lock_path)
    if report_path.exists():
        if verify_existing:
            return _existing_report(report_path, lock_sha256)
        raise ValueError(
            f"Evaluation report already exists at {report_path}; use --verify-existing to read it."
        )
    if verify_existing:
        raise ValueError(f"No existing evaluation report found at {report_path} to verify")

    started = time.monotonic()
    accessor = AsOfAccessor(db_path)
    predictions_by_race: dict[str, list[_Prediction]] = {race_id: [] for race_id in LOCKED_RACES}
    fit_changes: list[float] = []
    fit_losses: list[float] = []
    fit_attempts = 0
    fit_failures: list[dict[str, str | int]] = []
    baseline_prediction_cutoffs = 0
    bayesian_prediction_cutoffs = 0
    skipped_cutoffs = 0

    for race_index, race_id in enumerate(LOCKED_RACES, start=1):
        first_snapshot = accessor.snapshot(AsOf(race_id, 0))
        actual_distance = first_snapshot.race.scheduled_laps
        locked_distance = int(lock["split"]["scheduled_laps"][race_id])
        if actual_distance != locked_distance:
            raise ValueError(
                f"Locked distance for {race_id} is {locked_distance}, cache says {actual_distance}"
            )
        cutoffs = _eligible_cutoffs(lock, race_id)
        if progress:
            progress(f"[{race_index}/3] {race_id}: fitting at {len(cutoffs)} locked cutoffs")
        for cutoff_lap in cutoffs:
            at = AsOf(race_id, cutoff_lap)
            snapshot = first_snapshot if cutoff_lap == 0 else accessor.snapshot(at)
            features = _target_features(snapshot)
            if not features:
                skipped_cutoffs += 1
                continue
            linear_fit: LinearPaceFit = fit_linear_pace(snapshot)
            linear_predictions = {
                feature.driver_number: mean
                for feature in features
                if (mean := _predict_one(linear_fit, feature)) is not None
            }
            if not linear_predictions:
                skipped_cutoffs += 1
                continue
            baseline_prediction_cutoffs += 1

            fit_features = tuple(
                feature for feature in features if feature.driver_number in linear_predictions
            )
            fit_attempts += 1
            seed = _fit_seed(lock, race_id, cutoff_lap)
            try:
                fit_result = _fit_cutoff_isolated(db_path, race_id, cutoff_lap, seed, fit_features)
            except (RuntimeError, ValueError, FloatingPointError) as err:
                fit_failures.append(
                    {"race_id": race_id, "cutoff_lap": cutoff_lap, "reason": str(err)}
                )
                if progress:
                    progress(f"  lap {cutoff_lap}: Bayesian fit failed: {err}")
                gc.collect()
                continue
            if fit_result.error is not None:
                fit_failures.append(
                    {
                        "race_id": race_id,
                        "cutoff_lap": cutoff_lap,
                        "reason": fit_result.error,
                    }
                )
                if progress:
                    progress(f"  lap {cutoff_lap}: Bayesian fit failed: {fit_result.error}")
                gc.collect()
                continue
            if (
                fit_result.n_rows is None
                or fit_result.loss_relative_change is None
                or fit_result.final_loss is None
                or len(fit_result.prediction_means_s) != len(fit_features)
            ):
                fit_failures.append(
                    {
                        "race_id": race_id,
                        "cutoff_lap": cutoff_lap,
                        "reason": "Bayesian worker returned incomplete fit diagnostics",
                    }
                )
                gc.collect()
                continue
            fit_changes.append(fit_result.loss_relative_change)
            fit_losses.append(fit_result.final_loss)
            cutoff_predictions = 0
            for feature, bayesian_mean in zip(
                fit_features, fit_result.prediction_means_s, strict=True
            ):
                if bayesian_mean is None:
                    continue
                linear_mean = linear_predictions[feature.driver_number]
                predictions_by_race[race_id].append(
                    _Prediction(feature, linear_mean, bayesian_mean)
                )
                cutoff_predictions += 1
            if cutoff_predictions:
                bayesian_prediction_cutoffs += 1
            if progress and (cutoff_lap % 5 == 0 or cutoff_lap == cutoffs[-1]):
                progress(
                    f"  lap {cutoff_lap}: fit rows={fit_result.n_rows}; "
                    f"shared predictor candidates={cutoff_predictions}"
                )
            del linear_fit
            gc.collect()

    # Only after every cutoff fit and prediction is finished do we open target lap times.
    per_race_rows: dict[str, tuple[dict[str, float | int | str], ...]] = {}
    for race_id in LOCKED_RACES:
        final_snapshot = accessor.snapshot(AsOf(race_id, RACE_END))
        per_race_rows[race_id] = _pair_predictions(
            tuple(predictions_by_race[race_id]), final_snapshot.laps
        )

    per_race: dict[str, dict[str, float | int | None]] = {}
    all_rows: list[dict[str, float | int | str]] = []
    for race_id in LOCKED_RACES:
        rows = per_race_rows[race_id]
        all_rows.extend(rows)
        linear_errors, bayesian_errors = _absolute_errors(rows)
        unique_driver_laps = {(int(row["driver_number"]), int(row["target_lap"])) for row in rows}
        per_race[race_id] = {
            "paired_targets": len(rows),
            "unique_driver_target_laps": len(unique_driver_laps),
            "linear_mae_s": float(np.mean(linear_errors)) if rows else None,
            "bayesian_mae_s": float(np.mean(bayesian_errors)) if rows else None,
        }
    linear_errors, bayesian_errors = _absolute_errors(tuple(all_rows))
    paired_count = len(all_rows)
    unique_driver_target_laps = {
        (str(row["race_id"]), int(row["driver_number"]), int(row["target_lap"]))
        for race_rows in per_race_rows.values()
        for row in race_rows
    }
    linear_mae = float(np.mean(linear_errors)) if linear_errors else math.nan
    bayesian_mae = float(np.mean(bayesian_errors)) if bayesian_errors else math.nan
    improvement = (
        100.0 * (linear_mae - bayesian_mae) / linear_mae
        if linear_errors and linear_mae > 0.0
        else math.nan
    )
    metric_gate = paired_count >= int(lock["metric"]["minimum_paired_targets"])
    pac06_met = bool(metric_gate and math.isfinite(improvement) and improvement >= 15.0)
    finished = datetime.now(UTC).isoformat()
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "completed",
        "evaluation": "phase-07-locked-bayesian-pace-next-lap",
        "lock_sha256": lock_sha256,
        "locked_race_ids": list(LOCKED_RACES),
        "model_config": MODEL_CONFIG,
        "randomness": lock["randomness"],
        "target_definition": lock["split"]["target_mask"],
        "metric": lock["metric"],
        "paired_targets": paired_count,
        "unique_driver_target_laps": len(unique_driver_target_laps),
        "linear_mae_s": linear_mae if math.isfinite(linear_mae) else None,
        "bayesian_mae_s": bayesian_mae if math.isfinite(bayesian_mae) else None,
        "improvement_percent": improvement if math.isfinite(improvement) else None,
        "pac_06_met": pac06_met,
        "per_race": per_race,
        "fit_summary": {
            "attempts": fit_attempts,
            "successes": len(fit_changes),
            "failures": len(fit_failures),
            "failure_examples": fit_failures[:20],
            "cutoffs_with_baseline_prediction_candidates": baseline_prediction_cutoffs,
            "cutoffs_with_paired_prediction_candidates": bayesian_prediction_cutoffs,
            "cutoffs_skipped_without_baseline_targets": skipped_cutoffs,
            "advi_iterations_per_fit": MODEL_CONFIG["advi_iterations"],
            "loss_relative_change_min": min(fit_changes) if fit_changes else None,
            "loss_relative_change_median": float(np.median(fit_changes)) if fit_changes else None,
            "loss_relative_change_max": max(fit_changes) if fit_changes else None,
            "final_loss_median": float(np.median(fit_losses)) if fit_losses else None,
        },
        "era_identifiability": {
            "training_era": "ground_effect_2022_2025",
            "target_era": "ground_effect_2022_2025",
            "between_era_effect_measured": False,
            "note": lock["era_limit"],
        },
        "fit_predictions_completed_before_target_read": True,
        "started_at_utc": datetime.fromtimestamp(
            time.time() - (time.monotonic() - started), UTC
        ).isoformat(),
        "completed_at_utc": finished,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    _write_report(report_path, result)
    if progress:
        progress(
            f"Completed locked score: {paired_count} paired targets; "
            f"Bayesian MAE reduction {improvement:.2f}%"
            if math.isfinite(improvement)
            else f"Completed locked score: {paired_count} paired targets; MAE unavailable"
        )
    return result


def _write_report(report_path: Path, report: dict[str, Any]) -> None:
    """Atomically publish one compact score; refuse a concurrent second writer."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{report_path.name}.", suffix=".tmp", dir=report_path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        try:
            os.link(temp_name, report_path)
        except FileExistsError as err:
            raise ValueError(f"Evaluation report appeared during scoring: {report_path}") from err
        os.unlink(temp_name)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main(argv: list[str] | None = None) -> int:
    """Run or verify the one-shot Phase 7 pace score from a terminal."""
    parser = argparse.ArgumentParser(prog="python -m f1si.backtest.pace_evaluation")
    parser.add_argument("--data-dir", type=Path, default=paths.data_dir())
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--verify-existing",
        action="store_true",
        help="verify an existing report against the committed lock without recomputing scores",
    )
    args = parser.parse_args(argv)
    try:
        report = run_locked_evaluation(
            db_path=paths.db_path(args.data_dir),
            lock_path=args.lock,
            report_path=args.output,
            verify_existing=args.verify_existing,
            progress=print,
        )
    except (OSError, ValueError) as err:
        print(f"pace evaluation failed: {err}", file=sys.stderr)
        return 1
    if args.verify_existing:
        print(f"Verified existing report for lock {report['lock_sha256']}")
    else:
        print(f"Wrote locked pace evaluation to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
