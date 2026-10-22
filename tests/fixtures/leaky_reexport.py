"""DELIBERATELY LEAKY test fixture: reaching private storage through a re-exporting module (CR-01).

Never import this from src/. Each function tries to get a raw-SQL handle on the cache without
naming `duckdb` and without importing `f1si.data._db` directly:

* `results_row_count_via_from_import` does `from f1si.data.asof import _db`;
* `laps_via_attribute` does `import f1si.data.asof as m; m._db.read_df(...)`.

Two independent layers must stop this, and the meta-test checks both: the import-ban scanner
flags the source (the CI canary copies this file into `src/f1si` and expects the build to fail),
and at runtime the modules no longer expose `_db` at all, so both functions fail on import or
attribute lookup instead of returning data.
"""

from pathlib import Path
from typing import Protocol

import pandas as pd


class _HasRaceId(Protocol):
    @property
    def race_id(self) -> str: ...


def results_row_count_via_from_import(db_path: Path, at: _HasRaceId) -> int:
    """Count the results table, which the as-of door never serves."""
    from f1si.data.asof import _db  # type: ignore[attr-defined]

    frame: pd.DataFrame = _db.read_df(db_path, "SELECT count(*) AS n FROM results")
    return int(frame["n"].iloc[0])


def laps_via_attribute(db_path: Path, at: _HasRaceId) -> pd.DataFrame:
    """Every lap of the race, whatever the cutoff."""
    import f1si.data.asof as asof_module

    frame: pd.DataFrame = asof_module._db.read_df(  # type: ignore[attr-defined]
        db_path, "SELECT * FROM laps WHERE race_id = ?", [at.race_id]
    )
    return frame
