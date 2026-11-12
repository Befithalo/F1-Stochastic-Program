"""NumpySimulator end to end: shapes, conformance, validation, hand case, diagnostics."""

from pathlib import Path

import numpy as np
import pytest

from f1si.interfaces import Plan
from f1si.pace.linear import LinearPaceFit
from f1si.rng import make_rng
from f1si.sim.constants import MAX_CARS, MAX_LAPS, MAX_RACES
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import RaceState
from f1si.strategy.free_track import price_plan_slow
from tests.conformance.registry import SIMULATORS
from tests.conformance.suites import check_simulator_backend

from .conftest import ZeroNoisePace, hand_state


def _fit_sim(fit: LinearPaceFit, **kw: object) -> NumpySimulator:
    return NumpySimulator(
        fit,
        sc=SafetyCarModel(0.01, 4),
        compounds=fit.fitted_compounds,
        wear_sd_by_compound={c: fit.wear_se(c) for c in fit.fitted_compounds},
        **kw,  # type: ignore[arg-type]
    )


def _zero_sim(rate: float = 0.0, **kw: object) -> NumpySimulator:
    return NumpySimulator(
        ZeroNoisePace(),
        sc=SafetyCarModel(rate, 4),
        compounds=("HARD", "MEDIUM"),
        **kw,  # type: ignore[arg-type]
    )


def test_distribution_for_a_chosen_driver(long_lap0: tuple[RaceState, LinearPaceFit]) -> None:
    state, fit = long_lap0
    result = _fit_sim(fit).simulate(state, n_races=500, rng=make_rng(3))
    n_cars = len(state.cars)
    assert result.finish_positions.shape == (500, n_cars)
    assert result.finish_positions.dtype == np.int64
    assert result.total_time_s.dtype == np.float64
    assert (np.sort(result.finish_positions, axis=1) == np.arange(1, n_cars + 1)).all()
    assert np.isfinite(result.total_time_s).all()
    column = [c.driver for c in state.cars].index(state.cars[5].driver)
    pos = result.finish_positions[:, column]
    dist = np.bincount(pos, minlength=n_cars + 1)[1:] / 500
    assert dist.sum() == pytest.approx(1.0)
    assert 1.0 <= pos.mean() <= n_cars


def test_registered_in_conformance(long_synthetic_db: Path) -> None:
    sim, case = SIMULATORS["numpy_sim"](long_synthetic_db)
    check_simulator_backend(sim, case)


def test_validation_errors(long_lap0: tuple[RaceState, LinearPaceFit]) -> None:
    state, fit = long_lap0
    sim = _fit_sim(fit)
    for bad in (0, MAX_RACES + 1):
        with pytest.raises(ValueError, match=str(bad)):
            sim.simulate(state, n_races=bad, rng=make_rng(1))
    with pytest.raises(ValueError, match=str(MAX_CARS + 1)):
        _zero_sim().simulate(hand_state(MAX_CARS + 1), n_races=2, rng=make_rng(1))
    with pytest.raises(ValueError, match=str(MAX_LAPS + 1)):
        _zero_sim().simulate(hand_state(2, laps_total=MAX_LAPS + 1), n_races=2, rng=make_rng(1))
    with pytest.raises(ValueError, match="ZZZ"):
        sim.simulate(state, n_races=2, rng=make_rng(1), plans={"ZZZ": Plan((), (), 0.0)})
    for rate, duration in ((1.5, 4), (-0.1, 4), (0.1, 0)):
        with pytest.raises(ValueError, match=str(rate if duration == 4 else duration)):
            SafetyCarModel(rate, duration)
    with pytest.raises(ValueError, match="bogus"):
        _fit_sim(fit, variance_reduction="bogus")


def test_zero_variance_hand_case() -> None:
    state = hand_state(2, lap=0, laps_total=8, spacing_s=60.0)
    forced = {"AAA": Plan((4,), ("MEDIUM",), 0.0), "BBB": Plan((5,), ("MEDIUM",), 0.0)}
    result = _zero_sim().simulate(state, n_races=16, rng=make_rng(5), plans=forced)
    model = ZeroNoisePace()
    want = [
        price_plan_slow(model, state, "AAA", (4,), ("MEDIUM",)),
        60.0 + price_plan_slow(model, state, "BBB", (5,), ("MEDIUM",)),
    ]
    for col in range(2):
        np.testing.assert_allclose(result.total_time_s[:, col], want[col], atol=1e-9)
    assert (result.finish_positions == np.array([1, 2])).all()


@pytest.mark.parametrize("mode", ["none", "antithetic", "sobol_antithetic"])
def test_variance_reduction_modes_and_odd_n(
    long_lap0: tuple[RaceState, LinearPaceFit], mode: str
) -> None:
    state, fit = long_lap0
    sim = _fit_sim(fit, variance_reduction=mode)
    result = sim.simulate(state, n_races=63, rng=make_rng(2))
    assert result.finish_positions.shape[0] == 63
    assert (np.sort(result.finish_positions, axis=1) == np.arange(1, 21)).all()


def test_diagnostics_shapes(long_lap0: tuple[RaceState, LinearPaceFit]) -> None:
    state, fit = long_lap0
    result = _fit_sim(fit).simulate(state, n_races=32, rng=make_rng(4))
    assert len(result.plan_sources) == len(state.cars)
    assert result.sc_lap_mask is not None
    assert result.sc_lap_mask.shape == (32, 57)
    assert result.stop_laps is not None
    assert result.stop_laps.shape[:2] == (32, 20)
    assert result.stop_laps.shape[2] >= 1
    assert result.pit_loss_paid_s is not None
    assert result.pit_loss_paid_s.shape == (32, 20)
    assert result.clock_s is None
    clocks = _fit_sim(fit, record_clocks=True).simulate(state, n_races=8, rng=make_rng(4))
    assert clocks.clock_s is not None
    assert clocks.clock_s.shape == (8, 57, 20)
    assert np.array_equal(clocks.clock_s[:, -1, :], clocks.total_time_s)


def test_borrowed_pace_is_listed() -> None:
    state = hand_state(3, lap=0, laps_total=20, compound="SOFT", numbers=[1, 2, 81])
    sim = NumpySimulator(
        ZeroNoisePace(),
        sc=SafetyCarModel(0.0, 4),
        compounds=("HARD", "MEDIUM"),
        fitted_drivers=(1, 2),
    )
    result = sim.simulate(state, n_races=8, rng=make_rng(1))
    text = "\n".join(result.diagnostics)
    assert "SOFT pace borrowed from HARD, MEDIUM for 3 cars" in text
    assert "driver 81 not in the fit" in text
    assert all(s.source == "fallback" for s in result.plan_sources)
