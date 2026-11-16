"""build_race_state: lap 0, mid race, race end, unknown values and purity (INT-03, D-14, D-23)."""

import dataclasses
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from f1si.data import _db
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, RaceSnapshot
from f1si.pace.kalman import FilterSnapshot
from f1si.pace.linear import fit_linear_pace
from f1si.regime.markov import RegimeEstimate
from f1si.state import SC_PIT_LOSS_RATIO, RaceState, build_race_state
from tests.conftest import LONG_RACE_ID, SC_HISTORY_CURRENT_RACE_ID

LAPS_TOTAL = 57


def _snap(db: Path, lap: int | None) -> RaceSnapshot:
    at = AsOf(LONG_RACE_ID, RACE_END if lap is None else lap)
    return AsOfAccessor(db).snapshot(at)


def test_lap_zero(long_synthetic_db: Path) -> None:
    fit = fit_linear_pace(_snap(long_synthetic_db, None))
    state = build_race_state(
        _snap(long_synthetic_db, 0), fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0
    )
    assert state.lap == 0
    assert state.laps_total == LAPS_TOTAL
    assert len(state.cars) == 20
    for car in state.cars:
        assert car.position is None
        assert car.gap_ahead_s is None
        assert car.gap_behind_s is None
        assert car.compound == "MEDIUM"
        assert car.tire_age == 3
        assert car.stops_done == 0
        assert car.compounds_used == ("MEDIUM",)
        assert car.wear_rate_s_per_lap == fit.wear_rate("MEDIUM")
        assert car.wear_sd == fit.wear_se("MEDIUM")
        assert car.pace_offset_s == fit.pace_offset(car.driver_number)


def test_mid_race(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, 40)
    fit = fit_linear_pace(snap)
    assert fit.is_identified
    state = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    assert state.lap == 40
    assert [c.position for c in state.cars] == list(range(1, 21))
    assert state.cars[0].gap_ahead_s is None
    assert state.cars[-1].gap_behind_s is None
    for a, b in zip(state.cars, state.cars[1:], strict=False):
        assert b.gap_ahead_s is None or b.gap_ahead_s > 0
        assert a.gap_behind_s == b.gap_ahead_s
    assert any(c.gap_ahead_s is not None for c in state.cars)
    stopped = [c for c in state.cars if c.stops_done == 1]
    assert stopped
    stints = snap.stints
    for car in stopped:
        assert car.compound == "HARD"
        assert car.compounds_used == ("MEDIUM", "HARD")
        mine = stints[stints["driver_number"] == car.driver_number].sort_values("stint")
        assert car.tire_age == int(mine.iloc[-1]["tyre_life_now"])
    assert dict(state.regime) == {"green": 1.0}
    assert set(state.pit_loss_s) == {"green", "sc"}
    assert state.pit_loss_s["sc"] == 0.5 * state.pit_loss_s["green"]
    assert state.sc_laps_elapsed == 0


def test_started_pit_outlap_is_new_compound_age_zero_and_counted(
    long_synthetic_db: Path,
) -> None:
    laps = _db.read_table(long_synthetic_db, "laps", race_id=LONG_RACE_ID)
    cutoffs = _db.read_table(long_synthetic_db, "lap_cutoffs", race_id=LONG_RACE_ID)
    candidate: tuple[int, int, int, float, str] | None = None
    for cutoff in cutoffs.itertuples(index=False):
        in_progress = laps[
            laps["is_pit_out_lap"].fillna(False)
            & (laps["lap_start_s"] <= cutoff.cutoff_s)
            & (laps["lap_end_s"] > cutoff.cutoff_s)
        ]
        if not in_progress.empty:
            row = in_progress.iloc[0]
            candidate = (
                int(cast(Any, cutoff.lap)),
                int(row["driver_number"]),
                int(row["lap_number"]),
                float(cast(Any, cutoff.cutoff_s)),
                str(row["compound"]),
            )
            break
    assert candidate is not None, "synthetic race should include a cutoff inside a pit out-lap"
    lap, driver_number, out_lap_number, _cutoff_s, compound = candidate

    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf(LONG_RACE_ID, lap))
    assert not (
        (snapshot.laps["driver_number"] == driver_number)
        & (snapshot.laps["lap_number"] == out_lap_number)
    ).any()
    started_stint = snapshot.stints.loc[
        (snapshot.stints["driver_number"] == driver_number)
        & (snapshot.stints["first_lap"] == out_lap_number)
    ].iloc[0]
    assert started_stint["compound"] == compound
    assert started_stint["laps_so_far"] == 0
    assert started_stint["tyre_life_now"] == 0
    assert (
        (snapshot.pit_events["driver_number"] == driver_number)
        & (snapshot.pit_events["out_lap"] == out_lap_number)
    ).any()
    fit = fit_linear_pace(snapshot)
    state = build_race_state(
        snapshot,
        fit,
        laps_total=int(cutoffs["lap"].max()),
        pit_loss_s=22.0,
    )
    car = next(car for car in state.cars if car.driver_number == driver_number)

    assert car.laps_done == out_lap_number - 1
    assert car.compound == compound
    assert car.tire_age == 0
    assert car.stops_done >= 1


