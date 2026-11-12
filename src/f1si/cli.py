"""Command-line entry point for f1si.

Subcommands: `load` (fill the cache), `races` (list cached races with their regulation era),
`plot` (lap time by stint for one cached race) and `wear` (fitted tyre wear, fuel effect and pit
loss for one cached race). Exit codes: 0 ok, 1 user-facing error, 2 some
races failed.
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import f1si
from f1si import paths
from f1si.data import asof
from f1si.data.errors import F1siDataError, OutOfSampleLockedError
from f1si.data.loader import load_races
from f1si.data.sources import RaceSource, SourceError
from f1si.data.sources.openf1 import OpenF1Source
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.eras import ERAS, UnknownEraError
from f1si.pace.linear import (
    DEFAULT_PIT_LOSS_S,
    FUEL_SANITY_RANGE,
    MIN_CLEAN_LAPS_PER_COMPOUND,
    MIN_STINTS_PER_COMPOUND,
    fit_linear_pace,
    measure_pit_loss,
)
from f1si.plots.stints import plot_file_name, prepare_stint_plot_data, render_stint_plot
from f1si.rng import DEFAULT_SEED, make_rng

_FRIENDLY_VALUE_ERRORS = frozenset({"plot", "wear", "plan"})


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
    del reports_dir  # the wear plot (plan 02-03) is written there
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
