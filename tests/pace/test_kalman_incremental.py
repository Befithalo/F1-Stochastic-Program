"""Lap-by-lap filtering equals a batch pass and the regression over used laps (PAC-03, DEC-088)."""

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from f1si.pace.kalman import WearFilter, WearPrior

from .test_kalman_math import regression_oracle

PRIOR = WearPrior(rate_mean=0.07, rate_sd=0.02, fuel_sd=0.02, sigma=0.15)
SETTINGS = settings(max_examples=60, deadline=None, derandomize=True)


@given(st.lists(st.floats(min_value=85.0, max_value=95.0), min_size=2, max_size=14))
@SETTINGS
def test_lap_by_lap_equals_batch_and_is_deterministic(y: list[float]) -> None:
    one = WearFilter(PRIOR)
    for value in y:
        one.observe(value)
    two = WearFilter(PRIOR)
    results = [two.observe(value) for value in y]
    batch = WearFilter(PRIOR)
    list(map(batch.observe, y))
    np.testing.assert_array_equal(one._x, two._x)
    np.testing.assert_array_equal(one._p, two._p)
    np.testing.assert_array_equal(one._x, batch._x)
    np.testing.assert_array_equal(one._p, batch._p)
    assert results[-1].rate_mean == one.rate_mean
    assert results[-1].n_used == one.n_used


@given(
    st.lists(
        st.tuples(st.floats(min_value=85.0, max_value=95.0), st.booleans()),
        min_size=3,
        max_size=14,
    )
)
@SETTINGS
def test_interleaved_skips_equal_regression_over_used_laps(
    laps: list[tuple[float, bool]],
) -> None:
    # the first lap is always used so the stint has a start; gate-free values (all within 10 s)
    laps = [(laps[0][0], True), *laps[1:]]
    # a rejection by the gate would change the used set; keep every used lap in range of the gate
    filt = WearFilter(WearPrior(rate_mean=0.07, rate_sd=0.02, fuel_sd=0.02, sigma=5.0))
    used_y: list[float] = []
    used_d: list[int] = []
    for d, (value, use) in enumerate(laps):
        if use:
            update = filt.observe(value)
            if update.used:
                used_y.append(value)
                used_d.append(d)
        else:
            filt.observe(value, "pit in")
    # skipped trailing laps still advance the state to the last lap
    d_last = len(laps) - 1
    mean, cov = regression_oracle(filt._prior, used_y, [d - used_d[0] for d in used_d])
    # move the oracle's last-used-lap coordinates to the final lap
    shift = d_last - used_d[-1]
    t = np.array([[1.0, shift, shift], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    np.testing.assert_allclose(filt._x, t @ mean, rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(filt._p, t @ cov @ t.T, rtol=1e-8, atol=1e-9)


def test_skipped_laps_before_the_first_usable_lap_do_not_move_the_state() -> None:
    filt = WearFilter(PRIOR)
    before = filt.rate_sd
    update = filt.observe(91.0, "lap 1")
    assert not update.used
    assert update.reason == "lap 1"
    assert filt.rate_sd == before
    assert filt.n_used == 0
    assert filt.snapshot(3).prior_only is True


def test_snapshot_reports_cutoff_and_prior_only_flag() -> None:
    filt = WearFilter(PRIOR)
    for k in range(5):
        filt.observe(90.0 + 0.07 * k)
    snap = filt.snapshot(12)
    assert snap.cutoff_lap == 12
    assert snap.n_used == 5
    assert snap.prior_only is False
    assert snap.rate_mean == filt.rate_mean
    assert snap.rate_sd == filt.rate_sd
