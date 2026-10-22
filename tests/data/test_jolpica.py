"""Offline tests for the Jolpica client (invented payloads, no network)."""

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from f1si.data.sources import SourceError
from f1si.data.sources._http import RateLimitedClient
from f1si.data.sources.jolpica import (
    JOLPICA_BASE_URL,
    JolpicaClient,
    parse_duration_s,
)


class FakeGetter:
    """Answers by (path, offset); records every call."""

    def __init__(self, pages: Mapping[tuple[str, int], object]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, Mapping[str, str | int] | None, str]] = []

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int] | None = None,
        *,
        freshness: str = "forever",
    ) -> object:
        self.calls.append((path, params, freshness))
        offset = int(params["offset"]) if params and "offset" in params else 0
        return self.pages.get((path, offset))


def table(races: object, total: str = "1") -> dict[str, object]:
    return {"MRData": {"total": total, "RaceTable": {"Races": races}}}


def schedule_race(
    rnd: int, name: str, date: str, time: str | None = "15:00:00Z"
) -> dict[str, object]:
    race: dict[str, object] = {
        "season": "2023",
        "round": str(rnd),
        "raceName": name,
        "date": date,
        "Circuit": {
            "circuitId": f"circuit_{rnd}",
            "Location": {"locality": f"Town {rnd}", "country": "Nowhere"},
        },
    }
    if time is not None:
        race["time"] = time
    return race


def result_row(
    number: str,
    driver_id: str,
    position: str,
    position_text: str,
    *,
    grid: str = "1",
    millis: str | None = "5400000",
) -> dict[str, object]:
    row: dict[str, object] = {
        "number": number,
        "position": position,
        "positionText": position_text,
        "points": "25",
        "grid": grid,
        "laps": "57",
        "status": "Finished" if position_text.isdigit() else "Engine",
        "Driver": {
            "driverId": driver_id,
            "code": driver_id[:3].upper(),
            "givenName": "Given",
            "familyName": driver_id.title(),
        },
        "Constructor": {"name": "Team A"},
    }
    if millis is not None:
        row["Time"] = {"millis": millis}
    return row


def test_season_schedule_parses_races_and_uses_short_freshness() -> None:
    payload = table(
        [
            schedule_race(1, "Alpha GP", "2023-03-05"),
            schedule_race(2, "Beta GP", "2023-03-19", time=None),
            schedule_race(3, "Gamma GP", "2023-04-02", "05:00:00Z"),
        ],
        "3",
    )
    getter = FakeGetter({("/2023.json", 0): payload})
    races = JolpicaClient(getter).season_schedule(2023)
    assert [r.round for r in races] == [1, 2, 3]
    first = races[0]
    assert (first.season, first.race_name, first.circuit_id) == (2023, "Alpha GP", "circuit_1")
    assert (first.locality, first.country) == ("Town 1", "Nowhere")
    assert first.start_utc == datetime(2023, 3, 5, 15, 0, tzinfo=UTC)
    assert races[1].start_utc == datetime(2023, 3, 19, 0, 0, tzinfo=UTC)
    assert races[2].start_utc.tzinfo is UTC
    assert getter.calls == [("/2023.json", {"limit": 100}, "short")]


def test_results_columns_and_types() -> None:
    rows = [
        result_row("1", "alpha", "1", "1", grid="2"),
        result_row("44", "bravo", "2", "2", grid="0", millis=None),
        result_row("16", "charlie", "20", "R", grid="3", millis=None),
    ]
    payload = table([{"Results": rows}])
    getter = FakeGetter({("/2023/1/results.json", 0): payload})
    df = JolpicaClient(getter).results(2023, 1)
    assert list(df.columns) == [
        "driver_number", "driver_id", "driver_code", "given_name", "family_name", "team_name",
        "grid", "position", "position_text", "status", "points", "laps", "total_time_s",
    ]  # fmt: skip
    assert df["driver_number"].tolist() == [1, 44, 16]
    assert str(df["driver_number"].dtype) == "Int64"
    assert df["grid"].tolist() == [2, 0, 3]  # grid "0" stays 0
    assert df["position"].iloc[0] == 1
    assert pd.isna(df["position"].iloc[2])  # "R"
    assert df["position_text"].tolist() == ["1", "2", "R"]
    assert df["points"].dtype == "float64"
    assert df["laps"].iloc[0] == 57
    assert df["total_time_s"].iloc[0] == pytest.approx(5400.0)
    assert df["total_time_s"].isna().tolist() == [False, True, True]
    assert df["team_name"].unique().tolist() == ["Team A"]
    assert getter.calls[0][1] == {"limit": 100}
    assert getter.calls[0][2] == "forever"


