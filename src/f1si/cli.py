"""Command-line entry point for f1si.

Subcommands: `load` (fill the cache), `races` (list cached races with their regulation era),
`plot` (lap time by stint for one cached race) and `wear` (fitted tyre wear, fuel effect and pit
loss for one cached race), `plan` (fastest free-track 1- and 2-stop plans for one driver) and
`simulate` (a driver's finishing-position distribution from many simulated race continuations).
Exit codes: 0 ok, 1 user-facing error, 2 some races failed.
"""

import argparse
import re
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

import f1si
from f1si import paths
from f1si.data import asof
from f1si.data.errors import F1siDataError, OutOfSampleLockedError
from f1si.data.loader import load_races
from f1si.data.sources import RaceSource, SourceError
from f1si.data.sources.openf1 import OpenF1Source
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.eras import ERAS, UnknownEraError
from f1si.interfaces import DRY_COMPOUNDS, Plan
from f1si.pace.linear import (
    DEFAULT_PIT_LOSS_S,
    FUEL_SANITY_RANGE,
    MIN_CLEAN_LAPS_PER_COMPOUND,
    MIN_STINTS_PER_COMPOUND,
    PitLossEstimate,
    fit_linear_pace,
    measure_pit_loss,
)
from f1si.plots.simulate import prepare_sim_plot_data, render_sim_plot, sim_file_name
from f1si.plots.stints import (
    UnknownDriverError,
    plot_file_name,
    prepare_stint_plot_data,
    render_stint_plot,
)
from f1si.plots.wear import prepare_wear_plot_data, render_wear_plot, wear_file_name
from f1si.regime.sc_rate import ScRateEstimate, estimate_sc_rate
from f1si.rng import DEFAULT_SEED, make_rng
from f1si.sim.constants import MAX_RACES
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import CarState, RaceState, build_race_state
from f1si.strategy.free_track import FreeTrackOptimizer, PlanRefusedError

_FRIENDLY_VALUE_ERRORS = frozenset({"plot", "wear", "plan", "simulate"})
_DRIVER_CODE = re.compile(r"[A-Z]{3}")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="f1si",
        description="F1 Stochastic Intelligence Platform",
    )
    parser.add_argument("--version", action="version", version=f"f1si {f1si.__version__}")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="folder holding the DuckDB cache (default: $F1SI_DATA_DIR or ./data)",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=None,
        help="folder for generated plots (default: $F1SI_REPORTS_DIR or ./reports)",
    )
    parser.add_argument("--debug", action="store_true", help="show full tracebacks on errors")
    sub = parser.add_subparsers(dest="command", required=True)

    load = sub.add_parser("load", help="load races into the local cache")
    load.add_argument(
        "--source",
        choices=["openf1", "synthetic"],
        default="openf1",
        help="where races come from (default: openf1, real races from OpenF1 + Jolpica)",
    )
    load.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help=f"random seed (default {DEFAULT_SEED})"
    )
    load.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=None,
        metavar="YEAR",
        help="seasons to load (default: the source's default seasons)",
    )
    load.add_argument(
        "--only",
        nargs="+",
        default=None,
        metavar="RACE",
        help="load only these races, by slug (for example alpha-2023) or race id (2023-01)",
    )

    sub.add_parser("races", help="list cached races and their regulation era")

    plot = sub.add_parser("plot", help="plot lap time by stint for one cached race")
    plot.add_argument("slug", metavar="SLUG", help="race slug (for example bahrain-2023)")
    plot.add_argument(
        "--drivers",
        nargs="+",
        default=None,
        metavar="CODE",
        help="only these driver codes, for example VER HAM (default: all drivers)",
    )

    wear = sub.add_parser(
        "wear", help="fitted tyre wear (s/lap per compound), fuel effect and pit loss"
    )
    wear.add_argument("slug", metavar="SLUG", help="race slug (for example bahrain-2023)")
    wear.add_argument(
        "--lap",
        type=int,
        default=None,
        metavar="N",
        help="use only laps visible after the leader's lap N, for example 20 "
        "(default: the whole race)",
    )
    plan = sub.add_parser("plan", help="fastest free-track 1- and 2-stop pit plans for one driver")
    plan.add_argument("slug", metavar="SLUG", help="race slug (for example bahrain-2023)")
    plan.add_argument(
        "--driver",
        default=None,
        metavar="CODE",
        help="driver code, for example ALO (default: the leader at the shown cutoff)",
    )
    plan.add_argument(
        "--lap",
        type=int,
        default=None,
        metavar="N",
        help="plan from data visible after the leader's lap N, for example 20 "
        "(default: hindsight plan using the whole race)",
    )
    simulate = sub.add_parser(
        "simulate", help="finishing-position distribution of one driver from simulated races"
    )
    simulate.add_argument("slug", metavar="SLUG", help="race slug (for example bahrain-2023)")
    simulate.add_argument(
        "--driver",
        required=True,
        metavar="CODE",
        help="driver code, for example ALO (any case). Unlike plan, a driver on wet or "
        "intermediate tyres is simulated with borrowed dry pace",
    )
    simulate.add_argument(
        "--lap",
        type=int,
        default=None,
        metavar="N",
        help="simulate from the state after the leader's lap N using only data known then "
        "(default: hindsight simulation from lap 0 with a pace fit from the whole race)",
    )
    simulate.add_argument(
        "--n",
        type=int,
        default=50000,
        metavar="N",
        help=f"number of simulated races, 2 to {MAX_RACES} (default 50000); memory grows "
        "with N, about 1 GB at the maximum",
    )
    simulate.add_argument(
        "--seed",
        type=int,
        default=0,
        metavar="S",
        help="random seed, 0 or more, passed to make_rng (default 0)",
    )
    return parser


