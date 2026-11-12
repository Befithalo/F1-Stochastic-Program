"""Safety-car rate and duration from earlier races only (REG-01, D-01 to D-03).

Rate. Let ``k`` be the number of safety-car (SC) deployments and ``n`` the number of race laps
in the earlier in-sample races. With a Beta prior on the per-lap deployment probability ``p``,

    p ~ Beta(a0, b0),   k | p ~ Binomial(n, p)   =>   p | k, n ~ Beta(a0 + k, b0 + n - k).

The prior is ``(a0, b0) = (3, 297)``: mean ``a0 / (a0 + b0) = 1%`` per lap and weight ``a0 + b0 =
300`` laps, about five races. It is a documented weak assumption (assumption A3) that only matters
for the first races of the history. The posterior mean is ``(a0 + k) / (a0 + b0 + n)`` and the
90% interval is the 5% and 95% quantiles of the posterior, ``scipy.stats.beta.ppf``. The
denominator is race laps (D-01). An SC can only start on a green lap, so the exact hazard
denominator is the non-SC laps; the bias is about 4% of the rate and is accepted.

Deployment. A track-status row (sorted per race by ``t_s`` then ``seq``) with status "4" counts
as a deployment iff the previous row's status is missing, "1", "2", "6" or "7". An SC row that
follows a red flag ("5") is a restart under the safety car, not a new deployment, and a repeated
"4" row is the same SC.

Duration. The number of leader laps between the deployment row and the next row with another
status, ``count(cutoff_s <= t_end) - count(cutoff_s <= t_start)`` over the race's ``lap_cutoffs``
(at least 1). SCs that end in a red flag ("5") or never end are excluded from the durations
(they still count as deployments). The reported duration is the lower median of the measured
durations when at least ``MIN_EVENTS_FOR_MEDIAN`` exist, else ``FALLBACK_DURATION_LAPS`` (D-03).

Virtual safety cars and red flags are not modelled (D-02); a VSC event type can reuse the same
mechanics later (Phase 8).

The estimator takes a ``History`` (earlier in-sample races only), never the accessor, so it cannot
read the current race or the future (look-ahead rule).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scipy.stats import beta

if TYPE_CHECKING:
    import pandas as pd

    from f1si.data.asof import History

PRIOR_ALPHA: Final[float] = 3.0
PRIOR_BETA: Final[float] = 297.0
MIN_EVENTS_FOR_MEDIAN: Final[int] = 5
FALLBACK_DURATION_LAPS: Final[int] = 4
_CI_LEVELS: Final[tuple[float, float]] = (0.05, 0.95)
_DEPLOYMENT_PREDECESSORS: Final[frozenset[str | None]] = frozenset({None, "1", "2", "6", "7"})


@dataclass(frozen=True)
class ScRateEstimate:
    """Per-lap SC probability with a 90% interval, and the SC duration to simulate."""

    rate_per_lap: float
    ci_low: float
    ci_high: float
    n_deployments: int
    n_laps: int
    duration_laps: int
    n_durations: int
    is_prior_only: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.rate_per_lap <= 1.0:
            raise ValueError(f"rate_per_lap must be in [0, 1], got {self.rate_per_lap}")
        if not self.ci_low <= self.rate_per_lap <= self.ci_high:
            raise ValueError(
                f"need ci_low <= rate <= ci_high, got {self.ci_low}, {self.rate_per_lap}, "
                f"{self.ci_high}"
            )
        if self.duration_laps < 1:
            raise ValueError(f"duration_laps must be at least 1, got {self.duration_laps}")
        for name in ("n_deployments", "n_laps", "n_durations"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative, got {getattr(self, name)}")


def _status_or_none(value: object) -> str | None:
    if value is None or value != value:  # None or NaN/NA
        return None
    return str(value)


def _race_events(status: pd.DataFrame, cutoffs: np.ndarray[Any, Any]) -> tuple[int, list[int]]:
    """(deployments, measured durations in laps) of one race."""
    ordered = status.sort_values(["t_s", "seq"], kind="stable")
    codes = [_status_or_none(v) for v in ordered["status"].tolist()]
    times = [float(v) for v in ordered["t_s"].tolist()]
    deployments = 0
    durations: list[int] = []
    previous: str | None = None
    for k, code in enumerate(codes):
        if code == "4" and previous in _DEPLOYMENT_PREDECESSORS:
            deployments += 1
            end = next((j for j in range(k + 1, len(codes)) if codes[j] != "4"), None)
            if end is not None and codes[end] != "5":
                laps = int((cutoffs <= times[end]).sum() - (cutoffs <= times[k]).sum())
                durations.append(max(1, laps))
        previous = code
    return deployments, durations


def estimate_sc_rate(history: History) -> ScRateEstimate:
    """Estimate the per-lap SC rate and SC duration from the races in `history`.

    Args:
        history: earlier in-sample races only (as returned by the as-of door).

    Returns:
        The Beta-Binomial posterior mean and 90% interval, the SC duration in laps, and
        ``is_prior_only`` (True when no earlier race has track-status data). Never raises on
        empty tables.
    """
    track = history.track_status
    cut = history.lap_cutoffs
    deployments = 0
    n_laps = 0
    durations: list[int] = []
    if len(track) > 0 and len(cut) > 0:
        cut_by_race = {rid: g for rid, g in cut.groupby("race_id")}
        for race_id, status in track.groupby("race_id"):
            lap_cut = cut_by_race.get(race_id)
            if lap_cut is None:
                continue
            cutoffs = np.sort(lap_cut["cutoff_s"].to_numpy(dtype=np.float64))
            n_laps += int(lap_cut["lap"].max())
            k, found = _race_events(status, cutoffs)
            deployments += k
            durations.extend(found)
    a = PRIOR_ALPHA + deployments
    b = PRIOR_BETA + n_laps - deployments
    mean = a / (a + b)
    quantiles = np.asarray(beta.ppf(_CI_LEVELS, a, b), dtype=np.float64)
    low, high = float(quantiles[0]), float(quantiles[1])
    if len(durations) >= MIN_EVENTS_FOR_MEDIAN:
        duration = int(sorted(durations)[(len(durations) - 1) // 2])
    else:
        duration = FALLBACK_DURATION_LAPS
    return ScRateEstimate(
        rate_per_lap=mean,
        ci_low=min(low, mean),
        ci_high=max(high, mean),
        n_deployments=deployments,
        n_laps=n_laps,
        duration_laps=duration,
        n_durations=len(durations),
        is_prior_only=n_laps == 0,
    )
