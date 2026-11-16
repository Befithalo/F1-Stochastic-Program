"""Longstaff-Schwartz continuation helpers and CVaR-aware current action ranking.

The recursion fits conditional mean finishing position. CVaR is used only to rank the
current-cutoff option distributions; it is not a dynamically optimal stopping objective.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

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
    podium_probability: float
    top10_probability: float
    finish_p05: int
    finish_p95: int
    finish_quantiles: tuple[int, ...]


@dataclass(frozen=True)
class StrategyAnalysis:
    """Immutable current-cutoff recommendation and the distributions behind it."""

    driver: str
    lap: int
    options: tuple[RankedOption, ...]
    reason: str
    recommended_position_history: NDArray[np.int64] | None = None
    close_call_places: float | None = None
    close_call_two_se: float | None = None
    waiting_tie_window_laps: tuple[int, int] | None = None
    never_stop_allowed: bool = False

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


def _distribution_summary(
    sample: NDArray[np.float64],
) -> tuple[float, float, int, int]:
    """Summarize podium/top-10 mass and inclusive discrete finish endpoints."""
    podium_probability = float(np.mean(sample <= 3))
    top10_probability = float(np.mean(sample <= 10))
    p05, p95 = np.quantile(sample, [0.05, 0.95], method="inverted_cdf")
    return podium_probability, top10_probability, int(p05), int(p95)


def _midpoint_finish_quantiles(sample: NDArray[np.float64]) -> tuple[int, ...]:
    """Return 100 midpoint inverted-CDF quantiles for integer finishing positions."""
    values = np.asarray(sample, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("finish quantiles require a non-empty finite one-dimensional sample")
    if not np.equal(values, np.floor(values)).all():
        raise ValueError("finish quantiles require integer finishing positions")
    probabilities = (np.arange(100, dtype=np.float64) + 0.5) / 100.0
    points = np.quantile(values, probabilities, method="inverted_cdf")
    return tuple(int(value) for value in points)


def _fit_continuation(
    features: NDArray[np.float64],
    realized_values: NDArray[np.float64],
    *,
    predict_features: NDArray[np.float64] | None = None,
) -> NDArray[np.float64]:
    """Fit a conditional-mean basis and predict on the supplied paths.

    `predict_features` lets the Longstaff policy score paths independent of its regression fit.
    """
    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(realized_values, dtype=np.float64)
    predict_x = x if predict_features is None else np.asarray(predict_features, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.shape[0] or y.size == 0:
        raise ValueError("continuation regression requires aligned feature rows and values")
    if predict_x.ndim != 2 or predict_x.shape[1] != x.shape[1]:
        raise ValueError("continuation prediction features must match the fitted feature columns")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(predict_x).all():
        raise ValueError("continuation regression inputs must be finite")
    design = np.column_stack((np.ones(x.shape[0]), x))
    prediction_design = np.column_stack((np.ones(predict_x.shape[0]), predict_x))
    fallback = np.full(predict_x.shape[0], float(y.mean()), dtype=np.float64)
    if x.shape[0] < design.shape[1]:
        return fallback
    coefficients, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    if rank != design.shape[1]:
        return fallback
    prediction = prediction_design @ coefficients
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
    """Fit action and continuation means backward, then retain pathwise outcomes."""
    values, decisions, action_values, _, _ = _backward_stop_options_with_choices(
        features, stop_values, terminal_values
    )
    return values, decisions, action_values


def _backward_stop_options_with_choices(
    features: Mapping[int, NDArray[np.float64]],
    stop_values: Mapping[int, Mapping[str, NDArray[np.float64]]],
    terminal_values: NDArray[np.float64],
    *,
    force_stop_at_last_time: bool = False,
    fit_features: Mapping[int, NDArray[np.float64]] | None = None,
    fit_stop_values: Mapping[int, Mapping[str, NDArray[np.float64]]] | None = None,
    fit_terminal_values: NDArray[np.float64] | None = None,
) -> tuple[
    NDArray[np.float64],
    dict[int, NDArray[np.bool_]],
    dict[int, dict[str, NDArray[np.float64]]],
    dict[int, dict[str, NDArray[np.str_]]],
    NDArray[np.str_],
]:
    """Return continuation outcomes and the fixed branch chosen on each scenario path."""
    values = np.asarray(terminal_values, dtype=np.float64).copy()
    training_features = features if fit_features is None else fit_features
    training_stops = stop_values if fit_stop_values is None else fit_stop_values
    training_values = np.asarray(
        terminal_values if fit_terminal_values is None else fit_terminal_values, dtype=np.float64
    ).copy()
    if set(features) != set(training_features) or set(stop_values) != set(training_stops):
        raise ValueError("fit and score paths must have the same candidate stop times")
    decisions: dict[int, NDArray[np.bool_]] = {}
    action_values: dict[int, dict[str, NDArray[np.float64]]] = {}
    action_choices: dict[int, dict[str, NDArray[np.str_]]] = {}
    later_choices = np.full(values.shape, "stay out", dtype="<U64")
    last_time = max(stop_values, default=None)
    for time in sorted(stop_values, reverse=True):
        state = np.asarray(features[time], dtype=np.float64)
        fit_state = np.asarray(training_features[time], dtype=np.float64)
        continuation = (
            np.full(values.shape, np.inf, dtype=np.float64)
            if force_stop_at_last_time and time == last_time
            else _fit_continuation(fit_state, training_values, predict_features=state)
        )
        immediate = {
            action: np.asarray(sample, dtype=np.float64)
            for action, sample in stop_values[time].items()
        }
        fit_immediate = {
            action: np.asarray(sample, dtype=np.float64)
            for action, sample in training_stops[time].items()
        }
        if not immediate or any(sample.shape != values.shape for sample in immediate.values()):
            raise ValueError("stop and continuation outcomes must be non-empty and path-aligned")
        if immediate.keys() != fit_immediate.keys() or any(
            sample.shape != training_values.shape for sample in fit_immediate.values()
        ):
            raise ValueError("fit stop outcomes must be non-empty and path-aligned")
        names = tuple(immediate)
        expected_stop = {
            action: _fit_continuation(fit_state, fit_immediate[action], predict_features=state)
            for action in names
        }
        expected_stacked = np.column_stack(tuple(expected_stop.values()))
        best_indices = np.argmin(expected_stacked, axis=1)
        path_indices = np.arange(expected_stacked.shape[0])
        best_stop_expected = expected_stacked[path_indices, best_indices]
        realized_stacked = np.column_stack(tuple(immediate.values()))
        best_stop_realized = realized_stacked[path_indices, best_indices]
        exercise = best_stop_expected <= continuation

        fit_continuation = (
            np.full(training_values.shape, np.inf, dtype=np.float64)
            if force_stop_at_last_time and time == last_time
            else _fit_continuation(fit_state, training_values, predict_features=fit_state)
        )
        fit_expected_stop = {
            action: _fit_continuation(fit_state, fit_immediate[action]) for action in names
        }
        fit_expected_stacked = np.column_stack(tuple(fit_expected_stop.values()))
        fit_best_indices = np.argmin(fit_expected_stacked, axis=1)
        fit_path_indices = np.arange(fit_expected_stacked.shape[0])
        fit_best_stop_expected = fit_expected_stacked[fit_path_indices, fit_best_indices]
        fit_realized_stacked = np.column_stack(tuple(fit_immediate.values()))
        fit_best_stop_realized = fit_realized_stacked[fit_path_indices, fit_best_indices]
        fit_exercise = fit_best_stop_expected <= fit_continuation
        chosen_now = np.asarray(names, dtype="<U64")[best_indices]
        future_choices = later_choices.copy()
        action_values[time] = {
            action: np.where(expected_stop[action] <= continuation, sample, values)
            for action, sample in immediate.items()
        }
        action_choices[time] = {
            action: np.where(expected_stop[action] <= continuation, action, future_choices).astype(
                "<U64"
            )
            for action in immediate
        }
        later_choices = np.where(exercise, chosen_now, future_choices).astype("<U64")
        values = np.where(exercise, best_stop_realized, values)
        training_values = np.where(fit_exercise, fit_best_stop_realized, training_values)
        decisions[time] = exercise
    return values, decisions, action_values, action_choices, later_choices


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
        wear_sd_by_compound: Mapping[str, float | None] | None = None,
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
        self._wear_sd_by_compound = wear_sd_by_compound

    def analyze(
        self, state: RaceState, *, driver: str, retain_position_history: bool = False
    ) -> StrategyAnalysis:
        """Evaluate pit now, delays through five laps, and staying out on matching seeds."""
        _risk(self._risk)
        if self._n < 1:
            raise ValueError("n_simulations must be positive")
        car = state.car(driver)
        if state.laps_total - state.laps_done_of(car) <= 0:
            raise ValueError(f"The race is over for {driver}; choose an earlier cutoff")
        simulator = NumpySimulator(
            self._model,
            sc=self._sc,
            compounds=self._compounds,
            wear_sd_by_compound=self._wear_sd_by_compound,
        )
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
        if not options:
            # There can still be legal timing laps, but no fitted compound to pit onto. In that
            # case staying out is the only legal action and there are no stopping times to fit.
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
        # Two-fold cross-fitting uses disjoint halves of the registered path batch. The one-path
        # edge case needs a separate fit draw because it cannot be partitioned.
        separate_fit_batch = self._n == 1
        if separate_fit_batch:
            fit_rng, score_rng = make_rng(self._seed).spawn(2)
            fit_branched = simulator._branch_paths(
                checkpoint,
                actions=branches,
                n_races=self._n,
                rng=fit_rng,
                checkpoint_laps=capture_cutoffs,
                capture_actions=("stay out",),
            )
        else:
            fit_branched = None
            score_rng = make_rng(self._seed)
        branched = simulator._branch_paths(
            checkpoint,
            actions=branches,
            n_races=self._n,
            rng=score_rng,
            checkpoint_laps=capture_cutoffs,
            capture_actions=("stay out",),
            position_history_driver=driver if retain_position_history else None,
        )
        if fit_branched is None:
            fit_branched = branched
        column = [c.driver for c in state.cars].index(driver)
        stay_values = np.asarray(
            branched["stay out"].result.finish_positions[:, column], dtype=np.float64
        )
        fit_stay_values = np.asarray(
            fit_branched["stay out"].result.finish_positions[:, column], dtype=np.float64
        )

        def path_features(outcomes: Mapping[str, Any], cutoff: int) -> NDArray[np.float64]:
            """Small normalized basis from the target's aligned pre-decision path state."""
            if cutoff == state.lap:
                checkpoint_state = None
            else:
                checkpoint_state = outcomes["stay out"].checkpoints.get(cutoff)
            n = self._n
            if checkpoint_state is None:
                position = float(car.position or len(state.cars))
                gap_to_lead = 0.0 if car.gap_ahead_s is None else float(car.gap_ahead_s)
                tire_age = float(car.tire_age)
                stops_done = float(car.stops_done)
                safety_car = float(state.regime.get("sc", 0.0) >= 0.5)
                return np.tile(
                    np.asarray(
                        [
                            [
                                position / len(state.cars),
                                gap_to_lead / 60.0,
                                tire_age / max(1, state.laps_total),
                                (state.laps_total - cutoff) / state.laps_total,
                                stops_done / 3.0,
                                safety_car,
                            ]
                        ]
                    ),
                    (n, 1),
                )
            if (
                checkpoint_state.order is None
                or checkpoint_state.clock is None
                or checkpoint_state.tire_age is None
                or checkpoint_state.stops_done is None
                or checkpoint_state.safety_car_remaining is None
            ):
                raise RuntimeError("simulator path checkpoint is missing Longstaff features")
            order = checkpoint_state.order
            ranks = np.empty_like(order)
            place_numbers = np.broadcast_to(np.arange(1, len(state.cars) + 1), order.shape)
            np.put_along_axis(ranks, order, place_numbers, axis=1)
            place_by_path = ranks[:, column].astype(np.float64)
            clocks = checkpoint_state.clock
            gap_by_path = np.maximum(0.0, clocks[:, column] - clocks.min(axis=1))
            age_by_path = checkpoint_state.tire_age[:, column].astype(np.float64)
            stops_by_path = checkpoint_state.stops_done[:, column].astype(np.float64)
            remaining_by_path = np.full(n, (state.laps_total - cutoff) / state.laps_total)
            sc_by_path = (checkpoint_state.safety_car_remaining > 0).astype(np.float64)
            return np.column_stack(
                (
                    place_by_path / len(state.cars),
                    gap_by_path / 60.0,
                    age_by_path / max(1, state.laps_total),
                    remaining_by_path,
                    stops_by_path / 3.0,
                    sc_by_path,
                )
            )

        # Reverse-time Longstaff-Schwartz: each time step regresses aligned later-policy
        # outcomes on that cutoff's pathwise state, then exercises stop-now per scenario.
        feature_by_time = {t: path_features(branched, t - 1) for t in future_stops}
        fit_feature_by_time = {t: path_features(fit_branched, t - 1) for t in future_stops}
        stop_values_by_time: dict[int, dict[str, NDArray[np.float64]]] = {}
        fit_stop_values_by_time: dict[int, dict[str, NDArray[np.float64]]] = {}
        for stop_lap in future_stops:
            stop_values_by_time[stop_lap] = {
                action: np.asarray(
                    branched[action].result.finish_positions[:, column], dtype=np.float64
                )
                for action, plan in candidates
                if plan.stop_laps == (stop_lap,)
            }
            fit_stop_values_by_time[stop_lap] = {
                action: np.asarray(
                    fit_branched[action].result.finish_positions[:, column], dtype=np.float64
                )
                for action, plan in candidates
                if plan.stop_laps == (stop_lap,)
            }
        already_met_compound_rule = len(already_used) >= 2
        now_stop_lap = stop_laps[0] if stop_laps else None
        now_candidates = [
            (action, plan)
            for action, plan in candidates
            if now_stop_lap is not None and plan.stop_laps == (now_stop_lap,)
        ]

        def summarize(action: str, plan: Plan, sample: NDArray[np.float64]) -> RankedOption:
            tail = _cvar10(sample)
            distribution = _distribution_summary(sample)
            return RankedOption(
                action,
                plan,
                float(sample.mean()),
                float(sample.std()),
                tail,
                _score_option(sample, self._risk),
                *distribution,
                _midpoint_finish_quantiles(sample),
            )

        rows: list[RankedOption] = []
        samples_by_action: dict[str, NDArray[np.float64]] = {}
        choices_by_action: dict[str, NDArray[np.str_]] = {}
        for action, plan in now_candidates:
            sample = np.asarray(
                branched[action].result.finish_positions[:, column], dtype=np.float64
            )
            rows.append(summarize(action, plan, sample))
            samples_by_action[action] = sample
            choices_by_action[action] = np.full(self._n, action, dtype="<U64")

        waiting_starts = [
            time
            for time in future_stops
            if time > (now_stop_lap if now_stop_lap is not None else state.lap)
            and time - 1 > state.lap
        ]
        wait_sample: NDArray[np.float64] | None = None
        wait_choices: NDArray[np.str_] | None = None
        wait_plan = stay_out
        waiting_tie_window: tuple[int, int] | None = None
        if waiting_starts:
            plans_by_branch = {action: plan for action, plan in candidates}
            plans_by_branch["stay out"] = stay_out

            def policy_from(start_lap: int) -> tuple[NDArray[np.float64], NDArray[np.str_]]:
                active_times = [time for time in waiting_starts if time >= start_lap]
                all_indices = np.arange(self._n)
                score_folds = (
                    (all_indices,) if separate_fit_batch else (all_indices[::2], all_indices[1::2])
                )
                policy_values = np.empty(self._n, dtype=np.float64)
                policy_choices = np.empty(self._n, dtype="<U64")
                for score_indices in score_folds:
                    if not score_indices.size:
                        continue
                    fit_indices = (
                        all_indices
                        if separate_fit_batch
                        else all_indices[~np.isin(all_indices, score_indices)]
                    )
                    features = {time: feature_by_time[time][score_indices] for time in active_times}
                    training_features = {
                        time: fit_feature_by_time[time][fit_indices] for time in active_times
                    }
                    stop_values = {
                        time: {
                            action: sample[score_indices]
                            for action, sample in stop_values_by_time[time].items()
                        }
                        for time in active_times
                    }
                    training_stop_values = {
                        time: {
                            action: sample[fit_indices]
                            for action, sample in fit_stop_values_by_time[time].items()
                        }
                        for time in active_times
                    }
                    fold_values, _, _, _, fold_choices = _backward_stop_options_with_choices(
                        features,
                        stop_values,
                        stay_values[score_indices],
                        force_stop_at_last_time=not already_met_compound_rule,
                        fit_features=training_features,
                        fit_stop_values=training_stop_values,
                        fit_terminal_values=fit_stay_values[fit_indices],
                    )
                    policy_values[score_indices] = fold_values
                    policy_choices[score_indices] = fold_choices
                return policy_values, policy_choices

            wait_sample, wait_choices = policy_from(waiting_starts[0])
            choice_names, choice_counts = np.unique(wait_choices, return_counts=True)
            modal_branch = str(choice_names[int(np.argmax(choice_counts))])
            wait_plan = plans_by_branch.get(modal_branch, stay_out)
            wait_action = "wait and decide next lap"
            rows.append(summarize(wait_action, wait_plan, wait_sample))
            samples_by_action[wait_action] = wait_sample
            choices_by_action[wait_action] = wait_choices

            tied_starts: list[int] = []
            for start_lap in waiting_starts:
                candidate_sample, _ = policy_from(start_lap)
                paired_difference = candidate_sample - wait_sample
                standard_error = (
                    float(paired_difference.std(ddof=1) / math.sqrt(self._n))
                    if self._n > 1
                    else 0.0
                )
                if abs(float(paired_difference.mean())) <= 2.0 * standard_error:
                    tied_starts.append(start_lap)
            if tied_starts:
                waiting_tie_window = (min(tied_starts), max(tied_starts))

        if already_met_compound_rule:
            rows.append(summarize("stay out", stay_out, stay_values))
            samples_by_action["stay out"] = stay_values
            choices_by_action["stay out"] = np.full(self._n, "stay out", dtype="<U64")
        if not rows:
            raise ValueError(
                f"No legal stop action is available for {driver}; the two-compound rule "
                "does not allow a never-stop option."
            )
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
        close_call_places: float | None = None
        close_call_two_se: float | None = None
        if len(rows) > 1 and self._n > 1:
            top = samples_by_action[rows[0].action]
            runner_up = samples_by_action[rows[1].action]
            paired_difference = runner_up - top
            paired_se = float(paired_difference.std(ddof=1) / math.sqrt(self._n))
            gap_places = abs(rows[1].mean_finish - rows[0].mean_finish)
            if gap_places < 2.0 * paired_se:
                close_call_places = gap_places
                close_call_two_se = 2.0 * paired_se
        recommended_position_history: NDArray[np.int64] | None = None
        if retain_position_history:
            selected_branches = choices_by_action[best.action]
            history_rows = next(
                run.result.position_history
                for run in branched.values()
                if run.result.position_history is not None
            )
            recommended_position_history = np.empty_like(history_rows)
            for branch_name, run in branched.items():
                branch_history = run.result.position_history
                if branch_history is None:
                    raise RuntimeError("a policy branch omitted requested position history")
                selected = selected_branches == branch_name
                if selected.any():
                    recommended_position_history[selected] = branch_history[selected]
        reason = f"{best.action.capitalize()} has the lowest risk-adjusted finish estimate."
        return StrategyAnalysis(
            driver,
            state.lap,
            tuple(rows),
            reason,
            recommended_position_history,
            close_call_places,
            close_call_two_se,
            waiting_tie_window,
            already_met_compound_rule,
        )

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
