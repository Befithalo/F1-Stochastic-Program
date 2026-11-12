"""Plan resolution: optimizer plans, forced plans, fallback rule."""

import pytest

from f1si.interfaces import Plan
from f1si.pace.linear import LinearPaceFit
from f1si.sim.plans import fallback_plan, resolve_plans
from f1si.state import RaceState
from f1si.strategy.free_track import FreeTrackOptimizer

from .conftest import ZeroNoisePace, hand_state, with_car


def test_optimizer_plans_for_every_car(long_lap0: tuple[RaceState, LinearPaceFit]) -> None:
    state, fit = long_lap0
    optimizer = FreeTrackOptimizer(fit, compounds=fit.fitted_compounds)
    plans, sources = resolve_plans(state, None, optimizer, fit.fitted_compounds)
    assert len(plans) == len(sources) == len(state.cars)
    fitted = set(fit.fitted_compounds)
    for car, plan, src in zip(state.cars, plans, sources, strict=True):
        assert src.driver == car.driver
        if car.compound in fitted:
            assert src.source == "optimizer"
            assert plan == optimizer.rank_plans(state, driver=car.driver)[0]
        else:
            assert src.source == "fallback"


def test_forced_plan_and_validation(long_lap0: tuple[RaceState, LinearPaceFit]) -> None:
    state, fit = long_lap0
    optimizer = FreeTrackOptimizer(fit, compounds=fit.fitted_compounds)
    code = state.cars[0].driver
    forced = Plan((20, 40), ("HARD", "HARD"), 1.0)
    plans, sources = resolve_plans(state, {code: forced}, optimizer, fit.fitted_compounds)
    assert plans[0] is forced
    assert sources[0].source == "forced"
    with pytest.raises(ValueError, match="Unknown driver code"):
        resolve_plans(state, {"ZZZ": forced}, optimizer, fit.fitted_compounds)
    late = Plan((58,), ("HARD",), 0.0)
    with pytest.raises(ValueError, match="58"):
        resolve_plans(state, {code: late}, optimizer, fit.fitted_compounds)
    mid = hand_state(2, lap=20, laps_total=57)
    early = Plan((15,), ("MEDIUM",), 0.0)
    with pytest.raises(ValueError, match="15"):
        resolve_plans(mid, {"AAA": early}, optimizer, fit.fitted_compounds)


def test_fallback_for_unfitted_compound(long_lap0: tuple[RaceState, LinearPaceFit]) -> None:
    _, fit = long_lap0
    optimizer = FreeTrackOptimizer(fit, compounds=("HARD",))
    state = hand_state(2, lap=10, laps_total=57, compound="SOFT")
    state = with_car(state, 1, laps_done=9)
    plans, sources = resolve_plans(state, None, optimizer, ("HARD", "MEDIUM"))
    assert all(s.source == "fallback" for s in sources)
    assert "optimizer refused" in sources[0].reason
    assert "SOFT" in sources[0].reason
    assert plans[0].stop_laps == (10 + round(47 / 2),)
    assert plans[0].compounds == ("HARD",)
    assert plans[1].stop_laps == (9 + round(48 / 2),)
    assert plans[0].total_time_s == 0.0


def test_fallback_without_legal_stop() -> None:
    state = hand_state(1, lap=10, laps_total=57, compound="HARD")
    used_up = with_car(state, 0, compounds_used=("HARD", "SOFT"))
    plan, note = fallback_plan(used_up, used_up.cars[0], ("HARD", "SOFT"))
    assert plan.stop_laps == ()
    assert "no legal" in note
    near_end = hand_state(1, lap=52, laps_total=57)
    plan, note = fallback_plan(near_end, near_end.cars[0], ("HARD", "SOFT"))
    assert plan.stop_laps == ()
    assert note


def test_unknown_start_tyre_falls_back() -> None:
    optimizer = FreeTrackOptimizer(ZeroNoisePace(), compounds=("HARD", "MEDIUM"))
    state = hand_state(1, lap=0, laps_total=40, compound=None)
    plans, sources = resolve_plans(state, None, optimizer, ("HARD", "MEDIUM"))
    assert sources[0].source == "fallback"
    assert plans[0].stop_laps == (20,)
    assert plans[0].compounds == ("HARD",)
