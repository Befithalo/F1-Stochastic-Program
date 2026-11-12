"""Plug-in contracts: PaceModel, StrategyPolicy, SimulatorBackend (INT-01, INT-02).

Later phases (Monte Carlo, Kalman, Longstaff-Schwartz, Bayesian) are swapped in behind these
three typing Protocols, and a shared test suite (tests/conformance) polices every
implementation.

Lap-time model (D-01)
---------------------
A PaceModel predicts the lap time of driver d on lap L, on compound c, with tire age a::

    t(d, L) = alpha_d + fuel * (L - 1) + wear[c] * a + eps,     eps ~ N(0, sd^2)

where `fuel` (s per lap, negative because the car gets lighter) and `wear[c]` (s per lap of
tyre age) are fitted, and `alpha_d` is the driver offset. The model returns the mean and the
standard deviation of the lap time; it never draws samples (D-09), so the caller owns the
random stream.

Convention: `tire_age` is the number of laps on the tyres at the END of the lap (a fresh set
that has just completed its first lap has age 1), and `lap` is 1-based.

Status: `SimulatorBackend.simulate` and `SimulationResult` are provisional in shape. Phase 3 may
add fields to the result but must not change `finish_positions` and `total_time_s`.

`RaceState` is imported only under `TYPE_CHECKING`, so this module never imports
`f1si.state` at run time and the two can never form an import cycle (DEC-061).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from f1si.state import RaceState

DRY_COMPOUNDS: Final = ("SOFT", "MEDIUM", "HARD")


@dataclass(frozen=True)
class Plan:
    """A pit plan: the in-lap of each stop and the compound fitted at each stop.

    `stop_laps` are strictly increasing lap numbers (>= 1); `compounds[i]` is the compound of the
    new stint after stop i, so both tuples have the same length. `total_time_s` is the plan's
    predicted remaining race time in seconds.

    Raises:
        ValueError: if the stops are not strictly increasing and >= 1, or the lengths differ.
    """

    stop_laps: tuple[int, ...]
    compounds: tuple[str, ...]
    total_time_s: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "stop_laps", tuple(self.stop_laps))
        object.__setattr__(self, "compounds", tuple(self.compounds))
        if len(self.stop_laps) != len(self.compounds):
            raise ValueError(
                f"stop_laps and compounds must have the same length, got "
                f"{len(self.stop_laps)} and {len(self.compounds)}"
            )
        previous = 0
        for lap in self.stop_laps:
            if isinstance(lap, bool) or not isinstance(lap, int):
                raise ValueError(f"stop laps must be ints, got {lap!r}")
            if lap < 1 or lap <= previous:
                raise ValueError(
                    f"stop_laps must be strictly increasing and >= 1, got {self.stop_laps!r}"
                )
            previous = lap

    @property
    def n_stops(self) -> int:
        """Number of pit stops in the plan."""
        return len(self.stop_laps)


@dataclass(frozen=True)
class PitDecision:
    """A policy's answer for one driver at one lap.

    `lap` is the lap of the state the decision was made for. `compound` is the compound to fit
    when `pit_now` is true and None otherwise. `ranked_plans` is best first and
    `best_plan == ranked_plans[0]`.

    Raises:
        ValueError: if `ranked_plans` is empty or does not start with `best_plan`.
    """

    driver: str
    lap: int
    pit_now: bool
    compound: str | None
    best_plan: Plan
    ranked_plans: tuple[Plan, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "ranked_plans", tuple(self.ranked_plans))
        if not self.ranked_plans:
            raise ValueError("ranked_plans must hold at least one plan")
        if self.ranked_plans[0] != self.best_plan:
            raise ValueError("best_plan must equal ranked_plans[0]")


@dataclass(frozen=True, eq=False)
class SimulationResult:
    """Outcome of simulating many race continuations (provisional shape).

    `finish_positions` has shape (n_races, n_cars) and each row is a permutation of 1..n_cars;
    `total_time_s` has the same shape. Column order is `RaceState.cars` order.
    """

    finish_positions: NDArray[np.int64]
    total_time_s: NDArray[np.float64]


@runtime_checkable
class PaceModel(Protocol):
    """Predicts lap-time mean and SD, vectorised over drivers, compounds, ages and laps."""

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Return (mean_s, sd_s), float64 arrays of the same shape as the inputs.

        `driver` is the driver number, `tire_age` the laps on the tyres at the end of the lap and
        `lap` the 1-based lap. The model never samples and never reads the data accessor.
        """
        ...


@runtime_checkable
class StrategyPolicy(Protocol):
    """Decides whether a driver should pit now and ranks complete plans."""

    def decide(self, state: RaceState, *, driver: str) -> PitDecision:
        """Return the decision for the three-letter `driver` code given `state`.

        Deterministic: the contract has no rng. The state is never mutated.
        """
        ...


@runtime_checkable
class SimulatorBackend(Protocol):
    """Simulates race continuations from a state."""

    def simulate(
        self,
        state: RaceState,
        *,
        n_races: int,
        rng: np.random.Generator,
        plans: Mapping[str, Plan] | None = None,
    ) -> SimulationResult:
        """Simulate `n_races` continuations of `state`, optionally forcing `plans` by driver code.

        The same `rng` seed gives the same result. The state is never mutated.
        """
        ...
