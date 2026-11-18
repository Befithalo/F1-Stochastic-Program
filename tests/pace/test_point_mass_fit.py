"""Cutoff-safe effective point-mass fitting contracts (DEC-140/141/142)."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from f1si.data.asof import AsOf, RaceInfo, RaceSnapshot
from f1si.data.physics_input import PhysicsInput, VersionedArtifactRef
from f1si.geometry.profile import load_profile
from f1si.pace.point_mass import (
    PointMassPaceModel,
    PointMassParameters,
    PointMassVehicleScenario,
    _lap_time_s,
    _solve_speed_envelope,
)
from f1si.pace.point_mass_fit import fit_effective_power_mass_scale
from tests.geometry.test_profile import _write_profile


def _profile(tmp_path: Path):
    return load_profile(_write_profile(tmp_path), asset_root=tmp_path)


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame()


def _model(
    profile,
    *,
    season: int,
    scale: float,
    lap_numbers: range | tuple[int, ...] = range(2, 42),
    cutoff_s: float = 4_000.0,
    cutoff_boundary: bool = False,
    post_cutoff_row: bool = False,
    out_of_sample: bool = False,
) -> PointMassPaceModel:
    race_id = f"{season}-01"
    at = AsOf(race_id, 50)
    race = RaceInfo(
        race_id=race_id,
        season=season,
        round=1,
        slug=f"bahrain-{season}",
        event_name=f"Bahrain Grand Prix {season}",
        circuit="Bahrain International Circuit",
        country="Bahrain",
        race_start_utc=datetime(season, 3, 1, tzinfo=UTC),
        scheduled_laps=57,
        era="ground_effect",
        out_of_sample=out_of_sample,
    )
    scenario = PointMassVehicleScenario(
        driver=1,
        season="2023",
        mass_kg=850.0,
        fuel_kg=50.0,
        fuel_burn_kg_per_lap=1.7,
        power_w=650_000.0,
        drag_area_m2=1.4,
        downforce_area_m2=10.0,
        grip_mu=1.7,
        time_sd_s=0.15,
    )
    parameter_ref = VersionedArtifactRef("physics-parameters", "1", "a" * 64)
    placeholder = RaceSnapshot(
        race=race,
        at=at,
        cutoff_s=cutoff_s,
        entries=_empty_frame(),
        laps=pd.DataFrame(
            columns=[
                "driver_number",
                "lap_number",
                "lap_time_s",
                "tyre_life",
                "compound",
                "stint",
                "is_pit_in_lap",
                "is_pit_out_lap",
                "track_status",
                "visible_at_s",
            ]
        ),
        track_status=_empty_frame(),
        race_control=_empty_frame(),
        weather=_empty_frame(),
        car_data=_empty_frame(),
        location=_empty_frame(),
        stints=_empty_frame(),
        pit_events=_empty_frame(),
        cars=_empty_frame(),
    )
    prepared = PhysicsInput(placeholder, profile.reference, parameter_ref, {})
    parameters = PointMassParameters(parameter_ref, (scenario,))
    model = PointMassPaceModel(
        profile,
        prepared,
        parameters,
        {"SOFT": 1.1, "MEDIUM": 1.0, "HARD": 0.9},
    )
    laps: list[dict[str, object]] = []
    for lap_no in lap_numbers:
        fuel = max(0.0, scenario.fuel_kg - scenario.fuel_burn_kg_per_lap * (lap_no - 1))
        speed, _ = _solve_speed_envelope(
            ds=model._ds,
            curvature=model._curvature,
            mass_kg=scenario.mass_kg + fuel,
            power_w=scenario.power_w * scale,
            drag_area_m2=scenario.drag_area_m2,
            downforce_area_m2=scenario.downforce_area_m2,
            grip_mu=scenario.grip_mu,
        )
        visible_at = float(lap_no * 90)
        if cutoff_boundary and lap_no == max(lap_numbers):
            visible_at = cutoff_s
        if post_cutoff_row and lap_no == max(lap_numbers):
            visible_at = cutoff_s + 1.0
        laps.append(
            {
                "driver_number": 1,
                "lap_number": lap_no,
                "lap_time_s": _lap_time_s(model._ds, speed)
                + 0.004 * math.sin(lap_no * 0.71 + season),
                "tyre_life": lap_no,
                "compound": "MEDIUM",
                "stint": 1,
                "is_pit_in_lap": False,
                "is_pit_out_lap": False,
                "track_status": "1",
                "visible_at_s": visible_at,
            }
        )
    updated = replace(placeholder, laps=pd.DataFrame(laps))
    prepared = PhysicsInput(updated, profile.reference, parameter_ref, {})
    return PointMassPaceModel(
        profile,
        prepared,
        parameters,
        {"SOFT": 1.1, "MEDIUM": 1.0, "HARD": 0.9},
    )


def test_fit_recovers_effective_scale_from_cutoff_scoped_training_panel(
    tmp_path: Path,
) -> None:
    profile = _profile(tmp_path)
    models = tuple(_model(profile, season=year, scale=1.08) for year in (2023, 2024, 2025))

    report = fit_effective_power_mass_scale(
        models,
        declared_assumption=1.0,
        bounds=(0.75, 1.4),
    )

    assert report.status == "identified"
    assert report.candidate_scale == pytest.approx(1.08, rel=0.05)
    assert report.declared_assumption == 1.0
    assert report.sensitivity_rank > 0
    assert report.sensitivity_condition <= 1e6
    assert report.n_races == 3
    assert report.n_laps >= 30
    assert report.residual_variance_s2 is not None
    assert report.covariance is not None
    assert report.covariance >= 0.0
    assert report.absolute_assumptions == (
        "mass_kg",
        "fuel_kg",
        "fuel_burn_kg_per_lap",
        "power_w",
        "drag_area_m2",
        "downforce_area_m2",
        "grip_mu",
    )


def test_empty_panel_is_explicitly_unidentifiable_and_keeps_assumption() -> None:
    report = fit_effective_power_mass_scale([], declared_assumption=1.07)

    assert report.status == "unidentifiable"
    assert report.candidate_scale is None
    assert report.declared_assumption == 1.07
    assert report.covariance is None
    assert report.unidentifiable_reason


def test_bound_optimum_is_boundary_limited_and_does_not_replace_assumption(
    tmp_path: Path,
) -> None:
    profile = _profile(tmp_path)
    models = tuple(_model(profile, season=year, scale=1.8) for year in (2023, 2024, 2025))

    report = fit_effective_power_mass_scale(
        models,
        declared_assumption=1.0,
        bounds=(0.75, 1.4),
    )

    assert report.status == "boundary_limited"
    assert report.candidate_scale is None
    assert report.declared_assumption == 1.0
    assert report.boundary_value == pytest.approx(1.4)


def test_fit_report_keeps_absolute_vehicle_terms_as_assumptions(
    tmp_path: Path,
) -> None:
    profile = _profile(tmp_path)
    model = _model(profile, season=2023, scale=1.0)

    report = fit_effective_power_mass_scale((model,))
    serialized = report.to_dict()

    assert report.candidate_term == "effective_tractive_power_to_mass_scale"
    assert all(
        name in report.absolute_assumptions
        for name in (
            "mass_kg",
            "power_w",
            "drag_area_m2",
            "downforce_area_m2",
            "grip_mu",
        )
    )
    assert "results" not in str(serialized).lower()
    assert "classification" not in str(serialized).lower()
    assert "team" not in str(serialized).lower()
