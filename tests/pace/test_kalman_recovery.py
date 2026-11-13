"""Synthetic recovery of the wear filter: calibration, optimal accuracy (PAC-04, D-11, D-12, D-17).

Scenario. For each compound c (SOFT 0.12, MEDIUM 0.07, HARD 0.04 s/lap) the true wear rate of
every stint is drawn from the exact prior the filter uses, N(mu_c, tau_c^2) with tau_c = 0.5 mu_c
(D-12: deliberately wide, so the prior alone misses 10% and the data must do the work). A stint is
8 laps; lap 1 (age 1, the out-lap) is skipped, so stint lap 8 has 7 measured laps. Lap times are

    y_d = level_0 + (rate + fuel_dev) d + noise,   d = 0..6,   noise ~ N(0, 0.15^2),

with level_0 ~ N(95, 1) and fuel_dev = 0 (fuel known, filter fuel SD 1e-6) or fuel_dev ~
N(0, 0.02^2) (fuel from its prior, filter fuel SD 0.02). 2,000 stints per compound.

What is gated. (1) Calibration: the 95% interval of the rate covers the truth at every stint lap
and pooled, inside the binomial 99.9% band. The pooled band uses n = number of stints, not number
of intervals: the laps of one stint are positively correlated, a stint's covered fraction has
variance at most 0.95 * 0.05, so the stint count gives a valid (not tightened) band. (2) Optimal
accuracy (D-17): the posterior SD equals the closed form `posterior_rate_sd`; the mean absolute
error matches sqrt(2/pi) times that SD (the mean of |N(0, SD)|) within 4 Monte Carlo standard
errors; the filter equals the regression oracle to 1e-9; the error at stint lap 8 is below the
prior-only error and does not rise from lap to lap.

What is only reported. The owner's 10% accuracy target at stint lap 8 is reported against, never
asserted (D-17): at honest noise it is not attainable, see `test_accuracy_report` and DEC-092.
No seed, noise or prior is chosen to make a gate pass.

The production outlier gate (DEC-090) stays on. It rarely rejects an honest 3 SD lap; exact
comparisons (closed-form SD, oracle) use stints without a rejection, and the share of stints with
a rejection is itself asserted to be small.
"""

from dataclasses import dataclass
from functools import cache
from math import sqrt

import numpy as np
import pytest
from numpy.typing import NDArray
from scipy.stats import binom

from f1si.pace.kalman import WearFilter, WearPrior, posterior_rate_sd
from f1si.rng import make_rng
from tests.pace.test_kalman_math import regression_oracle

BASE_SEED = 20261112
REPORT_TARGET = 0.10  # printed against only, never asserted (D-17)
N_STINTS = 2000
N_LAPS = 8
SIGMA = 0.15
FUEL_SD_KNOWN = 1e-6
FUEL_SD_PRIOR = 0.02
MU = {"SOFT": 0.12, "MEDIUM": 0.07, "HARD": 0.04}
COMPOUNDS = tuple(MU)
MODES = {"fuel known": FUEL_SD_KNOWN, "fuel prior": FUEL_SD_PRIOR}
BAND = 0.999
NOMINAL = 0.95
# one fixed child stream per (compound, mode, purpose), spawned once from the base seed
_CHILDREN = make_rng(BASE_SEED).spawn(len(COMPOUNDS) * len(MODES) * 2)


def _child(compound: str, mode: str, purpose: int) -> np.random.Generator:
    index = (COMPOUNDS.index(compound) * len(MODES) + list(MODES).index(mode)) * 2 + purpose
    return _CHILDREN[index]


@dataclass(frozen=True)
class Sim:
    """Filter output for N stints: shape (n, 8) arrays, column k = stint lap k + 1."""

    compound: str
    mode: str
    tau: float
    sigma: float
    fuel_sd: float
    rate: NDArray[np.float64]
    mean: NDArray[np.float64]
    sd: NDArray[np.float64]
    lo: NDArray[np.float64]
    hi: NDArray[np.float64]
    rejections: NDArray[np.int64]
    y: NDArray[np.float64]
    prior_mean: float


