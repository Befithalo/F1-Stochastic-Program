"""Offline tests for OpenF1Source: invented payloads for a 20-driver, 3-lap race, no network."""

import copy
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from f1si.data import schema
from f1si.data.sources import RaceRef, SourceError
from f1si.data.sources.jolpica import JolpicaClient
from f1si.data.sources.openf1 import (
    NON_STARTER_STATUSES,
    OPENF1_BASE_URL,
    OpenF1Source,
)

NOW = datetime(2024, 1, 1, tzinfo=UTC)
LIGHTS_OUT = datetime(2023, 3, 5, 15, 3, 0, tzinfo=UTC)
SESSION_KEY = 100
N_DRIVERS = 20
N_LAPS = 3
LAP_S = 90.0

Rows = list[dict[str, object]]


def at(frame: pd.DataFrame, row: int, column: str) -> Any:
    """One cell of an indexed frame, typed loosely for assertions."""
    return frame.loc[row, column]


class OpenF1Fake:
    """Answers OpenF1 paths from a dict; records (path, params, freshness)."""

    def __init__(self, answers: Mapping[str, object]) -> None:
        self.answers = dict(answers)
        self.calls: list[tuple[str, Mapping[str, str | int] | None, str]] = []

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int] | None = None,
        *,
        freshness: str = "forever",
    ) -> object:
        self.calls.append((path, params, freshness))
        return self.answers.get(path)


class JolpicaFake:
    """Answers Jolpica by (path, offset)."""

    def __init__(self, pages: Mapping[tuple[str, int], object]) -> None:
        self.pages = dict(pages)

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int] | None = None,
        *,
        freshness: str = "forever",
    ) -> object:
        offset = int(params["offset"]) if params and "offset" in params else 0
        return self.pages.get((path, offset))


def iso(moment: datetime) -> str:
    return moment.isoformat()


def jolpica_table(races: object, total: str = "1") -> dict[str, object]:
    return {"MRData": {"total": total, "RaceTable": {"Races": races}}}


def schedule_race(rnd: int, name: str, day: str, time: str = "15:00:00Z") -> dict[str, object]:
    return {
        "season": "2023",
        "round": str(rnd),
        "raceName": name,
        "date": day,
        "time": time,
        "Circuit": {
            "circuitId": f"circuit_{rnd}",
            "Location": {"locality": f"Town {rnd}", "country": "Testland"},
        },
    }


def session(key: int, day: str, name: str = "Race", **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "session_key": key,
        "meeting_key": key - 50,
        "session_type": "Race",
        "session_name": name,
        "date_start": f"{day}T15:00:00+00:00",
    }
    row.update(extra)
    return row


def driver_id(number: int) -> str:
    return f"d{number:02d}"


def result_row(number: int) -> dict[str, object]:
    return {
        "number": str(number),
        "position": str(number),
        "positionText": str(number),
        "points": "0",
        "grid": str(number),
        "laps": str(N_LAPS),
        "status": "Finished",
        "Time": {"millis": str(5_400_000 + 1000 * number)},
        "Driver": {
            "driverId": driver_id(number),
            "code": f"D{number:02d}",
            "givenName": "Given",
            "familyName": f"Family{number}",
        },
        "Constructor": {"name": f"Team {number % 10}"},
    }


def lap_rows() -> Rows:
    rows: Rows = []
    for number in range(1, N_DRIVERS + 1):
        start = LIGHTS_OUT + timedelta(seconds=0.1 * number)
        for lap in range(1, N_LAPS + 1):
            duration = LAP_S + 0.1 * number
            rows.append(
                {
                    "driver_number": number,
                    "lap_number": lap,
                    "date_start": iso(start),
                    "lap_duration": duration,
                    "duration_sector_1": 30.0,
                    "duration_sector_2": 30.0,
                    "duration_sector_3": duration - 60.0,
                    "is_pit_out_lap": None if lap == 1 else False,
                }
            )
            start += timedelta(seconds=duration)
    return rows


