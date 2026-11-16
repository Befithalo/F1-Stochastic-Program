"""Longstaff-Schwartz continuation, current-action ranking, and policy contracts."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import fields, replace
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from f1si.interfaces import Plan
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel, _PathCheckpoint
from f1si.state import CarState, RaceState
from f1si.strategy import longstaff
from f1si.strategy.longstaff import (
    LongstaffSchwartzPolicy,
    _backward_stop,
    _backward_stop_options_with_choices,
    _cvar10,
    _fit_continuation,
    _midpoint_finish_quantiles,
    _score_option,
)


class FlatPace:
    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        return np.full(lap.shape, 90.0), np.full(lap.shape, 0.2)


def state(lap: int = 10, laps_total: int = 16) -> RaceState:
    cars = tuple(
        CarState(
            driver=code,
            driver_number=i,
            position=i,
            gap_ahead_s=None,
            gap_behind_s=None,
            compound="HARD",
            tire_age=lap,
            wear_rate_s_per_lap=0.05,
            wear_sd=0.01,
            pace_offset_s=0.0,
            stops_done=0,
            compounds_used=("HARD",),
        )
        for i, code in enumerate(("AAA", "BBB"), start=1)
    )
    return RaceState(lap, laps_total, {"green": 1.0}, {"green": 20.0, "sc": 10.0}, cars)


def state_with_two_compounds(lap: int = 10, laps_total: int = 16) -> RaceState:
    race = state(lap, laps_total)
    return replace(
        race,
        cars=(replace(race.cars[0], compounds_used=("HARD", "MEDIUM")), *race.cars[1:]),
    )


def test_continuation_regression_recovers_conditional_mean_and_falls_back() -> None:
    x = np.linspace(-1.0, 1.0, 40)[:, None]
    y = 7.0 + 2.5 * x[:, 0]
    predicted = _fit_continuation(x, y)
    np.testing.assert_allclose(predicted, y, atol=1e-10)
    # Fewer observations than basis columns must produce a finite intercept-only estimate.
    fallback = _fit_continuation(np.ones((1, 3)), np.array([4.0]))
    assert np.isfinite(fallback).all()
    np.testing.assert_allclose(fallback, 4.0)


def test_continuation_is_fit_on_training_paths_and_scored_on_independent_paths() -> None:
    fit_features = {16: np.zeros((4, 1), dtype=np.float64)}
    fit_stops = {16: {"medium": np.ones(4, dtype=np.float64)}}
    fit_terminal = np.full(4, 10.0)
    score_features = {16: np.zeros((2, 1), dtype=np.float64)}
    score_stops = {16: {"medium": np.full(2, 10.0)}}
    score_terminal = np.ones(2)

    values, _, _, _, choices = _backward_stop_options_with_choices(
        score_features,
        score_stops,
        score_terminal,
        fit_features=fit_features,
        fit_stop_values=fit_stops,
        fit_terminal_values=fit_terminal,
    )

    # The fit paths favor stopping (1 vs 10), while the disjoint score paths favor waiting
    # (10 vs 1). The held-out policy still chooses its trained stop and scores its 10-place draw.
    np.testing.assert_array_equal(values, np.full(2, 10.0))
    np.testing.assert_array_equal(choices, np.full(2, "medium"))


def test_pathwise_stopping_uses_different_cutoff_states() -> None:
    features = np.arange(4.0)[:, None]
    later_policy_values = 1.0 + 2.0 * features[:, 0]
    stopped, decisions = _backward_stop({4: features}, {4: np.full(4, 4.0)}, later_policy_values)
    np.testing.assert_allclose(stopped, [1.0, 3.0, 4.0, 4.0])
    assert decisions[4].tolist() == [False, False, True, True]


def test_delayed_option_does_not_use_future_finish_noise_to_choose_a_stop() -> None:
    features = {16: np.zeros((2, 1), dtype=np.float64)}
    stop_values = {16: {"medium": np.array([5.0, 15.0])}}
    terminal = np.array([9.0, 9.0])

    _, _, action_values, action_choices, _ = _backward_stop_options_with_choices(
        features, stop_values, terminal
    )

    # Both paths have identical decision-time features. The conditional mean stop finish
    # is worse than continuation, so future realized noise must not select the lucky path.
    np.testing.assert_array_equal(action_values[16]["medium"], np.array([9.0, 9.0]))
    np.testing.assert_array_equal(action_choices[16]["medium"], np.array(["stay out", "stay out"]))


def test_two_compound_rule_forces_a_stop_at_the_last_legal_window() -> None:
    features = {20: np.zeros((2, 1), dtype=np.float64)}
    stop_values = {20: {"hard": np.array([15.0, 16.0])}}
    terminal = np.array([1.0, 2.0])

    values, decisions, _, _, choices = _backward_stop_options_with_choices(
        features, stop_values, terminal, force_stop_at_last_time=True
    )

    np.testing.assert_array_equal(values, np.array([15.0, 16.0]))
    np.testing.assert_array_equal(decisions[20], np.array([True, True]))
    np.testing.assert_array_equal(choices, np.array(["hard", "hard"]))


def test_branch_paths_share_indexed_draws_and_default_result_shape() -> None:
    race = state()
    simulator = NumpySimulator(FlatPace(), sc=SafetyCarModel(0.2, 3), compounds=("HARD", "MEDIUM"))
    checkpoint = _PathCheckpoint(state=race, lap=race.lap)
    outcomes = simulator._branch_paths(
        checkpoint,
        actions={
            "stop": {"AAA": Plan((11,), ("MEDIUM",), 0.0)},
            "stay": {"AAA": Plan((), (), 0.0)},
        },
        n_races=32,
        rng=np.random.default_rng(13),
        checkpoint_laps=(11,),
        capture_actions=("stay",),
    )
    stopped = outcomes["stop"].result
    stayed = outcomes["stay"].result
    assert stopped.finish_positions.shape == stayed.finish_positions.shape == (32, 2)
    np.testing.assert_array_equal(stopped.sc_lap_mask, stayed.sc_lap_mask)
    order = outcomes["stay"].checkpoints[11].order
    assert order is not None
    assert order.shape == (32, 2)
    default_result = simulator.simulate(
        race, n_races=32, rng=np.random.default_rng(13), plans={"AAA": Plan((), (), 0.0)}
    )
    assert default_result.finish_positions.shape == (32, 2)
    assert default_result.clock_s is None


def test_cvar_uses_worst_tail_with_fractional_boundary_mass() -> None:
    assert _cvar10(np.arange(1.0, 11.0)) == pytest.approx(10.0)
    assert _cvar10(np.arange(1.0, 21.0)) == pytest.approx(19.5)


def test_score_blend_endpoints_and_invalid_risk() -> None:
    assert _score_option(np.array([1.0, 2.0, 9.0, 10.0]), 0.0) == pytest.approx(5.5)
    assert _score_option(np.array([1.0, 2.0, 9.0, 10.0]), 1.0) == pytest.approx(10.0)
    for risk in (-0.01, 1.01, math.inf, math.nan):
        with pytest.raises(ValueError, match="risk_aversion"):
            LongstaffSchwartzPolicy(FlatPace(), compounds=("HARD", "MEDIUM"), risk_aversion=risk)


def test_policy_returns_deterministic_decision_without_mutating_state() -> None:
    race = state()
    before = race.to_json()
    policy = LongstaffSchwartzPolicy(
        FlatPace(), compounds=("HARD", "MEDIUM", "SOFT"), n_simulations=16, seed=5
    )
    first = policy.decide(race, driver="AAA")
    second = policy.decide(race, driver="AAA")
    assert first == second
    assert race.to_json() == before
    assert first.lap == race.lap
    assert first.best_plan == first.ranked_plans[0]
    assert len(policy.analyze(race, driver="AAA").options) >= 1


def test_recommended_history_matches_the_pathwise_policy_finish_distribution() -> None:
    race = state(lap=10, laps_total=16)
    report = LongstaffSchwartzPolicy(
        FlatPace(), compounds=("HARD", "MEDIUM", "SOFT"), n_simulations=32, seed=9
    ).analyze(race, driver="AAA", retain_position_history=True)

    history = report.recommended_position_history
    assert history is not None
    assert history.shape == (32, race.laps_total - race.lap)
    finishes = history[:, -1].astype(np.float64)
    assert float(finishes.mean()) == pytest.approx(report.best.mean_finish)
    assert _midpoint_finish_quantiles(finishes) == report.best.finish_quantiles


def test_policy_ranks_stay_out_when_no_second_compound_is_available() -> None:
    race = state(lap=10, laps_total=16)
    policy = LongstaffSchwartzPolicy(FlatPace(), compounds=("HARD",), n_simulations=12, seed=5)
    with pytest.raises(ValueError, match="two-compound rule"):
        policy.analyze(race, driver="AAA")


@pytest.mark.parametrize("count", [0, -1])
def test_policy_refuses_nonpositive_sample_count_before_simulation(count: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        LongstaffSchwartzPolicy(FlatPace(), compounds=("HARD", "MEDIUM"), n_simulations=count)


def test_policy_ranks_box_now_and_wait_once_each() -> None:
    race = state(lap=10, laps_total=40)
    policy = LongstaffSchwartzPolicy(
        FlatPace(), compounds=("HARD", "MEDIUM"), n_simulations=16, seed=2
    )
    report = policy.analyze(race, driver="AAA")
    assert {row.action for row in report.options} == {"pit now", "wait and decide next lap"}
    assert report.never_stop_allowed is False
    assert all(
        np.isfinite([row.mean_finish, row.spread, row.cvar10, row.score]).all()
        for row in report.options
    )


def test_late_race_omits_stop_options_past_last_legal_boundary() -> None:
    race = state(lap=13, laps_total=16)
    policy = LongstaffSchwartzPolicy(
        FlatPace(), compounds=("HARD", "MEDIUM"), n_simulations=12, seed=4
    )
    with pytest.raises(ValueError, match="two-compound rule"):
        policy.analyze(race, driver="AAA")


def test_empty_outcome_samples_are_refused() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _cvar10(np.array([], dtype=np.float64))
    policy = LongstaffSchwartzPolicy(
        FlatPace(), compounds=("HARD", "MEDIUM"), n_simulations=12, seed=4
    )
    with pytest.raises(ValueError, match="race is over"):
        policy.analyze(state(lap=16, laps_total=16), driver="AAA")


def test_risk_endpoints_change_ranking_for_controlled_samples() -> None:
    steady = np.full(100, 5.0)
    volatile = np.ones(90)
    volatile = np.concatenate([volatile, np.full(10, 30.0)])
    assert _score_option(volatile, 0.0) < _score_option(steady, 0.0)
    assert _score_option(volatile, 1.0) > _score_option(steady, 1.0)


def test_reason_is_one_stable_score_grounded_sentence() -> None:
    race = state(lap=10, laps_total=40)
    policy = LongstaffSchwartzPolicy(
        FlatPace(), compounds=("HARD", "MEDIUM"), n_simulations=12, seed=7
    )
    reason = policy.analyze(race, driver="AAA").reason
    assert reason.endswith(".")
    assert reason.count("lowest risk-adjusted finish estimate") == 1
    assert "tire cliff" not in reason.lower()
    assert "future safety car" not in reason.lower()
    assert reason == policy.analyze(race, driver="AAA").reason


def test_tied_options_have_stable_action_order(monkeypatch: pytest.MonkeyPatch) -> None:
    class SameOutcomeSimulator:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def _branch_paths(
            self,
            checkpoint: _PathCheckpoint,
            *,
            actions: Mapping[str, Mapping[str, Plan]],
            n_races: int,
            rng: np.random.Generator,
            checkpoint_laps: Sequence[int],
            capture_actions: Sequence[str],
            position_history_driver: str | None = None,
        ) -> dict[str, Any]:
            from types import SimpleNamespace

            outcomes: dict[str, Any] = {}
            for name in actions:
                checkpoints: dict[int, Any] = (
                    {
                        cutoff: SimpleNamespace(
                            order=np.tile(np.array([[0, 1]], dtype=np.int64), (n_races, 1)),
                            clock=np.tile(np.array([[0.0, 10.0]]), (n_races, 1)),
                            tire_age=np.ones((n_races, 2), dtype=np.int64),
                            stops_done=np.zeros((n_races, 2), dtype=np.int64),
                            safety_car_remaining=np.zeros(n_races, dtype=np.int64),
                        )
                        for cutoff in checkpoint_laps
                    }
                    if name in capture_actions
                    else {}
                )
                outcomes[name] = SimpleNamespace(
                    result=SimpleNamespace(
                        finish_positions=np.ones((n_races, 2), dtype=np.int64),
                    ),
                    checkpoints=checkpoints,
                )
            return outcomes

    monkeypatch.setattr(longstaff, "NumpySimulator", SameOutcomeSimulator)
    report = LongstaffSchwartzPolicy(
        FlatPace(), compounds=("HARD", "MEDIUM"), n_simulations=20
    ).analyze(state(lap=10, laps_total=40), driver="AAA")
    assert [row.action for row in report.options] == ["pit now", "wait and decide next lap"]


def test_ranked_options_summarize_their_own_finish_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    samples = {
        "pit now": np.array([1, 2, 3, 4, 10, 10, 20, 20, 20, 20]),
        "pit in 1 lap(s)": np.full(10, 4),
        "pit in 2 lap(s)": np.array([1, 1, 1, 8, 8, 8, 8, 8, 8, 8]),
        "pit in 3 lap(s)": np.full(10, 12),
        "pit in 4 lap(s)": np.full(10, 17),
        "pit in 5 lap(s)": np.full(10, 20),
        "stay out": np.array([2, 2, 2, 6, 6, 6, 6, 6, 6, 6]),
    }

    class ControlledSimulator:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def _branch_paths(
            self,
            checkpoint: _PathCheckpoint,
            *,
            actions: Mapping[str, Mapping[str, Plan]],
            n_races: int,
            rng: np.random.Generator,
            checkpoint_laps: Sequence[int],
            capture_actions: Sequence[str],
            position_history_driver: str | None = None,
        ) -> dict[str, Any]:
            outcomes: dict[str, Any] = {}
            for name in actions:
                sample = samples[name]
                checkpoints = (
                    {
                        cutoff: SimpleNamespace(
                            order=np.tile(np.array([[0, 1]], dtype=np.int64), (n_races, 1)),
                            clock=np.tile(np.array([[0.0, 10.0]]), (n_races, 1)),
                            tire_age=np.ones((n_races, 2), dtype=np.int64),
                            stops_done=np.zeros((n_races, 2), dtype=np.int64),
                            safety_car_remaining=np.zeros(n_races, dtype=np.int64),
                        )
                        for cutoff in checkpoint_laps
                    }
                    if name in capture_actions
                    else {}
                )
                outcomes[name] = SimpleNamespace(
                    result=SimpleNamespace(
                        finish_positions=np.column_stack((sample, 21 - sample)),
                    ),
                    checkpoints=checkpoints,
                )
            return outcomes

    monkeypatch.setattr(longstaff, "NumpySimulator", ControlledSimulator)
    analysis = LongstaffSchwartzPolicy(
        FlatPace(), compounds=("HARD", "MEDIUM"), n_simulations=10
    ).analyze(state(lap=10, laps_total=40), driver="AAA")

    by_action = {option.action: option for option in analysis.options}
    option = by_action["pit now"]
    sample = samples["pit now"]
    assert (
        option.podium_probability,
        option.top10_probability,
        option.finish_p05,
        option.finish_p95,
    ) == (0.3, 0.6, 1, 20)
    assert option.podium_probability == pytest.approx(np.mean(sample <= 3))
    assert option.top10_probability == pytest.approx(np.mean(sample <= 10))
    expected = np.quantile(sample, [0.05, 0.95], method="inverted_cdf")
    assert (option.finish_p05, option.finish_p95) == tuple(expected.astype(int))
    quantile_levels = (np.arange(100, dtype=np.float64) + 0.5) / 100.0
    expected_quantiles = np.quantile(sample, quantile_levels, method="inverted_cdf")
    assert option.finish_quantiles == tuple(expected_quantiles.astype(int))
    assert len(by_action["wait and decide next lap"].finish_quantiles) == 100


def test_close_call_uses_paired_standard_error_with_common_random_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    n = 10
    box_now = np.full(n, 5.0)
    wait_draws = np.array([4.0, 6.0, 5.0, 6.0, 5.0, 6.0, 5.0, 6.0, 5.0, 6.0])
    future_branch = "pit in 1 lap(s)"
    rngs: list[np.random.Generator] = []
    fit_score_features: list[tuple[NDArray[np.float64], NDArray[np.float64]]] = []

    class PairedSimulator:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def _branch_paths(
            self,
            checkpoint: _PathCheckpoint,
            *,
            actions: Mapping[str, Mapping[str, Plan]],
            n_races: int,
            rng: np.random.Generator,
            checkpoint_laps: Sequence[int],
            capture_actions: Sequence[str],
            position_history_driver: str | None = None,
        ) -> dict[str, Any]:
            rngs.append(rng)
            order = np.tile(np.array([[0, 1]], dtype=np.int64), (n, 1))
            order[1::2] = np.array([1, 0])
            outcomes: dict[str, Any] = {}
            for name in actions:
                sample = (
                    box_now
                    if name == "pit now"
                    else np.full(n, 19.0)
                    if name == "stay out"
                    else wait_draws
                )
                checkpoints = (
                    {
                        cutoff: SimpleNamespace(
                            order=order,
                            clock=np.tile(np.array([[0.0, 10.0]]), (n, 1)),
                            tire_age=np.ones((n, 2), dtype=np.int64),
                            stops_done=np.zeros((n, 2), dtype=np.int64),
                            safety_car_remaining=np.zeros(n, dtype=np.int64),
                        )
                        for cutoff in checkpoint_laps
                    }
                    if name in capture_actions
                    else {}
                )
                outcomes[name] = SimpleNamespace(
                    result=SimpleNamespace(finish_positions=np.column_stack((sample, 21 - sample))),
                    checkpoints=checkpoints,
                )
            return outcomes

    def backward(
        features: Mapping[int, NDArray[np.float64]],
        stop_values: Mapping[int, Mapping[str, NDArray[np.float64]]],
        terminal: NDArray[np.float64],
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
        if fit_features is not None:
            time = next(iter(features))
            fit_score_features.append((features[time][:, 0], fit_features[time][:, 0]))
            score_position = features[next(iter(features))][0, 0]
            fold_offset = 0 if score_position < 0.75 else 1
            sample = wait_draws[np.arange(fold_offset, n, 2)]
        choices = np.full(terminal.size, future_branch, dtype="<U64")
        action_values = {
            time: {action: sample for action in actions} for time, actions in stop_values.items()
        }
        action_choices = {
            time: {action: choices for action in actions} for time, actions in stop_values.items()
        }
        decisions = {time: np.ones(terminal.size, dtype=np.bool_) for time in stop_values}
        return sample, decisions, action_values, action_choices, choices

    monkeypatch.setattr(longstaff, "NumpySimulator", PairedSimulator)
    monkeypatch.setattr(longstaff, "_backward_stop_options_with_choices", backward)
    analysis = LongstaffSchwartzPolicy(
        FlatPace(), compounds=("HARD", "MEDIUM"), n_simulations=n
    ).analyze(state(lap=10, laps_total=40), driver="AAA")

    difference = wait_draws - box_now
    expected_two_se = 2.0 * float(difference.std(ddof=1) / math.sqrt(n))
    assert analysis.close_call_places == pytest.approx(0.4)
    assert analysis.close_call_two_se == pytest.approx(expected_two_se)
    assert analysis.waiting_tie_window_laps == (12, 16)
    assert len(rngs) == 1
    assert fit_score_features
    for score_features, training_features in fit_score_features:
        assert set(score_features).isdisjoint(training_features)


def test_ranked_option_retains_100_midpoint_quantiles_for_known_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample = np.repeat(np.arange(1, 11, dtype=np.int64), 10)

    class KnownDistributionSimulator:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def _branch_paths(
            self,
            checkpoint: _PathCheckpoint,
            *,
            actions: Mapping[str, Mapping[str, Plan]],
            n_races: int,
            rng: np.random.Generator,
            checkpoint_laps: Sequence[int],
            capture_actions: Sequence[str],
            position_history_driver: str | None = None,
        ) -> dict[str, Any]:
            assert set(actions) == {"stay out"}
            outcomes = np.column_stack((sample, np.full(n_races, 11, dtype=np.int64)))
            return {
                "stay out": SimpleNamespace(
                    result=SimpleNamespace(finish_positions=outcomes),
                    checkpoints={},
                )
            }

    monkeypatch.setattr(longstaff, "NumpySimulator", KnownDistributionSimulator)
    option = (
        LongstaffSchwartzPolicy(FlatPace(), compounds=("HARD",), n_simulations=100, seed=3)
        .analyze(state_with_two_compounds(lap=12, laps_total=16), driver="AAA")
        .best
    )

    expected = tuple(int(value) for value in sample)
    assert getattr(option, "finish_quantiles", None) == expected, (
        "The ranked option should retain all 100 midpoint inverted-CDF quantiles "
        "from its known finish distribution."
    )
    assert len(option.finish_quantiles) == 100
    assert "sample" not in vars(option)
    assert "draws" not in vars(option)


def test_frozen_prediction_trace_carries_summaries_without_draw_arrays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    samples = {"stay out": np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])}

    class StayOutSimulator:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def _branch_paths(
            self,
            checkpoint: _PathCheckpoint,
            *,
            actions: Mapping[str, Mapping[str, Plan]],
            **kwargs: object,
        ) -> dict[str, Any]:
            return {
                "stay out": SimpleNamespace(
                    result=SimpleNamespace(
                        finish_positions=np.column_stack(
                            (samples["stay out"], np.arange(10, 0, -1))
                        )
                    ),
                    checkpoints={},
                )
            }

    monkeypatch.setattr(longstaff, "NumpySimulator", StayOutSimulator)
    report = LongstaffSchwartzPolicy(FlatPace(), compounds=("HARD",), n_simulations=10).analyze(
        state_with_two_compounds(lap=12, laps_total=16), driver="AAA"
    )
    from f1si.backtest.walk_forward import PredictionRow

    row = PredictionRow("2023-01", "AAA", 10, report)
    assert row.analysis is report
    assert report.options[0].podium_probability == pytest.approx(0.3)
    assert report.options[0].top10_probability == pytest.approx(1.0)
    assert (report.options[0].finish_p05, report.options[0].finish_p95) == (1, 10)
    assert all(field.name not in {"sample", "draws"} for field in fields(type(report.options[0])))
    assert all(field.name not in {"sample", "draws"} for field in fields(PredictionRow))
