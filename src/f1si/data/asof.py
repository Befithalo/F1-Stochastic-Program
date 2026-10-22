"""The as-of door: the public way to read cached race data.

Design (three doors). `f1si.data.asof` serves what was knowable at a cutoff on the race clock
(snapshots and history, added in plan 01-07) plus the race catalog; `f1si.data.results` serves
final outcomes and only the backtest scorer may import it; `f1si.data.out_of_sample` serves the
locked 2026 data and only the holdout evaluation may import it. No flag opens a door.

This module currently offers `catalog`: calendar facts only, never results.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from f1si.data import _db

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
    return _db.read_df(db_path, _CATALOG_SQL)
