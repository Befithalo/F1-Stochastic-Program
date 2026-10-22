"""Shared session fixtures: a seeded synthetic dataset and a DuckDB cache holding it."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from f1si import paths
from f1si.data.loader import load_races
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.rng import DEFAULT_SEED, make_rng
from f1si.synthetic import SyntheticRace, default_specs, generate_dataset


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
