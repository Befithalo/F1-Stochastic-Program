"""Filter cars in the NumPy simulator: byte identity for fit cars, direction, spread, CRN (DEC-094).

A car with `wear_source == "filter"` runs its current tyres on a virtual compound column with its
own rate (incremental correction from the cutoff age), its own wear SD and its own normal from a
fifth spawned stream. Statistical tolerances are 3 standard errors (means) or 10% (SD) and are
stated in each docstring; none was loosened to pass.
"""

from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from f1si.interfaces import Plan
from f1si.rng import make_rng
from f1si.sim import numpy_backend
from f1si.sim.draws import car_wear_draws, make_streams, normal_block
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import RaceState
from f1si.strategy.free_track import MIN_STINT_LAPS

from .conftest import ZeroNoisePace, hand_state, with_car
from .test_crn_and_plans import NoisyPace
from .test_kernel import Case, run
from .test_phase3_reference import NPZ, _run

SLOPE = 0.05  # age slope of ZeroNoisePace, s per lap
NO_STOP = Plan((), (), 0.0)
NUMBERS = (7, 14, 21)  # equal pace offsets (number % 7 == 0), so cars differ only by wear


def _sim(rate: float = 0.0, **kw: Any) -> NumpySimulator:
    return NumpySimulator(
        kw.pop("pace", ZeroNoisePace()),
        sc=SafetyCarModel(rate, 3),
        compounds=("HARD", "MEDIUM"),
        **kw,
    )


def _filter(state: RaceState, index: int, rate: float, sd: float | None) -> RaceState:
    return with_car(state, index, wear_rate_s_per_lap=rate, wear_sd=sd, wear_source="filter")


def _forced(state: RaceState) -> dict[str, Plan]:
    return {c.driver: NO_STOP for c in state.cars}


def _two_cars(laps_total: int = 12, spacing: float = 60.0, tire_age: int = 0) -> RaceState:
    return hand_state(
        2, lap=0, laps_total=laps_total, spacing_s=spacing, tire_age=tire_age, numbers=NUMBERS[:2]
    )


def _total(state: RaceState, n: int = 3000, seed: int = 11, **kw: Any) -> NDArray[np.float64]:
    res = _sim(**kw).simulate(state, n_races=n, rng=make_rng(seed), plans=_forced(state))
    return res.total_time_s


def test_fit_cars_unchanged_when_no_filter_car() -> None:
    """The Phase 3 reference scenario, also with wear_source "fit" and wear fields set."""
    ref = np.load(NPZ)
    finish, total = _run()
    assert np.array_equal(finish, ref["finish_positions"])
    assert np.allclose(total, ref["total_time_s"], rtol=0, atol=1e-9)
    state = hand_state(6, lap=3, laps_total=12, spacing_s=2.0, tire_age=3)
    for i in range(6):
        state = with_car(state, i, wear_rate_s_per_lap=0.09, wear_sd=0.02, wear_source="fit")
    sim = _sim(0.05, wear_sd_by_compound={"HARD": 0.01, "MEDIUM": 0.01})
    res = sim.simulate(state, n_races=256, rng=make_rng(20260101))
    assert np.array_equal(res.finish_positions, ref["finish_positions"])
    assert np.allclose(res.total_time_s, ref["total_time_s"], rtol=0, atol=1e-9)


def test_higher_filtered_rate_finishes_worse() -> None:
    """Mean total time rises by (rate - 0.04) * n(n+1)/2 over a fit car; tolerance 3 SE."""
    n_laps = 12
    tri = n_laps * (n_laps + 1) / 2
    base = _two_cars(n_laps)
    state = _filter(_filter(base, 0, 0.04, 0.01), 1, 0.12, 0.01)
    n = 3000
    fit_total = _total(base, n)
    filt_total = _total(state, n)
    for col, rate in ((0, 0.04), (1, 0.12)):
        extra = filt_total[:, col] - fit_total[:, col]
        expected = (rate - SLOPE) * tri
        se = filt_total[:, col].std(ddof=1) / np.sqrt(n)
        assert abs(extra.mean() - expected) < 3 * se + 1e-9
    gap = filt_total[:, 1].mean() - filt_total[:, 0].mean()
    assert gap == pytest.approx((fit_total[:, 1] - fit_total[:, 0]).mean() + 0.08 * tri, abs=0.5)
    # mean finish: B starts level with A but is slower, so it is never better
    close = _filter(_filter(_two_cars(20, spacing=1.0), 0, 0.04, 0.005), 1, 0.12, 0.005)
    res = _sim().simulate(close, n_races=2000, rng=make_rng(5), plans=_forced(close))
    finish = res.finish_positions.mean(axis=0)
    assert finish[1] >= finish[0]


