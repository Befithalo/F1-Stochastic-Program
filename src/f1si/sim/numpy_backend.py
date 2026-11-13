"""NumPy/Numba Monte Carlo race simulator: a `SimulatorBackend` for any `RaceState` (SIM-01).

Lap-time model. Per race, car `c` on compound `k` with `a` laps already on the tyres runs a free
lap of

    T = mean_table[c, k, a] + z_off[c] * offset_sd[c]
        + z_wear[k] * wear_sd[k] * (a + 1 - wear_age_off[k])
        + eps * sd_table[c, k, a]

with `mean_table` and `sd_table` from the fitted `PaceModel` (through `BorrowedPace`, evaluated
at the tyre age `a + 1` at the end of the lap), `z_off` one standard normal per car and race (the
pace-offset uncertainty from the Phase 2 standard error), `z_wear` one standard normal per compound
and race shared by all cars (the wear-rate uncertainty), and `eps` a fresh standard normal per car
and lap (lap-to-lap noise with the PaceModel SD). This is the parameter-draw form of D-12 refined
by DEC-077.

Passing. A follower closer than `MIN_GAP_S` to the car ahead passes with probability

    p = logistic((delta - THRESHOLD_S) / SCALE_S),   delta = ahead's free time - follower's,

else it is held at the gap (dirty air). Safety car: it starts on a green lap with probability
`rate_per_lap`, lasts `duration_laps` laps, freezes the order, slows every lap to
`SC_SLOWDOWN` times the leader's time, compresses the field to `RESTART_SPACING_S` on its last
lap and makes a stop cheap (`pit_loss_s["sc"]`). Free-strategy cars (not named in `plans`) take
their next planned stop under an SC that starts within `SC_STOP_WINDOW_LAPS` (D-11). All of this
is in `f1si.sim.kernel`.

Common random numbers. Every draw is indexed by (race, car, lap) and generated unconditionally, in
lap order, from streams spawned from the caller's generator (`f1si.sim.draws.make_streams`), so a
forced plan for one driver cannot move another car's draws.

Sobol dimension budget. One scrambled-Sobol engine of dimension
`n_sim_laps + n_cars + len(DRAW_COMPOUNDS)` (far below SciPy's 21,201 limit) supplies the
safety-car start uniforms (one column per lap), the pace-offset normals and the wear normals. The
wear normals use a fixed slot per canonical compound name (`DRAW_COMPOUNDS`), so the dimension and
every compound's draw are the same whatever plans are forced (DEC-087); a compound outside that
tuple gets no wear draw (zero) and a diagnostics line; one `Sobol(d=n_cars)` engine per lap
supplies the pass
uniforms; lap noise is plain antithetic normals (D-13). Odd `n_races` is padded to an even
antithetic block and trimmed back.

Starting from a real state. Clocks are relative to the leader's line crossing at lap `state.lap`:
the leader holds its predicted lap time, others the cumulative `gap_ahead_s` down the position
order (`START_SPACING_S` where a gap is unknown). Followers one lap behind run a noise-free
catch-up lap first. Cars further behind (retired or lapped) get a lap penalty and are placed last
so the result stays a permutation (D-09).

Filter cars (DEC-094). A car with `wear_source == "filter"` runs its CURRENT tyres on a virtual
compound column appended after the real ones: the mean table gets the incremental correction
`delta * (a + 1 - age0)` (delta = filtered rate minus the table's own age slope, age0 = the age
the kernel starts the car from), the wear SD is the car's own, `wear_age_off` is `age0` so the
wear-rate uncertainty scales with laps run after the cutoff, and the normal comes from one extra
spawned stream (`car_wear_draws`). The real tyre age is kept, so the opportunistic safety-car
rule sees it; after its first stop the car is back on a real compound. With no filter car
nothing here runs and the arrays are exactly the Phase 3 ones.

NOT modelled (D-09): lapping, retirements, virtual safety cars, red flags, reduced tyre wear under
the safety car, first-lap chaos. The simulator sees only a `RaceState`, never the data accessor.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from f1si.interfaces import PaceModel, Plan, SimulationResult
from f1si.sim.borrow import BorrowedPace
from f1si.sim.constants import (
    DRAW_COMPOUNDS,
    MAX_CARS,
    MAX_LAPS,
    MAX_RACES,
    MIN_GAP_S,
    PASS_COST_S,
    RESTART_SPACING_S,
    SC_SLOWDOWN,
    SC_STOP_WINDOW_LAPS,
    SCALE_S,
    START_SPACING_S,
    THRESHOLD_S,
)
from f1si.sim.draws import (
    MODES,
    VarianceReduction,
    car_wear_draws,
    make_streams,
    normal_block,
    normal_from_uniform,
    uniform_block,
)
from f1si.sim.kernel import lap_step
from f1si.sim.plans import resolve_plans
from f1si.state import CarState, RaceState
from f1si.strategy.free_track import MIN_STINT_LAPS, FreeTrackOptimizer

_NO_STOP = 1_000_000


@dataclass(frozen=True)
class SafetyCarModel:
    """Safety-car start chance per green lap and length in laps (REG-01 supplies the numbers)."""

    rate_per_lap: float
    duration_laps: int

    def __post_init__(self) -> None:
        if not (0.0 <= self.rate_per_lap <= 1.0):
            raise ValueError(f"rate_per_lap must be in [0, 1], got {self.rate_per_lap!r}")
        if isinstance(self.duration_laps, bool) or self.duration_laps < 1:
            raise ValueError(f"duration_laps must be at least 1, got {self.duration_laps!r}")


@dataclass(frozen=True)
class _PathCheckpoint:
    """Private batched race-interaction state captured after one simulated lap."""

    state: RaceState
    lap: int
    order: NDArray[np.int64] | None = None
    clock: NDArray[np.float64] | None = None
    tire_age: NDArray[np.int64] | None = None
    compounds: NDArray[np.int64] | None = None
    stops_done: NDArray[np.int64] | None = None
    stop_history: NDArray[np.int64] | None = None
    pit_loss_paid: NDArray[np.float64] | None = None
    safety_car_remaining: NDArray[np.int64] | None = None
    safety_car_fresh: NDArray[np.bool_] | None = None


@dataclass(frozen=True)
class _BranchRun:
    """Terminal outcomes plus aligned internal path states for one branch action."""

    result: SimulationResult
    checkpoints: Mapping[int, _PathCheckpoint]


class NumpySimulator:
    """Monte Carlo simulator of race continuations; satisfies `SimulatorBackend`.

    `model` prices lap times, `compounds` are the fitted dry compounds, `sc` the safety-car model,
    `wear_sd_by_compound` the standard errors of the wear rates (None or a missing compound means
    no wear uncertainty), `fitted_drivers` the driver numbers the fit knows (default: those in
    `model.report.driver_offsets`, else every driver in the state), `variance_reduction` the draw
    mode and `record_clocks` whether to return the per-lap clocks.
    """

    def __init__(
        self,
        model: PaceModel,
        *,
        sc: SafetyCarModel,
        compounds: Sequence[str],
        optimizer: FreeTrackOptimizer | None = None,
        wear_sd_by_compound: Mapping[str, float | None] | None = None,
        fitted_drivers: Sequence[int] | None = None,
        variance_reduction: VarianceReduction = "sobol_antithetic",
        record_clocks: bool = False,
    ) -> None:
        if variance_reduction not in MODES:
            raise ValueError(
                f"variance_reduction must be one of {MODES}, got {variance_reduction!r}"
            )
        self._model = model
        self._sc = sc
        self._compounds = tuple(sorted({str(c).upper() for c in compounds}))
        if not self._compounds:
            raise ValueError("compounds must list at least one fitted compound")
        self._optimizer = optimizer or FreeTrackOptimizer(model, compounds=self._compounds)
        self._wear_sd = (
            None
            if wear_sd_by_compound is None
            else {str(k).upper(): v for k, v in wear_sd_by_compound.items()}
        )
        if fitted_drivers is None:
            report = getattr(model, "report", None)
            offsets = getattr(report, "driver_offsets", None)
            self._drivers: tuple[int, ...] | None = (
                tuple(sorted(int(d) for d in offsets)) if offsets else None
            )
        else:
            self._drivers = tuple(sorted(int(d) for d in fitted_drivers))
        self._mode: VarianceReduction = variance_reduction
        self._record = record_clocks

    # ------------------------------------------------------------------ public API

    def _branch_paths(
        self,
        checkpoint: _PathCheckpoint,
        *,
        actions: Mapping[str, Mapping[str, Plan]],
        n_races: int,
        rng: np.random.Generator,
        checkpoint_laps: Sequence[int] = (),
        capture_actions: Sequence[str] = (),
    ) -> dict[str, _BranchRun]:
        """Replay candidate actions from one checkpoint with identical scenario-indexed draws."""
        if not actions:
            raise ValueError("at least one branch action is required")
        initial = copy.deepcopy(rng.bit_generator.state)
        outputs: dict[str, _BranchRun] = {}
        for name, plans in actions.items():
            bit_generator = type(rng.bit_generator)()
            bit_generator.state = copy.deepcopy(initial)
            result, states = self._simulate(
                checkpoint.state,
                n_races=n_races,
                rng=np.random.Generator(bit_generator),
                plans=plans,
                checkpoint_laps=checkpoint_laps if name in capture_actions else (),
            )
            outputs[name] = _BranchRun(result, states)
        return outputs

    def simulate(
        self,
        state: RaceState,
        *,
        n_races: int,
        rng: np.random.Generator,
        plans: Mapping[str, Plan] | None = None,
    ) -> SimulationResult:
        """Simulate `n_races` continuations of `state` (see the module docstring)."""
        result, _ = self._simulate(state, n_races=n_races, rng=rng, plans=plans, checkpoint_laps=())
        return result

    def _simulate(
        self,
        state: RaceState,
        *,
        n_races: int,
        rng: np.random.Generator,
        plans: Mapping[str, Plan] | None,
        checkpoint_laps: Sequence[int],
    ) -> tuple[SimulationResult, dict[int, _PathCheckpoint]]:
        """Private simulation core; checkpoint copies are produced only for branch callers."""
        self._validate(state, n_races)
        n = int(n_races)
        cars = state.cars
        n_cars = len(cars)
        diagnostics: list[str] = []

        resolved, sources = resolve_plans(state, plans, self._optimizer, self._compounds)
        diagnostics.extend(f"{s.driver}: {s.reason}" for s in sources if s.source == "fallback")

        # compound index
        names: set[str] = set(self._compounds)
        for car, plan in zip(cars, resolved, strict=True):
            if car.compound is not None:
                names.add(car.compound.upper())
            names.update(c.upper() for c in car.compounds_used)
            names.update(c.upper() for c in plan.compounds)
        comp_names = sorted(names)
        index = {name: i for i, name in enumerate(comp_names)}
        n_comp = len(comp_names)

        numbers = np.array([c.driver_number for c in cars], dtype=np.int64)
        drivers = self._drivers if self._drivers is not None else tuple(sorted(numbers.tolist()))
        pace = BorrowedPace(self._model, self._compounds, drivers)

        start_comp = np.zeros(n_cars, dtype=np.int64)
        for i, car in enumerate(cars):
            if car.compound is None:
                start_comp[i] = index[self._compounds[0]]
                diagnostics.append(
                    f"{car.driver}: start tyre unknown, assigned {self._compounds[0]}"
                )
            else:
                start_comp[i] = index[car.compound.upper()]

        # plans -> arrays
        n_slots = max(1, max(p.n_stops for p in resolved))
        stop_lap = np.full((n_cars, n_slots), _NO_STOP, dtype=np.int64)
        next_comp = np.zeros((n_cars, n_slots), dtype=np.int64)
        for i, plan in enumerate(resolved):
            for j, (lap_no, name) in enumerate(zip(plan.stop_laps, plan.compounds, strict=True)):
                stop_lap[i, j] = lap_no
                next_comp[i, j] = index[name.upper()]
        forced = set(plans) if plans else set()
        opportunistic = np.array([c.driver not in forced for c in cars], dtype=np.bool_)

        n_sim = state.laps_total - state.lap
        age0 = np.array([c.tire_age for c in cars], dtype=np.int64)
        max_age = int(age0.max(initial=0)) + n_sim + 2
        laps = np.arange(state.lap + 1, state.laps_total + 1, dtype=np.int64)
        mean_tab, sd_tab = self._tables(pace, numbers, comp_names, laps, max_age)

        off_sd = self._offset_sd(state, drivers, diagnostics)
        wear_sd = self._wear_sd_array(comp_names, diagnostics)

        # start state
        pit_green = float(state.pit_loss_s["green"])
        pit_sc = float(state.pit_loss_s.get("sc", pit_green))
        start = _start(
            state, pace, comp_names, start_comp, stop_lap, next_comp, pit_green, pit_sc, diagnostics
        )

        # borrowed-pace notes
        cars_by_comp: dict[str, int] = {}
        for i in range(n_cars):
            used = {comp_names[start_comp[i]], *(c.upper() for c in resolved[i].compounds)}
            for name in used:
                cars_by_comp[name] = cars_by_comp.get(name, 0) + 1
        absent = [int(x) for x in numbers if int(x) not in set(drivers)]
        diagnostics.extend(pace.describe(cars_by_comp, absent))

        # draws
        d_sc = max(1, n_sim)
        sc_params, passing, noise = make_streams(rng, d_sc)
        n_draw = len(DRAW_COMPOUNDS)
        block = uniform_block(self._mode, n_sim + n_cars + n_draw, n, sc_params)
        u_sc_all = np.ascontiguousarray(block[:, :n_sim])
        z_off = np.ascontiguousarray(normal_from_uniform(block[:, n_sim : n_sim + n_cars]))
        z_slots = normal_from_uniform(block[:, n_sim + n_cars :])
        # wear draws are keyed by compound NAME through the fixed slot layout, so the Sobol
        # dimension and every other compound's column never depend on the plans (DEC-087)
        z_wear = np.zeros((n, n_comp), dtype=np.float64)
        for i, name in enumerate(comp_names):
            if name in DRAW_COMPOUNDS:
                z_wear[:, i] = z_slots[:, DRAW_COMPOUNDS.index(name)]
            else:
                diagnostics.append(
                    f"{name}: not a standard compound, no wear draw (wear SD unused)"
                )
        z_wear = np.ascontiguousarray(z_wear)

        # filter cars (DEC-094): virtual compound columns for the current tyres, own wear draw
        wear_age_off = np.zeros(n_comp, dtype=np.int64)
        start_comp_run = start.comp
        eligible = _filter_eligible(state, start)
        if eligible:
            mean_tab, sd_tab, wear_sd, wear_age_off, virtual = _filter_car_columns(
                mean_tab, sd_tab, wear_sd, cars, eligible, start.comp, start.age
            )
            z_car = car_wear_draws(rng, self._mode, n_cars, n)
            z_wear = np.ascontiguousarray(
                np.concatenate([z_wear, z_car[:, eligible]], axis=1), dtype=np.float64
            )
            start_comp_run = start.comp.copy()
            for i, column in zip(eligible, virtual, strict=True):
                start_comp_run[i] = column
                diagnostics.append(
                    f"{cars[i].driver}: wear from filter (rate {cars[i].wear_rate_s_per_lap:.4f}, "
                    f"SD {cars[i].wear_sd:.4f}), tyre age {int(start.age[i])}"
                )
        n_comp_run = n_comp + len(eligible)

        order = np.ascontiguousarray(np.tile(start.order, (n, 1)))
        clock = np.ascontiguousarray(np.tile(start.clock, (n, 1)))
        age = np.ascontiguousarray(np.tile(start.age, (n, 1)))
        comp = np.ascontiguousarray(np.tile(start_comp_run, (n, 1)))
        stops_done = np.ascontiguousarray(np.tile(start.stops_done, (n, 1)))
        pit_paid = np.ascontiguousarray(np.tile(start.pit_paid, (n, 1)))
        stop_taken = np.full((n, n_cars, n_slots), -1, dtype=np.int64)
        for i in range(n_cars):
            if start.stops_done[i] > 0:
                stop_taken[:, i, 0] = state.lap
        sc_left = np.zeros(n, dtype=np.int64)
        sc_fresh = np.zeros(n, dtype=np.bool_)
        if state.regime.get("sc", 0.0) >= 0.5:
            sc_left[:] = max(1, self._sc.duration_laps - state.sc_laps_elapsed)
            sc_fresh[:] = True
        sc_mask = np.zeros((n, n_sim), dtype=np.bool_)
        checkpoints: dict[int, _PathCheckpoint] = {}
        clocks = np.zeros((n, n_sim, n_cars), dtype=np.float64) if self._record else None
        lap_mask = np.zeros(n, dtype=np.bool_)

        self._check_kernel_inputs(
            mean_tab, stop_lap, next_comp, n_comp_run, n_cars, wear_sd, wear_age_off, z_wear
        )
        for j in range(n_sim):
            pu = uniform_block(self._mode, n_cars, n, passing[j])
            eps = normal_block(self._mode, n_cars, n, noise)
            lap_step(
                int(laps[j]),
                mean_tab[j],
                sd_tab[j],
                np.ascontiguousarray(u_sc_all[:, j]),
                z_off,
                z_wear,
                eps,
                pu,
                off_sd,
                wear_sd,
                wear_age_off,
                stop_lap,
                next_comp,
                opportunistic,
                pit_green,
                pit_sc,
                float(self._sc.rate_per_lap),
                int(self._sc.duration_laps),
                MIN_GAP_S,
                THRESHOLD_S,
                SCALE_S,
                PASS_COST_S,
                SC_SLOWDOWN,
                RESTART_SPACING_S,
                SC_STOP_WINDOW_LAPS,
                MIN_STINT_LAPS,
                order,
                clock,
                age,
                comp,
                stops_done,
                sc_left,
                sc_fresh,
                pit_paid,
                stop_taken,
                lap_mask,
            )
            sc_mask[:, j] = lap_mask
            if clocks is not None:
                clocks[:, j, :] = clock
            lap_no = int(laps[j])
            if lap_no in checkpoint_laps:
                checkpoints[lap_no] = _PathCheckpoint(
                    state=state,
                    lap=lap_no,
                    order=order.copy(),
                    clock=clock.copy(),
                    tire_age=age.copy(),
                    compounds=comp.copy(),
                    stops_done=stops_done.copy(),
                    stop_history=stop_taken.copy(),
                    pit_loss_paid=pit_paid.copy(),
                    safety_car_remaining=sc_left.copy(),
                    safety_car_fresh=sc_fresh.copy(),
                )

        total = np.array(clock, dtype=np.float64)
        # finishing positions come from the running order, which the kernel keeps consistent with
        # the clocks (DEC-086); position p (0 = leader) of `order[r]` is finishing place p + 1
        positions = np.empty_like(order)
        np.put_along_axis(
            positions,
            order,
            np.broadcast_to(np.arange(1, n_cars + 1, dtype=np.int64), order.shape),
            axis=1,
        )
        return (
            SimulationResult(
                finish_positions=positions,
                total_time_s=total,
                sc_lap_mask=sc_mask,
                stop_laps=stop_taken,
                pit_loss_paid_s=pit_paid,
                plan_sources=sources,
                diagnostics=tuple(diagnostics),
                clock_s=clocks,
            ),
            checkpoints,
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _validate(state: RaceState, n_races: int) -> None:
        if isinstance(n_races, bool) or not isinstance(n_races, int | np.integer):
            raise ValueError(f"n_races must be an integer, got {n_races!r}")
        if not (1 <= n_races <= MAX_RACES):
            raise ValueError(f"n_races must be in 1..{MAX_RACES}, got {n_races!r}")
        if len(state.cars) > MAX_CARS:
            raise ValueError(f"at most {MAX_CARS} cars are supported, got {len(state.cars)}")
        if len(state.cars) < 1:
            raise ValueError("the state has no cars")
        if state.laps_total > MAX_LAPS:
            raise ValueError(f"at most {MAX_LAPS} laps are supported, got {state.laps_total}")

    @staticmethod
    def _check_kernel_inputs(
        mean_tab: NDArray[np.float64],
        stop_lap: NDArray[np.int64],
        next_comp: NDArray[np.int64],
        n_comp: int,
        n_cars: int,
        wear_sd: NDArray[np.float64],
        wear_age_off: NDArray[np.int64],
        z_wear: NDArray[np.float64],
    ) -> None:
        """Numba does not bounds-check: validate shapes and index ranges here (T-03-11)."""
        if mean_tab.shape[1:3] != (n_cars, n_comp):
            raise ValueError(f"pace table has shape {mean_tab.shape}, expected cars/compounds")
        if wear_sd.shape != (n_comp,) or wear_age_off.shape != (n_comp,):
            raise ValueError("wear_sd and wear_age_off must both have shape (compounds,)")
        if wear_age_off.dtype != np.int64:
            raise ValueError(f"wear_age_off must be int64, got {wear_age_off.dtype}")
        if z_wear.ndim != 2 or z_wear.shape[1] != n_comp:
            raise ValueError(f"z_wear has shape {z_wear.shape}, expected (races, {n_comp})")
        if stop_lap.shape != next_comp.shape or stop_lap.shape[0] != n_cars:
            raise ValueError("stop_lap and next_comp must both have shape (cars, slots)")
        if next_comp.min() < 0 or next_comp.max() >= n_comp:
            raise ValueError("next_comp holds a compound index outside the compound table")

    def _tables(
        self,
        pace: BorrowedPace,
        numbers: NDArray[np.int64],
        comp_names: list[str],
        laps: NDArray[np.int64],
        max_age: int,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """mean/sd tables of shape (laps, cars, compounds, age rows); row `a` = `a` laps done."""
        shape = (len(laps), len(numbers), len(comp_names), max_age)
        lap_g = np.broadcast_to(laps[:, None, None, None], shape)
        drv_g = np.broadcast_to(numbers[None, :, None, None], shape)
        names = np.array(comp_names, dtype=np.str_)
        comp_g = np.broadcast_to(names[None, None, :, None], shape)
        age_g = np.broadcast_to(
            np.arange(1, max_age + 1, dtype=np.int64)[None, None, None, :], shape
        )
        mean, sd = pace.predict(
            driver=np.ascontiguousarray(drv_g).ravel(),
            compound=np.ascontiguousarray(comp_g).ravel(),
            tire_age=np.ascontiguousarray(age_g).ravel(),
            lap=np.ascontiguousarray(lap_g).ravel(),
        )
        return (
            np.ascontiguousarray(mean.reshape(shape), dtype=np.float64),
            np.ascontiguousarray(sd.reshape(shape), dtype=np.float64),
        )

    def _offset_sd(
        self, state: RaceState, drivers: Sequence[int], diagnostics: list[str]
    ) -> NDArray[np.float64]:
        known = [c.pace_offset_s for c in state.cars if c.pace_offset_s is not None]
        spread = float(np.std(known, ddof=1)) if len(known) >= 2 else 0.0
        out = np.zeros(len(state.cars), dtype=np.float64)
        in_fit = set(drivers)
        for i, car in enumerate(state.cars):
            if car.driver_number not in in_fit:
                out[i] = spread
                diagnostics.append(
                    f"{car.driver}: not in the fit, pace-offset SD set to the field spread "
                    f"{spread:.3f} s"
                )
            elif car.pace_offset_sd is not None:
                out[i] = car.pace_offset_sd
        return out

    def _wear_sd_array(self, comp_names: list[str], diagnostics: list[str]) -> NDArray[np.float64]:
        table = self._wear_sd or {}
        fitted_values = [
            float(v) for k, v in table.items() if k in self._compounds and v is not None
        ]
        out = np.zeros(len(comp_names), dtype=np.float64)
        for i, name in enumerate(comp_names):
            value = table.get(name)
            if value is not None:
                out[i] = float(value)
            elif name not in self._compounds and fitted_values:
                out[i] = max(fitted_values)
                diagnostics.append(f"{name}: wear SD borrowed as the largest fitted value")
            elif self._wear_sd is not None:
                diagnostics.append(f"{name}: no wear SD supplied, wear uncertainty set to 0")
        return out


def _filter_eligible(state: RaceState, start: _Start) -> list[int]:
    """Indices of cars whose current tyres use the filter (DEC-094).

    Needs source "filter", a finite rate, a finite non-negative SD, a known compound and no stop
    on the cutoff lap (`stops_done == 0`); anything else behaves as a fit car. At most one
    virtual column per car, so the extra columns are bounded by `MAX_CARS`.
    """
    out: list[int] = []
    for i, car in enumerate(state.cars):
        rate, sd = car.wear_rate_s_per_lap, car.wear_sd
        if (
            car.wear_source == "filter"
            and car.compound is not None
            and rate is not None
            and sd is not None
            and np.isfinite(rate)
            and np.isfinite(sd)
            and sd >= 0.0
            and start.stops_done[i] == 0
        ):
            out.append(i)
    return out


def _filter_car_columns(
    mean_tab: NDArray[np.float64],
    sd_tab: NDArray[np.float64],
    wear_sd: NDArray[np.float64],
    cars: Sequence[CarState],
    eligible: Sequence[int],
    comp: NDArray[np.int64],
    age: NDArray[np.int64],
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.int64],
    list[int],
]:
    """Append one virtual compound column per filter car (DEC-094).

    For car `i` on real compound `k0` with start age `age0`, the new column copies the `k0`
    columns of every car (all values finite) and, for car `i` only, adds the incremental wear
    correction `delta * (a + 1 - age0)` for table rows `a >= age0`, where `delta` is the filtered
    rate minus the median first difference of the car's own `k0` row over age (the slope the pace
    table really uses, also for borrowed slopes). Returns the extended tables, the extended wear
    SD, `wear_age_off` (0 for real columns, `age0` for the car's virtual one) and the virtual
    column index of each eligible car.
    """
    n_real = mean_tab.shape[2]
    m = len(eligible)
    n_rows = mean_tab.shape[3]
    mean_new = np.zeros((*mean_tab.shape[:2], m, n_rows), dtype=np.float64)
    sd_new = np.zeros((*sd_tab.shape[:2], m, n_rows), dtype=np.float64)
    wear_sd_ext = np.concatenate([wear_sd, np.zeros(m)])
    off = np.zeros(n_real + m, dtype=np.int64)
    columns: list[int] = []
    rows = np.arange(n_rows)
    for j, i in enumerate(eligible):
        k0 = int(comp[i])
        age0 = int(age[i])
        mean_new[:, :, j, :] = mean_tab[:, :, k0, :]
        sd_new[:, :, j, :] = sd_tab[:, :, k0, :]
        rate = cars[i].wear_rate_s_per_lap
        sd = cars[i].wear_sd
        assert rate is not None
        assert sd is not None
        slope = float(np.median(np.diff(mean_tab[0, i, k0, :]))) if n_rows > 1 else 0.0
        delta = rate - slope
        corr = np.where(rows >= age0, delta * (rows + 1 - age0), 0.0)
        mean_new[:, i, j, :] += corr
        wear_sd_ext[n_real + j] = sd
        off[n_real + j] = age0
        columns.append(n_real + j)
    return (
        np.ascontiguousarray(np.concatenate([mean_tab, mean_new], axis=2)),
        np.ascontiguousarray(np.concatenate([sd_tab, sd_new], axis=2)),
        wear_sd_ext,
        off,
        columns,
    )


def _mean_lap(pace: BorrowedPace, car: CarState, compound: str, lap: int, age: int) -> float:
    mean, _ = pace.predict(
        driver=np.array([car.driver_number], dtype=np.int64),
        compound=np.array([compound], dtype=np.str_),
        tire_age=np.array([age], dtype=np.int64),
        lap=np.array([lap], dtype=np.int64),
    )
    return float(mean[0])


@dataclass(frozen=True)
class _Start:
    """Per-car start arrays, in `RaceState.cars` order (`order` lists car indices by position)."""

    order: NDArray[np.int64]
    clock: NDArray[np.float64]
    age: NDArray[np.int64]
    comp: NDArray[np.int64]
    stops_done: NDArray[np.int64]
    pit_paid: NDArray[np.float64]


def _start(
    state: RaceState,
    pace: BorrowedPace,
    comp_names: list[str],
    start_comp: NDArray[np.int64],
    stop_lap: NDArray[np.int64],
    next_comp: NDArray[np.int64],
    pit_green: float,
    pit_sc: float,
    diagnostics: list[str],
) -> _Start:
    """Clocks, order, tyre state and pit losses at the cutoff (module docstring)."""
    cars = state.cars
    n_cars = len(cars)
    lap = state.lap
    rank = sorted(
        range(n_cars),
        key=lambda i: (cars[i].position is None, cars[i].position or 0, cars[i].driver_number),
    )
    cum = np.zeros(n_cars, dtype=np.float64)
    run = 0.0
    for place, i in enumerate(rank):
        if place > 0:
            gap = cars[i].gap_ahead_s
            run += START_SPACING_S if gap is None else gap
        cum[i] = run
    lead = rank[0]
    l_ref = 0.0
    if lap > 0:
        l_ref = _mean_lap(
            pace, cars[lead], comp_names[int(start_comp[lead])], lap, max(1, cars[lead].tire_age)
        )
    sc_active = state.regime.get("sc", 0.0) >= 0.5
    clock = cum.copy()
    age = np.array([c.tire_age for c in cars], dtype=np.int64)
    comp = start_comp.copy()
    stops = np.zeros(n_cars, dtype=np.int64)
    paid = np.zeros(n_cars, dtype=np.float64)
    retired: list[int] = []
    for i, car in enumerate(cars):
        done = state.laps_done_of(car)
        if done >= lap:
            clock[i] += l_ref
            continue
        lag = lap - 1 - done
        if lag > 0:
            clock[i] += lag * l_ref
            retired.append(i)
        if sc_active:
            clock[i] += SC_SLOWDOWN * l_ref
        else:
            clock[i] += _mean_lap(pace, car, comp_names[int(comp[i])], lap, int(age[i]) + 1)
        if stop_lap[i, 0] == lap:
            loss = pit_sc if sc_active else pit_green
            clock[i] += loss
            paid[i] = loss
            comp[i] = next_comp[i, 0]
            age[i] = 0
            stops[i] = 1
        else:
            age[i] += 1
    if retired:
        normal = [clock[i] for i in range(n_cars) if i not in retired]
        floor = max(normal) if normal else float(clock.max())
        for j, i in enumerate(sorted(retired, key=lambda k: clock[k])):
            clock[i] = max(clock[i], floor + START_SPACING_S * (j + 1))
            diagnostics.append(f"driver {cars[i].driver}: retired or lapped, placed last")
    order = np.argsort(clock, kind="stable").astype(np.int64)
    return _Start(order, clock, age, comp, stops, paid)
