"""Future-scramble harness: the "through the accessor" half of the look-ahead guard (D-02, DAT-04).

How scrambling proves a negative. If a consumer's output cannot change when the future changes,
the output cannot depend on the future. `scramble_future` takes every table, keeps everything
that is knowable at an `AsOf` point byte-identical, and replaces everything else with garbage:

* Visible rows of the current race (``visible_at_s <= cutoff``), all rows of earlier races and
  the calendar rows of earlier races are left untouched.
* Future rows are: later races (calendar, entries, time rows, results), the current race's rows
  that become visible only after the cutoff (or never mid-race), and the current race's results.
  Future rows keep their key columns and get a different value in every other column; time
  columns of the current race's future rows are pushed beyond the cutoff so they stay future.
  About 20% of future rows are dropped, junk future rows with new keys are added, one junk later
  race ("2099-99") is added, and every table is shuffled.
* For `RACE_END` nothing of the current race's time tables is scrambled, dropped or added: with no
  time filter every such row is visible. Only later races, the junk race and the current race's
  results (which the as-of door must never serve) change.

`assert_no_lookahead` writes the original and the scrambled tables to two DuckDB files, runs a
consumer on each and requires identical output (or the identical exception).

Guarantees against false negatives (Pitfall 12): garbage always differs from the original value
in every non-key column (numbers are shifted by 1e3..1e4 or become NA, NA becomes a number,
booleans flip, strings become "JUNK-..."); NOT NULL columns never receive NA, so the scrambled
tables always insert into DuckDB; every table in `schema.TABLES` is covered.

Note that `write_tables` recomputes ``visible_at_s`` from the table's time column (DEC-018), so
the harness changes the time column and ``visible_at_s`` together.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from f1si.data import _db, schema
from f1si.data.asof import AsOf, RaceEnd

Consumer = Callable[[Path, AsOf], object]

JUNK_RACE_ID: Final = "2099-99"
_STRUCTURAL_RACE_COLUMNS: Final = frozenset(
    {"race_id", "season", "round", "out_of_sample", "load_status"}
)
_TIME_TABLES: Final = tuple(n for n, s in schema.TABLES.items() if s.visibility == "time")
_DROP_FRACTION: Final = 0.2
_NA_FRACTION: Final = 0.2
_JUNK_ROWS_PER_TABLE: Final = 2


class LookaheadDetected(AssertionError):  # noqa: N818 - name fixed by the plan
    """A consumer's output changed when only the future changed."""


def _different(
    series: pd.Series[Any], sql_type: str, nullable: bool, rng: np.random.Generator
) -> Any:
    """A column of values that all differ from `series` (NA stays impossible for NOT NULL)."""
    n = len(series)
    na = series.isna().to_numpy()
    if sql_type == "INTEGER":
        base = series.fillna(0).to_numpy(dtype="int64")
        out = pd.Series(
            pd.array(base + rng.integers(1000, 10000, n), dtype="Int64"), index=series.index
        )
    elif sql_type == "DOUBLE":
        base_f = series.fillna(0.0).to_numpy(dtype="float64")
        out = pd.Series(
            pd.array(base_f + rng.uniform(1e3, 1e4, n), dtype="Float64"), index=series.index
        )
    elif sql_type == "BOOLEAN":
        base_b = series.fillna(False).to_numpy(dtype=bool)
        out = pd.Series(pd.array(np.where(na, True, ~base_b), dtype="boolean"), index=series.index)
    elif sql_type == "TIMESTAMP":
        base_t = pd.to_datetime(series).fillna(pd.Timestamp("2000-01-01"))
        shift = pd.to_timedelta(rng.integers(1, 1000, n), unit="D")
        out = pd.Series(base_t.to_numpy() + shift.to_numpy(), index=series.index).astype(
            "datetime64[us]"
        )
    else:
        out = pd.Series(
            [f"JUNK-{rng.bytes(4).hex()}" for _ in range(n)], index=series.index, dtype=object
        )
    if nullable and n:
        make_na = (~na) & (rng.random(n) < _NA_FRACTION)
        out = out.mask(pd.Series(make_na, index=series.index))
    return out


