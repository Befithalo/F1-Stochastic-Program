"""Safety car in the simulator: opportunistic stops, frozen order, restart gaps, cheap stops."""

from pathlib import Path

import numpy as np

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.interfaces import Plan
from f1si.pace.linear import fit_linear_pace, measure_pit_loss
from f1si.rng import make_rng
from f1si.sim.constants import RESTART_SPACING_S
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import build_race_state
from f1si.strategy.free_track import FreeTrackOptimizer

from .conftest import ZeroNoisePace, hand_state

NO_STOP = Plan((), (), 0.0)


class _FixedOptimizer(FreeTrackOptimizer):
    """Optimizer double: every car gets the same one-stop plan on lap 4."""

    def rank_plans(self, state, *, driver):  # type: ignore[no-untyped-def]
        return (Plan((4,), ("MEDIUM",), 0.0),)


def _sim(rate: float, duration: int = 3, **kw: object) -> NumpySimulator:
    return NumpySimulator(
        ZeroNoisePace(),
        sc=SafetyCarModel(rate, duration),
        compounds=("HARD", "MEDIUM"),
        **kw,  # type: ignore[arg-type]
    )


def test_opportunistic_stop_moves_to_the_sc_lap_but_forced_does_not() -> None:
    state = hand_state(2, lap=0, laps_total=10, spacing_s=60.0, tire_age=6)
    optimizer = _FixedOptimizer(ZeroNoisePace(), compounds=("HARD", "MEDIUM"))
    free = _sim(1.0, optimizer=optimizer).simulate(state, n_races=8, rng=make_rng(1))
    assert free.stop_laps is not None
    assert free.pit_loss_paid_s is not None
    assert (free.stop_laps[:, 0, 0] == 1).all()
    np.testing.assert_allclose(free.pit_loss_paid_s[:, 0], state.pit_loss_s["sc"])
    forced = _sim(1.0, optimizer=optimizer).simulate(
        state, n_races=8, rng=make_rng(1), plans={"AAA": Plan((4,), ("MEDIUM",), 0.0)}
    )
    assert forced.stop_laps is not None
    assert forced.pit_loss_paid_s is not None
    assert (forced.stop_laps[:, 0, 0] == 4).all()
    np.testing.assert_allclose(forced.pit_loss_paid_s[:, 0], state.pit_loss_s["sc"])
    green = _sim(0.0, optimizer=optimizer).simulate(
        state, n_races=8, rng=make_rng(1), plans={"AAA": Plan((4,), ("MEDIUM",), 0.0)}
    )
    assert green.pit_loss_paid_s is not None
    np.testing.assert_allclose(green.pit_loss_paid_s[:, 0], state.pit_loss_s["green"])


def test_frozen_order_restart_gaps_and_cheap_stop() -> None:
    state = hand_state(4, lap=0, laps_total=3, spacing_s=5.0)
    stop = {"BBB": Plan((2,), ("MEDIUM",), 0.0)}
    sim = _sim(1.0, record_clocks=True)
    res = sim.simulate(state, n_races=8, rng=make_rng(1), plans={**stop})
    assert res.clock_s is not None
    assert res.pit_loss_paid_s is not None
    assert res.sc_lap_mask is not None
    assert res.sc_lap_mask.all()
    np.testing.assert_allclose(res.pit_loss_paid_s[:, 1], state.pit_loss_s["sc"])
    clocks = res.clock_s
    order1 = np.argsort(clocks[:, 0, :], axis=1)
    order2 = np.argsort(clocks[:, 1, :], axis=1)
    keep = np.array([0, 2, 3])
    for r in range(8):
        before = [c for c in order1[r] if c in keep]
        after = [c for c in order2[r] if c in keep]
        assert before == after
    last = np.sort(clocks[:, 2, :], axis=1)
    np.testing.assert_allclose(np.diff(last, axis=1), RESTART_SPACING_S, atol=1e-9)

    def cost(rate: float) -> float:
        stopper = _sim(rate).simulate(state, n_races=32, rng=make_rng(2), plans=stop)
        runner = _sim(rate).simulate(state, n_races=32, rng=make_rng(2), plans={"BBB": NO_STOP})
        return float(np.mean(stopper.total_time_s[:, 1] - runner.total_time_s[:, 1]))

    assert cost(1.0) < cost(0.0)


def test_safety_car_active_at_the_cutoff(sc_history_db: Path) -> None:
    accessor = AsOfAccessor(sc_history_db)
    end = accessor.snapshot(AsOf("2023-06", RACE_END))
    fit = fit_linear_pace(end)
    pit = measure_pit_loss(end, fit)
    state = build_race_state(
        accessor.snapshot(AsOf("2023-06", 11)), fit, laps_total=40, pit_loss_s=pit.median_s
    )
    assert state.regime == {"sc": 1.0}
    assert state.sc_laps_elapsed == 2
    sim = NumpySimulator(fit, sc=SafetyCarModel(0.0, 4), compounds=fit.fitted_compounds)
    res = sim.simulate(state, n_races=32, rng=make_rng(3))
    assert res.sc_lap_mask is not None
    assert res.sc_lap_mask[:, :2].all()
    assert not res.sc_lap_mask[:, 2:].any()
