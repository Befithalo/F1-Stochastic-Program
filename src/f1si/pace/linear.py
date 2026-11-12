"""Joint fuel and tyre-wear fit, and pit-loss measurement (PAC-01, D-01 to D-05, D-19, D-25).

Model. For driver `d` on lap `L` (1-based) with tyre compound `c` and tyre age `a` (laps on the
tyres at the END of the lap), one ordinary least squares fit over clean laps:

    t(d, L) = alpha_d + fuel * (L - 1) + wear[c] * a + eps,    eps ~ Normal(0, sigma^2)

`alpha_d` is a per-driver intercept; `fuel` (s per lap, negative: the car gets lighter) is shared
by all drivers; `wear[c]` (s per lap of tyre age) is shared by all drivers on compound `c`.

Why fuel and wear separate. Tyre age resets at a stop while the lap number keeps rising. Inside
one stint the two are the same straight line (age and lap number rise together), so one stint
alone cannot tell them apart. A driver with two stints on different tyres has two different
age-versus-lap lines, and that difference is what identifies each effect. With no driver having
two stints visible (for example before the first stop) the fit says so and reports no number.

Identification rests on there being no stint-level effect other than tyre age. The fuel estimate
therefore also absorbs track evolution (the track getting faster as rubber is laid down); that is
likely, not proven (D-25). Fuel is reported as measured, never clamped. Compound pace offsets
(a fresh hard being slower than a fresh soft at age zero) are not modeled (D-19); at Bahrain 2023
a HARD offset measured +0.26 s with standard error 0.13 s.

Honesty rules. The design matrix is rebuilt from scratch on every pass. If its rank is deficient,
its condition number is above `COND_LIMIT`, or the residual degrees of freedom are below
`MIN_RESID_DF`, the fit returns no fuel or wear numbers and names what cannot be identified; it
never falls back to a minimum-norm answer. A compound needs at least `MIN_CLEAN_LAPS_PER_COMPOUND`
clean laps from at least `MIN_STINTS_PER_COMPOUND` stints, otherwise it is listed as "not enough
data" and its laps leave the fit. After a first solve, laps with a residual further than
`MAD_K` robust standard deviations (1.4826 * median absolute deviation) from the median are
trimmed, up to `MAX_TRIM_ITERATIONS` passes. Laps with no stint number are dropped with the
reason "no stint" (they must not share one invented stint; DEC-070). Standard errors are
classical, with the covariance taken from the thin SVD X = U S V' (no matrix inverse; DEC-071),
and `COND_LIMIT` = 1e6 so that cond(X'X) = cond(X)^2 stays far below double-precision
breakdown (1e16):

    s^2 = RSS / (n - p),    cov = s^2 V diag(1 / S^2) V',    SE = sqrt(diag(cov)),
    interval = estimate +/- 1.96 SE

Trimming at +/- c cuts the tails, so RSS / (n - p) understates the noise variance. If the noise
is Normal(0, sigma^2) cut at +/- c, the kept variance is sigma^2 * v(c / sigma) with

    v(k) = 1 - 2 k phi(k) / (2 Phi(k) - 1)        (v(3) = 0.9733)

and `sigma_s` is the root of sigma^2 v(c / sigma) = RSS / (n - p), with c the cutoff actually
applied in the last pass (or the largest kept deviation if larger). `sigma_s` and the SEs use that
corrected sigma (DEC-072).

The wear slope SE is what fills `RaceState` `wear_sd` (D-04).

Pit loss (D-05). For a green-flag stop, loss = (in-lap + out-lap time) - (the model's clean
prediction for the same two laps). The estimate is the median over visible stops with a 10-90%
range. With no usable stop a documented default of `DEFAULT_PIT_LOSS_S` is returned and flagged.

The module sees only a `RaceSnapshot` (plain data), so at lap N it uses only laps visible at N.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from f1si.data.asof import RaceSnapshot
from f1si.interfaces import DRY_COMPOUNDS
from f1si.laps import fade_reason, slow_status

MIN_CLEAN_LAPS_PER_COMPOUND: Final = 30
MIN_STINTS_PER_COMPOUND: Final = 2
MIN_DRIVER_LAPS: Final = 5
MIN_RESID_DF: Final = 30
MAD_K: Final = 3.0
MAX_TRIM_ITERATIONS: Final = 5
CI_Z: Final = 1.96
COND_LIMIT: Final = 1e6
FUEL_SANITY_RANGE: Final = (-0.06, -0.03)
DEFAULT_PIT_LOSS_S: Final = 22.0
_NULL_LOADING: Final = 1e-6


@dataclass(frozen=True)
class CompoundFit:
    """Fitted wear rate of one compound, in seconds per lap of tyre age."""

    compound: str
    wear_s_per_lap: float
    se: float
    ci_low: float
    ci_high: float
    n_laps: int
    n_stints: int


@dataclass(frozen=True)
class FitReport:
    """Everything the fit found, as plain Python values (no arrays)."""

    fuel_s_per_lap: float | None
    fuel_se: float | None
    fuel_ci_low: float | None
    fuel_ci_high: float | None
    compounds: tuple[CompoundFit, ...]
    not_enough_data: tuple[str, ...]
    unidentified: tuple[str, ...]
    driver_offsets: Mapping[int, float]
    sigma_s: float | None
    df_resid: int
    n_clean: int
    n_trimmed: int
    dropped: Mapping[str, int]
    message: str
    driver_offset_se: Mapping[int, float] = field(default_factory=dict)


@dataclass(frozen=True)
class PitLossEstimate:
    """Pit loss in seconds: median and 10-90% range over green-flag stops, or the default."""

    median_s: float
    p10_s: float
    p90_s: float
    n_stops: int
    n_slow_excluded: int
    n_unusable: int
    is_default: bool


@dataclass(frozen=True)
class LinearPaceFit:
    """A fitted `PaceModel`: mean = alpha_d + fuel * (lap - 1) + wear[c] * tire_age."""

    report: FitReport

    @property
    def is_identified(self) -> bool:
        """True if fuel and every kept compound's wear slope have numbers."""
        return self.report.fuel_s_per_lap is not None and bool(self.report.compounds)

    @property
    def fitted_compounds(self) -> tuple[str, ...]:
        """Compounds that have a wear slope."""
        return tuple(c.compound for c in self.report.compounds)

    @property
    def fuel_effect(self) -> float | None:
        """Fuel effect in seconds per lap, or None if not identified."""
        return self.report.fuel_s_per_lap

    def wear_rate(self, compound: str) -> float | None:
        """Wear rate in seconds per lap of tyre age, or None for an unfitted compound."""
        for c in self.report.compounds:
            if c.compound == compound:
                return c.wear_s_per_lap
        return None

    def wear_se(self, compound: str) -> float | None:
        """Standard error of the wear rate; this fills `RaceState` `wear_sd` (D-04)."""
        for c in self.report.compounds:
            if c.compound == compound:
                return c.se
        return None

    def pace_offset(self, driver_number: int) -> float | None:
        """Driver intercept minus the mean intercept over all fitted drivers.

        It includes each driver's level over their clean laps. None for a driver not in the fit.
        """
        offsets = self.report.driver_offsets
        if driver_number not in offsets:
            return None
        return offsets[driver_number] - float(np.mean(list(offsets.values())))

    def pace_offset_se(self, driver_number: int) -> float | None:
        """Standard error of the driver's raw intercept, or None for a driver not in the fit.

        This is the SE of the raw offset, not of the offset minus the mean offset; the raw SE is
        the conservative per-driver value (DEC-077).
        """
        return self.report.driver_offset_se.get(driver_number)

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Return (mean, sd): alpha_d + fuel * (lap - 1) + wear[c] * tire_age, sd = sigma.

        Raises:
            ValueError: if the fit is not identified, or a driver or compound was not fitted.
        """
        report = self.report
        if not self.is_identified or report.fuel_s_per_lap is None or report.sigma_s is None:
            raise ValueError(
                "The pace fit is not identified: "
                + (", ".join(report.unidentified) or report.message)
            )
        alpha = np.empty(driver.shape, dtype=np.float64)
        for number in np.unique(driver):
            if int(number) not in report.driver_offsets:
                raise ValueError(f"Driver number {int(number)} was not in the pace fit")
            alpha[driver == number] = report.driver_offsets[int(number)]
        wear = np.empty(driver.shape, dtype=np.float64)
        for name in np.unique(compound):
            rate = self.wear_rate(str(name))
            if rate is None:
                raise ValueError(f"Compound {str(name)!r} was not fitted (no wear rate)")
            wear[compound == name] = rate
        mean = (
            alpha
            + report.fuel_s_per_lap * (lap.astype(np.float64) - 1.0)
            + wear * tire_age.astype(np.float64)
        )
        return mean, np.full(driver.shape, report.sigma_s, dtype=np.float64)


def _unidentified(
    n_clean: int,
    dropped: Mapping[str, int],
    not_enough: tuple[str, ...],
    unidentified: tuple[str, ...],
    message: str,
    df_resid: int = 0,
    n_trimmed: int = 0,
) -> LinearPaceFit:
    return LinearPaceFit(
        FitReport(
            fuel_s_per_lap=None,
            fuel_se=None,
            fuel_ci_low=None,
            fuel_ci_high=None,
            compounds=(),
            not_enough_data=not_enough,
            unidentified=unidentified,
            driver_offsets={},
            sigma_s=None,
            df_resid=df_resid,
            n_clean=n_clean,
            n_trimmed=n_trimmed,
            dropped=dict(dropped),
            message=message,
        )
    )


def _classify(laps: pd.DataFrame) -> pd.DataFrame:
    """One row per lap with plain columns and the first matching drop reason (None = clean)."""
    pit_in = laps["is_pit_in_lap"].fillna(False).astype(bool).to_numpy()
    pit_out = laps["is_pit_out_lap"].fillna(False).astype(bool).to_numpy()
    time_s = laps["lap_time_s"].astype("Float64").to_numpy(dtype=np.float64, na_value=np.nan)
    age = laps["tyre_life"].astype("Float64").to_numpy(dtype=np.float64, na_value=np.nan)
    stint = laps["stint"].astype("Float64").to_numpy(dtype=np.float64, na_value=np.nan)
    compound = [
        str(v).upper() if isinstance(v, str) else None for v in laps["compound"].astype("object")
    ]
    lap_no = laps["lap_number"].astype(int).to_numpy()
    status = list(laps["track_status"].astype("object"))
    reasons: list[str | None] = []
    for i in range(len(laps)):
        reason: str | None
        if np.isnan(time_s[i]):
            reason = "no lap time"
        else:
            reason = fade_reason(int(lap_no[i]), bool(pit_in[i]), bool(pit_out[i]), status[i])
            if reason is None:
                if compound[i] is None or np.isnan(age[i]):
                    reason = "no compound or tyre age"
                elif np.isnan(stint[i]):
                    reason = "no stint"
                elif compound[i] not in DRY_COMPOUNDS:
                    reason = "wet compound"
        reasons.append(reason)
    return pd.DataFrame(
        {
            "driver": laps["driver_number"].astype(int).to_numpy(),
            "lap": lap_no.astype(float),
            "time": time_s,
            "age": age,
            "stint": stint,
            "compound": pd.Series(compound, dtype="object").to_numpy(),
            "reason": pd.Series(reasons, dtype="object").to_numpy(),
        }
    )


@dataclass(frozen=True)
class _LapRow:
    """One lap as plain values, for pit-loss lookups."""

    time_s: float
    age: float
    compound: str
    slow: bool


@dataclass
class _Design:
    """One design matrix pass over the active clean laps."""

    rows: NDArray[np.intp]
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    drivers: list[int]
    kept: list[str]
    not_enough: list[str]
    excluded: dict[int, str]  # row index -> reason it left the regression


def _build(table: pd.DataFrame, active: NDArray[np.bool_]) -> _Design:
    """Rebuild the design: driver dummies, a fuel column, one wear column per kept compound."""
    excluded: dict[int, str] = {}
    live = active.copy()
    not_enough: set[str] = set()
    driver_all = table["driver"].to_numpy()
    comp_all = table["compound"].to_numpy()
    stint_all = table["stint"].to_numpy()
    while True:
        changed = False
        drivers_here = driver_all[live]
        counts = Counter(int(d) for d in drivers_here)
        sparse = {d for d, n in counts.items() if n < MIN_DRIVER_LAPS}
        if sparse:
            for idx in np.flatnonzero(live):
                if int(driver_all[idx]) in sparse:
                    live[idx] = False
                    excluded[int(idx)] = "driver with too few laps"
            changed = True
        for name in sorted({str(c) for c in comp_all[live]}):
            mask = live & (comp_all == name)
            stints = {
                (int(d), float(s)) for d, s in zip(driver_all[mask], stint_all[mask], strict=True)
            }
            if (
                int(mask.sum()) < MIN_CLEAN_LAPS_PER_COMPOUND
                or len(stints) < MIN_STINTS_PER_COMPOUND
            ):
                not_enough.add(name)
                for idx in np.flatnonzero(mask):
                    live[idx] = False
                    excluded[int(idx)] = "compound with too few laps"
                changed = True
        if not changed:
            break
    rows = np.flatnonzero(live).astype(np.intp)
    drivers = sorted({int(d) for d in driver_all[rows]})
    kept = sorted({str(c) for c in comp_all[rows]})
    n = len(rows)
    x = np.zeros((n, len(drivers) + 1 + len(kept)), dtype=np.float64)
    d_index = {d: i for i, d in enumerate(drivers)}
    for r, idx in enumerate(rows):
        x[r, d_index[int(driver_all[idx])]] = 1.0
    x[:, len(drivers)] = table["lap"].to_numpy()[rows] - 1.0
    ages = table["age"].to_numpy()[rows]
    for j, name in enumerate(kept):
        is_c = comp_all[rows] == name
        x[:, len(drivers) + 1 + j] = np.where(is_c, ages, 0.0)
    y = table["time"].to_numpy()[rows]
    return _Design(rows, x, y, drivers, kept, sorted(not_enough), excluded)


def _param_names(design: _Design) -> list[str]:
    return (
        [f"driver {d}" for d in design.drivers]
        + ["fuel effect"]
        + [f"wear {c}" for c in design.kept]
    )


def truncated_variance_factor(k: float) -> float:
    """Variance of a standard normal cut at +/- k: v(k) = 1 - 2 k phi(k) / (2 Phi(k) - 1)."""
    pdf = math.exp(-0.5 * k * k) / math.sqrt(2.0 * math.pi)
    mass = math.erf(k / math.sqrt(2.0))  # 2 Phi(k) - 1
    return 1.0 - 2.0 * k * pdf / mass


def untruncated_sigma(s: float, cutoff: float) -> float:
    """Normal sigma whose +/- `cutoff` truncation has standard deviation `s`.

    Solves sigma^2 * v(cutoff / sigma) = s^2 for sigma >= s. If no root exists (the sample is
    spread out almost as much as a uniform on the cut), it returns `s` unchanged.
    """
    if s <= 0.0 or cutoff <= 0.0:
        return s

    def gap(sigma: float) -> float:
        return sigma**2 * truncated_variance_factor(cutoff / sigma) - s**2

    upper = 4.0 * s
    if gap(upper) <= 0.0:
        return s
    low, high = s, upper
    for _ in range(100):  # bisection; gap is increasing in sigma
        mid = 0.5 * (low + high)
        if gap(mid) < 0.0:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def fit_linear_pace(snapshot: RaceSnapshot) -> LinearPaceFit:
    """Fit fuel and per-compound wear on the clean laps of `snapshot` (never raises on shortage).

    When the data cannot identify a parameter the returned fit has no numbers and names the
    parameter in `report.unidentified`.
    """
    laps = snapshot.laps
    if laps.empty:
        return _unidentified(0, {}, (), ("fuel effect",), "no laps visible yet")
    table = _classify(laps)
    reason_col = table["reason"].to_numpy()
    final_reason = np.array(reason_col, dtype=object)
    active = np.array([r is None for r in reason_col], dtype=bool)
    n_trimmed = 0
    cutoff: float | None = None
    design = _build(table, active)
    for iteration in range(MAX_TRIM_ITERATIONS + 1):
        design = _build(table, active)
        n, p = design.x.shape
        if n == 0 or not design.kept:
            return _unidentified(
                n,
                _dropped(final_reason, design),
                tuple(design.not_enough),
                ("fuel effect",),
                "no tyre compound has enough clean laps yet",
                n_trimmed=n_trimmed,
            )
        names = _param_names(design)
        try:
            _, sv, vt_thin = np.linalg.svd(design.x, full_matrices=False)
        except np.linalg.LinAlgError:
            return _unidentified(
                n,
                _dropped(final_reason, design),
                tuple(design.not_enough),
                tuple(nm for nm in names if not nm.startswith("driver ")),
                "the least-squares solver did not converge on the laps visible so far",
                df_resid=n - p,
                n_trimmed=n_trimmed,
            )
        rank = int(np.sum(sv > sv[0] * max(design.x.shape) * np.finfo(float).eps))
        cond = float(sv[0] / sv[-1]) if sv[-1] > 0 else float("inf")
        if rank < p or cond > COND_LIMIT:
            vt = np.linalg.svd(design.x, full_matrices=True)[2]
            null = vt[min(rank, p - 1) :]
            loading = np.abs(null).max(axis=0)
            bad = [
                nm
                for nm, v in zip(names, loading, strict=True)
                if v > _NULL_LOADING and not nm.startswith("driver ")
            ]
            bad = bad or ["driver intercepts"]
            return _unidentified(
                n,
                _dropped(final_reason, design),
                tuple(design.not_enough),
                tuple(bad),
                "these parameters cannot be separated with the laps visible so far: "
                + ", ".join(bad)
                + " (a driver needs two stints on different tyres to separate fuel from wear)",
                df_resid=n - p,
                n_trimmed=n_trimmed,
            )
        if n - p < MIN_RESID_DF:
            return _unidentified(
                n,
                _dropped(final_reason, design),
                tuple(design.not_enough),
                tuple(nm for nm in names if not nm.startswith("driver ")),
                f"only {n - p} spare laps beyond the {p} parameters; need {MIN_RESID_DF}",
                df_resid=n - p,
                n_trimmed=n_trimmed,
            )
        coef = np.linalg.lstsq(design.x, design.y, rcond=None)[0]
        resid = design.y - design.x @ coef
        if iteration == MAX_TRIM_ITERATIONS:
            break
        centre = float(np.median(resid))
        sigma_rob = 1.4826 * float(np.median(np.abs(resid - centre)))
        if sigma_rob <= 0.0:
            break
        cutoff = MAD_K * sigma_rob
        out = np.abs(resid - centre) > cutoff
        if not out.any():
            break
        for idx in design.rows[out]:
            active[idx] = False
            final_reason[idx] = "outlier"
        n_trimmed += int(out.sum())
    n, p = design.x.shape
    rss = float(resid @ resid)
    s2 = rss / (n - p)
    if n_trimmed > 0 and cutoff is not None:
        c_eff = max(cutoff, float(np.max(np.abs(resid - np.median(resid)))))
        s2 = untruncated_sigma(float(np.sqrt(s2)), c_eff) ** 2
    cov = s2 * (vt_thin.T / sv**2) @ vt_thin
    se = np.sqrt(np.diag(cov))
    nd = len(design.drivers)
    fuel = float(coef[nd])
    fuel_se = float(se[nd])
    comp_fits: list[CompoundFit] = []
    comp_arr = table["compound"].to_numpy()
    for j, name in enumerate(design.kept):
        k = nd + 1 + j
        mask = comp_arr[design.rows] == name
        stints = {
            (int(d), float(s))
            for d, s in zip(
                table["driver"].to_numpy()[design.rows][mask],
                table["stint"].to_numpy()[design.rows][mask],
                strict=True,
            )
        }
        est, err = float(coef[k]), float(se[k])
        comp_fits.append(
            CompoundFit(
                name, est, err, est - CI_Z * err, est + CI_Z * err, int(mask.sum()), len(stints)
            )
        )
    report = FitReport(
        fuel_s_per_lap=fuel,
        fuel_se=fuel_se,
        fuel_ci_low=fuel - CI_Z * fuel_se,
        fuel_ci_high=fuel + CI_Z * fuel_se,
        compounds=tuple(comp_fits),
        not_enough_data=tuple(design.not_enough),
        unidentified=(),
        driver_offsets={d: float(coef[i]) for i, d in enumerate(design.drivers)},
        sigma_s=float(np.sqrt(s2)),
        df_resid=n - p,
        n_clean=n,
        n_trimmed=n_trimmed,
        dropped=_dropped(final_reason, design),
        message="identified",
        driver_offset_se={d: float(se[i]) for i, d in enumerate(design.drivers)},
    )
    return LinearPaceFit(report)


def _dropped(final_reason: NDArray[np.object_], design: _Design) -> dict[str, int]:
    """Count laps by the reason they are not in the regression."""
    reasons = list(final_reason)
    for idx, why in design.excluded.items():
        if reasons[idx] is None:
            reasons[idx] = why
    counts = Counter(str(r) for r in reasons if r is not None)
    return dict(counts)


def measure_pit_loss(snapshot: RaceSnapshot, fit: LinearPaceFit) -> PitLossEstimate:
    """Median and 10-90% range of the green-flag pit loss over the stops visible in `snapshot`.

    loss = (in-lap + out-lap time) - (the fit's clean prediction for the same two laps). Stops where
    either lap ran under a safety car, VSC or red flag are counted in `n_slow_excluded`; stops with
    missing data in `n_unusable`. With no usable stop, or an unidentified fit, the documented
    default is returned with `is_default` True.
    """
    default = PitLossEstimate(
        DEFAULT_PIT_LOSS_S, DEFAULT_PIT_LOSS_S, DEFAULT_PIT_LOSS_S, 0, 0, 0, True
    )
    if not fit.is_identified or snapshot.pit_events.empty or snapshot.laps.empty:
        return default
    lap_rows: dict[tuple[int, int], _LapRow] = {}
    lp = snapshot.laps
    for number, lap_no, time_s, age, comp, status in zip(
        lp["driver_number"].astype(int).to_numpy(),
        lp["lap_number"].astype(int).to_numpy(),
        lp["lap_time_s"].astype("Float64").to_numpy(dtype=np.float64, na_value=np.nan),
        lp["tyre_life"].astype("Float64").to_numpy(dtype=np.float64, na_value=np.nan),
        lp["compound"].astype("object"),
        lp["track_status"].astype("object"),
        strict=True,
    ):
        name = str(comp).upper() if isinstance(comp, str) else ""
        lap_rows[(int(number), int(lap_no))] = _LapRow(
            float(time_s), float(age), name, slow_status(status)
        )
    fitted = set(fit.fitted_compounds)
    losses: list[float] = []
    n_slow = 0
    n_unusable = 0
    events = zip(
        snapshot.pit_events["driver_number"].astype(int).to_numpy(),
        snapshot.pit_events["in_lap"].astype(int).to_numpy(),
        snapshot.pit_events["out_lap"].astype(int).to_numpy(),
        strict=True,
    )
    for number_e, in_e, out_e in events:
        number, in_lap, out_lap = int(number_e), int(in_e), int(out_e)
        a = lap_rows.get((number, in_lap))
        b = lap_rows.get((number, out_lap))
        if a is None or b is None:
            n_unusable += 1
            continue
        if a.slow or b.slow:
            n_slow += 1
            continue
        if (
            a.compound not in fitted
            or b.compound not in fitted
            or any(np.isnan(v) for v in (a.time_s, b.time_s, a.age, b.age))
            or fit.pace_offset(number) is None
        ):
            n_unusable += 1
            continue
        predicted = 0.0
        for row, lap_no in ((a, in_lap), (b, out_lap)):
            mean, _ = fit.predict(
                driver=np.array([number], dtype=np.int64),
                compound=np.array([row.compound], dtype=np.str_),
                tire_age=np.array([int(row.age)], dtype=np.int64),
                lap=np.array([lap_no], dtype=np.int64),
            )
            predicted += float(mean[0])
        losses.append(a.time_s + b.time_s - predicted)
    if not losses:
        return PitLossEstimate(
            DEFAULT_PIT_LOSS_S, DEFAULT_PIT_LOSS_S, DEFAULT_PIT_LOSS_S, 0, n_slow, n_unusable, True
        )
    arr = np.array(losses, dtype=np.float64)
    return PitLossEstimate(
        float(np.median(arr)),
        float(np.percentile(arr, 10)),
        float(np.percentile(arr, 90)),
        len(losses),
        n_slow,
        n_unusable,
        False,
    )
