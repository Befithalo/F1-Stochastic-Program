"""Kalman filter for the hidden tyre-wear rate of one stint (PAC-03, D-01 to D-09, D-18).

What it estimates. Inside a stint a car's fuel-corrected lap time is a level that drifts upward
by the wear rate (seconds per lap) every lap, plus noise. The filter turns one lap time at a time
into a posterior for the wear rate, with a standard deviation that includes the fuel uncertainty.

State and equations. The state is x = [level, rate, fuel_dev], with covariance P (3 x 3):

    level     fuel-corrected pace at the current lap (s)
    rate      tyre wear, seconds gained per lap of tyre age (s / lap)
    fuel_dev  residual error of the fuel correction already removed from the lap time (s / lap)

    transition   x' = F x + w,   F = [[1, 1, 1], [0, 1, 0], [0, 0, 1]],   Q = diag(0, q^2, 0)
    observation  y  = H x + v,   H = [1, 0, 0],                           Var(v) = sigma^2

so the level moves by rate + fuel_dev each lap. One call to `observe` advances exactly one race
lap. With innovation e = y - H x and S = H P H' + sigma^2, the gain is K = P H' / S, the mean
update is x = x + K e and the covariance update is the Joseph form

    P = (I - K H) P (I - K H)' + sigma^2 K K',

symmetrised as (P + P') / 2 so rounding cannot make P lose symmetry or positive semi-definiteness.

Equivalence to Bayesian regression. With q = 0 the model is the static regression
y_d = level_0 + (rate + fuel_dev) d with d = laps since the first measured lap, and the filter
posterior equals the closed-form Bayesian linear regression with the same Gaussian priors
(tests/pace/test_kalman_math.py). Fuel and wear are therefore inseparable inside one stint: both
multiply d, only the prior separates them. With K measured laps, Sxx = K (K^2 - 1) / 12 and
tau the prior SD of the rate, the posterior rate variance is

    Var = tau^2 - tau^4 / (tau^2 + fuel_sd^2 + sigma^2 / Sxx),

which tends to the floor tau^2 fuel_sd^2 / (tau^2 + fuel_sd^2) as K grows (`posterior_rate_sd`).

Why the level is diffuse (D-03). The absolute pace level depends on the car, the track and the
fuel at the stint start, none of which the filter knows. It starts as the first usable lap time
with SD DIFFUSE_LEVEL_SD, so the level carries almost no prior information and the rate is learned
from the lap-to-lap trend only.

Which laps update. The caller decides which laps are clean (`f1si.laps.fade_reason`) and passes a
skip reason for the others; a skipped lap only runs the prediction step, so the band does not
shrink on it (D-08). A usable lap is also skipped by the outlier gate: once at least
GATE_MIN_USED laps have been used (DEC-090), a lap whose innovation exceeds GATE_Z standard
deviations of S is rejected, except that the lap right after a rejection is never rejected (a
real step change must not freeze the filter). Non-finite lap times are skipped before they can
touch the covariance.

The array core sees no snapshot. `filter_stints` is the only function in this module that reads
race data, and it receives a `RaceSnapshot` (plain data), never the accessor (D-09).

Priors (D-05, D-06, D-07, D-19). Each stint is its own filter (D-03). The rate prior, the fuel
correction and the noise all come from `fit_linear_pace` of the SAME snapshot, so nothing from a
later lap can leak in. Each quantity falls back on its own to a generic prior when the fit does
not identify it, and the result says which ("fit" or a string starting "prior only"):

    quantity            from the fit                          generic fallback [ASSUMED] (DEC-091)
    wear rate (s/lap)   N(wear_c, se_c^2 + TAU_CAR^2)          N(0.10 / 0.08 / 0.06, 0.05^2)  S/M/H
    fuel effect (s/lap) mean fuel, SD sqrt(se^2 + 0.02^2)     N(-0.05, 0.025^2)
    lap-time noise (s)  sigma_s of the fit                    0.30

The fit prior is used only when the fit is identified and the compound is fitted (D-19). The fuel
correction removes `fuel_mean * (lap - 1)` from each lap time, the same convention as
`LinearPaceFit.predict`; what is left of the fuel error is the filter's fuel state.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from f1si.data.asof import RaceSnapshot
from f1si.interfaces import DRY_COMPOUNDS
from f1si.pace.linear import CI_Z, LinearPaceFit, _classify

GATE_Z: Final = 3.0
GATE_MIN_USED: Final = 3
DIFFUSE_LEVEL_SD: Final = 1000.0

# Generic priors, each [ASSUMED] (DEC-091): used only where the fit does not identify a quantity.
GENERIC_RATE_MEAN: Final = {"SOFT": 0.10, "MEDIUM": 0.08, "HARD": 0.06}  # [ASSUMED] DEC-091
GENERIC_RATE_SD: Final = 0.05  # [ASSUMED] DEC-091
GENERIC_FUEL_MEAN: Final = -0.05  # [ASSUMED] DEC-091
GENERIC_FUEL_SD: Final = 0.025  # [ASSUMED] DEC-091
GENERIC_SIGMA_S: Final = 0.30  # [ASSUMED] DEC-091
TAU_CAR: Final = 0.03  # [ASSUMED] DEC-091: car-to-car spread added to the fitted compound rate
FUEL_SD_EXTRA: Final = 0.02  # [ASSUMED] DEC-091: extra fuel SD (track evolution absorbed, D-25)

_F: Final[NDArray[np.float64]] = np.array(
    [[1.0, 1.0, 1.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64
)
_H: Final[NDArray[np.float64]] = np.array([1.0, 0.0, 0.0], dtype=np.float64)


def _finite(name: str, value: float) -> None:
    """Raise ValueError unless `value` is a finite real number (numpy scalars count, bool not)."""
    is_number = isinstance(value, int | float | np.integer | np.floating)
    if not is_number or isinstance(value, bool | np.bool_) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")


@dataclass(frozen=True)
class WearPrior:
    """Prior and noise settings of one stint's filter (all in seconds or seconds per lap)."""

    rate_mean: float
    rate_sd: float
    fuel_sd: float
    sigma: float
    q: float = 0.0

    def __post_init__(self) -> None:
        for name in ("rate_mean", "rate_sd", "fuel_sd", "sigma", "q"):
            _finite(name, getattr(self, name))
        if self.rate_sd <= 0:
            raise ValueError(f"rate_sd must be > 0, got {self.rate_sd!r}")
        if self.sigma <= 0:
            raise ValueError(f"sigma must be > 0, got {self.sigma!r}")
        if self.fuel_sd < 0:
            raise ValueError(f"fuel_sd must be >= 0, got {self.fuel_sd!r}")
        if self.q < 0:
            raise ValueError(f"q must be >= 0, got {self.q!r}")