def test_last_lap_round_trips(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, None)
    state = build_race_state(snap, fit_linear_pace(snap), laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    assert state.lap == LAPS_TOTAL
    assert RaceState.from_json(state.to_json()) == state


def test_markov_state_json_round_trips_transition_and_regime_costs(long_synthetic_db: Path) -> None:
    snapshot = _snap(long_synthetic_db, 40)
    state = build_race_state(
        snapshot, fit_linear_pace(snapshot), laps_total=LAPS_TOTAL, pit_loss_s=22.0
    )
    transition = np.eye(5, dtype=np.float64)
    costs = np.array([22.0, 16.5, 11.0, 22.0, 22.0])
    marked = dataclasses.replace(state, regime_transition=transition, pit_loss_by_regime_s=costs)

    restored = RaceState.from_json(marked.to_json())

    assert restored.regime_transition is not None
    assert restored.pit_loss_by_regime_s is not None
    np.testing.assert_array_equal(restored.regime_transition, transition)
    np.testing.assert_array_equal(restored.pit_loss_by_regime_s, costs)
    assert restored.regime_transition.flags.c_contiguous
    assert not restored.regime_transition.flags.writeable
    assert restored == marked


def test_markov_state_builder_keeps_all_regime_costs_and_visible_regime(
    long_synthetic_db: Path,
) -> None:
    snapshot = _snap(long_synthetic_db, 40)
    transition = np.full((5, 5), 0.2, dtype=np.float64)
    estimate = RegimeEstimate(transition, np.zeros((5, 5)), 0)

    state = build_race_state(
        snapshot,
        fit_linear_pace(snapshot),
        laps_total=LAPS_TOTAL,
        pit_loss_s=24.0,
        regime_estimate=estimate,
    )

    assert dict(state.regime) == {"green": 1.0}
    np.testing.assert_array_equal(state.regime_transition, transition)
    np.testing.assert_array_equal(state.pit_loss_by_regime_s, [24.0, 18.0, 12.0, 24.0, 24.0])
    restored = RaceState.from_json(state.to_json())
    assert dict(restored.regime) == {"green": 1.0}
    np.testing.assert_array_equal(restored.pit_loss_by_regime_s, [24.0, 18.0, 12.0, 24.0, 24.0])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("regime_transition", [[1.0, 0.0], [0.0, 1.0]], "5x5"),
        ("regime_transition", [[0.1] * 5] * 5, "sum to one"),
        ("pit_loss_by_regime_s", [22.0, 16.5, 11.0, 22.0, float("inf")], "finite"),
        ("pit_loss_by_regime_s", [22.0, 16.5, 11.0, 22.0, 0.0], "finite positive"),
    ],
)
def test_markov_state_rejects_invalid_numeric_inputs(
    long_synthetic_db: Path, field: str, value: object, message: str
) -> None:
    snapshot = _snap(long_synthetic_db, 40)
    state = build_race_state(
        snapshot, fit_linear_pace(snapshot), laps_total=LAPS_TOTAL, pit_loss_s=22.0
    )
    marked = dataclasses.replace(
        state,
        regime_transition=np.eye(5),
        pit_loss_by_regime_s=np.array([22.0, 16.5, 11.0, 22.0, 22.0]),
    )
    with pytest.raises(ValueError, match=message):
        dataclasses.replace(marked, **{field: cast(Any, value)})


