"""Locked, once-only 2026 holdout evaluation (D-02, D-05)."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import tempfile
import zlib
from pathlib import Path
from typing import Any, Final, cast

import numpy as np
import pandas as pd

from f1si.data import asof
from f1si.data.out_of_sample import OutOfSampleAccessor
from f1si.regime.markov import REGIMES, RegimeEstimate, label_regime

HOLDOUT_RACE_IDS: Final = tuple(f"2026-{round_number:02d}" for round_number in range(9, 18))
IN_SAMPLE_RACE_IDS: Final = (
    *(f"2023-{round_number:02d}" for round_number in range(1, 8)),
    *(f"2024-{round_number:02d}" for round_number in range(1, 8)),
    *(f"2025-{round_number:02d}" for round_number in range(1, 7)),
)
LOCK_PATH: Final = (
    Path(__file__).resolve().parents[3]
    / ".planning/milestones/v1.0-phases/08-markov-regimes-full-backtest/08-holdout-lock.json"
)
DEFAULT_REPORT: Final = Path("reports/backtest/phase-08-holdout.json")
LOCK_SHA256: Final = "7c181dd855048b14e5d338bec31acdd0868046b62aabe781589ee2b350adc2d6"
_SIMULATION: Final = {"pace_model": "linear", "n_simulations": 1_000, "seed": 0, "risk": 0.5}


def _load_holdout_lock(lock_path: Path = LOCK_PATH) -> dict[str, Any]:
    """Read and verify the exact holdout protocol without opening the race cache."""
    try:
        value = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ValueError(f"Could not read the committed holdout lock at {lock_path}.") from err
    if not isinstance(value, dict):
        raise ValueError("The holdout lock must be a JSON object.")
    digest = value.get("lock_digest")
    if not isinstance(digest, dict) or digest.get("algorithm") != "sha256":
        raise ValueError("The holdout lock has no supported digest.")
    payload = dict(value)
    payload.pop("lock_digest", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if actual != LOCK_SHA256 or digest.get("sha256") != LOCK_SHA256:
        raise ValueError("The holdout lock digest does not match the committed contract.")
    if value.get("race_ids") != list(HOLDOUT_RACE_IDS):
        raise ValueError("The holdout calendar does not match the committed lock.")
    if tuple(value.get("training", {}).get("race_ids", ())) != IN_SAMPLE_RACE_IDS:
        raise ValueError("The holdout training calendar does not match the committed lock.")
    if value.get("era") != "reg_2026" or value.get("simulation") != _SIMULATION:
        raise ValueError("The holdout era or simulation settings differ from the lock.")
    schedule = value.get("schedule")
    events = schedule.get("events") if isinstance(schedule, dict) else None
    provenance = schedule.get("provenance") if isinstance(schedule, dict) else None
    if (
        not isinstance(events, dict)
        or set(events) != set(HOLDOUT_RACE_IDS)
        or not isinstance(provenance, dict)
        or set(provenance) != set(HOLDOUT_RACE_IDS)
    ):
        raise ValueError("The holdout schedule must cover every locked race and its provenance.")
    for race_id in HOLDOUT_RACE_IDS:
        event = events[race_id]
        if (
            not isinstance(event, dict)
            or not isinstance(event.get("circuit"), str)
            or type(event.get("scheduled_laps")) is not int
            or event["scheduled_laps"] < 1
            or not isinstance(provenance[race_id], str)
            or not provenance[race_id].strip()
        ):
            raise ValueError(f"The locked schedule entry is invalid for {race_id}.")
    if value.get("report_schema", {}).get("schema_version") != 1:
        raise ValueError("The holdout report schema differs from the lock.")
    return value


def _resolve_scheduled_laps(
    race_id: str,
    observed_laps: int | None,
    locked_schedule: dict[str, Any],
) -> int:
    """Use the ex-ante locked horizon and reject conflicting local metadata."""
    event = locked_schedule.get(race_id)
    if not isinstance(event, dict):
        raise ValueError(f"No locked scheduled distance is available for {race_id}.")
    locked_laps = event.get("scheduled_laps")
    if type(locked_laps) is not int or locked_laps < 1:
        raise ValueError(f"No locked scheduled distance is available for {race_id}.")
    if observed_laps is not None and observed_laps != locked_laps:
        raise ValueError(
            f"Scheduled lap metadata disagrees with locked schedule for {race_id}: "
            f"observed {observed_laps}, locked {locked_laps}."
        )
    return locked_laps


def _regime_sequences_from_snapshots(
    snapshots: tuple[asof.RaceSnapshot, ...],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    sequences: list[tuple[str, tuple[str, ...]]] = []
    for snapshot in snapshots:
        finished = snapshot.laps.loc[snapshot.laps["lap_end_s"].notna()]
        cutoffs = finished.groupby("lap_number", sort=True)["lap_end_s"].min()
        labels = tuple(
            label_regime(snapshot.track_status, snapshot.weather, float(cutoff))
            for cutoff in cutoffs.to_numpy(dtype=np.float64)
        )
        sequences.append((snapshot.race.race_id, labels))
    return tuple(sequences)


def build_in_sample_regime_sequences(
    accessor: asof.AsOfAccessor,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Build ordered transition sequences only from complete 2023-2025 RACE_END snapshots."""
    snapshots: list[asof.RaceSnapshot] = []
    for race_id in IN_SAMPLE_RACE_IDS:
        snapshot = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
        if snapshot.race.out_of_sample or snapshot.race.race_id != race_id:
            raise ValueError(f"Unexpected or out-of-sample training snapshot: {race_id}.")
        if snapshot.laps.empty or snapshot.laps["lap_end_s"].notna().sum() == 0:
            raise ValueError(f"Training race {race_id} has no complete laps.")
        snapshots.append(snapshot)
    return _regime_sequences_from_snapshots(tuple(snapshots))


