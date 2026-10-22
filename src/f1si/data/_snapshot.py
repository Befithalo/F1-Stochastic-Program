"""Snapshot and history construction shared by the as-of and out-of-sample doors (D-01, D-03, D-04).

This module is private: the import ban lets only `f1si.data.asof` and `f1si.data.out_of_sample`
import it.

The visibility rule
-------------------
Let c be the cutoff of "lap N": the time at which the race leader completed lap N, read from the
precomputed `lap_cutoffs` table (lap 0 is the start of the race). A row is visible at c iff

    visible_at_s IS NOT NULL  and  visible_at_s <= c

For `RACE_END` there is no time filter: every row of the race is visible, including rows whose
`visible_at_s` is NULL. Final results are never read here for the current race (D-03).

Plain-words consequence (D-01): at "lap N" the leader has completed N laps, but every other car is
still on its way to the line and has completed at most N-1. A strategy that needs to know where
a rival is must work from those N-1 laps, exactly as a pit-wall engineer would at that moment.

Rebuilt fields (D-03)
---------------------
Stints, pit events and per-car lap counts and positions are rebuilt from the visible laps only.
The stored stint end lap and length, final position, points and total time are never served
because they depend on laps that have not happened yet.

History (D-04, revised)
-----------------------
`build_history` returns every earlier in-sample race in full, including results, and nothing
from the current or later races. A race is earlier iff season < s or (season = s and round < r).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import pandas as pd

from f1si.data import _db, schema
from f1si.data.errors import LapOutOfRangeError, UnknownRaceError


@dataclass(frozen=True)
class RaceEnd:
    """Marker meaning "the whole race, through the as-of door, still without results"."""

    def __repr__(self) -> str:
        return "RACE_END"


RACE_END: Final = RaceEnd()


@dataclass(frozen=True)
class AsOf:
    """A point on the race clock: after the leader completed `lap` laps, or `RACE_END`.

    Raises:
        ValueError: if `lap` is negative, a bool, or neither an int nor `RACE_END`.
    """

    race_id: str
    lap: int | RaceEnd

    def __post_init__(self) -> None:
        if isinstance(self.lap, RaceEnd):
            return
        if isinstance(self.lap, bool) or not isinstance(self.lap, int):
            raise ValueError(f"lap must be an int >= 0 or RACE_END, got {self.lap!r}")
        if self.lap < 0:
            raise ValueError(f"lap must be >= 0 (0 means before the start), got {self.lap}")


@dataclass(frozen=True)
class RaceInfo:
    """Calendar facts about one race (no results)."""

    race_id: str
    season: int
    round: int
    slug: str
    event_name: str
    circuit: str
    country: str
    race_start_utc: datetime
    scheduled_laps: int | None
    era: str
    out_of_sample: bool


@dataclass(frozen=True, eq=False)
class RaceSnapshot:
    """What was knowable at `at`. Plain data: it grants no further access to the cache.

    `cutoff_s` is the race-clock second of the cutoff, or None for `RACE_END`. `cars` holds one
    row per entry with `laps_done`, `position` and `stops_done` rebuilt from visible laps.
    """

    race: RaceInfo
    at: AsOf
    cutoff_s: float | None
    entries: pd.DataFrame
    laps: pd.DataFrame
    track_status: pd.DataFrame
    race_control: pd.DataFrame
    weather: pd.DataFrame
    stints: pd.DataFrame
    pit_events: pd.DataFrame
    cars: pd.DataFrame


@dataclass(frozen=True, eq=False)
class History:
    """Every earlier in-sample race in full, results included (never the current race)."""

    as_of: AsOf
    races: list[str]
    entries: pd.DataFrame
    laps: pd.DataFrame
    track_status: pd.DataFrame
    race_control: pd.DataFrame
    weather: pd.DataFrame
    lap_cutoffs: pd.DataFrame
    results: pd.DataFrame


_TIME_TABLES: Final = ("laps", "track_status", "race_control", "weather")
_HISTORY_TABLES: Final = (
    "entries",
    "laps",
    "track_status",
    "race_control",
    "weather",
    "lap_cutoffs",
    "results",
)

_RACE_INFO_SQL: Final = (
    "SELECT race_id, season, round, slug, event_name, circuit, country, race_start_utc, "
    "scheduled_laps, era, out_of_sample FROM races WHERE race_id = ? AND load_status = ?"
)
_KNOWN_SQL: Final = "SELECT race_id, slug FROM races WHERE load_status = ?"
_COMPLETE: Final = "complete"
_EARLIER_PREDICATE: Final = (
    "load_status = 'complete' AND NOT out_of_sample AND (season < ? OR (season = ? AND round < ?))"
)


def _order(table: str) -> str:
    return ", ".join(schema.TABLES[table].key)


def _without_visibility(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[schema.VISIBILITY_COLUMN], errors="ignore").reset_index(drop=True)


def race_info(db_path: Path, race_id: str) -> RaceInfo:
    """Look up one finished race by id (bound parameter).

    Raises:
        UnknownRaceError: if the race is absent or its load did not finish.
    """
    df = _db.read_df(db_path, _RACE_INFO_SQL, [race_id, _COMPLETE])
    if df.empty:
        known_df = _db.read_df(db_path, _KNOWN_SQL, [_COMPLETE])
        known = [str(v) for v in known_df["race_id"]] + [str(v) for v in known_df["slug"]]
        raise UnknownRaceError(race_id, known)
    row = df.iloc[0]
    scheduled = row["scheduled_laps"]
    return RaceInfo(
        race_id=str(row["race_id"]),
        season=int(row["season"]),
        round=int(row["round"]),
        slug=str(row["slug"]),
        event_name=str(row["event_name"]),
        circuit=str(row["circuit"]),
        country=str(row["country"]),
        race_start_utc=pd.Timestamp(row["race_start_utc"]).to_pydatetime(),
        scheduled_laps=None if pd.isna(scheduled) else int(scheduled),
        era=str(row["era"]),
        out_of_sample=bool(row["out_of_sample"]),
    )


def _cutoff(db_path: Path, at: AsOf, info: RaceInfo) -> float | None:
    """The cutoff for `at`; reads only the lap-N row of `lap_cutoffs` (DEC-008)."""
    if isinstance(at.lap, RaceEnd):
        return None
    df = _db.read_df(
        db_path,
        "SELECT cutoff_s FROM lap_cutoffs WHERE race_id = ? AND lap = ?",
        [info.race_id, at.lap],
    )
    if df.empty:
        raise LapOutOfRangeError(at.lap, info.slug)
    return float(df["cutoff_s"].iloc[0])


def _visible_rows(db_path: Path, table: str, race_id: str, cutoff_s: float | None) -> pd.DataFrame:
    """Rows of a time table that are visible at the cutoff (all rows for RACE_END)."""
    spec = schema.TABLES[table]
    if spec.visibility != "time":
        raise ValueError(f"{table!r} is not a time-indexed table")
    order = _order(table)
    if cutoff_s is None:
        sql = f"SELECT * FROM {table} WHERE race_id = ? ORDER BY {order}"
        params: list[object] = [race_id]
    else:
        sql = (
            f"SELECT * FROM {table} WHERE race_id = ? "
            f"AND visible_at_s IS NOT NULL AND visible_at_s <= ? ORDER BY {order}"
        )
        params = [race_id, cutoff_s]
    return _without_visibility(schema.normalize(table, _db.read_df(db_path, sql, params)))


def _typed(columns: Mapping[str, Any], dtypes: Mapping[str, str]) -> pd.DataFrame:
    """Build a frame with exactly `dtypes` (name -> pandas dtype), in that order."""
    return pd.DataFrame(
        {name: pd.Series(columns[name]).astype(dtype) for name, dtype in dtypes.items()}  # type: ignore[call-overload]
    )


_STINT_DTYPES: Final = {
    "driver_number": "Int64",
    "stint": "Int64",
    "compound": "object",
    "first_lap": "Int64",
    "last_visible_lap": "Int64",
    "laps_so_far": "Int64",
    "tyre_life_now": "Int64",
}
_PIT_DTYPES: Final = {
    "driver_number": "Int64",
    "in_lap": "Int64",
    "out_lap": "Int64",
    "pit_duration_s": "Float64",
}
_CAR_DTYPES: Final = {
    "driver_number": "Int64",
    "driver_code": "object",
    "laps_done": "Int64",
    "last_lap_end_s": "Float64",
    "stops_done": "Int64",
    "position": "Int64",
}


def rebuild_stints(laps: pd.DataFrame) -> pd.DataFrame:
    """One row per (driver, stint) from the visible laps only.

    Columns: driver_number, stint, compound, first_lap, last_visible_lap, laps_so_far (visible
    laps in the stint), tyre_life_now (tyre life at the last visible lap of the stint). There is
    deliberately no stint end lap or length: they would reveal laps that have not happened yet.
    """
    vis = laps[laps["stint"].notna()].sort_values(["driver_number", "stint", "lap_number"])
    if vis.empty:
        return _typed({n: pd.Series([], dtype="object") for n in _STINT_DTYPES}, _STINT_DTYPES)
    grouped = vis.groupby(["driver_number", "stint"], sort=True)
    out = grouped.agg(
        compound=("compound", "first"),
        first_lap=("lap_number", "min"),
        last_visible_lap=("lap_number", "max"),
        laps_so_far=("lap_number", "count"),
        tyre_life_now=("tyre_life", "last"),
    ).reset_index()
    return _typed({n: out[n] for n in _STINT_DTYPES}, _STINT_DTYPES).reset_index(drop=True)


def rebuild_pit_events(laps: pd.DataFrame) -> pd.DataFrame:
    """One row per stop seen so far: a visible out-lap after lap 1 (in_lap = out_lap - 1).

    A lap-1 out-lap is a pit-lane start, not a stop.
    """
    is_out = laps["is_pit_out_lap"].fillna(False).astype(bool)
    stops = laps[is_out & (laps["lap_number"] > 1)].sort_values(["driver_number", "lap_number"])
    cols: dict[str, Any] = {
        "driver_number": stops["driver_number"],
        "in_lap": stops["lap_number"] - 1,
        "out_lap": stops["lap_number"],
        "pit_duration_s": stops["pit_duration_s"],
    }
    return _typed(cols, _PIT_DTYPES).reset_index(drop=True)


def rebuild_cars(laps: pd.DataFrame, entries: pd.DataFrame) -> pd.DataFrame:
    """One row per entry: laps_done, last_lap_end_s, stops_done and position.

    laps_done counts visible laps with an end time. position ranks cars that have finished at
    least one lap by laps_done (more first), then by last_lap_end_s (earlier first), then by
    driver number; it is NA for cars without a finished lap. It is named laps_done, not
    laps_completed, so it cannot be confused with the final results column.
    """
    done = laps[laps["lap_end_s"].notna()]
    per_driver = done.groupby("driver_number", sort=True).agg(
        laps_done=("lap_end_s", "count"), last_lap_end_s=("lap_end_s", "max")
    )
    stops = rebuild_pit_events(laps).groupby("driver_number", sort=True).size()
    cars = entries[["driver_number", "driver_code"]].copy()
    numbers = cars["driver_number"].astype("int64")
    cars["laps_done"] = numbers.map(per_driver["laps_done"]).fillna(0).astype("Int64")
    cars["last_lap_end_s"] = numbers.map(per_driver["last_lap_end_s"]).astype("Float64")
    cars["stops_done"] = numbers.map(stops).fillna(0).astype("Int64")
    running = cars[cars["laps_done"] > 0].sort_values(
        ["laps_done", "last_lap_end_s", "driver_number"], ascending=[False, True, True]
    )
    ranks = pd.Series(range(1, len(running) + 1), index=running.index, dtype="Int64")
    cars["position"] = ranks.reindex(cars.index).astype("Int64")
    return _typed({n: cars[n] for n in _CAR_DTYPES}, _CAR_DTYPES).reset_index(drop=True)


def build_snapshot(db_path: Path, at: AsOf, info: RaceInfo) -> RaceSnapshot:
    """Everything knowable about `info` at `at`, with results never read (D-01, D-03).

    Raises:
        LapOutOfRangeError: if `at.lap` is beyond the last lap of the race.
    """
    cutoff_s = _cutoff(db_path, at, info)
    entries = schema.normalize("entries", _db.read_table(db_path, "entries", race_id=info.race_id))
    frames = {t: _visible_rows(db_path, t, info.race_id, cutoff_s) for t in _TIME_TABLES}
    laps = frames["laps"]
    return RaceSnapshot(
        race=info,
        at=at,
        cutoff_s=cutoff_s,
        entries=entries,
        laps=laps,
        track_status=frames["track_status"],
        race_control=frames["race_control"],
        weather=frames["weather"],
        stints=rebuild_stints(laps),
        pit_events=rebuild_pit_events(laps),
        cars=rebuild_cars(laps, entries),
    )


def build_history(db_path: Path, at: AsOf, info: RaceInfo) -> History:
    """Every earlier in-sample race in full (results included), none from `info` onwards."""
    params: list[object] = [info.season, info.season, info.round]
    race_df = _db.read_df(
        db_path,
        f"SELECT race_id FROM races WHERE {_EARLIER_PREDICATE} ORDER BY season, round",
        params,
    )
    frames: dict[str, pd.DataFrame] = {}
    for table in _HISTORY_TABLES:
        sql = (
            f"SELECT * FROM {table} WHERE race_id IN "
            f"(SELECT race_id FROM races WHERE {_EARLIER_PREDICATE}) ORDER BY {_order(table)}"
        )
        frames[table] = _without_visibility(
            schema.normalize(table, _db.read_df(db_path, sql, params))
        )
    return History(
        as_of=at,
        races=[str(v) for v in race_df["race_id"]],
        entries=frames["entries"],
        laps=frames["laps"],
        track_status=frames["track_status"],
        race_control=frames["race_control"],
        weather=frames["weather"],
        lap_cutoffs=frames["lap_cutoffs"],
        results=frames["results"],
    )


__all__ = [
    "RACE_END",
    "AsOf",
    "History",
    "RaceEnd",
    "RaceInfo",
    "RaceSnapshot",
    "build_history",
    "build_snapshot",
    "race_info",
    "rebuild_cars",
    "rebuild_pit_events",
    "rebuild_stints",
]