@dataclass(frozen=True)
class LapUpdate:
    """What one lap did to the filter. `reason` is None when the lap was used."""

    used: bool
    reason: str | None
    innovation: float | None
    innovation_sd: float | None
    rate_mean: float
    rate_sd: float
    rate_lo: float
    rate_hi: float
    n_used: int
    n_gate_rejections: int


@dataclass(frozen=True)
class FilterSnapshot:
    """The filter's wear estimate as of one lap cutoff."""

    rate_mean: float
    rate_sd: float
    n_used: int
    prior_only: bool
    cutoff_lap: int


class WearFilter:
    """Joseph-form Kalman filter for [level, rate, fuel_dev] (see the module docstring)."""

    def __init__(self, prior: WearPrior) -> None:
        self._prior = prior
        self._x: NDArray[np.float64] = np.array([0.0, prior.rate_mean, 0.0], dtype=np.float64)
        self._p: NDArray[np.float64] = np.diag(
            [DIFFUSE_LEVEL_SD**2, prior.rate_sd**2, prior.fuel_sd**2]
        ).astype(np.float64)
        self._started = False
        self._n_used = 0
        self._n_rejected = 0
        self._last_rejected = False

    # ------------------------------------------------------------------ read-only views

    @property
    def rate_mean(self) -> float:
        """Posterior mean of the wear rate (s / lap)."""
        return float(self._x[1])

    @property
    def rate_sd(self) -> float:
        """Posterior SD of the wear rate (s / lap), marginal, so it includes the fuel error."""
        return math.sqrt(max(float(self._p[1, 1]), 0.0))

    @property
    def n_used(self) -> int:
        """Number of laps that updated the filter."""
        return self._n_used

    @property
    def n_gate_rejections(self) -> int:
        """Number of laps rejected by the outlier gate."""
        return self._n_rejected

    # ------------------------------------------------------------------ recursion

    def _predict(self) -> None:
        q = np.zeros((3, 3), dtype=np.float64)
        q[1, 1] = self._prior.q**2
        self._x = _F @ self._x
        p = _F @ self._p @ _F.T + q
        self._p = 0.5 * (p + p.T)

    def _result(
        self,
        used: bool,
        reason: str | None,
        innovation: float | None,
        innovation_sd: float | None,
    ) -> LapUpdate:
        mean, sd = self.rate_mean, self.rate_sd
        return LapUpdate(
            used=used,
            reason=reason,
            innovation=innovation,
            innovation_sd=innovation_sd,
            rate_mean=mean,
            rate_sd=sd,
            rate_lo=mean - CI_Z * sd,
            rate_hi=mean + CI_Z * sd,
            n_used=self._n_used,
            n_gate_rejections=self._n_rejected,
        )

    def observe(self, y: float | None, skip_reason: str | None = None) -> LapUpdate:
        """Advance one race lap and update with `y` (fuel-corrected lap time) when usable.

        `skip_reason` marks a lap the caller rejects (for example a `fade_reason` string); the
        lap then only predicts. `y` of None or non-finite is skipped too. Before the first
        usable lap there is no state to advance, so earlier laps are counted as skipped only.
        """
        reason = skip_reason
        value = 0.0
        if reason is None:
            if y is None:
                reason = "no lap time"
            elif not math.isfinite(y):
                reason = "non-finite lap time"
            else:
                value = float(y)
        if self._started:
            self._predict()
        if reason is not None:
            return self._result(False, reason, None, None)

        first = not self._started
        if first:
            self._x[0] = value
            self._started = True
        innovation = value - float(self._x[0])
        r = self._prior.sigma**2
        s = float(self._p[0, 0]) + r
        sd_s = math.sqrt(s)
        if (
            not first
            and self._n_used >= GATE_MIN_USED
            and not self._last_rejected
            and abs(innovation) > GATE_Z * sd_s
        ):
            self._n_rejected += 1
            self._last_rejected = True
            return self._result(False, "outlier gate", innovation, sd_s)

        gain = self._p @ _H / s
        self._x = self._x + gain * innovation
        a = np.eye(3, dtype=np.float64) - np.outer(gain, _H)
        p = a @ self._p @ a.T + r * np.outer(gain, gain)
        self._p = 0.5 * (p + p.T)
        self._n_used += 1
        self._last_rejected = False
        if first:
            return self._result(True, None, None, None)
        return self._result(True, None, innovation, sd_s)

    def snapshot(self, cutoff_lap: int) -> FilterSnapshot:
        """The current estimate, stamped with the lap cutoff of the data it was run on."""
        return FilterSnapshot(
            rate_mean=self.rate_mean,
            rate_sd=self.rate_sd,
            n_used=self._n_used,
            prior_only=self._n_used == 0,
            cutoff_lap=int(cutoff_lap),
        )