def _cmd_load(
    data_dir: Path,
    source_name: str,
    seed: int,
    seasons: Sequence[int] | None,
    only: Sequence[str] | None,
) -> int:
    source: RaceSource
    if source_name == "openf1":
        source = OpenF1Source(http_cache_dir=paths.http_cache_dir(data_dir), echo=print)
        chosen = source.default_seasons if seasons is None else tuple(seasons)
        print(
            f"Loading seasons {', '.join(str(s) for s in chosen)} from OpenF1 + Jolpica. "
            "New races take about 15 s each; finished races are kept if you stop with Ctrl+C."
        )
    else:
        source = SyntheticSource(rng=make_rng(seed))
        chosen = source.default_seasons if seasons is None else tuple(seasons)
    db = paths.db_path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    report = load_races(
        source,
        db,
        chosen,
        now=datetime.now(UTC),
        echo=print,
        only=only,
    )
    return report.exit_code


def _cmd_races(data_dir: Path) -> int:
    cat = asof.catalog(paths.db_path(data_dir))
    header = ("RACE ID", "SLUG", "SEASON", "ROUND", "ERA", "OUT-OF-SAMPLE")
    rows = [
        (
            str(r.race_id),
            str(r.slug),
            str(r.season),
            str(r.round),
            str(r.era),
            "yes (locked)" if bool(r.out_of_sample) else "no",
        )
        for r in cat.itertuples(index=False)
    ]
    if not rows:
        print("No races cached yet. Run: uv run f1si load")
        return 0
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(header)]
    for line in (header, *rows):
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip())
    locked = sum(1 for row in rows if row[5] != "no")
    print(f"{len(rows)} races cached ({locked} out-of-sample and locked).")
    return 0


def _cmd_plot(data_dir: Path, reports_dir: Path, slug: str, drivers: Sequence[str] | None) -> int:
    db = paths.db_path(data_dir)
    race_id = asof.resolve_slug(db, slug)
    try:
        snapshot = asof.AsOfAccessor(db).snapshot(asof.AsOf(race_id, asof.RACE_END))
    except OutOfSampleLockedError as err:
        print(
            f"{err} 2026 races are out-of-sample, so they cannot be plotted in Phase 1.",
            file=sys.stderr,
        )
        return 1
    data = prepare_stint_plot_data(snapshot, drivers=drivers)
    out = reports_dir / plot_file_name(snapshot.race.slug, drivers)
    render_stint_plot(data, out)
    print(
        f"Wrote {out} ({len(data.drivers)} drivers; {data.skipped_laps} laps without a time "
        "were skipped). Open it to see lap times by stint."
    )
    return 0


