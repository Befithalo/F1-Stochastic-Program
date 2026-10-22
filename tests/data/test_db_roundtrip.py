"""Storage round trip against a real DuckDB file: transactions, NULLs, locks and injection."""

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from f1si.data import _db, schema
from f1si.data.errors import CacheBusyError, CacheMissingError
from tests.data.mini_race import RACE_ID, mini_entries, mini_laps, mini_race_row, mini_tables

_HOLD_LOCK = (
    "import sys, duckdb\n"
    "con = duckdb.connect(sys.argv[1])\n"
    "print('ready', flush=True)\n"
    "sys.stdin.readline()\n"
    "con.close()\n"
)


_MINI_COUNTS = {
    "races": 1,
    "entries": 2,
    "laps": 6,
    "track_status": 2,
    "race_control": 1,
    "weather": 2,
    "lap_cutoffs": 4,
    "results": 2,
}


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "f1si.duckdb"
    _db.write_race(path, mini_race_row(), mini_tables())
    return path


def _count(db: Path, table: str) -> int:
    return int(_db.read_df(db, f"SELECT count(*) AS n FROM {table}")["n"].iloc[0])


def test_round_trip_returns_what_was_written(db: Path) -> None:
    written = {"races": mini_race_row(), **mini_tables()}
    for name in schema.TABLES:
        got = _db.read_table(db, name)
        want = schema.normalize(name, schema.add_visibility(name, written[name]))
        pd.testing.assert_frame_equal(got, want)
    assert set(_db.read_all_tables(db)) == set(schema.TABLES)


def test_every_schema_table_is_covered_by_the_mini_race() -> None:
    assert set(mini_tables()) | {"races"} == set(schema.TABLES)


def test_na_is_stored_as_sql_null(db: Path) -> None:
    n_null = _db.read_df(db, "SELECT count(*) AS n FROM laps WHERE lap_end_s IS NULL")["n"].iloc[0]
    assert n_null == 1
    n_null_vis = _db.read_df(db, "SELECT count(*) AS n FROM laps WHERE visible_at_s IS NULL")
    assert n_null_vis["n"].iloc[0] == 1
    grid = _db.read_df(db, "SELECT count(*) AS n FROM entries WHERE grid_position IS NULL")
    assert grid["n"].iloc[0] == 1


def test_visibility_equals_lap_end(db: Path) -> None:
    laps = _db.read_table(db, "laps")
    pd.testing.assert_series_equal(laps["visible_at_s"], laps["lap_end_s"], check_names=False)


def test_writing_twice_is_idempotent(db: Path) -> None:
    before = {t: _count(db, t) for t in schema.TABLES}
    _db.write_race(db, mini_race_row(), mini_tables())
    assert {t: _count(db, t) for t in schema.TABLES} == before
    assert before == _MINI_COUNTS


def test_failed_write_leaves_no_rows_for_that_race(tmp_path: Path) -> None:
    path = tmp_path / "f1si.duckdb"
    bad = mini_tables()
    bad["laps"] = bad["laps"].drop(columns=["lap_time_s"])
    with pytest.raises(KeyError, match="lap_time_s"):
        _db.write_race(path, mini_race_row(), bad)
    for table in schema.TABLES:
        assert _count(path, table) == 0


def test_failed_rewrite_keeps_the_previous_complete_race(db: Path) -> None:
    bad = mini_tables()
    bad["laps"] = bad["laps"].drop(columns=["lap_time_s"])
    with pytest.raises(KeyError):
        _db.write_race(db, mini_race_row(), bad)
    assert {t: _count(db, t) for t in schema.TABLES} == _MINI_COUNTS


