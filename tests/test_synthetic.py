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


def _race(races: list[SyntheticRace], slug: str) -> SyntheticRace:
    return next(r for r in races if r.race.ref.slug == slug)


def test_vsc_track_status_sequence_around_lap_8(races: list[SyntheticRace]) -> None:
    track = _race(races, "alpha-2023").race.tables["track_status"].sort_values("t_s")
    codes = track["status"].tolist()
    assert codes == ["1", "6", "7", "1"]
    laps = _race(races, "alpha-2023").race.tables["laps"]
    lap8 = laps[laps["lap_number"] == 8]
    deployed = track[track["status"] == "6"]["t_s"].iloc[0]
    assert deployed == pytest.approx(lap8["lap_start_s"].min() + 1.0)
    ending = track[track["status"] == "7"]["t_s"].iloc[0]
    assert ending == pytest.approx(lap8["lap_end_s"].max() - 1.0)
    clear = track[track["status"] == "1"]["t_s"].iloc[-1]
    assert clear == pytest.approx(ending + 12.0)


def test_race_without_vsc_stays_green(races: list[SyntheticRace]) -> None:
    track = _race(races, "charlie-2024").race.tables["track_status"]
    assert track["status"].tolist() == ["1"]


def test_weather_covers_before_and_after_lights_out(races: list[SyntheticRace]) -> None:
    for r in races:
        weather = r.race.tables["weather"]
        assert (weather["t_s"] <= 0).any()
        assert (weather["t_s"] > 0).any()
        assert not weather["rainfall"].astype(bool).any()
        last_end = r.race.tables["laps"]["lap_end_s"].max()
        assert weather["t_s"].max() >= last_end


def test_race_control_has_pre_race_green_and_chequered(races: list[SyntheticRace]) -> None:
    for r in races:
        rc = r.race.tables["race_control"]
        pre = rc[(rc["flag"] == "GREEN") & (rc["t_s"] < 0)]
        assert len(pre) == 1
        chequered = rc[rc["flag"] == "CHEQUERED"]
        assert len(chequered) == 1
        laps = r.race.tables["laps"]
        finishers = laps[laps["lap_number"] == r.spec.n_laps]
        assert chequered["t_s"].iloc[0] == pytest.approx(finishers["lap_end_s"].min())


def test_results_order_points_and_retirement(races: list[SyntheticRace]) -> None:
    alpha = _race(races, "alpha-2023").race.tables["results"].sort_values("final_position")
    assert alpha["points"].tolist() == [25.0, 18.0, 15.0, 12.0, 10.0, 8.0]
    assert alpha["classified_position"].tolist() == ["1", "2", "3", "4", "5", "6"]
    laps = _race(races, "alpha-2023").race.tables["laps"]
    final = laps[laps["lap_number"] == 12].set_index("driver_number")["lap_end_s"]
    ordered = final.sort_values().index.tolist()
    assert alpha["driver_number"].tolist() == ordered

    bravo = _race(races, "bravo-2023").race.tables["results"].set_index("driver_number")
    retired = bravo.loc[15]
    assert pd.isna(retired["final_position"])
    assert retired["classified_position"] == "R"
    assert retired["status"] == "Retired"
    assert retired["laps_completed"] == 4
    assert pd.isna(retired["total_time_s"])
    assert bravo["final_position"].dropna().astype(int).tolist() == [1, 2, 3, 4, 5]
    assert bravo["points"].sum() == pytest.approx(25 + 18 + 15 + 12 + 10)


def test_first_lap_follows_the_documented_model(races: list[SyntheticRace]) -> None:
    """Lap 1 of the first driver is base + start cost + one lap of wear, within 6 noise sd."""
    laps = _race(races, "alpha-2023").race.tables["laps"]
    first = laps[(laps["driver_number"] == 10) & (laps["lap_number"] == 1)].iloc[0]
    assert first["lap_time_s"] == pytest.approx(90.0 + 3.0 - 0.03 * 0 + 0.07 * 1, abs=1.0)