def _simulate(
    compound: str, mode: str, n: int, rng: np.random.Generator, fuel_sd: float | None = None
) -> Sim:
    mu = MU[compound]
    tau = 0.5 * mu
    fs = MODES[mode] if fuel_sd is None else fuel_sd
    rate = rng.normal(mu, tau, size=n)
    fuel_truth = np.zeros(n) if mode == "fuel known" else rng.normal(0.0, FUEL_SD_PRIOR, size=n)
    level0 = rng.normal(95.0, 1.0, size=n)
    noise = rng.normal(0.0, SIGMA, size=(n, N_LAPS - 1))
    d = np.arange(N_LAPS - 1, dtype=np.float64)
    y = level0[:, None] + (rate + fuel_truth)[:, None] * d[None, :] + noise
    prior = WearPrior(rate_mean=mu, rate_sd=tau, fuel_sd=fs, sigma=SIGMA)
    mean = np.empty((n, N_LAPS))
    sd = np.empty((n, N_LAPS))
    lo = np.empty((n, N_LAPS))
    hi = np.empty((n, N_LAPS))
    rejections = np.zeros(n, dtype=np.int64)
    for i in range(n):
        filt = WearFilter(prior)
        updates = [filt.observe(None, "pit out")]
        updates += [filt.observe(float(v)) for v in y[i]]
        for k, u in enumerate(updates):
            mean[i, k], sd[i, k], lo[i, k], hi[i, k] = u.rate_mean, u.rate_sd, u.rate_lo, u.rate_hi
        rejections[i] = filt.n_gate_rejections
    return Sim(compound, mode, tau, SIGMA, fs, rate, mean, sd, lo, hi, rejections, y, mu)


@cache
def _sim(compound: str, mode: str) -> Sim:
    return _simulate(compound, mode, N_STINTS, _child(compound, mode, 0))


def _all_sims() -> list[Sim]:
    return [_sim(c, m) for c in COMPOUNDS for m in MODES]


def _band(n: int) -> tuple[float, float]:
    low, high = binom.interval(BAND, n, NOMINAL)
    return float(low) / n, float(high) / n


def _covered(s: Sim) -> NDArray[np.bool_]:
    out: NDArray[np.bool_] = (s.lo <= s.rate[:, None]) & (s.rate[:, None] <= s.hi)
    return out


def _coverage_gate(mode: str) -> None:
    sims = [_sim(c, mode) for c in COMPOUNDS]
    covered = np.concatenate([_covered(s) for s in sims], axis=0)  # (3 * n, 8)
    n = covered.shape[0]
    low, high = _band(n)
    for lap in range(2, N_LAPS + 1):
        share = float(covered[:, lap - 1].mean())
        assert low <= share <= high, f"{mode}: stint lap {lap} coverage {share:.4f} outside band"
    pooled_low, pooled_high = _band(n)  # stint count, see the module docstring
    pooled = float(covered[:, 1:].mean())
    assert pooled_low <= pooled <= pooled_high, f"{mode}: pooled coverage {pooled:.4f}"
    for s in sims:
        c_low, c_high = _band(len(s.rate))
        share = float(_covered(s)[:, 1:].mean())
        assert c_low <= share <= c_high, f"{mode} {s.compound}: coverage {share:.4f}"


def test_coverage() -> None:
    """Fuel known: 95% interval coverage at every stint lap and pooled is in the 99.9% band."""
    _coverage_gate("fuel known")


def test_coverage_with_fuel_prior() -> None:
    """Fuel from its prior: the RATE interval still covers inside the 99.9% band."""
    _coverage_gate("fuel prior")


def test_band_helper_is_the_binomial_interval() -> None:
    low, high = _band(6000)
    assert low < NOMINAL < high
    assert high - low < 0.02


def test_gate_rejects_few_honest_laps() -> None:
    for s in _all_sims():
        assert float((s.rejections > 0).mean()) < 0.02


def test_posterior_sd_matches_closed_form() -> None:
    """Stint lap 8 filter SD equals the closed form to 1e-9 (stints without a gate rejection)."""
    for s in _all_sims():
        closed = posterior_rate_sd(s.tau, s.sigma, s.fuel_sd, N_LAPS - 1)
        clean = s.rejections == 0
        assert clean.sum() > 0.98 * len(clean)
        np.testing.assert_allclose(s.sd[clean, N_LAPS - 1], closed, rtol=0.0, atol=1e-9)


