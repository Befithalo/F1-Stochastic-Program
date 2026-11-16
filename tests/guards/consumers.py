"""Registry of as-of consumers checked by the future-scramble property test (D-02, DAT-04).

Every new consumer of the as-of door must be registered in `CONSUMERS` so that the scramble test
proves it ignores the future. A consumer is a function `(db_path, at) -> output`; the output is
compared exactly (DataFrames, dataclasses, lists, scalars). The stint plot data (plan 01-09) is
registered below.
"""

from pathlib import Path
from typing import Final

import numpy as np

from f1si.backtest.walk_forward import cutoff_consumer
from f1si.cli import _replay_at_cutoff
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.pace.kalman import current_stint_snapshots, filter_stints, resolve_priors
from f1si.pace.linear import fit_linear_pace, measure_pit_loss
from f1si.plots.stints import prepare_stint_plot_data
from f1si.plots.wear import prepare_wear_plot_data
from f1si.regime.sc_rate import estimate_sc_rate
from f1si.state import build_race_state
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


def linear_fit(db_path: Path, at: AsOf) -> object:
    """The joint fuel/wear fit and a few predictions (early cutoffs give an unidentified report)."""
    fit = fit_linear_pace(AsOfAccessor(db_path).snapshot(at))
    if not fit.is_identified:
        return fit.report, ()
    driver = np.array(sorted(fit.report.driver_offsets)[:2], dtype=np.int64)
    compound = np.array([fit.fitted_compounds[0]] * len(driver), dtype=np.str_)
    mean, sd = fit.predict(
        driver=driver,
        compound=compound,
        tire_age=np.array([3, 4], dtype=np.int64)[: len(driver)],
        lap=np.array([5, 6], dtype=np.int64)[: len(driver)],
    )
    return fit.report, tuple(float(v) for v in (*mean, *sd))


def pit_loss(db_path: Path, at: AsOf) -> object:
    """The pit-loss estimate from the visible stops."""
    snapshot = AsOfAccessor(db_path).snapshot(at)
    return measure_pit_loss(snapshot, fit_linear_pace(snapshot))


def race_state(db_path: Path, at: AsOf) -> object:
    """The RaceState built from the snapshot and its own fit, as JSON text and arrays."""
    snapshot = AsOfAccessor(db_path).snapshot(at)
    fit = fit_linear_pace(snapshot)
    pit = measure_pit_loss(snapshot, fit)
    lap = at.lap if isinstance(at.lap, int) else 12
    state = build_race_state(snapshot, fit, laps_total=max(12, lap), pit_loss_s=pit.median_s)
    first = state.cars[0].driver if state.cars else None
    arrays = state.to_arrays()
    return (
        state.to_json(),
        state.to_json_dict(),
        None if first is None else state.car(first),
        arrays.position.tolist(),
    )


def race_state_filter(db_path: Path, at: AsOf) -> object:
    """The RaceState built with the Kalman wear filter, so filter-fed state cannot see the future.

    The CLI `wear-filter` replay holds the accessor only in cli.py; this consumer proves the same
    snapshot -> fit -> filter -> state path ignores data after the cutoff (D-09, D-15).
    """
    snapshot = AsOfAccessor(db_path).snapshot(at)
    fit = fit_linear_pace(snapshot)
    pit = measure_pit_loss(snapshot, fit)
    lap = at.lap if isinstance(at.lap, int) else 12
    results = filter_stints(snapshot, fit)
    state = build_race_state(
        snapshot,
        fit,
        laps_total=max(12, lap),
        pit_loss_s=pit.median_s,
        wear_filter=current_stint_snapshots(results),
    )
    return state.to_json(), state.to_json_dict(), state.to_arrays().position.tolist()


def wear_plot_data(db_path: Path, at: AsOf) -> object:
    """The wear plot's prepared data (points, lines, panels)."""
    snapshot = AsOfAccessor(db_path).snapshot(at)
    return prepare_wear_plot_data(snapshot, fit_linear_pace(snapshot))


def sc_rate(db_path: Path, at: AsOf) -> object:
    """The safety-car rate and duration estimated from the earlier races."""
    return estimate_sc_rate(AsOfAccessor(db_path).history(at))


def wear_filter(db_path: Path, at: AsOf) -> object:
    """Per-stint Kalman wear estimates from the snapshot and its own fit, and current posteriors."""
    snapshot = AsOfAccessor(db_path).snapshot(at)
    fit = fit_linear_pace(snapshot)
    results = filter_stints(snapshot, fit)
    priors = resolve_priors(fit, "MEDIUM")
    return results, current_stint_snapshots(results), priors


def strategy_replay(db_path: Path, at: AsOf) -> object:
    """The CLI's cutoff-local Longstaff recommendation and ranked evidence."""
    accessor = AsOfAccessor(db_path)
    snapshot = accessor.snapshot(at)
    if snapshot.entries.empty:
        return ("unavailable", "No entrants are available.")
    distance = accessor.snapshot(AsOf(at.race_id, RACE_END))
    if distance.laps.empty:
        return ("unavailable", "No lap data are available.")
    laps_total = int(distance.laps["lap_number"].max())
    lap = at.lap if isinstance(at.lap, int) else laps_total
    code = sorted(str(value) for value in snapshot.entries["driver_code"])[0]
    result = _replay_at_cutoff(
        accessor,
        at.race_id,
        laps_total,
        code,
        lap,
        n_simulations=1,
        risk=0.5,
        seed=0,
    )
    if result.analysis is None:
        return ("unavailable", (), result.unavailable_reason)
    status = "fallback" if result.is_fallback else "available"
    evidence = tuple(
        (option.action, option.mean_finish, option.spread, option.cvar10, option.score)
        for option in result.analysis.options
    )
    return (status, evidence, result.analysis.reason)


