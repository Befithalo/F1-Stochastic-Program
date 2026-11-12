"""SIM-02 benchmark: 50,000 races of a full 57-lap, 20-car state in under 10 s (D-18).

Numba compile time is excluded by a warm-up call: `cache=True` makes the first CI run compile
(about 1 s) and later runs load the cache, and the warm-up makes both cases equal. The test stays
in the default selection (no marker, no skip) because the CI gate is what makes SIM-02 count.
"""

import time

import numpy as np
import pytest

from f1si.interfaces import SimulationResult
from f1si.pace.linear import LinearPaceFit
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import RaceState

N_RACES = 50_000
BUDGET_S = 10.0
RATE = 0.01
LAPS = 57


@pytest.fixture(scope="module")
def timed(long_lap0: tuple[RaceState, LinearPaceFit]) -> tuple[SimulationResult, float]:
    state, fit = long_lap0
    sim = NumpySimulator(
        fit,
        sc=SafetyCarModel(RATE, 4),
        compounds=fit.fitted_compounds,
        wear_sd_by_compound={c: fit.wear_se(c) for c in fit.fitted_compounds},
        record_clocks=False,
    )
    sim.simulate(state, n_races=64, rng=make_rng(0))  # warm-up: JIT compile excluded
    start = time.perf_counter()
    result = sim.simulate(state, n_races=N_RACES, rng=make_rng(1))
    elapsed = time.perf_counter() - start
    print(f"\n50,000 races x 20 cars x 57 laps: {elapsed:.3f} s")
    return result, elapsed


def test_50k_races_under_10_seconds(timed: tuple[SimulationResult, float]) -> None:
    result, elapsed = timed
    assert result.finish_positions.shape == (N_RACES, 20)
    assert result.total_time_s.shape == (N_RACES, 20)
    assert elapsed < BUDGET_S, f"50,000 races took {elapsed:.2f} s (budget {BUDGET_S} s)"


def test_result_memory_is_modest(timed: tuple[SimulationResult, float]) -> None:
    result, _ = timed
    assert result.finish_positions.nbytes + result.total_time_s.nbytes < 40_000_000
    assert result.clock_s is None


def test_result_is_valid(timed: tuple[SimulationResult, float]) -> None:
    result, _ = timed
    assert (np.sort(result.finish_positions, axis=1) == np.arange(1, 21)).all()
    mask = result.sc_lap_mask
    assert mask is not None
    share = float(mask.any(axis=1).mean())
    # P(at least one SC) depends only on the green laps before the first one, so the duration
    # does not change it: exactly 1 - (1 - RATE) ** LAPS (SE about 0.002 at 50,000 races)
    assert 0.2 < share < 0.5
    assert abs(share - (1 - (1 - RATE) ** LAPS)) < 0.03
