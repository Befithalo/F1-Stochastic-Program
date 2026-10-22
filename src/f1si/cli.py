"""Command-line entry point for f1si.

Subcommands: `load` (fill the cache), `races` (list cached races with their regulation era) and
`plot` (lap time by stint for one cached race). Exit codes: 0 ok, 1 user-facing error, 2 some
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
from f1si.plots.stints import plot_file_name, prepare_stint_plot_data, render_stint_plot
from f1si.rng import DEFAULT_SEED, make_rng


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
        if args.debug or args.command != "plot":
            raise
        print(str(err), file=sys.stderr)
        return 1
    except (F1siDataError, SourceError) as err:
        if args.debug:
            raise
        print(str(err), file=sys.stderr)
        return 1