def test_markov_state_requires_a_one_hot_cutoff_regime(long_synthetic_db: Path) -> None:
    snapshot = _snap(long_synthetic_db, 40)
    state = build_race_state(
        snapshot, fit_linear_pace(snapshot), laps_total=LAPS_TOTAL, pit_loss_s=22.0
    )

    with pytest.raises(ValueError, match="one-hot"):
        dataclasses.replace(
            state,
            regime={"green": 0.5, "sc": 0.5},
            regime_transition=np.eye(5),
            pit_loss_by_regime_s=np.array([22.0, 16.5, 11.0, 22.0, 22.0]),
        )


def test_gap_not_positive_becomes_none(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, 40)
    fit = fit_linear_pace(snap)
    base = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    behind = next(c for c in base.cars if c.gap_ahead_s is not None)
    ahead = base.cars[(behind.position or 0) - 2]
    assert ahead.position == (behind.position or 0) - 1
    done = dict(zip(snap.cars["driver_number"], snap.cars["laps_done"], strict=True))
    common = min(int(done[behind.driver_number]), int(done[ahead.driver_number]))

    def with_end(value: float) -> RaceSnapshot:
        laps = snap.laps.copy()
        row = (laps["driver_number"] == ahead.driver_number) & (laps["lap_number"] == common)
        ref = laps[(laps["driver_number"] == behind.driver_number) & (laps["lap_number"] == common)]
        laps.loc[row, "lap_end_s"] = float(ref["lap_end_s"].iloc[0]) + value
        return dataclasses.replace(snap, laps=laps)

    for shift in (5.0, 0.0):  # ahead later than behind, and exactly level
        state = build_race_state(with_end(shift), fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
        assert state.car(behind.driver).gap_ahead_s is None
        assert state.car(ahead.driver).gap_behind_s is None
        for car in state.cars:
            assert car.gap_ahead_s is None or car.gap_ahead_s > 0
            assert car.gap_behind_s is None or car.gap_behind_s > 0


def test_laps_total_below_lap_raises(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, 40)
    with pytest.raises(ValueError, match="race distance"):
        build_race_state(snap, fit_linear_pace(snap), laps_total=30, pit_loss_s=22.0)


def test_unidentified_fit_gives_none_not_invented(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, 20)
    fit = fit_linear_pace(snap)
    assert not fit.is_identified
    state = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    for car in state.cars:
        assert car.wear_rate_s_per_lap is None
        assert car.wear_sd is None
        assert car.pace_offset_s is None


def test_pure_and_does_not_mutate(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, 40)
    fit = fit_linear_pace(snap)
    before = {name: getattr(snap, name).copy() for name in ("cars", "laps", "stints", "entries")}
    first = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    second = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    assert first == second
    for name, frame in before.items():
        pd.testing.assert_frame_equal(frame, getattr(snap, name))


def test_pace_offset_sd_filled_from_fit(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, 40)
    fit = fit_linear_pace(snap)
    state = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    for car in state.cars:
        assert car.pace_offset_sd == fit.pace_offset_se(car.driver_number)
    assert any(c.pace_offset_sd is not None for c in state.cars)
    assert RaceState.from_json(state.to_json()).cars[0].pace_offset_sd == (
        state.cars[0].pace_offset_sd
    )


def _sc_state(db: Path, lap: int) -> RaceState:
    at = AsOf(SC_HISTORY_CURRENT_RACE_ID, lap)
    snap = AsOfAccessor(db).snapshot(at)
    fit = fit_linear_pace(AsOfAccessor(db).snapshot(AsOf(SC_HISTORY_CURRENT_RACE_ID, RACE_END)))
    return build_race_state(snap, fit, laps_total=40, pit_loss_s=22.0)


def test_safety_car_regime_follows_the_cutoff(sc_history_db: Path) -> None:
    before = _sc_state(sc_history_db, 9)
    assert dict(before.regime) == {"green": 1.0}
    assert before.sc_laps_elapsed == 0
    for lap, elapsed in ((10, 1), (11, 2), (12, 3)):
        state = _sc_state(sc_history_db, lap)
        assert dict(state.regime) == {"sc": 1.0}
        assert state.sc_laps_elapsed == elapsed
        assert state.pit_loss_s["sc"] == SC_PIT_LOSS_RATIO * 22.0
    after = _sc_state(sc_history_db, 14)
    assert dict(after.regime) == {"green": 1.0}
    assert after.sc_laps_elapsed == 0


def _filter_snapshot(
    rate: float, sd: float, cutoff: int, *, prior_only: bool = False
) -> FilterSnapshot:
    return FilterSnapshot(rate, sd, 5, prior_only, cutoff)


def test_wear_filter_fills_rate_sd_and_source(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, 40)
    fit = fit_linear_pace(snap)
    base = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    a, b, c = base.cars[0], base.cars[1], base.cars[2]
    flt = {
        a.driver_number: _filter_snapshot(0.09, 0.011, 40),
        b.driver_number: _filter_snapshot(0.05, 0.02, 40, prior_only=True),
    }
    state = build_race_state(
        snap,
        fit,
        laps_total=LAPS_TOTAL,
        pit_loss_s=22.0,
        wear_filter=flt,
    )
    assert state.cars[0].wear_rate_s_per_lap == 0.09
    assert state.cars[0].wear_sd == 0.011
    assert state.cars[0].wear_source == "filter"
    assert state.cars[1] == b
    assert state.cars[2] == c
    assert state.cars[1].wear_source == "fit"
    assert RaceState.from_json(state.to_json()) == state


def test_wear_filter_none_equals_default(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, 40)
    fit = fit_linear_pace(snap)
    plain = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    none = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0, wear_filter=None)
    assert plain == none


