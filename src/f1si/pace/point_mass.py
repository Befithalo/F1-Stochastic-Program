"""Deterministic quasi-static point-mass lap model over prepared geometry (DEC-140/141).

The model is intentionally reduced order: speed is solved on a closed spatial grid from
curvature, drive power, drag, downforce, mass and combined tire grip. It does not claim that
unobserved car or tire values are measured.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

import numpy as np
from numpy.typing import NDArray

from f1si.data.physics_input import PhysicsInput, VersionedArtifactRef
from f1si.geometry.profile import GeometryProfile

_G: Final = 9.80665
_RHO: Final = 1.225
_V_REF: Final = 200.0 / 3.6
_SPEED_TOL: Final = 1e-5
_MAX_PASSES: Final = 1000
_BOUNDS: Final = {
    "mass_kg": (798.0, 1000.0),
    "fuel_kg": (0.0, 150.0),
    "fuel_burn_kg_per_lap": (0.5, 3.0),
    "power_w": (500_000.0, 1_000_000.0),
    "drag_area_m2": (0.7, 2.5),
    "downforce_area_m2": (2.0 * 10_000.0 / (_RHO * _V_REF**2), 2.0 * 60_000.0 / (_RHO * _V_REF**2)),
    "grip_mu": (0.8, 3.0),
    "time_sd_s": (0.01, 5.0),
}


class PointMassConvergenceError(RuntimeError):
    """Raised when the cyclic speed envelope does not converge within its fixed work bound."""


@dataclass(frozen=True)
class PointMassVehicleScenario:
    """Explicit driver-level vehicle assumptions in SI units, bounded to declared M2 ranges."""

    driver: int
    season: str
    mass_kg: float
    fuel_kg: float
    fuel_burn_kg_per_lap: float
    power_w: float
    drag_area_m2: float
    downforce_area_m2: float
    grip_mu: float
    time_sd_s: float = 0.15

    def __post_init__(self) -> None:
        if isinstance(self.driver, bool) or self.driver < 1:
            raise ValueError("driver must be a positive integer")
        if not self.season.isdigit() or self.season not in {"2023", "2024", "2025"}:
            raise ValueError("season must be one of the declared 2023-2025 seasons")
        for name, (lower, upper) in _BOUNDS.items():
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < lower or value > upper:
                raise ValueError(
                    f"{name} must be finite and within inclusive bounds [{lower}, {upper}]"
                )
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class PointMassParameters:
    """Immutable scenario set tied to one versioned parameter-register artifact."""

    parameter_ref: VersionedArtifactRef
    scenarios: tuple[PointMassVehicleScenario, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenarios", tuple(self.scenarios))
        drivers = [item.driver for item in self.scenarios]
        if not drivers or len(drivers) != len(set(drivers)):
            raise ValueError("scenarios must include unique driver identifiers")

    def for_driver(self, driver: int) -> PointMassVehicleScenario:
        for scenario in self.scenarios:
            if scenario.driver == driver:
                return scenario
        raise ValueError(f"unknown driver {driver}")


def _geometry_grid(geometry: GeometryProfile) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    x = np.asarray(geometry.x_m, dtype=np.float64)
    y = np.asarray(geometry.y_m, dtype=np.float64)
    if (
        x.ndim != 1
        or y.shape != x.shape
        or len(x) < 4
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
    ):
        raise ValueError("geometry must contain at least four finite planar points")
    # Loader profiles may include a repeated closure point; this is the same seam, not a segment.
    if math.hypot(float(x[-1] - x[0]), float(y[-1] - y[0])) <= 1e-9:
        x, y = x[:-1], y[:-1]
    dx = np.roll(x, -1) - x
    dy = np.roll(y, -1) - y
    ds = np.hypot(dx, dy).astype(np.float64)
    if np.any(ds <= 0) or not np.isfinite(ds).all():
        raise ValueError("geometry contains zero-length or non-finite spatial intervals")
    # Signed circumcircle curvature at each vertex; the absolute value is used for grip demand.
    ax, ay = np.roll(x, 1), np.roll(y, 1)
    bx, by = x, y
    cx, cy = np.roll(x, -1), np.roll(y, -1)
    ab = np.hypot(bx - ax, by - ay)
    bc = np.hypot(cx - bx, cy - by)
    ca = np.hypot(ax - cx, ay - cy)
    cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    curvature = np.divide(
        2.0 * cross, ab * bc * ca, out=np.zeros_like(ds), where=(ab * bc * ca) > 0
    )
    if not np.isfinite(curvature).all():
        raise ValueError("geometry curvature must be finite")
    return ds, np.abs(curvature)


def _terminal_speed(power_w: float, drag_area_m2: float) -> float:
    """Solve power = aerodynamic drag * speed for a finite straight terminal speed."""
    return float((2.0 * power_w / (_RHO * drag_area_m2)) ** (1.0 / 3.0))


def _corner_caps(
    curvature: NDArray[np.float64], mass_kg: float, downforce_area_m2: float, grip_mu: float
) -> NDArray[np.float64]:
    """Solve m*v²*k = mu*(m*g + rho*A*v²/2), capped by finite straight speed."""
    den = mass_kg * curvature - grip_mu * 0.5 * _RHO * downforce_area_m2
    numerator = grip_mu * mass_kg * _G
    caps = np.full(curvature.shape, _terminal_speed(1_000_000.0, 0.7), dtype=np.float64)
    limited = den > 0
    caps[limited] = np.sqrt(numerator / den[limited])
    return caps


def _solve_speed_envelope(
    *,
    ds: NDArray[np.float64],
    curvature: NDArray[np.float64],
    mass_kg: float,
    power_w: float,
    drag_area_m2: float,
    downforce_area_m2: float,
    grip_mu: float,
    max_passes: int = _MAX_PASSES,
    tolerance_m_s: float = _SPEED_TOL,
) -> tuple[NDArray[np.float64], int]:
    """Close cyclic forward acceleration and backward braking reachability to DEC-141."""
    if (
        ds.ndim != 1
        or curvature.shape != ds.shape
        or not len(ds)
        or not np.isfinite(ds).all()
        or not np.isfinite(curvature).all()
        or np.any(ds <= 0)
    ):
        raise ValueError(
            "spatial intervals and curvature must be finite, positive-length matching arrays"
        )
    if max_passes < 1 or tolerance_m_s <= 0:
        raise ValueError("solver limits must be positive")
    terminal = _terminal_speed(power_w, drag_area_m2)
    speed = np.minimum(_corner_caps(curvature, mass_kg, downforce_area_m2, grip_mu), terminal)
    for pass_index in range(1, max_passes + 1):
        before = speed.copy()
        for i in range(len(speed)):
            j = (i + 1) % len(speed)
            v = max(float(speed[i]), 1.0)
            lateral = mass_kg * v * v * curvature[i]
            normal = mass_kg * _G + 0.5 * _RHO * downforce_area_m2 * v * v
            remaining = math.sqrt(max(0.0, (grip_mu * normal) ** 2 - lateral**2))
            drag = 0.5 * _RHO * drag_area_m2 * v * v
            drive_force = min(max(0.0, power_w / v - drag), remaining)
            accel = drive_force / mass_kg
            speed[j] = min(speed[j], math.sqrt(max(0.0, v * v + 2.0 * accel * ds[i])))
        for i in range(len(speed) - 1, -1, -1):
            j = (i + 1) % len(speed)
            v = max(float(speed[j]), 1.0)
            lateral = mass_kg * v * v * curvature[j]
            normal = mass_kg * _G + 0.5 * _RHO * downforce_area_m2 * v * v
            remaining = math.sqrt(max(0.0, (grip_mu * normal) ** 2 - lateral**2))
            decel = (remaining + 0.5 * _RHO * drag_area_m2 * v * v) / mass_kg
            speed[i] = min(speed[i], math.sqrt(max(0.0, v * v + 2.0 * decel * ds[i])))
        if not np.isfinite(speed).all() or np.any(speed <= 0):
            raise ValueError("solver produced a nonpositive or non-finite segment speed")
        if float(np.max(np.abs(speed - before))) <= tolerance_m_s:
            return speed.astype(np.float64), pass_index
    raise PointMassConvergenceError(
        f"cyclic speed envelope did not converge in {max_passes} passes"
    )


def _lap_time_s(ds: NDArray[np.float64], speed: NDArray[np.float64]) -> float:
    """Integrate segment travel time using the DEC-141 reciprocal-speed trapezoid."""
    if (
        ds.shape != speed.shape
        or np.any(ds <= 0)
        or np.any(speed <= 0)
        or not np.isfinite(ds).all()
        or not np.isfinite(speed).all()
    ):
        raise ValueError("segment distance and speed must be finite, positive, and shape-matched")
    result = float(np.sum(ds * (1.0 / speed + 1.0 / np.roll(speed, -1)) / 2.0, dtype=np.float64))
    if not math.isfinite(result) or result <= 0:
        raise ValueError("integrated lap time must be finite and positive")
    return result


def _refined_lap_time_s(
    *,
    ds: NDArray[np.float64],
    curvature: NDArray[np.float64],
    mass_kg: float,
    power_w: float,
    drag_area_m2: float,
    downforce_area_m2: float,
    grip_mu: float,
) -> tuple[float, float]:
    """Compare the prepared grid with a midpoint-bisected grid using linear curvature only."""
    base_speed, _ = _solve_speed_envelope(
        ds=ds,
        curvature=curvature,
        mass_kg=mass_kg,
        power_w=power_w,
        drag_area_m2=drag_area_m2,
        downforce_area_m2=downforce_area_m2,
        grip_mu=grip_mu,
    )
    half = ds / 2.0
    midpoint_curvature = (curvature + np.roll(curvature, -1)) / 2.0
    refined_ds = np.repeat(half, 2).astype(np.float64)
    refined_curvature = np.empty(2 * len(curvature), dtype=np.float64)
    refined_curvature[0::2] = curvature
    refined_curvature[1::2] = midpoint_curvature
    fine_speed, _ = _solve_speed_envelope(
        ds=refined_ds,
        curvature=refined_curvature,
        mass_kg=mass_kg,
        power_w=power_w,
        drag_area_m2=drag_area_m2,
        downforce_area_m2=downforce_area_m2,
        grip_mu=grip_mu,
    )
    return _lap_time_s(ds, base_speed), _lap_time_s(refined_ds, fine_speed)


@dataclass(frozen=True, init=False)
class PointMassPaceModel:
    """Prepared immutable geometry, cutoff input, scenarios, and compound grip mapping."""

    geometry: GeometryProfile
    physics_input: PhysicsInput
    parameters: PointMassParameters
    compound_grip: Mapping[str, float]
    _ds: NDArray[np.float64]
    _curvature: NDArray[np.float64]

    def __init__(
        self,
        geometry: GeometryProfile,
        physics_input: PhysicsInput,
        parameters: PointMassParameters,
        compound_grip: dict[str, float],
    ) -> None:
        if not isinstance(geometry, GeometryProfile) or not isinstance(physics_input, PhysicsInput):
            raise TypeError("model requires validated GeometryProfile and PhysicsInput artifacts")
        if not isinstance(parameters, PointMassParameters):
            raise TypeError("parameters must be a validated PointMassParameters artifact")
        if geometry.reference != physics_input.geometry_ref:
            raise ValueError("geometry reference does not match PhysicsInput geometry reference")
        if parameters.parameter_ref != physics_input.parameter_ref:
            raise ValueError("parameter reference does not match PhysicsInput parameter reference")
        if physics_input.race.out_of_sample:
            raise ValueError("out-of-sample PhysicsInput cannot construct a point-mass model")
        if set(compound_grip) != {"SOFT", "MEDIUM", "HARD"}:
            raise ValueError("compound grip must explicitly declare SOFT, MEDIUM, and HARD")
        grips = dict(compound_grip)
        for compound, value in grips.items():
            if not math.isfinite(float(value)) or not 0 < float(value) <= 2:
                raise ValueError(f"{compound} compound grip multiplier must be finite in (0, 2]")
        ds, curvature = _geometry_grid(geometry)
        object.__setattr__(self, "geometry", geometry)
        object.__setattr__(self, "physics_input", physics_input)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "compound_grip", MappingProxyType(grips))
        ds.setflags(write=False)
        curvature.setflags(write=False)
        object.__setattr__(self, "_ds", ds)
        object.__setattr__(self, "_curvature", curvature)

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Return deterministic mean and declared scenario uncertainty in exact input order."""
        arrays = (driver, compound, tire_age, lap)
        if any(not isinstance(item, np.ndarray) or item.ndim != 1 for item in arrays):
            raise ValueError("predict inputs must be one-dimensional NumPy arrays")
        if len({item.shape for item in arrays}) != 1:
            raise ValueError("predict inputs must have identical shapes")
        if driver.dtype != np.int64 or tire_age.dtype != np.int64 or lap.dtype != np.int64:
            raise ValueError("driver, tire_age, and lap must use int64")
        if len(driver) == 0:
            empty = np.empty(0, dtype=np.float64)
            return empty, empty.copy()
        if np.any(tire_age < 0) or np.any(lap < 1):
            raise ValueError("tire age must be nonnegative and lap must be 1-based")
        mean = np.empty(len(driver), dtype=np.float64)
        sd = np.empty(len(driver), dtype=np.float64)
        for index, (driver_id, compound_name, age, lap_number) in enumerate(
            zip(driver, compound, tire_age, lap, strict=True)
        ):
            scenario = self.parameters.for_driver(int(driver_id))
            if str(compound_name) not in self.compound_grip:
                raise ValueError(f"unknown compound {compound_name!r}")
            fuel = max(
                0.0, scenario.fuel_kg - scenario.fuel_burn_kg_per_lap * (int(lap_number) - 1)
            )
            mass = scenario.mass_kg + fuel
            grip = scenario.grip_mu * self.compound_grip[str(compound_name)]
            speed, _ = _solve_speed_envelope(
                ds=self._ds,
                curvature=self._curvature,
                mass_kg=mass,
                power_w=scenario.power_w,
                drag_area_m2=scenario.drag_area_m2,
                downforce_area_m2=scenario.downforce_area_m2,
                grip_mu=min(3.0, grip),
            )
            mean[index] = _lap_time_s(self._ds, speed)
            # Tire age has no fitted wear coefficient until the tire-state phase.
            mean[index] += 0.0 * float(age)
            sd[index] = scenario.time_sd_s
        return mean, sd

    def validate_grid_refinement(self, scenario: PointMassVehicleScenario) -> float:
        """Return relative one-bisection lap-time change, enforcing DEC-141's 0.1% limit."""
        base, refined = _refined_lap_time_s(
            ds=self._ds,
            curvature=self._curvature,
            mass_kg=scenario.mass_kg + scenario.fuel_kg,
            power_w=scenario.power_w,
            drag_area_m2=scenario.drag_area_m2,
            downforce_area_m2=scenario.downforce_area_m2,
            grip_mu=scenario.grip_mu,
        )
        relative = abs(refined - base) / base
        if relative > 0.001:
            raise ValueError(
                f"track grid refinement changes lap time by {relative:.3%}, above DEC-141's 0.1%"
            )
        return relative
