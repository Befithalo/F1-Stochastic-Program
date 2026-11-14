"""Contracts for the Phase 6 fixed-sample, prediction-only walk-forward runner."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
from typing import Any, cast

import pytest
from f1si.backtest.walk_forward import REGISTERED_RACE_IDS, preflight_races, run_walk_forward

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


def test_registered_sample_is_fixed_calendar_first_and_immutable() -> None:
    assert REGISTERED_RACE_IDS == EXPECTED_RACES
    assert isinstance(REGISTERED_RACE_IDS, tuple)


def test_preflight_requires_every_registered_race_complete() -> None:
    complete = {race_id: True for race_id in EXPECTED_RACES}
    assert preflight_races(complete) == ()
    complete.pop("2024-02")
    complete["2025-02"] = False
    assert preflight_races(complete) == ("2024-02", "2025-02")


def test_incomplete_sample_stops_before_any_prediction_or_results_access() -> None:
    events: list[str] = []

    class Accessor:
        def catalog(self) -> dict[str, bool]:
            events.append("catalog")
            return {race_id: race_id != "2024-02" for race_id in EXPECTED_RACES}

        def snapshot(self, _at: object) -> None:
            events.append("snapshot")
            raise AssertionError("prediction started before all-race preflight")

        def history(self, _at: object) -> None:
            events.append("history")
            raise AssertionError("prediction started before all-race preflight")

    with pytest.raises((ValueError, RuntimeError), match="2024-02"):
        run_walk_forward(Accessor())
    assert events == ["catalog"]
    assert "results" not in events
    assert "score" not in events


def test_prediction_freeze_precedes_results_access_and_scoring() -> None:
    events: list[tuple[str, int]] = []

    def freeze(rows: list[Any]) -> None:
        events.append(("freeze", len(rows)))

    def results(_race_id: str) -> None:
        events.append(("results", 0))

    def score(_rows: list[Any]) -> None:
        events.append(("score", 0))

    trace = run_walk_forward(
        database=None,
        freeze_hook=freeze,
        results_hook=results,
        score_hook=score,
        races=EXPECTED_RACES,
    )
    freeze_index = next(i for i, event in enumerate(events) if event[0] == "freeze")
    results_index = next(i for i, event in enumerate(events) if event[0] == "results")
    score_index = next(i for i, event in enumerate(events) if event[0] == "score")
    assert freeze_index < results_index
    assert freeze_index < score_index
    assert events[freeze_index][1] == len(trace.predictions)


def test_cutoffs_are_chronological_and_frozen_rows_are_immutable() -> None:
    trace = run_walk_forward(database=None, races=("2023-01",), driver="ALO")
    cutoffs = [row.cutoff_lap for row in trace.predictions]
    assert cutoffs == sorted(cutoffs)
    assert all(row.race_id == "2023-01" for row in trace.predictions)
    first = trace.predictions[0]
    if is_dataclass(first):
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            cast(Any, first).cutoff_lap = -1


def test_requesting_regulation_reset_race_is_rejected() -> None:
    with pytest.raises((ValueError, RuntimeError), match=r"2026|out.of.sample|locked"):
        run_walk_forward(database=None, races=("2026-01",))
