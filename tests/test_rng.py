"""Seed reproducibility (FND-03)."""

import numpy as np
import pandas as pd
import pytest

from f1si.rng import DEFAULT_SEED, make_rng
from f1si.synthetic import SyntheticRaceSpec, default_specs, generate_dataset


def test_make_rng_returns_generator() -> None:
    assert isinstance(make_rng(DEFAULT_SEED), np.random.Generator)


@pytest.mark.parametrize("bad", [True, -1])
def test_make_rng_rejects_bad_seed(bad: int) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        make_rng(bad)


def test_same_seed_is_byte_identical() -> None:
    first = generate_dataset(default_specs(), rng=make_rng(1))
    second = generate_dataset(default_specs(), rng=make_rng(1))
    for a, b in zip(first, second, strict=True):
        for name, table in a.race.tables.items():
            pd.testing.assert_frame_equal(table, b.race.tables[name], check_exact=True)


def test_different_seed_differs() -> None:
    a = generate_dataset(default_specs(), rng=make_rng(1))
    b = generate_dataset(default_specs(), rng=make_rng(2))
    assert not a[0].race.tables["laps"]["lap_time_s"].equals(b[0].race.tables["laps"]["lap_time_s"])


def test_changing_one_spec_leaves_other_races_unchanged() -> None:
    specs = default_specs()
    changed = (specs[0], SyntheticRaceSpec(2023, 2, "Bravo Grand Prix", n_laps=14), *specs[2:])
    base = generate_dataset(specs, rng=make_rng(7))
    other = generate_dataset(changed, rng=make_rng(7))
    pd.testing.assert_frame_equal(
        base[0].race.tables["laps"], other[0].race.tables["laps"], check_exact=True
    )
    pd.testing.assert_frame_equal(
        base[2].race.tables["laps"], other[2].race.tables["laps"], check_exact=True
    )
    assert len(base[1].race.tables["laps"]) != len(other[1].race.tables["laps"])