def test_wear_filter_cutoff_mismatch_raises(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, 40)
    fit = fit_linear_pace(snap)
    with pytest.raises(ValueError, match=r"39.*40"):
        build_race_state(
            snap,
            fit,
            laps_total=LAPS_TOTAL,
            pit_loss_s=22.0,
            wear_filter={1: _filter_snapshot(0.09, 0.011, 39)},
        )


def test_wear_filter_ignored_for_unknown_compound(long_synthetic_db: Path) -> None:
    snap = _snap(long_synthetic_db, 0)
    fit = fit_linear_pace(snap)
    base = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    number = base.cars[0].driver_number
    unknown = dataclasses.replace(snap, entries=snap.entries.assign(start_compound=None))
    st = build_race_state(
        unknown,
        fit,
        laps_total=LAPS_TOTAL,
        pit_loss_s=22.0,
        wear_filter={number: _filter_snapshot(0.09, 0.011, 0)},
    )
    car = next(c for c in st.cars if c.driver_number == number)
    assert car.compound is None
    assert car.wear_source == "fit"
    assert car.wear_rate_s_per_lap is None


def test_wear_filter_entry_for_another_compound_is_ignored(long_synthetic_db: Path) -> None:
    """WR-04: a filter snapshot of the previous tyre must not replace the current tyre's fit."""
    snap = _snap(long_synthetic_db, 40)
    fit = fit_linear_pace(snap)
    base = build_race_state(snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0)
    a = base.cars[0]
    assert a.compound is not None
    other = "SOFT" if a.compound != "SOFT" else "HARD"
    stale = dataclasses.replace(_filter_snapshot(0.09, 0.011, 40), compound=other)
    same = dataclasses.replace(_filter_snapshot(0.09, 0.011, 40), compound=a.compound)
    ignored = build_race_state(
        snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0, wear_filter={a.driver_number: stale}
    )
    assert ignored.cars[0] == a
    assert ignored.cars[0].wear_source == "fit"
    used = build_race_state(
        snap, fit, laps_total=LAPS_TOTAL, pit_loss_s=22.0, wear_filter={a.driver_number: same}
    )
    assert used.cars[0].wear_source == "filter"
    assert used.cars[0].wear_rate_s_per_lap == 0.09
    assert RaceState.from_json(used.to_json()) == used
