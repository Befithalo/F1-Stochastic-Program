"""Independent synthetic recovery and track-shape sensitivity checks."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from f1si.data.asof import AsOf, RaceInfo, RaceSnapshot
from f1si.data.physics_input import PhysicsInput, VersionedArtifactRef
from f1si.geometry.profile import GeometryProfile, load_profile
from f1si.pace.point_mass import (
    PointMassPaceModel,
    PointMassParameters,
    PointMassVehicleScenario,
    _corner_caps,
    _geometry_grid,
)
from f1si.pace.point_mass_fit import fit_effective_power_mass_scale
from tests.geometry.test_profile import _write_profile
from tests.pace.point_mass_truth import (
    PointMassTruth,
    generate_point_mass_truth,
    recovery_within_tolerance,
)


def _rewrite_profile(
    root: Path,
    *,
    kind: str,
    radius_m: float = 120.0,
    y_radius_m: float = 550.0,
    segment_count: int = 64,
) -> GeometryProfile:
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = _write_profile(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset_path = root / manifest["asset_path"]
    if kind == "circle":
        points = [
            (
                radius_m * math.cos(2.0 * math.pi * index / segment_count),
                radius_m * math.sin(2.0 * math.pi * index / segment_count),
            )
            for index in range(segment_count + 1)
        ]
        manifest["quality"].update(
            minimum_distance_m=700.0,
            maximum_distance_m=800.0,
            maximum_curvature_inv_m=0.02,
        )
    elif kind == "ellipse":
        points = [
            (
                1_400.0 * math.cos(2.0 * math.pi * index / segment_count),
                y_radius_m * math.sin(2.0 * math.pi * index / segment_count),
            )
            for index in range(segment_count + 1)
        ]
    else:
        raise ValueError(f"unsupported synthetic profile kind: {kind}")
    raw = "x_m,y_m,width_m\n" + "".join(f"{x:.9f},{y:.9f},12.00\n" for x, y in points)
    asset_path.write_text(raw, encoding="utf-8")
    manifest["sha256"] = hashlib.sha256(asset_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return load_profile(manifest_path, asset_root=root)


def _scenario(season: int = 2023) -> PointMassVehicleScenario:
    return PointMassVehicleScenario(
        driver=1,
        season=str(season),
        mass_kg=850.0,
        fuel_kg=50.0,
        fuel_burn_kg_per_lap=1.7,
        power_w=650_000.0,
        drag_area_m2=1.4,
        downforce_area_m2=5.3,
        grip_mu=1.7,
        time_sd_s=0.15,
    )


def _empty_model(profile: GeometryProfile, season: int = 2023) -> PointMassPaceModel:
    race_id = f"{season}-01"
    race = RaceInfo(
        race_id=race_id,
        season=season,
        round=1,
        slug=f"synthetic-circle-{season}",
        event_name=f"Synthetic Circle {season}",
        circuit="Synthetic uniform circle",
        country="Test",
        race_start_utc=datetime(season, 3, 1, tzinfo=UTC),
        scheduled_laps=57,
        era="synthetic",
        out_of_sample=False,
    )
    empty = pd.DataFrame()
    snapshot = RaceSnapshot(
        race=race,
        at=AsOf(race_id, 50),
        cutoff_s=10_000.0,
        entries=empty,
        laps=empty,
        track_status=empty,
        race_control=empty,
        weather=empty,
        car_data=empty,
        location=empty,
        stints=empty,
        pit_events=empty,
        cars=empty,
    )
    parameter_ref = VersionedArtifactRef("synthetic-physics", "1", "c" * 64)
    parameters = PointMassParameters(parameter_ref, (_scenario(season),))
    physics = PhysicsInput(snapshot, profile.reference, parameter_ref, {})
    return PointMassPaceModel(
        profile,
        physics,
        parameters,
        {"SOFT": 1.1, "MEDIUM": 1.0, "HARD": 0.9},
    )


def _training_model(
    profile: GeometryProfile,
    season: int,
    truth: PointMassTruth,
) -> PointMassPaceModel:
    model = _empty_model(profile, season)
    race_id = f"{season}-01"
    rows = [
        {
            "driver_number": lap.driver_number,
            "lap_number": lap.lap_number,
            "lap_time_s": lap.lap_time_s,
            "tyre_life": lap.lap_number,
            "compound": "MEDIUM",
            "stint": 1,
            "is_pit_in_lap": False,
            "is_pit_out_lap": False,
            "track_status": "1",
            "visible_at_s": float(lap.lap_number * 90),
        }
        for lap in truth.laps
        if lap.race_id == race_id
    ]
    snapshot = replace(model.physics_input.snapshot, laps=pd.DataFrame(rows))
    physics = PhysicsInput(
        snapshot,
        profile.reference,
        model.parameters.parameter_ref,
        model.physics_input.coverage,
    )
    return PointMassPaceModel(
        profile,
        physics,
        model.parameters,
        model.compound_grip,
    )


def test_truth_generator_is_independent_seeded_and_records_si_contract(tmp_path: Path) -> None:
    race_laps = {f"{season}-01": tuple(range(2, 42)) for season in (2023, 2024, 2025)}
    first = generate_point_mass_truth(race_laps=race_laps, seed=10_142)
    second = generate_point_mass_truth(race_laps=race_laps, seed=10_142)

    assert first == second
    assert first.seed == 10_142
    assert first.sample_size == len(first.laps) == 120
    assert first.identifiable_terms == ("effective_tractive_power_to_mass_scale",)
    assert dict(first.units)["lap_time_s"] == "s"
    assert dict(first.units)["power_w"] == "W"
    assert "mass_kg" in dict(first.assumptions)
    assert np.isfinite(np.asarray([lap.lap_time_s for lap in first.laps], dtype=np.float64)).all()
    source = Path(__file__).with_name("point_mass_truth.py").read_text(encoding="utf-8")
    assert "f1si.pace" not in source
    assert "_solve_speed_envelope" not in source


def test_independent_truth_recovers_only_effective_scale_within_five_percent(
    tmp_path: Path,
) -> None:
    profile = _rewrite_profile(tmp_path / "truth-circle", kind="circle")
    race_laps = {f"{season}-01": tuple(range(2, 42)) for season in (2023, 2024, 2025)}
    truth = generate_point_mass_truth(race_laps=race_laps, seed=10_142)
    models = tuple(_training_model(profile, season, truth) for season in (2023, 2024, 2025))

    report = fit_effective_power_mass_scale(models, bounds=truth.fit_bounds)

    assert report.status == "identified", json.dumps(report.to_dict())
    assert report.candidate_scale is not None
    assert recovery_within_tolerance(
        report.candidate_scale,
        truth.effective_power_mass_scale,
    )
    assert report.sensitivity_rank > 0
    assert report.sensitivity_condition is not None
    assert report.sensitivity_condition <= 1e6
    assert report.absolute_assumptions == tuple(name for name, _value in truth.assumptions)


def test_unexcited_truth_returns_unidentifiable_without_an_arbitrary_estimate(
    tmp_path: Path,
) -> None:
    profile = _rewrite_profile(tmp_path / "unexcited-circle", kind="circle")
    race_laps = {f"{season}-01": (20,) for season in (2023, 2024, 2025)}
    truth = generate_point_mass_truth(race_laps=race_laps, seed=71)
    models = tuple(_training_model(profile, season, truth) for season in (2023, 2024, 2025))

    report = fit_effective_power_mass_scale(models, declared_assumption=1.03)

    assert truth.identifiable_terms == ()
    assert report.status == "unidentifiable"
    assert report.candidate_scale is None
    assert report.declared_assumption == 1.03
    assert report.unidentifiable_reason


def test_five_percent_recovery_boundary_is_inclusive() -> None:
    assert recovery_within_tolerance(1.05, 1.0)
    assert not recovery_within_tolerance(1.050001, 1.0)


def test_track_shape_curvature_change_changes_closed_lap_without_mutating_source(
    tmp_path: Path,
) -> None:
    from f1si.pace.point_mass import _lap_time_s, _solve_speed_envelope

    base = _rewrite_profile(tmp_path / "base-shape", kind="ellipse", y_radius_m=550.0)
    changed = _rewrite_profile(tmp_path / "changed-shape", kind="ellipse", y_radius_m=400.0)
    base_y_before = base.y_m.copy()
    base_ds, base_curvature = _geometry_grid(base)
    changed_ds, changed_curvature = _geometry_grid(changed)
    scenario = _scenario()
    base_caps = _corner_caps(base_curvature, 900.0, scenario.downforce_area_m2, scenario.grip_mu)
    changed_caps = _corner_caps(
        changed_curvature,
        900.0,
        scenario.downforce_area_m2,
        scenario.grip_mu,
    )
    base_speed, _ = _solve_speed_envelope(
        ds=base_ds,
        curvature=base_curvature,
        mass_kg=900.0,
        power_w=scenario.power_w,
        drag_area_m2=scenario.drag_area_m2,
        downforce_area_m2=scenario.downforce_area_m2,
        grip_mu=scenario.grip_mu,
    )
    changed_speed, _ = _solve_speed_envelope(
        ds=changed_ds,
        curvature=changed_curvature,
        mass_kg=900.0,
        power_w=scenario.power_w,
        drag_area_m2=scenario.drag_area_m2,
        downforce_area_m2=scenario.downforce_area_m2,
        grip_mu=scenario.grip_mu,
    )

    assert changed_caps.min() < base_caps.min()
    assert not np.array_equal(base_speed, changed_speed)
    assert _lap_time_s(base_ds, base_speed) != pytest.approx(
        _lap_time_s(changed_ds, changed_speed), rel=1e-6
    )
    assert len(base_ds) == base.validation.segment_count
    assert len(changed_ds) == changed.validation.segment_count
    assert float(base_ds.sum()) == pytest.approx(base.total_distance_m, rel=1e-9)
    assert float(changed_ds.sum()) == pytest.approx(changed.total_distance_m, rel=1e-9)
    np.testing.assert_array_equal(base.y_m, base_y_before)
