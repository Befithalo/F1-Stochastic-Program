"""Command-line entry point for f1si.

Subcommands: `load` (fill the cache) and `races` (list cached races with their regulation era).
Plan 01-09 adds `plot`. Exit codes: 0 ok, 1 user-facing error, 2 some races failed.
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import f1si
from f1si import paths
from f1si.data import asof
from f1si.data.errors import F1siDataError
from f1si.data.loader import load_races
from f1si.data.sources import SourceError
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.eras import ERAS, UnknownEraError
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
    parser.add_argument("--debug", action="store_true", help="show full tracebacks on errors")
    sub = parser.add_subparsers(dest="command", required=True)

    load = sub.add_parser("load", help="load races into the local cache")
    load.add_argument(
        "--source", required=True, choices=["synthetic"], help="where races come from"
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
    return parser


def _cmd_load(
    data_dir: Path, seed: int, seasons: Sequence[int] | None, only: Sequence[str] | None
) -> int:
    source = SyntheticSource(rng=make_rng(seed))
    db = paths.db_path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    report = load_races(
        source,
        db,
        source.default_seasons if seasons is None else seasons,
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the f1si command line and return the process exit code."""
    args = build_parser().parse_args(argv)
    data_dir: Path = args.data_dir if args.data_dir is not None else paths.data_dir()
    try:
        if args.command == "load":
            return _cmd_load(data_dir, args.seed, args.seasons, args.only)
        return _cmd_races(data_dir)
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
    except (F1siDataError, SourceError) as err:
        if args.debug:
            raise
        print(str(err), file=sys.stderr)
        return 1
