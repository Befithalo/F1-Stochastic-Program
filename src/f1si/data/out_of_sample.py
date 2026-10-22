"""The out-of-sample door: the locked 2026 races (D-04, DAT-05).

Only `f1si.evaluation.holdout` (Phase 8) may import this module; the import ban enforces it. The
holdout is touched once per milestone (BKT-05). Snapshots obey exactly the same cutoff rule as
the as-of door; final results are served by `final_classification`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from f1si.data._snapshot import AsOf, RaceInfo, RaceSnapshot

__all__ = ["OutOfSampleAccessor"]

_RESULTS_SQL = (
    "SELECT r.race_id, r.driver_number, e.driver_code, r.final_position, r.classified_position, "
    "r.status, r.points, r.laps_completed, r.total_time_s "
    "FROM results r JOIN entries e ON e.race_id = r.race_id AND e.driver_number = r.driver_number "
    "WHERE r.race_id = ? ORDER BY r.final_position NULLS LAST, r.driver_number"
)


class OutOfSampleAccessor:
    """Snapshots and final results of out-of-sample (2026) races only."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _info(self, race_id: str) -> RaceInfo:
        from f1si.data import _snapshot  # local import: not a module attribute (CR-01)

        info = _snapshot.race_info(self._db_path, race_id)
        if not info.out_of_sample:
            raise ValueError(f"{race_id} is in-sample; use f1si.data.asof.AsOfAccessor")
        return info

    def snapshot(self, at: AsOf) -> RaceSnapshot:
        """Rows of an out-of-sample race visible at `at` (same cutoff rule as the as-of door).

        Raises:
            UnknownRaceError: unknown race id.
            ValueError: the race is in-sample (use `f1si.data.asof.AsOfAccessor`).
            LapOutOfRangeError: `at.lap` is beyond the last lap.
        """
        from f1si.data import _snapshot  # local import: not a module attribute (CR-01)

        return _snapshot.build_snapshot(self._db_path, at, self._info(at.race_id))

    def final_classification(self, race_id: str) -> pd.DataFrame:
        """Final results of an out-of-sample race, ordered by final_position, with driver_code.

        Raises:
            UnknownRaceError: unknown race id.
            ValueError: the race is in-sample.
        """
        from f1si.data import _db  # local import: not a module attribute (CR-01)

        info = self._info(race_id)
        return _db.read_df(self._db_path, _RESULTS_SQL, [info.race_id])
