"""Registry of as-of consumers checked by the future-scramble property test (D-02, DAT-04).

Every new consumer of the as-of door must be registered in `CONSUMERS` so that the scramble test
proves it ignores the future. A consumer is a function `(db_path, at) -> output`; the output is
compared exactly (DataFrames, dataclasses, lists, scalars). Plan 01-09 adds the stint plot data.
"""

from pathlib import Path
from typing import Final

from f1si.data.asof import AsOf, AsOfAccessor
from tests.guards.scramble import Consumer


def snapshot(db_path: Path, at: AsOf) -> object:
    """The whole snapshot."""
    return AsOfAccessor(db_path).snapshot(at)


def history(db_path: Path, at: AsOf) -> object:
    """The whole history."""
    return AsOfAccessor(db_path).history(at)


def stints(db_path: Path, at: AsOf) -> object:
    """Stints rebuilt from visible laps."""
    return AsOfAccessor(db_path).snapshot(at).stints


def pit_events(db_path: Path, at: AsOf) -> object:
    """Pit events rebuilt from visible laps."""
    return AsOfAccessor(db_path).snapshot(at).pit_events


def cars(db_path: Path, at: AsOf) -> object:
    """Per-car laps done, stops and position rebuilt from visible laps."""
    return AsOfAccessor(db_path).snapshot(at).cars


CONSUMERS: Final[dict[str, Consumer]] = {
    "snapshot": snapshot,
    "history": history,
    "stints": stints,
    "pit_events": pit_events,
    "cars": cars,
}
