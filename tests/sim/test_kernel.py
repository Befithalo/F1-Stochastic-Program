"""Lap kernel: hand cases, safety-car and pit rules, jitted versus Python equality."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from f1si.rng import make_rng
from f1si.sim.constants import (
    MIN_GAP_S,
    PASS_COST_S,
    RESTART_SPACING_S,
    SC_SLOWDOWN,
    SC_STOP_WINDOW_LAPS,
    SCALE_S,
    THRESHOLD_S,
)
from f1si.sim.kernel import lap_step, pass_probability

BIG = 10_000
K = 2
A = 12
S = 2


@dataclass
class Case:
    """Small arrays for `lap_step`; the lap time of car c is `base[c]` on every tyre and age."""

    n: int
    c: int
    base: list[float]
    clock: list[float]
    stop_lap: list[list[int]] = field(default_factory=list)
    next_comp: list[list[int]] = field(default_factory=list)
    opportunistic: list[bool] = field(default_factory=list)
    u_sc: float = 1.0
    pu: float = 0.5
    sc_left: int = 0
    sc_fresh: bool = False
    sc_rate: float = 0.0
    sc_duration: int = 3
    ages: list[int] = field(default_factory=list)

    def build(self) -> dict[str, Any]:
        n, c = self.n, self.c
        mean = np.zeros((c, K, A))
        for i in range(c):
            mean[i] = self.base[i]
        stop_lap = np.array(self.stop_lap or [[BIG] * S] * c, dtype=np.int64)
        next_comp = np.array(self.next_comp or [[1] * S] * c, dtype=np.int64)
        return {
            "mean_tab": mean,
            "sd_tab": np.zeros((c, K, A)),
            "u_sc": np.full(n, self.u_sc),
            "z_off": np.zeros((n, c)),
            "z_wear": np.zeros((n, K)),
            "eps": np.zeros((n, c)),
            "pu": np.full((n, c), self.pu),
            "off_sd": np.zeros(c),
            "wear_sd": np.zeros(K),
            "stop_lap": stop_lap,
            "next_comp": next_comp,
            "opportunistic": np.array(self.opportunistic or [False] * c, dtype=np.bool_),
            "order": np.tile(np.arange(c, dtype=np.int64), (n, 1)),
            "clock": np.tile(np.array(self.clock, dtype=np.float64), (n, 1)),
            "age": np.tile(np.array(self.ages or [3] * c, dtype=np.int64), (n, 1)),
            "comp": np.zeros((n, c), dtype=np.int64),
            "stops_done": np.zeros((n, c), dtype=np.int64),
            "sc_left": np.full(n, self.sc_left, dtype=np.int64),
            "sc_fresh": np.full(n, self.sc_fresh, dtype=np.bool_),
            "pit_paid": np.zeros((n, c)),
            "stop_taken": np.full((n, c, S), -1, dtype=np.int64),
            "sc_mask": np.zeros(n, dtype=np.bool_),
        }


def run(state: dict[str, Any], lap: int = 5, *, python: bool = False, **over: Any) -> None:
    fn = lap_step.py_func if python else lap_step
    a = {**state, **over}
    fn(
        lap,
        a["mean_tab"],
        a["sd_tab"],
        a["u_sc"],
        a["z_off"],
        a["z_wear"],
        a["eps"],
        a["pu"],
        a["off_sd"],
        a["wear_sd"],
        a["stop_lap"],
        a["next_comp"],
        a["opportunistic"],
        a.get("pit_loss_green", 22.0),
        a.get("pit_loss_sc", 11.0),
        a.get("sc_rate", 0.1),
        a.get("sc_duration", 3),
        MIN_GAP_S,
        THRESHOLD_S,
        SCALE_S,
        PASS_COST_S,
        SC_SLOWDOWN,
        RESTART_SPACING_S,
        SC_STOP_WINDOW_LAPS,
        5,
        a["order"],
        a["clock"],
        a["age"],
        a["comp"],
        a["stops_done"],
        a["sc_left"],
        a["sc_fresh"],
        a["pit_paid"],
        a["stop_taken"],
        a["sc_mask"],
    )


def test_no_pass_when_gap_is_large() -> None:
    st = Case(1, 2, [90.0, 90.0], [0.0, 5.0]).build()
    run(st)
    np.testing.assert_allclose(st["clock"][0], [90.0, 95.0])
    assert st["order"][0].tolist() == [0, 1]
    assert st["age"][0].tolist() == [4, 4]


def test_pass_succeeds_with_cost() -> None:
    # Car 0 leads by 0.3 s clock; car 1 is 2 s/lap faster.
    st = Case(1, 2, [90.0, 88.0], [0.0, 0.3], pu=0.0).build()
    run(st)
    assert st["order"][0].tolist() == [1, 0]
    passer = 0.3 + 88.0 + PASS_COST_S
    assert st["clock"][0, 1] == pytest.approx(passer)
    assert st["clock"][0, 0] >= passer + MIN_GAP_S - 1e-12


def test_pass_fails_and_follower_is_held() -> None:
    st = Case(1, 2, [90.0, 90.0], [0.0, 0.3], pu=0.999999).build()
    run(st)
    assert st["order"][0].tolist() == [0, 1]
    assert st["clock"][0, 1] == pytest.approx(st["clock"][0, 0] + MIN_GAP_S)


def test_pit_stop_bookkeeping_and_reordering() -> None:
    case = Case(
        1,
        2,
        [90.0, 90.0],
        [0.0, 1.0],
        stop_lap=[[5, BIG], [BIG, BIG]],
        next_comp=[[1, 1], [1, 1]],
        pu=0.999999,
    )
    st = case.build()
    run(st, lap=5)
    assert st["pit_paid"][0].tolist() == [22.0, 0.0]
    assert st["stops_done"][0].tolist() == [1, 0]
    assert st["age"][0].tolist() == [0, 4]
    assert st["comp"][0].tolist() == [1, 0]
    assert st["stop_taken"][0, 0].tolist() == [5, -1]
    assert st["order"][0].tolist() == [1, 0]
    # Deterministic reordering: the non-pitting car is not charged a pass cost.
    assert st["clock"][0, 1] == pytest.approx(1.0 + 90.0)


def test_sc_start_freezes_order_and_scales_time() -> None:
    st = Case(2, 3, [90.0, 80.0, 85.0], [0.0, 3.0, 6.0], u_sc=0.0, pu=0.0).build()
    st["u_sc"][1] = 0.99
    run(st, sc_rate=0.5)
    assert st["sc_mask"].tolist() == [True, False]
    assert st["sc_left"].tolist() == [2, 0]
    assert st["order"][0].tolist() == [0, 1, 2]
    np.testing.assert_allclose(st["clock"][0], np.array([0.0, 3.0, 6.0]) + SC_SLOWDOWN * 90.0)


def test_no_second_sc_while_active() -> None:
    st = Case(1, 2, [90.0, 90.0], [0.0, 5.0], u_sc=0.0, sc_left=2).build()
    run(st, sc_rate=1.0)
    assert st["sc_left"].tolist() == [1]
    assert st["sc_mask"].tolist() == [True]


def test_sc_pit_loss_and_opportunistic_stop() -> None:
    case = Case(
        1,
        3,
        [90.0, 90.0, 90.0],
        [0.0, 10.0, 20.0],
        stop_lap=[[7, BIG], [7, BIG], [BIG, BIG]],
        u_sc=0.0,
        opportunistic=[True, False, False],
    )
    st = case.build()
    run(st, lap=5, sc_rate=1.0)
    assert st["pit_paid"][0].tolist() == [11.0, 0.0, 0.0]
    assert st["stops_done"][0].tolist() == [1, 0, 0]
    # A planned stop on an SC lap pays the SC loss.
    st2 = Case(1, 2, [90.0, 90.0], [0.0, 10.0], stop_lap=[[5, BIG], [BIG, BIG]], sc_left=2).build()
    run(st2, lap=5)
    assert st2["pit_paid"][0, 0] == 11.0


def test_sc_fresh_counts_as_start() -> None:
    case = Case(
        1,
        2,
        [90.0, 90.0],
        [0.0, 10.0],
        stop_lap=[[8, BIG], [8, BIG]],
        opportunistic=[True, False],
        sc_left=3,
        sc_fresh=True,
    )
    st = case.build()
    run(st, lap=5)
    assert st["pit_paid"][0].tolist() == [11.0, 0.0]
    assert not st["sc_fresh"][0]
    assert st["sc_left"].tolist() == [2]


def test_restart_compression_then_green() -> None:
    st = Case(1, 4, [90.0] * 4, [0.0, 7.0, 15.0, 30.0], sc_left=1).build()
    run(st)
    arrivals = np.sort(st["clock"][0])
    np.testing.assert_allclose(arrivals - arrivals[0], RESTART_SPACING_S * np.arange(4))
    assert st["sc_left"].tolist() == [0]
    run(st, lap=6, u_sc=np.array([1.0]), sc_rate=0.0)
    assert st["sc_mask"].tolist() == [False]


def _random_state(seed: int) -> dict[str, Any]:
    rng = make_rng(seed)
    n, c = 16, 5
    case = Case(
        n,
        c,
        [float(x) for x in rng.uniform(85, 95, c)],
        [float(x) for x in np.sort(rng.uniform(0, 8, c))],
        stop_lap=[[int(rng.integers(3, 9)), BIG] for _ in range(c)],
        next_comp=[[1, 0] for _ in range(c)],
        opportunistic=[bool(x) for x in rng.integers(0, 2, c)],
        sc_duration=3,
    )
    st = case.build()
    st["u_sc"] = rng.random(n)
    st["z_off"] = rng.standard_normal((n, c))
    st["z_wear"] = rng.standard_normal((n, K))
    st["eps"] = rng.standard_normal((n, c))
    st["pu"] = rng.random((n, c))
    st["off_sd"] = rng.uniform(0.0, 0.3, c)
    st["wear_sd"] = rng.uniform(0.0, 0.02, K)
    st["sd_tab"] = rng.uniform(0.1, 0.4, (c, K, A))
    return st


def _copy(st: dict[str, Any]) -> dict[str, Any]:
    return {k: v.copy() for k, v in st.items()}


KEYS = ("order", "clock", "age", "comp", "stops_done", "sc_left", "pit_paid", "stop_taken")


def test_jitted_equals_python() -> None:
    a = _random_state(1)
    b = _copy(a)
    for lap in range(1, 14):
        run(a, lap=lap, sc_rate=0.15)
        run(b, lap=lap, sc_rate=0.15, python=True)
        for key in (*KEYS, "sc_mask", "sc_fresh"):
            assert np.array_equal(a[key], b[key]), (lap, key)


def test_invariants_over_many_laps() -> None:
    st = _random_state(2)
    rng = make_rng(3)
    for lap in range(1, 25):
        st["u_sc"] = rng.random(16)
        st["pu"] = rng.random((16, 5))
        run(st, lap=lap, sc_rate=0.2)
        order: NDArray[np.int64] = st["order"]
        assert (np.sort(order, axis=1) == np.arange(5)).all()
        assert np.isfinite(st["clock"]).all()


@pytest.mark.parametrize("python", [False, True])
def test_clocks_increase_along_order_after_every_green_lap(python: bool) -> None:
    """CR-01: after any lap `clock` is strictly increasing along `order` (DEC-086)."""
    rng = np.random.default_rng(2024)
    n, c = 300, 8
    for _ in range(3 if python else 12):
        base = rng.uniform(88.0, 92.0, size=c).tolist()
        clock0 = np.sort(rng.uniform(0.0, 3.0, size=c)).tolist()
        stops = [[int(rng.integers(1, 6)), BIG] for _ in range(c)]
        st = Case(n, c, base, clock0, stop_lap=stops, pu=0.0).build()
        st["order"] = np.tile(np.arange(c, dtype=np.int64), (n, 1))
        for lap in range(1, 7):
            st["pu"] = rng.random((n, c))
            st["eps"] = rng.normal(0.0, 0.3, size=(n, c))
            run(st, lap=lap, python=python, sc_rate=0.0)
            along = np.take_along_axis(st["clock"], st["order"], axis=1)
            assert (np.diff(along, axis=1) > 0.0).all()
            assert (np.sort(st["order"], axis=1) == np.arange(c)).all()


def test_pass_probability_survives_huge_negative_gap() -> None:
    """WR-02: no OverflowError in the Python twin when the pace gap is hugely negative."""
    for fn in (pass_probability, pass_probability.py_func):
        assert fn(-500.0, THRESHOLD_S, SCALE_S) == 0.0
        assert fn(THRESHOLD_S, THRESHOLD_S, SCALE_S) == pytest.approx(0.5)
