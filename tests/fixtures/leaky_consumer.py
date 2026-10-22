"""DELIBERATELY LEAKY test fixture for the D-02 meta-test and CI canary.

Never import this from src/. It opens the DuckDB file directly (a back door around the as-of
door) and averages the whole race, ignoring any cutoff. The import-ban scanner must flag it, and
the CI canary copies it into `src/f1si` to prove that the build then fails.
"""

from pathlib import Path
from typing import Protocol

import duckdb


class _HasRaceId(Protocol):
    @property
    def race_id(self) -> str: ...


def mean_lap_time_whole_race(db_path: Path, at: _HasRaceId) -> float:
    """Mean lap time over the entire race, including laps that have not happened yet."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        row = con.execute(
            "SELECT avg(lap_time_s) FROM laps WHERE race_id = ?", [at.race_id]
        ).fetchone()
    finally:
        con.close()
    if row is None or row[0] is None:
        return 0.0
    return float(row[0])