def test_larger_sd_widens_spread() -> None:
    """Total-time SD of a filter car equals SD * n(n+1)/2 (laps run after the cutoff), 10%."""
    n_laps = 12
    tri = n_laps * (n_laps + 1) / 2
    base = _two_cars(n_laps)
    state = _filter(_filter(base, 0, SLOPE, 0.002), 1, SLOPE, 0.02)
    total = _total(state, 4000)
    sds = total.std(axis=0, ddof=1)
    assert sds[0] == pytest.approx(0.002 * tri, rel=0.10)
    assert sds[1] == pytest.approx(0.02 * tri, rel=0.10)
    assert sds[1] / sds[0] == pytest.approx(10.0, rel=0.10)
    se = sds / np.sqrt(total.shape[0])
    fit_total = _total(base, 4000)
    assert abs(total[:, 0].mean() - fit_total[:, 0].mean()) < 3 * se[0] + 1e-6
    assert abs(total[:, 1].mean() - fit_total[:, 1].mean()) < 3 * se[1] + 1e-6


def test_spread_ignores_laps_already_run() -> None:
    """Same rate and SD at tyre age 0 and 10: SD within 5%, means differ by slope * 10 per lap."""
    n_laps = 12
    state = _two_cars(n_laps)
    state = with_car(state, 1, tire_age=10)
    state = _filter(_filter(state, 0, SLOPE, 0.01), 1, SLOPE, 0.01)
    total = _total(state, 4000)
    sds = total.std(axis=0, ddof=1)
    assert sds[1] == pytest.approx(sds[0], rel=0.05)
    fit_state = with_car(_two_cars(n_laps), 1, tire_age=10)
    fit_total = _total(fit_state, 4000)
    mean_gap = total[:, 1].mean() - total[:, 0].mean()
    fit_gap = fit_total[:, 1].mean() - fit_total[:, 0].mean()
    assert mean_gap == pytest.approx(fit_gap, abs=1e-6)
    assert mean_gap - 60.0 == pytest.approx(SLOPE * 10 * n_laps, abs=1e-6)


def test_sc_stop_decision_matches_fit_car() -> None:
    """A filter car keeps the real tyre age, so the min_stint rule decides as for a fit car."""
    state = hand_state(2, lap=10, laps_total=40, spacing_s=60.0, numbers=NUMBERS[:2])
    state = with_car(state, 0, tire_age=12)
    state = with_car(state, 1, tire_age=2)
    filt = _filter(with_car(state, 1, wear_source="fit"), 0, SLOPE, 0.01)
    filt = _filter(filt, 1, SLOPE, 0.01)
    fit = state
    kw: dict[str, Any] = {"wear_sd_by_compound": {"HARD": 0.01, "MEDIUM": 0.01}}
    res_f = _sim(0.1, **kw).simulate(filt, n_races=1500, rng=make_rng(3))
    res_b = _sim(0.1, **kw).simulate(fit, n_races=1500, rng=make_rng(3))
    assert res_f.stop_laps is not None
    assert res_b.stop_laps is not None
    assert np.array_equal(res_f.stop_laps, res_b.stop_laps)
    stops = res_f.stop_laps
    planned = np.bincount(stops[:, 0, 0][stops[:, 0, 0] > 0]).argmax()
    assert (stops[:, 0, 0] != planned).any(), "no opportunistic stop happened; test is vacuous"
    for car, age0 in ((0, 12), (1, 2)):
        taken = stops[:, car, 0]
        taken = taken[taken > 0]
        age_before_pit = age0 + (taken - state.lap - 1)
        assert (age_before_pit + 1 >= MIN_STINT_LAPS).all()


