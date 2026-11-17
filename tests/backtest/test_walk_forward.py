"""Contracts for the Phase 6 fixed-sample, prediction-only walk-forward runner."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pandas as pd
import pytest

import f1si.backtest.walk_forward as walk_forward
from f1si.backtest.walk_forward import (
    REGISTERED_RACE_IDS,
    PredictionRow,
    predict_at_cutoff,
    preflight_races,
    run_walk_forward,
)
from f1si.cli import main
from f1si.data import asof
from f1si.strategy.longstaff import StrategyAnalysis
from tests.conftest import LONG_RACE_ID

PHASE_08_RACES = (
    "2023-01",
    "2023-02",
    "2023-03",
    "2023-04",
    "2023-05",
    "2023-06",
    "2023-07",
    "2024-01",
    "2024-02",
    "2024-03",
    "2024-04",
    "2024-05",
    "2024-06",
    "2024-07",
    "2025-01",
    "2025-02",
    "2025-03",
    "2025-04",
    "2025-05",
    "2025-06",
)


def test_phase_08_in_sample_lock_records_exact_calendar_and_settings() -> None:
    lock_path = (
        Path(__file__).parents[2]
        / ".planning/phases/08-markov-regimes-full-backtest/08-in-sample-evaluation-lock.json"
    )
    lock = json.loads(lock_path.read_text(encoding="utf-8"))

    assert lock["race_ids"] == list(PHASE_08_RACES)
    assert lock["era_by_race"] == {race_id: "ground_effect_2022_2025" for race_id in PHASE_08_RACES}
    assert lock["simulation"] == {
        "pace_model": "linear",
        "n_simulations": 1_000,
        "base_seed": 0,
        "risk": 0.5,
    }
    assert lock["sample_boundary"]["preflight"].startswith("every listed race")
    assert lock["randomness"]["prediction_seed"].startswith("(base_seed + crc32")
    assert lock["randomness"]["pace_fit_seed_scope"] == (
        "shared by all drivers at one race and cutoff"
    )
    assert lock["randomness"]["bootstrap_resamples"] == 2_000
    assert len(lock["cutoff_and_target"]["target_mask"]) == 5
    assert {
        "podium_brier",
        "top10_brier",
        "paired_probability_mask",
        "finish_interval_90",
        "team_strategy_comparison",
        "wear_band_retrospective_proxy",
        "aggregation",
        "uncertainty",
        "empty_race_rule",
    } == set(lock["metrics"])
    assert lock["report_schema"]["schema_version"] == 1
    assert "per-race" in lock["report_schema"]["required_denominators"]
    assert lock["holdout_boundary"]["race_ids"] == [
        f"2026-{round_number:02d}" for round_number in range(9, 18)
    ]
    assert lock["holdout_boundary"]["score_policy"] == (
        "score once and never tune or rescore against the holdout"
    )

    digest_payload = dict(lock)
    del digest_payload["lock_digest"]
    canonical = json.dumps(digest_payload, sort_keys=True, separators=(",", ":"))
    assert lock["lock_digest"]["sha256"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_runner_registry_matches_the_committed_phase_08_sample() -> None:
    assert REGISTERED_RACE_IDS == PHASE_08_RACES


def _catalog(*, missing: tuple[str, ...] = ()) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "race_id": race_id,
                "load_status": "partial" if race_id in missing else "complete",
                "out_of_sample": False,
            }
            for race_id in PHASE_08_RACES
            if race_id not in missing or race_id != "2024-02"
        ]
    )


def test_registered_sample_is_fixed_calendar_first_and_immutable() -> None:
    assert REGISTERED_RACE_IDS == PHASE_08_RACES
    assert isinstance(REGISTERED_RACE_IDS, tuple)


def test_preflight_requires_every_registered_race_complete() -> None:
    complete = {race_id: True for race_id in PHASE_08_RACES}
    assert preflight_races(complete) == ()
    complete.pop("2024-02")
    complete["2025-02"] = False
    assert preflight_races(complete) == ("2024-02", "2025-02")


def test_incomplete_sample_stops_before_prediction_or_results_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asof, "catalog", lambda _db: _catalog(missing=("2024-02",)))
    monkeypatch.setattr(
        walk_forward,
        "_predict_from_accessor",
        lambda *_args, **_kwargs: pytest.fail("prediction ran before complete-sample preflight"),
    )
    with pytest.raises(ValueError, match="2024-02"):
        predict_at_cutoff(Path("cache.duckdb"), "2023-01", "ALO", 0)


def test_reference_cli_returns_prediction_row_after_full_preflight(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from f1si.cli import _ReplayCutoff

    events: list[str] = []
    monkeypatch.setattr(asof, "catalog", lambda _db: _catalog())

    class Accessor:
        def __init__(self, _db: Path) -> None:
            events.append("accessor")

        def snapshot(self, _at: object) -> object:
            events.append("snapshot")
            return SimpleNamespace(
                race=SimpleNamespace(scheduled_laps=1),
                laps=pd.DataFrame({"lap_number": [1]}),
                entries=pd.DataFrame({"driver_code": ["ALO"]}),
            )

    monkeypatch.setattr(walk_forward, "_new_accessor", Accessor)
    monkeypatch.setattr("f1si.paths.db_path", lambda _data_dir: Path("cache.duckdb"))

    def replay(accessor: object, *_args: object, **_kwargs: object) -> object:
        assert isinstance(accessor, Accessor)
        events.append("prediction")
        analysis = cast(
            StrategyAnalysis,
            SimpleNamespace(best=SimpleNamespace(action="stay out"), reason="cutoff-local"),
        )
        return _ReplayCutoff(0, analysis)

    monkeypatch.setattr("f1si.cli._replay_at_cutoff", replay)
    result = main(
        ["--data-dir", ".", "backtest", "--race", "2023-01", "--driver", "ALO", "--lap", "0"]
    )
    assert result == 0
    assert events == ["accessor", "snapshot", "prediction"]
    output = capsys.readouterr().out
    assert "2023-01 ALO lap 0: stay out" in output
    assert "cutoff-local" in output
    assert "score" not in events
    assert "results" not in events


def test_predict_at_cutoff_passes_the_selected_pace_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asof, "catalog", lambda _db: _catalog())
    captured: list[str] = []

    class Accessor:
        def __init__(self, _db: Path) -> None:
            pass

        def snapshot(self, _at: object) -> object:
            return SimpleNamespace(
                race=SimpleNamespace(scheduled_laps=10),
                laps=pd.DataFrame({"lap_number": [1]}),
                entries=pd.DataFrame({"driver_code": ["ALO"]}),
            )

    monkeypatch.setattr(walk_forward, "_new_accessor", Accessor)

    def predict(*_args: object, **options: object) -> PredictionRow:
        captured.append(str(options["pace_model"]))
        return PredictionRow("2025-01", "ALO", 5, None, "stub")

    monkeypatch.setattr(walk_forward, "_predict_from_accessor", predict)
    row = predict_at_cutoff(Path("cache.duckdb"), "2025-01", "ALO", 5, pace_model="bayesian")
    assert row.unavailable_reason == "stub"
    assert captured == ["bayesian"]


def test_registered_backtest_prediction_uses_bayesian_selected_context(
    long_synthetic_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from f1si import cli
    from f1si.data.asof import AsOfAccessor
    from f1si.pace.linear import fit_linear_pace

    accessor = AsOfAccessor(long_synthetic_db)
    lap = 35
    snapshot = accessor.snapshot(asof.AsOf(LONG_RACE_ID, lap))
    driver = str(snapshot.entries.iloc[0]["driver_code"])
    fit_calls: list[tuple[str, int]] = []

    def substitute(_panel: object, *, seed: int) -> object:
        fit_calls.append((LONG_RACE_ID, seed))
        return fit_linear_pace(snapshot)

    monkeypatch.setattr(cli, "_fit_bayesian_panel", substitute)
    row = walk_forward._predict_from_accessor(
        accessor,
        LONG_RACE_ID,
        driver,
        lap,
        n_simulations=1,
        risk=0.5,
        seed=123,
        laps_total=57,
        pace_model="bayesian",
    )
    assert row.analysis is not None
    assert fit_calls == [(LONG_RACE_ID, walk_forward._model_seed(LONG_RACE_ID, lap, 123))]


def test_prediction_runner_has_no_results_or_scoring_imports() -> None:
    from pathlib import Path

    source = Path("src/f1si/backtest/walk_forward.py").read_text(encoding="utf-8")
    assert "f1si.data.results" not in source
    assert "ResultsAccessor" not in source
    assert "score(" not in source


def test_full_runner_freezes_every_driver_and_cutoff_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from f1si import cli

    calls: list[tuple[str, int, str]] = []
    monkeypatch.setattr(asof, "catalog", lambda _db: _catalog())

    class Accessor:
        def __init__(self, _db: Path) -> None:
            pass

        def snapshot(self, _at: object) -> object:
            return SimpleNamespace(
                race=SimpleNamespace(scheduled_laps=3),
                entries=pd.DataFrame({"driver_code": ["AAA", "BBB"]}),
            )

    monkeypatch.setattr(walk_forward, "_new_accessor", Accessor)
    monkeypatch.setattr(
        cli,
        "_prepare_replay_context",
        lambda _accessor, _race_id, _laps_total, _lap, *, snapshot, **_options: SimpleNamespace(
            snapshot=snapshot
        ),
        raising=False,
    )

    def prediction(
        _accessor: object,
        race_id: str,
        driver: str,
        lap: int,
        **_options: object,
    ) -> PredictionRow:
        calls.append((race_id, lap, driver))
        return PredictionRow(race_id, driver, lap, None, "test row")

    monkeypatch.setattr(walk_forward, "_predict_from_accessor", prediction)
    trace = run_walk_forward(Path("cache.duckdb"))
    expected = [
        (race_id, lap, driver)
        for race_id in PHASE_08_RACES
        for lap in range(3)
        for driver in ("AAA", "BBB")
    ]
    assert calls == expected
    assert isinstance(trace.predictions, tuple)
    assert len(trace.predictions) == len(expected)


def test_full_runner_fails_before_prediction_when_schedule_distance_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asof, "catalog", lambda _db: _catalog())
    requested: list[asof.AsOf] = []

    class Accessor:
        def __init__(self, _db: Path) -> None:
            pass

        def snapshot(self, at: asof.AsOf) -> object:
            requested.append(at)
            return SimpleNamespace(
                race=SimpleNamespace(scheduled_laps=None),
                laps=pd.DataFrame(columns=["lap_number"]),
                entries=pd.DataFrame({"driver_code": ["AAA"]}),
            )

    monkeypatch.setattr(walk_forward, "_new_accessor", Accessor)
    monkeypatch.setattr(
        walk_forward,
        "_predict_from_accessor",
        lambda *_args, **_kwargs: pytest.fail("prediction ran without schedule metadata"),
    )
    with pytest.raises(ValueError, match="Scheduled race distance is unavailable for 2023-01"):
        run_walk_forward(Path("cache.duckdb"))
    assert requested == [asof.AsOf("2023-01", 0)]


def test_full_runner_prepares_shared_replay_context_once_per_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from f1si import cli

    monkeypatch.setattr(asof, "catalog", lambda _db: _catalog())

    class Accessor:
        def __init__(self, _db: Path) -> None:
            pass

        def snapshot(self, _at: object) -> object:
            return SimpleNamespace(
                race=SimpleNamespace(scheduled_laps=3),
                entries=pd.DataFrame({"driver_code": ["AAA", "BBB"]}),
            )

    monkeypatch.setattr(walk_forward, "_new_accessor", Accessor)
    prepared: list[tuple[str, int, object]] = []
    prepared_models: list[object] = []
    received: list[tuple[str, int, str, object]] = []

    def prepare(
        _accessor: object,
        race_id: str,
        _laps_total: int,
        lap: int,
        **_options: object,
    ) -> object:
        context = object()
        prepared.append((race_id, lap, context))
        prepared_models.append(_options.get("pace_model"))
        return context

    monkeypatch.setattr(cli, "_prepare_replay_context", prepare, raising=False)

    def prediction(
        _accessor: object,
        race_id: str,
        driver: str,
        lap: int,
        **options: object,
    ) -> PredictionRow:
        received.append((race_id, lap, driver, options.get("prepared_context")))
        return PredictionRow(race_id, driver, lap, None, "test row")

    monkeypatch.setattr(walk_forward, "_predict_from_accessor", prediction)
    run_walk_forward(Path("cache.duckdb"), pace_model="bayesian")

    expected_cutoffs = [(race_id, lap) for race_id in PHASE_08_RACES for lap in range(3)]
    assert [(race_id, lap) for race_id, lap, _ in prepared] == expected_cutoffs
    assert prepared_models == ["bayesian"] * len(expected_cutoffs)
    assert len(received) == 2 * len(expected_cutoffs)
    contexts = {(race_id, lap): context for race_id, lap, context in prepared}
    assert all(context is contexts[(race_id, lap)] for race_id, lap, _, context in received)


def test_prepared_replay_matches_standalone_prediction_exactly(long_synthetic_db: Path) -> None:
    from f1si import cli

    accessor = walk_forward._new_accessor(long_synthetic_db)
    race_id = "2023-01"
    lap = 12
    laps_total = 57
    snapshot = accessor.snapshot(asof.AsOf(race_id, lap))
    code = str(snapshot.entries.iloc[0]["driver_code"])
    context = cli._prepare_replay_context(accessor, race_id, laps_total, lap, snapshot=snapshot)

    standalone = cli._replay_at_cutoff(
        accessor, race_id, laps_total, code, lap, n_simulations=3, risk=0.5, seed=12345
    )
    shared = cli._replay_at_cutoff(
        accessor,
        race_id,
        laps_total,
        code,
        lap,
        n_simulations=3,
        risk=0.5,
        seed=12345,
        prepared_context=context,
    )

    assert shared == standalone


def test_walk_forward_exposes_bounded_worker_control() -> None:
    from inspect import signature

    assert "workers" in signature(run_walk_forward).parameters


def test_serial_and_parallel_full_trace_match_exactly(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from f1si import paths
    from f1si.data.loader import load_races
    from f1si.data.sources.synthetic_source import SyntheticSource
    from f1si.rng import make_rng
    from f1si.synthetic import SyntheticRaceSpec

    specs = tuple(
        SyntheticRaceSpec(
            season, round_number, f"Race {season}-{round_number}", n_drivers=2, n_laps=4
        )
        for season, rounds in ((2023, 7), (2024, 7), (2025, 6))
        for round_number in range(1, rounds + 1)
    )
    db_path = paths.db_path(tmp_path)
    load_races(
        SyntheticSource(specs, rng=make_rng(42)),
        db_path,
        (2023, 2024, 2025),
        now=datetime(2026, 10, 22, tzinfo=UTC),
        echo=lambda _line: None,
    )

    serial = run_walk_forward(db_path, n_simulations=1, risk=0.5, seed=159, workers=1)
    parallel = run_walk_forward(db_path, n_simulations=1, risk=0.5, seed=159, workers=2)

    drivers = sorted({row.driver for row in serial.predictions if row.race_id == PHASE_08_RACES[0]})
    expected = [
        (race_id, lap, driver)
        for race_id in PHASE_08_RACES
        for lap in range(4)
        for driver in drivers
    ]
    actual = [(row.race_id, row.cutoff_lap, row.driver) for row in parallel.predictions]
    assert actual == expected
    assert len(expected) == 160
    assert parallel == serial


def test_requesting_2026_race_is_rejected_before_prediction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        asof,
        "catalog",
        lambda _db: pytest.fail("out-of-sample request reached cache preflight"),
    )
    with pytest.raises(ValueError, match=r"2026|registered"):
        predict_at_cutoff(Path("cache.duckdb"), "2026-01", "ALO", 0)
