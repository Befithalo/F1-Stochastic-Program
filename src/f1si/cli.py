"""Command-line entry point for f1si.

Plan 01-03 adds the subcommands (load, races, plot).
"""

import argparse
from collections.abc import Sequence

import f1si


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="f1si",
        description="F1 Stochastic Intelligence Platform",
    )
    parser.add_argument("--version", action="version", version=f"f1si {f1si.__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the f1si command line and return the process exit code."""
    build_parser().parse_args(argv)
    return 0
