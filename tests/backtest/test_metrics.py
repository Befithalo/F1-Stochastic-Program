"""Numeric and ordering contracts for Phase 6 scoring and metric aggregation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

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


def test_grid_prior_bounds_podium_probability_for_tiny_fields() -> None:
    neutral = grid_position_probability(pd.DataFrame(), grid_position=None, field_size=1)

    assert neutral == {"podium": 1.0, "top10": 1.0}


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
    assert isinstance(result, dict)
    assert result["classified_finishers"] == 2
    assert result["covered"] == 1


def test_dataframe_finish_interval_requires_explicit_observed_flag() -> None:
    rows = pd.DataFrame({"finish_samples": [[1, 2, 3]], "finish_position": [2]})
    with pytest.raises(ValueError, match="DataFrame inputs require observed=True"):
        finish_interval(rows)


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


@pytest.mark.parametrize(
    ("column", "invalid_probability"),
    [
        ("predicted_podium", np.inf),
        ("predicted_top10", -np.inf),
        ("predicted_podium", 1.01),
        ("predicted_top10", -0.01),
        ("baseline_podium", np.inf),
        ("baseline_top10", 1.01),
    ],
)
def test_brier_scores_reject_invalid_probabilities(column: str, invalid_probability: float) -> None:
    rows = pd.DataFrame(
        {
            "predicted_podium": [0.2],
            "predicted_top10": [0.7],
            "baseline_podium": [0.3],
            "baseline_top10": [0.8],
            "finish_position": [4],
        }
    )
    rows.loc[0, column] = invalid_probability

    with pytest.raises(ValueError, match="Brier probability column"):
        brier_scores(rows, paired=True)


def test_diagnostics_extension_rejects_incomplete_phase_six_probability_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    from f1si.backtest import scoring
    from f1si.backtest.walk_forward import REGISTERED_RACE_IDS

    report: dict[str, Any] = {
        "schema_version": 1,
        "race_ids": list(REGISTERED_RACE_IDS),
        "metadata": {
            "base_seed": 3,
            "n_simulations_per_prediction": 64,
            "risk_aversion": 0.5,
        },
        "metrics": {},
    }
    before = json.loads(json.dumps(report))
    monkeypatch.setattr(
        scoring,
        "score_team_strategy_sample",
        lambda *_args, **_kwargs: pytest.fail("diagnostics ran on an incomplete report"),
    )

    with pytest.raises(ValueError, match="required probability metrics are missing"):
        scoring.extend_existing_report(
            Path("cache.duckdb"), report, n_simulations=64, risk=0.5, seed=3
        )

    assert report == before


@pytest.mark.parametrize(
    ("path", "invalid_value"),
    [
        (("metrics", "podium_brier", "model", "mean"), None),
        (("metrics", "top10_brier", "baseline", "per_race", "2023-01"), "invalid"),
        (("metrics", "finish_interval_90", "coverage", "per_race", "2023-01"), 1.1),
        (("metrics", "finish_interval_90", "covered"), 101),
        (("metrics", "podium_brier", "model_minus_baseline_95", "low"), 0.5),
    ],
)
def test_diagnostics_extension_rejects_malformed_probability_values_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str, ...],
    invalid_value: object,
) -> None:
    import json

    from f1si.backtest import scoring
    from f1si.backtest.walk_forward import REGISTERED_RACE_IDS

    def summary(value: float) -> dict[str, Any]:
        return {
            "mean": value,
            "per_race": {race_id: value for race_id in REGISTERED_RACE_IDS},
            "race_count": len(REGISTERED_RACE_IDS),
        }

    def paired(mean: float) -> dict[str, Any]:
        return {"mean": mean, "low": -0.2, "high": 0.0, "cluster_count": len(REGISTERED_RACE_IDS)}

    report: dict[str, Any] = {
        "schema_version": 1,
        "race_ids": list(REGISTERED_RACE_IDS),
        "metadata": {"base_seed": 3, "n_simulations_per_prediction": 64, "risk_aversion": 0.5},
        "metrics": {
            "podium_brier": {
                "model": summary(0.2),
                "baseline": summary(0.3),
                "model_minus_baseline_95": paired(-0.1),
            },
            "top10_brier": {
                "model": summary(0.4),
                "baseline": summary(0.5),
                "model_minus_baseline_95": paired(-0.1),
            },
            "brier_observation_count": 100,
            "finish_interval_90": {
                "covered": 40,
                "classified_finishers": 100,
                "coverage": summary(0.4),
                "race_cluster_95": {
                    "mean": 0.4,
                    "low": 0.3,
                    "high": 0.5,
                    "cluster_count": len(REGISTERED_RACE_IDS),
                },
            },
        },
    }
    target: Any = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = invalid_value
    before = json.loads(json.dumps(report))
    monkeypatch.setattr(scoring, "score_team_strategy_sample", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(scoring, "wear_proxy_diagnostic", lambda *_args, **_kwargs: {})

    with pytest.raises(ValueError, match="does not match diagnostic inputs"):
        scoring.extend_existing_report(
            Path("cache.duckdb"), report, n_simulations=64, risk=0.5, seed=3
        )

    assert report == before


@pytest.mark.parametrize(
    ("path", "invalid_value", "message"),
    [
        (
            ("metrics", "podium_brier", "model", "mean"),
            0.21,
            "podium_brier.model.mean is inconsistent",
        ),
        (
            ("metrics", "podium_brier", "model_minus_baseline_95", "mean"),
            -0.2,
            "podium_brier paired mean is inconsistent",
        ),
        (
            ("metrics", "top10_brier", "model_minus_baseline_95", "low"),
            -0.05,
            "top10_brier paired mean is outside",
        ),
        (
            ("metrics", "finish_interval_90", "coverage", "mean"),
            0.41,
            "coverage mean is inconsistent",
        ),
        (
            ("metrics", "finish_interval_90", "race_cluster_95", "high"),
            0.39,
            "uncertainty mean is inconsistent",
        ),
    ],
)
def test_diagnostics_extension_rejects_inconsistent_probability_summaries_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str, ...],
    invalid_value: object,
    message: str,
) -> None:
    import json

    from f1si.backtest import scoring
    from f1si.backtest.walk_forward import REGISTERED_RACE_IDS

    def summary(value: float) -> dict[str, Any]:
        return {
            "mean": value,
            "per_race": {race_id: value for race_id in REGISTERED_RACE_IDS},
            "race_count": len(REGISTERED_RACE_IDS),
        }

    report: dict[str, Any] = {
        "schema_version": 1,
        "race_ids": list(REGISTERED_RACE_IDS),
        "metadata": {
            "base_seed": 3,
            "n_simulations_per_prediction": 64,
            "risk_aversion": 0.5,
        },
        "metrics": {
            "podium_brier": {
                "model": summary(0.2),
                "baseline": summary(0.3),
                "model_minus_baseline_95": {
                    "mean": -0.1,
                    "low": -0.2,
                    "high": 0.0,
                    "cluster_count": len(REGISTERED_RACE_IDS),
                },
            },
            "top10_brier": {
                "model": summary(0.4),
                "baseline": summary(0.5),
                "model_minus_baseline_95": {
                    "mean": -0.1,
                    "low": -0.2,
                    "high": 0.0,
                    "cluster_count": len(REGISTERED_RACE_IDS),
                },
            },
            "brier_observation_count": 100,
            "finish_interval_90": {
                "covered": 40,
                "classified_finishers": 100,
                "coverage": summary(0.4),
                "race_cluster_95": {
                    "mean": 0.4,
                    "low": 0.3,
                    "high": 0.5,
                    "cluster_count": len(REGISTERED_RACE_IDS),
                },
            },
        },
    }
    target: Any = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = invalid_value
    before = json.loads(json.dumps(report))
    monkeypatch.setattr(
        scoring,
        "score_team_strategy_sample",
        lambda *_args, **_kwargs: pytest.fail("diagnostics ran on an inconsistent report"),
    )

    with pytest.raises(ValueError, match=message):
        scoring.extend_existing_report(
            Path("cache.duckdb"), report, n_simulations=64, risk=0.5, seed=3
        )

    assert report == before


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


def test_preflight_requires_all_ten_races_before_scoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from f1si.backtest import scoring

    events: list[str] = []
    monkeypatch.setattr(
        "f1si.backtest.scoring.asof.catalog",
        lambda _db: pd.DataFrame(
            {
                "race_id": ["2023-01"],
                "load_status": ["complete"],
                "out_of_sample": [False],
            }
        ),
    )
    monkeypatch.setattr(
        scoring,
        "run_walk_forward",
        lambda *_args, **_kwargs: events.append("prediction"),
    )
    monkeypatch.setattr(
        scoring,
        "_new_results_accessor",
        lambda *_args, **_kwargs: pytest.fail("results opened before all-ten preflight"),
    )

    with pytest.raises(ValueError, match="2023-02"):
        scoring.score_registered_sample(Path("cache.duckdb"))
    assert events == []


def _scoring_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    missing: tuple[tuple[str, int, str], ...] = (),
    duplicate: bool = False,
    events: list[str] | None = None,
) -> None:
    from f1si.backtest import scoring
    from f1si.backtest.walk_forward import (
        REGISTERED_RACE_IDS,
        PredictionRow,
        WalkForwardTrace,
    )
    from f1si.interfaces import Plan
    from f1si.strategy.longstaff import RankedOption, StrategyAnalysis

    trace_events = events if events is not None else []
    race_ids = REGISTERED_RACE_IDS
    predictions = tuple(
        PredictionRow(
            race_id,
            "AAA",
            0,
            StrategyAnalysis(
                driver="AAA",
                lap=0,
                options=(
                    RankedOption(
                        action="stay out",
                        plan=Plan((), (), 0.0),
                        mean_finish=4.0,
                        spread=1.0,
                        cvar10=8.0,
                        score=6.0,
                        podium_probability=0.2,
                        top10_probability=0.7,
                        finish_p05=2,
                        finish_p95=8,
                    ),
                ),
                reason="test prediction",
            ),
        )
        for race_id in race_ids
        if (race_id, 0, "AAA") not in missing
    )
    if duplicate:
        predictions += (predictions[0],)
    trace = WalkForwardTrace(predictions)
    from f1si.backtest.metrics import brier_scores as real_brier_scores

    class AsOf:
        def __init__(self, _db: Path) -> None:
            pass

        def snapshot(self, _at: object) -> object:
            return SimpleNamespace(
                race=SimpleNamespace(scheduled_laps=1),
                entries=pd.DataFrame(
                    {
                        "driver_number": [1],
                        "driver_code": ["AAA"],
                        "grid_position": [1],
                    }
                ),
                pit_events=pd.DataFrame(columns=["driver_number", "in_lap"]),
            )

        def history(self, _at: object) -> object:
            return SimpleNamespace(
                entries=pd.DataFrame(columns=["race_id", "driver_number", "grid_position"]),
                results=pd.DataFrame(columns=["race_id", "driver_number", "final_position"]),
            )

    class Results:
        def __init__(self, _db: Path) -> None:
            trace_events.append("results_open")
            expected = {(row.race_id, row.cutoff_lap, row.driver) for row in trace.predictions}
            assert len(expected) == len(race_ids), (
                "full prediction set must freeze before results open"
            )

        def final_classification(self, race_id: str) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "race_id": [race_id],
                    "driver_code": ["AAA"],
                    "final_position": [3],
                }
            )

    def brier(rows: pd.DataFrame, *, paired: bool = False) -> dict[str, Any]:
        trace_events.append("score")
        return real_brier_scores(rows, paired=paired)

    monkeypatch.setattr("f1si.backtest.scoring.asof.AsOfAccessor", AsOf)
    monkeypatch.setattr(scoring, "_new_results_accessor", Results)
    monkeypatch.setattr(scoring, "run_walk_forward", lambda *_args, **_kwargs: trace)
    monkeypatch.setattr(scoring, "wear_proxy_diagnostic", lambda *_args: {})
    monkeypatch.setattr("f1si.backtest.scoring.brier_scores", brier)
    monkeypatch.setattr(
        "f1si.backtest.scoring.asof.catalog",
        lambda _db: pd.DataFrame(
            {
                "race_id": list(race_ids),
                "load_status": ["complete"] * len(race_ids),
                "out_of_sample": [False] * len(race_ids),
            }
        ),
    )
    if events is not None:
        trace_events.append("predictions_ready")


def test_predictions_freeze_before_first_results_open_and_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from f1si.backtest import scoring
    from f1si.backtest.walk_forward import REGISTERED_RACE_IDS

    events: list[str] = []
    _scoring_fakes(monkeypatch, events=events)
    report = scoring.score_registered_sample(Path("cache.duckdb"))
    assert events[0] == "predictions_ready"
    assert "results_open" in events
    score_positions = [i for i, event in enumerate(events) if event == "score"]
    results_positions = [i for i, event in enumerate(events) if event == "results_open"]
    assert score_positions
    assert max(results_positions) < min(score_positions)
    assert report["metrics"]["brier_observation_count"] == len(REGISTERED_RACE_IDS)


@pytest.mark.parametrize("duplicate", [False, True])
def test_incomplete_or_duplicate_trace_stops_before_results_open_or_score(
    monkeypatch: pytest.MonkeyPatch, duplicate: bool
) -> None:
    from f1si.backtest import scoring

    events: list[str] = []
    _scoring_fakes(
        monkeypatch,
        missing=(("2024-02", 0, "AAA"),) if not duplicate else (),
        duplicate=duplicate,
        events=events,
    )
    with pytest.raises(ValueError, match="prediction trace"):
        scoring.score_registered_sample(Path("cache.duckdb"))
    assert events == ["predictions_ready"]
