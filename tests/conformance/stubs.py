"""DELIBERATELY non-conforming test stubs, one defect each; never import from src.

Each stub is a minimal copy of a conforming double with exactly one planted defect. The meta-test
in test_suites.py shows that the matching check function rejects every one of them, and for the
right reason (the assertion message starts with the defect keyword).
"""

from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray

from f1si.interfaces import PitDecision, Plan, SimulationResult
from f1si.state import RaceState
from tests.conformance.registry import ConstantPace, HoldPolicy, NoisySimulator

F64 = NDArray[np.float64]
I64 = NDArray[np.int64]
STR = NDArray[np.str_]


class WrongShapePace(ConstantPace):
    def predict(self, *, driver: I64, compound: STR, tire_age: I64, lap: I64) -> tuple[F64, F64]:
        mean, sd = super().predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)
        return mean[:-1], sd[:-1]


class NanPace(ConstantPace):
    def predict(self, *, driver: I64, compound: STR, tire_age: I64, lap: I64) -> tuple[F64, F64]:
        mean, sd = super().predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)
        mean[0] = np.nan
        return mean, sd


class IntDtypePace(ConstantPace):
    def predict(self, *, driver: I64, compound: STR, tire_age: I64, lap: I64) -> tuple[F64, F64]:
        mean, sd = super().predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)
        return mean.astype(np.int64), sd


class ZeroSdPace(ConstantPace):
    def predict(self, *, driver: I64, compound: STR, tire_age: I64, lap: I64) -> tuple[F64, F64]:
        mean, _ = super().predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)
        return mean, np.zeros_like(mean)


class MutatesInputPace(ConstantPace):
    def predict(self, *, driver: I64, compound: STR, tire_age: I64, lap: I64) -> tuple[F64, F64]:
        driver[0] += 1
        return super().predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)


class NonDeterministicPace(ConstantPace):
    def predict(self, *, driver: I64, compound: STR, tire_age: I64, lap: I64) -> tuple[F64, F64]:
        mean, sd = super().predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)
        return mean + np.random.default_rng().normal(0.0, 0.01, mean.shape), sd


class MissingPredict:
    pass


class MutatesStatePolicy(HoldPolicy):
    def decide(self, state: RaceState, *, driver: str) -> PitDecision:
        object.__setattr__(state, "lap", state.lap + 1)
        return super().decide(state, driver=driver)


class NonDeterministicPolicy(HoldPolicy):
    def decide(self, state: RaceState, *, driver: str) -> PitDecision:
        plan = Plan((), (), 5000.0 + float(np.random.default_rng().normal()))
        return PitDecision(driver, state.lap, False, None, plan, (plan,))


class IllegalCompoundPolicy(HoldPolicy):
    def decide(self, state: RaceState, *, driver: str) -> PitDecision:
        plan = Plan((state.lap,), ("INTERMEDIATE",), 5000.0)
        return PitDecision(driver, state.lap, True, "INTERMEDIATE", plan, (plan,))


class WrongReturnPolicy(HoldPolicy):
    def decide(self, state: RaceState, *, driver: str) -> Any:
        return {"pit_now": False}


class MissingDecide:
    pass


class WrongShapeSim(NoisySimulator):
    def simulate(
        self,
        state: RaceState,
        *,
        n_races: int,
        rng: np.random.Generator,
        plans: Mapping[str, Plan] | None = None,
    ) -> SimulationResult:
        res = super().simulate(state, n_races=n_races, rng=rng, plans=plans)
        return SimulationResult(res.finish_positions[:, :-1], res.total_time_s[:, :-1])


class WrongDiagnosticsShapeSim(NoisySimulator):
    def simulate(
        self,
        state: RaceState,
        *,
        n_races: int,
        rng: np.random.Generator,
        plans: Mapping[str, Plan] | None = None,
    ) -> SimulationResult:
        res = super().simulate(state, n_races=n_races, rng=rng, plans=plans)
        mask = np.zeros((n_races - 1, 3), dtype=np.bool_)
        return SimulationResult(res.finish_positions, res.total_time_s, sc_lap_mask=mask)


class NanSim(NoisySimulator):
    def simulate(
        self,
        state: RaceState,
        *,
        n_races: int,
        rng: np.random.Generator,
        plans: Mapping[str, Plan] | None = None,
    ) -> SimulationResult:
        res = super().simulate(state, n_races=n_races, rng=rng, plans=plans)
        total = res.total_time_s.copy()
        total[0, 0] = np.nan
        return SimulationResult(res.finish_positions, total)


class NotPermutationSim(NoisySimulator):
    def simulate(
        self,
        state: RaceState,
        *,
        n_races: int,
        rng: np.random.Generator,
        plans: Mapping[str, Plan] | None = None,
    ) -> SimulationResult:
        res = super().simulate(state, n_races=n_races, rng=rng, plans=plans)
        return SimulationResult(np.ones_like(res.finish_positions), res.total_time_s)


class IgnoresSeedSim(NoisySimulator):
    def simulate(
        self,
        state: RaceState,
        *,
        n_races: int,
        rng: np.random.Generator,
        plans: Mapping[str, Plan] | None = None,
    ) -> SimulationResult:
        return super().simulate(state, n_races=n_races, rng=np.random.default_rng(), plans=plans)


class MissingSimulate:
    pass
