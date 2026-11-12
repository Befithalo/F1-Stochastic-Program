"""Starting from a real state: catch-up lap, retired cars, borrowed pace."""

from dataclasses import replace

import numpy as np

from f1si.interfaces import Plan
from f1si.pace.linear import LinearPaceFit
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import RaceState

from .conftest import ZeroNoisePace, hand_state, with_car, zero_mean

NO_STOP = Plan((), (), 0.0)


def _zero_sim() -> NumpySimulator:
    return NumpySimulator(ZeroNoisePace(), sc=SafetyCarModel(0.0, 4), compounds=("HARD", "MEDIUM"))


def test_catch_up_lap_hand_sum() -> None:
    gap = 30.0
    state = hand_state(
        2, lap=20, laps_total=30, spacing_s=gap, laps_done=[None, 19], compound="HARD", tire_age=5
    )
    result = _zero_sim().simulate(
        state, n_races=8, rng=make_rng(1), plans={"AAA": NO_STOP, "BBB": NO_STOP}
    )
    # the follower runs laps 20..30; at lap L the tyres have L - 19 more laps than at the cutoff
    hand = sum(zero_mean(2, lap, 5 + (lap - 19)) for lap in range(20, 31))
    np.testing.assert_allclose(result.total_time_s[:, 1] - gap, hand, atol=1e-9)
    leader = zero_mean(1, 20, 5) + sum(zero_mean(1, lap, 5 + (lap - 20)) for lap in range(21, 31))
    np.testing.assert_allclose(result.total_time_s[:, 0], leader, atol=1e-9)


def test_retired_car_finishes_last() -> None:
    state = hand_state(3, lap=10, laps_total=20, spacing_s=5.0, laps_done=[None, 9, 5])
    result = _zero_sim().simulate(state, n_races=16, rng=make_rng(2))
    assert (result.finish_positions[:, 2] == 3).all()
    assert (np.sort(result.finish_positions, axis=1) == np.arange(1, 4)).all()
    assert any("retired or lapped" in line and "CCC" in line for line in result.diagnostics)


def test_unfitted_compound_and_absent_driver_are_borrowed(
    long_lap0: tuple[RaceState, LinearPaceFit],
) -> None:
    state, fit = long_lap0
    state = with_car(state, 0, compound="SOFT", compounds_used=("SOFT",))
    state = with_car(state, 1, driver_number=999)
    sim = NumpySimulator(
        fit,
        sc=SafetyCarModel(0.01, 4),
        compounds=fit.fitted_compounds,
        wear_sd_by_compound={c: fit.wear_se(c) for c in fit.fitted_compounds},
    )
    result = sim.simulate(state, n_races=16, rng=make_rng(3))
    text = "\n".join(result.diagnostics)
    assert "SOFT pace borrowed from HARD, MEDIUM for 1 cars" in text
    assert "driver 999 not in the fit" in text
    assert result.plan_sources[0].source == "fallback"
    assert np.isfinite(result.total_time_s).all()
    assert replace(state, lap=state.lap) == state
