"""The only module that imports duckdb: schema DDL, transactional per-race writes, reads.

Rules this module enforces (DEC-010, DEC-011):

* Connections are short-lived context managers and are always closed before returning, so a
  Windows file lock never outlives the call.
* One transaction per race: delete the race's old rows, insert the new ones, insert the `races`
  row last (the completion marker), commit. Any exception, including Ctrl+C, triggers a ROLLBACK.
* Every value reaches SQL as a bound `?` parameter. Table and view names are interpolated only
  after being checked against the constants in `f1si.data.schema`.
* A multi-query read (a snapshot, a history) opens ONE read-only connection with
  `connect_reader` and passes it to every query via `con=`. While it is open no other process can
  take the write lock, so all the queries see one consistent load of the cache (WR-04).
* Lock errors from DuckDB (a Linux conflicting-lock message, a Windows "used by another
  process" message) become `CacheBusyError`; a missing file becomes `CacheMissingError`.
"""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd

from f1si.data import schema
from f1si.data.errors import CacheBusyError, CacheMissingError

# Specific phrases only. A bare "lock" would also match "block", so a corrupt file ("computed
# checksum of block ...") or a short read would be reported as a busy cache (WR-10).
_LOCK_PHRASES = (
    "could not set lock",
    "conflicting lock",
    "being used by another process",
    "already open",
)

# Deterministic row order for the views (tables are ordered by their spec key)
_VIEW_ORDER: Mapping[str, str] = {
    "stints": "race_id, driver_number, stint",
    "pit_stops": "race_id, driver_number, in_lap",
}


Connection = duckdb.DuckDBPyConnection  # re-exported so callers never import duckdb


def _is_lock_error(err: duckdb.IOException) -> bool:
    text = str(err).lower()
    return any(phrase in text for phrase in _LOCK_PHRASES)


@contextmanager
def _open(db_path: Path, *, read_only: bool) -> Iterator[duckdb.DuckDBPyConnection]:
    try:
        con = duckdb.connect(str(db_path), read_only=read_only)
    except duckdb.IOException as err:
        if _is_lock_error(err):
            raise CacheBusyError() from err
        raise
    try:
        yield con
    finally:
        con.close()


