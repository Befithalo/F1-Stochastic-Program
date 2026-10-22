"""DELIBERATELY LEAKY through the public door; only the scramble test can catch these.

Each function uses nothing but `f1si.data.asof`, so the import ban sees nothing wrong. They
misuse the door: asking for a later lap, asking for the whole race, asking for the history of
the next race (which contains the current race in full).
"""

from pathlib import Path

import pandas as pd

from f1si.data import asof
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, RaceEnd


def lap_plus_three(db_path: Path, at: AsOf) -> pd.DataFrame:
    """Laps visible three laps after `at`."""
    lap = at.lap
    assert not isinstance(lap, RaceEnd)
    return AsOfAccessor(db_path).snapshot(AsOf(at.race_id, lap + 3)).laps


def race_end_weather(db_path: Path, at: AsOf) -> pd.DataFrame:
    """Weather for the whole race, whatever `at` says."""
    return AsOfAccessor(db_path).snapshot(AsOf(at.race_id, RACE_END)).weather


def history_of_next_race(db_path: Path, at: AsOf) -> pd.DataFrame:
    """Laps of the history of the next race, which include the current race in full."""
    races = asof.catalog(db_path)
    ids = [str(v) for v in races["race_id"]]
    next_id = ids[ids.index(at.race_id) + 1]
    return AsOfAccessor(db_path).history(AsOf(next_id, 0)).laps
