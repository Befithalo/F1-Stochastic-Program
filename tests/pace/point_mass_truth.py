"""Independent closed-form synthetic truth for uniform circular point-mass laps.

This test-side generator intentionally imports no production pace-model or fit code. A uniform
circle has one curvature and one segment speed, so the closed-lap solution is the smaller of the
power/drag terminal speed and the grip/downforce corner cap.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

_G_M_S2 = 9.80665
_AIR_DENSITY_KG_M3 = 1.225


@dataclass(frozen=True)
class PointMassTruthLap:
    """One independently generated target row, with values represented in SI units."""

    race_id: str
    driver_number: int
    lap_number: int
    lap_time_s: float


@dataclass(frozen=True)
class PointMassTruth:
    """Synthetic truth metadata and targets needed to audit a recovery test."""

    seed: int
    effective_power_mass_scale: float
    fit_bounds: tuple[float, float]
    noise_sd_s: float
    sample_size: int
    radius_m: float
    segment_count: int
    identifiable_terms: tuple[str, ...]
    units: tuple[tuple[str, str], ...]
    assumptions: tuple[tuple[str, float], ...]
    laps: tuple[PointMassTruthLap, ...]


def _closed_lap_time_s(
    *,
    radius_m: float,
    segment_count: int,
    mass_kg: float,
    power_w: float,
    drag_area_m2: float,
    downforce_area_m2: float,
    grip_mu: float,
    effective_power_mass_scale: float,
) -> float:
    """Solve a constant-curvature lap from force balance, without production helpers."""
    curvature_inv_m = 1.0 / radius_m
    corner_denominator_kg_m = (
        mass_kg * curvature_inv_m - grip_mu * 0.5 * _AIR_DENSITY_KG_M3 * downforce_area_m2
    )
    corner_speed_m_s = (
        math.sqrt(grip_mu * mass_kg * _G_M_S2 / corner_denominator_kg_m)
        if corner_denominator_kg_m > 0
        else math.inf
    )
    terminal_speed_m_s = (
        2.0 * power_w * effective_power_mass_scale / (_AIR_DENSITY_KG_M3 * drag_area_m2)
    ) ** (1.0 / 3.0)
    segment_length_m = 2.0 * radius_m * math.sin(math.pi / segment_count)
    closed_distance_m = segment_count * segment_length_m
    return float(closed_distance_m / min(corner_speed_m_s, terminal_speed_m_s))


def generate_point_mass_truth(
    *,
    race_laps: Mapping[str, Sequence[int]],
    effective_power_mass_scale: float = 1.08,
    fit_bounds: tuple[float, float] = (1.0, 1.15),
    radius_m: float = 120.0,
    segment_count: int = 64,
    mass_kg: float = 850.0,
    fuel_kg: float = 50.0,
    fuel_burn_kg_per_lap: float = 1.7,
    power_w: float = 650_000.0,
    drag_area_m2: float = 1.4,
    downforce_area_m2: float = 5.3,
    grip_mu: float = 1.7,
    seed: int = 10_142,
    noise_sd_s: float = 0.0005,
) -> PointMassTruth:
    """Generate seeded SI lap targets on a uniform circle from a separate force balance."""
    numeric = (
        effective_power_mass_scale,
        radius_m,
        mass_kg,
        fuel_kg,
        fuel_burn_kg_per_lap,
        power_w,
        drag_area_m2,
        downforce_area_m2,
        grip_mu,
        noise_sd_s,
    )
    if not all(math.isfinite(float(value)) for value in numeric):
        raise ValueError("synthetic truth assumptions must be finite float64-compatible values")
    if (
        effective_power_mass_scale <= 0
        or radius_m <= 0
        or segment_count < 8
        or mass_kg <= 0
        or fuel_kg < 0
        or fuel_burn_kg_per_lap < 0
        or power_w <= 0
        or drag_area_m2 <= 0
        or downforce_area_m2 < 0
        or grip_mu <= 0
        or noise_sd_s < 0
    ):
        raise ValueError("synthetic truth needs positive physical scales and nonnegative noise")
    if (
        len(fit_bounds) != 2
        or not all(math.isfinite(float(value)) for value in fit_bounds)
        or fit_bounds[0] <= 0
        or fit_bounds[0] >= fit_bounds[1]
        or not fit_bounds[0] <= effective_power_mass_scale <= fit_bounds[1]
    ):
        raise ValueError("fit bounds must be finite, ordered, positive, and contain the truth")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    row_keys = tuple(
        (race_id, int(lap_number))
        for race_id, lap_numbers in sorted(race_laps.items())
        for lap_number in sorted(lap_numbers)
    )
    if any(not race_id or lap_number < 2 for race_id, lap_number in row_keys):
        raise ValueError("synthetic rows need race identifiers and lap numbers >= 2")
    noise = np.random.default_rng(seed).normal(0.0, noise_sd_s, size=len(row_keys))
    generated: list[PointMassTruthLap] = []
    for (race_id, lap_number), residual in zip(row_keys, noise, strict=True):
        fuel_at_lap_kg = max(0.0, fuel_kg - fuel_burn_kg_per_lap * (lap_number - 1))
        lap_mass_kg = mass_kg + fuel_at_lap_kg
        mean_s = _closed_lap_time_s(
            radius_m=radius_m,
            segment_count=segment_count,
            mass_kg=lap_mass_kg,
            power_w=power_w,
            drag_area_m2=drag_area_m2,
            downforce_area_m2=downforce_area_m2,
            grip_mu=grip_mu,
            effective_power_mass_scale=effective_power_mass_scale,
        )
        generated.append(
            PointMassTruthLap(
                race_id=race_id,
                driver_number=1,
                lap_number=lap_number,
                lap_time_s=float(np.float64(mean_s + residual)),
            )
        )

    terms = ("effective_tractive_power_to_mass_scale",) if len(row_keys) > len(race_laps) else ()
    assumptions = (
        ("mass_kg", float(mass_kg)),
        ("fuel_kg", float(fuel_kg)),
        ("fuel_burn_kg_per_lap", float(fuel_burn_kg_per_lap)),
        ("power_w", float(power_w)),
        ("drag_area_m2", float(drag_area_m2)),
        ("downforce_area_m2", float(downforce_area_m2)),
        ("grip_mu", float(grip_mu)),
    )
    return PointMassTruth(
        seed=seed,
        effective_power_mass_scale=float(effective_power_mass_scale),
        fit_bounds=(float(fit_bounds[0]), float(fit_bounds[1])),
        noise_sd_s=float(noise_sd_s),
        sample_size=len(generated),
        radius_m=float(radius_m),
        segment_count=segment_count,
        identifiable_terms=terms,
        units=(
            ("radius_m", "m"),
            ("mass_kg", "kg"),
            ("power_w", "W"),
            ("lap_time_s", "s"),
            ("curvature_inv_m", "1/m"),
        ),
        assumptions=assumptions,
        laps=tuple(generated),
    )


def recovery_within_tolerance(
    estimate: float, truth: float, *, relative_tolerance: float = 0.05
) -> bool:
    """Accept an inclusive relative recovery tolerance for a positive scalar truth."""
    if (
        not math.isfinite(float(estimate))
        or not math.isfinite(float(truth))
        or truth <= 0
        or not math.isfinite(float(relative_tolerance))
        or relative_tolerance < 0
    ):
        return False
    relative_error = abs(float(estimate) - float(truth)) / float(truth)
    return relative_error <= relative_tolerance or math.isclose(
        relative_error,
        relative_tolerance,
        rel_tol=0.0,
        abs_tol=1e-12,
    )
