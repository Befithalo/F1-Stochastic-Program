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


SC_HISTORY_CURRENT_RACE_ID = "2023-06"
SC_HISTORY_CURRENT_SLUG = "sc-six-2023"
# (deployment laps, SC duration in laps) of rounds 1-5; round 6 is the current race.
SC_HISTORY_EARLIER = (((8,), 4), ((), 4), ((12, 30), 3), ((20,), 4), ((), 3))


def sc_history_specs() -> tuple[SyntheticRaceSpec, ...]:
    """Six races of one season with known safety-car laps; round 6 is the current race."""
    names = ("One", "Two", "Three", "Four", "Five", "Six")
    specs = [
        SyntheticRaceSpec(
            2023,
            rnd,
            f"Sc {names[rnd - 1]}",
            n_drivers=10,
            n_laps=40,
            start_tyre_age=3,
            sc_laps=laps,
            sc_duration_laps=duration,
        )
        for rnd, (laps, duration) in enumerate(SC_HISTORY_EARLIER, start=1)
    ]
    specs.append(
        SyntheticRaceSpec(
            2023,
            6,
            "Sc Six",
            n_drivers=10,
            n_laps=40,
            start_tyre_age=3,
            sc_laps=(10,),
            sc_duration_laps=4,
        )
    )
    return tuple(specs)


def build_sc_history_db(folder: Path, seed: int) -> Path:
    """Load the six SC-history races drawn with `seed` into `folder`; return the DuckDB path."""
    folder.mkdir(parents=True, exist_ok=True)
    load_races(
        SyntheticSource(sc_history_specs(), rng=make_rng(seed)),
        paths.db_path(folder),
        (2023,),
        now=datetime(2026, 10, 22, tzinfo=UTC),
        echo=lambda _line: None,
    )
    return paths.db_path(folder)


@pytest.fixture(scope="session")
def sc_history_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A DuckDB file of six races with known safety-car laps (read-only use)."""
    folder = tmp_path_factory.mktemp("sc_history")
    build_sc_history_db(folder, DEFAULT_SEED)
    return paths.db_path(folder)
