"""Shared fixtures and helpers for the simulator tests."""

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.pace.linear import LinearPaceFit, fit_linear_pace, measure_pit_loss
from f1si.state import CarState, RaceState, build_race_state

_EXTRA = tuple(f"Z{chr(65 + i // 26)}{chr(65 + i % 26)}" for i in range(64))
CODES = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", *_EXTRA)
PIT = {"green": 22.0, "sc": 11.0}


class ZeroNoisePace:
    """Deterministic pace double: mean 90 + 0.05 * age + 0.01 * lap + 0.1 * (driver % 7), SD 0."""

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        mean = (
            90.0
            + 0.05 * tire_age.astype(np.float64)
            + 0.01 * lap.astype(np.float64)
            + 0.1 * (driver % 7).astype(np.float64)
        )
        return mean, np.zeros(driver.shape, dtype=np.float64)


def zero_mean(number: int, lap: int, age: int) -> float:
    """Hand value of the `ZeroNoisePace` mean for one car-lap."""
    return 90.0 + 0.05 * age + 0.01 * lap + 0.1 * (number % 7)


def hand_state(
    n_cars: int = 2,
    *,
    lap: int = 0,
    laps_total: int = 8,
    spacing_s: float = 60.0,
    laps_done: Sequence[int | None] | None = None,
    compound: str | None = "HARD",
    tire_age: int = 0,
    pit_loss_s: dict[str, float] | None = None,
    regime: dict[str, float] | None = None,
    sc_laps_elapsed: int = 0,
    numbers: Sequence[int] | None = None,
) -> RaceState:
    """A hand-built state of `n_cars` cars spaced `spacing_s` apart, car 0 leading."""
    nums = list(numbers) if numbers is not None else list(range(1, n_cars + 1))
    cars = []
    for i in range(n_cars):
        cars.append(
            CarState(
                driver=CODES[i],
                driver_number=nums[i],
                position=i + 1,
                gap_ahead_s=None if i == 0 else spacing_s,
                gap_behind_s=None if i == n_cars - 1 else spacing_s,
                compound=compound,
                tire_age=tire_age,
                wear_rate_s_per_lap=None,
                wear_sd=None,
                pace_offset_s=0.0,
                stops_done=0,
                compounds_used=() if compound is None else (compound,),
                laps_done=None if laps_done is None else laps_done[i],
                pace_offset_sd=0.0,
            )
        )
    return RaceState(
        lap=lap,
        laps_total=laps_total,
        regime=regime if regime is not None else {"green": 1.0},
        pit_loss_s=pit_loss_s if pit_loss_s is not None else dict(PIT),
        cars=tuple(cars),
        sc_laps_elapsed=sc_laps_elapsed,
    )


def with_car(state: RaceState, index: int, **changes: object) -> RaceState:
    """A copy of `state` with car `index` changed."""
    cars = list(state.cars)
    cars[index] = replace(cars[index], **changes)  # type: ignore[arg-type]
    return replace(state, cars=tuple(cars))


def build_long(db: Path, lap: int) -> tuple[RaceState, LinearPaceFit]:
    """The long synthetic race at `lap`: the state, and the whole-race fit (as in the registry)."""
    accessor = AsOfAccessor(db)
    end = accessor.snapshot(AsOf("2023-01", RACE_END))
    fit = fit_linear_pace(end)
    pit = measure_pit_loss(end, fit)
    state = build_race_state(
        accessor.snapshot(AsOf("2023-01", lap)), fit, laps_total=57, pit_loss_s=pit.median_s
    )
    return state, fit


@pytest.fixture(scope="session")
def long_lap0(long_synthetic_db: Path) -> tuple[RaceState, LinearPaceFit]:
    """Lap-0 state of the long synthetic race with its whole-race fit."""
    return build_long(long_synthetic_db, 0)


@pytest.fixture(scope="session")
def long_lap20(long_synthetic_db: Path) -> tuple[RaceState, LinearPaceFit]:
    """Lap-20 state of the long synthetic race with its whole-race fit."""
    return build_long(long_synthetic_db, 20)
