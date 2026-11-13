"""Skip reasons, the 3.0 SD outlier gate and bad inputs (PAC-03, DEC-090, T-04-01, T-04-02)."""

import numpy as np
import pytest

from f1si.pace.kalman import GATE_MIN_USED, GATE_Z, WearFilter, WearPrior

PRIOR = WearPrior(rate_mean=0.07, rate_sd=0.02, fuel_sd=0.02, sigma=0.15)


def _clean(n: int) -> list[float]:
    return [90.0 + 0.07 * k for k in range(n)]


def test_gate_constants() -> None:
    assert GATE_Z == 3.0
    assert GATE_MIN_USED == 3


def test_no_rejection_in_the_first_three_used_laps_even_for_a_huge_lap() -> None:
    filt = WearFilter(PRIOR)
    assert filt.observe(90.0).used
    assert filt.observe(140.0).used  # +50 s on the 2nd used lap
    assert filt.observe(90.2).used
    assert filt.n_gate_rejections == 0


def test_fourth_lap_outlier_is_rejected_with_reason_and_counted() -> None:
    filt = WearFilter(PRIOR)
    for y in _clean(3):
        filt.observe(y)
    mean_before, sd_before, used_before = filt.rate_mean, filt.rate_sd, filt.n_used
    update = filt.observe(90.0 + 0.07 * 3 + 5.0)
    assert not update.used
    assert update.reason == "outlier gate"
    assert update.n_gate_rejections == 1
    assert filt.n_gate_rejections == 1
    assert filt.n_used == used_before
    assert update.innovation is not None
    assert update.innovation_sd is not None
    assert abs(update.innovation) > GATE_Z * update.innovation_sd
    # the rejected lap left the estimate untouched at q = 0
    assert filt.rate_mean == mean_before
    assert filt.rate_sd == sd_before


def test_two_consecutive_outliers_first_rejected_second_accepted() -> None:
    filt = WearFilter(PRIOR)
    for y in _clean(3):
        filt.observe(y)
    first = filt.observe(95.3)
    second = filt.observe(95.4)
    assert not first.used
    assert first.reason == "outlier gate"
    assert second.used
    assert second.reason is None
    assert filt.n_gate_rejections == 1
    assert filt.n_used == 4


def test_a_normal_lap_is_not_rejected() -> None:
    filt = WearFilter(PRIOR)
    for y in _clean(3):
        filt.observe(y)
    assert filt.observe(90.0 + 0.07 * 3 + 0.2).used


@pytest.mark.parametrize("reason", ["lap 1", "pit in", "pit out", "safety car/VSC/red"])
def test_skip_reasons_are_echoed_and_do_not_use_the_lap(reason: str) -> None:
    filt = WearFilter(PRIOR)
    for y in _clean(4):
        filt.observe(y)
    sd, used = filt.rate_sd, filt.n_used
    update = filt.observe(99.0, reason)
    assert update.used is False
    assert update.reason == reason
    assert update.innovation is None
    assert filt.n_used == used
    assert filt.rate_sd == sd  # q = 0: a skipped lap leaves the band unchanged
    assert filt.n_gate_rejections == 0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_lap_times_are_skipped_and_covariance_stays_valid(bad: float) -> None:
    filt = WearFilter(PRIOR)
    for y in _clean(4):
        filt.observe(y)
    update = filt.observe(bad)
    assert update.used is False
    assert update.reason == "non-finite lap time"
    assert np.isfinite(filt._p).all()
    assert np.isfinite(filt._x).all()
    np.testing.assert_allclose(filt._p, filt._p.T, rtol=0, atol=1e-12)
    assert np.linalg.eigvalsh(filt._p).min() > -1e-9
    assert filt.observe(90.0 + 0.07 * 5).used  # the filter keeps working afterwards


def test_non_finite_first_lap_does_not_start_the_filter() -> None:
    filt = WearFilter(PRIOR)
    assert filt.observe(float("nan")).reason == "non-finite lap time"
    assert filt.n_used == 0
    assert np.isfinite(filt._p).all()
    assert filt.observe(90.0).used


def test_missing_lap_time_without_reason_is_skipped() -> None:
    update = WearFilter(PRIOR).observe(None)
    assert not update.used
    assert update.reason is not None


def test_gate_recovers_from_a_step_change() -> None:
    """A real +3 s step: one lap rejected, then the filter takes the new level."""
    filt = WearFilter(PRIOR)
    for y in _clean(5):
        filt.observe(y)
    results = [filt.observe(90.0 + 0.07 * k + 3.0) for k in range(5, 10)]
    assert not results[0].used
    assert all(r.used for r in results[1:2])
    assert filt.n_gate_rejections >= 1