@contextmanager
def connect_writer(db_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open the cache read-write (creating the folder and file), closing it on exit."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _open(db_path, read_only=False) as con:
        yield con


@contextmanager
def connect_reader(db_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open the cache read-only, closing it on exit.

    Raises:
        CacheMissingError: if the file does not exist.
        CacheBusyError: if another process holds it open for writing.
    """
    if not db_path.exists():
        raise CacheMissingError(db_path)
    with _open(db_path, read_only=True) as con:
        yield con


def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create every table (IF NOT EXISTS) and (re)create the stints and pit_stops views."""
    for table in schema.TABLES:
        con.execute(schema.ddl(table))
    con.execute("ALTER TABLE weather ADD COLUMN IF NOT EXISTS source_utc TIMESTAMP")
    for view, select in schema.VIEWS.items():
        con.execute(f"CREATE OR REPLACE VIEW {view} AS {select}")


def _insert_frame(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame) -> None:
    """Insert `df` (already normalized) into `table`; `table` is a schema constant."""
    con.register("incoming", df)
    try:
        con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM incoming")
    finally:
        con.unregister("incoming")


def _prepared(table: str, df: pd.DataFrame) -> pd.DataFrame:
    return schema.normalize(table, schema.add_visibility(table, df))


def write_race(db_path: Path, race_row: pd.DataFrame, tables: Mapping[str, pd.DataFrame]) -> None:
    """Write one race atomically: all per-race tables, then the `races` completion row.

    Raises:
        ValueError: if `tables` lacks a per-race table or holds an unknown one.
        KeyError: if a frame lacks a required column (nothing is written).
    """
    unknown = sorted(set(tables) - set(schema.PER_RACE_TABLES))
    missing = [
        name
        for name in schema.PER_RACE_TABLES
        if name not in tables and not schema.TABLES[name].optional
    ]
    if unknown or missing:
        raise ValueError(f"write_race tables mismatch: unknown={unknown}, missing={missing}")
    if len(race_row) != 1:
        raise ValueError("race_row must hold exactly one row")
    race_id = str(race_row["race_id"].iloc[0])
    with connect_writer(db_path) as con:
        ensure_schema(con)
        con.begin()
        try:
            for name in schema.PER_RACE_TABLES:
                con.execute(f"DELETE FROM {name} WHERE race_id = ?", [race_id])
                frame = tables[name] if name in tables else schema.empty_frame(name)
                _insert_frame(con, name, _prepared(name, frame))
            con.execute("DELETE FROM races WHERE race_id = ?", [race_id])
            _insert_frame(con, "races", _prepared("races", race_row))
            con.commit()
        except BaseException:
            con.rollback()
            raise


def write_tables(db_path: Path, tables: Mapping[str, pd.DataFrame]) -> None:
    """Replace whole tables (any subset of `schema.TABLES`) in one transaction.

    Used by test harnesses that build a dataset by hand; the loader uses `write_race`.
    """
    unknown = sorted(set(tables) - set(schema.TABLES))
    if unknown:
        raise ValueError(f"unknown table(s): {unknown}")
    with connect_writer(db_path) as con:
        ensure_schema(con)
        con.begin()
        try:
            for name, df in tables.items():
                con.execute(f"DELETE FROM {name}")
                _insert_frame(con, name, _prepared(name, df))
            con.commit()
        except BaseException:
            con.rollback()
            raise


def read_df(
    db_path: Path,
    sql: str,
    params: Sequence[object] = (),
    *,
    con: Connection | None = None,
) -> pd.DataFrame:
    """Run a read-only query with bound `params` and return a DataFrame.

    With `con` (from `connect_reader`) the query runs on that open connection; without it a
    short-lived connection is opened and closed around this one query.
    """
    if con is not None:
        return con.execute(sql, list(params)).df()
    with connect_reader(db_path) as own:
        return own.execute(sql, list(params)).df()


def read_table(
    db_path: Path,
    table: str,
    *,
    race_id: str | None = None,
    con: Connection | None = None,
) -> pd.DataFrame:
    """Read a table or view, optionally for one race, in a deterministic order.

    Pass `con` to reuse an open read connection (see `read_df`).

    Raises:
        ValueError: if `table` is not in `schema.TABLES` or `schema.VIEWS`.
    """
    if table in schema.TABLES:
        order = ", ".join(schema.TABLES[table].key)
    elif table in schema.VIEWS:
        order = _VIEW_ORDER[table]
    else:
        raise ValueError(
            f"unknown table {table!r}; known: {sorted(schema.TABLES)} and {sorted(schema.VIEWS)}"
        )
    where = "" if race_id is None else " WHERE race_id = ?"
    params: list[object] = [] if race_id is None else [race_id]
    if table in schema.TABLES and schema.TABLES[table].optional:
        own = con
        if own is None:
            with connect_reader(db_path) as opened:
                if not table_exists(opened, table):
                    return schema.empty_frame(table)
                df = opened.execute(f"SELECT * FROM {table}{where} ORDER BY {order}", params).df()
        elif not table_exists(own, table):
            return schema.empty_frame(table)
        else:
            df = own.execute(f"SELECT * FROM {table}{where} ORDER BY {order}", params).df()
    else:
        df = read_df(db_path, f"SELECT * FROM {table}{where} ORDER BY {order}", params, con=con)
    return schema.normalize(table, df) if table in schema.TABLES else df


def table_exists(con: Connection, table: str) -> bool:
    """Whether a schema table exists in this cache, including pre-M2 caches."""
    row = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1", [table]
    ).fetchone()
    return row is not None


def read_all_tables(db_path: Path) -> dict[str, pd.DataFrame]:
    """Read every table in `schema.TABLES`."""
    return {name: read_table(db_path, name) for name in schema.TABLES}


def completed_race_ids(db_path: Path) -> set[str]:
    """Race ids whose load finished (`load_status = 'complete'`); empty if no cache exists."""
    if not db_path.exists():
        return set()
    df = read_df(db_path, "SELECT race_id FROM races WHERE load_status = ?", ["complete"])
    return {str(v) for v in df["race_id"]}


def update_scheduled_laps(db_path: Path, race_id: str, laps: int) -> bool:
    """Update only scheduled-lap metadata for one complete 2023-2025 in-sample race.

    Returns whether a previously missing or invalid value was updated. Out-of-sample rows and
    races outside the Phase 6 catalog are rejected before any write.
    """
    if isinstance(laps, bool) or not isinstance(laps, int) or laps < 1:
        raise ValueError("scheduled lap count must be a positive integer")
    with connect_writer(db_path) as con:
        row = con.execute(
            "SELECT season, out_of_sample, load_status, scheduled_laps "
            "FROM races WHERE race_id = ?",
            [race_id],
        ).fetchone()
        if row is None:
            raise ValueError(f"Race {race_id} is not present in the cache")
        season, out_of_sample, load_status, existing = row
        if not 2023 <= int(season) <= 2025 or bool(out_of_sample) or load_status != "complete":
            raise ValueError(f"Race {race_id} is not an eligible complete in-sample race")
        if existing is not None and int(existing) > 0:
            return False
        con.begin()
        try:
            con.execute(
                "UPDATE races SET scheduled_laps = ? "
                "WHERE race_id = ? AND season BETWEEN 2023 AND 2025 "
                "AND out_of_sample = FALSE AND load_status = 'complete' "
                "AND (scheduled_laps IS NULL OR scheduled_laps < 1)",
                [laps, race_id],
            )
            updated = con.execute(
                "SELECT scheduled_laps FROM races WHERE race_id = ?", [race_id]
            ).fetchone()
            if updated is None or int(updated[0]) != laps:
                raise ValueError(f"Scheduled lap count update did not persist for {race_id}")
            con.commit()
        except BaseException:
            con.rollback()
            raise
    return True


def sources_in_cache(db_path: Path) -> set[str]:
    """Distinct data sources present in the cache; empty if no cache exists."""
    if not db_path.exists():
        return set()
    df = read_df(db_path, "SELECT DISTINCT source FROM races")
    return {str(v) for v in df["source"]}