def test_kernel_jit_equals_py_func_with_wear_age_off() -> None:
    """Jitted and Python kernels agree with a nonzero offset; zeros equal the old expression."""
    rng = make_rng(8)
    n, c = 4, 2
    case = Case(n, c, [90.0, 91.0], [0.0, 300.0], ages=[3, 5])
    jit_st = case.build()
    jit_st["z_wear"] = rng.standard_normal((n, 2))
    jit_st["wear_sd"] = np.array([0.01, 0.02])
    jit_st["comp"][:, 1] = 1
    jit_st["age"][:] = np.array([3, 9])
    off = np.array([0, 7], dtype=np.int64)
    py_st = {k: v.copy() for k, v in jit_st.items()}
    run(jit_st, wear_age_off=off)
    run(py_st, wear_age_off=off, python=True)
    for key in ("clock", "age", "comp", "order"):
        assert np.array_equal(jit_st[key], py_st[key])
    free1 = 91.0 + jit_st["z_wear"][:, 1] * 0.02 * (9 + 1 - 7)
    assert np.array_equal(jit_st["clock"][:, 1], 300.0 + free1)
    # all-zero offsets give the pre-change expression z * sd * (age + 1)
    base = case.build()
    base["z_wear"] = jit_st["z_wear"].copy()
    base["wear_sd"] = np.array([0.01, 0.02])
    base["comp"][:, 1] = 1
    base["age"][:] = np.array([3, 9])
    run(base, wear_age_off=np.zeros(2, dtype=np.int64))
    expected = 300.0 + (91.0 + base["z_wear"][:, 1] * 0.02 * (9 + 1))
    assert np.array_equal(base["clock"][:, 1], expected)


def test_no_filter_car_takes_phase3_path_exactly(monkeypatch: pytest.MonkeyPatch) -> None:
    """No filter car: nothing spawned beyond make_streams, Phase 3 table shapes, same output."""

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("filter path must not run without a filter car")

    monkeypatch.setattr(numpy_backend, "_filter_car_columns", boom)
    monkeypatch.setattr(numpy_backend, "car_wear_draws", boom)
    seen: dict[str, tuple[int, ...]] = {}
    original = NumpySimulator._check_kernel_inputs

    def spy(
        mean_tab: Any, stop_lap: Any, next_comp: Any, n_comp: int, n_cars: int, *a: Any
    ) -> None:
        seen["mean"] = mean_tab.shape
        seen["z_wear"] = a[2].shape
        seen["n_comp"] = (n_comp,)
        original(mean_tab, stop_lap, next_comp, n_comp, n_cars, *a)

    monkeypatch.setattr(NumpySimulator, "_check_kernel_inputs", staticmethod(spy))
    state = hand_state(6, lap=3, laps_total=12, spacing_s=2.0, tire_age=3)
    state = with_car(state, 0, wear_rate_s_per_lap=0.1, wear_sd=0.02, wear_source="fit")
    rng = make_rng(20260101)
    sim = _sim(0.05, wear_sd_by_compound={"HARD": 0.01, "MEDIUM": 0.01})
    res = sim.simulate(
        hand_state(6, lap=3, laps_total=12, spacing_s=2.0, tire_age=3), n_races=256, rng=rng
    )
    sim.simulate(state, n_races=8, rng=make_rng(1))
    assert rng.bit_generator.seed_seq.n_children_spawned == 4  # type: ignore[attr-defined]
    fresh = make_rng(20260101)
    make_streams(fresh, 9)
    assert fresh.bit_generator.seed_seq.n_children_spawned == 4  # type: ignore[attr-defined]
    assert seen["mean"][2] == 2
    assert seen["n_comp"] == (2,)
    assert seen["z_wear"] == (8, 2)
    ref = np.load(NPZ)
    assert np.array_equal(res.finish_positions, ref["finish_positions"])
    assert np.allclose(res.total_time_s, ref["total_time_s"], rtol=0, atol=1e-9)


def test_level_continuous_at_cutoff() -> None:
    """The correction is incremental: first lap gains delta * 1, not delta * tyre age."""
    state = hand_state(2, lap=4, laps_total=5, spacing_s=60.0, tire_age=15, numbers=NUMBERS[:2])
    fit_total = _total(state, 64)
    same = _total(_filter(state, 0, SLOPE, 0.0), 64)
    assert np.allclose(same[:, 0], fit_total[:, 0], rtol=0, atol=1e-9)
    higher = _total(_filter(state, 0, SLOPE + 0.05, 0.0), 64)
    assert np.allclose(higher[:, 0] - fit_total[:, 0], 0.05, rtol=0, atol=1e-9)
    assert np.allclose(higher[:, 1], fit_total[:, 1], rtol=0, atol=1e-9)


