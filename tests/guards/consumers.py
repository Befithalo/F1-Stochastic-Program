"""Registry of as-of consumers checked by the future-scramble property test (D-02, DAT-04).

Every new consumer of the as-of door must be registered in `CONSUMERS` so that the scramble test
proves it ignores the future. A consumer is a function `(db_path, at) -> output`; the output is
compared exactly (DataFrames, dataclasses, lists, scalars). The stint plot data (plan 01-09) is
registered below.
"""

from pathlib import Path
from typing import Final

from f1si.data.asof import AsOf, AsOfAccessor
from f1si.plots.stints import prepare_stint_plot_data
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


def stint_plot_data(db_path: Path, at: AsOf) -> object:
    """The stint plot's prepared data (points, y-range, panel titles, stint starts)."""
    return prepare_stint_plot_data(AsOfAccessor(db_path).snapshot(at))


CONSUMERS: Final[dict[str, Consumer]] = {
    "snapshot": snapshot,
    "history": history,
    "stints": stints,
    "pit_events": pit_events,
    "cars": cars,
    "stint_plot_data": stint_plot_data,
}