def _concat(frames: list[pd.DataFrame], *, ignore_index: bool = True) -> pd.DataFrame:
    """Concatenate, skipping empty frames (pandas warns about empty/NaT dtype inference)."""
    non_empty = [f for f in frames if not f.empty]
    if not non_empty:
        return frames[0]
    return pd.concat(non_empty, ignore_index=ignore_index)


def _scramble_columns(
    table: str, df: pd.DataFrame, rng: np.random.Generator, *, protected: frozenset[str]
) -> pd.DataFrame:
    """Give every non-key, non-protected column of `df` a different value in every row."""
    spec = schema.TABLES[table]
    out = df.copy()
    if out.empty:
        return out
    for col in spec.columns:
        if col.name in spec.key or col.name in protected:
            continue
        out[col.name] = _different(out[col.name], col.sql_type, col.nullable, rng)
    return out


def _push_beyond(
    table: str, df: pd.DataFrame, cutoff_s: float, rng: np.random.Generator
) -> pd.DataFrame:
    """Move the time column (and visible_at_s with it) strictly after the cutoff."""
    spec = schema.TABLES[table]
    assert spec.time_column is not None
    out = df.copy()
    when = cutoff_s + rng.uniform(1.0, 1e4, len(out))
    out[spec.time_column] = pd.array(when, dtype="Float64")
    out[schema.VISIBILITY_COLUMN] = pd.array(when, dtype="Float64")
    return out


def _sync_visibility(table: str, df: pd.DataFrame) -> pd.DataFrame:
    spec = schema.TABLES[table]
    if spec.visibility == "time" and spec.time_column is not None:
        df = df.copy()
        df[schema.VISIBILITY_COLUMN] = df[spec.time_column]
    return df