def _cmd_wear(data_dir: Path, reports_dir: Path, slug: str, lap: int | None) -> int:
    """Print fitted wear per compound, the fuel effect, the pit loss and what was dropped."""
    db = paths.db_path(data_dir)
    race_id = asof.resolve_slug(db, slug)
    if lap is not None and lap < 0:
        print(
            f"--lap must be 0 or more, got {lap}. Try: uv run f1si wear {slug} --lap 20",
            file=sys.stderr,
        )
        return 1
    at = asof.AsOf(race_id, asof.RACE_END if lap is None else lap)
    try:
        snapshot = asof.AsOfAccessor(db).snapshot(at)
    except OutOfSampleLockedError as err:
        print(
            f"{err} 2026 races are out-of-sample, so they cannot be analysed in Phase 2.",
            file=sys.stderr,
        )
        return 1
    fit = fit_linear_pace(snapshot)
    report = fit.report
    if not fit.is_identified:
        hint = "" if lap is None else f" Try: uv run f1si wear {slug} --lap {max(lap + 20, 40)}"
        print(f"Not enough laps yet to fit tyre wear: {report.message}.{hint}", file=sys.stderr)
        return 1
    race = snapshot.race
    where = "at the end of the race" if lap is None else f"after lap {lap}"
    print(
        f"{race.event_name} {race.season}: tyre wear {where} "
        f"({len(report.driver_offsets)} drivers, {report.n_clean} clean laps)"
    )
    header = ("COMPOUND", "WEAR (s/lap)", "95% INTERVAL", "CLEAN LAPS")
    rows = [
        (
            c.compound,
            f"{c.wear_s_per_lap:+.3f}",
            f"{c.ci_low:+.3f} to {c.ci_high:+.3f}",
            str(c.n_laps),
        )
        for c in report.compounds
    ]
    rows += [
        (
            name,
            f"not enough data (needs {MIN_CLEAN_LAPS_PER_COMPOUND} clean laps in at least "
            f"{MIN_STINTS_PER_COMPOUND} stints)",
            "",
            "",
        )
        for name in report.not_enough_data
    ]
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(header)]
    for line in (header, *rows):
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip())
    assert report.fuel_s_per_lap is not None
    assert report.fuel_ci_low is not None
    assert report.fuel_ci_high is not None
    low, high = FUEL_SANITY_RANGE
    print(
        f"Fuel effect: {report.fuel_s_per_lap:+.3f} s/lap (95% interval "
        f"{report.fuel_ci_low:+.3f} to {report.fuel_ci_high:+.3f}); literature range about "
        f"{low:+.3f} to {high:+.3f} s/lap (approximate; negative = car gets faster)"
    )
    if not low <= report.fuel_s_per_lap <= high:
        print(
            "Outside the literature range: this estimate likely also absorbs track evolution. "
            "It is reported as measured, not clamped."
        )
    pit = measure_pit_loss(snapshot, fit)
    if pit.is_default:
        print(f"Pit loss: {DEFAULT_PIT_LOSS_S:.1f} s (default: no green-flag stop seen yet)")
    else:
        print(
            f"Pit loss: median {pit.median_s:.1f} s over {pit.n_stops} green-flag stops "
            f"(10-90% range {pit.p10_s:.1f} to {pit.p90_s:.1f} s)"
        )
    dropped = sorted(report.dropped.items(), key=lambda kv: (-kv[1], kv[0]))
    print("Laps dropped: " + (", ".join(f"{k}={v}" for k, v in dropped) or "none"))
    print(
        "Note: compound pace offsets are not modeled; "
        "compound choice among near-ties is not meaningful."
    )
    out = reports_dir / wear_file_name(race.slug)
    render_wear_plot(prepare_wear_plot_data(snapshot, fit), out)
    print(f"Wrote {out}. Open it to see fuel-corrected lap time against tyre age.")
    return 0


_HINDSIGHT_LABEL = (
    "Hindsight plan: priced with a fit from the whole race. It makes no claim of foresight."
)
_PLAN_NOTES = (
    "Free-track plan: no traffic, overtaking or safety cars, so this is a lower bound on race "
    "time, not a forecast.",
    "Note: compound pace offsets are not modeled; compound choice among near-ties is not "
    "meaningful.",
    "A stop at lap k means you come in on lap k; lap k+1 is the first lap on the new tyres.",
)


def _fmt_time(seconds: float) -> str:
    """Seconds as h:mm:ss.s."""
    tenths = round(seconds * 10)
    hours, rest = divmod(tenths, 36000)
    minutes, rest = divmod(rest, 600)
    return f"{hours}:{minutes:02d}:{rest / 10:04.1f}"


