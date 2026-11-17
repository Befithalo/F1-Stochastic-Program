"""Holdout protocol contracts; all result access is represented by fakes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import f1si.evaluation.holdout as holdout
from f1si.cli import build_parser
from f1si.data import asof
from f1si.evaluation.holdout import (
    HOLDOUT_RACE_IDS,
    _load_holdout_lock,
    build_in_sample_regime_sequences,
    score_holdout,
    verify_holdout_report,
)


def test_holdout_lock_freezes_exact_contract_and_digest() -> None:
    lock = _load_holdout_lock()
    assert lock["race_ids"] == [f"2026-{round_number:02d}" for round_number in range(9, 18)]
    assert tuple(lock["race_ids"]) == HOLDOUT_RACE_IDS
    assert lock["era"] == "reg_2026"
    assert lock["simulation"] == {
        "pace_model": "linear",
        "n_simulations": 1000,
        "seed": 0,
        "risk": 0.5,
    }
    payload = dict(lock)
    digest = payload.pop("lock_digest")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert digest["sha256"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_exact_score_command_parses_without_opening_data() -> None:
    args = build_parser().parse_args(
        [
            "holdout",
            "--score",
            "--output",
            "reports/backtest/phase-08-holdout.json",
            "--n",
            "1000",
            "--risk",
            "0.5",
            "--seed",
            "0",
        ]
    )
    assert args.command == "holdout"
    assert args.score is True
    assert args.verify_existing is False
    assert args.n == 1000
    assert args.risk == 0.5
    assert args.seed == 0


def test_regime_sequences_use_only_registered_in_sample_race_end_snapshots() -> None:
    class FakeAccessor:
        def __init__(self) -> None:
            self.calls: list[asof.AsOf] = []

        def snapshot(self, at: asof.AsOf) -> object:
            self.calls.append(at)
            assert at.race_id in {f"2023-{n:02d}" for n in range(1, 8)} | {
                f"2024-{n:02d}" for n in range(1, 8)
            } | {f"2025-{n:02d}" for n in range(1, 7)}
            assert isinstance(at.lap, asof.RaceEnd)
            return type(
                "Snapshot",
                (),
                {
                    "race": type("Race", (), {"race_id": at.race_id, "out_of_sample": False})(),
                    "laps": pd.DataFrame({"lap_number": [1, 2], "lap_end_s": [60.0, 120.0]}),
                    "track_status": pd.DataFrame(columns=["t_s", "status"]),
                    "weather": pd.DataFrame(columns=["t_s", "seq", "rainfall"]),
                },
            )()

    accessor = FakeAccessor()
    sequences = build_in_sample_regime_sequences(accessor)  # type: ignore[arg-type]
    assert len(sequences) == 20
    assert [race_id for race_id, _ in sequences] == list(
        dict.fromkeys(at.race_id for at in accessor.calls)
    )
    assert all(sequence == ("green", "green") for _, sequence in sequences)
    assert len(accessor.calls) == 20


def test_verify_existing_reads_only_lock_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = {
        "schema_version": 1,
        "race_ids": [f"2026-{n:02d}" for n in range(9, 18)],
        "metadata": {"locked_contract_sha256": _load_holdout_lock()["lock_digest"]["sha256"]},
        "metrics": {
            "race_denominators": {f"2026-{n:02d}": {"era": "reg_2026"} for n in range(9, 18)}
        },
        "per_race": {
            f"2026-{n:02d}": {
                "era": "reg_2026",
                "prediction_count": 0,
                "scored_driver_cutoffs": 0,
            }
            for n in range(9, 18)
        },
    }
    path = tmp_path / "holdout.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(holdout.asof, "catalog", lambda *_: pytest.fail("catalog access"))
    monkeypatch.setattr(holdout, "OutOfSampleAccessor", lambda *_: pytest.fail("results access"))
    assert verify_holdout_report(path)["race_ids"] == report["race_ids"]


def test_score_freezes_predictions_before_first_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    class FakeResults:
        def __init__(self, _db_path: Path) -> None:
            pass

        def snapshot(self, _at: asof.AsOf) -> object:
            assert events[0] == "predictions"
            return SimpleNamespace(
                entries=pd.DataFrame(columns=["driver_number", "driver_code"]),
                pit_events=pd.DataFrame(columns=["driver_number", "in_lap"]),
            )

        def final_classification(self, race_id: str) -> pd.DataFrame:
            assert events[0] == "predictions"
            events.append(f"result:{race_id}")
            return pd.DataFrame(columns=["driver_code", "final_position"])

    monkeypatch.setattr(holdout, "_preflight_catalog", lambda _db: None)
    monkeypatch.setattr(
        holdout,
        "_frozen_predictions",
        lambda *_args, **_kwargs: events.append("predictions") or (),
    )
    monkeypatch.setattr(holdout, "OutOfSampleAccessor", FakeResults)
    result = score_holdout(Path("unused.duckdb"), report_path=tmp_path / "report.json")
    assert result["metadata"]["predictions_frozen_before_results"] is True
    assert events[0] == "predictions"
    assert events[1:] == [f"result:{race_id}" for race_id in HOLDOUT_RACE_IDS]


def test_score_refuses_existing_report_before_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "existing.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        holdout,
        "_preflight_catalog",
        lambda *_: pytest.fail("catalog preflight after output exists"),
    )
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        score_holdout(Path("unused.duckdb"), report_path=path)
