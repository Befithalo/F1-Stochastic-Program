"""Contracts for complete-catalog telemetry coverage and the single bounded probe."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_local_audit_counts_every_complete_race_and_channel(synthetic_db: Path) -> None:
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


def test_bahrain_probe_is_bounded_to_three_optional_endpoints() -> None:
    from f1si.data.coverage_audit import probe_bahrain_2023

    calls: list[tuple[str, dict[str, object]]] = []

    def rows(path: str, params: dict[str, object], **_kwargs: object) -> list[dict[str, object]]:
        calls.append((path, params))
        if path == "/sessions":
            return [{"session_key": 1234, "session_name": "Race", "year": 2023}]
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
        assert 0 <= (end - start).total_seconds() <= 600


def test_probe_records_endpoint_counts_timestamp_quality_and_clock_alignment() -> None:
    from f1si.data.coverage_audit import probe_bahrain_2023

    def rows(path: str, _params: dict[str, object], **_kwargs: object) -> list[dict[str, object]]:
        if path == "/sessions":
            return [{"session_key": 1234, "session_name": "Race", "year": 2023}]
        if path == "/laps":
            return [{"lap_number": 1, "date_start": "2023-03-05T15:00:00Z"}]
        return [
            {
                "date": "2023-03-05T15:03:00Z",
                "driver_number": 14,
                "speed": 300.0,
            }
        ]

    result = probe_bahrain_2023(rows=rows)

    assert set(result["endpoints"]) == {"/car_data", "/location", "/weather"}
    for endpoint in result["endpoints"].values():
        assert endpoint["row_count"] == 1
        assert endpoint["valid_timestamp_fraction"] == 1.0
        assert endpoint["race_clock_alignment"] in {"aligned", "misaligned"}
        assert endpoint["first_source_utc"]
        assert endpoint["first_race_clock_s"] >= 0


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
