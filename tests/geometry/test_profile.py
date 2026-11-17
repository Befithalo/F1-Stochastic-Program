"""Provenance, digest, confinement, and quality contracts for track profiles."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest


def _write_profile(root: Path, *, asset_path: str = "Sakhir.csv") -> Path:
    asset = root / asset_path
    asset.parent.mkdir(parents=True, exist_ok=True)
    points = [
        (1_400 * math.cos(2 * math.pi * index / 64), 550 * math.sin(2 * math.pi * index / 64), 12.0)
        for index in range(65)
    ]
    raw = "x_m,y_m,width_m\n" + "".join(f"{x:.6f},{y:.6f},{width:.2f}\n" for x, y, width in points)
    asset.write_text(raw, encoding="utf-8")
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "profile_id": "bahrain-2023-sakhir",
        "source_revision": "a" * 40,
        "source_asset_path": "tracks/Sakhir.csv",
        "asset_path": asset_path,
        "sha256": digest,
        "coordinate_frame": "local_cartesian_xy",
        "transform": {"type": "identity", "translation_m": [0.0, 0.0], "rotation_deg": 0.0},
        "units": {"coordinates": "m", "width": "m"},
        "attribution": "TUMFTM racetrack-database; source data attribution pending review",
        "redistribution_status": "external_local_only",
        "quality": {
            "validation_version": "1",
            "minimum_width_m": 1.0,
            "maximum_width_m": 30.0,
            "minimum_distance_m": 4_000.0,
            "maximum_distance_m": 6_500.0,
            "closed_loop_tolerance_m": 1.0,
            "maximum_curvature_inv_m": 0.02,
        },
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_valid_profile_preserves_units_transform_rights_and_digest(
    tmp_path: Path, long_synthetic_db: Path
) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import VersionedArtifactRef, build_physics_input
    from f1si.geometry.profile import load_profile

    manifest_path = _write_profile(tmp_path)

    profile = load_profile(manifest_path, asset_root=tmp_path)

    assert profile.manifest.units["coordinates"] == "m"
    assert profile.manifest.coordinate_frame == "local_cartesian_xy"
    assert profile.manifest.transform["type"] == "identity"
    assert profile.manifest.redistribution_status == "external_local_only"
    assert len(profile.manifest.sha256) == 64
    assert profile.total_distance_m == pytest.approx(6_500.0, rel=0.02)
    assert profile.reference.sha256 == profile.manifest.sha256
    assert not profile.x_m.flags.writeable
    serialized = profile.manifest.to_dict()
    assert serialized["transform"]["type"] == "identity"
    assert json.loads(json.dumps(serialized))["units"]["coordinates"] == "m"
    with pytest.raises(TypeError):
        profile.manifest.transform["type"] = "mutated"
    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10))
    prepared = build_physics_input(
        snapshot,
        geometry_ref=profile.reference,
        parameter_ref=VersionedArtifactRef("parameters", "1", "0" * 64),
    )
    assert prepared.geometry_ref == profile.reference


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "digest",
        "escape",
        "malformed",
        "open_loop",
        "zero_width",
        "degenerate",
        "distance",
        "curvature",
    ],
)
def test_invalid_or_unavailable_profile_fails_closed(tmp_path: Path, failure: str) -> None:
    from f1si.geometry.profile import GeometryProfileError, load_profile

    manifest_path = _write_profile(tmp_path, asset_path="nested/Sakhir.csv")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset = tmp_path / manifest["asset_path"]
    if failure == "digest":
        asset.write_text(asset.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    elif failure == "escape":
        manifest["asset_path"] = "../outside.csv"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif failure == "malformed":
        asset.write_text("x_m,y_m,width_m\nNaN,0,12\n", encoding="utf-8")
        manifest["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif failure == "open_loop":
        lines = asset.read_text(encoding="utf-8").splitlines()
        lines[-1] = "50.0,0.0,12.0"
        asset.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        manifest["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif failure == "zero_width":
        text = asset.read_text(encoding="utf-8").replace(",12.00", ",0.00")
        asset.write_text(text, encoding="utf-8")
        manifest["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif failure == "degenerate":
        asset.write_text("x_m,y_m,width_m\n" + "0,0,12\n" * 65, encoding="utf-8")
        manifest["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif failure == "distance":
        points = [
            (
                14_000 * math.cos(2 * math.pi * index / 64),
                5_500 * math.sin(2 * math.pi * index / 64),
                12.0,
            )
            for index in range(65)
        ]
        raw = "x_m,y_m,width_m\n" + "".join(
            f"{x:.6f},{y:.6f},{width:.2f}\n" for x, y, width in points
        )
        asset.write_text(raw, encoding="utf-8")
        manifest["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif failure == "curvature":
        points = [
            (
                1_400 * math.cos(2 * math.pi * index / 64) + (150.0 if index == 16 else 0.0),
                550 * math.sin(2 * math.pi * index / 64),
                12.0,
            )
            for index in range(65)
        ]
        raw = "x_m,y_m,width_m\n" + "".join(
            f"{x:.6f},{y:.6f},{width:.2f}\n" for x, y, width in points
        )
        asset.write_text(raw, encoding="utf-8")
        manifest["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif failure == "missing":
        asset.unlink()

    with pytest.raises((GeometryProfileError, ValueError, FileNotFoundError)):
        load_profile(manifest_path, asset_root=tmp_path)


def test_curve_with_zero_length_segments_is_rejected(tmp_path: Path) -> None:
    from f1si.geometry.profile import GeometryProfileError, load_profile

    manifest_path = _write_profile(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset = tmp_path / manifest["asset_path"]
    asset.write_text("x_m,y_m,width_m\n" + "0,0,12\n" * 65, encoding="utf-8")
    manifest["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises((GeometryProfileError, ValueError)):
        load_profile(manifest_path, asset_root=tmp_path)


def test_non_finite_coordinate_property_is_rejected(tmp_path: Path) -> None:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    from f1si.geometry.profile import GeometryProfileError, load_profile

    @settings(max_examples=8, deadline=None)
    @given(st.one_of(st.just(float("nan")), st.just(float("inf")), st.just(float("-inf"))))
    def check_coordinate_is_rejected(value: float) -> None:
        manifest_path = _write_profile(tmp_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        asset = tmp_path / manifest["asset_path"]
        asset.write_text(f"x_m,y_m,width_m\n{value!r},0,12\n", encoding="utf-8")
        manifest["sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with pytest.raises((GeometryProfileError, ValueError)):
            load_profile(manifest_path, asset_root=tmp_path)

    check_coordinate_is_rejected()


def test_asset_path_must_remain_inside_geometry_root(tmp_path: Path) -> None:
    from f1si.geometry.profile import load_profile

    manifest_path = _write_profile(tmp_path, asset_path="../outside.csv")

    with pytest.raises((ValueError, OSError)):
        load_profile(manifest_path, asset_root=tmp_path)
