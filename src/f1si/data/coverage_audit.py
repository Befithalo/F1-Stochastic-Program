"""Read-only audit of cached optional channels and one bounded OpenF1 probe (DAT-01)."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from f1si.data import _db
from f1si.data.sources import RateLimitedError, SourceError
from f1si.data.sources.openf1 import OpenF1Source

CHANNELS = ("weather", "car_data", "location")
EXPECTED_COMPLETE_RACES = 87
_DATE_COLUMN = "date"

Rows = Callable[..., list[dict[str, object]]]


def _local_cache_report(db_path: Path) -> dict[str, Any]:
    """Count each optional channel for every complete race, without reading outcomes."""
    with _db.connect_reader(db_path) as con:
        catalog_rows = con.execute(
            "SELECT race_id FROM races WHERE load_status = 'complete' ORDER BY season, round"
        ).fetchall()
        race_ids = [str(row[0]) for row in catalog_rows]
        counts: dict[str, dict[str, int]] = {channel: {} for channel in CHANNELS}
        for channel in CHANNELS:
            if not _db.table_exists(con, channel):
                continue
            grouped = con.execute(
                f"SELECT race_id, COUNT(*) FROM {channel} GROUP BY race_id"
            ).fetchall()
            counts[channel] = {str(race_id): int(count) for race_id, count in grouped}

    races: list[dict[str, Any]] = [
        {
            "race_id": race_id,
            "channels": {
                channel: {
                    "present": counts[channel].get(race_id, 0) > 0,
                    "row_count": counts[channel].get(race_id, 0),
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
    http_cache_dir: Path = Path("data/http-cache"),
    rows: Rows | None = None,
) -> dict[str, Any]:
    """Request at most three 10-minute Bahrain 2023 channels through OpenF1's cached seam."""
    if rows is None:
        source = OpenF1Source(http_cache_dir=http_cache_dir)
        fetch_rows: Rows = source._rows
    else:
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
    http_cache_dir: Path = Path("data/http-cache"),
) -> dict[str, Any]:
    """Build the local catalog report, optionally running the single bounded Bahrain probe."""
    report: dict[str, Any] = {
        "schema_version": 1,
        "local_cache": _local_cache_report(db_path),
    }
    report["complete_catalog_race_ids"] = [row["race_id"] for row in report["local_cache"]["races"]]
    if probe:
        report["bahrain_2023_probe"] = probe_bahrain_2023(http_cache_dir=http_cache_dir)
    return report


def write_coverage_report(report: Mapping[str, Any], destination: Path) -> None:
    """Write stable, human-readable JSON for the audit artifact."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--http-cache-dir", type=Path, default=Path("data/http-cache"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe-race", choices=("2023-01",))
    args = parser.parse_args(argv)
    report = build_coverage_report(
        args.database,
        probe=args.probe_race == "2023-01",
        http_cache_dir=args.http_cache_dir,
    )
    write_coverage_report(report, args.output)
    print(
        f"Wrote {args.output}: {report['local_cache']['catalog_complete_races']} complete races; "
        f"Bahrain probe {report.get('bahrain_2023_probe', {}).get('status', 'not requested')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