class Payloads:
    """All invented upstream data for one race; tests edit it before building the source."""

    def __init__(self) -> None:
        self.sessions: Rows = [
            session(100, "2023-03-05"),
            session(99, "2023-03-04", "Sprint"),
            session(101, "2023-03-19", is_cancelled=True),
            session(102, "2099-01-01"),
            session(103, "2023-07-01"),
        ]
        self.schedule = [
            schedule_race(4, "Alpha Grand Prix", "2023-02-26"),
            schedule_race(5, "Testland Grand Prix", "2023-03-05"),
            schedule_race(6, "Beta Grand Prix", "2023-03-19"),
        ]
        self.drivers: Rows = [
            {
                "driver_number": n,
                "name_acronym": f"X{n:02d}",
                "full_name": f"Given FAMILY{n}",
                "team_name": "Team",
            }
            for n in range(1, N_DRIVERS + 1)
        ]
        self.laps = lap_rows()
        self.stints: Rows = [
            {
                "driver_number": n,
                "stint_number": 1,
                "compound": "SOFT" if n != 1 else "soft",
                "lap_start": 1,
                "lap_end": None,
                "tyre_age_at_start": 2 if n == 1 else 0,
            }
            for n in range(1, N_DRIVERS + 1)
        ]
        self.control: Rows = [
            {
                "date": iso(LIGHTS_OUT - timedelta(seconds=60)),
                "category": "Flag",
                "flag": "GREEN",
                "scope": "Track",
                "message": "GREEN LIGHT - PIT EXIT OPEN",
            },
            {
                "date": iso(LIGHTS_OUT + timedelta(seconds=100)),
                "category": "SafetyCar",
                "flag": None,
                "scope": None,
                "message": "VIRTUAL SAFETY CAR DEPLOYED",
            },
            {
                "date": iso(LIGHTS_OUT + timedelta(seconds=140)),
                "category": "SafetyCar",
                "flag": None,
                "scope": None,
                "message": "VIRTUAL SAFETY CAR ENDING",
            },
        ]
        self.weather: Rows = [
            {
                "date": iso(LIGHTS_OUT + timedelta(seconds=60 * i)),
                "air_temperature": 25.0,
                "track_temperature": 31.5,
                "humidity": 40.0,
                "pressure": 1011.0,
                "rainfall": 0,
                "wind_speed": 2.5,
                "wind_direction": 180,
            }
            for i in range(4)
        ]
        self.results = [result_row(n) for n in range(1, N_DRIVERS + 1)]
        self.pit_stops: Rows = [
            {
                "driverId": driver_id(2),
                "lap": "2",
                "stop": "1",
                "time": "15:05:00",
                "duration": "23.456",
            }
        ]

    def openf1(self) -> OpenF1Fake:
        return OpenF1Fake(
            {
                "/sessions": copy.deepcopy(self.sessions),
                "/drivers": copy.deepcopy(self.drivers),
                "/laps": copy.deepcopy(self.laps),
                "/stints": copy.deepcopy(self.stints),
                "/race_control": copy.deepcopy(self.control),
                "/weather": copy.deepcopy(self.weather),
            }
        )

    def jolpica(self) -> JolpicaFake:
        return JolpicaFake(
            {
                ("/2023.json", 0): jolpica_table(copy.deepcopy(self.schedule), "3"),
                ("/2023/5/results.json", 0): jolpica_table(
                    [{"Results": copy.deepcopy(self.results)}]
                ),
                ("/2023/5/pitstops.json", 0): jolpica_table(
                    [{"PitStops": copy.deepcopy(self.pit_stops)}], str(len(self.pit_stops))
                ),
            }
        )

    def source(self, echo: Callable[[str], None] | None = None) -> tuple[OpenF1Source, OpenF1Fake]:
        fake = self.openf1()
        source = OpenF1Source(
            http_cache_dir=Path("unused"),
            echo=echo or (lambda _msg: None),
            openf1=fake,
            jolpica=JolpicaClient(self.jolpica()),
        )
        return source, fake


def fetch_race(payloads: Payloads) -> tuple[dict[str, pd.DataFrame], RaceRef, OpenF1Fake]:
    source, fake = payloads.source()
    (ref,) = source.list_races(2023, now=NOW)
    fake.calls.clear()
    race = source.fetch(ref)
    assert schema.validate_race(race) == []
    return dict(race.tables), ref, fake


# ---------------------------------------------------------------- list_races


