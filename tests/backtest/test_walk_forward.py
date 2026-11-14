"""Contracts for the Phase 6 fixed-sample, prediction-only walk-forward runner."""

from __future__ import annotations

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

EXPECTED_RACES = (
    "2023-01",
    "2023-02",
    "2023-03",
    "2023-04",
    "2024-01",
    "2024-02",
    "2024-03",
    "2025-01",
    "2025-02",
    "2025-03",
)


def _catalog(*, missing: tuple[str, ...] = ()) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "race_id": race_id,
                "load_status": "partial" if race_id in missing else "complete",
                "out_of_sample": False,
            }
            for race_id in EXPECTED_RACES
            if race_id not in missing or race_id != "2024-02"
        ]
    )


def test_registered_sample_is_fixed_calendar_first_and_immutable() -> None:
    assert REGISTERED_RACE_IDS == EXPECTED_RACES
    assert isinstance(REGISTERED_RACE_IDS, tuple)


def test_preflight_requires_every_registered_race_complete() -> None:
    complete = {race_id: True for race_id in EXPECTED_RACES}
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
        lambda _accessor, _race_id, _laps_total, _lap, *, snapshot: SimpleNamespace(
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
        for race_id in EXPECTED_RACES
        for lap in range(3)
        for driver in ("AAA", "BBB")
    ]
    assert calls == expected
    assert isinstance(trace.predictions, tuple)
    assert len(trace.predictions) == len(expected)


def test_full_runner_uses_completed_lap_horizon_when_schedule_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from f1si import cli

    monkeypatch.setattr(asof, "catalog", lambda _db: _catalog())

    class Accessor:
        def __init__(self, _db: Path) -> None:
            pass

        def snapshot(self, at: asof.AsOf) -> object:
            if at.lap == asof.RACE_END:
                return SimpleNamespace(
                    race=SimpleNamespace(scheduled_laps=None),
                    laps=pd.DataFrame({"lap_number": [1, 2, 3]}),
                    entries=pd.DataFrame({"driver_code": ["AAA"]}),
                )
            return SimpleNamespace(
                race=SimpleNamespace(scheduled_laps=None),
                laps=pd.DataFrame(columns=["lap_number"]),
                entries=pd.DataFrame({"driver_code": ["AAA"]}),
            )

    monkeypatch.setattr(walk_forward, "_new_accessor", Accessor)
    monkeypatch.setattr(
        cli,
        "_prepare_replay_context",
        lambda _accessor, _race_id, _laps_total, _lap, *, snapshot: SimpleNamespace(
            snapshot=snapshot
        ),
        raising=False,
    )
    calls: list[tuple[str, int]] = []

    def prediction(
        _accessor: object,
        race_id: str,
        driver: str,
        lap: int,
        **_options: object,
    ) -> PredictionRow:
        calls.append((race_id, lap))
        return PredictionRow(race_id, driver, lap, None, "test row")

    monkeypatch.setattr(walk_forward, "_predict_from_accessor", prediction)
    trace = run_walk_forward(Path("cache.duckdb"))
    assert calls == [(race_id, lap) for race_id in EXPECTED_RACES for lap in range(3)]
    assert len(trace.predictions) == len(EXPECTED_RACES) * 3


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
    run_walk_forward(Path("cache.duckdb"))

    expected_cutoffs = [(race_id, lap) for race_id in EXPECTED_RACES for lap in range(3)]
    assert [(race_id, lap) for race_id, lap, _ in prepared] == expected_cutoffs
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
        for season, rounds in ((2023, 4), (2024, 3), (2025, 3))
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

    drivers = sorted({row.driver for row in serial.predictions if row.race_id == EXPECTED_RACES[0]})
    expected = [
        (race_id, lap, driver)
        for race_id in EXPECTED_RACES
        for lap in range(4)
        for driver in drivers
    ]
    actual = [(row.race_id, row.cutoff_lap, row.driver) for row in parallel.predictions]
    assert actual == expected
    assert len(expected) == 80
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
