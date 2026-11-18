"""Cutoff-safe effective point-mass fitting contracts (DEC-140/141/142)."""

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
    _lap_time_s,
    _solve_speed_envelope,
)
from f1si.pace.point_mass_fit import fit_effective_power_mass_scale
from tests.geometry.test_profile import _write_profile


def _profile(tmp_path: Path) -> GeometryProfile:
    manifest_path = _write_profile(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset_path = tmp_path / manifest["asset_path"]
    points: list[tuple[float, float]] = []
    points.extend((float(x), 100.0) for x in np.linspace(-1_000, 1_000, 80, endpoint=False))
    points.extend(
        (
            1_000.0 + 100.0 * math.cos(float(angle)),
            100.0 * math.sin(float(angle)),
        )
        for angle in np.linspace(math.pi / 2, -math.pi / 2, 13, endpoint=True)
    )
    points.extend((float(x), -100.0) for x in np.linspace(1_000, -1_000, 80, endpoint=False)[1:])
    points.extend(
        (
            -1_000.0 + 100.0 * math.cos(float(angle)),
            100.0 * math.sin(float(angle)),
        )
        for angle in np.linspace(-math.pi / 2, -3 * math.pi / 2, 13, endpoint=True)
    )
    asset = "x_m,y_m,width_m\n" + "".join(f"{x:.6f},{y:.6f},12.00\n" for x, y in points)
    asset_path.write_text(asset, encoding="utf-8")
    manifest["sha256"] = hashlib.sha256(asset_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return load_profile(manifest_path, asset_root=tmp_path)


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame()


def _model(
    profile: GeometryProfile,
    *,
    season: int,
    scale: float,
    lap_numbers: range | tuple[int, ...] = range(2, 42),
    cutoff_s: float = 4_000.0,
    cutoff_boundary: bool = False,
    post_cutoff_row: bool = False,
    future_time_delta: float = 0.0,
    out_of_sample: bool = False,
    observed_scale: float | None = None,
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
        season=str(season) if season in (2023, 2024, 2025) else "2023",
        mass_kg=850.0,
        fuel_kg=50.0,
        fuel_burn_kg_per_lap=1.7,
        power_w=650_000.0,
        drag_area_m2=1.4,
        downforce_area_m2=5.3,
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
                "lap_time_s": (
                    100.0 - observed_scale * lap_no
                    if observed_scale is not None
                    else _lap_time_s(model._ds, speed)
                )
                + 0.004 * math.sin(lap_no * 0.71 + season)
                + (future_time_delta if visible_at > cutoff_s else 0.0),
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


def _with_laps(model: PointMassPaceModel, laps: pd.DataFrame) -> PointMassPaceModel:
    snapshot = replace(model.physics_input.snapshot, laps=laps)
    physics = PhysicsInput(
        snapshot,
        model.geometry.reference,
        model.parameters.parameter_ref,
        model.physics_input.coverage,
    )
    return PointMassPaceModel(
        model.geometry,
        physics,
        model.parameters,
        model.compound_grip,
    )


def test_fit_uses_lap_end_time_when_prepared_input_has_no_visible_at_column(
    tmp_path: Path,
) -> None:
    profile = _profile(tmp_path)
    models = tuple(_model(profile, season=year, scale=1.08) for year in (2023, 2024, 2025))
    expected = fit_effective_power_mass_scale(models)
    lap_end_models = []
    for model in models:
        laps = model.physics_input.laps
        laps["lap_end_s"] = laps["visible_at_s"]
        laps = laps.drop(columns=["visible_at_s"])
        lap_end_models.append(_with_laps(model, laps))

    actual = fit_effective_power_mass_scale(tuple(lap_end_models))

    assert actual.to_dict() == expected.to_dict()


def test_fit_rejects_driver_scenario_from_another_race_season(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    model = _model(profile, season=2025, scale=1.08)
    mismatched_scenario = replace(model.parameters.scenarios[0], season="2023")
    mismatched_parameters = replace(model.parameters, scenarios=(mismatched_scenario,))
    # Exercise the fitter's defensive check against a corrupted/legacy prepared model.
    object.__setattr__(model, "parameters", mismatched_parameters)

    report = fit_effective_power_mass_scale((model,))

    assert report.status == "unidentifiable"
    assert report.candidate_scale is None
    assert report.unidentifiable_reason is not None
    assert "scenario season" in report.unidentifiable_reason


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
    assert report.sensitivity_condition is not None
    assert report.sensitivity_condition <= 1e6
    assert report.n_races == 3
    assert report.n_laps >= 30
    assert report.residual_variance_s2 is not None
    assert report.residual_support_laps == report.n_laps
    assert report.residual_support_races == 3
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


@pytest.mark.parametrize(
    ("observed_scale", "expected_boundary"),
    [(0.2, 0.8), (2.0, 1.4)],
)
def test_bound_optimum_is_boundary_limited_and_does_not_replace_assumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    observed_scale: float,
    expected_boundary: float,
) -> None:
    from f1si.pace import point_mass_fit

    profile = _profile(tmp_path)
    models = tuple(
        _model(profile, season=year, scale=1.0, observed_scale=observed_scale)
        for year in (2023, 2024, 2025)
    )
    monkeypatch.setattr(
        point_mass_fit,
        "_lap_prediction",
        lambda row, scale: 100.0 - scale * row.lap,
    )

    report = fit_effective_power_mass_scale(
        models,
        declared_assumption=1.0,
        bounds=(0.8, 1.4),
    )

    assert report.status == "boundary_limited"
    assert report.candidate_scale is None
    assert report.declared_assumption == 1.0
    assert report.boundary_value == pytest.approx(expected_boundary)


def test_rank_deficient_panel_is_unidentifiable_and_keeps_assumption(
    tmp_path: Path,
) -> None:
    profile = _profile(tmp_path)
    models = tuple(
        _model(profile, season=year, scale=1.0, lap_numbers=(10,)) for year in (2023, 2024, 2025)
    )

    report = fit_effective_power_mass_scale(models, declared_assumption=1.0)

    assert report.status == "unidentifiable"
    assert report.candidate_scale is None
    assert report.declared_assumption == 1.0
    assert report.sensitivity_rank < report.n_races + 1
    assert "rank deficient" in (report.unidentifiable_reason or "")


@pytest.mark.parametrize("season", [2022, 2026])
def test_fit_rejects_races_outside_the_training_seasons(tmp_path: Path, season: int) -> None:
    profile = _profile(tmp_path)
    model = _model(profile, season=2023, scale=1.0)
    unsupported_id = f"{season}-01"
    unsupported_race = replace(model.physics_input.race, race_id=unsupported_id, season=season)
    unsupported_snapshot = replace(
        model.physics_input.snapshot,
        race=unsupported_race,
        at=replace(model.physics_input.snapshot.at, race_id=unsupported_id),
    )
    object.__setattr__(
        model,
        "physics_input",
        PhysicsInput(
            unsupported_snapshot,
            model.geometry.reference,
            model.parameters.parameter_ref,
            model.physics_input.coverage,
        ),
    )

    report = fit_effective_power_mass_scale((model,))

    assert report.status == "unidentifiable"
    assert report.candidate_scale is None
    assert "2023-2025" in (report.unidentifiable_reason or "")


def test_cutoff_equality_is_included_and_reported(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    model = _model(
        profile,
        season=2023,
        scale=1.08,
        lap_numbers=range(2, 42),
        cutoff_boundary=True,
    )

    report = fit_effective_power_mass_scale((model,))

    assert report.n_laps == 40
    assert report.cutoffs == (("2023-01", 4_000.0),)
    assert report.race_ids == ("2023-01",)


def test_post_cutoff_rows_and_values_leave_fit_report_unchanged(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    visible = tuple(
        _model(profile, season=year, scale=1.08, lap_numbers=range(2, 41))
        for year in (2023, 2024, 2025)
    )
    future = tuple(
        _model(
            profile,
            season=year,
            scale=1.08,
            lap_numbers=range(2, 42),
            post_cutoff_row=True,
            future_time_delta=10_000.0,
        )
        for year in (2023, 2024, 2025)
    )

    visible_report = fit_effective_power_mass_scale(visible)
    future_report = fit_effective_power_mass_scale(future)

    assert visible_report.to_dict() == future_report.to_dict()


def test_training_row_and_model_permutation_leave_report_unchanged(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    models = tuple(_model(profile, season=year, scale=1.08) for year in (2023, 2024, 2025))
    permuted = tuple(
        _with_laps(
            model,
            model.physics_input.laps.iloc[
                np.random.default_rng(42 + model.physics_input.race.season).permutation(
                    len(model.physics_input.laps)
                )
            ].reset_index(drop=True),
        )
        for model in reversed(models)
    )

    expected = fit_effective_power_mass_scale(models)
    actual = fit_effective_power_mass_scale(permuted)

    assert expected.to_dict() == actual.to_dict()


def test_fit_report_keeps_absolute_vehicle_terms_as_assumptions(
    tmp_path: Path,
) -> None:
    report = fit_effective_power_mass_scale([])
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


def test_residual_support_is_unavailable_without_three_supported_races(
    tmp_path: Path,
) -> None:
    profile = _profile(tmp_path)
    model = _model(profile, season=2023, scale=1.08)

    report = fit_effective_power_mass_scale((model,))
    bound = report.bind(model.parameters)

    assert report.status == "identified"
    assert report.residual_support_available is False
    assert report.residual_variance_s2 is None
    assert report.covariance is None
    assert bound.residual_variance_s2 is None
    assert bound.power_mass_scale_variance is None


def test_residual_support_opens_at_30_laps_across_three_races(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    models = tuple(
        _model(profile, season=year, scale=1.08, lap_numbers=range(2, 12))
        for year in (2023, 2024, 2025)
    )

    report = fit_effective_power_mass_scale(models)

    assert report.status == "identified"
    assert report.n_laps == 30
    assert report.residual_support_available is True
    assert report.residual_support_laps == 30
    assert report.residual_support_races == 3
    assert report.residual_variance_s2 is not None
