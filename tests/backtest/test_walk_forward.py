"""Contracts for the Phase 6 fixed-sample, prediction-only walk-forward runner."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from f1si.backtest.walk_forward import (
    REGISTERED_RACE_IDS,
    PredictionRow,
    predict_at_cutoff,
    preflight_races,
    run_walk_forward,
)
from f1si.cli import main

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
    from f1si.backtest import walk_forward

    monkeypatch.setattr(walk_forward.asof, "catalog", lambda _db: _catalog(missing=("2024-02",)))
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
    from f1si.backtest import walk_forward
    from f1si.cli import _ReplayCutoff

    events: list[str] = []
    monkeypatch.setattr(walk_forward.asof, "catalog", lambda _db: _catalog())

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
        return _ReplayCutoff(
            0,
            SimpleNamespace(best=SimpleNamespace(action="stay out"), reason="cutoff-local"),
        )

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
    from f1si.backtest import walk_forward

    calls: list[tuple[str, int, str]] = []
    monkeypatch.setattr(walk_forward.asof, "catalog", lambda _db: _catalog())

    class Accessor:
        def __init__(self, _db: Path) -> None:
            pass

        def snapshot(self, _at: object) -> object:
            return SimpleNamespace(
                race=SimpleNamespace(scheduled_laps=3),
                entries=pd.DataFrame({"driver_code": ["AAA", "BBB"]}),
            )

    monkeypatch.setattr(walk_forward, "_new_accessor", Accessor)

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


def test_requesting_2026_race_is_rejected_before_prediction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from f1si.backtest import walk_forward

    monkeypatch.setattr(
        walk_forward.asof,
        "catalog",
        lambda _db: pytest.fail("out-of-sample request reached cache preflight"),
    )
    with pytest.raises(ValueError, match=r"2026|registered"):
        predict_at_cutoff(Path("cache.duckdb"), "2026-01", "ALO", 0)
