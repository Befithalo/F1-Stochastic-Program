"""Cutoff-safe five-state regime labels and transition estimates."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING, Final

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from f1si.data.asof import History

REGIMES: Final[tuple[str, ...]] = ("green", "vsc", "sc", "red", "wet")
_STATUS_REGIME: Final[dict[str, str]] = {"4": "sc", "5": "red", "6": "vsc", "7": "vsc"}


@dataclass(frozen=True, eq=False)
class RegimeEstimate:
    """Race-local transition probabilities and observed transition counts."""

    transition: np.ndarray
    counts: np.ndarray
    n_transitions: int

    def __post_init__(self) -> None:
        matrix = np.asarray(self.transition, dtype=np.float64)
        counts = np.asarray(self.counts, dtype=np.float64)
        if matrix.shape != (5, 5) or counts.shape != (5, 5):
            raise ValueError("regime transition and counts must have shape (5, 5)")
        if not np.isfinite(matrix).all() or (matrix < 0).any():
            raise ValueError("regime transition probabilities must be finite and non-negative")
        if not np.allclose(matrix.sum(axis=1), 1.0, atol=1e-10):
            raise ValueError("each regime transition row must sum to one")
        if not np.isfinite(counts).all() or (counts < 0).any():
            raise ValueError("regime transition counts must be finite and non-negative")
        object.__setattr__(self, "transition", np.ascontiguousarray(matrix))
        object.__setattr__(self, "counts", np.ascontiguousarray(counts))


def label_regime(track_status: pd.DataFrame, weather: pd.DataFrame, cutoff_s: float) -> str:
    """Label one cutoff using only the latest visible control and rainfall observations."""
    status = track_status
    if len(status):
        status = status.loc[pd.to_numeric(status["t_s"], errors="coerce") <= cutoff_s]
        if len(status):
            latest = status.sort_values(["t_s", "seq"], kind="stable").iloc[-1]["status"]
            if not pd.isna(latest):
                label = _STATUS_REGIME.get(str(latest))
                if label is not None:
                    return label
    rain = weather
    if len(rain):
        rain = rain.loc[pd.to_numeric(rain["t_s"], errors="coerce") <= cutoff_s]
        if len(rain):
            latest = rain.sort_values(["t_s", "seq"], kind="stable").iloc[-1]["rainfall"]
            if not pd.isna(latest) and bool(latest):
                return "wet"
    return "green"


def estimate_regime_model(history: History) -> RegimeEstimate:
    """Fit earlier-race one-lap transitions with independent Dirichlet(1) row priors.

    Each race's lap sequence is labelled from that race's track-control and weather observations;
    transitions are counted only within that race, so the last state of one race never connects to
    the first state of another.
    """
    counts = np.zeros((5, 5), dtype=np.float64)
    cutoffs = history.laps.loc[history.laps["lap_end_s"].notna()]
    if len(cutoffs):
        for race_id, rows in cutoffs.groupby("race_id", sort=False):
            ordered = rows.groupby("lap_number", sort=True)["lap_end_s"].min()
            track = history.track_status.loc[history.track_status["race_id"] == race_id]
            weather = history.weather.loc[history.weather["race_id"] == race_id]
            labels = [
                label_regime(track, weather, float(cutoff))
                for cutoff in ordered.to_numpy(dtype=np.float64)
            ]
            for before, after in pairwise(labels):
                counts[REGIMES.index(before), REGIMES.index(after)] += 1.0
    smoothed = counts + 1.0
    matrix = smoothed / smoothed.sum(axis=1, keepdims=True)
    return RegimeEstimate(matrix, counts, int(counts.sum()))