def test_list_races_returns_one_matched_grand_prix_and_echoes_the_unmatched() -> None:
    messages: list[str] = []
    source, fake = Payloads().source(echo=messages.append)
    refs = source.list_races(2023, now=NOW)
    assert len(refs) == 1
    ref = refs[0]
    assert ref.race_id == "2023-05"
    assert ref.slug == "testland-2023"
    assert (ref.season, ref.round) == (2023, 5)
    assert ref.circuit == "circuit_5"
    assert ref.event_name == "Testland Grand Prix"
    assert ref.scheduled_laps is None
    assert ref.race_start_utc == datetime(2023, 3, 5, 15, 0, tzinfo=UTC)
    assert dict(ref.source_keys) == {"session_key": "100", "meeting_key": "50"}
    assert any("session 103" in m and "no Jolpica round" in m for m in messages)
    assert fake.calls[0][0] == "/sessions"
    assert fake.calls[0][1] == {"year": 2023, "session_name": "Race"}
    assert fake.calls[0][2] == "short"


def test_list_races_before_2023_names_the_first_season() -> None:
    source, _ = Payloads().source()
    with pytest.raises(SourceError, match="2023"):
        source.list_races(2022, now=NOW)


def test_list_races_treats_no_results_as_empty() -> None:
    payloads = Payloads()
    source, fake = payloads.source()
    fake.answers["/sessions"] = {"detail": "No results found."}
    assert source.list_races(2023, now=NOW) == []


def test_list_races_skips_a_race_that_started_less_than_six_hours_ago() -> None:
    source, _ = Payloads().source()
    just_after = datetime(2023, 3, 5, 18, 0, tzinfo=UTC)
    assert source.list_races(2023, now=just_after) == []
    assert len(source.list_races(2023, now=datetime(2023, 3, 5, 21, 0, 1, tzinfo=UTC))) == 1


def test_list_races_adds_round_suffix_when_slugs_clash() -> None:
    payloads = Payloads()
    payloads.sessions = [session(100, "2023-03-05"), session(104, "2023-03-19")]
    payloads.schedule = [
        schedule_race(5, "Testland Grand Prix", "2023-03-05"),
        schedule_race(6, "Testland Grand Prix", "2023-03-19"),
    ]
    source, _ = payloads.source()
    assert [r.slug for r in source.list_races(2023, now=NOW)] == [
        "testland-2023-r5",
        "testland-2023-r6",
    ]


def test_source_identity_and_defaults() -> None:
    source, _ = Payloads().source()
    assert source.name == "openf1+jolpica"
    assert source.default_seasons == (2023, 2024, 2025, 2026)
    assert source.version.startswith("openf1-api+jolpica-ergast;f1si-")
    assert OPENF1_BASE_URL == "https://api.openf1.org/v1"


# ---------------------------------------------------------------- fetch


def test_fetch_makes_exactly_five_openf1_calls() -> None:
    _, _, fake = fetch_race(Payloads())
    assert [c[0] for c in fake.calls] == [
        "/drivers",
        "/laps",
        "/stints",
        "/race_control",
        "/weather",
    ]
    assert all(c[1] == {"session_key": SESSION_KEY} for c in fake.calls)


def test_fetch_returns_all_tables_with_a_valid_shape() -> None:
    tables, _, _ = fetch_race(Payloads())
    assert set(tables) == {"entries", "laps", "track_status", "race_control", "weather", "results"}
    assert len(tables["entries"]) == N_DRIVERS
    assert len(tables["laps"]) == N_DRIVERS * N_LAPS
    assert len(tables["weather"]) == 4


def test_race_clock_starts_at_the_earliest_lap_one() -> None:
    tables, _, _ = fetch_race(Payloads())
    laps = tables["laps"]
    first = laps[(laps["driver_number"] == 1) & (laps["lap_number"] == 1)].iloc[0]
    assert first["lap_start_s"] == 0.0
    second = laps[(laps["driver_number"] == 1) & (laps["lap_number"] == 2)].iloc[0]
    assert second["lap_start_s"] == pytest.approx(first["lap_end_s"])
    other = laps[(laps["driver_number"] == 11) & (laps["lap_number"] == 1)].iloc[0]
    assert other["lap_start_s"] == pytest.approx(1.0)  # 0.1 s per car number after car 1
    assert first["s1_s"] == 30.0
    # messages before lights out are on the same clock
    assert tables["race_control"]["t_s"].iloc[0] == pytest.approx(-60.0 - 0.1)


