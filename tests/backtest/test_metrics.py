"""Numeric and ordering contracts for Phase 6 scoring and metric aggregation."""

from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd

from f1si.backtest.metrics import (
    brier_scores,
    finish_interval,
    grid_position_probability,
    race_cluster_interval,
    summarize_by_race,
)


def test_frozen_prediction_scoring_api_is_available() -> None:
    module = importlib.util.find_spec("f1si.backtest.scoring")
    assert module is not None, "the isolated scorer must consume frozen predictions"


def test_brier_outcomes_treat_unclassified_starters_as_binary_failures() -> None:
    rows = pd.DataFrame(
        {
            "predicted_podium": [0.8, 0.2, 0.4],
            "predicted_top10": [0.9, 0.7, 0.3],
            "finish_position": [2, 12, np.nan],
        }
    )
    scored = brier_scores(rows)
    assert scored["podium"] == np.mean([(0.8 - 1) ** 2, 0.2**2, 0.4**2])
    assert scored["top10"] == np.mean([(0.9 - 1) ** 2, 0.7**2, 0.3**2])


def test_grid_prior_is_neutral_then_shrinks_with_five_pseudo_observations() -> None:
    history = pd.DataFrame(
        {
            "grid_position": [1, 1, 1, 2],
            "finish_position": [1, 8, 15, 2],
        }
    )
    neutral = grid_position_probability(history.iloc[:0], grid_position=1, field_size=20)
    assert neutral["podium"] == 3 / 20
    assert neutral["top10"] == 10 / 20
    estimate = grid_position_probability(history, grid_position=1, field_size=20)
    assert estimate["podium"] == (1 + 5 * (3 / 20)) / 8
    assert estimate["top10"] == (2 + 5 * (10 / 20)) / 8


def test_finish_interval_uses_inclusive_discrete_inverted_cdf_endpoints() -> None:
    assert finish_interval(np.arange(1, 21), coverage=0.9) == tuple(
        np.quantile(np.arange(1, 21), [0.05, 0.95], method="inverted_cdf").astype(int)
    )


def test_interval_coverage_excludes_unclassified_finishers_and_reports_denominator() -> None:
    rows = pd.DataFrame(
        {
            "finish_samples": [[1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4]],
            "finish_position": [2, 8, np.nan],
        }
    )
    result = finish_interval(rows, coverage=0.9, observed=True)
    assert result["classified_finishers"] == 2
    assert result["covered"] == 1


def test_observation_masks_are_shared_between_model_and_baseline() -> None:
    rows = pd.DataFrame(
        {
            "predicted_podium": [0.4, np.nan, 0.1],
            "baseline_podium": [0.3, 0.2, 0.1],
            "predicted_top10": [0.5, 0.5, 0.1],
            "baseline_top10": [0.6, 0.6, 0.1],
            "finish_position": [2, 3, np.nan],
        }
    )
    result = brier_scores(rows, paired=True)
    assert result["observation_count"] == 2
    assert result["model_mask"].equals(result["baseline_mask"])


def test_race_aggregation_weights_races_equally_not_rows() -> None:
    rows = pd.DataFrame({"race_id": ["a", "a", "a", "b"], "loss": [0, 0, 0, 1]})
    result = summarize_by_race(rows, value="loss")
    assert result["mean"] == 0.5
    assert result["race_count"] == 2


def test_cluster_bootstrap_is_paired_race_level_and_seed_reproducible() -> None:
    rows = pd.DataFrame({"race_id": ["a", "a", "b", "c"], "value": [1, 3, 5, 7]})
    first = race_cluster_interval(rows, value="value", rng=np.random.default_rng(31))
    second = race_cluster_interval(rows, value="value", rng=np.random.default_rng(31))
    assert first == second
    assert first["cluster_count"] == 3