CONSUMERS: Final[dict[str, Consumer]] = {
    "snapshot": snapshot,
    "history": history,
    "stints": stints,
    "pit_events": pit_events,
    "cars": cars,
    "stint_plot_data": stint_plot_data,
    "linear_fit": linear_fit,
    "pit_loss": pit_loss,
    "race_state": race_state,
    "race_state_filter": race_state_filter,
    "wear_plot_data": wear_plot_data,
    "sc_rate": sc_rate,
    "wear_filter": wear_filter,
    "strategy_replay": strategy_replay,
    "walk_forward_cutoff": cutoff_consumer,
}


# Registration is enforced, not trusted (WR-02): `test_consumer_registry.py` lists every public
# function and method of the DESIGNATED_MODULES and fails unless each one is either CONSUMED
# (some registered consumer calls it) or EXEMPT with a written reason. Adding a public function to
# one of these modules therefore forces a decision here. A module outside this list that reads
# race data must not hold the accessor unless the import-scan policy explicitly identifies it as a
# replay/backtest driver; model and plot code must receive prepared snapshots or values instead.
DESIGNATED_MODULES: Final = (
    "f1si.data.asof",
    "f1si.plots.stints",
    "f1si.pace.linear",
    "f1si.pace.kalman",
    "f1si.state",
    "f1si.plots.wear",
    "f1si.plots.wear_filter",
    "f1si.regime.sc_rate",
)

# qualified name -> name of the registered consumer that calls it
CONSUMED: Final[dict[str, str]] = {
    "f1si.data.asof.AsOfAccessor.snapshot": "snapshot",
    "f1si.data.asof.AsOfAccessor.history": "history",
    "f1si.plots.stints.prepare_stint_plot_data": "stint_plot_data",
    "f1si.pace.linear.fit_linear_pace": "linear_fit",
    "f1si.pace.linear.measure_pit_loss": "pit_loss",
    "f1si.pace.linear.LinearPaceFit.predict": "linear_fit",
    "f1si.plots.wear.prepare_wear_plot_data": "wear_plot_data",
    "f1si.state.build_race_state": "race_state",
    "f1si.state.RaceState.to_json": "race_state",
    "f1si.state.RaceState.to_json_dict": "race_state",
    "f1si.state.RaceState.car": "race_state",
    "f1si.state.RaceState.to_arrays": "race_state",
    "f1si.regime.sc_rate.estimate_sc_rate": "sc_rate",
    "f1si.pace.kalman.filter_stints": "wear_filter",
    "f1si.pace.kalman.resolve_priors": "wear_filter",
    "f1si.pace.kalman.current_stint_snapshots": "wear_filter",
}

# qualified name -> why no scramble consumer is needed
_PURE_MATHS: Final = "pure array maths; takes numbers, never a snapshot or accessor (D-09)"
EXEMPT: Final[dict[str, str]] = {
    "f1si.data.asof.catalog": "calendar facts (names, dates, eras) of every race are public",
    "f1si.data.asof.resolve_slug": "maps a name to a race id using the calendar only",
    "f1si.plots.stints.build_figure": "pure drawing of already-prepared StintPlotData",
    "f1si.plots.stints.render_stint_plot": "writes a figure of prepared StintPlotData to disk",
    "f1si.pace.linear.LinearPaceFit.wear_rate": "pure lookup of already fitted values",
    "f1si.pace.linear.LinearPaceFit.wear_se": "pure lookup of already fitted values",
    "f1si.pace.linear.LinearPaceFit.pace_offset": "pure lookup of already fitted values",
    "f1si.pace.linear.LinearPaceFit.pace_offset_se": "pure lookup of already fitted values",
    "f1si.plots.wear.build_wear_figure": "pure drawing of already-prepared WearPlotData",
    "f1si.plots.wear.render_wear_plot": "writes a figure of prepared WearPlotData to disk",
    "f1si.plots.wear.wear_file_name": "string function of a validated slug",
    "f1si.plots.stints.plot_file_name": "string function of a slug and driver codes",
    "f1si.pace.linear.truncated_variance_factor": "pure math of a number, reads no race data",
    "f1si.pace.linear.untruncated_sigma": "pure math of two numbers, reads no race data",
    "f1si.state.RaceState.laps_done_of": "pure lookup of a value already stored in the state",
    "f1si.pace.kalman.WearFilter.observe": _PURE_MATHS,
    "f1si.pace.kalman.WearFilter.snapshot": _PURE_MATHS,
    "f1si.pace.kalman.posterior_rate_sd": _PURE_MATHS,
    "f1si.pace.kalman.cutoff_row": "pure lookup over already-computed results",
    "f1si.pace.kalman.cutoff_rows": "pure lookup over already-computed results",
    "f1si.plots.wear_filter.prepare_wear_filter_data": (
        "takes already-computed CutoffRow values, no snapshot"
    ),
    "f1si.plots.wear_filter.build_wear_filter_figure": (
        "pure drawing of already-prepared WearFilterPlotData"
    ),
    "f1si.plots.wear_filter.render_wear_filter_plot": (
        "writes a figure of prepared WearFilterPlotData to disk"
    ),
    "f1si.plots.wear_filter.wear_filter_file_name": "string function of a validated slug and code",
}
