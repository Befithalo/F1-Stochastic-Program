"""Longstaff-Schwartz continuation, current-action ranking, and policy contracts."""

import math

import numpy as np
import pytest

from f1si.interfaces import Plan
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel, _PathCheckpoint
from f1si.state import CarState, RaceState
from f1si.strategy.longstaff import (
    LongstaffSchwartzPolicy,
    _backward_stop,
    _cvar10,
    _fit_continuation,
    _score_option,
)


class FlatPace:
    def predict(self, *, driver, compound, tire_age, lap):
        return np.full(lap.shape, 90.0), np.full(lap.shape, 0.2)


def state(lap: int = 10) -> RaceState:
    cars = tuple(
        CarState(
            driver=code,
            driver_number=i,
            position=i,
            gap_ahead_s=None,
            gap_behind_s=None,
            compound="HARD",
            tire_age=lap,
            wear_rate_s_per_lap=0.05,
            wear_sd=0.01,
            pace_offset_s=0.0,
            stops_done=0,
            compounds_used=("HARD",),
        )
        for i, code in enumerate(("AAA", "BBB"), start=1)
    )
    return RaceState(lap, 16, {"green": 1.0}, {"green": 20.0, "sc": 10.0}, cars)


def test_continuation_regression_recovers_conditional_mean_and_falls_back() -> None:
    x = np.linspace(-1.0, 1.0, 40)[:, None]
    y = 7.0 + 2.5 * x[:, 0]
    predicted = _fit_continuation(x, y)
    np.testing.assert_allclose(predicted, y, atol=1e-10)
    # Fewer observations than basis columns must produce a finite intercept-only estimate.
    fallback = _fit_continuation(np.ones((1, 3)), np.array([4.0]))
    assert np.isfinite(fallback).all()
    np.testing.assert_allclose(fallback, 4.0)


def test_pathwise_stopping_uses_different_cutoff_states() -> None:
    features = np.arange(4.0)[:, None]
    later_policy_values = 1.0 + 2.0 * features[:, 0]
    stopped, decisions = _backward_stop({4: features}, {4: np.full(4, 4.0)}, later_policy_values)
    np.testing.assert_allclose(stopped, [1.0, 3.0, 4.0, 4.0])
    assert decisions[4].tolist() == [False, False, True, True]


def test_branch_paths_share_indexed_draws_and_default_result_shape() -> None:
    race = state()
    simulator = NumpySimulator(FlatPace(), sc=SafetyCarModel(0.2, 3), compounds=("HARD", "MEDIUM"))
    checkpoint = _PathCheckpoint(state=race, lap=race.lap)
    outcomes = simulator._branch_paths(
        checkpoint,
        actions={
            "stop": {"AAA": Plan((11,), ("MEDIUM",), 0.0)},
            "stay": {"AAA": Plan((), (), 0.0)},
        },
        n_races=32,
        rng=np.random.default_rng(13),
        checkpoint_laps=(11,),
        capture_actions=("stay",),
    )
    stopped = outcomes["stop"].result
    stayed = outcomes["stay"].result
    assert stopped.finish_positions.shape == stayed.finish_positions.shape == (32, 2)
    np.testing.assert_array_equal(stopped.sc_lap_mask, stayed.sc_lap_mask)
    assert outcomes["stay"].checkpoints[11].order.shape == (32, 2)
    default_result = simulator.simulate(
        race, n_races=32, rng=np.random.default_rng(13), plans={"AAA": Plan((), (), 0.0)}
    )
    assert default_result.finish_positions.shape == (32, 2)
    assert default_result.clock_s is None


def test_cvar_uses_worst_tail_with_fractional_boundary_mass() -> None:
    assert _cvar10(np.arange(1.0, 11.0)) == pytest.approx(10.0)
    assert _cvar10(np.arange(1.0, 21.0)) == pytest.approx(19.5)


def test_score_blend_endpoints_and_invalid_risk() -> None:
    assert _score_option(np.array([1.0, 2.0, 9.0, 10.0]), 0.0) == pytest.approx(5.5)
    assert _score_option(np.array([1.0, 2.0, 9.0, 10.0]), 1.0) == pytest.approx(10.0)
    for risk in (-0.01, 1.01, math.inf, math.nan):
        with pytest.raises(ValueError, match="risk_aversion"):
            LongstaffSchwartzPolicy(FlatPace(), compounds=("HARD", "MEDIUM"), risk_aversion=risk)


def test_policy_returns_deterministic_decision_without_mutating_state() -> None:
    race = state()
    before = race.to_json()
    policy = LongstaffSchwartzPolicy(
        FlatPace(), compounds=("HARD", "MEDIUM", "SOFT"), n_simulations=16, seed=5
    )
    first = policy.decide(race, driver="AAA")
    second = policy.decide(race, driver="AAA")
    assert first == second
    assert race.to_json() == before
    assert first.lap == race.lap
    assert first.best_plan == first.ranked_plans[0]
    assert len(policy.analyze(race, driver="AAA").options) >= 1


def test_policy_refuses_nonpositive_sample_count_before_simulation() -> None:
    with pytest.raises(ValueError, match="positive"):
        LongstaffSchwartzPolicy(FlatPace(), compounds=("HARD", "MEDIUM"), n_simulations=0)
