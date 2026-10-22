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


# Registration is enforced, not trusted (WR-02): `test_consumer_registry.py` lists every public
# function and method of the DESIGNATED_MODULES and fails unless each one is either CONSUMED
# (some registered consumer calls it) or EXEMPT with a written reason. Adding a public function to
# one of these modules therefore forces a decision here. A module outside this list that reads
# race data must not hold the accessor at all: the import scan allows `AsOfAccessor` and
# `RACE_END` only in the replay drivers and the CLI.
DESIGNATED_MODULES: Final = ("f1si.data.asof", "f1si.plots.stints")

# qualified name -> name of the registered consumer that calls it
CONSUMED: Final[dict[str, str]] = {
    "f1si.data.asof.AsOfAccessor.snapshot": "snapshot",
    "f1si.data.asof.AsOfAccessor.history": "history",
    "f1si.plots.stints.prepare_stint_plot_data": "stint_plot_data",
}

# qualified name -> why no scramble consumer is needed
EXEMPT: Final[dict[str, str]] = {
    "f1si.data.asof.catalog": "calendar facts (names, dates, eras) of every race are public",
    "f1si.data.asof.resolve_slug": "maps a name to a race id using the calendar only",
    "f1si.plots.stints.build_figure": "pure drawing of already-prepared StintPlotData",
    "f1si.plots.stints.render_stint_plot": "writes a figure of prepared StintPlotData to disk",
    "f1si.plots.stints.plot_file_name": "string function of a slug and driver codes",
}
