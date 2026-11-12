"""FreeTrackOptimizer: analytic ground truth, price equivalence, legality, edge cases (PAC-02)."""

import time
from collections.abc import Sequence

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from f1si.interfaces import PitDecision, Plan
from f1si.state import CarState, RaceState
from f1si.strategy.free_track import (
    MIN_STINT_LAPS,
    FreeTrackOptimizer,
    PlanRefusedError,
    price_plan_slow,
)


class AnalyticPace:
    """t = alpha + fuel * (lap - 1) + wear[compound] * age, SD 0.3 (hand-built ground truth)."""

    def __init__(self, alpha: float, fuel: float, wear: dict[str, float]) -> None:
        self.alpha = alpha
        self.fuel = fuel
        self.wear = wear

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        rate = np.array([self.wear[str(c)] for c in compound], dtype=np.float64)
        mean = self.alpha + self.fuel * (lap.astype(np.float64) - 1.0) + rate * tire_age
        return mean.astype(np.float64), np.full(mean.shape, 0.3, dtype=np.float64)


def make_state(
    *,
    lap: int = 0,
    laps_total: int = 60,
    pit_loss: float = 20.0,
    compound: str | None = "HARD",
    tire_age: int = 0,
    stops_done: int = 0,
    used: tuple[str, ...] | None = None,
) -> RaceState:
    if used is None:
        used = () if compound is None else (compound,)
    cars = tuple(
        CarState(
            driver=code,
            driver_number=number,
            position=number,
            gap_ahead_s=None,
            gap_behind_s=None,
            compound=compound,
            tire_age=tire_age,
            wear_rate_s_per_lap=None,
            wear_sd=None,
            pace_offset_s=None,
            stops_done=stops_done,
            compounds_used=used,
        )
        for code, number in (("AAA", 1), ("BBB", 2))
    )
    return RaceState(
        lap=lap,
        laps_total=laps_total,
        regime={"green": 1.0},
        pit_loss_s={"green": pit_loss},
        cars=cars,
    )


def is_legal(
    plan: Plan,
    state: RaceState,
    candidates: Sequence[str],
    min_stint: int = MIN_STINT_LAPS,
) -> bool:
    car = state.car("AAA")
    used = set(car.compounds_used) | set(plan.compounds)
    if len(used & {"SOFT", "MEDIUM", "HARD"}) < 2:
        return False
    if any(c not in candidates for c in plan.compounds):
        return False
    if car.stops_done + plan.n_stops not in (1, 2):
        return False
    previous = state.lap
    for k in plan.stop_laps:
        if k < state.lap + 1 or k < previous + 1:
            return False
        previous = k
    if plan.stop_laps and state.laps_total - plan.stop_laps[-1] < min_stint:
        return False
    return not any(
        b - a < min_stint for a, b in zip(plan.stop_laps[:-1], plan.stop_laps[1:], strict=True)
    )


def test_analytic_one_stop_at_half_distance() -> None:
    model = AnalyticPace(90.0, 0.0, {"SOFT": 0.06, "HARD": 0.06})
    state = make_state(pit_loss=20.0)
    plans = FreeTrackOptimizer(model, compounds=["SOFT", "HARD"]).rank_plans(state, driver="AAA")
    one_stop = next(p for p in plans if p.n_stops == 1)
    assert one_stop.stop_laps == (30,)
    assert one_stop.compounds == ("SOFT",)
    assert one_stop.total_time_s == pytest.approx(60 * 90 + 0.06 * (2 * 30 * 31 / 2) + 20)
    assert plans[0] == one_stop


def test_analytic_two_stops_at_thirds_and_legality() -> None:
    model = AnalyticPace(90.0, 0.0, {"SOFT": 0.06, "HARD": 0.06})
    state = make_state(pit_loss=1.0)
    plans = FreeTrackOptimizer(model, compounds=["SOFT", "HARD"]).rank_plans(state, driver="AAA")
    best = plans[0]
    assert best.stop_laps == (20, 40)
    assert best.compounds == ("HARD", "SOFT")
    assert best.total_time_s == pytest.approx(60 * 90 + 0.06 * (3 * 20 * 21 / 2) + 2)
    assert is_legal(best, state, ["SOFT", "HARD"])
    assert not is_legal(Plan((20, 40), ("HARD", "HARD"), 0.0), state, ["SOFT", "HARD"])
    best_one = min((p for p in plans if p.n_stops == 1), key=lambda p: p.total_time_s)
    assert best.total_time_s < best_one.total_time_s


