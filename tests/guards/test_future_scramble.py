"""Future-scramble self-checks and the property test over every registered consumer (D-02).

The harness must be strong before its verdicts mean anything, so the first tests check the
scrambler itself (visible rows identical, every future row different, every table covered).
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from f1si.data import _db, schema
from f1si.data.asof import RACE_END, AsOf, RaceEnd
from f1si.data.errors import OutOfSampleLockedError
from f1si.synthetic import default_specs
from tests.guards.consumers import CONSUMERS
from tests.guards.scramble import (
    JUNK_RACE_ID,
    assert_consumers_no_lookahead,
    assert_no_lookahead,
    scramble_future,
)

CURRENT = "2023-02"
TIME_TABLES = tuple(n for n, s in schema.TABLES.items() if s.visibility == "time")
STRUCTURAL_RACE_COLUMNS = {"race_id", "season", "round", "out_of_sample", "load_status"}


@pytest.fixture(scope="module")
def original_tables(synthetic_db: Path) -> dict[str, pd.DataFrame]:
    return _db.read_all_tables(synthetic_db)


def _keyed(table: str, df: pd.DataFrame) -> pd.DataFrame:
    return df.set_index(list(schema.TABLES[table].key)).sort_index()


def _cutoff(tables: dict[str, pd.DataFrame], lap: int) -> float:
    lc = tables["lap_cutoffs"]
    return float(lc.loc[(lc["race_id"] == CURRENT) & (lc["lap"] == lap), "cutoff_s"].iloc[0])


def _assert_all_different(table: str, orig: pd.DataFrame, new: pd.DataFrame) -> None:
    """Every non-key column of every row in `new` differs from the same-key row in `orig`."""
    o, n = _keyed(table, orig), _keyed(table, new)
    common = n.index.intersection(o.index)
    assert len(common) > 0, f"{table}: no surviving future rows to compare"
    for col in n.columns:
        if table == "races" and col in STRUCTURAL_RACE_COLUMNS:
            continue
        a, b = o.loc[common, col], n.loc[common, col]
        same = (a == b).fillna(False).to_numpy(dtype=bool) | (a.isna() & b.isna()).to_numpy()
        assert not same.any(), f"{table}.{col} has an unchanged future value"


def test_harness_covers_every_table(original_tables: dict[str, pd.DataFrame]) -> None:
    scrambled = scramble_future(original_tables, AsOf(CURRENT, 5), rng=np.random.default_rng(1))
    assert set(scrambled) == set(schema.TABLES)
    for name in schema.TABLES:
        assert not _keyed(name, scrambled[name]).equals(_keyed(name, original_tables[name])), name


def test_visible_rows_and_earlier_races_stay_identical(
    original_tables: dict[str, pd.DataFrame],
) -> None:
    scrambled = scramble_future(original_tables, AsOf(CURRENT, 5), rng=np.random.default_rng(2))
    cutoff = _cutoff(original_tables, 5)
    for name in schema.TABLES:
        orig, new = original_tables[name], scrambled[name]
        if name in ("races", "entries"):
            keep = orig["race_id"].isin(["2023-01", CURRENT])
        elif name == "results":
            keep = orig["race_id"] == "2023-01"
        else:
            visible = orig["visible_at_s"].notna() & (orig["visible_at_s"] <= cutoff)
            keep = (orig["race_id"] == "2023-01") | ((orig["race_id"] == CURRENT) & visible)
        want = _keyed(name, orig[keep])
        got = _keyed(name, new).loc[want.index]
        pd.testing.assert_frame_equal(got, want, check_exact=True)


def test_every_future_row_differs_and_stays_future(
    original_tables: dict[str, pd.DataFrame],
) -> None:
    scrambled = scramble_future(original_tables, AsOf(CURRENT, 5), rng=np.random.default_rng(3))
    cutoff = _cutoff(original_tables, 5)
    for name in TIME_TABLES:
        orig = original_tables[name]
        orig_cur = orig[orig["race_id"] == CURRENT]
        was_visible = orig_cur["visible_at_s"].notna() & (orig_cur["visible_at_s"] <= cutoff)
        orig_future = orig_cur[~was_visible]
        now_cur = scrambled[name].query("race_id == @CURRENT")
        orig_keys = set(_keyed(name, orig_cur).index)
        future_keys = set(_keyed(name, orig_future).index)
        now_keys = list(_keyed(name, now_cur).index)
        is_future = [k in future_keys or k not in orig_keys for k in now_keys]
        is_junk = [k not in orig_keys for k in now_keys]
        assert any(is_junk), f"no junk future row with a new key in {name}"
        now_future = _keyed(name, now_cur)[is_future].reset_index()
        assert bool((now_future["visible_at_s"] > cutoff).all()), name
        survivors = now_future[
            [
                k in future_keys
                for k in map(tuple, now_future[list(schema.TABLES[name].key)].to_numpy())
            ]
        ]
        if name in ("laps", "weather"):
            assert len(orig_future) > 0  # these tables always have future rows at lap 5
        if len(orig_future) > 0 and len(survivors) > 0:
            _assert_all_different(name, orig_future, survivors)
    for name in ("entries", "laps", "results"):
        assert JUNK_RACE_ID in set(scrambled[name]["race_id"]), name
    junk_race = scrambled["races"].set_index("race_id").loc[JUNK_RACE_ID]
    assert (junk_race["season"], junk_race["round"]) == (2099, 99)
    assert bool(junk_race["out_of_sample"]) is False
    assert junk_race["load_status"] == "complete"
    laps_keys = [tuple(k) for k in scrambled["laps"][list(schema.TABLES["laps"].key)].to_numpy()]
    assert laps_keys != sorted(laps_keys), "row order was not shuffled"


def test_race_end_leaves_current_race_time_tables_untouched(
    original_tables: dict[str, pd.DataFrame],
) -> None:
    at = AsOf(CURRENT, RACE_END)
    scrambled = scramble_future(original_tables, at, rng=np.random.default_rng(4))
    for name in TIME_TABLES:
        want = _keyed(name, original_tables[name].query("race_id == @CURRENT"))
        got = _keyed(name, scrambled[name].query("race_id == @CURRENT"))
        pd.testing.assert_frame_equal(got, want, check_exact=True)
    # the current race's results and everything later still change
    want_results = original_tables["results"].query("race_id == @CURRENT")
    got_results = scrambled["results"].query("race_id == @CURRENT")
    _assert_all_different("results", want_results, got_results)
    assert JUNK_RACE_ID in set(scrambled["laps"]["race_id"])
    _assert_all_different(
        "entries",
        original_tables["entries"].query("race_id == '2024-01'"),
        scrambled["entries"].query("race_id == '2024-01'"),
    )


@settings(
    deadline=None,
    max_examples=20,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    race=st.sampled_from(["2023-01", "2023-02", "2024-01"]),
    lap=st.integers(0, 12) | st.just(RACE_END),
    seed=st.integers(0, 2**32 - 1),
    consumer=st.sampled_from(sorted(CONSUMERS)),
)
def test_consumers_ignore_the_future(
    original_tables: dict[str, pd.DataFrame],
    race: str,
    lap: int | RaceEnd,
    seed: int,
    consumer: str,
) -> None:
    rng = np.random.default_rng(seed)
    assert_no_lookahead(CONSUMERS[consumer], original_tables, AsOf(race, lap), rng=rng)


def _full_grid() -> list[tuple[str, int | RaceEnd]]:
    """Every in-sample synthetic race at every lap 0..n_laps, plus RACE_END (WR-02)."""
    grid: list[tuple[str, int | RaceEnd]] = []
    for spec in default_specs():
        if spec.season >= 2026:
            continue  # locked race; covered by test_locked_race_raises_identically
        race_id = f"{spec.season}-{spec.round:02d}"
        grid += [(race_id, lap) for lap in range(spec.n_laps + 1)]
        grid.append((race_id, RACE_END))
    return grid


_GRID = _full_grid()


@pytest.mark.parametrize(("race", "lap"), _GRID, ids=[f"{race}-{lap!r}" for race, lap in _GRID])
def test_every_consumer_ignores_the_future_on_the_full_grid(
    original_tables: dict[str, pd.DataFrame], race: str, lap: int | RaceEnd
) -> None:
    """Deterministic: every registered consumer at every race and lap, not a random sample.

    The seed depends only on (race, lap), so a failure reproduces exactly. The random Hypothesis
    test above still explores other seeds.
    """
    seed = int(race.replace("-", "")) * 100 + (99 if isinstance(lap, RaceEnd) else lap)
    assert_consumers_no_lookahead(
        CONSUMERS, original_tables, AsOf(race, lap), rng=np.random.default_rng(seed)
    )


def test_grid_covers_every_in_sample_race(original_tables: dict[str, pd.DataFrame]) -> None:
    """The grid is built from the specs; it must match what the database actually holds."""
    races = original_tables["races"]
    in_sample = set(races.loc[~races["out_of_sample"].astype(bool), "race_id"])
    assert {race for race, _ in _GRID} == in_sample
    lc = original_tables["lap_cutoffs"]
    for race in in_sample:
        last = int(lc.loc[lc["race_id"] == race, "lap"].max())
        assert {lap for r, lap in _GRID if r == race and not isinstance(lap, RaceEnd)} == set(
            range(last + 1)
        ), race


def test_locked_race_raises_identically(original_tables: dict[str, pd.DataFrame]) -> None:
    """A 2026 race is locked at every lap; asserted explicitly, not compared (WR-01)."""
    locked = {"snapshot": OutOfSampleLockedError, "history": OutOfSampleLockedError}
    for lap in (0, 5, RACE_END):
        assert_consumers_no_lookahead(
            {name: CONSUMERS[name] for name in locked},
            original_tables,
            AsOf("2026-01", lap),
            rng=np.random.default_rng(7),
            expect_error=locked,
        )
