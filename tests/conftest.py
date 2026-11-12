"""Shared session fixtures: a seeded synthetic dataset and a DuckDB cache holding it."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from f1si import paths
from f1si.data.loader import load_races
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.rng import DEFAULT_SEED, make_rng
from f1si.synthetic import (
    SyntheticRace,
    SyntheticRaceSpec,
    SyntheticTruth,
    default_specs,
    generate_dataset,
)

LONG_SLUG = "long-2023"
LONG_RACE_ID = "2023-01"


@pytest.fixture(scope="session")
def synthetic_races() -> list[SyntheticRace]:
    """The four default synthetic races, generated from the default seed."""
    return generate_dataset(default_specs(), rng=make_rng(DEFAULT_SEED))


@pytest.fixture(scope="session")
def synthetic_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A DuckDB file holding the four synthetic races (read-only use)."""
    folder = tmp_path_factory.mktemp("synthetic_db")
    db = paths.db_path(folder)
    load_races(
        SyntheticSource(rng=make_rng(DEFAULT_SEED)),
        db,
        (2023, 2024, 2026),
        now=datetime(2026, 10, 22, tzinfo=UTC),
        echo=lambda _line: None,
    )
    return db


def long_specs() -> tuple[SyntheticRaceSpec, ...]:
    """One 57-lap, 20-driver race (slug long-2023) for wear recovery and conformance."""
    return (
        SyntheticRaceSpec(2023, 1, "Long Grand Prix", n_drivers=20, n_laps=57, start_tyre_age=3),
    )


def build_long_db(folder: Path, seed: int) -> Path:
    """Load the long synthetic race drawn with `seed` into `folder`; return the DuckDB path."""
    folder.mkdir(parents=True, exist_ok=True)
    load_races(
        SyntheticSource(long_specs(), rng=make_rng(seed)),
        paths.db_path(folder),
        (2023,),
        now=datetime(2026, 10, 22, tzinfo=UTC),
        echo=lambda _line: None,
    )
    return paths.db_path(folder)


@pytest.fixture(scope="session")
def long_synthetic_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A data folder whose cache holds the long synthetic race."""
    folder = tmp_path_factory.mktemp("long_synthetic")
    build_long_db(folder, DEFAULT_SEED)
    return folder


@pytest.fixture(scope="session")
def long_synthetic_db(long_synthetic_data_dir: Path) -> Path:
    """The DuckDB file of the long synthetic race (read-only use)."""
    return paths.db_path(long_synthetic_data_dir)


@pytest.fixture(scope="session")
def long_synthetic_truth() -> SyntheticTruth:
    """The true parameters of the long race drawn with the default seed."""
    return generate_dataset(long_specs(), rng=make_rng(DEFAULT_SEED))[0].truth