def _print_table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(header)]
    for line in (header, *rows):
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip())


def _plan_rows(
    plans: Sequence[Plan], ranked: Sequence[Plan], car: CarState
) -> list[tuple[str, ...]]:
    best = ranked[0].total_time_s
    return [
        (
            str(ranked.index(plan) + 1),
            str(car.stops_done + plan.n_stops),
            ", ".join(str(k) for k in plan.stop_laps) or "none",
            " > ".join((str(car.compound), *plan.compounds)),
            _fmt_time(plan.total_time_s),
            f"+{plan.total_time_s - best:.1f} s",
        )
        for plan in plans
    ]


def _wet_codes(end: asof.RaceSnapshot) -> set[str]:
    """Driver codes that ran on a non-dry compound at any point of the race."""
    names = end.entries.set_index("driver_number")["driver_code"]
    wet: set[str] = set()
    for frame in (end.stints, end.laps):
        compounds = frame["compound"].astype("object")
        for number, compound in zip(frame["driver_number"], compounds, strict=True):
            if isinstance(compound, str) and compound.upper() not in DRY_COMPOUNDS:
                wet.add(str(names.get(int(number), "")))
    wet.discard("")
    return wet


def _actual_strategy(snapshot: asof.RaceSnapshot, number: int) -> tuple[list[str], list[int]]:
    """The driver's visible compounds in stint order and the in-laps of the visible stops."""
    stints = snapshot.stints[snapshot.stints["driver_number"] == number].sort_values("stint")
    tyres = [str(c).upper() for c in stints["compound"].astype("object")]
    pits = snapshot.pit_events[snapshot.pit_events["driver_number"] == number]
    return tyres, [int(k) for k in pits.sort_values("in_lap")["in_lap"]]


def _pick_driver(
    shown: asof.RaceSnapshot, leader_from: asof.RaceSnapshot, driver: str | None
) -> str:
    """Validate the requested code (D-08) or default to the leader of `leader_from`."""
    if driver is not None:
        code = driver.upper()
        if not _DRIVER_CODE.fullmatch(code):
            raise ValueError(f"Driver codes are three letters, like VER; got {driver}")
        codes = sorted(str(c) for c in shown.cars["driver_code"])
        if code not in codes:
            raise UnknownDriverError([code], codes)
        return code
    cars = leader_from.cars[leader_from.cars["position"] == 1]
    if cars.empty:
        raise ValueError("No car has completed a lap yet. Try: uv run f1si plan SLUG --lap 20")
    return str(cars.iloc[0]["driver_code"])


