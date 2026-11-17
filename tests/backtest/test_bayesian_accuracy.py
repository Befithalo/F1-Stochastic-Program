"""Tests for the pre-registered, one-shot Bayesian pace accuracy evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import numpy as np
import pandas as pd
import pytest

from f1si.backtest import pace_evaluation
from f1si.backtest.pace_evaluation import (
    LOCKED_RACES,
    _CutoffFitResult,
    _eligible_cutoffs,
    _fit_seed,
    _pair_predictions,
    _Prediction,
    _read_lock,
    _target_features,
    _TargetFeatures,
    run_locked_evaluation,
)
from f1si.data.asof import AsOf, RaceEnd, RaceSnapshot

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / ".planning/phases/07-bayesian-pace-model/07-05-evaluation-lock.json"
REPORT_PATH = ROOT / "reports/pace/phase-07.json"


def test_lock_freezes_the_race_order_all_cutoffs_and_seed_derivation() -> None:
    lock, digest = _read_lock(LOCK_PATH)

    assert tuple(lock["split"]["race_ids"]) == LOCKED_RACES
    assert _eligible_cutoffs(lock, "2025-01") == tuple(range(57))
    assert _eligible_cutoffs(lock, "2025-02") == tuple(range(56))
    assert _eligible_cutoffs(lock, "2025-03") == tuple(range(53))
    assert len(digest) == 64
    assert _fit_seed(lock, "2025-01", 15) == _fit_seed(lock, "2025-01", 15)
    assert _fit_seed(lock, "2025-01", 15) != _fit_seed(lock, "2025-01", 16)


def test_cutoff_target_features_use_only_known_state_for_age_and_compound() -> None:
    snapshot = cast(
        RaceSnapshot,
        SimpleNamespace(
            race=SimpleNamespace(race_id="2025-01", scheduled_laps=57),
            at=SimpleNamespace(lap=12),
            entries=pd.DataFrame(
                {
                    "driver_number": [14],
                    "start_compound": ["HARD"],
                    "start_tyre_age": [0],
                }
            ),
            stints=pd.DataFrame(
                {
                    "driver_number": [14],
                    "stint": [2],
                    "compound": ["MEDIUM"],
                    "tyre_life_now": [7],
                }
            ),
            cars=pd.DataFrame({"driver_number": [14], "laps_done": [12]}),
            laps=pd.DataFrame({"driver_number": [14], "lap_number": [12], "lap_time_s": [89.5]}),
        ),
    )

    features = _target_features(snapshot)

    assert features == (_TargetFeatures("2025-01", 12, 14, 13, "MEDIUM", 8, 2),)


def test_only_identical_finite_clean_next_lap_rows_enter_paired_mae() -> None:
    def feature(
        number: int, lap: int, compound: str = "SOFT", stint: int | None = 1
    ) -> _TargetFeatures:
        return _TargetFeatures("2025-01", 12, number, lap, compound, 3, stint)

    predictions = (
        _Prediction(feature(1, 2), 91.0, 89.0),
        _Prediction(feature(2, 3), 91.0, 89.0),
        _Prediction(feature(3, 4), 91.0, 89.0),
        _Prediction(feature(4, 5), 91.0, 89.0),
        _Prediction(feature(5, 6), float("nan"), 89.0),
        _Prediction(feature(6, 7), 91.0, 89.0),
    )
    laps = pd.DataFrame(
        {
            "driver_number": [1, 2, 3, 4, 5, 6],
            "lap_number": [2, 3, 4, 5, 6, 7],
            "lap_time_s": [90.0] * 6,
            "lap_end_s": [100.0, 200.0, 300.0, 400.0, 500.0, None],
            "tyre_life": [3] * 6,
            "stint": [1, 1, 1, 2, 1, 1],
            "compound": ["SOFT", "SOFT", "HARD", "SOFT", "SOFT", "SOFT"],
            "is_pit_in_lap": [False] * 6,
            "is_pit_out_lap": [False, True, False, False, False, False],
            "track_status": ["1"] * 6,
        }
    )

    paired = _pair_predictions(predictions, laps)

    assert len(paired) == 1
    assert paired[0]["driver_number"] == 1
    assert paired[0]["actual_s"] == 90.0
    assert paired[0]["linear_prediction_s"] == 91.0
    assert paired[0]["bayesian_prediction_s"] == 89.0


def test_one_shot_command_refuses_existing_report_and_verifies_without_scoring(
    tmp_path: Path,
) -> None:
    _lock, digest = _read_lock(LOCK_PATH)
    report = tmp_path / "phase-07.json"
    report.write_bytes(REPORT_PATH.read_bytes())

    with pytest.raises(ValueError, match="already exists"):
        run_locked_evaluation(
            db_path=tmp_path / "must-not-open.duckdb",
            lock_path=LOCK_PATH,
            report_path=report,
        )
    verified = run_locked_evaluation(
        db_path=tmp_path / "must-not-open.duckdb",
        lock_path=LOCK_PATH,
        report_path=report,
        verify_existing=True,
    )

    assert verified["lock_sha256"] == digest
    assert verified["paired_targets"] == 1348


@pytest.mark.parametrize("tamper", ["missing-races", "contradictory-mae"])
def test_existing_report_verification_rejects_incomplete_or_inconsistent_reports(
    tmp_path: Path, tamper: str
) -> None:
    report_data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if tamper == "missing-races":
        report_data["per_race"].pop("2025-01")
    else:
        report_data["linear_mae_s"] += 1.0
    report = tmp_path / "phase-07.json"
    report.write_text(json.dumps(report_data), encoding="utf-8")

    with pytest.raises(ValueError, match="Existing evaluation report"):
        run_locked_evaluation(
            db_path=tmp_path / "must-not-open.duckdb",
            lock_path=LOCK_PATH,
            report_path=report,
            verify_existing=True,
        )


def test_isolated_fit_worker_reopens_only_the_requested_cutoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    at = AsOf("2025-02", 9)
    snapshot = object()
    history = SimpleNamespace(as_of=at)
    requested: list[AsOf] = []
    fitted: list[tuple[object, int]] = []

    class FakeAccessor:
        def __init__(self, _db_path: Path) -> None:
            pass

        def snapshot(self, requested_at: AsOf) -> object:
            requested.append(requested_at)
            return snapshot

        def history(self, requested_at: AsOf) -> object:
            assert requested_at == at
            return history

    class FakeFit:
        report = SimpleNamespace(n_rows=700, loss_relative_change=0.03, final_loss=77.0)

        def predict(self, **_kwargs: object) -> tuple[np.ndarray, np.ndarray]:
            return np.asarray([88.0]), np.asarray([0.4])

    class FakeConnection:
        result: object | None = None
        closed = False

        def send(self, value: object) -> None:
            self.result = value

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(pace_evaluation, "AsOfAccessor", FakeAccessor)

    def build_panel(received_snapshot: object, received_history: object) -> str:
        assert received_snapshot is snapshot
        assert received_history is history
        return "cutoff-panel"

    def fit_panel(panel: object, *, seed: int) -> FakeFit:
        fitted.append((panel, seed))
        return FakeFit()

    monkeypatch.setattr(pace_evaluation, "build_bayesian_training_panel", build_panel)
    monkeypatch.setattr(pace_evaluation, "_fit_bayesian", fit_panel)
    connection = FakeConnection()
    feature = _TargetFeatures("2025-02", 9, 14, 10, "MEDIUM", 5, 2)

    pace_evaluation._fit_cutoff_worker(
        str(tmp_path / "cache.duckdb"),
        "2025-02",
        9,
        441,
        (feature,),
        connection,  # type: ignore[arg-type]
    )

    assert requested == [at]
    assert fitted == [("cutoff-panel", 441)]
    assert connection.result == _CutoffFitResult((88.0,), 700, 0.03, 77.0)
    assert connection.closed


def test_locked_runner_fits_every_cutoff_before_opening_target_laps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock_copy = tmp_path / "lock.json"
    lock_copy.write_bytes(LOCK_PATH.read_bytes())
    fit_races: list[str] = []
    target_reads: list[str] = []

    class FakeFit:
        def __init__(self, mean_s: float) -> None:
            self.mean_s = mean_s
            self.report = SimpleNamespace(
                n_rows=100,
                loss_relative_change=0.02,
                final_loss=123.0,
            )

        def predict(self, **_kwargs: object) -> tuple[np.ndarray, np.ndarray]:
            return np.asarray([self.mean_s]), np.asarray([0.5])

    class FakeAccessor:
        def __init__(self, _db_path: Path) -> None:
            pass

        def snapshot(self, at: object) -> object:
            asof = at
            race_id = str(asof.race_id)  # type: ignore[attr-defined]
            if isinstance(asof.lap, RaceEnd):  # type: ignore[attr-defined]
                assert fit_races == list(LOCKED_RACES)
                target_reads.append(race_id)
                return SimpleNamespace(laps=target_laps)
            distances = {"2025-01": 57, "2025-02": 56, "2025-03": 53}
            return SimpleNamespace(
                race=SimpleNamespace(race_id=race_id, scheduled_laps=distances[race_id]),
                at=asof,
            )

        def history(self, at: object) -> object:
            return SimpleNamespace(as_of=at)

    target_laps = pd.DataFrame(
        {
            "driver_number": [1],
            "lap_number": [2],
            "lap_time_s": [90.0],
            "lap_end_s": [100.0],
            "tyre_life": [2],
            "stint": [1],
            "compound": ["SOFT"],
            "is_pit_in_lap": [False],
            "is_pit_out_lap": [False],
            "track_status": ["1"],
        }
    )
    monkeypatch.setattr(pace_evaluation, "AsOfAccessor", FakeAccessor)
    monkeypatch.setattr(pace_evaluation, "_eligible_cutoffs", lambda _lock, _race: (0,))
    monkeypatch.setattr(
        pace_evaluation,
        "_target_features",
        lambda snapshot: (_TargetFeatures(str(snapshot.race.race_id), 0, 1, 2, "SOFT", 2, 1),),
    )
    monkeypatch.setattr(pace_evaluation, "fit_linear_pace", lambda _snapshot: FakeFit(91.0))

    def fit_cutoff(
        race_id: str,
        cutoff_lap: int,
        seed: int,
        features: tuple[_TargetFeatures, ...],
    ) -> _CutoffFitResult:
        assert cutoff_lap == 0
        assert seed >= 0
        assert tuple(feature.race_id for feature in features) == (race_id,)
        fit_races.append(race_id)
        return _CutoffFitResult((89.5,), 100, 0.02, 123.0)

    monkeypatch.setattr(
        pace_evaluation,
        "_fit_cutoff_isolated",
        lambda _db, race, lap, seed, features: fit_cutoff(race, lap, seed, features),
    )
    report = run_locked_evaluation(
        db_path=tmp_path / "fixture.duckdb",
        lock_path=lock_copy,
        report_path=tmp_path / "report.json",
    )

    assert fit_races == list(LOCKED_RACES)
    assert target_reads == list(LOCKED_RACES)
    assert report["paired_targets"] == 3
    assert report["linear_mae_s"] == 1.0
    assert report["bayesian_mae_s"] == 0.5
    assert report["improvement_percent"] == 50.0
    assert report["pac_06_met"] is False
