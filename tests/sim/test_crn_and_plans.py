"""Forced plans are exact; a forced plan for one driver leaves every other car's draws alone."""

import numpy as np
from numpy.typing import NDArray

from f1si.interfaces import Plan
from f1si.pace.linear import LinearPaceFit
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import RaceState

from .conftest import ZeroNoisePace, hand_state


class NoisyPace(ZeroNoisePace):
    """Deterministic mean with lap-to-lap SD 0.3, so the draws matter."""

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        mean, _ = super().predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)
        return mean, np.full(driver.shape, 0.3, dtype=np.float64)


def test_forced_two_stop_plan_is_followed_exactly(
    long_lap0: tuple[RaceState, LinearPaceFit],
) -> None:
    state, fit = long_lap0
    sim = NumpySimulator(
        fit,
        sc=SafetyCarModel(0.0, 4),
        compounds=fit.fitted_compounds,
        wear_sd_by_compound={c: fit.wear_se(c) for c in fit.fitted_compounds},
    )
    code = state.cars[3].driver
    plan = Plan((15, 35), ("HARD", "MEDIUM"), 0.0)
    result = sim.simulate(state, n_races=64, rng=make_rng(4), plans={code: plan})
    assert result.stop_laps is not None
    assert result.pit_loss_paid_s is not None
    assert (result.stop_laps[:, 3, :2] == np.array([15, 35])).all()
    np.testing.assert_allclose(result.pit_loss_paid_s[:, 3], 2 * state.pit_loss_s["green"])
    sources = {s.driver: s.source for s in result.plan_sources}
    assert sources[code] == "forced"
    assert all(v in ("optimizer", "fallback") for k, v in sources.items() if k != code)


def test_common_random_numbers_across_forced_plans() -> None:
    state = hand_state(3, lap=0, laps_total=8, spacing_s=60.0)
    plan_a = Plan((3,), ("MEDIUM",), 0.0)
    plan_b = Plan((5, 7), ("MEDIUM", "HARD"), 0.0)

    def run(rate: float, plan: Plan) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
        sim = NumpySimulator(NoisyPace(), sc=SafetyCarModel(rate, 3), compounds=("HARD", "MEDIUM"))
        res = sim.simulate(state, n_races=64, rng=make_rng(9), plans={"BBB": plan})
        assert res.sc_lap_mask is not None
        return res.total_time_s, res.sc_lap_mask

    times_a, mask_a = run(0.0, plan_a)
    times_b, mask_b = run(0.0, plan_b)
    for col in (0, 2):
        assert np.array_equal(times_a[:, col], times_b[:, col])
    assert not np.array_equal(times_a[:, 1], times_b[:, 1])
    assert np.array_equal(mask_a, mask_b)
    _, sc_a = run(0.15, plan_a)
    _, sc_b = run(0.15, plan_b)
    assert sc_a.any()
    assert np.array_equal(sc_a, sc_b)


def test_finish_positions_agree_with_clock_ranks() -> None:
    """CR-01: places come from the running order, which matches the clock ranking."""
    state = hand_state(8, lap=0, laps_total=12, spacing_s=0.3)
    sim = NumpySimulator(NoisyPace(), sc=SafetyCarModel(0.05, 3), compounds=("HARD", "MEDIUM"))
    res = sim.simulate(state, n_races=400, rng=make_rng(21))
    ranks = np.argsort(np.argsort(res.total_time_s, axis=1, kind="stable"), axis=1) + 1
    assert (res.finish_positions == ranks).all()


def test_forced_new_compound_leaves_other_draws_alone() -> None:
    """CR-02: a forced plan on a compound outside the fitted set shifts nobody's draws."""
    state = hand_state(3, lap=0, laps_total=8, spacing_s=60.0)
    wear = {"HARD": 0.02, "MEDIUM": 0.03}

    def run(compound: str, rate: float) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
        sim = NumpySimulator(
            NoisyPace(),
            sc=SafetyCarModel(rate, 3),
            compounds=("HARD", "MEDIUM"),
            wear_sd_by_compound=wear,
        )
        plan = Plan((4,), (compound,), 0.0)
        res = sim.simulate(state, n_races=64, rng=make_rng(13), plans={"BBB": plan})
        assert res.sc_lap_mask is not None
        return res.total_time_s, res.sc_lap_mask

    # no safety car: cars 60 s apart never interact, so the other cars' times are pure draws
    times_a, _ = run("MEDIUM", 0.0)
    times_b, _ = run("SOFT", 0.0)
    for col in (0, 2):
        assert np.array_equal(times_a[:, col], times_b[:, col])
    assert not np.array_equal(times_a[:, 1], times_b[:, 1])
    # with a safety car, the SC lap mask (the u_sc draws) is identical too
    _, mask_a = run("MEDIUM", 0.15)
    _, mask_b = run("SOFT", 0.15)
    assert mask_a.any()
    assert np.array_equal(mask_a, mask_b)
