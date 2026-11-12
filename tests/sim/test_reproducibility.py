"""Reproducibility by seed (D-15): the generator is the only source of randomness."""

import numpy as np

from f1si.pace.linear import LinearPaceFit
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import RaceState


def _sim(fit: LinearPaceFit) -> NumpySimulator:
    return NumpySimulator(
        fit,
        sc=SafetyCarModel(0.03, 4),
        compounds=fit.fitted_compounds,
        wear_sd_by_compound={c: fit.wear_se(c) for c in fit.fitted_compounds},
    )


def test_same_seed_is_bit_identical(long_lap0: tuple[RaceState, LinearPaceFit]) -> None:
    state, fit = long_lap0
    before = state.to_json()
    sim = _sim(fit)
    a = sim.simulate(state, n_races=200, rng=make_rng(11))
    b = sim.simulate(state, n_races=200, rng=make_rng(11))
    c = sim.simulate(state, n_races=200, rng=make_rng(12))
    for name in ("finish_positions", "total_time_s", "sc_lap_mask", "stop_laps", "pit_loss_paid_s"):
        assert np.array_equal(getattr(a, name), getattr(b, name)), name
    assert not np.array_equal(a.total_time_s, c.total_time_s)
    assert state.to_json() == before


def test_same_generator_object_gives_fresh_draws(
    long_lap0: tuple[RaceState, LinearPaceFit],
) -> None:
    state, fit = long_lap0
    sim = _sim(fit)
    rng = make_rng(21)
    first = sim.simulate(state, n_races=100, rng=rng)
    second = sim.simulate(state, n_races=100, rng=rng)
    assert not np.array_equal(first.total_time_s, second.total_time_s)
