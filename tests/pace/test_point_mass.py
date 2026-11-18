"""Production-path checks for the deterministic geometry-backed PaceModel."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest


def _profile(tmp_path: Path):
    from f1si.geometry.profile import load_profile
    from tests.geometry.test_profile import _write_profile

    return load_profile(_write_profile(tmp_path), asset_root=tmp_path)


def _model(tmp_path: Path, db_path: Path):
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


def test_solver_force_envelope_and_segment_integration() -> None:
    from f1si.pace.point_mass import _lap_time_s, _solve_speed_envelope

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
    assert _lap_time_s(ds, speed) == pytest.approx(
        float(np.sum(ds * (1 / speed + 1 / np.roll(speed, -1)) / 2))
    )


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
    scenario = PointMassVehicleScenario(1, "2023", 850, 50, 1.7, 650000, 1.4, 10, 1.7)
    with pytest.raises(ValueError, match="parameter reference"):
        PointMassPaceModel(
            profile,
            prepared,
            PointMassParameters(VersionedArtifactRef("other", "1", "c" * 64), (scenario,)),
            {"SOFT": 1, "MEDIUM": 1, "HARD": 1},
        )


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

    base = PointMassVehicleScenario(1, "2023", 850, 50, 1.7, 650_000, 1.4, 10, 1.7)
    for endpoint in (lower, upper):
        replace(base, **{field: endpoint})
    with pytest.raises(ValueError, match=field):
        replace(base, **{field: float(np.nextafter(lower, -math.inf))})
    with pytest.raises(ValueError, match=field):
        replace(base, **{field: float(np.nextafter(upper, math.inf))})