def test_analytic_unequal_slopes_match_an_independent_minimum() -> None:
    soft, hard = 0.10, 0.04
    state = make_state(pit_loss=20.0)
    model = AnalyticPace(90.0, 0.0, {"SOFT": soft, "HARD": hard})
    plans = FreeTrackOptimizer(model, compounds=["SOFT", "HARD"]).rank_plans(state, driver="AAA")
    best_one = min((p for p in plans if p.n_stops == 1), key=lambda p: p.total_time_s)
    totals = {
        k: 60 * 90 + hard * k * (k + 1) / 2 + soft * (60 - k) * (61 - k) / 2 + 20
        for k in range(1, 56)
    }
    k_best = min(totals, key=lambda k: totals[k])
    assert best_one.stop_laps == (k_best,)
    assert best_one.compounds == ("SOFT",)
    assert best_one.total_time_s == pytest.approx(totals[k_best])


@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    alpha=st.floats(80.0, 100.0),
    fuel=st.floats(-0.1, 0.05),
    soft=st.floats(0.0, 0.2),
    hard=st.floats(0.0, 0.2),
    laps_total=st.integers(20, 70),
    lap=st.integers(0, 20),
    tire_age=st.integers(0, 10),
    stops_done=st.sampled_from([0, 1]),
)
def test_vectorised_price_equals_the_slow_reference(
    alpha: float,
    fuel: float,
    soft: float,
    hard: float,
    laps_total: int,
    lap: int,
    tire_age: int,
    stops_done: int,
) -> None:
    model = AnalyticPace(alpha, fuel, {"SOFT": soft, "HARD": hard})
    used = ("HARD",) if stops_done == 0 else ("SOFT", "HARD")
    state = make_state(
        lap=lap, laps_total=laps_total, tire_age=tire_age, stops_done=stops_done, used=used
    )
    opt = FreeTrackOptimizer(model, compounds=["SOFT", "HARD"])
    try:
        plans = opt.rank_plans(state, driver="AAA")
    except PlanRefusedError:
        assume(False)  # too few laps left for any legal plan
        return
    totals = [p.total_time_s for p in plans]
    assert totals == sorted(totals)
    floor = min(
        alpha + fuel * (L - 1) + min(soft, hard) * 1 for L in range(lap + 1, laps_total + 1)
    ) * (laps_total - lap)
    sample = [*plans[:5], *plans[-5:], *plans[::97]]
    for plan in sample:
        slow = price_plan_slow(model, state, "AAA", plan.stop_laps, plan.compounds)
        assert plan.total_time_s == pytest.approx(slow, abs=1e-6)
        assert opt.price_plan(
            state, driver="AAA", stop_laps=plan.stop_laps, compounds=plan.compounds
        ) == pytest.approx(slow, abs=1e-6)
        assert plan.total_time_s >= floor - 1e-6
        assert is_legal(plan, state, ["SOFT", "HARD"])


def test_every_plan_is_legal_mid_race() -> None:
    model = AnalyticPace(90.0, -0.03, {"SOFT": 0.1, "MEDIUM": 0.07, "HARD": 0.04})
    state = make_state(lap=22, tire_age=25, compound="MEDIUM", stops_done=0)
    plans = FreeTrackOptimizer(model, compounds=["SOFT", "MEDIUM", "HARD"]).rank_plans(
        state, driver="AAA"
    )
    assert plans
    assert all(is_legal(p, state, ["SOFT", "MEDIUM", "HARD"]) for p in plans)
    assert all(p.stop_laps[0] >= 23 for p in plans)


def test_stops_done_two_with_two_compounds_only_stays_out() -> None:
    model = AnalyticPace(90.0, 0.0, {"SOFT": 0.1, "HARD": 0.04})
    state = make_state(lap=40, stops_done=2, used=("SOFT", "HARD", "HARD"))
    plans = FreeTrackOptimizer(model, compounds=["SOFT", "HARD"]).rank_plans(state, driver="AAA")
    assert len(plans) == 1
    assert plans[0].stop_laps == ()