def _drop_some(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    if df.empty:
        return df
    return df[rng.random(len(df)) >= _DROP_FRACTION]


def _junk_new_key_rows(table: str, current: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Template rows with new keys (lap 900+k / seq 9000+k) for the current race."""
    if current.empty:
        return current.iloc[0:0]
    parts: list[pd.DataFrame] = []
    for k in range(_JUNK_ROWS_PER_TABLE):
        if table == "laps":
            tmpl = current.drop_duplicates("driver_number").copy()
            tmpl["lap_number"] = pd.array([900 + k] * len(tmpl), dtype="Int64")
        elif table == "lap_cutoffs":
            tmpl = current.iloc[[0]].copy()
            tmpl["lap"] = pd.array([900 + k], dtype="Int64")
        else:
            tmpl = current.iloc[[0]].copy()
            tmpl["seq"] = pd.array([9000 + k], dtype="Int64")
        parts.append(tmpl)
    return _concat(parts)


def scramble_future(
    tables: Mapping[str, pd.DataFrame], at: AsOf, *, rng: np.random.Generator
) -> dict[str, pd.DataFrame]:
    """Return a copy of `tables` whose every row that is not knowable at `at` is garbage.

    See the module docstring for the exact rules. The input is not modified.
    """
    races = tables["races"]
    current = at.race_id
    order = races.sort_values(["season", "round"])["race_id"].tolist()
    later = set(order[order.index(current) + 1 :])
    later |= {str(r) for r in races.loc[races["out_of_sample"].astype(bool), "race_id"]}
    later.discard(current)
    race_end = isinstance(at.lap, RaceEnd)

    cutoff_s: float | None = None
    if not race_end:
        lc = tables["lap_cutoffs"]
        hit = lc[(lc["race_id"] == current) & (lc["lap"] == at.lap)]
        if hit.empty:
            raise ValueError(f"no lap_cutoffs row for {current} lap {at.lap}")
        cutoff_s = float(hit["cutoff_s"].iloc[0])

    out: dict[str, pd.DataFrame] = {}
    for name, spec in schema.TABLES.items():
        df = tables[name]
        race_ids = df["race_id"].astype(str)
        is_later = race_ids.isin(later)
        is_current = race_ids == current
        protected = _STRUCTURAL_RACE_COLUMNS if name == "races" else frozenset()
        if name == "races" or name == "entries":
            future = is_later
        elif name == "results":
            future = is_later | is_current
        else:
            future = is_later.copy()
            if cutoff_s is not None:
                vis = df[schema.VISIBILITY_COLUMN]
                late = vis.isna() | (vis > cutoff_s)
                future = future | (is_current & late.fillna(True).astype(bool))

        keep = df[~future]
        fut = df[future]
        if name != "races":
            fut = _drop_some(fut, rng)

        extra: list[pd.DataFrame] = []
        if spec.visibility == "time" and cutoff_s is not None:
            extra.append(_junk_new_key_rows(name, df[is_current], rng))
        fut = _concat([fut, *extra]) if extra else fut

        # the junk later race is built from the current race's rows and is entirely future
        template = df[is_current].copy()
        template["race_id"] = JUNK_RACE_ID
        if name == "races":
            template["season"] = pd.array([2099] * len(template), dtype="Int64")
            template["round"] = pd.array([99] * len(template), dtype="Int64")
            template["out_of_sample"] = pd.array([False] * len(template), dtype="boolean")
            template["load_status"] = "complete"
        fut = _concat([fut, template])

        fut = _scramble_columns(name, fut, rng, protected=protected)
        if spec.visibility == "time":
            fut = _sync_visibility(name, fut)
            if cutoff_s is not None and not fut.empty:
                in_current = fut["race_id"].astype(str) == current
                if bool(in_current.any()):
                    pushed = _push_beyond(name, fut[in_current], cutoff_s, rng)
                    fut = _concat([fut[~in_current], pushed])

        merged = _concat([keep, fut])
        merged = merged.iloc[rng.permutation(len(merged))]
        out[name] = schema.normalize(name, merged)
    return out


def _run(consumer: Consumer, db_path: Path, at: AsOf) -> tuple[str, object]:
    try:
        return ("value", consumer(db_path, at))
    except Exception as err:
        return ("raised", (type(err).__name__, str(err)))


def _same_scalar(a: object, b: object) -> bool:
    if a is pd.NA or b is pd.NA:
        return a is b
    if isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b):
        return True
    if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
        return bool(np.array_equal(a, b, equal_nan=True))
    return bool(a == b)


def _compare(a: object, b: object, path: str) -> None:
    """Raise LookaheadDetected naming `path` if `a` and `b` differ."""
    if type(a) is not type(b):
        raise LookaheadDetected(f"{path}: type {type(a).__name__} vs {type(b).__name__}")
    if isinstance(a, pd.DataFrame):
        assert isinstance(b, pd.DataFrame)
        try:
            pd.testing.assert_frame_equal(a, b, check_exact=True)
        except AssertionError as err:
            raise LookaheadDetected(f"{path} differs when only the future changed: {err}") from err
    elif dataclasses.is_dataclass(a) and not isinstance(a, type):
        for field in dataclasses.fields(a):
            _compare(getattr(a, field.name), getattr(b, field.name), f"{path}.{field.name}")
    elif isinstance(a, Mapping):
        assert isinstance(b, Mapping)
        if set(a) != set(b):
            raise LookaheadDetected(f"{path}: keys {sorted(a)} vs {sorted(b)}")
        for key in a:
            _compare(a[key], b[key], f"{path}[{key!r}]")
    elif isinstance(a, list | tuple):
        assert isinstance(b, list | tuple)
        if len(a) != len(b):
            raise LookaheadDetected(f"{path}: length {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _compare(x, y, f"{path}[{i}]")
    elif not _same_scalar(a, b):
        raise LookaheadDetected(f"{path}: {a!r} vs {b!r}")


def assert_no_lookahead(
    consumer: Consumer,
    tables: Mapping[str, pd.DataFrame],
    at: AsOf,
    *,
    rng: np.random.Generator,
) -> None:
    """Run `consumer` on the original and on the scrambled-future database; outputs must match.

    Raises:
        LookaheadDetected: naming the field or table that differed, or when only one run raised
            or the two runs raised different exceptions.
    """
    scrambled = scramble_future(tables, at, rng=rng)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        original_db = Path(tmp) / "a.duckdb"
        scrambled_db = Path(tmp) / "b.duckdb"
        _db.write_tables(original_db, tables)
        _db.write_tables(scrambled_db, scrambled)
        result_a = _run(consumer, original_db, at)
        result_b = _run(consumer, scrambled_db, at)
    _compare(result_a, result_b, "output")