def test_lap_one_without_date_start_is_zero_and_missing_duration_uses_next_start() -> None:
    payloads = Payloads()
    for row in payloads.laps:
        if row["driver_number"] == 5 and row["lap_number"] == 1:
            row["date_start"] = None
        if row["driver_number"] == 6 and row["lap_number"] == 2:
            row["lap_duration"] = None
    tables, _, _ = fetch_race(payloads)
    laps = tables["laps"]
    five = laps[(laps["driver_number"] == 5) & (laps["lap_number"] == 1)].iloc[0]
    assert five["lap_start_s"] == 0.0
    six = laps[laps["driver_number"] == 6].set_index("lap_number")
    assert at(six, 2, "lap_end_s") == pytest.approx(at(six, 3, "lap_start_s"))
    assert at(six, 2, "lap_time_s") == pytest.approx(
        at(six, 3, "lap_start_s") - at(six, 2, "lap_start_s")
    )


def test_stints_give_tyre_life_and_upper_case_compound() -> None:
    tables, _, _ = fetch_race(Payloads())
    laps = tables["laps"]
    one = laps[laps["driver_number"] == 1].set_index("lap_number")
    assert at(one, 1, "tyre_life") == 3  # age 2 at start, first lap of the stint
    assert at(one, 3, "tyre_life") == 5  # null lap_end extends to the last lap
    assert set(one["compound"]) == {"SOFT"}
    assert set(one["stint"]) == {1}


def test_unknown_compound_becomes_null() -> None:
    payloads = Payloads()
    payloads.stints[3]["compound"] = "UNKNOWN"
    tables, _, _ = fetch_race(payloads)
    laps = tables["laps"]
    assert laps.loc[laps["driver_number"] == 4, "compound"].isna().all()
    entries = tables["entries"].set_index("driver_number")
    assert pd.isna(at(entries, 4, "start_compound"))
    assert at(entries, 1, "start_compound") == "SOFT"
    assert at(entries, 1, "start_tyre_age") == 2


def test_pit_stop_marks_in_lap_and_puts_duration_on_the_out_lap() -> None:
    payloads = Payloads()
    for row in payloads.laps:
        if row["driver_number"] == 2 and row["lap_number"] == 3:
            row["is_pit_out_lap"] = True
    tables, _, _ = fetch_race(payloads)
    laps = tables["laps"]
    two = laps[laps["driver_number"] == 2].set_index("lap_number")
    assert bool(at(two, 2, "is_pit_in_lap"))
    assert not bool(at(two, 1, "is_pit_in_lap"))
    assert at(two, 3, "pit_duration_s") == pytest.approx(23.456)
    assert pd.isna(at(two, 2, "pit_duration_s"))
    assert bool(at(two, 3, "is_pit_out_lap"))
    assert not bool(at(two, 1, "is_pit_out_lap"))  # null becomes False


def set_result(payloads: Payloads, number: int, **fields: str) -> None:
    row = payloads.results[number - 1]
    for key, value in fields.items():
        row[key] = value


def test_pit_lane_start_rule() -> None:
    payloads = Payloads()
    set_result(payloads, 7, grid="0", status="Retired", laps="0", positionText="R")
    set_result(payloads, 8, grid="0", status="Did not start", laps="0", positionText="W")
    set_result(payloads, 9, grid="3")
    tables, _, _ = fetch_race(payloads)
    entries = tables["entries"].set_index("driver_number")
    assert pd.isna(at(entries, 7, "grid_position"))
    assert bool(at(entries, 7, "pit_lane_start"))
    assert pd.isna(at(entries, 8, "grid_position"))
    assert not bool(at(entries, 8, "pit_lane_start"))
    assert at(entries, 9, "grid_position") == 3
    assert not bool(at(entries, 9, "pit_lane_start"))
    assert not entries["pit_lane_start"].drop([7]).any()
    assert at(entries, 1, "driver_code") == "D01"
    assert at(entries, 1, "full_name") == "Given FAMILY1"
    assert at(entries, 1, "driver_id") == "d01"


