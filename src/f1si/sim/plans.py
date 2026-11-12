"""Per-car pit-plan resolution for the simulator (SIM-01, D-10).

Every simulated car needs a plan: the stop laps and the compound fitted at each stop. The rules,
in order, for car `c`:

1. A plan passed in `forced` for the driver code is used exactly as given ("forced"). Its stop
   laps must lie in `(laps_done, laps_total]`, so a stop cannot sit in the past or beyond the
   flag; an unknown code raises the friendly `state.car` error.
2. Otherwise the best plan of the free-track optimizer, `rank_plans(state, driver=code)[0]`,
   computed once per call ("optimizer").
3. If the optimizer refuses (`PlanRefusedError`: unfitted or unknown tyre, no legal plan, ...) a
   documented fallback is used ("fallback"): one stop near the middle of the remaining laps,

       k = laps_done + round((laps_total - laps_done) / 2),

   onto the first fitted compound (sorted order) the car has not used yet. The stop is legal only
   if both stints keep at least `MIN_STINT_LAPS` laps and the car has stops left
   (`MAX_TOTAL_STOPS - stops_done`); otherwise the plan has no stop. Fallback plans are not
   priced, so `Plan.total_time_s` is 0.0.

Pure function of its arguments: it holds no data accessor and no random numbers.
"""

from collections.abc import Mapping, Sequence

from f1si.interfaces import Plan, PlanSource
from f1si.state import CarState, RaceState
from f1si.strategy.free_track import (
    MAX_TOTAL_STOPS,
    MIN_STINT_LAPS,
    FreeTrackOptimizer,
    PlanRefusedError,
)


def fallback_plan(
    state: RaceState, car: CarState, fitted_compounds: Sequence[str]
) -> tuple[Plan, str]:
    """The documented fallback plan for `car` and a note saying why no stop was legal ("")."""
    done = state.laps_done_of(car)
    last = state.laps_total
    remaining = last - done
    used = {c.upper() for c in car.compounds_used}
    if car.compound is not None:
        used.add(car.compound.upper())
    choices = [c for c in sorted({str(c).upper() for c in fitted_compounds}) if c not in used]
    stop = done + round(remaining / 2)
    legal = (
        bool(choices)
        and car.stops_done < MAX_TOTAL_STOPS
        and stop - done >= MIN_STINT_LAPS
        and last - stop >= MIN_STINT_LAPS
    )
    if legal:
        return Plan((stop,), (choices[0],), 0.0), ""
    return Plan((), (), 0.0), "no legal fallback stop exists, so the car runs to the flag"


def _check_forced(state: RaceState, code: str, plan: Plan) -> None:
    car = state.car(code)
    done = state.laps_done_of(car)
    for lap in plan.stop_laps:
        if lap <= done or lap > state.laps_total:
            raise ValueError(
                f"forced plan for {code} has a stop on lap {lap}; stops must lie in "
                f"{done + 1}..{state.laps_total} (laps already done: {done})"
            )


def resolve_plans(
    state: RaceState,
    forced: Mapping[str, Plan] | None,
    optimizer: FreeTrackOptimizer,
    fitted_compounds: Sequence[str],
) -> tuple[list[Plan], tuple[PlanSource, ...]]:
    """One `Plan` and one `PlanSource` per car of `state`, in `state.cars` order.

    Raises:
        ValueError: for an unknown driver code in `forced` or a forced stop lap outside
            `(laps_done, laps_total]`.
    """
    forced = {} if forced is None else forced
    for code, plan in forced.items():
        _check_forced(state, code, plan)
    plans: list[Plan] = []
    sources: list[PlanSource] = []
    for car in state.cars:
        code = car.driver
        if code in forced:
            plans.append(forced[code])
            sources.append(PlanSource(code, "forced", ""))
            continue
        try:
            plans.append(optimizer.rank_plans(state, driver=code)[0])
            sources.append(PlanSource(code, "optimizer", ""))
        except PlanRefusedError as err:
            plan, note = fallback_plan(state, car, fitted_compounds)
            reason = f"optimizer refused: {err}" + (f" ({note})" if note else "")
            plans.append(plan)
            sources.append(PlanSource(code, "fallback", reason))
    return plans, tuple(sources)