def test_results_empty_races_says_no_results() -> None:
    getter = FakeGetter({("/2026/9/results.json", 0): table([])})
    with pytest.raises(SourceError, match="no results"):
        JolpicaClient(getter).results(2026, 9)


def test_pit_stops_paginate_and_parse_durations() -> None:
    def page(start: int, count: int) -> dict[str, object]:
        stops = [
            {
                "driverId": "alpha",
                "lap": str(start + i + 1),
                "stop": "1",
                "time": "14:00:00",
                "duration": "23.456" if i % 2 == 0 else "1:02.345",
            }
            for i in range(count)
        ]
        return table([{"PitStops": stops}], "130")

    getter = FakeGetter(
        {("/2023/1/pitstops.json", 0): page(0, 100), ("/2023/1/pitstops.json", 100): page(100, 30)}
    )
    df = JolpicaClient(getter).pit_stops(2023, 1)
    assert len(df) == 130
    assert list(df.columns) == ["driver_id", "lap", "stop", "duration_s"]
    assert df["duration_s"].iloc[0] == pytest.approx(23.456)
    assert df["duration_s"].iloc[1] == pytest.approx(62.345)
    assert [c[1] for c in getter.calls] == [
        {"limit": 100, "offset": 0},
        {"limit": 100, "offset": 100},
    ]
    assert df["lap"].iloc[129] == 130


def test_pit_stops_with_no_data_is_an_empty_frame() -> None:
    getter = FakeGetter({("/2023/1/pitstops.json", 0): table([], "0")})
    df = JolpicaClient(getter).pit_stops(2023, 1)
    assert df.empty
    assert list(df.columns) == ["driver_id", "lap", "stop", "duration_s"]


def test_pit_stops_stop_when_a_page_is_empty() -> None:
    page = table([{"PitStops": []}], "500")
    getter = FakeGetter({("/2023/1/pitstops.json", 0): page})
    assert JolpicaClient(getter).pit_stops(2023, 1).empty
    assert len(getter.calls) == 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("23.456", 23.456),
        ("1:02.345", 62.345),
        ("22:34.567", 1354.567),
        ("1:02:03.5", 3723.5),
        ("", None),
        ("abc", None),
        ("1:ab", None),
        ("1:2:3:4", None),
        ("-5", None),
    ],
)
def test_parse_duration_s(text: str, expected: float | None) -> None:
    result = parse_duration_s(text)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"MRData": {}},
        {"MRData": {"RaceTable": {}}},
        {"MRData": {"RaceTable": {"Races": "nope"}}},
        [1, 2],
    ],
)
def test_bad_payload_shapes_raise_source_error_naming_the_path(payload: object) -> None:
    getter = FakeGetter({("/2023.json", 0): payload, ("/2023/1/results.json", 0): payload})
    client = JolpicaClient(getter)
    with pytest.raises(SourceError, match=r"/2023.json"):
        client.season_schedule(2023)
    with pytest.raises(SourceError, match=r"/2023/1/results.json"):
        client.results(2023, 1)


def test_missing_fields_raise_source_error() -> None:
    bad = result_row("1", "alpha", "1", "1")
    del bad["Driver"]
    getter = FakeGetter({("/2023/1/results.json", 0): table([{"Results": [bad]}])})
    with pytest.raises(SourceError, match=r"Unexpected response from Jolpica.*Driver"):
        JolpicaClient(getter).results(2023, 1)


def test_non_numeric_strings_raise_source_error() -> None:
    bad = result_row("x1", "alpha", "1", "1")
    getter = FakeGetter({("/2023/1/results.json", 0): table([{"Results": [bad]}])})
    with pytest.raises(SourceError, match="number"):
        JolpicaClient(getter).results(2023, 1)


def test_create_uses_production_pacing(tmp_path: Path) -> None:
    client = JolpicaClient.create(cache_dir=tmp_path, echo=lambda _m: None, sleep=lambda _s: None)
    inner = client._getter
    try:
        assert isinstance(inner, RateLimitedClient)
        assert inner._min_interval_s == 0.5
        assert inner._max_per_hour == 450
        assert inner._base_url == JOLPICA_BASE_URL
    finally:
        if isinstance(inner, RateLimitedClient):
            inner.close()
