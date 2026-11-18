"""Contracts for complete-catalog telemetry coverage and the single bounded probe."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_local_audit_counts_every_complete_race_and_channel(synthetic_db: Path) -> None:
    import duckdb

    from f1si.data.coverage_audit import build_coverage_report

    report = build_coverage_report(synthetic_db, probe=False)

    catalog = report["local_cache"]
    races = catalog["races"]
    assert catalog["catalog_complete_races"] == len(races)
    assert set(catalog["channels"]) == {"weather", "car_data", "location"}
    assert {row["race_id"] for row in races} == {
        race_id for race_id in report["complete_catalog_race_ids"]
    }
    for row in races:
        assert set(row["channels"]) == {"weather", "car_data", "location"}
        assert all(channel["row_count"] >= 0 for channel in row["channels"].values())

    complete_ids = {str(race_id) for race_id in report["complete_catalog_race_ids"]}
    with duckdb.connect(str(synthetic_db), read_only=True) as connection:
        for channel_name, summary in catalog["channels"].items():
            stored_rows = connection.execute(
                f"SELECT race_id, COUNT(*) FROM {channel_name} GROUP BY race_id"
            ).fetchall()
            expected_counts = {
                str(race_id): int(row_count)
                for race_id, row_count in stored_rows
                if str(race_id) in complete_ids
            }
            assert summary["row_count"] == sum(expected_counts.values())
            for race in races:
                row = race["channels"][channel_name]
                expected_count = expected_counts.get(race["race_id"], 0)
                assert row["row_count"] == expected_count
                assert row["present"] is (expected_count > 0)


def test_bahrain_probe_is_bounded_to_three_optional_endpoints() -> None:
    from f1si.data.coverage_audit import probe_bahrain_2023

    calls: list[tuple[str, dict[str, object]]] = []

    def rows(path: str, params: dict[str, object], **_kwargs: object) -> list[dict[str, object]]:
        calls.append((path, params))
        if path == "/sessions":
            return [
                {
                    "session_key": 1234,
                    "session_name": "Race",
                    "year": 2023,
                    "country_name": "Bahrain",
                }
            ]
        if path == "/laps":
            return [{"lap_number": 1, "date_start": "2023-03-05T15:00:00Z"}]
        return []

    result = probe_bahrain_2023(rows=rows)

    channel_calls = [
        (path, params) for path, params in calls if path in {"/car_data", "/location", "/weather"}
    ]
    assert {path for path, _params in channel_calls} == {"/car_data", "/location", "/weather"}
    assert len(channel_calls) == 3
    assert result["status"] == "unavailable"
    assert result["reason"]
    assert result["race_id"] == "2023-01"
    assert result["window"]["duration_minutes"] <= 10
    assert result["session_key"] == 1234
    assert result["lights_out_utc"] == "2023-03-05T15:00:00Z"
    for _path, params in channel_calls:
        assert params["session_key"] == 1234
        start = pd.Timestamp(str(params["date>"]))
        end = pd.Timestamp(str(params["date<"]))
        assert (end - start).total_seconds() == pytest.approx(600.000002)
        assert start == pd.Timestamp("2023-03-05T14:59:59.999999Z")
        assert end == pd.Timestamp("2023-03-05T15:10:00.000001Z")


def test_probe_records_endpoint_counts_timestamp_quality_and_clock_alignment() -> None:
    from f1si.data.coverage_audit import probe_bahrain_2023

    def rows(path: str, _params: dict[str, object], **_kwargs: object) -> list[dict[str, object]]:
        if path == "/sessions":
            return [
                {
                    "session_key": 1234,
                    "session_name": "Race",
                    "year": 2023,
                    "country_name": "Bahrain",
                }
            ]
        if path == "/laps":
            return [{"lap_number": 1, "date_start": "2023-03-05T15:00:00Z"}]
        return [
            {
                "date": timestamp,
                "driver_number": 14,
                "speed": 300.0,
            }
            for timestamp in (
                "2023-03-05T15:00:00Z",
                "2023-03-05T15:03:00Z",
                "2023-03-05T15:10:00Z",
            )
        ]

    result = probe_bahrain_2023(rows=rows)

    assert set(result["endpoints"]) == {"/car_data", "/location", "/weather"}
    for endpoint in result["endpoints"].values():
        assert endpoint["row_count"] == 3
        assert endpoint["usable_row_count"] == 3
        assert endpoint["valid_timestamp_fraction"] == 1.0
        assert endpoint["race_clock_alignment"] in {"aligned", "misaligned"}
        assert endpoint["first_source_utc"]
        assert endpoint["first_race_clock_s"] >= 0


@pytest.mark.parametrize("missing_field", ["year", "country_name", "session_name"])
def test_probe_requires_explicit_bahrain_2023_race_identity(missing_field: str) -> None:
    from f1si.data.coverage_audit import probe_bahrain_2023

    session = {
        "session_key": 1234,
        "session_name": "Race",
        "year": 2023,
        "country_name": "Bahrain",
    }
    session.pop(missing_field)
    calls: list[str] = []

    def rows(path: str, _params: dict[str, object], **_kwargs: object) -> list[dict[str, object]]:
        calls.append(path)
        return [session] if path == "/sessions" else []

    result = probe_bahrain_2023(rows=rows)

    assert result["status"] == "unavailable"
    assert "expected one Bahrain 2023 Race session, found 0" in result["reason"]
    assert calls == ["/sessions"]


def test_probe_rejects_invalid_session_key_before_bounded_requests() -> None:
    from f1si.data.coverage_audit import probe_bahrain_2023

    calls: list[str] = []

    def rows(path: str, _params: dict[str, object], **_kwargs: object) -> list[dict[str, object]]:
        calls.append(path)
        if path == "/sessions":
            return [
                {
                    "session_key": 0,
                    "session_name": "Race",
                    "year": 2023,
                    "country_name": "Bahrain",
                }
            ]
        return []

    result = probe_bahrain_2023(rows=rows)

    assert result["status"] == "unavailable"
    assert "invalid session_key" in result["reason"]
    assert calls == ["/sessions"]


def test_probe_counts_only_rows_inside_the_requested_clock_window() -> None:
    from f1si.data.coverage_audit import probe_bahrain_2023

    def rows(path: str, _params: dict[str, object], **_kwargs: object) -> list[dict[str, object]]:
        if path == "/sessions":
            return [
                {
                    "session_key": 1234,
                    "session_name": "Race",
                    "year": 2023,
                    "country_name": "Bahrain",
                }
            ]
        if path == "/laps":
            return [{"lap_number": 1, "date_start": "2023-03-05T15:00:00Z"}]
        return [{"date": "2023-03-05T15:10:01Z"}]

    result = probe_bahrain_2023(rows=rows)

    assert result["status"] == "unavailable"
    for endpoint in result["endpoints"].values():
        assert endpoint["row_count"] == 1
        assert endpoint["usable_row_count"] == 0
        assert endpoint["race_clock_alignment"] == "misaligned"
        assert endpoint["status"] == "unavailable"
        assert "inside the 0-600 second window" in endpoint["reason"]


def test_probe_keeps_partial_endpoint_evidence_when_later_request_fails() -> None:
    from f1si.data.coverage_audit import probe_bahrain_2023
    from f1si.data.sources import SourceError

    def rows(path: str, _params: dict[str, object], **_kwargs: object) -> list[dict[str, object]]:
        if path == "/sessions":
            return [
                {
                    "session_key": 1234,
                    "session_name": "Race",
                    "year": 2023,
                    "country_name": "Bahrain",
                }
            ]
        if path == "/laps":
            return [{"lap_number": 1, "date_start": "2023-03-05T15:00:00Z"}]
        if path == "/car_data":
            return [{"date": "2023-03-05T15:03:00Z"}]
        if path == "/location":
            raise SourceError("location endpoint unavailable")
        raise AssertionError("weather must not be requested after location fails")

    result = probe_bahrain_2023(rows=rows)

    assert result["status"] == "unavailable"
    assert "location endpoint unavailable" in result["reason"]
    assert result["endpoints"]["/car_data"]["row_count"] == 1
    assert result["endpoints"]["/car_data"]["usable_row_count"] == 1
    assert result["endpoints"]["/car_data"]["status"] == "available"
    assert "request failed" in result["endpoints"]["/location"]["reason"]
    assert "not requested" in result["endpoints"]["/weather"]["reason"]


def test_coverage_report_writer_emits_explicit_unavailable_status(tmp_path: Path) -> None:
    import json

    from f1si.data.coverage_audit import write_coverage_report

    report = {
        "local_cache": {
            "catalog_complete_races": 1,
            "races": [],
            "channels": {"weather": {}, "car_data": {}, "location": {}},
        },
        "bahrain_2023_probe": {
            "status": "unavailable",
            "reason": "no usable rows returned",
            "endpoints": {},
        },
    }
    destination = tmp_path / "coverage.json"

    write_coverage_report(report, destination)

    saved = json.loads(destination.read_text(encoding="utf-8"))
    assert saved["bahrain_2023_probe"]["status"] == "unavailable"
    assert saved["bahrain_2023_probe"]["reason"]