def test_stops_done_two_without_two_compounds_refuses() -> None:
    model = AnalyticPace(90.0, 0.0, {"SOFT": 0.1, "HARD": 0.04})
    state = make_state(lap=40, stops_done=2, used=("HARD", "HARD"))
    with pytest.raises(PlanRefusedError, match="No legal plan"):
        FreeTrackOptimizer(model, compounds=["SOFT", "HARD"]).rank_plans(state, driver="AAA")


def test_few_laps_left_gives_the_single_no_stop_plan() -> None:
    model = AnalyticPace(90.0, 0.0, {"SOFT": 0.1, "HARD": 0.04})
    state = make_state(lap=56, stops_done=1, used=("SOFT", "HARD"), laps_total=60)
    plans = FreeTrackOptimizer(model, compounds=["SOFT", "HARD"]).rank_plans(state, driver="AAA")
    assert len(plans) == 1
    assert plans[0].stop_laps == ()


def test_refusals() -> None:
    model = AnalyticPace(90.0, 0.0, {"SOFT": 0.1, "HARD": 0.04})
    opt = FreeTrackOptimizer(model, compounds=["SOFT", "HARD"])
    with pytest.raises(PlanRefusedError, match="race is over"):
        opt.rank_plans(make_state(lap=60), driver="AAA")
    with pytest.raises(PlanRefusedError, match="out of scope"):
        opt.rank_plans(make_state(stops_done=1, used=("HARD", "INTERMEDIATE")), driver="AAA")
    with pytest.raises(PlanRefusedError, match="out of scope"):
        opt.rank_plans(make_state(compound="WET", used=("WET",)), driver="AAA")
    with pytest.raises(PlanRefusedError, match="AAA"):
        opt.rank_plans(make_state(compound=None), driver="AAA")
    with pytest.raises(PlanRefusedError, match="No wear rate"):
        opt.rank_plans(make_state(compound="MEDIUM"), driver="AAA")
    with pytest.raises(ValueError, match="AAA, BBB"):
        opt.rank_plans(make_state(), driver="ZZZ")


def test_decide_is_deterministic_and_pits_when_the_best_stop_is_now() -> None:
    model = AnalyticPace(90.0, 0.0, {"SOFT": 0.06, "HARD": 0.06})
    opt = FreeTrackOptimizer(model, compounds=["SOFT", "HARD"])
    state = make_state(lap=29, tire_age=29, pit_loss=20.0)
    before = state.to_json()
    first = opt.decide(state, driver="AAA")
    assert isinstance(first, PitDecision)
    assert first == opt.decide(state, driver="AAA")
    assert state.to_json() == before
    assert first.pit_now == (first.best_plan.stop_laps[0] == 30)
    assert first.pit_now
    assert first.compound == first.best_plan.compounds[0] == "SOFT"
    early = opt.decide(make_state(), driver="AAA")
    assert not early.pit_now
    assert early.compound is None


def test_search_size_and_speed_at_lap_zero() -> None:
    model = AnalyticPace(90.0, -0.03, {"SOFT": 0.1, "HARD": 0.04})
    state = make_state(laps_total=57)
    opt = FreeTrackOptimizer(model, compounds=["SOFT", "HARD"])
    start = time.perf_counter()
    plans = opt.rank_plans(state, driver="AAA")
    assert time.perf_counter() - start < 2.0
    assert 1000 < len(plans) < 10000
    keys = [(round(p.total_time_s, 9), p.n_stops, p.stop_laps, p.compounds) for p in plans]
    assert keys == sorted(keys)


def test_price_plan_validates_stop_laps() -> None:
    model = AnalyticPace(90.0, 0.0, {"SOFT": 0.1, "HARD": 0.04})
    opt = FreeTrackOptimizer(model, compounds=["SOFT", "HARD"])
    with pytest.raises(ValueError, match="stop laps"):
        opt.price_plan(make_state(), driver="AAA", stop_laps=(0,), compounds=("SOFT",))
    with pytest.raises(ValueError, match="stop laps"):
        opt.price_plan(make_state(), driver="AAA", stop_laps=(30, 20), compounds=("SOFT", "HARD"))
