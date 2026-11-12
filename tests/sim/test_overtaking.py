"""Pass probability: logistic in the pace gap (D-08, DEC-078)."""

import itertools

import numpy as np

from f1si.rng import make_rng
from f1si.sim.constants import SCALE_S, THRESHOLD_S
from f1si.sim.kernel import pass_probability


def _p(delta: float) -> float:
    return float(pass_probability(delta, THRESHOLD_S, SCALE_S))


def test_monotone_and_anchor_values() -> None:
    grid = np.linspace(-3.0, 3.0, 61)
    values = [_p(float(d)) for d in grid]
    assert all(b >= a for a, b in itertools.pairwise(values))
    assert _p(2.0) > 0.99
    assert _p(0.0) < 0.25  # 0.231 with the fixed constants (plan said 0.2)
    assert _p(-2.0) < 0.01
    assert _p(THRESHOLD_S) == 0.5


def test_empirical_pass_frequency_matches() -> None:
    pu = make_rng(11).random(20_000)
    freq = float(np.mean(pu < _p(1.0)))
    assert abs(freq - _p(1.0)) < 0.01
