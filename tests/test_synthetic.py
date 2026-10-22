"""The synthetic generator and its RaceSource."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from f1si.data import schema
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.rng import DEFAULT_SEED, make_rng
from f1si.synthetic import SyntheticRace, default_specs, generate_dataset


@pytest.fixture(scope="module")
def races() -> list[SyntheticRace]:
    return generate_dataset(default_specs(), rng=make_rng(DEFAULT_SEED))


def test_all_default_races_validate(races: list[SyntheticRace]) -> None:
    for r in races:
        assert schema.validate_race(r.race) == []


def test_lap_counts_and_truth(races: list[SyntheticRace]) -> None:
    for r in races:
        spec, laps = r.spec, r.race.tables["laps"]
        counts = laps.groupby("driver_number").size()
        for i in range(spec.n_drivers):
            expected = spec.n_laps
            if spec.retired_driver_index == i and spec.retire_after_lap is not None:
                expected = spec.retire_after_lap
            assert counts[10 + i] == expected
            assert r.truth.driver_pace_offset_s[10 + i] == pytest.approx(
                i * spec.driver_gap_s_per_lap
            )
        assert dict(r.truth.wear_rate_s_per_lap) == dict(spec.wear_rate_s_per_lap)
        assert r.truth.fuel_effect_s_per_lap == spec.fuel_effect_s_per_lap


def test_pit_flags_match_truth(races: list[SyntheticRace]) -> None:
    for r in races:
        laps = r.race.tables["laps"]
        entries = r.race.tables["entries"].set_index("driver_number")
        for number, stops in r.truth.pit_laps.items():
            d = laps[laps["driver_number"] == number]
            pit_in = d.loc[d["is_pit_in_lap"].astype(bool), "lap_number"].tolist()
            assert pit_in == list(stops)
            starter = bool(entries.loc[number, "pit_lane_start"])
            pit_out = d.loc[d["is_pit_out_lap"].astype(bool), "lap_number"].tolist()
            assert pit_out == ([1] if starter else []) + [s + 1 for s in stops]
    assert races[1].truth.pit_laps[15] == ()  # retired before its stop


def test_pit_lane_starter(races: list[SyntheticRace]) -> None:
    entries = races[1].race.tables["entries"].set_index("driver_number")
    assert pd.isna(entries.loc[14, "grid_position"])
    assert bool(entries.loc[14, "pit_lane_start"])
    laps = races[1].race.tables["laps"]
    first = laps[(laps["driver_number"] == 14) & (laps["lap_number"] == 1)].iloc[0]
    assert bool(first["is_pit_out_lap"])


def test_clock_properties(races: list[SyntheticRace]) -> None:
    for r in races:
        laps = r.race.tables["laps"]
        first = laps[laps["lap_number"] == 1]
        assert (first["lap_start_s"] == 0.0).all()
        for _, d in laps.groupby("driver_number"):
            assert d["lap_end_s"].astype(float).diff().dropna().gt(0).all()
        assert not laps.duplicated(subset=["lap_number", "lap_end_s"]).any()


def test_synthetic_source() -> None:
    src = SyntheticSource(rng=make_rng(DEFAULT_SEED))
    assert src.name == "synthetic"
    assert src.default_seasons == (2023, 2024, 2026)
    refs = src.list_races(2023, now=datetime(2026, 10, 22, tzinfo=UTC))
    assert [r.slug for r in refs] == ["alpha-2023", "bravo-2023"]
    assert src.fetch(refs[0]).ref == refs[0]
