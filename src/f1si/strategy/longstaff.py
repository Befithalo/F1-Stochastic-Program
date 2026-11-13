"""Longstaff-Schwartz continuation helpers and CVaR-aware current action ranking.

The recursion fits conditional mean finishing position. CVaR is used only to rank the
current-cutoff option distributions; it is not a dynamically optimal stopping objective.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from f1si.interfaces import DRY_COMPOUNDS, PaceModel, PitDecision, Plan
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel, _PathCheckpoint
from f1si.state import RaceState
from f1si.strategy.free_track import MIN_STINT_LAPS


@dataclass(frozen=True)
class RankedOption:
    """Outcome summary for one legal stop-time action."""

    action: str
    plan: Plan
    mean_finish: float
    spread: float
    cvar10: float
    score: float


@dataclass(frozen=True)
class StrategyAnalysis:
    """Immutable current-cutoff recommendation and the distributions behind it."""

    driver: str
    lap: int
    options: tuple[RankedOption, ...]
    reason: str

    @property
    def best(self) -> RankedOption:
        return self.options[0]


def _cvar10(values: Sequence[float] | NDArray[np.float64]) -> float:
    """Mean of exactly the worst 10% of finishing-position mass (larger is worse)."""
    sample = np.asarray(values, dtype=np.float64)
    if sample.ndim != 1 or sample.size == 0 or not np.isfinite(sample).all():
        raise ValueError("CVaR10 requires a non-empty finite one-dimensional sample")
    ordered = np.sort(sample)[::-1]
    mass = sample.size * 0.1
    whole = math.floor(mass)
    fraction = mass - whole
    total = float(ordered[:whole].sum()) if whole else 0.0
    if fraction > 0.0:
        total += fraction * float(ordered[whole])
    return total / mass


def _fit_continuation(
    features: NDArray[np.float64], realized_values: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Fit a linear conditional-mean basis; use the finite intercept mean when rank is poor."""
    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(realized_values, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.shape[0] or y.size == 0:
        raise ValueError("continuation regression requires aligned feature rows and values")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("continuation regression inputs must be finite")
    design = np.column_stack((np.ones(x.shape[0]), x))
    fallback = np.full(y.shape, float(y.mean()), dtype=np.float64)
    if x.shape[0] < design.shape[1]:
        return fallback
    coefficients, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    if rank != design.shape[1]:
        return fallback
    prediction = design @ coefficients
    return np.asarray(prediction, dtype=np.float64)


def _backward_stop(
    features: Mapping[int, NDArray[np.float64]],
    stop_values: Mapping[int, NDArray[np.float64]],
    terminal_values: NDArray[np.float64],
) -> tuple[NDArray[np.float64], dict[int, NDArray[np.bool_]]]:
    """Apply one-action-per-time pathwise exercise decisions backward."""
    options = {time: {"stop": values} for time, values in stop_values.items()}
    realized, exercised, _ = _backward_stop_options(features, options, terminal_values)
    return realized, exercised


def _backward_stop_options(
    features: Mapping[int, NDArray[np.float64]],
    stop_values: Mapping[int, Mapping[str, NDArray[np.float64]]],
    terminal_values: NDArray[np.float64],
) -> tuple[
    NDArray[np.float64],
    dict[int, NDArray[np.bool_]],
    dict[int, dict[str, NDArray[np.float64]]],
]:
    """Fit continuation means backward and retain each compound's pathwise action value."""
    values = np.asarray(terminal_values, dtype=np.float64).copy()
    decisions: dict[int, NDArray[np.bool_]] = {}
    action_values: dict[int, dict[str, NDArray[np.float64]]] = {}
    for time in sorted(stop_values, reverse=True):
        state = np.asarray(features[time], dtype=np.float64)
        continuation = _fit_continuation(state, values)
        immediate = {
            action: np.asarray(sample, dtype=np.float64)
            for action, sample in stop_values[time].items()
        }
        if not immediate or any(sample.shape != values.shape for sample in immediate.values()):
            raise ValueError("stop and continuation outcomes must be non-empty and path-aligned")
        action_values[time] = {
            action: np.where(sample <= continuation, sample, values)
            for action, sample in immediate.items()
        }
        best_stop = np.minimum.reduce(tuple(immediate.values()))
        exercise = best_stop <= continuation
        values = np.where(exercise, best_stop, values)
        decisions[time] = exercise
    return values, decisions, action_values


def _score_option(values: NDArray[np.float64], risk_aversion: float = 0.5) -> float:
    """Return the locked mean/CVaR blend; lower finishing-position scores are better."""
    risk = _risk(risk_aversion)
    sample = np.asarray(values, dtype=np.float64)
    if sample.ndim != 1 or sample.size == 0 or not np.isfinite(sample).all():
        raise ValueError("option scoring requires a non-empty finite sample")
    return float((1.0 - risk) * sample.mean() + risk * _cvar10(sample))


def _risk(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("risk_aversion must be a finite number in [0, 1]")
    try:
        risk = float(value)
    except (TypeError, ValueError) as err:
        raise ValueError("risk_aversion must be a finite number in [0, 1]") from err
    if not math.isfinite(risk) or not 0.0 <= risk <= 1.0:
        raise ValueError(f"risk_aversion must be finite and in [0, 1], got {value!r}")
    return risk


class LongstaffSchwartzPolicy:
    """Deterministic strategy policy backed by seeded comparable race continuations."""

    def __init__(
        self,
        model: PaceModel,
        *,
        compounds: Sequence[str],
        risk_aversion: float = 0.5,
        n_simulations: int = 512,
        seed: int = 0,
        sc: SafetyCarModel | None = None,
    ) -> None:
        self._risk = _risk(risk_aversion)
        if (
            isinstance(n_simulations, bool)
            or not isinstance(n_simulations, int)
            or n_simulations < 1
        ):
            raise ValueError("n_simulations must be a positive integer")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a non-negative integer")
        self._model = model
        self._compounds = tuple(sorted({str(c).upper() for c in compounds} & set(DRY_COMPOUNDS)))
        if not self._compounds:
            raise ValueError("compounds must include at least one fitted dry compound")
        self._n = n_simulations
        self._seed = seed
        self._sc = sc or SafetyCarModel(0.0, 4)

    def analyze(self, state: RaceState, *, driver: str) -> StrategyAnalysis:
        """Evaluate pit now, delays through five laps, and staying out on matching seeds."""
        _risk(self._risk)
        if self._n < 1:
            raise ValueError("n_simulations must be positive")
        car = state.car(driver)
        if state.laps_total - state.laps_done_of(car) <= 0:
            raise ValueError(f"The race is over for {driver}; choose an earlier cutoff")
        simulator = NumpySimulator(self._model, sc=self._sc, compounds=self._compounds)
        next_lap = state.laps_done_of(car) + 1
        already_used = set(car.compounds_used)
        if car.compound is not None:
            already_used.add(car.compound.upper())
        options = [c for c in self._compounds if len(already_used | {c}) >= 2]
        stop_laps = [
            next_lap + delay
            for delay in range(6)
            if next_lap + delay <= state.laps_total - MIN_STINT_LAPS
        ]
        if car.stops_done >= 2:
            stop_laps = []
        candidates: list[tuple[str, Plan]] = []
        if options:
            for delay, stop_lap in enumerate(stop_laps):
                label = "pit now" if delay == 0 else f"pit in {delay} lap(s)"
                for name in options:
                    action = f"{label} ({name})" if len(options) > 1 else label
                    candidates.append((action, Plan((stop_lap,), (name,), 0.0)))
        stay_out = Plan((), (), 0.0)
        branches = {action: {driver: plan} for action, plan in candidates}
        branches["stay out"] = {driver: stay_out}
        checkpoint = _PathCheckpoint(state=state, lap=state.lap)
        future_stops = sorted(t for t in stop_laps if t > state.lap)
        capture_cutoffs = tuple(t - 1 for t in future_stops if t - 1 > state.lap)
        branched = simulator._branch_paths(
            checkpoint,
            actions=branches,
            n_races=self._n,
            rng=make_rng(self._seed),
            checkpoint_laps=capture_cutoffs,
            capture_actions=("stay out",),
        )
        column = [c.driver for c in state.cars].index(driver)
        stay_values = np.asarray(
            branched["stay out"].result.finish_positions[:, column], dtype=np.float64
        )

        def path_features(cutoff: int) -> NDArray[np.float64]:
            """Small normalized basis from the target's aligned pre-decision path state."""
            if cutoff == state.lap:
                checkpoint_state = None
            else:
                checkpoint_state = branched["stay out"].checkpoints.get(cutoff)
            n = self._n
            if checkpoint_state is None:
                pos = float(car.position or len(state.cars))
                gap = 0.0 if car.gap_ahead_s is None else float(car.gap_ahead_s)
                age = float(car.tire_age)
                stops = float(car.stops_done)
                sc = float(state.regime.get("sc", 0.0) >= 0.5)
                return np.tile(
                    np.asarray(
                        [
                            [
                                pos / len(state.cars),
                                gap / 60.0,
                                age / max(1, state.laps_total),
                                (state.laps_total - cutoff) / state.laps_total,
                                stops / 3.0,
                                sc,
                            ]
                        ]
                    ),
                    (n, 1),
                )
            order = checkpoint_state.order
            ranks = np.empty_like(order)
            place_numbers = np.broadcast_to(np.arange(1, len(state.cars) + 1), order.shape)
            np.put_along_axis(ranks, order, place_numbers, axis=1)
            place = ranks[:, column].astype(np.float64)
            clocks = checkpoint_state.clock
            gap = np.maximum(0.0, clocks[:, column] - clocks.min(axis=1))
            age = checkpoint_state.tire_age[:, column].astype(np.float64)
            stops = checkpoint_state.stops_done[:, column].astype(np.float64)
            remaining = np.full(n, (state.laps_total - cutoff) / state.laps_total)
            sc = (checkpoint_state.safety_car_remaining > 0).astype(np.float64)
            return np.column_stack(
                (
                    place / len(state.cars),
                    gap / 60.0,
                    age / max(1, state.laps_total),
                    remaining,
                    stops / 3.0,
                    sc,
                )
            )

        # Reverse-time Longstaff-Schwartz: each time step regresses aligned later-policy
        # outcomes on that cutoff's pathwise state, then exercises stop-now per scenario.
        feature_by_time = {t: path_features(t - 1) for t in future_stops}
        stop_values_by_time: dict[int, dict[str, NDArray[np.float64]]] = {}
        for stop_lap in future_stops:
            stop_values_by_time[stop_lap] = {
                action: np.asarray(
                    branched[action].result.finish_positions[:, column], dtype=np.float64
                )
                for action, plan in candidates
                if plan.stop_laps == (stop_lap,)
            }
        _, _, value_after_wait = _backward_stop_options(
            feature_by_time, stop_values_by_time, stay_values
        )

        rows: list[RankedOption] = []
        for action, plan in candidates:
            stop_lap = plan.stop_laps[0]
            sample = (
                np.asarray(branched[action].result.finish_positions[:, column], dtype=np.float64)
                if stop_lap <= state.lap
                else value_after_wait[stop_lap][action]
            )
            tail = _cvar10(sample)
            rows.append(
                RankedOption(
                    action,
                    plan,
                    float(sample.mean()),
                    float(sample.std()),
                    tail,
                    _score_option(sample, self._risk),
                )
            )
        stay_plan = stay_out
        tail = _cvar10(stay_values)
        rows.append(
            RankedOption(
                "stay out",
                stay_plan,
                float(stay_values.mean()),
                float(stay_values.std()),
                tail,
                _score_option(stay_values, self._risk),
            )
        )
        if not rows:
            raise ValueError(f"No legal stop timing or stay-out sample is available for {driver}")
        rows.sort(
            key=lambda row: (
                row.score,
                row.mean_finish,
                row.cvar10,
                row.plan.stop_laps[0] if row.plan.stop_laps else math.inf,
                row.plan.compounds[0] if row.plan.compounds else "~",
            )
        )
        best = rows[0]
        reason = (
            f"{best.action.capitalize()} ranks first with blended score {best.score:.3f} "
            f"(mean {best.mean_finish:.2f}, CVaR10 {best.cvar10:.2f})."
        )
        return StrategyAnalysis(driver, state.lap, tuple(rows), reason)

    def decide(self, state: RaceState, *, driver: str) -> PitDecision:
        analysis = self.analyze(state, driver=driver)
        best = analysis.best.plan
        next_lap = state.laps_done_of(state.car(driver)) + 1
        pit_now = bool(best.stop_laps) and best.stop_laps[0] == next_lap
        ranked_plans = tuple(row.plan for row in analysis.options)
        return PitDecision(
            driver=driver,
            lap=state.lap,
            pit_now=pit_now,
            compound=best.compounds[0] if pit_now else None,
            best_plan=best,
            ranked_plans=ranked_plans,
        )
