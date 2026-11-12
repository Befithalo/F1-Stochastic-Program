"""Review fix WR-01: each car is planned from its own completed laps, not the leader's (DEC-073)."""

import dataclasses
import json
from pathlib import Path

import pytest

from f1si.data.asof import AsOf, AsOfAccessor
from f1si.pace.linear import fit_linear_pace
from f1si.state import CarState, RaceState, build_race_state
from f1si.strategy.free_track import FreeTrackOptimizer, price_plan_slow
from tests.conftest import LONG_RACE_ID
from tests.strategy.test_free_track import AnalyticPace, make_state

MODEL = AnalyticPace(90.0, -0.03, {"SOFT": 0.08, "MEDIUM": 0.06, "HARD": 0.04})
OPT = FreeTrackOptimizer(MODEL, compounds=["SOFT", "MEDIUM", "HARD"])


def _two_cars(leader_done: int = 20, follower_done: int = 19) -> RaceState:
    """Leader AAA after 20 laps; BBB one lap behind, so its tyre age is one lower than AAA's."""
    base = make_state(lap=leader_done, tire_age=20, compound="HARD")
    cars = (
        dataclasses.replace(base.cars[0], laps_done=leader_done, tire_age=20),
        dataclasses.replace(base.cars[1], laps_done=follower_done, tire_age=follower_done),
    )
    return dataclasses.replace(base, cars=cars)


def test_follower_is_priced_from_its_own_next_lap() -> None:
    state = _two_cars()
    # BBB: 19 laps done, hard tyres of age 19. Stop on lap 30, then 30 laps on SOFT (laps 31-60).
    by_hand = 0.0
    for lap in range(20, 31):  # laps 20..30 on the old hards, age 20..30
        by_hand += 90.0 - 0.03 * (lap - 1) + 0.04 * (lap)
    for i, lap in enumerate(range(31, 61)):  # fresh softs, age 1..30
        by_hand += 90.0 - 0.03 * (lap - 1) + 0.08 * (i + 1)
    by_hand += 20.0
    got = OPT.price_plan(state, driver="BBB", stop_laps=[30], compounds=["SOFT"])
    assert got == pytest.approx(by_hand)
    assert price_plan_slow(MODEL, state, "BBB", [30], ["SOFT"]) == pytest.approx(by_hand)


def test_ranked_plans_for_the_follower_start_at_its_next_lap() -> None:
    state = _two_cars()
    follower = OPT.rank_plans(state, driver="BBB")
    leader = OPT.rank_plans(state, driver="AAA")
    assert min(p.stop_laps[0] for p in follower if p.stop_laps) == 20
    assert min(p.stop_laps[0] for p in leader if p.stop_laps) == 21
    for plan in follower[:5] + follower[-5:]:
        slow = price_plan_slow(MODEL, state, "BBB", plan.stop_laps, plan.compounds)
        assert plan.total_time_s == pytest.approx(slow, rel=1e-12)
        priced = OPT.price_plan(
            state, driver="BBB", stop_laps=plan.stop_laps, compounds=plan.compounds
        )
        assert priced == pytest.approx(plan.total_time_s, rel=1e-12)


def test_pit_now_means_the_cars_own_next_lap() -> None:
    state = _two_cars()
    decision = OPT.decide(state, driver="BBB")
    best = decision.best_plan
    assert decision.pit_now == bool(best.stop_laps and best.stop_laps[0] == 20)


def test_a_car_with_no_laps_done_falls_back_to_the_state_lap() -> None:
    base = make_state(lap=20, tire_age=20)
    assert base.cars[0].laps_done is None
    assert base.laps_done_of(base.cars[0]) == 20
    stops = OPT.rank_plans(base, driver="AAA")
    assert min(p.stop_laps[0] for p in stops if p.stop_laps) == 21


def test_laps_done_round_trips_through_json_and_old_json_still_loads() -> None:
    state = _two_cars()
    assert RaceState.from_json(state.to_json()) == state
    data = json.loads(state.to_json())
    assert [c["laps_done"] for c in data["cars"]] == [20, 19]
    for car in data["cars"]:
        del car["laps_done"]
    legacy = RaceState.from_json_dict(data)
    assert all(c.laps_done is None for c in legacy.cars)


def test_laps_done_is_validated() -> None:
    state = _two_cars()
    too_far = dataclasses.replace(state.cars[1], laps_done=25)
    with pytest.raises(ValueError, match="laps_done"):
        dataclasses.replace(state, cars=(state.cars[0], too_far))
    with pytest.raises(ValueError, match="laps_done"):
        CarState(**{**dataclasses.asdict(state.cars[0]), "laps_done": -1})


def test_builder_fills_laps_done_from_the_snapshot(long_synthetic_db: Path) -> None:
    snap = AsOfAccessor(long_synthetic_db).snapshot(AsOf(LONG_RACE_ID, 40))
    state = build_race_state(snap, fit_linear_pace(snap), laps_total=57, pit_loss_s=22.0)
    numbers = snap.cars["driver_number"].astype(int).tolist()
    done = dict(zip(numbers, snap.cars["laps_done"].astype(int).tolist(), strict=True))
    assert {c.driver_number: c.laps_done for c in state.cars} == done
    assert max(done.values()) == state.lap == 40
    assert min(done.values()) < state.lap  # followers sit behind the leader at the cutoff
