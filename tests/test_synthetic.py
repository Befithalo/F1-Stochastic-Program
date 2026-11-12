"""The synthetic generator and its RaceSource."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import pytest

from f1si import paths
from f1si.data import schema
from f1si.data.loader import load_races
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.rng import DEFAULT_SEED, make_rng
from f1si.synthetic import SyntheticRace, SyntheticRaceSpec, default_specs, generate_dataset


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


# --- safety-car spec (Phase 3, D-06) -------------------------------------------------------------

# SHA-256 over every table of every race, computed BEFORE the safety-car edit of the generator.
DEFAULT_DATASET_DIGEST = "40e9cf6d9563f7b83e6d83f180145ed601a78c51066190bb7b400c71314258d4"
LONG_RACE_DIGEST = "d092644939068b0c84e687620d54de052efc6c3e932dd117d056ed2eff30e85d"


def _digest(generated: list[SyntheticRace]) -> str:
    h = hashlib.sha256()
    for r in generated:
        for name in sorted(r.race.tables):
            h.update(name.encode())
            h.update(
                np.asarray(pd.util.hash_pandas_object(r.race.tables[name], index=True)).tobytes()
            )
    return h.hexdigest()


def test_default_fixtures_are_byte_identical(races: list[SyntheticRace]) -> None:
    assert _digest(races) == DEFAULT_DATASET_DIGEST
    long = (
        SyntheticRaceSpec(2023, 1, "Long Grand Prix", n_drivers=20, n_laps=57, start_tyre_age=3),
    )
    assert _digest(generate_dataset(long, rng=make_rng(DEFAULT_SEED))) == LONG_RACE_DIGEST


def test_empty_sc_laps_equals_omitted_fields() -> None:
    base = SyntheticRaceSpec(2023, 1, "Alpha Grand Prix", vsc_laps=(8,))
    explicit = SyntheticRaceSpec(2023, 1, "Alpha Grand Prix", vsc_laps=(8,), sc_laps=())
    assert base == explicit
    assert _digest(generate_dataset([base], rng=make_rng(1))) == _digest(
        generate_dataset([explicit], rng=make_rng(1))
    )


def _sc_pair(**kwargs: Any) -> tuple[SyntheticRace, SyntheticRace]:
    plain = SyntheticRaceSpec(2023, 1, "Sc Grand Prix", n_laps=20, **kwargs)
    with_sc = SyntheticRaceSpec(
        2023, 1, "Sc Grand Prix", n_laps=20, sc_laps=(10,), sc_duration_laps=4, **kwargs
    )
    return (
        generate_dataset([plain], rng=make_rng(3))[0],
        generate_dataset([with_sc], rng=make_rng(3))[0],
    )


def test_sc_status_rows_and_lap_time_effect() -> None:
    plain, sc = _sc_pair()
    assert sc.truth.sc_laps == (10,)
    track = sc.race.tables["track_status"].sort_values("seq")
    assert track["status"].tolist() == ["1", "4", "1"]
    assert track["message"].tolist() == ["GREEN LIGHT", "SAFETY CAR DEPLOYED", "TRACK CLEAR"]
    a = plain.race.tables["laps"].set_index(["driver_number", "lap_number"])["lap_time_s"]
    b = sc.race.tables["laps"].set_index(["driver_number", "lap_number"])["lap_time_s"]
    for lap in range(1, 21):
        factor = 1.4 if 10 <= lap <= 13 else 1.0
        assert b.xs(lap, level="lap_number").to_numpy() == pytest.approx(
            a.xs(lap, level="lap_number").to_numpy() * factor
        )
    laps = sc.race.tables["laps"]
    deployed = track[track["status"] == "4"]["t_s"].iloc[0]
    assert deployed == pytest.approx(laps[laps["lap_number"] == 10]["lap_start_s"].min() + 1.0)
    clear = track["t_s"].iloc[-1]
    assert clear == pytest.approx(laps[laps["lap_number"] == 13]["lap_end_s"].max() + 1.0)


def test_sc_race_control_row() -> None:
    _, sc = _sc_pair()
    rc = sc.race.tables["race_control"]
    rows = rc[rc["message"] == "SAFETY CAR DEPLOYED"]
    assert len(rows) == 1
    assert rows["category"].iloc[0] == "SafetyCar"


def test_sc_duration_convention_through_the_database(tmp_path: Path) -> None:
    spec = SyntheticRaceSpec(
        2023, 1, "Sc Grand Prix", n_laps=20, sc_laps=(5, 12), sc_duration_laps=3
    )
    db = paths.db_path(tmp_path)
    load_races(
        SyntheticSource([spec], rng=make_rng(4)),
        db,
        (2023,),
        now=datetime(2026, 10, 22, tzinfo=UTC),
        echo=lambda _line: None,
    )
    with duckdb.connect(str(db), read_only=True) as con:
        track = con.execute("SELECT t_s, status FROM track_status ORDER BY t_s, seq").df()
        cutoffs = con.execute("SELECT cutoff_s FROM lap_cutoffs").df()["cutoff_s"].to_numpy()
    rows = track.to_dict("records")
    durations = []
    for k, row in enumerate(rows):
        if row["status"] == "4":
            end = rows[k + 1]["t_s"]
            durations.append(int((cutoffs <= end).sum() - (cutoffs <= row["t_s"]).sum()))
    assert durations == [3, 3]


def test_overlapping_sc_laps_raise() -> None:
    spec = SyntheticRaceSpec(2023, 1, "Sc Grand Prix", n_laps=20, sc_laps=(5, 7))
    with pytest.raises(ValueError, match="SC lap 7"):
        generate_dataset([spec], rng=make_rng(1))


def test_sc_window_past_the_last_lap_raises() -> None:
    spec = SyntheticRaceSpec(2023, 1, "Sc Grand Prix", n_laps=12, sc_laps=(10,), sc_duration_laps=4)
    with pytest.raises(ValueError, match="after the last lap"):
        spec.sc_windows()


def test_non_positive_sc_slowdown_raises() -> None:
    spec = SyntheticRaceSpec(2023, 1, "Sc Grand Prix", sc_laps=(3,), sc_slowdown_factor=0.0)
    with pytest.raises(ValueError, match="sc_slowdown_factor"):
        spec.sc_windows()