def test_pit_lane_start_ignores_laps_completed() -> None:
    results = []
    for laps in ("0", "57"):
        payloads = Payloads()
        set_result(payloads, 7, grid="0", status="Retired", laps=laps)
        tables, _, _ = fetch_race(payloads)
        results.append(tables["entries"].set_index("driver_number").loc[7, "pit_lane_start"])
    assert results[0] == results[1]
    assert bool(results[0])


def test_non_starter_statuses_are_compared_case_insensitively() -> None:
    assert "did not start" in NON_STARTER_STATUSES
    payloads = Payloads()
    set_result(payloads, 7, grid="0", status="  WITHDREW ")
    tables, _, _ = fetch_race(payloads)
    assert not bool(tables["entries"].set_index("driver_number").loc[7, "pit_lane_start"])


def test_results_table() -> None:
    payloads = Payloads()
    set_result(payloads, 3, positionText="R", status="Engine")
    tables, _, _ = fetch_race(payloads)
    results = tables["results"].set_index("driver_number")
    assert at(results, 1, "final_position") == 1
    assert pd.isna(at(results, 3, "final_position"))
    assert at(results, 3, "classified_position") == "R"
    assert at(results, 1, "laps_completed") == N_LAPS
    assert at(results, 1, "total_time_s") == pytest.approx(5401.0)


def test_virtual_safety_car_message_becomes_status_six() -> None:
    tables, _, _ = fetch_race(Payloads())
    track = tables["track_status"]
    assert "6" in set(track["status"])
    row = track[track["status"] == "6"].iloc[0]
    assert row["t_s"] == pytest.approx(100.0 - 0.1)  # relative to car 1's lap 1 start


def test_weather_columns() -> None:
    tables, _, _ = fetch_race(Payloads())
    weather = tables["weather"]
    assert weather["air_temp_c"].iloc[0] == 25.0
    assert weather["rainfall"].tolist() == [False] * 4
    assert weather["wind_direction_deg"].iloc[0] == 180.0


# ---------------------------------------------------------------- failures


def test_missing_weather_fails_the_race_with_a_clear_reason() -> None:
    payloads = Payloads()
    payloads.weather = []
    source, _ = payloads.source()
    (ref,) = source.list_races(2023, now=NOW)
    with pytest.raises(SourceError, match="weather"):
        source.fetch(ref)


def test_no_results_detail_for_weather_is_treated_as_missing() -> None:
    source, fake = Payloads().source()
    (ref,) = source.list_races(2023, now=NOW)
    fake.answers["/weather"] = {"detail": "No results found."}
    with pytest.raises(SourceError, match="weather"):
        source.fetch(ref)


def test_too_few_entrants_fails_the_race() -> None:
    payloads = Payloads()
    payloads.results = payloads.results[:17]
    payloads.laps = [row for row in payloads.laps if int(str(row["driver_number"])) <= 17]
    source, _ = payloads.source()
    (ref,) = source.list_races(2023, now=NOW)
    with pytest.raises(SourceError, match="entries"):
        source.fetch(ref)


def test_garbage_timestamp_is_an_unexpected_response() -> None:
    payloads = Payloads()
    payloads.laps[0]["date_start"] = "garbage"
    source, _ = payloads.source()
    (ref,) = source.list_races(2023, now=NOW)
    with pytest.raises(SourceError, match="Unexpected"):
        source.fetch(ref)


def test_garbage_number_is_an_unexpected_response() -> None:
    payloads = Payloads()
    payloads.laps[0]["lap_duration"] = "fast"
    source, _ = payloads.source()
    (ref,) = source.list_races(2023, now=NOW)
    with pytest.raises(SourceError, match="Unexpected"):
        source.fetch(ref)


def test_lap_for_a_driver_missing_from_the_results_fails_the_race() -> None:
    payloads = Payloads()
    extra = dict(payloads.laps[0])
    extra["driver_number"] = 77
    payloads.laps.append(extra)
    source, _ = payloads.source()
    (ref,) = source.list_races(2023, now=NOW)
    with pytest.raises(SourceError, match="not in entries"):
        source.fetch(ref)


def test_row_without_required_key_is_an_unexpected_response() -> None:
    payloads = Payloads()
    del payloads.laps[0]["lap_number"]
    source, _ = payloads.source()
    (ref,) = source.list_races(2023, now=NOW)
    with pytest.raises(SourceError, match="Unexpected"):
        source.fetch(ref)
