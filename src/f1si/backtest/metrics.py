"""Deterministic proper scores and equal-race uncertainty summaries."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _finish_positions(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce")


def _binary_outcomes(finish: pd.Series) -> tuple[pd.Series, pd.Series]:
    podium = (finish <= 3).fillna(False).astype(np.float64)
    top10 = (finish <= 10).fillna(False).astype(np.float64)
    return podium, top10


def brier_scores(rows: pd.DataFrame, *, paired: bool = False) -> dict[str, Any]:
    """Return binary Brier scores; null/unclassified finishes are failures.

    When baseline columns are present and ``paired`` is true, both models use one identical
    finite-probability and observed-row mask and the result includes paired row losses.
    """
    required = {"finish_position", "predicted_podium", "predicted_top10"}
    missing = required.difference(rows.columns)
    if missing:
        raise ValueError(f"Brier rows are missing required columns: {', '.join(sorted(missing))}")
    finish = _finish_positions(rows["finish_position"])
    outcomes = _binary_outcomes(finish)
    model_columns = ("predicted_podium", "predicted_top10")
    paired_columns = ("baseline_podium", "baseline_top10")
    use_paired = paired and set(paired_columns).issubset(rows.columns)
    mask = pd.Series(True, index=rows.index)
    for column in model_columns:
        mask &= pd.to_numeric(rows[column], errors="coerce").notna()
    if use_paired:
        for column in paired_columns:
            mask &= pd.to_numeric(rows[column], errors="coerce").notna()
    if not mask.any():
        raise ValueError("Brier scores require at least one shared observed prediction row")

    result: dict[str, Any] = {"observation_count": int(mask.sum())}
    for name, outcome, model_column in zip(
        ("podium", "top10"), outcomes, model_columns, strict=True
    ):
        model_loss = (pd.to_numeric(rows[model_column]).loc[mask] - outcome.loc[mask]) ** 2
        result[name] = float(model_loss.mean())
        if use_paired:
            baseline_column = paired_columns[0 if name == "podium" else 1]
            baseline_loss = (
                pd.to_numeric(rows[baseline_column]).loc[mask] - outcome.loc[mask]
            ) ** 2
            result[f"baseline_{name}"] = float(baseline_loss.mean())
            result[f"model_minus_baseline_{name}"] = float((model_loss - baseline_loss).mean())
            result[f"model_{name}_losses"] = model_loss.to_numpy(dtype=np.float64)
            result[f"baseline_{name}_losses"] = baseline_loss.to_numpy(dtype=np.float64)
    if use_paired:
        result["model_mask"] = mask.copy()
        result["baseline_mask"] = mask.copy()
    return result


def grid_position_probability(
    history: pd.DataFrame, *, grid_position: int | None, field_size: int
) -> dict[str, float]:
    """Estimate podium/top-10 chance from earlier race results with five prior starts."""
    if field_size < 1:
        raise ValueError("field_size must be positive")
    neutral = {"podium": 3.0 / field_size, "top10": min(10, field_size) / field_size}
    if grid_position is None or pd.isna(grid_position) or history.empty:
        return neutral
    required = {"grid_position", "finish_position"}
    if not required.issubset(history.columns):
        raise ValueError("grid history requires grid_position and finish_position")
    positions = pd.to_numeric(history["grid_position"], errors="coerce")
    earlier_at_position = history.loc[positions == grid_position]
    if earlier_at_position.empty:
        return neutral
    finish = _finish_positions(earlier_at_position["finish_position"])
    starts = len(earlier_at_position)
    podium_events = int((finish <= 3).fillna(False).sum())
    top10_events = int((finish <= 10).fillna(False).sum())
    denominator = starts + 5.0
    return {
        "podium": (podium_events + 5 * neutral["podium"]) / denominator,
        "top10": (top10_events + 5 * neutral["top10"]) / denominator,
    }


def finish_interval(
    samples: np.ndarray | pd.DataFrame, *, coverage: float = 0.9, observed: bool = False
) -> tuple[int, int] | dict[str, int]:
    """Use inclusive empirical inverted-CDF endpoints; optionally summarize observed hits."""
    if not 0.0 < coverage < 1.0:
        raise ValueError("coverage must be between zero and one")
    alpha = (1.0 - coverage) / 2.0
    if isinstance(samples, pd.DataFrame):
        if not {"finish_samples", "finish_position"}.issubset(samples.columns):
            raise ValueError("coverage rows require finish_samples and finish_position")
        classified = pd.to_numeric(samples["finish_position"], errors="coerce").notna()
        covered = 0
        classified_rows = samples.loc[classified]
        observed_finishes = pd.to_numeric(
            classified_rows["finish_position"], errors="coerce"
        ).to_numpy(dtype=np.float64)
        for sample, observed_finish in zip(
            classified_rows["finish_samples"].tolist(), observed_finishes, strict=True
        ):
            low, high = finish_interval(np.asarray(sample), coverage=coverage)
            covered += int(low <= observed_finish <= high)
        return {"covered": covered, "classified_finishers": int(classified.sum())}
    positions = np.asarray(samples, dtype=np.float64).reshape(-1)
    if positions.size == 0 or not np.isfinite(positions).all():
        raise ValueError("finish samples must be non-empty and finite")
    endpoints = np.quantile(positions, [alpha, 1.0 - alpha], method="inverted_cdf")
    return int(endpoints[0]), int(endpoints[1])


def summarize_by_race(rows: pd.DataFrame, *, value: str) -> dict[str, Any]:
    """Average rows within race, then assign every observed race equal weight."""
    if "race_id" not in rows or value not in rows:
        raise ValueError("race summary requires race_id and the selected value column")
    per_race = rows.groupby("race_id", sort=True)[value].mean().astype(float)
    if per_race.empty or not np.isfinite(per_race.to_numpy()).all():
        raise ValueError("race summary requires finite observations for at least one race")
    return {
        "mean": float(per_race.mean()),
        "race_count": len(per_race),
        "per_race": {str(race): float(score) for race, score in per_race.items()},
    }


def race_cluster_interval(
    rows: pd.DataFrame,
    *,
    value: str,
    rng: np.random.Generator,
    n_resamples: int = 2_000,
    confidence: float = 0.95,
) -> dict[str, float | int]:
    """Bootstrap already paired row values by complete race clusters."""
    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be an injected numpy.random.Generator")
    if n_resamples < 1:
        raise ValueError("n_resamples must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between zero and one")
    summary = summarize_by_race(rows, value=value)
    race_values = np.asarray(list(summary["per_race"].values()), dtype=np.float64)
    draws = rng.integers(0, len(race_values), size=(n_resamples, len(race_values)))
    bootstrap_means = race_values[draws].mean(axis=1)
    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(bootstrap_means, [tail, 1.0 - tail])
    return {
        "mean": float(summary["mean"]),
        "low": float(low),
        "high": float(high),
        "cluster_count": len(race_values),
    }
