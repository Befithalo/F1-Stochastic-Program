"""Conformance suites: one plain-assert check function per Protocol (INT-02, D-11).

Each assertion message starts with a short defect keyword ("shape", "dtype", "finite", ...) so
the meta-tests can show that a planted defect is rejected for the right reason. The functions
never use `pytest.raises`; they either return or raise `AssertionError`.
"""

# ruff: noqa: PT018

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from f1si.interfaces import (
    DRY_COMPOUNDS,
    PaceModel,
    PitDecision,
    SimulationResult,
    SimulatorBackend,
    StrategyPolicy,
)
from f1si.rng import make_rng
from f1si.state import RaceState


@dataclass(frozen=True, eq=False)
class PaceProbe:
    """Valid example inputs for `PaceModel.predict`: four 1-D arrays of equal length >= 8."""

    driver: NDArray[np.int64]
    compound: NDArray[np.str_]
    tire_age: NDArray[np.int64]
    lap: NDArray[np.int64]


@dataclass(frozen=True)
class PolicyCase:
    """A state, a driver code and the compounds that are legal to fit."""

    state: RaceState
    driver: str
    legal_compounds: frozenset[str]


@dataclass(frozen=True)
class SimCase:
    """A state and a small number of races for a simulator check."""

    state: RaceState
    n_races: int = 64


def _predict(model: PaceModel, probe: PaceProbe) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    result = model.predict(
        driver=probe.driver.copy(),
        compound=probe.compound.copy(),
        tire_age=probe.tire_age.copy(),
        lap=probe.lap.copy(),
    )
    assert isinstance(result, tuple) and len(result) == 2, (
        f"return type: predict must return a (mean, sd) tuple, got {type(result).__name__}"
    )
    return result


def check_pace_model(model: object, probe: PaceProbe) -> None:
    """Assert that `model` honours the PaceModel contract on `probe`."""
    assert isinstance(model, PaceModel), "structure: object has no predict method"
    assert len(probe.driver) >= 8, "probe must hold at least 8 entries"
    shape = probe.driver.shape

    driver = probe.driver.copy()
    compound = probe.compound.copy()
    tire_age = probe.tire_age.copy()
    lap = probe.lap.copy()
    result = model.predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)
    assert isinstance(result, tuple) and len(result) == 2, (
        f"return type: predict must return a (mean, sd) tuple, got {type(result).__name__}"
    )
    mean, sd = result
    assert isinstance(mean, np.ndarray) and isinstance(sd, np.ndarray), (
        "return type: mean and sd must be numpy arrays"
    )
    assert mean.shape == shape and sd.shape == shape, (
        f"shape: expected {shape}, got {mean.shape} and {sd.shape}"
    )
    assert mean.dtype == np.float64 and sd.dtype == np.float64, (
        f"dtype: expected float64, got {mean.dtype} and {sd.dtype}"
    )
    assert np.isfinite(mean).all() and np.isfinite(sd).all(), "finite: outputs must be finite"
    assert (sd > 0).all(), "sd: standard deviations must be > 0"
    assert (
        np.array_equal(driver, probe.driver)
        and np.array_equal(compound, probe.compound)
        and np.array_equal(tire_age, probe.tire_age)
        and np.array_equal(lap, probe.lap)
    ), "mutation: predict changed an input array"

    again_mean, again_sd = _predict(model, probe)
    assert np.array_equal(mean, again_mean) and np.array_equal(sd, again_sd), (
        "determinism: the same input gave different outputs"
    )
    for i in range(len(probe.driver)):
        one_mean, one_sd = model.predict(
            driver=probe.driver[i : i + 1].copy(),
            compound=probe.compound[i : i + 1].copy(),
            tire_age=probe.tire_age[i : i + 1].copy(),
            lap=probe.lap[i : i + 1].copy(),
        )
        assert np.allclose(one_mean, mean[i : i + 1], rtol=1e-12, atol=1e-12) and np.allclose(
            one_sd, sd[i : i + 1], rtol=1e-12, atol=1e-12
        ), f"batch: element {i} differs between batch and single-element calls"


def check_strategy_policy(policy: object, case: PolicyCase) -> None:
    """Assert that `policy` honours the StrategyPolicy contract on `case`."""
    assert isinstance(policy, StrategyPolicy), "structure: object has no decide method"
    state = case.state
    before = state.to_json()
    decision = policy.decide(state, driver=case.driver)
    assert isinstance(decision, PitDecision), (
        f"return type: decide must return a PitDecision, got {type(decision).__name__}"
    )
    assert state.to_json() == before and state == RaceState.from_json(before), (
        "mutation: decide changed the input RaceState"
    )
    again = policy.decide(state, driver=case.driver)
    assert decision == again, "determinism: the same state gave different decisions"
    assert decision.driver == case.driver and decision.lap == state.lap, (
        f"driver: decision is for {decision.driver!r} at lap {decision.lap}, "
        f"expected {case.driver!r} at lap {state.lap}"
    )
    legal = case.legal_compounds & set(DRY_COMPOUNDS)
    assert decision.compound is None or decision.compound in legal, (
        f"legal: illegal compound {decision.compound!r}, legal are {sorted(legal)}"
    )
    assert not decision.pit_now or decision.compound is not None, (
        "legal: pit_now requires a compound"
    )
    assert decision.best_plan == decision.ranked_plans[0], "legal: best_plan != ranked_plans[0]"
    for plan in decision.ranked_plans:
        assert all(c in legal for c in plan.compounds), (
            f"legal: plan uses illegal compound in {plan.compounds!r}"
        )


def check_simulator_backend(sim: object, case: SimCase) -> None:
    """Assert that `sim` honours the SimulatorBackend contract on `case`."""
    assert isinstance(sim, SimulatorBackend), "structure: object has no simulate method"
    state = case.state
    n_cars = len(state.cars)
    before = state.to_json()
    result = sim.simulate(state, n_races=case.n_races, rng=make_rng(7))
    assert isinstance(result, SimulationResult), (
        f"return type: simulate must return a SimulationResult, got {type(result).__name__}"
    )
    want = (case.n_races, n_cars)
    pos, tot = result.finish_positions, result.total_time_s
    assert pos.shape == want and tot.shape == want, (
        f"shape: expected {want}, got {pos.shape} and {tot.shape}"
    )
    assert pos.dtype == np.int64 and tot.dtype == np.float64, (
        f"dtype: expected int64 and float64, got {pos.dtype} and {tot.dtype}"
    )
    assert np.isfinite(tot).all(), "finite: total_time_s must be finite"
    expected = np.arange(1, n_cars + 1)
    assert (np.sort(pos, axis=1) == expected).all(), (
        "permutation: each row of finish_positions must be a permutation of 1..n_cars"
    )
    assert state.to_json() == before and state == RaceState.from_json(before), (
        "mutation: simulate changed the input RaceState"
    )
    again = sim.simulate(state, n_races=case.n_races, rng=make_rng(7))
    assert np.array_equal(pos, again.finish_positions) and np.array_equal(
        tot, again.total_time_s
    ), "reproducible: the same seed gave different results"