def test_crn_forced_plan_does_not_move_filter_draws() -> None:
    """Another driver's forced plan (new compound too) leaves the filter car's draws alone."""
    state = hand_state(3, lap=0, laps_total=8, spacing_s=60.0, numbers=NUMBERS)
    state = _filter(state, 0, 0.08, 0.02)

    def times(compound: str) -> NDArray[np.float64]:
        plans = {
            state.cars[0].driver: NO_STOP,
            state.cars[1].driver: Plan((4,), (compound,), 0.0),
            state.cars[2].driver: NO_STOP,
        }
        sim = _sim(0.0, pace=NoisyPace(), wear_sd_by_compound={"HARD": 0.02, "MEDIUM": 0.03})
        return sim.simulate(state, n_races=64, rng=make_rng(13), plans=plans).total_time_s

    a, b = times("MEDIUM"), times("SOFT")
    for col in (0, 2):
        assert np.array_equal(a[:, col], b[:, col])
    assert not np.array_equal(a[:, 1], b[:, 1])
    z1 = car_wear_draws(make_rng(2), "sobol_antithetic", 3, 64)
    z2 = car_wear_draws(make_rng(2), "sobol_antithetic", 3, 64)
    assert z1.shape == (64, 3)
    assert np.array_equal(z1, z2)


def test_make_streams_children_unchanged() -> None:
    """Calling car_wear_draws after make_streams does not change the four make_streams children."""

    def draw(call: bool) -> list[NDArray[np.float64]]:
        rng = make_rng(77)
        sc, passing, noise = make_streams(rng, 3)
        if call:
            car_wear_draws(rng, "sobol_antithetic", 4, 16)
        gens = [sc, *passing, noise]
        return [normal_block("none", 5, 8, g) for g in gens]

    for x, y in zip(draw(False), draw(True), strict=True):
        assert np.array_equal(x, y)
    rng = make_rng(77)
    make_streams(rng, 3)
    own = car_wear_draws(rng, "none", 5, 8)
    assert not np.array_equal(own, normal_block("none", 5, 8, make_streams(make_rng(77), 3)[0]))


def test_ineligible_filter_car_behaves_as_fit() -> None:
    """wear_sd None, or a stop on the cutoff lap, makes the filter car a fit car."""
    kw: dict[str, Any] = {"wear_sd_by_compound": {"HARD": 0.01, "MEDIUM": 0.01}}
    state = hand_state(2, lap=3, laps_total=10, spacing_s=60.0, numbers=NUMBERS[:2])
    no_sd = _filter(state, 0, 0.12, None)
    fit = with_car(no_sd, 0, wear_source="fit")
    res_a = _sim(**kw).simulate(no_sd, n_races=64, rng=make_rng(4), plans=_forced(state))
    res_b = _sim(**kw).simulate(fit, n_races=64, rng=make_rng(4), plans=_forced(state))
    assert np.array_equal(res_a.total_time_s, res_b.total_time_s)
    # a car that has not finished the cutoff lap and stops on it
    late = hand_state(
        2, lap=3, laps_total=10, spacing_s=60.0, numbers=NUMBERS[:2], laps_done=[None, 2]
    )
    plans = {"AAA": NO_STOP, "BBB": Plan((3,), ("MEDIUM",), 0.0)}
    filt = _filter(late, 1, 0.12, 0.02)
    res_c = _sim(**kw).simulate(filt, n_races=64, rng=make_rng(4), plans=plans)
    res_d = _sim(**kw).simulate(
        with_car(filt, 1, wear_source="fit"), n_races=64, rng=make_rng(4), plans=plans
    )
    assert np.array_equal(res_c.total_time_s, res_d.total_time_s)
    assert res_c.stop_laps is not None
    assert res_d.stop_laps is not None
    assert np.array_equal(res_c.stop_laps, res_d.stop_laps)
