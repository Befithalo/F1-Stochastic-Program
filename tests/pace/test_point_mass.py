"""Production-path checks for the deterministic geometry-backed PaceModel."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest


def _profile(tmp_path: Path) -> Any:
    from f1si.geometry.profile import load_profile
    from tests.geometry.test_profile import _write_profile

    return load_profile(_write_profile(tmp_path), asset_root=tmp_path)


def _model(tmp_path: Path, db_path: Path) -> Any:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import VersionedArtifactRef, build_physics_input
    from f1si.pace.point_mass import (
        PointMassPaceModel,
        PointMassParameters,
        PointMassVehicleScenario,
    )

    profile = _profile(tmp_path)
    parameter_ref = VersionedArtifactRef("physics-parameters", "1", "a" * 64)
    prepared = build_physics_input(
        AsOfAccessor(db_path).snapshot(AsOf("2023-01", 10)), profile.reference, parameter_ref
    )
    scenarios = tuple(
        PointMassVehicleScenario(
            driver=driver,
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
        for driver in (1, 2, 3, 4, 5, 6, 7, 8)
    )
    params = PointMassParameters(parameter_ref=parameter_ref, scenarios=scenarios)
    return PointMassPaceModel(
        geometry=profile,
        physics_input=prepared,
        parameters=params,
        compound_grip={"SOFT": 1.1, "MEDIUM": 1.0, "HARD": 0.9},
    )


def _uncertain_model(
    tmp_path: Path,
    db_path: Path,
    *,
    scale: float = 1.0,
    covariance: float = 1e-4,
    residual_variance_s2: float | None = 0.0025,
) -> Any:
    from f1si.pace.point_mass import PointMassPaceModel

    model = _model(tmp_path, db_path)
    parameters = replace(
        model.parameters,
        effective_power_mass_scale=scale,
        power_mass_scale_variance=covariance,
        residual_variance_s2=residual_variance_s2,
        residual_support_laps=30 if residual_variance_s2 is not None else 0,
        residual_support_races=3 if residual_variance_s2 is not None else 0,
    )
    return PointMassPaceModel(
        model.geometry,
        model.physics_input,
        parameters,
        model.compound_grip,
    )


@pytest.mark.parametrize("seed", [1])
def test_analytic_circle_deterministic_mean_sd_and_protocol(
    tmp_path: Path, long_synthetic_db: Path, seed: int
) -> None:
    from f1si.interfaces import PaceModel
    from f1si.pace.point_mass import PointMassPaceModel

    model = _model(tmp_path, long_synthetic_db)
    assert isinstance(model, PaceModel)
    driver = np.arange(1, 9, dtype=np.int64)
    compound = np.array(["SOFT", "MEDIUM", "HARD", "SOFT", "MEDIUM", "HARD", "SOFT", "MEDIUM"])
    age = np.arange(1, 9, dtype=np.int64)
    lap = np.arange(3, 11, dtype=np.int64)
    original = tuple(array.copy() for array in (driver, compound, age, lap))
    mean, sd = model.predict(driver=driver, compound=compound, tire_age=age, lap=lap)
    again, again_sd = model.predict(driver=driver, compound=compound, tire_age=age, lap=lap)
    assert mean.shape == sd.shape == driver.shape
    assert mean.dtype == sd.dtype == np.float64
    assert np.isfinite(mean).all()
    assert np.isfinite(sd).all()
    assert (sd > 0).all()
    assert np.array_equal(mean, again)
    assert np.array_equal(sd, again_sd)
    assert all(
        np.array_equal(current, before)
        for current, before in zip((driver, compound, age, lap), original, strict=True)
    )
    for index in range(len(driver)):
        row_mean, row_sd = model.predict(
            driver=driver[index : index + 1],
            compound=compound[index : index + 1],
            tire_age=age[index : index + 1],
            lap=lap[index : index + 1],
        )
        assert row_mean[0] == mean[index]
        assert row_sd[0] == sd[index]
    assert isinstance(model, PointMassPaceModel)
    from tests.conformance.suites import PaceProbe, check_pace_model

    check_pace_model(model, PaceProbe(driver, compound, age, lap))


def test_empty_batch_and_unknown_identifiers_fail_closed(
    tmp_path: Path, long_synthetic_db: Path
) -> None:

    model = _model(tmp_path, long_synthetic_db)
    empty = np.array([], dtype=np.int64)
    means, sds = model.predict(
        driver=empty, compound=np.array([], dtype=str), tire_age=empty, lap=empty
    )
    assert means.shape == sds.shape == (0,)
    assert means.dtype == sds.dtype == np.float64
    with pytest.raises(ValueError, match="unknown driver"):
        model.predict(
            driver=np.array([99]),
            compound=np.array(["SOFT"]),
            tire_age=np.array([1]),
            lap=np.array([1]),
        )
    with pytest.raises(ValueError, match="unknown compound"):
        model.predict(
            driver=np.array([1]),
            compound=np.array(["WET"]),
            tire_age=np.array([1]),
            lap=np.array([1]),
        )


def test_profile_counts_closed_seam_once_and_refinement_is_bounded(
    tmp_path: Path, long_synthetic_db: Path
) -> None:
    from f1si.pace.point_mass import _geometry_grid

    model = _model(tmp_path, long_synthetic_db)
    intervals, _curvature = _geometry_grid(model.geometry)
    assert len(intervals) == model.geometry.validation.segment_count
    assert float(intervals.sum()) == pytest.approx(model.geometry.total_distance_m)
    assert model.validate_grid_refinement(model.parameters.scenarios[0]) <= 0.001


def test_solver_force_envelope_and_segment_integration() -> None:
    from f1si.pace.point_mass import (
        PointMassConvergenceError,
        _corner_caps,
        _lap_time_s,
        _refined_lap_time_s,
        _solve_speed_envelope,
        _terminal_speed,
    )

    ds = np.full(48, 2 * math.pi * 100 / 48, dtype=np.float64)
    curvature = np.full(48, 1 / 100, dtype=np.float64)
    speed, passes = _solve_speed_envelope(
        ds=ds,
        curvature=curvature,
        mass_kg=850,
        power_w=650_000,
        drag_area_m2=1.4,
        downforce_area_m2=3.0,
        grip_mu=1.7,
    )
    cap = math.sqrt(1.7 * 850 * 9.80665 / (850 / 100 - 1.7 * 0.5 * 1.225 * 3.0))
    assert np.max(speed) <= cap + 1e-4
    assert passes <= 1000
    assert np.all(speed <= _corner_caps(curvature, 850, 3.0, 1.7) + 1e-6)
    assert _lap_time_s(ds, speed) == pytest.approx(
        float(np.sum(ds * (1 / speed + 1 / np.roll(speed, -1)) / 2))
    )
    base, refined = _refined_lap_time_s(
        ds=ds,
        curvature=curvature,
        mass_kg=850,
        power_w=650_000,
        drag_area_m2=1.4,
        downforce_area_m2=3.0,
        grip_mu=1.7,
    )
    assert abs(refined - base) / base <= 0.001
    assert math.isfinite(_terminal_speed(650_000, 1.4))
    with pytest.raises(PointMassConvergenceError, match="did not converge"):
        _solve_speed_envelope(
            ds=ds,
            curvature=np.where(np.arange(48) % 2, 0.01, 0.002),
            mass_kg=850,
            power_w=650_000,
            drag_area_m2=1.4,
            downforce_area_m2=3.0,
            grip_mu=1.7,
            max_passes=1,
        )


def test_one_at_a_time_physical_sensitivities_preserve_expected_direction() -> None:
    from f1si.pace.point_mass import (
        _corner_caps,
        _lap_time_s,
        _solve_speed_envelope,
    )

    radius_m = 120.0
    segment_count = 64
    ds = np.full(segment_count, 2.0 * math.pi * radius_m / segment_count, dtype=np.float64)
    curvature = np.full(segment_count, 1.0 / radius_m, dtype=np.float64)

    def lap_time(
        *, mass_kg: float = 850.0, power_w: float = 650_000.0, drag_area_m2: float = 1.4
    ) -> float:
        speed, _ = _solve_speed_envelope(
            ds=ds,
            curvature=curvature,
            mass_kg=mass_kg,
            power_w=power_w,
            drag_area_m2=drag_area_m2,
            downforce_area_m2=5.3,
            grip_mu=1.7,
        )
        return _lap_time_s(ds, speed)

    drive_limited = lap_time()
    assert lap_time(power_w=700_000.0) < drive_limited
    assert lap_time(drag_area_m2=1.8) > drive_limited
    assert lap_time(mass_kg=900.0) > drive_limited

    curvature_sample = np.asarray([1.0 / radius_m], dtype=np.float64)
    corner_cap = _corner_caps(curvature_sample, 850.0, 5.3, 1.7)
    more_grip_cap = _corner_caps(curvature_sample, 850.0, 5.3, 1.8)
    more_downforce_cap = _corner_caps(curvature_sample, 850.0, 5.8, 1.7)
    assert more_grip_cap[0] > corner_cap[0]
    assert more_downforce_cap[0] > corner_cap[0]


def test_point_mass_references_must_match(tmp_path: Path, long_synthetic_db: Path) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import VersionedArtifactRef, build_physics_input
    from f1si.pace.point_mass import (
        PointMassPaceModel,
        PointMassParameters,
        PointMassVehicleScenario,
    )

    profile = _profile(tmp_path)
    wrong = VersionedArtifactRef("wrong", "1", "b" * 64)
    prepared = build_physics_input(
        AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10)), profile.reference, wrong
    )
    scenario = PointMassVehicleScenario(1, "2023", 850, 50, 1.7, 650000, 1.4, 10, 1.7, 0.15)
    with pytest.raises(ValueError, match="parameter reference"):
        PointMassPaceModel(
            profile,
            prepared,
            PointMassParameters(VersionedArtifactRef("other", "1", "c" * 64), (scenario,)),
            {"SOFT": 1, "MEDIUM": 1, "HARD": 1},
        )


def test_future_physics_input_rows_do_not_change_prepared_model(
    tmp_path: Path, long_synthetic_db: Path
) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import build_physics_input
    from f1si.pace.point_mass import PointMassPaceModel

    model = _model(tmp_path, long_synthetic_db)
    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10))
    weather = snapshot.weather
    future = (
        weather.iloc[[0]].copy() if not weather.empty else pd.DataFrame(columns=weather.columns)
    )
    if future.empty:
        future = pd.DataFrame({"visible_at_s": [float(snapshot.cutoff_s or 0) + 1]})
    else:
        future["visible_at_s"] = float(snapshot.cutoff_s or 0) + 1
    replaced = replace(snapshot, weather=pd.concat([weather, future], ignore_index=True))
    prepared = build_physics_input(
        replaced, model.geometry.reference, model.parameters.parameter_ref
    )
    changed = PointMassPaceModel(model.geometry, prepared, model.parameters, model.compound_grip)
    values = np.arange(1, 9, dtype=np.int64)
    compounds = np.array(["SOFT", "MEDIUM", "HARD", "SOFT", "MEDIUM", "HARD", "SOFT", "MEDIUM"])
    original_mean, original_sd = model.predict(
        driver=values, compound=compounds, tire_age=values, lap=values
    )
    changed_mean, changed_sd = changed.predict(
        driver=values, compound=compounds, tire_age=values, lap=values
    )
    assert np.array_equal(original_mean, changed_mean)
    assert np.array_equal(original_sd, changed_sd)


def test_first_order_uncertainty_reports_separate_deterministic_components(
    tmp_path: Path, long_synthetic_db: Path
) -> None:
    model = _uncertain_model(tmp_path, long_synthetic_db)
    diagnostic = model.uncertainty_for(driver=1, compound="MEDIUM", lap=20)
    values = np.array([1], dtype=np.int64)
    mean, sd = model.predict(
        driver=values,
        compound=np.array(["MEDIUM"]),
        tire_age=values,
        lap=np.array([20], dtype=np.int64),
    )
    again, again_sd = model.predict(
        driver=values,
        compound=np.array(["MEDIUM"]),
        tire_age=values,
        lap=np.array([20], dtype=np.int64),
    )

    assert diagnostic.method == "first_order"
    assert diagnostic.active_set_stable is True
    assert diagnostic.parameter_variance_s2 is not None
    assert diagnostic.parameter_variance_s2 > 0.0
    assert diagnostic.residual_variance_s2 == pytest.approx(0.0025)
    assert diagnostic.scenario_variance_s2 == pytest.approx(0.15**2)
    assert sd[0] ** 2 == pytest.approx(diagnostic.total_variance_s2)
    assert mean.dtype == sd.dtype == np.float64
    assert np.array_equal(mean, again)
    assert np.array_equal(sd, again_sd)


def test_active_set_change_selects_bounded_sigma_points(
    tmp_path: Path,
    long_synthetic_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import f1si.pace.point_mass as point_mass

    model = _uncertain_model(tmp_path, long_synthetic_db)
    monkeypatch.setattr(
        point_mass,
        "_active_set_signature",
        lambda **kwargs: (int(kwargs["power_mass_scale"] > 1.0),),
    )

    diagnostic = model.uncertainty_for(driver=1, compound="MEDIUM", lap=20)

    assert diagnostic.method == "sigma_points"
    assert diagnostic.active_set_stable is False
    assert diagnostic.sigma_point_variance_s2 is not None
    assert diagnostic.parameter_variance_s2 == diagnostic.sigma_point_variance_s2


def test_uncertainty_variance_disagreement_selects_sigma_points(
    tmp_path: Path,
    long_synthetic_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from f1si.pace.point_mass import PointMassPaceModel

    model = _uncertain_model(tmp_path, long_synthetic_db, covariance=0.04)

    def nonlinear_mean(
        self: Any,
        *,
        scenario: Any,
        mass_kg: float,
        grip_mu: float,
        power_mass_scale: float,
    ) -> float:
        del self, scenario, mass_kg, grip_mu
        delta = power_mass_scale - 1.0
        return 100.0 + 2.0 * delta + 50.0 * delta**3

    monkeypatch.setattr(PointMassPaceModel, "_lap_mean", nonlinear_mean)
    diagnostic = model.uncertainty_for(driver=1, compound="MEDIUM", lap=20)

    assert diagnostic.active_set_stable is True
    assert diagnostic.method == "sigma_points"
    assert diagnostic.relative_variance_error is not None
    assert diagnostic.relative_variance_error > 0.1


def test_uncertainty_bound_shrink_preserves_symmetry_and_fails_at_zero_radius(
    tmp_path: Path, long_synthetic_db: Path
) -> None:
    upper = 1_000_000.0 / 650_000.0
    shrunken = _uncertain_model(
        tmp_path,
        long_synthetic_db,
        scale=upper - 0.001,
        covariance=0.04,
        residual_variance_s2=None,
    )
    diagnostic = shrunken.uncertainty_for(driver=1, compound="MEDIUM", lap=20)

    assert diagnostic.method == "sigma_points"
    assert diagnostic.feasible_radius_scale is not None
    assert 0.0 < diagnostic.feasible_radius_scale < 1.0
    assert diagnostic.residual_variance_s2 is None
    zero_radius = _uncertain_model(
        tmp_path,
        long_synthetic_db,
        scale=upper,
        covariance=0.04,
    )
    with pytest.raises(ValueError, match="no feasible symmetric"):
        zero_radius.uncertainty_for(driver=1, compound="MEDIUM", lap=20)


def test_uncertainty_nonfinite_finite_difference_uses_finite_sigma_points(
    tmp_path: Path,
    long_synthetic_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from f1si.pace.point_mass import PointMassPaceModel

    model = _uncertain_model(tmp_path, long_synthetic_db)

    def partially_nonfinite_mean(
        self: Any,
        *,
        scenario: Any,
        mass_kg: float,
        grip_mu: float,
        power_mass_scale: float,
    ) -> float:
        del self, scenario, mass_kg, grip_mu
        delta = power_mass_scale - 1.0
        if 0.0 < abs(delta) < 0.001:
            return math.nan
        return 100.0 + 2.0 * delta

    monkeypatch.setattr(PointMassPaceModel, "_lap_mean", partially_nonfinite_mean)
    diagnostic = model.uncertainty_for(driver=1, compound="MEDIUM", lap=20)

    assert diagnostic.method == "sigma_points"
    assert diagnostic.first_order_variance_s2 is None
    assert diagnostic.sigma_point_variance_s2 is not None
    assert diagnostic.parameter_variance_s2 == diagnostic.sigma_point_variance_s2


def test_parameters_reject_residual_variance_without_supported_rows(
    tmp_path: Path, long_synthetic_db: Path
) -> None:
    model = _model(tmp_path, long_synthetic_db)

    with pytest.raises(ValueError, match="30 laps from three training races"):
        replace(model.parameters, residual_variance_s2=0.02)


def test_out_of_sample_physics_input_is_rejected(tmp_path: Path, long_synthetic_db: Path) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.data.physics_input import PhysicsInput
    from f1si.pace.point_mass import PointMassPaceModel

    model = _model(tmp_path, long_synthetic_db)
    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10))
    locked = replace(snapshot, race=replace(snapshot.race, out_of_sample=True))
    prepared = PhysicsInput(locked, model.geometry.reference, model.parameters.parameter_ref, {})
    with pytest.raises(ValueError, match="out-of-sample"):
        PointMassPaceModel(model.geometry, prepared, model.parameters, model.compound_grip)


@pytest.mark.parametrize(
    ("field", "lower", "upper"),
    [
        ("mass_kg", 798.0, 1000.0),
        ("fuel_kg", 0.0, 150.0),
        ("fuel_burn_kg_per_lap", 0.5, 3.0),
        ("power_w", 500_000.0, 1_000_000.0),
        ("drag_area_m2", 0.7, 2.5),
        ("downforce_area_m2", 5.289795918367346, 31.73877551020408),
        ("grip_mu", 0.8, 3.0),
        ("time_sd_s", 0.01, 5.0),
    ],
)
def test_physical_scenario_bounds_are_inclusive_and_next_float_fails(
    field: str, lower: float, upper: float
) -> None:
    from dataclasses import replace

    from f1si.pace.point_mass import PointMassVehicleScenario

    base = PointMassVehicleScenario(1, "2023", 850, 50, 1.7, 650_000, 1.4, 10, 1.7, 0.15)
    for endpoint in (lower, upper):
        cast(Any, replace)(base, **{field: endpoint})
    with pytest.raises(ValueError, match=field):
        cast(Any, replace)(base, **{field: float(np.nextafter(lower, -math.inf))})
    with pytest.raises(ValueError, match=field):
        cast(Any, replace)(base, **{field: float(np.nextafter(upper, math.inf))})