def _feature_history(
    snapshots: tuple[asof.RaceSnapshot, ...],
) -> asof.History:
    """Assemble only public feature frames; results remain an empty typed frame."""

    def combine(name: str) -> pd.DataFrame:
        frames = [getattr(snapshot, name) for snapshot in snapshots]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    laps = combine("laps")
    cutoffs = (
        laps.loc[laps["lap_end_s"].notna()]
        .groupby(["race_id", "lap_number"], as_index=False, sort=True)["lap_end_s"]
        .min()
        .reset_index()
        .rename(columns={"lap_number": "lap", "lap_end_s": "cutoff_s"})
    )
    return asof.History(
        as_of=asof.AsOf(IN_SAMPLE_RACE_IDS[-1], asof.RACE_END),
        races=list(IN_SAMPLE_RACE_IDS),
        entries=combine("entries"),
        laps=laps,
        track_status=combine("track_status"),
        race_control=combine("race_control"),
        weather=combine("weather"),
        lap_cutoffs=cutoffs,
        results=pd.DataFrame(
            columns=["race_id", "driver_number", "final_position", "classified_position"]
        ),
    )


def _estimate_from_sequences(
    sequences: tuple[tuple[str, tuple[str, ...]], ...],
) -> RegimeEstimate:
    counts = np.zeros((len(REGIMES), len(REGIMES)), dtype=np.float64)
    indices = {name: index for index, name in enumerate(REGIMES)}
    for _race_id, labels in sequences:
        for before, after in itertools.pairwise(labels):
            counts[indices[before], indices[after]] += 1.0
    smoothed = counts + 1.0
    return RegimeEstimate(smoothed / smoothed.sum(axis=1, keepdims=True), counts, int(counts.sum()))


