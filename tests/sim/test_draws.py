"""Draw layer: Sobol pairing, antithetic modes, stream layout (DEC-080)."""

import warnings

import numpy as np
import pytest

from f1si.rng import make_rng
from f1si.sim.draws import (
    make_streams,
    normal_block,
    normal_from_uniform,
    sobol_pairs,
    uniform_block,
)


def test_sobol_pairs_shape_antithetic_and_odd() -> None:
    u = sobol_pairs(3, 100, make_rng(1))
    assert u.shape == (100, 3)
    assert (u > 0).all()
    assert (u < 1).all()
    np.testing.assert_allclose(u[:50] + u[50:], 1.0, atol=1e-15)
    odd = sobol_pairs(3, 99, make_rng(1))
    np.testing.assert_array_equal(odd, u[:99])
    np.testing.assert_array_equal(u, sobol_pairs(3, 100, make_rng(1)))
    assert not np.array_equal(u, sobol_pairs(3, 100, make_rng(2)))


@pytest.mark.parametrize("n", [1000, 1024, 25000])
def test_sobol_no_warning(n: int) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        u = sobol_pairs(4, n, make_rng(3))
    assert u.shape == (n, 4)
    if n == 1024:
        assert np.all(np.abs(u.mean(axis=0) - 0.5) < 1e-3)


def test_blocks_by_mode() -> None:
    for mode in ("none", "antithetic", "sobol_antithetic"):
        assert uniform_block(mode, 5, 40, make_rng(4)).shape == (40, 5)
        assert normal_block(mode, 5, 40, make_rng(4)).shape == (40, 5)
    u = uniform_block("none", 3, 40, make_rng(4))
    assert not np.allclose(u[:20] + u[20:], 1.0)
    e = normal_block("none", 3, 40, make_rng(4))
    assert not np.allclose(e[:20], -e[20:])
    ua = uniform_block("antithetic", 3, 40, make_rng(4))
    np.testing.assert_allclose(ua[:20] + ua[20:], 1.0)
    for mode in ("antithetic", "sobol_antithetic"):
        ea = normal_block(mode, 3, 41, make_rng(4))
        np.testing.assert_allclose(ea[:21][:20], -ea[21:41])
    us = uniform_block("sobol_antithetic", 3, 40, make_rng(4))
    np.testing.assert_array_equal(us, sobol_pairs(3, 40, make_rng(4)))
    np.testing.assert_array_equal(
        normal_block("sobol_antithetic", 3, 40, make_rng(4)),
        normal_block("antithetic", 3, 40, make_rng(4)),
    )


def test_validation() -> None:
    with pytest.raises(ValueError, match="bogus"):
        uniform_block("bogus", 2, 4, make_rng(1))
    with pytest.raises(ValueError, match="bogus"):
        normal_block("bogus", 2, 4, make_rng(1))
    with pytest.raises(ValueError, match="got 0"):
        uniform_block("none", 2, 0, make_rng(1))
    with pytest.raises(ValueError, match="got 0"):
        normal_block("none", 0, 4, make_rng(1))
    with pytest.raises(ValueError, match="21201"):
        sobol_pairs(21202, 4, make_rng(1))
    with pytest.raises(ValueError, match="n_laps"):
        make_streams(make_rng(1), 0)


def test_make_streams_crn_layout() -> None:
    a, b = make_rng(7), make_rng(7)
    sa, pa, na = make_streams(a, 5)
    sb, pb, nb = make_streams(b, 5)
    assert len(pa) == 5
    np.testing.assert_array_equal(sa.random(4), sb.random(4))
    np.testing.assert_array_equal(na.random(4), nb.random(4))
    for x, y in zip(pa, pb, strict=True):
        np.testing.assert_array_equal(x.random(4), y.random(4))
    # The parent is untouched apart from the spawn counter.
    np.testing.assert_array_equal(a.random(3), make_rng(7).random(3))
    # Different laps use different streams.
    _, p2, _ = make_streams(make_rng(7), 5)
    assert not np.array_equal(p2[0].random(4), p2[1].random(4))


def test_normal_from_uniform() -> None:
    z = normal_from_uniform(np.array([0.0, 1.0, 0.5]))
    assert np.isfinite(z).all()
    assert z[2] == 0.0
    big = normal_from_uniform(sobol_pairs(1, 4096, make_rng(5)))
    assert abs(float(big.mean())) < 0.02
    assert abs(float(big.std()) - 1.0) < 0.02
