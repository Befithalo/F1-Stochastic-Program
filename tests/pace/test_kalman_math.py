"""Kalman wear filter equals closed-form Bayesian regression at q = 0 (PAC-03, DEC-088)."""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from f1si.pace.kalman import DIFFUSE_LEVEL_SD, WearFilter, WearPrior, posterior_rate_sd


def regression_oracle(
    prior: WearPrior, y: list[float], offsets: list[int]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Posterior mean and covariance of [level, rate, fuel_dev] at the last offset.

    Bayesian linear regression y_d = level_0 + (rate + fuel_dev) d with the same Gaussian priors
    as the filter (level prior mean = first y, SD DIFFUSE_LEVEL_SD), moved to the level at the
    last lap by the linear map T.
    """
    x = np.array([[1.0, d, d] for d in offsets])
    prior_prec = np.diag([1 / DIFFUSE_LEVEL_SD**2, 1 / prior.rate_sd**2, 1 / prior.fuel_sd**2])
    prior_mean = np.array([y[0], prior.rate_mean, 0.0])
    prec = prior_prec + x.T @ x / prior.sigma**2
    rhs = prior_prec @ prior_mean + x.T @ np.array(y) / prior.sigma**2
    cov0 = np.linalg.inv(prec)
    mean0 = cov0 @ rhs
    d_last = float(offsets[-1])
    t = np.array([[1.0, d_last, d_last], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    return t @ mean0, t @ cov0 @ t.T


def _run(prior: WearPrior, y: list[float]) -> WearFilter:
    filt = WearFilter(prior)
    for value in y:
        filt.observe(value)
    return filt


def test_filter_equals_bayesian_regression_for_random_priors() -> None:
    rng = np.random.default_rng(20261113)
    for _ in range(60):
        prior = WearPrior(
            rate_mean=float(rng.uniform(0.02, 0.15)),
            rate_sd=float(rng.uniform(0.005, 0.06)),
            fuel_sd=float(rng.uniform(0.005, 0.05)),
            sigma=float(rng.uniform(0.05, 0.5)),
        )
        n = int(rng.integers(2, 13))
        # honest model data with noise clipped at 2 SD, so the outlier gate never rejects a lap
        noise = np.clip(rng.normal(0.0, prior.sigma, size=n), -2 * prior.sigma, 2 * prior.sigma)
        y = [float(90.0 + 0.08 * d + noise[d]) for d in range(n)]
        filt = _run(prior, y)
        assert filt.n_gate_rejections == 0
        mean, cov = regression_oracle(prior, y, list(range(n)))
        np.testing.assert_allclose(filt._x, mean, rtol=1e-9, atol=1e-10)
        np.testing.assert_allclose(filt._p, cov, rtol=1e-9, atol=1e-10)
        assert filt.n_used == n


@pytest.mark.parametrize(
    ("tau", "expected"), [(0.01, 0.0094), (0.02, 0.0163), (0.03, 0.0206), (0.05, 0.0247)]
)
def test_closed_form_matches_research_table_without_fuel_error(tau: float, expected: float) -> None:
    assert posterior_rate_sd(tau, 0.15, 0.0, 7) == pytest.approx(expected, abs=5e-5)


def test_filter_rate_sd_matches_closed_form_with_fuel_error() -> None:
    prior = WearPrior(rate_mean=0.07, rate_sd=0.02, fuel_sd=0.02, sigma=0.15)
    filt = _run(prior, [90.0 + 0.07 * k for k in range(7)])
    closed = posterior_rate_sd(0.02, 0.15, 0.02, 7)
    assert closed == pytest.approx(0.0173, abs=5e-5)
    assert filt.rate_sd == pytest.approx(closed, abs=1e-9)


@pytest.mark.parametrize(
    ("tau", "sigma", "fuel_sd"), [(0.01, 0.15, 0.0), (0.03, 0.28, 0.01), (0.05, 0.48, 0.02)]
)
def test_filter_rate_sd_matches_closed_form_over_cells(
    tau: float, sigma: float, fuel_sd: float
) -> None:
    # fuel_sd = 0 would make the prior precision infinite in the oracle, so the filter alone is used
    prior = WearPrior(rate_mean=0.07, rate_sd=tau, fuel_sd=fuel_sd, sigma=sigma)
    filt = _run(prior, [90.0 + 0.05 * k for k in range(7)])
    assert filt.rate_sd == pytest.approx(posterior_rate_sd(tau, sigma, fuel_sd, 7), abs=1e-9)


def test_band_approaches_the_fuel_floor() -> None:
    tau, fuel_sd = 0.02, 0.02
    floor = tau * fuel_sd / math.sqrt(tau**2 + fuel_sd**2)
    assert posterior_rate_sd(tau, 0.15, fuel_sd, 400) == pytest.approx(floor, rel=1e-3)
    assert posterior_rate_sd(tau, 0.15, fuel_sd, 400) > floor


def test_one_measured_lap_carries_no_slope_information() -> None:
    assert posterior_rate_sd(0.02, 0.15, 0.02, 1) == 0.02


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rate_sd": 0.0},
        {"rate_sd": -0.01},
        {"sigma": 0.0},
        {"sigma": -1.0},
        {"fuel_sd": -0.01},
        {"q": -0.1},
        {"rate_mean": float("nan")},
        {"rate_sd": float("inf")},
        {"sigma": float("nan")},
        {"fuel_sd": float("inf")},
        {"q": float("nan")},
    ],
)
def test_invalid_priors_raise_value_error(kwargs: dict[str, float]) -> None:
    base = {"rate_mean": 0.07, "rate_sd": 0.02, "fuel_sd": 0.02, "sigma": 0.15, "q": 0.0}
    with pytest.raises(ValueError, match="must be"):
        WearPrior(**{**base, **kwargs})


def test_closed_form_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="need tau"):
        posterior_rate_sd(0.0, 0.15, 0.02, 7)
    with pytest.raises(ValueError, match="finite"):
        posterior_rate_sd(0.02, float("nan"), 0.02, 7)
    with pytest.raises(ValueError, match="n_measured"):
        posterior_rate_sd(0.02, 0.15, 0.02, 0)
