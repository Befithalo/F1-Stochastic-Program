"""Acceptance contracts for the immutable, cutoff-safe physics input envelope."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from f1si.data.asof import RaceSnapshot
from f1si.data.physics_input import VersionedArtifactRef


def _artifact_ref(kind: str) -> VersionedArtifactRef:
    return VersionedArtifactRef(name=kind, version="1", sha256="0" * 64)


def test_car_data_cutoff_preserves_source_utc_and_race_clock(long_synthetic_db: Path) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import build_physics_input

    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10))
    cutoff = snapshot.cutoff_s
    assert cutoff is not None
    source_time = pd.Timestamp("2023-03-05T15:10:00Z")
    rows = pd.DataFrame(
        {
            "driver_number": [14],
            "source_utc": [source_time],
            "t_s": [cutoff],
            "visible_at_s": [cutoff],
            "speed_kph": [301.0],
            "rpm": [12_000],
        }
    )
    snapshot = replace(snapshot, car_data=rows)

    prepared = build_physics_input(
        snapshot, geometry_ref=_artifact_ref("geometry"), parameter_ref=_artifact_ref("parameters")
    )

    observed = prepared.car_data.iloc[0]
    assert observed["source_utc"] == source_time
    assert observed["t_s"] == cutoff
    assert observed["visible_at_s"] == cutoff
    assert observed["speed_kph"] == 301.0


def test_future_car_data_perturbation_does_not_change_physics_input(
    long_synthetic_db: Path,
) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import build_physics_input

    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10))
    cutoff = snapshot.cutoff_s
    assert cutoff is not None
    visible = pd.DataFrame(
        {
            "driver_number": [14],
            "source_utc": [pd.Timestamp("2023-03-05T15:10:00Z")],
            "t_s": [cutoff],
            "visible_at_s": [cutoff],
            "speed_kph": [301.0],
        }
    )
    future = pd.DataFrame(
        {
            "driver_number": [14],
            "source_utc": [pd.Timestamp("2023-03-05T15:11:00Z")],
            "t_s": [cutoff + 10.0],
            "visible_at_s": [cutoff + 10.0],
            "speed_kph": [400.0],
        }
    )
    refs = {
        "geometry_ref": _artifact_ref("geometry"),
        "parameter_ref": _artifact_ref("parameters"),
    }

    before = build_physics_input(replace(snapshot, car_data=visible), **refs)
    after = build_physics_input(replace(snapshot, car_data=pd.concat([visible, future])), **refs)

    pd.testing.assert_frame_equal(before.car_data, after.car_data)
    assert before.car_data["speed_kph"].tolist() == [301.0]


def test_physics_input_is_immutable_and_carries_versioned_refs(long_synthetic_db: Path) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import build_physics_input

    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10))
    prepared = build_physics_input(
        snapshot, geometry_ref=_artifact_ref("geometry"), parameter_ref=_artifact_ref("parameters")
    )
    original = prepared.laps.copy(deep=True)
    exposed = prepared.laps
    exposed.loc[:, "lap_time_s"] = -1.0

    pd.testing.assert_frame_equal(prepared.laps, original)
    assert prepared.geometry_ref.version == "1"
    assert prepared.parameter_ref.sha256 == "0" * 64
    assert not hasattr(prepared, "accessor")
    assert not hasattr(prepared, "database_path")


def test_sparse_optional_channels_report_cached_lap_fallback(long_synthetic_db: Path) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import build_physics_input

    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10))
    prepared = build_physics_input(
        snapshot,
        geometry_ref=_artifact_ref("geometry"),
        parameter_ref=_artifact_ref("parameters"),
    )

    assert prepared.coverage["car_data"].status in {"unavailable", "sparse"}
    assert prepared.coverage["car_data"].fallback == "cached_lap_timing"


def test_large_per_driver_sampling_gaps_select_cached_lap_fallback(long_synthetic_db: Path) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import build_physics_input

    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10))
    cutoff = snapshot.cutoff_s
    assert cutoff is not None
    source_time = pd.Timestamp("2023-03-05T15:00:00Z")
    car_data = pd.DataFrame(
        {
            "driver_number": [14, 14, 14],
            "source_utc": [
                source_time,
                source_time + timedelta(seconds=10),
                source_time + timedelta(seconds=20),
            ],
            "t_s": [0.0, 10.0, 20.0],
            "visible_at_s": [cutoff, cutoff, cutoff],
            "speed_kph": [300.0, 300.0, 300.0],
        }
    )
    prepared = build_physics_input(
        replace(snapshot, car_data=car_data),
        geometry_ref=_artifact_ref("geometry"),
        parameter_ref=_artifact_ref("parameters"),
    )

    coverage = prepared.coverage["car_data"]
    assert coverage.sampling_gap_p95_s == pytest.approx(10.0)
    assert coverage.sampling_gap_status == "exceeds_limit"
    assert coverage.status == "sparse"
    assert coverage.fallback == "cached_lap_timing"


def test_malformed_optional_channel_without_race_clock_fails_to_cached_laps(
    long_synthetic_db: Path,
) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import build_physics_input

    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10))
    cutoff = snapshot.cutoff_s
    assert cutoff is not None
    malformed = pd.DataFrame({"source_utc": [pd.NaT], "visible_at_s": [cutoff]})
    prepared = build_physics_input(
        replace(snapshot, car_data=malformed),
        geometry_ref=_artifact_ref("geometry"),
        parameter_ref=_artifact_ref("parameters"),
    )

    coverage = prepared.coverage["car_data"]
    assert coverage.race_clock_alignment == "unavailable"
    assert coverage.status == "sparse"
    assert coverage.fallback == "cached_lap_timing"


def test_physics_input_refuses_history_or_out_of_sample_capabilities() -> None:
    from f1si.data.physics_input import build_physics_input

    with pytest.raises((TypeError, ValueError)):
        build_physics_input(
            cast(RaceSnapshot, object()),
            geometry_ref=_artifact_ref("geometry"),
            parameter_ref=_artifact_ref("parameters"),
        )
