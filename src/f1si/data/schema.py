"""The normalized schema every race data source emits (D-01, D-08).

Conventions
-----------
* All times are float seconds on the race clock, where t = 0 is lights out (DOUBLE columns).
* Every time-indexed table carries `visible_at_s`, the race-clock second at which the row became
  knowable. The visibility rule is one generic predicate:

      a row is visible at cutoff c  iff  visible_at_s IS NOT NULL AND visible_at_s <= c

  A NULL `visible_at_s` means "not knowable mid-race" (for example a lap with no recorded end
  time); such a row is visible only at the race end and in history.
* Canonical pandas dtypes after `normalize`: INTEGER -> Int64, DOUBLE -> Float64,
  BOOLEAN -> boolean, VARCHAR -> object holding str or None, TIMESTAMP -> tz-naive UTC
  datetime64[us]. Missing values are pandas NA, which DuckDB stores as SQL NULL.
* Keys are not enforced with PRIMARY KEY constraints (over-eager checking and memory use on large
  tables); `validate_race` and the tests enforce them instead.

Provenance rule (DEC-010): every stored column of a time-indexed row must be knowable at that
row's `visible_at_s`. `laps.track_status` therefore only summarizes statuses up to the lap's end,
and `lap_cutoffs` is precomputed at load time so the as-of door never has to look at other cars'
future laps to find a leader's lap-N completion time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Literal

import pandas as pd

from f1si.data.sources import NormalizedRace

VISIBILITY_COLUMN: Final = "visible_at_s"

SqlType = Literal["INTEGER", "DOUBLE", "BOOLEAN", "VARCHAR", "TIMESTAMP"]
Visibility = Literal["calendar", "pre_race", "time", "results"]


@dataclass(frozen=True)
class ColumnSpec:
    """One column: name, SQL type and whether NULL is allowed."""

    name: str
    sql_type: SqlType
    nullable: bool = True


@dataclass(frozen=True)
class TableSpec:
    """One table: columns, key, and how its rows become visible.

    `visibility` is "calendar" (always known), "pre_race" (known before lights out), "time"
    (visible at `time_column`, copied into `visible_at_s`) or "results" (only through the results
    door). `derived` tables are computed by the loader, not supplied by a source.
    """

    name: str
    columns: tuple[ColumnSpec, ...]
    key: tuple[str, ...]
    visibility: Visibility
    time_column: str | None
    derived: bool = False

    @property
    def column_names(self) -> tuple[str, ...]:
        """Column names in storage order."""
        return tuple(c.name for c in self.columns)


def _col(name: str, sql_type: SqlType, *, required: bool = False) -> ColumnSpec:
    return ColumnSpec(name, sql_type, nullable=not required)


_RACES = TableSpec(
    name="races",
    columns=(
        _col("race_id", "VARCHAR", required=True),
        _col("season", "INTEGER", required=True),
        _col("round", "INTEGER", required=True),
        _col("slug", "VARCHAR", required=True),
        _col("event_name", "VARCHAR", required=True),
        _col("circuit", "VARCHAR", required=True),
        _col("country", "VARCHAR", required=True),
        _col("race_start_utc", "TIMESTAMP", required=True),
        _col("scheduled_laps", "INTEGER"),
        _col("era", "VARCHAR", required=True),
        _col("out_of_sample", "BOOLEAN", required=True),
        _col("source", "VARCHAR", required=True),
        _col("source_version", "VARCHAR", required=True),
        _col("loaded_at_utc", "TIMESTAMP", required=True),
        _col("load_status", "VARCHAR", required=True),
    ),
    key=("race_id",),
    visibility="calendar",
    time_column=None,
)

_ENTRIES = TableSpec(
    name="entries",
    columns=(
        _col("race_id", "VARCHAR", required=True),
        _col("driver_number", "INTEGER", required=True),
        _col("driver_code", "VARCHAR", required=True),
        _col("driver_id", "VARCHAR", required=True),
        _col("full_name", "VARCHAR"),
        _col("team_name", "VARCHAR"),
        # NULL grid_position = pit-lane start or no grid slot
        _col("grid_position", "INTEGER"),
        _col("pit_lane_start", "BOOLEAN", required=True),
        _col("start_compound", "VARCHAR"),
        _col("start_tyre_age", "INTEGER"),
    ),
    key=("race_id", "driver_number"),
    visibility="pre_race",
    time_column=None,
)

_LAPS = TableSpec(
    name="laps",
    columns=(
        _col("race_id", "VARCHAR", required=True),
        _col("driver_number", "INTEGER", required=True),
        _col("lap_number", "INTEGER", required=True),
        _col("lap_start_s", "DOUBLE"),
        _col("lap_end_s", "DOUBLE"),
        _col("lap_time_s", "DOUBLE"),
        _col("s1_s", "DOUBLE"),
        _col("s2_s", "DOUBLE"),
        _col("s3_s", "DOUBLE"),
        _col("is_pit_in_lap", "BOOLEAN", required=True),
        _col("is_pit_out_lap", "BOOLEAN", required=True),
        # set on the out-lap: time lost in the pit lane for the stop that ended on this lap
        _col("pit_duration_s", "DOUBLE"),
        _col("stint", "INTEGER"),
        _col("compound", "VARCHAR"),
        # laps on this tyre at the end of the lap
        _col("tyre_life", "INTEGER"),
        # filled by the loader: statuses seen during the lap, e.g. "1", "167" (derive.py)
        _col("track_status", "VARCHAR"),
        _col(VISIBILITY_COLUMN, "DOUBLE"),
    ),
    key=("race_id", "driver_number", "lap_number"),
    visibility="time",
    time_column="lap_end_s",
)

TRACK_STATUS_CODES: Final[frozenset[str]] = frozenset({"1", "2", "4", "5", "6", "7"})

_TRACK_STATUS = TableSpec(
    name="track_status",
    columns=(
        _col("race_id", "VARCHAR", required=True),
        _col("seq", "INTEGER", required=True),
        _col("t_s", "DOUBLE", required=True),
        # 1 green, 2 yellow, 4 safety car, 5 red flag, 6 VSC deployed, 7 VSC ending
        _col("status", "VARCHAR", required=True),
        _col("message", "VARCHAR"),
        _col(VISIBILITY_COLUMN, "DOUBLE"),
    ),
    key=("race_id", "seq"),
    visibility="time",
    time_column="t_s",
)

_RACE_CONTROL = TableSpec(
    name="race_control",
    columns=(
        _col("race_id", "VARCHAR", required=True),
        _col("seq", "INTEGER", required=True),
        _col("t_s", "DOUBLE", required=True),
        _col("category", "VARCHAR", required=True),
        _col("flag", "VARCHAR"),
        _col("scope", "VARCHAR"),
        _col("sector", "INTEGER"),
        _col("driver_number", "INTEGER"),
        _col("lap_number", "INTEGER"),
        _col("message", "VARCHAR", required=True),
        _col(VISIBILITY_COLUMN, "DOUBLE"),
    ),
    key=("race_id", "seq"),
    visibility="time",
    time_column="t_s",
)

_WEATHER = TableSpec(
    name="weather",
    columns=(
        _col("race_id", "VARCHAR", required=True),
        _col("seq", "INTEGER", required=True),
        _col("t_s", "DOUBLE", required=True),
        _col("air_temp_c", "DOUBLE"),
        _col("track_temp_c", "DOUBLE"),
        _col("humidity_pct", "DOUBLE"),
        _col("pressure_mbar", "DOUBLE"),
        _col("rainfall", "BOOLEAN"),
        _col("wind_speed_ms", "DOUBLE"),
        _col("wind_direction_deg", "DOUBLE"),
        _col(VISIBILITY_COLUMN, "DOUBLE"),
    ),
    key=("race_id", "seq"),
    visibility="time",
    time_column="t_s",
)

# Derived by the loader (see f1si.data.derive), never supplied by a source.
_LAP_CUTOFFS = TableSpec(
    name="lap_cutoffs",
    columns=(
        _col("race_id", "VARCHAR", required=True),
        _col("lap", "INTEGER", required=True),
        _col("cutoff_s", "DOUBLE", required=True),
        _col(VISIBILITY_COLUMN, "DOUBLE"),
    ),
    key=("race_id", "lap"),
    visibility="time",
    time_column="cutoff_s",
    derived=True,
)

_RESULTS = TableSpec(
    name="results",
    columns=(
        _col("race_id", "VARCHAR", required=True),
        _col("driver_number", "INTEGER", required=True),
        # NULL for a driver who was not classified as a finisher
        _col("final_position", "INTEGER"),
        _col("classified_position", "VARCHAR", required=True),
        _col("status", "VARCHAR", required=True),
        _col("points", "DOUBLE", required=True),
        _col("laps_completed", "INTEGER", required=True),
        _col("total_time_s", "DOUBLE"),
    ),
    key=("race_id", "driver_number"),
    visibility="results",
    time_column=None,
)

TABLES: Final[Mapping[str, TableSpec]] = MappingProxyType(
    {
        spec.name: spec
        for spec in (
            _RACES,
            _ENTRIES,
            _LAPS,
            _TRACK_STATUS,
            _RACE_CONTROL,
            _WEATHER,
            _LAP_CUTOFFS,
            _RESULTS,
        )
    }
)

PER_RACE_TABLES: Final[tuple[str, ...]] = tuple(name for name in TABLES if name != "races")

# SELECT bodies; `f1si.data._db.ensure_schema` wraps each in CREATE OR REPLACE VIEW <name> AS.
VIEWS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "stints": (
            "SELECT race_id, driver_number, stint, any_value(compound) AS compound, "
            "min(lap_number) AS first_lap, max(lap_number) AS last_lap, count(*) AS n_laps "
            "FROM laps WHERE stint IS NOT NULL GROUP BY race_id, driver_number, stint"
        ),
        "pit_stops": (
            "SELECT race_id, driver_number, lap_number - 1 AS in_lap, lap_number AS out_lap, "
            "pit_duration_s FROM laps WHERE is_pit_out_lap AND lap_number > 1"
        ),
    }
)


def _spec(table: str) -> TableSpec:
    try:
        return TABLES[table]
    except KeyError:
        raise ValueError(f"unknown table {table!r}; known tables: {sorted(TABLES)}") from None


def ddl(table: str) -> str:
    """Return the CREATE TABLE IF NOT EXISTS statement for `table` (no PRIMARY KEY)."""
    spec = _spec(table)
    parts = [f"{c.name} {c.sql_type}{'' if c.nullable else ' NOT NULL'}" for c in spec.columns]
    return f"CREATE TABLE IF NOT EXISTS {spec.name} ({', '.join(parts)})"


def add_visibility(table: str, df: pd.DataFrame) -> pd.DataFrame:
    """Set `visible_at_s` for time-indexed tables; return other tables unchanged.

    For a "time" table the visibility equals its `time_column`: a lap becomes knowable when it
    ends. NA stays NA, which means the row is only visible at the race end.
    """
    spec = _spec(table)
    if spec.visibility != "time" or spec.time_column is None:
        return df
    if spec.time_column not in df.columns:
        raise KeyError(f"table {table!r} is missing column {spec.time_column!r}")
    out = df.copy()
    out[VISIBILITY_COLUMN] = out[spec.time_column]
    return out


def _cast(series: pd.Series[Any], sql_type: str) -> pd.Series[Any]:
    if sql_type == "INTEGER":
        return series.astype("Int64")
    if sql_type == "DOUBLE":
        return series.astype("Float64")
    if sql_type == "BOOLEAN":
        return series.astype("boolean")
    if sql_type == "TIMESTAMP":
        converted = pd.to_datetime(series, utc=True)
        return converted.dt.tz_localize(None).astype("datetime64[us]")
    # VARCHAR: object column holding str or None
    values = [None if pd.isna(v) else str(v) for v in series]
    return pd.Series(values, index=series.index, dtype=object)


def normalize(table: str, df: pd.DataFrame) -> pd.DataFrame:
    """Return `df` with exactly the table's columns, in order, in the canonical dtypes.

    Time-indexed tables get `visible_at_s` filled from their time column when absent.

    Raises:
        KeyError: naming the missing column(s).
    """
    spec = _spec(table)
    if spec.visibility == "time" and VISIBILITY_COLUMN not in df.columns:
        df = add_visibility(table, df)
    missing = [c.name for c in spec.columns if c.name not in df.columns]
    if missing:
        raise KeyError(f"table {table!r} is missing column(s): {', '.join(missing)}")
    out = pd.DataFrame({c.name: _cast(df[c.name], c.sql_type) for c in spec.columns})
    return out.reset_index(drop=True)


def validate_race(race: NormalizedRace) -> list[str]:
    """Return human-readable problems with a source's output; an empty list means valid.

    Checks: every non-derived per-race table is present with all its columns; required columns
    and keys are non-null and unique; every race_id equals `race.ref.race_id`; lap numbers start
    at 1; laps and results reference known entries; track status codes are in the known set; a lap
    does not end before it starts. Derived tables (lap_cutoffs) are not required from sources.
    """
    problems: list[str] = []
    race_id = race.ref.race_id
    normalized: dict[str, pd.DataFrame] = {}

    for name in PER_RACE_TABLES:
        spec = TABLES[name]
        if spec.derived:
            continue
        if name not in race.tables:
            problems.append(f"missing required table '{name}'")
            continue
        df = race.tables[name]
        missing = [
            c.name for c in spec.columns if c.name != VISIBILITY_COLUMN and c.name not in df.columns
        ]
        if missing:
            problems.append(f"table '{name}' is missing column(s): {', '.join(missing)}")
            continue
        try:
            norm = normalize(name, df)
        except (KeyError, TypeError, ValueError) as err:
            problems.append(f"table '{name}' could not be converted to the schema types: {err}")
            continue
        normalized[name] = norm

        for col in spec.columns:
            if not col.nullable and bool(norm[col.name].isna().any()):
                problems.append(f"table '{name}' has null values in required column '{col.name}'")
        n_dup = int(norm.duplicated(subset=list(spec.key)).sum())
        if n_dup:
            problems.append(f"table '{name}' has {n_dup} duplicate key(s) on {spec.key}")
        wrong_ids = sorted({str(v) for v in norm["race_id"].dropna().unique()} - {race_id})
        if wrong_ids:
            problems.append(
                f"table '{name}' has race_id value(s) {wrong_ids} different from "
                f"the race's ref.race_id '{race_id}'"
            )

    track = normalized.get("track_status")
    if track is not None:
        bad = sorted({str(v) for v in track["status"].dropna().unique()} - TRACK_STATUS_CODES)
        if bad:
            problems.append(
                f"table 'track_status' has unknown status code(s) {bad}; "
                f"allowed: {sorted(TRACK_STATUS_CODES)}"
            )

    results = normalized.get("results")
    entries_for_results = normalized.get("entries")
    if results is not None and entries_for_results is not None:
        known_drivers = set(entries_for_results["driver_number"].dropna().astype(int))
        extra = sorted(set(results["driver_number"].dropna().astype(int)) - known_drivers)
        if extra:
            problems.append(f"table 'results' references driver_number(s) not in entries: {extra}")

    laps = normalized.get("laps")
    if laps is not None:
        if bool((laps["lap_number"] < 1).fillna(False).any()):
            problems.append("table 'laps' has lap_number < 1 (laps are numbered from 1)")
        entries = normalized.get("entries")
        if entries is not None:
            known = set(entries["driver_number"].dropna().astype(int))
            unknown = sorted(set(laps["driver_number"].dropna().astype(int)) - known)
            if unknown:
                problems.append(
                    f"table 'laps' references driver_number(s) not in entries: {unknown}"
                )
        backwards = (laps["lap_end_s"] < laps["lap_start_s"]).fillna(False)
        if bool(backwards.any()):
            problems.append(
                f"table 'laps' has {int(backwards.sum())} lap(s) ending before they start"
            )

    return problems