@pytest.mark.parametrize("compound", COMPOUNDS)
@pytest.mark.parametrize("fuel_sd", [1e-3, FUEL_SD_PRIOR])
def test_filter_equals_regression_oracle(compound: str, fuel_sd: float) -> None:
    """The filter estimate equals the closed-form Bayesian regression to 1e-9 (D-17 (a))."""
    mode = "fuel prior" if fuel_sd == FUEL_SD_PRIOR else "fuel known"
    s = _simulate(compound, mode, 200, _child(compound, mode, 1), fuel_sd=fuel_sd)
    prior = WearPrior(rate_mean=MU[compound], rate_sd=s.tau, fuel_sd=fuel_sd, sigma=SIGMA)
    checked = 0
    for i in range(len(s.rate)):
        if s.rejections[i]:
            continue
        mean, cov = regression_oracle(prior, list(s.y[i]), list(range(N_LAPS - 1)))
        assert s.mean[i, N_LAPS - 1] == pytest.approx(float(mean[1]), abs=1e-9)
        assert s.sd[i, N_LAPS - 1] == pytest.approx(sqrt(float(cov[1, 1])), abs=1e-9)
        checked += 1
    assert checked > 190


def _abs_err(s: Sim, lap: int) -> NDArray[np.float64]:
    """|estimate - truth| at stint lap `lap`; lap 0 is the prior alone."""
    estimate = s.prior_mean if lap == 0 else s.mean[:, lap - 1]
    out: NDArray[np.float64] = np.abs(estimate - s.rate)
    return out


def _mean_se(x: NDArray[np.float64]) -> tuple[float, float]:
    return float(x.mean()), float(x.std(ddof=1) / sqrt(len(x)))


def test_optimal_accuracy() -> None:
    for s in _all_sims():
        tag = f"{s.compound} {s.mode}"
        closed = posterior_rate_sd(s.tau, s.sigma, s.fuel_sd, N_LAPS - 1)
        # (b) Monte Carlo error equals the Bayes-optimal value sqrt(2/pi) * posterior SD
        mae, se = _mean_se(_abs_err(s, N_LAPS))
        expected = sqrt(2.0 / np.pi) * closed
        assert abs(mae - expected) < 4 * se, f"{tag}: MAE {mae:.5f} vs {expected:.5f} (SE {se:.5f})"
        # (c) better than the prior alone, by at least 3 paired standard errors
        gain, gain_se = _mean_se(_abs_err(s, 0) - _abs_err(s, N_LAPS))
        assert gain > 3 * gain_se, f"{tag}: gain {gain:.5f} SE {gain_se:.5f}"
        # (d) the error does not rise from one measured lap to the next
        for lap in range(2, N_LAPS):
            step, step_se = _mean_se(_abs_err(s, lap + 1) - _abs_err(s, lap))
            assert step < 4 * step_se, (
                f"{tag}: lap {lap}->{lap + 1} step {step:.5f} SE {step_se:.5f}"
            )


def test_accuracy_report(capsys: pytest.CaptureFixture[str]) -> None:
    """Print the relative error per compound against the 10% target; assert nothing about it."""
    lines = [
        "",
        "Wear-rate accuracy at stint lap 8 (7 measured laps), sigma 0.15 s, 2,000 stints each",
        "relative error = mean |estimate - truth| / truth over stints with truth > 0.25 * mu",
        f"{'compound':8} {'mode':10} {'prior only':>11} {'lap 8':>8} {'closed form':>12}  verdict",
    ]
    for s in _all_sims():
        keep = s.rate > 0.25 * s.prior_mean
        prior_rel = float((_abs_err(s, 0)[keep] / s.rate[keep]).mean())
        lap8_rel = float((_abs_err(s, N_LAPS)[keep] / s.rate[keep]).mean())
        closed = posterior_rate_sd(s.tau, s.sigma, s.fuel_sd, N_LAPS - 1)
        achievable = sqrt(2.0 / np.pi) * closed / s.prior_mean
        verdict = (
            "target 10%: met"
            if lap8_rel <= REPORT_TARGET
            else "target 10%: not met at honest noise (reported, not gated, D-17)"
        )
        lines.append(
            f"{s.compound:8} {s.mode:10} {prior_rel:11.1%} {lap8_rel:8.1%} {achievable:12.1%}  "
            f"{verdict}"
        )
    lines.append("closed form = sqrt(2/pi) * posterior SD / mu, the best any estimator can reach")
    with capsys.disabled():
        print("\n".join(lines))