def _refuse(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _cmd_plan(data_dir: Path, slug: str, driver: str | None, lap: int | None) -> int:
    """Print the best 1-stop, best 2-stop and top 5 free-track plans for one driver."""
    db = paths.db_path(data_dir)
    race_id = asof.resolve_slug(db, slug)
    if lap is not None and lap < 0:
        return _refuse(
            f"--lap must be 0 or more, got {lap}. Try: uv run f1si plan {slug} --driver CODE"
        )
    accessor = asof.AsOfAccessor(db)
    try:
        end = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
        # The race distance is public (D-21), and the CLI is a replay driver, so it may read it
        # from the completed race. In mid-race mode nothing else of `end` is used.
        laps_total = int(end.laps["lap_number"].max())
        if lap is None:
            fit_snapshot = end
            state_snapshot = accessor.snapshot(asof.AsOf(race_id, 0))
        elif lap >= laps_total:
            return _refuse(
                f"Nothing to plan: the race is over after lap {laps_total}. "
                f"Try: uv run f1si plan {slug} --driver CODE --lap {max(laps_total - 20, 20)}"
            )
        else:
            fit_snapshot = state_snapshot = accessor.snapshot(asof.AsOf(race_id, lap))
    except OutOfSampleLockedError as err:
        return _refuse(
            f"{err} 2026 races are out-of-sample, so they cannot be analysed in Phase 2."
        )
    fit = fit_linear_pace(fit_snapshot)
    if not fit.is_identified:
        retry = 20 if lap is None or lap < 10 else lap + 10
        shown = "in this race" if lap is None else f"after lap {lap}"
        return _refuse(
            f"Cannot plan: not enough laps yet to fit wear {shown} ({fit.report.message}); "
            f"try --lap {retry}. Example: uv run f1si plan {slug} --driver CODE --lap {retry}"
        )
    pit = measure_pit_loss(fit_snapshot, fit)
    state = build_race_state(state_snapshot, fit, laps_total=laps_total, pit_loss_s=pit.median_s)
    code = _pick_driver(state_snapshot, state_snapshot if lap is not None else end, driver)
    if lap is None:
        wet = _wet_codes(end)
        if code in wet:
            others = [c.driver for c in state.cars if c.driver not in wet and c.driver != code]
            return _refuse(
                f"{code} ran on wet or intermediate tyres in this race; wet and intermediate "
                "strategy is out of scope for the free-track optimizer. "
                f"Try: uv run f1si plan {slug} --driver {others[0] if others else 'VER'}"
            )
    optimizer = FreeTrackOptimizer(fit, compounds=fit.fitted_compounds)
    try:
        ranked = optimizer.rank_plans(state, driver=code)
    except PlanRefusedError as err:
        return _refuse(f"{err} Try: uv run f1si plan {slug} --driver {code} --lap 20")
    car = state.car(code)
    race = end.race
    print(f"{race.event_name} {race.season}: {code}")
    print(_HINDSIGHT_LABEL if lap is None else f"Plan after lap {lap}")
    _print_plan_report(state, car, ranked, pit, hindsight=lap is None)
    source = end if lap is None else state_snapshot
    tyres, stops = _actual_strategy(source, car.driver_number)
    if lap is not None:
        print(
            f"Actual strategy so far: {' > '.join(tyres) or 'unknown'}, stops on laps "
            f"{', '.join(str(k) for k in stops) or 'none'} (visible stints only; not priced)"
        )
    else:
        print(_compare_line(optimizer, state, car, ranked[0], tyres, stops, fit.fitted_compounds))
    return 0


def _print_plan_report(
    state: RaceState,
    car: CarState,
    ranked: Sequence[Plan],
    pit: PitLossEstimate,
    *,
    hindsight: bool,
) -> None:
    label = "Starting" if hindsight else "Current"
    print(
        f"{label} tyre: {car.compound}, {car.tire_age} laps old; stops done: {car.stops_done}; "
        f"laps to plan: {state.laps_done_of(car) + 1}-{state.laps_total}"
    )
    if pit.is_default:
        print(f"Pit loss: {pit.median_s:.1f} s (default: no green-flag stop seen yet)")
    else:
        print(f"Pit loss: {pit.median_s:.1f} s (median over {pit.n_stops} green-flag stops)")
    for note in _PLAN_NOTES:
        print(note)
    time_label = "RACE TIME" if state.lap == 0 else "TIME TO FINISH"
    header = ("RANK", "TOTAL STOPS", "STOP LAPS", "TYRES", time_label, "GAP TO BEST")
    groups: tuple[tuple[str, list[Plan]], ...] = (
        ("Best 1-stop", [p for p in ranked if car.stops_done + p.n_stops == 1][:1]),
        ("Best 2-stop", [p for p in ranked if car.stops_done + p.n_stops == 2][:1]),
        ("Top 5 overall", list(ranked[:5])),
    )
    for title, plans in groups:
        print()
        print(title)
        if plans:
            _print_table(header, _plan_rows(plans, ranked, car))
        else:
            print("none legal")
    print()


def _compare_line(
    optimizer: FreeTrackOptimizer,
    state: RaceState,
    car: CarState,
    best: Plan,
    tyres: list[str],
    stops: list[int],
    fitted: Sequence[str],
) -> str:
    """One line pricing the driver's real strategy with the same model ('compared against')."""
    text = " > ".join(tyres) or "unknown"
    stop_text = ", ".join(str(k) for k in stops) or "none"
    if not tyres or tyres[0] != car.compound or len(stops) != len(tyres) - 1:
        reason = "its stints and stops do not line up with the starting tyre"
    elif any(t not in fitted for t in tyres):
        reason = "a compound has no fitted wear rate"
    else:
        try:
            actual = optimizer.price_plan(
                state, driver=car.driver, stop_laps=stops, compounds=tyres[1:]
            )
        except ValueError as err:
            reason = str(err)
        else:
            return (
                f"Compared against: {car.driver}'s actual strategy {text} with stops on laps "
                f"{stop_text}, priced by the same model: {_fmt_time(actual)} "
                f"({actual - best.total_time_s:+.1f} s versus the best plan above)"
            )
    return f"Compared against: the actual strategy could not be priced ({reason})."


_SIM_NOTE = (
    "Limitations: rivals follow the free-track best plan (D-10) and no retirements are "
    "simulated (D-09)."
)


def _sc_source(est: ScRateEstimate) -> str:
    if est.is_prior_only:
        return "prior only: no earlier races"
    return f"{est.n_deployments} earlier SC deployments over {est.n_laps} laps from earlier races"


def _cmd_simulate(
    data_dir: Path,
    reports_dir: Path,
    slug: str,
    driver: str,
    lap: int | None,
    n_races: int,
    seed: int,
) -> int:
    """Simulate n_races continuations and print one driver's finishing-position distribution."""
    try_line = f"Try: uv run f1si simulate {slug} --driver CODE --lap 20"
    driver = driver.upper()
    if not _DRIVER_CODE.fullmatch(driver):
        return _refuse(
            f"Driver codes are three capital letters, like VER; got {driver}. {try_line}"
        )
    if lap is not None and lap < 0:
        return _refuse(f"--lap must be 0 or more, got {lap}. {try_line}")
    if not 2 <= n_races <= MAX_RACES:
        return _refuse(f"--n must be between 2 and {MAX_RACES}, got {n_races}. {try_line}")
    try:
        rng = make_rng(seed)
        warm_rng = make_rng(seed)
    except ValueError as err:
        return _refuse(f"{err}. {try_line}")
    db = paths.db_path(data_dir)
    race_id = asof.resolve_slug(db, slug)
    accessor = asof.AsOfAccessor(db)
    try:
        end = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
        laps_total = int(end.laps["lap_number"].max())
        if lap is None:
            fit_snapshot = end
            state_snapshot = accessor.snapshot(asof.AsOf(race_id, 0))
            history = accessor.history(asof.AsOf(race_id, 0))
        elif lap >= laps_total:
            return _refuse(
                f"Nothing to simulate: the race is over after lap {laps_total}. "
                f"Try: uv run f1si simulate {slug} --driver {driver} --lap "
                f"{max(laps_total - 20, 20)}"
            )
        else:
            fit_snapshot = state_snapshot = accessor.snapshot(asof.AsOf(race_id, lap))
            history = accessor.history(asof.AsOf(race_id, lap))
    except OutOfSampleLockedError as err:
        return _refuse(
            f"{err} 2026 races are out-of-sample, so they cannot be analysed in Phase 3."
        )
    fit = fit_linear_pace(fit_snapshot)
    if not fit.is_identified:
        retry = 20 if lap is None or lap < 10 else lap + 10
        shown = "in this race" if lap is None else f"after lap {lap}"
        return _refuse(
            f"Cannot simulate: not enough laps yet to fit wear {shown} ({fit.report.message}); "
            f"try --lap {retry}. Example: uv run f1si simulate {slug} --driver {driver} "
            f"--lap {retry}"
        )
    pit = measure_pit_loss(fit_snapshot, fit)
    state = build_race_state(state_snapshot, fit, laps_total=laps_total, pit_loss_s=pit.median_s)
    try:
        code = _pick_driver(state_snapshot, end, driver)
    except UnknownDriverError as err:
        return _refuse(f"{err}. Try: uv run f1si simulate {slug} --driver CODE")
    estimate = estimate_sc_rate(history)
    simulator = NumpySimulator(
        fit,
        sc=SafetyCarModel(estimate.rate_per_lap, estimate.duration_laps),
        compounds=fit.fitted_compounds,
        wear_sd_by_compound={c.compound: c.se for c in fit.report.compounds},
    )
    simulator.simulate(state, n_races=64, rng=warm_rng)  # warm-up: compile time not reported
    started = time.perf_counter()
    result = simulator.simulate(state, n_races=n_races, rng=rng)
    runtime = time.perf_counter() - started

    race = end.race
    print(
        f"{race.event_name} {race.season}: {code}, simulated from lap {state.lap} of {laps_total}"
    )
    print(
        "This is a hindsight simulation: the pace fit uses the whole race. "
        "It makes no claim of foresight."
        if lap is None
        else f"Simulation after lap {lap}: only data known at that lap is used."
    )
    print(
        f"Safety car rate: {estimate.rate_per_lap * 100:.2f}% per lap "
        f"(source: {_sc_source(estimate)}), 90% interval "
        f"[{estimate.ci_low * 100:.2f}%, {estimate.ci_high * 100:.2f}%], typical safety car "
        f"length {estimate.duration_laps} laps"
    )
    sources = result.plan_sources
    n_opt = sum(1 for s in sources if s.source == "optimizer")
    n_fb = sum(1 for s in sources if s.source == "fallback")
    reasons = sorted({s.reason for s in sources if s.source == "fallback" and s.reason})
    print(
        f"Plans: {n_opt} from the free-track optimizer, {n_fb} fallback"
        + (f" ({'; '.join(reasons)})" if reasons else "")
    )
    for line in result.diagnostics:
        print(f"Note: {line}")
    print(_SIM_NOTE)
    column = [c.driver for c in state.cars].index(code)
    mine = result.finish_positions[:, column]
    n_cars = len(state.cars)
    shares = np.bincount(mine, minlength=n_cars + 1)[1 : n_cars + 1] / float(len(mine))
    print()
    print(f"Finishing position of {code} over {n_races} simulated races")
    _print_table(
        ("POSITION", "SHARE"),
        [(f"P{k}", f"{share * 100:.1f}%") for k, share in enumerate(shares, start=1)],
    )
    low, high = (float(q) for q in np.quantile(mine, [0.05, 0.95]))
    print(
        f"mean {float(mine.mean()):.2f}, median {float(np.median(mine)):.1f}, "
        f"90% interval {low:.0f} to {high:.0f}"
    )
    sc_share = 0.0 if result.sc_lap_mask is None else float(result.sc_lap_mask.any(axis=1).mean())
    print(f"Safety car in {sc_share * 100:.1f}% of simulated races")
    print(f"runtime: {runtime:.1f} s for {n_races} races")
    out = reports_dir / sim_file_name(race.slug, code, state.lap)
    render_sim_plot(
        prepare_sim_plot_data(
            mine,
            slug=race.slug,
            driver=code,
            lap=state.lap,
            n_races=n_races,
            sc_share=sc_share,
            sc_source=_sc_source(estimate),
            hindsight=lap is None,
            n_cars=n_cars,
        ),
        out,
    )
    print(f"Wrote {out}. Open it to see the finishing-position distribution.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the f1si command line and return the process exit code."""
    args = build_parser().parse_args(argv)
    data_dir: Path = args.data_dir if args.data_dir is not None else paths.data_dir()
    try:
        if args.command == "plot":
            reports_dir: Path = (
                args.reports_dir if args.reports_dir is not None else paths.reports_dir()
            )
            return _cmd_plot(data_dir, reports_dir, args.slug, args.drivers)
        if args.command == "wear":
            wear_reports: Path = (
                args.reports_dir if args.reports_dir is not None else paths.reports_dir()
            )
            return _cmd_wear(data_dir, wear_reports, args.slug, args.lap)
        if args.command == "plan":
            return _cmd_plan(data_dir, args.slug, args.driver, args.lap)
        if args.command == "simulate":
            sim_reports: Path = (
                args.reports_dir if args.reports_dir is not None else paths.reports_dir()
            )
            return _cmd_simulate(
                data_dir, sim_reports, args.slug, args.driver, args.lap, args.n, args.seed
            )
        if args.command == "load":
            return _cmd_load(data_dir, args.source, args.seed, args.seasons, args.only)
        return _cmd_races(data_dir)
    except KeyboardInterrupt:
        print("Stopped. Finished races are kept; run the same command to continue.")
        return 130
    except UnknownEraError as err:
        if args.debug:
            raise
        first = min(era.first_season for era in ERAS)
        last = max(era.last_season for era in ERAS)
        print(
            f"Season {err.season} has no regulation era defined "
            f"(supported seasons: {first}-{last}, see f1si/eras.py)",
            file=sys.stderr,
        )
        return 1
    except ValueError as err:
        if args.debug or args.command not in _FRIENDLY_VALUE_ERRORS:
            raise
        print(str(err), file=sys.stderr)
        return 1
    except (F1siDataError, SourceError) as err:
        if args.debug:
            raise
        print(str(err), file=sys.stderr)
        return 1