def test_write_race_rejects_missing_or_unknown_tables(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing"):
        _db.write_race(tmp_path / "x.duckdb", mini_race_row(), {"entries": mini_entries()})
    with pytest.raises(ValueError, match="unknown"):
        _db.write_race(
            tmp_path / "x.duckdb", mini_race_row(), {**mini_tables(), "nope": mini_laps()}
        )


def test_stints_view_has_one_row_per_driver_and_stint(db: Path) -> None:
    stints = _db.read_table(db, "stints")
    pairs = stints[["driver_number", "stint"]].astype(int).to_records(index=False).tolist()
    assert pairs == [(10, 1), (10, 2), (11, 1)]
    first = stints.iloc[0]
    assert (first["compound"], first["first_lap"], first["last_lap"], first["n_laps"]) == (
        "MEDIUM",
        1,
        2,
        2,
    )


def test_pit_stops_view_has_one_row_per_real_stop(db: Path) -> None:
    stops = _db.read_table(db, "pit_stops")
    assert len(stops) == 1
    row = stops.iloc[0]
    assert (int(row["driver_number"]), int(row["in_lap"]), int(row["out_lap"])) == (10, 2, 3)
    assert row["pit_duration_s"] == 2.5


def test_read_table_rejects_unknown_names(db: Path) -> None:
    with pytest.raises(ValueError, match="unknown table"):
        _db.read_table(db, "laps; DROP TABLE laps")


def test_quotes_and_drop_table_in_a_value_are_inert(db: Path) -> None:
    evil = "x'; DROP TABLE laps; --"
    assert len(_db.read_table(db, "laps", race_id=evil)) == 0
    assert len(_db.read_df(db, "SELECT * FROM laps WHERE race_id = ?", [evil])) == 0
    assert _count(db, "laps") == 6
    assert len(_db.read_table(db, "laps", race_id=RACE_ID)) == 6


def test_missing_file_raises_cache_missing(tmp_path: Path) -> None:
    with pytest.raises(CacheMissingError, match="uv run f1si load"):
        _db.read_df(tmp_path / "nope.duckdb", "SELECT 1")


def test_completed_race_ids_and_sources(db: Path, tmp_path: Path) -> None:
    assert _db.completed_race_ids(db) == {RACE_ID}
    assert _db.sources_in_cache(db) == {"synthetic"}
    missing = tmp_path / "absent.duckdb"
    assert _db.completed_race_ids(missing) == set()
    assert _db.sources_in_cache(missing) == set()


def test_incomplete_races_are_not_completed(tmp_path: Path) -> None:
    path = tmp_path / "f1si.duckdb"
    _db.write_race(path, mini_race_row(status="partial"), mini_tables())
    assert _db.completed_race_ids(path) == set()


def test_write_tables_replaces_whole_tables(tmp_path: Path) -> None:
    path = tmp_path / "f1si.duckdb"
    _db.write_tables(path, {"races": mini_race_row(), **mini_tables()})
    _db.write_tables(path, {"entries": mini_entries().iloc[:1]})
    assert {t: _count(path, t) for t in schema.TABLES} == {**_MINI_COUNTS, "entries": 1}


@pytest.fixture
def lock_holder(db: Path) -> Iterator[subprocess.Popen[str]]:
    """A child process holding a write connection to the cache."""
    proc = subprocess.Popen(
        [sys.executable, "-I", "-c", _HOLD_LOCK, str(db)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    assert proc.stdout.readline().strip() == "ready"
    try:
        yield proc
    finally:
        if proc.stdin is not None:
            proc.stdin.close()
        proc.wait(timeout=30)
        if proc.stdout is not None:
            proc.stdout.close()


def test_lock_held_by_another_process_raises_cache_busy(
    db: Path, lock_holder: subprocess.Popen[str]
) -> None:
    assert lock_holder.poll() is None
    with pytest.raises(CacheBusyError, match="busy"):
        _db.read_df(db, "SELECT 1")
    with pytest.raises(CacheBusyError):
        _db.write_race(db, mini_race_row(), mini_tables())


@pytest.mark.parametrize(
    ("message", "busy"),
    [
        (
            'IO Error: Could not set lock on file "x.duckdb": Conflicting lock is held in '
            "python (PID 12) by user someone.",
            True,
        ),
        ('IO Error: Cannot open file "x.duckdb": it is being used by another process.', True),
        ("IO Error: File is already open in /usr/bin/python (PID 7)", True),
        ("IO Error: Corrupt database file: computed checksum of block 12 does not match", False),
        ("IO Error: Could not read enough bytes from block 3 of file x.duckdb", False),
        ("IO Error: Cannot open file: No such file or directory", False),
        ("IO Error: unlocked block", False),
    ],
)
def test_only_real_lock_messages_mean_a_busy_cache(message: str, busy: bool) -> None:
    """WR-10: 'block' contains 'lock'; a corrupt file must not look like a busy one."""
    assert _db._is_lock_error(duckdb.IOException(message)) is busy


def test_loader_written_cache_has_cutoffs_and_track_status(synthetic_db: Path) -> None:
    n_cutoffs = _db.read_df(
        synthetic_db, "SELECT count(*) AS n FROM lap_cutoffs WHERE race_id = ?", ["2023-01"]
    )["n"].iloc[0]
    assert n_cutoffs == 13  # 12 laps plus lap 0
    missing = _db.read_df(
        synthetic_db,
        "SELECT count(*) AS n FROM laps WHERE track_status IS NULL "
        "AND lap_start_s IS NOT NULL AND lap_end_s IS NOT NULL",
    )["n"].iloc[0]
    assert missing == 0
    alpha = _db.read_table(synthetic_db, "laps", race_id="2023-01")
    statuses = set(alpha["track_status"].dropna())
    assert "1" in statuses
    assert any("6" in s and "7" in s for s in statuses)


def test_leader_has_lap_n_and_everyone_else_lap_n_minus_1_at_the_cutoff(
    synthetic_db: Path,
) -> None:
    laps = _db.read_table(synthetic_db, "laps", race_id="2023-01")
    cutoffs = _db.read_table(synthetic_db, "lap_cutoffs", race_id="2023-01")
    assert cutoffs["cutoff_s"].iloc[0] == 0.0
    assert cutoffs["cutoff_s"].is_monotonic_increasing
    ends = laps.pivot(index="driver_number", columns="lap_number", values="lap_end_s")
    for n in range(1, int(cutoffs["lap"].max()) + 1):
        cutoff = float(cutoffs.loc[cutoffs["lap"] == n, "cutoff_s"].iloc[0])
        at_n = ends[n].astype(float)
        assert int((at_n == cutoff).sum()) == 1  # exactly one leader completed lap n
        others = at_n[at_n != cutoff]
        assert (others > cutoff).all()  # nobody else has completed lap n yet
        if n >= 2:
            previous = ends[n - 1].astype(float)
            assert (previous <= cutoff).all()  # everyone has completed lap n - 1


def test_every_car_stays_within_one_lap_of_the_leader_in_synthetic_data(
    synthetic_db: Path,
) -> None:
    laps = _db.read_table(synthetic_db, "laps")
    cutoffs = _db.read_table(synthetic_db, "lap_cutoffs")
    for race_id, race_laps in laps.groupby("race_id"):
        c = cutoffs[cutoffs["race_id"] == race_id].set_index("lap")["cutoff_s"].astype(float)
        for _, row in race_laps.iterrows():
            n = int(row["lap_number"])
            if n >= 2 and pd.notna(row["lap_end_s"]):
                # the lap before this one ended no later than the leader's lap-n completion
                prev = race_laps[
                    (race_laps["driver_number"] == row["driver_number"])
                    & (race_laps["lap_number"] == n - 1)
                ]["lap_end_s"].iloc[0]
                assert float(prev) <= float(c[n])
