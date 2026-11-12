"""Free-track pit-plan optimizer: check every legal 1- and 2-stop plan and rank them (PAC-02).

Math
----
State at lap N means the car has completed N laps; a plan covers laps N+1..L (L = laps_total).
A stop at "lap k" means lap k is the in-lap and lap k+1 is the out-lap on fresh tyres with tyre
age 1; "pit now" is k = N+1. The running stint's first priced lap has age ``tire_age + 1``. With a
`PaceModel` giving the mean clean lap time ``t(d, lap, compound, age)``::

    total = sum over laps N+1..L of t(d, lap, compound_in_use, age) + n_new_stops * pit_loss_s

Pit loss already contains the in- and out-lap costs (D-05), so no extra model terms are added for
those laps. Pricing calls ``PaceModel.predict`` and builds prefix sums, so any model plugs in; it
does not use closed-form parameters. A stint of m laps that starts at lap s on compound c costs
``sum_{i=0}^{m-1} t(d, s+i, c, 1+i)``.

"Free track" means no traffic, no overtaking and no safety cars. The result is therefore a lower
bound on race time under the fitted tyre model, not a forecast. Compound pace offsets are not
modeled, so the compound chosen among near-ties is not meaningful (D-19).

Legal plans (D-06): total stops 1 or 2; at least two different dry compounds across the compounds
already used and the plan; the running tyre and its age are fixed; every new stint and the final
stint last at least `min_stint_laps` laps (the running stint is exempt); new compounds come only
from the compounds the model can price; wet and intermediate running is refused.

Ties are broken deterministically (D-11): total time rounded to 1e-9, then fewer new stops, then
earlier stop laps, then compound names. The optimizer is a pure function of the state and the
injected model; it holds no data accessor.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

from f1si.interfaces import DRY_COMPOUNDS, PaceModel, PitDecision, Plan
from f1si.state import CarState, RaceState

MIN_STINT_LAPS: Final = 5
MAX_TOTAL_STOPS: Final = 2


class PlanRefusedError(ValueError):
    """The optimizer will not plan for this driver; the message says why and what to do next."""


def price_plan_slow(
    model: PaceModel,
    state: RaceState,
    driver: str,
    stop_laps: Sequence[int],
    compounds: Sequence[str],
) -> float:
    """Reference price: a plain lap-by-lap loop with one `predict` call per lap (tests only)."""
    car = state.car(driver)
    assert car.compound is not None
    stops = list(stop_laps)
    tyre = [car.compound, *compounds]
    total = 0.0
    stint = 0
    age = car.tire_age
    for lap in range(state.lap + 1, state.laps_total + 1):
        age += 1
        mean, _ = model.predict(
            driver=np.array([car.driver_number], dtype=np.int64),
            compound=np.array([tyre[stint]], dtype=np.str_),
            tire_age=np.array([age], dtype=np.int64),
            lap=np.array([lap], dtype=np.int64),
        )
        total += float(mean[0])
        if stint < len(stops) and lap == stops[stint]:
            stint += 1
            age = 0
            total += state.pit_loss_s["green"]
    return total


class FreeTrackOptimizer:
    """Brute-force 1- and 2-stop optimizer; a `StrategyPolicy` (D-10).

    `compounds` are the dry compounds the model can price. The model is injected at construction
    so `RaceState` needs no per-compound rate map.
    """

    def __init__(
        self,
        model: PaceModel,
        *,
        compounds: Sequence[str],
        min_stint_laps: int = MIN_STINT_LAPS,
    ) -> None:
        if min_stint_laps < 1:
            raise ValueError(f"min_stint_laps must be >= 1, got {min_stint_laps}")
        self._model = model
        self._compounds = tuple(sorted({str(c).upper() for c in compounds}))
        self._min = int(min_stint_laps)

    # ------------------------------------------------------------------ public API

    def decide(self, state: RaceState, *, driver: str) -> PitDecision:
        """Rank every legal plan; pit now iff the best plan stops on lap ``state.lap + 1``."""
        plans = self.rank_plans(state, driver=driver)
        best = plans[0]
        pit_now = bool(best.stop_laps) and best.stop_laps[0] == state.lap + 1
        return PitDecision(
            driver=driver,
            lap=state.lap,
            pit_now=pit_now,
            compound=best.compounds[0] if pit_now else None,
            best_plan=best,
            ranked_plans=plans,
        )

    def rank_plans(self, state: RaceState, *, driver: str) -> tuple[Plan, ...]:
        """Every legal plan for `driver`, best first.

        Raises:
            ValueError: for an unknown driver code (the message lists the valid codes).
            PlanRefusedError: when the driver cannot be planned for (wet tyres, unknown compound,
                race over, no legal plan, driver or compound the model cannot price).
        """
        car = state.car(driver)
        compound = self._check_car(state, car)
        remaining = state.laps_total - state.lap
        try:
            cur, fresh = self._prefix_sums(state, car, compound)
        except ValueError as err:
            raise PlanRefusedError(
                f"The pace model cannot price {driver}: {err}. "
                f"Try: choose another driver with --driver."
            ) from err
        pit = state.pit_loss_s["green"]
        used = set(car.compounds_used) | {compound}
        done = car.stops_done
        n = state.lap
        last = state.laps_total
        rows: list[tuple[float, int, tuple[int, ...], tuple[str, ...]]] = []

        def add(total: float, stops: tuple[int, ...], comps: tuple[str, ...]) -> None:
            rows.append((round(total, 9), len(stops), stops, comps))

        if done >= 1 and len(used) >= 2:
            add(float(cur[remaining]), (), ())
        if done < MAX_TOTAL_STOPS:
            # one more stop
            for k1 in range(n + 1, last - self._min + 1):
                for c1 in self._compounds:
                    if len(used | {c1}) < 2:
                        continue
                    total = cur[k1 - n] + fresh[c1][k1 + 1, last - k1] + pit
                    add(float(total), (k1,), (c1,))
            # two more stops
            if done == 0:
                for k1 in range(n + 1, last - 2 * self._min + 1):
                    k2s = np.arange(k1 + self._min, last - self._min + 1)
                    for c1 in self._compounds:
                        for c2 in self._compounds:
                            if len(used | {c1, c2}) < 2:
                                continue
                            totals = (
                                cur[k1 - n]
                                + fresh[c1][k1 + 1, k2s - k1]
                                + fresh[c2][k2s + 1, last - k2s]
                                + 2 * pit
                            )
                            for k2, total in zip(k2s.tolist(), totals.tolist(), strict=True):
                                add(float(total), (k1, int(k2)), (c1, c2))
        if not rows:
            raise PlanRefusedError(
                f"No legal plan for {driver} after lap {state.lap}: it needs two different dry "
                f"compounds, at most {MAX_TOTAL_STOPS} stops and stints of at least {self._min} "
                f"laps. Try: pick another driver or an earlier lap with --lap."
            )
        rows.sort(key=lambda r: (r[0], r[1], r[2], r[3]))
        return tuple(Plan(stops, comps, total) for total, _, stops, comps in rows)

    def price_plan(
        self,
        state: RaceState,
        *,
        driver: str,
        stop_laps: Sequence[int],
        compounds: Sequence[str],
    ) -> float:
        """Price any plan for `driver` with the same model (legality is not enforced).

        Raises:
            ValueError: if the stop laps are not strictly increasing within the remaining laps, the
                lengths differ, or the model cannot price a compound.
        """
        car = state.car(driver)
        if car.compound is None:
            raise PlanRefusedError(f"The current compound of {driver} is unknown.")
        stops = [int(k) for k in stop_laps]
        if len(stops) != len(compounds):
            raise ValueError("stop_laps and compounds must have the same length")
        prev = state.lap
        for k in stops:
            if k <= prev or k > state.laps_total - 1:
                raise ValueError(
                    f"stop laps must increase and lie in {state.lap + 1}..{state.laps_total - 1}, "
                    f"got {stops!r}"
                )
            prev = k
        tyres = [car.compound, *[str(c).upper() for c in compounds]]
        bounds = [state.lap, *stops, state.laps_total]
        total = 0.0
        for i, tyre in enumerate(tyres):
            first_lap = bounds[i] + 1
            length = bounds[i + 1] - bounds[i]
            first_age = car.tire_age + 1 if i == 0 else 1
            total += self._segment(car.driver_number, tyre, first_lap, first_age, length)
        return total + len(stops) * state.pit_loss_s["green"]

    # ------------------------------------------------------------------ helpers

    def _check_car(self, state: RaceState, car: CarState) -> str:
        if car.compound is None:
            raise PlanRefusedError(
                f"The current tyre of {car.driver} is unknown, so no plan can be priced. "
                f"Try: uv run f1si plan with another --driver."
            )
        names = {car.compound.upper(), *(c.upper() for c in car.compounds_used)}
        wet = sorted(names - set(DRY_COMPOUNDS))
        if wet:
            raise PlanRefusedError(
                f"{car.driver} ran on {', '.join(wet)} tyres; wet and intermediate strategy is "
                "out of scope for the free-track optimizer. Try: plan a driver on dry tyres only."
            )
        if state.laps_total - state.lap <= 0:
            raise PlanRefusedError(
                f"The race is over after lap {state.laps_total}, so there is nothing to plan. "
                "Try: an earlier cutoff with --lap."
            )
        compound = car.compound.upper()
        if compound not in self._compounds:
            raise PlanRefusedError(
                f"No wear rate was fitted for {compound}, the current tyre of {car.driver}. "
                f"Try: another --driver, or a later --lap so more laps are visible."
            )
        return compound

    def _segment(self, number: int, compound: str, first_lap: int, first_age: int, n: int) -> float:
        if n <= 0:
            return 0.0
        laps = np.arange(first_lap, first_lap + n, dtype=np.int64)
        mean, _ = self._model.predict(
            driver=np.full(n, number, dtype=np.int64),
            compound=np.repeat(np.array([compound], dtype=np.str_), n),
            tire_age=np.arange(first_age, first_age + n, dtype=np.int64),
            lap=laps,
        )
        return float(np.sum(mean))

    def _prefix_sums(
        self, state: RaceState, car: CarState, compound: str
    ) -> tuple[NDArray[np.float64], dict[str, NDArray[np.float64]]]:
        """Prefix sums: `cur[j]` for the running stint, `fresh[c][start, m]` for new stints."""
        n, last = state.lap, state.laps_total
        remaining = last - n
        number = car.driver_number
        laps = np.arange(n + 1, last + 1, dtype=np.int64)
        mean, _ = self._model.predict(
            driver=np.full(remaining, number, dtype=np.int64),
            compound=np.repeat(np.array([compound], dtype=np.str_), remaining),
            tire_age=np.arange(car.tire_age + 1, car.tire_age + 1 + remaining, dtype=np.int64),
            lap=laps,
        )
        cur = np.concatenate(([0.0], np.cumsum(mean)))
        starts = np.arange(n + 2, last + 1, dtype=np.int64)
        fresh: dict[str, NDArray[np.float64]] = {}
        for name in self._compounds:
            table = np.zeros((last + 2, remaining + 2), dtype=np.float64)
            if len(starts):
                width = last - int(starts[0]) + 1
                offs = np.arange(width, dtype=np.int64)
                grid_lap = np.minimum(starts[:, None] + offs[None, :], last)
                grid_age = np.broadcast_to(offs[None, :] + 1, grid_lap.shape)
                mean, _ = self._model.predict(
                    driver=np.full(grid_lap.size, number, dtype=np.int64),
                    compound=np.repeat(np.array([name], dtype=np.str_), grid_lap.size),
                    tire_age=np.ascontiguousarray(grid_age).reshape(-1).astype(np.int64),
                    lap=grid_lap.reshape(-1).astype(np.int64),
                )
                grid = mean.reshape(grid_lap.shape)
                valid = (starts[:, None] + offs[None, :]) <= last
                cum = np.cumsum(np.where(valid, grid, 0.0), axis=1)
                table[starts[:, None], offs[None, :] + 1] = cum
            fresh[name] = table
        return cur, fresh