def posterior_rate_sd(tau: float, sigma: float, fuel_sd: float, n_measured: int) -> float:
    """Closed-form posterior SD of the wear rate after `n_measured` laps with q = 0.

    Var = tau^2 - tau^4 / (tau^2 + fuel_sd^2 + sigma^2 / Sxx), Sxx = K (K^2 - 1) / 12. One
    measured lap carries no slope information, so the answer is the prior SD tau.
    """
    for name, value in (("tau", tau), ("sigma", sigma), ("fuel_sd", fuel_sd)):
        _finite(name, value)
    if tau <= 0 or sigma <= 0 or fuel_sd < 0:
        raise ValueError(
            f"need tau > 0, sigma > 0, fuel_sd >= 0, got {tau!r}, {sigma!r}, {fuel_sd!r}"
        )
    if n_measured < 1:
        raise ValueError(f"n_measured must be >= 1, got {n_measured!r}")
    sxx = n_measured * (n_measured**2 - 1) / 12.0
    if sxx == 0.0:
        return tau
    data_var = sigma**2 / sxx
    return math.sqrt(tau**2 - tau**4 / (tau**2 + fuel_sd**2 + data_var))


@dataclass(frozen=True)
class ResolvedPriors:
    """Priors of one stint and where each came from ("fit" or "prior only: <why>")."""

    prior: WearPrior
    fuel_mean: float
    rate_source: str
    fuel_source: str
    noise_source: str


