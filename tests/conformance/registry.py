"""Registries of implementations under conformance test (D-11, INT-02).

Adding an implementation is one entry in the matching dict. Each factory receives the path of
the long synthetic cache (unused by the doubles; real implementations registered by plans 02-02
and 02-04 use it) and returns the object together with a valid probe or case.

The doubles here are minimal conforming implementations. They must not import
`f1si.data.asof`.
"""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.interfaces import (
    PaceModel,
    PitDecision,
    Plan,
    SimulationResult,
    SimulatorBackend,
    StrategyPolicy,
)
from f1si.pace.linear import fit_linear_pace, measure_pit_loss
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import CarState, RaceState, build_race_state
from f1si.strategy.free_track import FreeTrackOptimizer
from tests.conformance.suites import PaceProbe, PolicyCase, SimCase


def example_state() -> RaceState:
    """A hand-written state: 4 cars, lap 10 of 57."""
    cars = tuple(
        CarState(
            driver=code,
            driver_number=number,
            position=position,
            gap_ahead_s=None if position == 1 else 1.5 * (position - 1),
            gap_behind_s=None if position == 4 else 1.5 * position,
            compound="MEDIUM",
            tire_age=10,
            wear_rate_s_per_lap=0.07,
            wear_sd=0.01,
            pace_offset_s=0.1 * position,
            stops_done=0,
            compounds_used=("MEDIUM",),
        )
        for code, number, position in (
            ("VER", 1, 1),
            ("HAM", 44, 2),
            ("ALO", 14, 3),
            ("LEC", 16, 4),
        )
    )
    return RaceState(
        lap=10,
        laps_total=57,
        regime={"green": 1.0},
        pit_loss_s={"green": 22.0},
        cars=cars,
    )


class ConstantPace:
    """Conforming double: mean 90 + 0.05 * tire_age, SD 0.3."""

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        mean = 90.0 + 0.05 * tire_age.astype(np.float64)
        return mean, np.full(tire_age.shape, 0.3, dtype=np.float64)


class HoldPolicy:
    """Conforming double: never pits."""

    def decide(self, state: RaceState, *, driver: str) -> PitDecision:
        plan = Plan((), (), 5000.0)
        return PitDecision(driver, state.lap, False, None, plan, (plan,))


class NoisySimulator:
    """Conforming double: lap-based total time plus Gaussian noise; positions by rank."""

    def simulate(
        self,
        state: RaceState,
        *,
        n_races: int,
        rng: np.random.Generator,
        plans: Mapping[str, Plan] | None = None,
    ) -> SimulationResult:
        n_cars = len(state.cars)
        remaining = state.laps_total - state.lap
        base = remaining * (90.0 + 0.1 * np.arange(n_cars))
        total = base[None, :] + rng.normal(0.0, 2.0, size=(n_races, n_cars))
        positions = (np.argsort(np.argsort(total, axis=1), axis=1) + 1).astype(np.int64)
        return SimulationResult(finish_positions=positions, total_time_s=total)


def _pace_probe() -> PaceProbe:
    return PaceProbe(
        driver=np.array([1, 44, 14, 16, 1, 44, 14, 16, 1, 44], dtype=np.int64),
        compound=np.array(
            ["SOFT", "MEDIUM", "HARD", "MEDIUM", "SOFT", "HARD", "HARD", "SOFT", "MEDIUM", "HARD"],
            dtype=np.str_,
        ),
        tire_age=np.array([1, 5, 12, 20, 3, 8, 30, 2, 15, 25], dtype=np.int64),
        lap=np.array([2, 6, 13, 21, 4, 9, 31, 3, 16, 26], dtype=np.int64),
    )


def _constant_pace(long_db: Path) -> tuple[PaceModel, PaceProbe]:
    return ConstantPace(), _pace_probe()


def _linear_fit(long_db: Path) -> tuple[PaceModel, PaceProbe]:
    """The joint fuel/wear fit of the long synthetic race at the end of the race."""
    fit = fit_linear_pace(AsOfAccessor(long_db).snapshot(AsOf("2023-01", RACE_END)))
    drivers = sorted(fit.report.driver_offsets)[:4]
    compounds = list(fit.fitted_compounds)
    n = 12
    return fit, PaceProbe(
        driver=np.array([drivers[i % len(drivers)] for i in range(n)], dtype=np.int64),
        compound=np.array([compounds[i % len(compounds)] for i in range(n)], dtype=np.str_),
        tire_age=np.arange(1, n + 1, dtype=np.int64),
        lap=np.arange(2, n + 2, dtype=np.int64),
    )


def _hold_policy(long_db: Path) -> tuple[StrategyPolicy, PolicyCase]:
    case = PolicyCase(example_state(), "ALO", frozenset({"SOFT", "MEDIUM", "HARD"}))
    return HoldPolicy(), case


def _free_track(long_db: Path) -> tuple[StrategyPolicy, PolicyCase]:
    """The brute-force optimizer on the long synthetic race, planned from lap 0."""
    accessor = AsOfAccessor(long_db)
    end = accessor.snapshot(AsOf("2023-01", RACE_END))
    fit = fit_linear_pace(end)
    pit = measure_pit_loss(end, fit)
    state = build_race_state(
        accessor.snapshot(AsOf("2023-01", 0)), fit, laps_total=57, pit_loss_s=pit.median_s
    )
    fitted = frozenset(fit.fitted_compounds)
    driver = next(c.driver for c in state.cars if c.compound in fitted)
    optimizer = FreeTrackOptimizer(fit, compounds=fit.fitted_compounds)
    return optimizer, PolicyCase(state, driver, fitted)


def _noisy_simulator(long_db: Path) -> tuple[SimulatorBackend, SimCase]:
    return NoisySimulator(), SimCase(example_state(), 64)


def _numpy_sim(long_db: Path) -> tuple[SimulatorBackend, SimCase]:
    """The Monte Carlo simulator on the long synthetic race, simulated from lap 0."""
    accessor = AsOfAccessor(long_db)
    end = accessor.snapshot(AsOf("2023-01", RACE_END))
    fit = fit_linear_pace(end)
    pit = measure_pit_loss(end, fit)
    state = build_race_state(
        accessor.snapshot(AsOf("2023-01", 0)), fit, laps_total=57, pit_loss_s=pit.median_s
    )
    sim = NumpySimulator(
        fit,
        sc=SafetyCarModel(0.01, 4),
        compounds=fit.fitted_compounds,
        wear_sd_by_compound={c: fit.wear_se(c) for c in fit.fitted_compounds},
    )
    return sim, SimCase(state, 64)


PACE_MODELS: Final[dict[str, Callable[[Path], tuple[PaceModel, PaceProbe]]]] = {
    "constant_pace": _constant_pace,
    "linear_fit": _linear_fit,
}
POLICIES: Final[dict[str, Callable[[Path], tuple[StrategyPolicy, PolicyCase]]]] = {
    "hold_policy": _hold_policy,
    "free_track": _free_track,
}
SIMULATORS: Final[dict[str, Callable[[Path], tuple[SimulatorBackend, SimCase]]]] = {
    "noisy_simulator": _noisy_simulator,
    "numpy_sim": _numpy_sim,
}
