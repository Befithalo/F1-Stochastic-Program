"""The results door: final outcomes of finished in-sample races (D-03).

Only `f1si.backtest.scoring` (Phase 6) may import this module; the import ban enforces it. The
as-of door never serves any of these columns and has no flag to ask for them. The 2026 races
stay locked here too (`OutOfSampleLockedError`); `f1si.data.out_of_sample` serves their results.

This module deliberately does not import `f1si.data._snapshot`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from f1si.data import _db
from f1si.data.errors import OutOfSampleLockedError, UnknownRaceError

__all__ = ["ResultsAccessor"]

_RACE_SQL = "SELECT out_of_sample FROM races WHERE race_id = ? AND load_status = 'complete'"
_KNOWN_SQL = "SELECT race_id, slug FROM races WHERE load_status = 'complete'"
_RESULTS_SQL = (
    "SELECT r.race_id, r.driver_number, e.driver_code, r.final_position, r.classified_position, "
    "r.status, r.points, r.laps_completed, r.total_time_s "
    "FROM results r JOIN entries e ON e.race_id = r.race_id AND e.driver_number = r.driver_number "
    "WHERE r.race_id = ? ORDER BY r.final_position NULLS LAST, r.driver_number"
)


class ResultsAccessor:
    """Final classification of finished in-sample races."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def final_classification(self, race_id: str) -> pd.DataFrame:
        """Final results, ordered by final_position (unclassified last), with driver_code.

        Columns: race_id, driver_number, driver_code, final_position, classified_position,
        status, points, laps_completed, total_time_s.

        Raises:
            UnknownRaceError: unknown race id.
            OutOfSampleLockedError: the race is a 2026 race.
        """
        race = _db.read_df(self._db_path, _RACE_SQL, [race_id])
        if race.empty:
            known_df = _db.read_df(self._db_path, _KNOWN_SQL)
            known = [str(v) for v in known_df["race_id"]] + [str(v) for v in known_df["slug"]]
            raise UnknownRaceError(race_id, known)
        if bool(race["out_of_sample"].iloc[0]):
            raise OutOfSampleLockedError(race_id)
        return _db.read_df(self._db_path, _RESULTS_SQL, [race_id])