@dataclass(frozen=True)
class LapRow:
    """One lap of a stint after the filter has seen it (`reason` is None when used)."""

    race_lap: int
    tyre_age: int
    used: bool
    reason: str | None
    rate_mean: float
    rate_sd: float
    rate_lo: float
    rate_hi: float


@dataclass(frozen=True)
class StintFilterResult:
    """Lap-by-lap wear estimate of one driver's stint, as of the snapshot's cutoff."""

    driver_number: int
    stint: int
    compound: str
    priors: ResolvedPriors
    rows: tuple[LapRow, ...]
    n_used: int
    n_gate_rejections: int
    is_current: bool
    cutoff_lap: int


def resolve_priors(fit: LinearPaceFit, compound: str) -> ResolvedPriors:
    """Priors for a stint on `compound` from `fit`, falling back per quantity (D-06, D-19)."""
    report = fit.report
    fuel_known = report.fuel_s_per_lap is not None
    rate = fit.wear_rate(compound) if fuel_known else None
    se = fit.wear_se(compound) if fuel_known else None
    if rate is not None and se is not None and math.isfinite(rate) and math.isfinite(se):
        rate_mean, rate_sd, rate_source = rate, math.sqrt(se**2 + TAU_CAR**2), "fit"
    else:
        rate_mean = GENERIC_RATE_MEAN.get(compound, GENERIC_RATE_MEAN["MEDIUM"])
        rate_sd = GENERIC_RATE_SD
        why = "compound not fitted yet" if fuel_known else "fit not identified yet"
        rate_source = f"prior only: {why}"
    fuel = report.fuel_s_per_lap
    if fuel is not None and report.fuel_se is not None and math.isfinite(fuel):
        fuel_mean = fuel
        fuel_sd = math.sqrt(report.fuel_se**2 + FUEL_SD_EXTRA**2)
        fuel_source = "fit"
    else:
        fuel_mean, fuel_sd = GENERIC_FUEL_MEAN, GENERIC_FUEL_SD
        fuel_source = "prior only: fuel effect not identified yet"
    sigma = report.sigma_s
    if sigma is not None and math.isfinite(sigma) and sigma > 0:
        noise, noise_source = float(sigma), "fit"
    else:
        noise, noise_source = GENERIC_SIGMA_S, "prior only: noise not estimated yet"
    return ResolvedPriors(
        prior=WearPrior(rate_mean=rate_mean, rate_sd=rate_sd, fuel_sd=fuel_sd, sigma=noise),
        fuel_mean=fuel_mean,
        rate_source=rate_source,
        fuel_source=fuel_source,
        noise_source=noise_source,
    )


