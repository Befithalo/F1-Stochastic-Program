"""Contracts for one-to-one, strictly pre-event strategy comparison."""

from __future__ import annotations

import numpy as np
import pandas as pd
from f1si.backtest.strategy import match_team_stops, summarize_team_calls


def test_each_stop_uses_latest_recommendation_strictly_before_event() -> None:
    recommendations = pd.DataFrame(
        {
            "race_id": ["2023-01"] * 4,
            "driver": ["ALO"] * 4,
            "cutoff_lap": [4, 7, 9, 10],
            "top_action": ["stay out", "pit", "pit", "stay out"],
            "planned_stop_lap": [None, 8, 10, None],
        }
    )
    stops = pd.DataFrame({"race_id": ["2023-01"], "driver": ["ALO"], "in_lap": [10]})
    matched = match_team_stops(recommendations, stops)
    assert len(matched) == 1
    assert matched.iloc[0]["cutoff_lap"] == 9
    assert matched.iloc[0]["in_lap"] == 10


def test_actual_event_contributes_once_despite_many_prior_recommendations() -> None:
    recommendations = pd.DataFrame(
        {
            "race_id": ["r"] * 5,
            "driver": ["ALO"] * 5,
            "cutoff_lap": range(5),
            "top_action": ["pit"] * 5,
            "planned_stop_lap": [5] * 5,
        }
    )
    stops = pd.DataFrame({"race_id": ["r"], "driver": ["ALO"], "in_lap": [5]})
    assert len(match_team_stops(recommendations, stops)) == 1


def test_cutoff_at_or_after_inlap_never_matches() -> None:
    recommendations = pd.DataFrame(
        {
            "race_id": ["r"] * 2,
            "driver": ["ALO"] * 2,
            "cutoff_lap": [5, 6],
            "top_action": ["pit"] * 2,
            "planned_stop_lap": [6, 7],
        }
    )
    stops = pd.DataFrame({"race_id": ["r"], "driver": ["ALO"], "in_lap": [6]})
    assert match_team_stops(recommendations, stops).iloc[0]["cutoff_lap"] == 5


def test_per_race_summary_and_seeded_intervals_resample_races() -> None:
    rows = pd.DataFrame(
        {
            "race_id": ["a", "a", "b", "c"],
            "action_agrees": [True, False, True, False],
            "timing_error_laps": [0, 2, 1, 3],
        }
    )
    first = summarize_team_calls(rows, rng=np.random.default_rng(9))
    second = summarize_team_calls(rows, rng=np.random.default_rng(9))
    assert first == second
    assert first["race_count"] == 3
    assert first["confidence_level"] == 0.95
    assert first["resampling_unit"] == "race"


def test_report_description_is_observational_not_superiority_claim() -> None:
    rows = pd.DataFrame(
        {
            "race_id": ["a"],
            "action_agrees": [True],
            "timing_error_laps": [0],
        }
    )
    text = summarize_team_calls(rows, rng=np.random.default_rng(1))["description"].lower()
    assert "observed team" in text
    assert "beats" not in text
    assert "better than" not in text
