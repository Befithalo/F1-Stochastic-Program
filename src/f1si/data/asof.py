"""The as-of door: the public way to read cached race data.

Three doors guard the cache (D-01..D-04). Nothing else reads it.

* `f1si.data.asof` (this module, public) answers "what did we know at lap N of race R?" with a
  `RaceSnapshot`, and "what happened in earlier races?" with a `History`. It also lists the race
  catalog (calendar facts only).
* `f1si.data.results` serves final outcomes (classification, points, total time). Only
  `f1si.backtest.scoring` may import it; no flag on this door opens it.
* `f1si.data.out_of_sample` serves the locked 2026 races. Only `f1si.evaluation.holdout` may
  import it. Every 2026 race raises `OutOfSampleLockedError` here.

Snapshots are plain data, not capabilities. Model and strategy code receives a `RaceSnapshot`;
only the replay or backtest driver holds the `AsOfAccessor`, so model code cannot ask for lap
N+3. The import ban and the future-scramble test enforce this (tests/guards).

Cutoffs. "Lap N" means the moment the race leader completed lap N, read from the precomputed
`lap_cutoffs` table. A row is visible iff `visible_at_s IS NOT NULL AND visible_at_s <= cutoff`.
At lap N the leader therefore shows N laps and every other running car N-1; lap 0 shows only
pre-race facts (entries, weather and race-control messages up to lights out).

`RACE_END` shows every row of the race through the same door, still without results.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from f1si.data._snapshot import RACE_END, AsOf, History, RaceEnd, RaceInfo, RaceSnapshot
from f1si.data.errors import OutOfSampleLockedError, UnknownRaceError

__all__ = [
    "RACE_END",
    "AsOf",
    "AsOfAccessor",
    "History",
    "RaceEnd",
    "RaceInfo",
    "RaceSnapshot",
    "catalog",
    "resolve_slug",
]

_CATALOG_SQL = (
    "SELECT race_id, season, round, slug, event_name, circuit, era, out_of_sample, source, "
    "load_status FROM races ORDER BY season, round"
)


def catalog(db_path: Path) -> pd.DataFrame:
    """Calendar facts for every cached race, ordered by season and round.

    Columns: race_id, season, round, slug, event_name, circuit, era, out_of_sample, source,
    load_status.

    Raises:
        CacheMissingError: if no cache exists at `db_path`.
        CacheBusyError: if another process holds the cache open.
    """
    from f1si.data import _db  # local import: asof must not re-export the storage module (CR-01)

    return _db.read_df(db_path, _CATALOG_SQL)


def resolve_slug(db_path: Path, slug_or_race_id: str) -> str:
    """Return the race_id for a slug (such as `bahrain-2023`) or a race_id (`2023-01`).

    Raises:
        UnknownRaceError: if nothing matches; the message lists the closest slugs.
    """
    cat = catalog(db_path)
    done = cat[cat["load_status"] == "complete"]
    for _, row in done.iterrows():
        if slug_or_race_id in (row["race_id"], row["slug"]):
            return str(row["race_id"])
    known = [str(v) for v in done["slug"]] + [str(v) for v in done["race_id"]]
    raise UnknownRaceError(slug_or_race_id, known)


class AsOfAccessor:
    """Read-only access to what was knowable at a point of a race (D-01, D-04).

    Exactly two methods, and no flags: results, 2026 data and look-ahead are not reachable here.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @staticmethod
    def _check(info: RaceInfo) -> None:
        if info.out_of_sample:
            raise OutOfSampleLockedError(info.race_id)

    def snapshot(self, at: AsOf) -> RaceSnapshot:
        """Rows of race `at.race_id` visible at `at`, with stints, pit events and cars rebuilt.

        Raises:
            UnknownRaceError: unknown race id.
            OutOfSampleLockedError: the race is a 2026 race.
            LapOutOfRangeError: `at.lap` is beyond the last lap.
        """
        from f1si.data import _snapshot  # local import: not a module attribute (CR-01)

        return _snapshot.guarded_snapshot(self._db_path, at, self._check)

    def history(self, at: AsOf) -> History:
        """Every earlier in-sample race in full, results included; never `at.race_id` or later.

        Raises:
            UnknownRaceError: unknown race id.
            OutOfSampleLockedError: the race is a 2026 race.
        """
        from f1si.data import _snapshot  # local import: not a module attribute (CR-01)

        return _snapshot.guarded_history(self._db_path, at, self._check)