def filter_stints(
    snapshot: RaceSnapshot,
    fit: LinearPaceFit,
    *,
    driver_numbers: Sequence[int] | None = None,
) -> tuple[StintFilterResult, ...]:
    """Run one `WearFilter` per driver stint over the laps visible in `snapshot`.

    `fit` must be the fit of the same snapshot (D-07). Laps are read in race order; the clean-lap
    rule is `f1si.pace.linear._classify` (D-08). Never raises on an empty snapshot.
    """
    laps = snapshot.laps
    if laps.empty:
        return ()
    table = _classify(laps)
    table = table[table["stint"].notna()].reset_index(drop=True)
    if table.empty:
        return ()
    at_lap = snapshot.at.lap
    cutoff = at_lap if isinstance(at_lap, int) else int(laps["lap_number"].max())
    wanted = None if driver_numbers is None else {int(n) for n in driver_numbers}
    results: list[StintFilterResult] = []
    for driver, mine in table.groupby("driver", sort=True):
        number = int(str(driver))
        if wanted is not None and number not in wanted:
            continue
        last_stint = float(str(mine.loc[mine["lap"].idxmax(), "stint"]))
        for stint_no, grp in mine.groupby("stint", sort=True):
            stint_value = float(str(stint_no))
            names = [str(c) for c in grp["compound"] if isinstance(c, str)]
            if not names or any(c not in DRY_COMPOUNDS for c in names):
                continue
            compound = max(set(names), key=names.count)
            priors = resolve_priors(fit, compound)
            wear_filter = WearFilter(priors.prior)
            rows: list[LapRow] = []
            previous_age = -1
            for _, lap in grp.sort_values("lap").iterrows():
                race_lap = int(lap["lap"])
                age = previous_age + 1 if math.isnan(lap["age"]) else int(lap["age"])
                previous_age = age
                reason = lap["reason"] if isinstance(lap["reason"], str) else None
                y: float | None = None
                if reason is None:
                    y = float(lap["time"]) - priors.fuel_mean * (race_lap - 1)
                update = wear_filter.observe(y, reason)
                rows.append(
                    LapRow(
                        race_lap=race_lap,
                        tyre_age=age,
                        used=update.used,
                        reason=update.reason,
                        rate_mean=update.rate_mean,
                        rate_sd=update.rate_sd,
                        rate_lo=update.rate_lo,
                        rate_hi=update.rate_hi,
                    )
                )
            results.append(
                StintFilterResult(
                    driver_number=number,
                    stint=int(stint_value),
                    compound=compound,
                    priors=priors,
                    rows=tuple(rows),
                    n_used=wear_filter.n_used,
                    n_gate_rejections=wear_filter.n_gate_rejections,
                    is_current=stint_value == last_stint,
                    cutoff_lap=cutoff,
                )
            )
    return tuple(results)


def current_stint_snapshots(results: Sequence[StintFilterResult]) -> dict[int, FilterSnapshot]:
    """Driver number -> posterior of the driver's current stint, only when it used a lap."""
    out: dict[int, FilterSnapshot] = {}
    for r in results:
        if r.is_current and r.n_used >= 1 and r.rows:
            last = r.rows[-1]
            out[r.driver_number] = FilterSnapshot(
                rate_mean=last.rate_mean,
                rate_sd=last.rate_sd,
                n_used=r.n_used,
                prior_only=False,
                cutoff_lap=r.cutoff_lap,
            )
    return out


@dataclass(frozen=True)
class CutoffRow:
    """The newest row a driver's filter showed at `cutoff_lap`, with its stint's priors.

    `row.race_lap` can be below `cutoff_lap`: cars behind the leader have not yet completed the
    leader's lap when the cutoff is taken.
    """

    cutoff_lap: int
    stint: int
    compound: str
    priors: ResolvedPriors
    row: LapRow


def cutoff_row(
    results: Sequence[StintFilterResult], driver_number: int, cutoff_lap: int
) -> CutoffRow | None:
    """The driver's newest row with race_lap <= `cutoff_lap`, or None (nothing visible yet).

    The as-of door shows a car's lap only after the leader's cutoff lap has passed it, so a car
    behind the leader usually has its lap `cutoff_lap - 1` as the newest one. Pure lookup over
    already computed results; it reads no race data.
    """
    best: CutoffRow | None = None
    for r in results:
        if r.driver_number != driver_number:
            continue
        for row in r.rows:
            if row.race_lap <= cutoff_lap and (best is None or row.race_lap > best.row.race_lap):
                best = CutoffRow(
                    cutoff_lap=cutoff_lap,
                    stint=r.stint,
                    compound=r.compound,
                    priors=r.priors,
                    row=row,
                )
    return best