def _preflight_catalog(db_path: Path) -> None:
    catalog = asof.catalog(db_path)
    rows = catalog.set_index("race_id")
    missing = [race_id for race_id in HOLDOUT_RACE_IDS if race_id not in rows.index]
    invalid = [
        race_id
        for race_id in HOLDOUT_RACE_IDS
        if race_id in rows.index
        and (
            rows.loc[race_id, "load_status"] != "complete"
            or not bool(rows.loc[race_id, "out_of_sample"])
        )
    ]
    if missing or invalid:
        failed = missing + invalid
        raise ValueError(
            "Holdout cache must contain every complete locked out-of-sample race: "
            + ", ".join(failed)
        )


def _frozen_predictions(
    db_path: Path,
    *,
    n_simulations: int,
    risk: float,
    seed: int,
    pace_model: str,
    locked_schedule: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    from f1si.cli import _prepare_replay_context, _replay_at_cutoff
    from f1si.data.asof import AsOfAccessor

    training_accessor = AsOfAccessor(db_path)
    sequences = build_in_sample_regime_sequences(training_accessor)
    snapshots = tuple(
        training_accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
        for race_id in IN_SAMPLE_RACE_IDS
    )
    regime_fit = _estimate_from_sequences(sequences)
    history = _feature_history(snapshots)
    accessor = OutOfSampleAccessor(db_path)
    frozen: list[dict[str, Any]] = []
    for race_id in HOLDOUT_RACE_IDS:
        first = accessor.snapshot(asof.AsOf(race_id, 0))
        laps_total = _resolve_scheduled_laps(race_id, first.race.scheduled_laps, locked_schedule)
        for lap in range(laps_total):
            snapshot = first if lap == 0 else accessor.snapshot(asof.AsOf(race_id, lap))
            prepared = _prepare_replay_context(
                cast(Any, accessor),
                race_id,
                laps_total,
                lap,
                snapshot=cast(Any, snapshot),
                pace_model=pace_model,
                seed=(seed + zlib.crc32(f"{race_id}:pace:{lap}".encode())) & 0x7FFFFFFF,
                history_override=history,
                regime_estimate_override=regime_fit,
            )
            for driver in sorted(str(value) for value in snapshot.entries["driver_code"]):
                result = _replay_at_cutoff(
                    cast(Any, accessor),
                    race_id,
                    laps_total,
                    driver,
                    lap,
                    n_simulations=n_simulations,
                    risk=risk,
                    seed=(seed + zlib.crc32(f"{race_id}:{driver}:{lap}".encode())) & 0x7FFFFFFF,
                    prepared_context=prepared,
                    pace_model=pace_model,
                )
                analysis = result.analysis
                frozen.append(
                    {
                        "race_id": race_id,
                        "driver": driver,
                        "cutoff_lap": lap,
                        "available": analysis is not None,
                        "unavailable_reason": result.unavailable_reason,
                        "top_action": None if analysis is None else analysis.best.action,
                        "planned_stop_lap": (
                            None
                            if analysis is None or not analysis.best.plan.stop_laps
                            else analysis.best.plan.stop_laps[0]
                        ),
                        "podium_probability": None
                        if analysis is None
                        else analysis.best.podium_probability,
                        "top10_probability": None
                        if analysis is None
                        else analysis.best.top10_probability,
                        "finish_p05": None if analysis is None else analysis.best.finish_p05,
                        "finish_p95": None if analysis is None else analysis.best.finish_p95,
                    }
                )
    return tuple(frozen)


def score_holdout(
    db_path: Path,
    *,
    report_path: Path = DEFAULT_REPORT,
    lock_path: Path = LOCK_PATH,
    n_simulations: int = 1_000,
    risk: float = 0.5,
    seed: int = 0,
    pace_model: str = "linear",
) -> dict[str, Any]:
    """Score once; all predictions are frozen before the first protected result query."""
    lock = _load_holdout_lock(lock_path)
    supplied = {
        "pace_model": pace_model,
        "n_simulations": n_simulations,
        "seed": seed,
        "risk": risk,
    }
    if supplied != lock["simulation"]:
        raise ValueError(f"Holdout settings differ from the committed lock: {supplied!r}.")
    if report_path.exists():
        raise ValueError(f"Refusing to overwrite existing holdout report at {report_path}.")
    _preflight_catalog(db_path)
    predictions = _frozen_predictions(
        db_path,
        n_simulations=n_simulations,
        risk=risk,
        seed=seed,
        pace_model=pace_model,
        locked_schedule=lock["schedule"]["events"],
    )
    accessor = OutOfSampleAccessor(db_path)
    strategy_by_race: dict[str, dict[str, int | float | None]] = {}
    strategy_events: list[tuple[str, str, int]] = []
    for race_id in HOLDOUT_RACE_IDS:
        end = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
        codes = end.entries.set_index("driver_number")["driver_code"]
        for event in end.pit_events.itertuples(index=False):
            code = codes.get(cast(int, event.driver_number))
            if code is not None:
                strategy_events.append((race_id, str(code).upper(), cast(int, event.in_lap)))
    strategy_errors: list[int] = []
    strategy_matched = 0
    strategy_agreements = 0
    for race_id in HOLDOUT_RACE_IDS:
        race_errors: list[int] = []
        race_matched = 0
        race_agreements = 0
        for stop_race, driver, in_lap in strategy_events:
            if stop_race != race_id:
                continue
            eligible = [
                row
                for row in predictions
                if row["race_id"] == race_id
                and row["driver"] == driver
                and row["available"]
                and row["cutoff_lap"] < in_lap
            ]
            if not eligible:
                continue
            recommendation = max(eligible, key=lambda row: row["cutoff_lap"])
            planned = recommendation["planned_stop_lap"]
            if planned is None:
                continue
            error = int(planned) - in_lap
            race_errors.append(error)
            strategy_errors.append(error)
            race_matched += 1
            race_agreements += int(error == 0)
        strategy_by_race[race_id] = {
            "observed_stop_events": sum(1 for item in strategy_events if item[0] == race_id),
            "matched_stop_events": race_matched,
            "signed_timing_error_laps": None if not race_errors else float(np.mean(race_errors)),
            "agreement": None if not race_matched else race_agreements / race_matched,
        }
        strategy_matched += race_matched
        strategy_agreements += race_agreements
    race_results = {race_id: accessor.final_classification(race_id) for race_id in HOLDOUT_RACE_IDS}
    per_race: dict[str, dict[str, Any]] = {}
    brier_podium: list[float] = []
    brier_top10: list[float] = []
    coverage_hits = 0
    classified_count = 0
    for race_id in HOLDOUT_RACE_IDS:
        frame = race_results[race_id].copy()
        frame["driver_code"] = frame["driver_code"].astype(str).str.upper()
        classified = {
            str(row.driver_code).upper(): row.final_position
            for row in frame.itertuples(index=False)
        }
        rows = [row for row in predictions if row["race_id"] == race_id and row["available"]]
        podium_scores: list[float] = []
        top10_scores: list[float] = []
        race_hits = 0
        race_finishers = 0
        for row in rows:
            if row["driver"] not in classified:
                continue
            raw_position = classified[row["driver"]]
            position = (
                None if raw_position is None or pd.isna(raw_position) else cast(int, raw_position)
            )
            podium_target = position is not None and 0 < position <= 3
            top10_target = position is not None and 0 < position <= 10
            podium_scores.append((float(row["podium_probability"]) - float(podium_target)) ** 2)
            top10_scores.append((float(row["top10_probability"]) - float(top10_target)) ** 2)
            if position is not None and position > 0:
                race_finishers += 1
                race_hits += int(int(row["finish_p05"]) <= position <= int(row["finish_p95"]))
        if podium_scores:
            brier_podium.append(float(np.mean(podium_scores)))
        if top10_scores:
            brier_top10.append(float(np.mean(top10_scores)))
        coverage_hits += race_hits
        classified_count += race_finishers
        per_race[race_id] = {
            "era": "reg_2026",
            "prediction_count": len([row for row in predictions if row["race_id"] == race_id]),
            "scored_driver_cutoffs": len(podium_scores),
            "podium_brier": None if not podium_scores else float(np.mean(podium_scores)),
            "top10_brier": None if not top10_scores else float(np.mean(top10_scores)),
            "finish_interval_90": {
                "classified_finishers": race_finishers,
                "covered": race_hits,
                "coverage": None if not race_finishers else race_hits / race_finishers,
            },
            "strategy": strategy_by_race[race_id],
        }
    report: dict[str, Any] = {
        "schema_version": lock["report_schema"]["schema_version"],
        "race_ids": list(HOLDOUT_RACE_IDS),
        "metadata": {
            "era": "reg_2026",
            "pace_model": pace_model,
            "n_simulations": n_simulations,
            "seed": seed,
            "risk": risk,
            "locked_contract_sha256": LOCK_SHA256,
            "predictions_frozen_before_results": True,
        },
        "metrics": {
            "podium_brier": None if not brier_podium else float(np.mean(brier_podium)),
            "top10_brier": None if not brier_top10 else float(np.mean(brier_top10)),
            "race_count_with_podium_scores": len(brier_podium),
            "race_count_with_top10_scores": len(brier_top10),
            "podium_observation_count": sum(
                int(row["scored_driver_cutoffs"]) for row in per_race.values()
            ),
            "top10_observation_count": sum(
                int(row["scored_driver_cutoffs"]) for row in per_race.values()
            ),
            "finish_interval_90": {
                "classified_finishers": classified_count,
                "covered": coverage_hits,
                "coverage": None if not classified_count else coverage_hits / classified_count,
            },
            "strategy": {
                "observed_stop_events": len(strategy_events),
                "matched_stop_events": strategy_matched,
                "signed_timing_error_laps": (
                    None if not strategy_errors else float(np.mean(strategy_errors))
                ),
                "absolute_timing_error_laps": (
                    None if not strategy_errors else float(np.mean(np.abs(strategy_errors)))
                ),
                "agreement": None
                if not strategy_matched
                else strategy_agreements / strategy_matched,
                "top_action_wait_count": sum(
                    row["available"] and str(row["top_action"]).startswith("pit in ")
                    for row in predictions
                ),
                "top_action_count": len(predictions),
            },
        },
        "per_race": per_race,
        "predictions": list(predictions),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{report_path.name}.", suffix=".tmp", dir=report_path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        try:
            os.link(temporary, report_path)
        except FileExistsError as err:
            raise ValueError(f"Holdout report appeared during scoring: {report_path}.") from err
        os.unlink(temporary)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return report


_FROZEN_PREDICTION_FIELDS: Final = frozenset(
    {
        "race_id",
        "driver",
        "cutoff_lap",
        "available",
        "unavailable_reason",
        "top_action",
        "planned_stop_lap",
        "podium_probability",
        "top10_probability",
        "finish_p05",
        "finish_p95",
    }
)


def _validate_frozen_predictions(predictions: list[Any], locked_schedule: dict[str, Any]) -> None:
    """Validate the optional report trace against the rows emitted by the scorer."""
    for index, row in enumerate(predictions):
        if not isinstance(row, dict) or set(row) != _FROZEN_PREDICTION_FIELDS:
            raise ValueError(f"The holdout report has an invalid prediction row at index {index}.")
        race_id = row["race_id"]
        if not isinstance(race_id, str) or race_id not in HOLDOUT_RACE_IDS:
            raise ValueError(f"The holdout report has an invalid prediction race at index {index}.")
        driver = row["driver"]
        cutoff_lap = row["cutoff_lap"]
        if not isinstance(driver, str) or not driver.strip() or type(cutoff_lap) is not int:
            raise ValueError(
                f"The holdout report has invalid prediction identity at index {index}."
            )
        scheduled_laps = locked_schedule[race_id]["scheduled_laps"]
        if not 0 <= cutoff_lap < scheduled_laps:
            raise ValueError(f"The holdout report has an invalid cutoff lap at index {index}.")

        available = row["available"]
        unavailable_reason = row["unavailable_reason"]
        top_action = row["top_action"]
        planned_stop_lap = row["planned_stop_lap"]
        if type(available) is not bool:
            raise ValueError(
                f"The holdout report has an invalid availability flag at index {index}."
            )
        if available:
            if (
                unavailable_reason is not None
                or not isinstance(top_action, str)
                or not top_action.strip()
            ):
                raise ValueError(
                    f"The holdout report has invalid available prediction details at index {index}."
                )
        elif not isinstance(unavailable_reason, str) or not unavailable_reason.strip():
            raise ValueError(
                f"The holdout report has an invalid unavailable reason at index {index}."
            )
        if planned_stop_lap is not None and (
            type(planned_stop_lap) is not int or not 1 <= planned_stop_lap <= scheduled_laps
        ):
            raise ValueError(
                f"The holdout report has an invalid planned stop lap at index {index}."
            )

        for field in ("podium_probability", "top10_probability"):
            value = row[field]
            if available:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or not 0.0 <= value <= 1.0
                ):
                    raise ValueError(f"The holdout report has an invalid {field} at index {index}.")
            elif value is not None:
                raise ValueError(f"The holdout report has an invalid {field} at index {index}.")

        finish_values = (row["finish_p05"], row["finish_p95"])
        if available:
            if (
                any(
                    type(value) is not int or not 1 <= value <= scheduled_laps
                    for value in finish_values
                )
                or finish_values[0] > finish_values[1]
            ):
                raise ValueError(
                    f"The holdout report has an invalid finish interval at index {index}."
                )
        elif (
            any(value is not None for value in finish_values)
            or top_action is not None
            or planned_stop_lap is not None
        ):
            raise ValueError(
                f"The holdout report has invalid unavailable prediction details at index {index}."
            )


def verify_holdout_report(
    report_path: Path = DEFAULT_REPORT,
    *,
    lock_path: Path = LOCK_PATH,
) -> dict[str, Any]:
    """Verify only the committed lock and JSON report; never instantiate data accessors."""
    lock = _load_holdout_lock(lock_path)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ValueError(f"Could not read a valid holdout report at {report_path}.") from err
    required_fields = set(lock["report_schema"]["required_top_level_fields"])
    # The lock enumerates required fields, while score_holdout also persists the
    # frozen driver/cutoff predictions used to compute the aggregates. Keep that
    # known extension optional for compatibility with minimal verification
    # fixtures, and reject any other unregistered top-level fields.
    allowed_fields = required_fields | {"predictions"}
    if (
        not isinstance(report, dict)
        or not required_fields.issubset(report)
        or not set(report).issubset(allowed_fields)
    ):
        raise ValueError("The holdout report does not match the locked top-level schema.")
    if "predictions" in report:
        if not isinstance(report["predictions"], list):
            raise ValueError("The holdout report predictions extension must be a list.")
        _validate_frozen_predictions(report["predictions"], lock["schedule"]["events"])
    if report.get("schema_version") != lock["report_schema"]["schema_version"]:
        raise ValueError("The holdout report schema version differs from the lock.")
    if report.get("race_ids") != list(HOLDOUT_RACE_IDS):
        raise ValueError("The holdout report race IDs differ from the lock.")
    metadata = report.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("locked_contract_sha256") != LOCK_SHA256:
        raise ValueError("The holdout report is not bound to the committed lock.")
    per_race = report.get("per_race")
    if not isinstance(per_race, dict) or tuple(per_race) != HOLDOUT_RACE_IDS:
        raise ValueError("The holdout report must retain all race rows in locked order.")
    for race_id, row in per_race.items():
        if not isinstance(row, dict) or row.get("era") != "reg_2026":
            raise ValueError(f"The holdout report has an invalid race row for {race_id}.")
        for key in ("prediction_count", "scored_driver_cutoffs"):
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"The holdout report has an invalid {key} for {race_id}.")
    return cast(dict[str, Any], report)
