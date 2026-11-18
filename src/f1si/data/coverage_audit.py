"""Read-only audit of cached optional channels and one bounded OpenF1 probe (DAT-01)."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from f1si.data import asof
from f1si.data.sources import RateLimitedError, SourceError

CHANNELS = ("weather", "car_data", "location")
EXPECTED_COMPLETE_RACES = 87
_DATE_COLUMN = "date"

Rows = Callable[..., list[dict[str, object]]]


def _local_cache_report(
    catalog: pd.DataFrame, channel_counts: Mapping[str, Mapping[str, int]]
) -> dict[str, Any]:
    """Count each optional channel for every complete race, without reading outcomes."""
    complete = catalog[catalog["load_status"] == "complete"].sort_values(["season", "round"])
    race_ids = complete["race_id"].astype(str).tolist()

    races: list[dict[str, Any]] = [
        {
            "race_id": race_id,
            "channels": {
                channel: {
                    "present": channel_counts.get(channel, {}).get(race_id, 0) > 0,
                    "row_count": channel_counts.get(channel, {}).get(race_id, 0),
                }
                for channel in CHANNELS
            },
        }
        for race_id in race_ids
    ]
    channel_totals = {
        channel: {
            "races_present": sum(row["channels"][channel]["present"] for row in races),
            "row_count": sum(row["channels"][channel]["row_count"] for row in races),
        }
        for channel in CHANNELS
    }
    return {
        "catalog_complete_races": len(races),
        "expected_complete_races": EXPECTED_COMPLETE_RACES,
        "matches_expected_catalog_size": len(races) == EXPECTED_COMPLETE_RACES,
        "races": races,
        "channels": channel_totals,
    }


def _unavailable_probe(reason: str, *, session_key: int | None = None) -> dict[str, Any]:
    """Keep all requested endpoint statuses explicit when the probe cannot produce evidence."""
    return {
        "race_id": "2023-01",
        "status": "unavailable",
        "reason": reason,
        "session_key": session_key,
        "lights_out_utc": None,
        "window": {"start_utc": None, "end_utc": None, "duration_minutes": 10},
        "endpoints": {
            endpoint: {
                "row_count": 0,
                "usable_row_count": 0,
                "valid_timestamp_fraction": 0.0,
                "race_clock_alignment": "unavailable",
                "first_source_utc": None,
                "first_race_clock_s": None,
            }
            for endpoint in ("/car_data", "/location", "/weather")
        },
    }


def _utc_iso(value: pd.Timestamp) -> str:
    return value.tz_convert(UTC).isoformat().replace("+00:00", "Z")


def probe_bahrain_2023(
    *,
    rows: Rows | None = None,
) -> dict[str, Any]:
    """Request at most three 10-minute Bahrain 2023 channels through OpenF1's cached seam."""
    if rows is None:
        return _unavailable_probe("OpenF1 source callback was not supplied by the CLI")
    fetch_rows = rows

    try:
        sessions = fetch_rows(
            "/sessions",
            {"year": 2023, "session_name": "Race", "country_name": "Bahrain"},
            freshness="forever",
        )
        candidates = [
            row
            for row in sessions
            if row.get("session_name") == "Race"
            and str(row.get("year", "2023")) == "2023"
            and str(row.get("country_name", "Bahrain")).casefold() == "bahrain"
        ]
        if len(candidates) != 1:
            return _unavailable_probe(
                f"expected one Bahrain 2023 Race session, found {len(candidates)}"
            )
        session_row = candidates[0]
        session_key = int(str(session_row["session_key"]))
        lap_rows = fetch_rows(
            "/laps",
            {"session_key": session_key, "lap_number": 1},
            freshness="forever",
        )
    except (KeyError, TypeError, ValueError, SourceError, RateLimitedError) as error:
        return _unavailable_probe(f"OpenF1 session metadata unavailable: {error}")

    lap_one_times = pd.to_datetime(
        [str(row.get("date_start", "")) for row in lap_rows if row.get("lap_number") == 1],
        utc=True,
        errors="coerce",
    ).dropna()
    if lap_one_times.empty:
        return _unavailable_probe(
            "OpenF1 Bahrain session has no usable lap-one date_start", session_key=session_key
        )
    lights_out = pd.Timestamp(lap_one_times.min())
    end = lights_out + timedelta(minutes=10)
    params: dict[str, str | int] = {
        "session_key": session_key,
        "date>": _utc_iso(lights_out),
        "date<": _utc_iso(end),
    }
    endpoints: dict[str, Any] = {}
    try:
        for endpoint in ("/car_data", "/location", "/weather"):
            endpoint_rows = fetch_rows(endpoint, params, freshness="forever")
            timestamps = pd.to_datetime(
                [str(row.get(_DATE_COLUMN, "")) for row in endpoint_rows],
                utc=True,
                errors="coerce",
            )
            valid = timestamps.notna()
            valid_count = sum(1 for value in valid if bool(value))
            valid_times = timestamps[valid]
            race_clock = (valid_times - lights_out).total_seconds()
            aligned = bool(len(valid_times) > 0 and ((race_clock >= 0) & (race_clock <= 600)).all())
            first_index = int(valid_times.argmin()) if len(valid_times) else None
            first_source = None
            first_race_clock = None
            if first_index is not None:
                first_timestamp = pd.Timestamp(valid_times[first_index])
                first_source = _utc_iso(first_timestamp)
                first_race_clock = float((first_timestamp - lights_out).total_seconds())
            endpoints[endpoint] = {
                "row_count": len(endpoint_rows),
                "usable_row_count": valid_count,
                "valid_timestamp_fraction": valid_count / len(endpoint_rows)
                if endpoint_rows
                else 0.0,
                "race_clock_alignment": "aligned" if aligned else "misaligned",
                "first_source_utc": first_source,
                "first_race_clock_s": first_race_clock,
            }
    except (SourceError, RateLimitedError) as error:
        unavailable = _unavailable_probe(
            f"bounded telemetry probe failed: {error}", session_key=session_key
        )
        unavailable["lights_out_utc"] = _utc_iso(lights_out)
        unavailable["window"] = {
            "start_utc": _utc_iso(lights_out),
            "end_utc": _utc_iso(end),
            "duration_minutes": 10,
        }
        unavailable["endpoints"].update(endpoints)
        return unavailable

    usable = sum(int(value["usable_row_count"]) for value in endpoints.values())
    probe_report: dict[str, Any] = {
        "race_id": "2023-01",
        "status": "available" if usable else "unavailable",
        "session_key": session_key,
        "lights_out_utc": _utc_iso(lights_out),
        "window": {
            "start_utc": _utc_iso(lights_out),
            "end_utc": _utc_iso(end),
            "duration_minutes": 10,
        },
        "endpoints": endpoints,
    }
    if not usable:
        probe_report["reason"] = "all three optional endpoints returned no usable timestamped rows"
    return probe_report


def build_coverage_report(
    db_path: Path,
    *,
    probe: bool = False,
    probe_rows: Rows | None = None,
) -> dict[str, Any]:
    """Build an audit through public data doors, with source access injected by the CLI."""
    catalog = asof.catalog(db_path)
    channel_counts = asof.optional_channel_row_counts(db_path)
    report: dict[str, Any] = {
        "schema_version": 1,
        "local_cache": _local_cache_report(catalog, channel_counts),
    }
    report["complete_catalog_race_ids"] = [row["race_id"] for row in report["local_cache"]["races"]]
    if probe:
        report["bahrain_2023_probe"] = probe_bahrain_2023(rows=probe_rows)
    return report


def write_coverage_report(report: Mapping[str, Any], destination: Path) -> None:
    """Write stable, human-readable JSON for the audit artifact."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
