"""The wear band narrows on measured laps, holds on skipped ones, q widens it (PAC-03, DEC-089)."""

import itertools

import numpy as np
import pytest

from f1si.pace.kalman import WearFilter, WearPrior
from f1si.pace.linear import CI_Z

PRIOR = WearPrior(rate_mean=0.07, rate_sd=0.02, fuel_sd=0.02, sigma=0.15)


def _laps(n: int, seed: int = 3) -> list[float]:
    rng = np.random.default_rng(seed)
    # noise clipped at 2 SD so the outlier gate (tested in test_kalman_gate.py) stays out of play
    noise = np.clip(rng.normal(0.0, 0.15, size=n), -0.3, 0.3)
    return [float(90.0 + 0.07 * k + noise[k]) for k in range(n)]


def test_rate_sd_never_increases_on_a_measured_lap() -> None:
    filt = WearFilter(PRIOR)
    sds = [filt.rate_sd]
    for y in _laps(25):
        update = filt.observe(y)
        assert update.used
        sds.append(update.rate_sd)
    assert all(b <= a + 1e-15 for a, b in itertools.pairwise(sds))
    assert sds[-1] < sds[0]
    assert sds[2] < sds[1]  # the second measured lap is the first to carry slope information


def test_rate_sd_is_exactly_unchanged_on_a_skipped_lap() -> None:
    filt = WearFilter(PRIOR)
    for y in _laps(5):
        filt.observe(y)
    before = filt.rate_sd
    update = filt.observe(95.0, "pit in")
    assert not update.used
    assert update.rate_sd == before
    assert filt.rate_sd == before
    assert filt.observe(None, "safety car/VSC/red").rate_sd == before


def test_interval_half_width_is_ci_z_times_sd() -> None:
    filt = WearFilter(PRIOR)
    for y in _laps(6):
        update = filt.observe(y)
    assert update.rate_hi - update.rate_lo == pytest.approx(2 * CI_Z * update.rate_sd)
    assert (update.rate_lo + update.rate_hi) / 2 == pytest.approx(update.rate_mean)


def test_positive_q_widens_the_band_and_stops_it_shrinking() -> None:
    q0 = WearFilter(PRIOR)
    q1 = WearFilter(WearPrior(0.07, 0.02, 0.02, 0.15, q=0.01))
    sd_q0, sd_q1 = [], []
    for y in _laps(60):
        sd_q0.append(q0.observe(y).rate_sd)
        sd_q1.append(q1.observe(y).rate_sd)
    assert sd_q1[9] > sd_q0[9]
    assert sd_q1[59] > sd_q0[59]
    # q > 0 settles at a floor set by q, while q = 0 keeps shrinking toward its own floor
    assert sd_q1[59] == pytest.approx(sd_q1[39], rel=0.05)
    assert sd_q1[59] > 0.5 * 0.01


def test_a_skipped_lap_widens_the_band_when_q_is_positive() -> None:
    filt = WearFilter(WearPrior(0.07, 0.02, 0.02, 0.15, q=0.01))
    for y in _laps(5):
        filt.observe(y)
    before = filt.rate_sd
    assert filt.observe(None, "pit out").rate_sd > before


def test_measurement_changes_the_mean_toward_the_data() -> None:
    filt = WearFilter(PRIOR)
    for k in range(10):
        filt.observe(90.0 + 0.15 * k)
    assert filt.rate_mean > PRIOR.rate_mean
    assert filt.rate_mean < 0.15
