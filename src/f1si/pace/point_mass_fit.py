"""Cutoff-safe fit of the single effective point-mass drive scale (DEC-140/141)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any, Final

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.optimize import minimize_scalar

from f1si.data.asof import RaceEnd
from f1si.interfaces import DRY_COMPOUNDS
from f1si.laps import slow_status
from f1si.pace.point_mass import PointMassPaceModel, PointMassParameters

_CANDIDATE_TERM: Final = "effective_tractive_power_to_mass_scale"
_ABSOLUTE_ASSUMPTIONS: Final = (
    "mass_kg",
    "fuel_kg",
    "fuel_burn_kg_per_lap",
    "power_w",
    "drag_area_m2",
    "downforce_area_m2",
    "grip_mu",
)
_FIT_SEASONS: Final = frozenset({2023, 2024, 2025})
_MIN_RESIDUAL_ROWS: Final = 30
_MIN_RESIDUAL_RACES: Final = 3
_COND_LIMIT: Final = 1e6
_OPT_XTOL: Final = 1e-8


@dataclass(frozen=True)
class _FitRow:
    model: PointMassPaceModel
    race_id: str
    season: int
    cutoff_s: float | None
    driver: int
    lap: int
    compound: str
    tire_age: float
    observed_s: float
    group: tuple[str, int]


@dataclass(frozen=True)
class PointMassFitReport:
    """Immutable fit result; only the declared dimensionless effective scale may be fitted."""

    status: str
    candidate_term: str
    unit: str
    declared_assumption: float
    candidate_scale: float | None
    bounds: tuple[float, float]
    covariance: float | None
    residual_variance_s2: float | None
    residual_support_available: bool
    residual_support_laps: int
    residual_support_races: int
    sensitivity_rank: int
    sensitivity_condition: float | None
    n_races: int
    n_laps: int
    race_ids: tuple[str, ...]
    cutoffs: tuple[tuple[str, float | None], ...]
    cutoff_policy: str
    absolute_assumptions: tuple[str, ...] = _ABSOLUTE_ASSUMPTIONS
    nuisance_offset_rule: str = "residuals centered by race and driver; offsets are not reported"
    unidentifiable_reason: str | None = None
    boundary_value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a detached, JSON-compatible report with stable scalar and tuple values."""
        return asdict(self)

    def bind(self, parameters: PointMassParameters) -> PointMassParameters:
        """Return parameters carrying this fit without changing any absolute scenario values."""
        scale = (
            self.candidate_scale
            if self.status == "identified" and self.candidate_scale is not None
            else self.declared_assumption
        )
        return replace(
            parameters,
            effective_power_mass_scale=scale,
            power_mass_scale_variance=self.covariance,
            residual_variance_s2=(
                self.residual_variance_s2 if self.residual_support_available else None
            ),
        )


def _finite_float(value: Any) -> float | None:
    if value is None or value is pd.NA:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _empty_report(
    *,
    reason: str,
    declared_assumption: float,
    bounds: tuple[float, float],
    race_ids: tuple[str, ...] = (),
    cutoffs: tuple[tuple[str, float | None], ...] = (),
    n_laps: int = 0,
    sensitivity_rank: int = 0,
    sensitivity_condition: float | None = None,
) -> PointMassFitReport:
    return PointMassFitReport(
        status="unidentifiable",
        candidate_term=_CANDIDATE_TERM,
        unit="dimensionless",
        declared_assumption=declared_assumption,
        candidate_scale=None,
        bounds=bounds,
        covariance=None,
        residual_variance_s2=None,
        residual_support_available=False,
        residual_support_laps=0,
        residual_support_races=0,
        sensitivity_rank=sensitivity_rank,
        sensitivity_condition=sensitivity_condition,
        n_races=len(race_ids),
        n_laps=n_laps,
        race_ids=race_ids,
        cutoffs=cutoffs,
        cutoff_policy="visible_at_s <= supplied cutoff_s; equality is included",
        unidentifiable_reason=reason,
    )


def _eligible_rows(
    model: PointMassPaceModel,
) -> tuple[list[_FitRow], str | None]:
    physics = model.physics_input
    race = physics.race
    if race.out_of_sample:
        return [], f"race {race.race_id} is marked out-of-sample"
    if race.season not in _FIT_SEASONS:
        return [], f"race {race.race_id} is outside the 2023-2025 training range"
    if physics.snapshot.at.race_id != race.race_id:
        return [], f"race identity does not match the prepared as-of input for {race.race_id}"
    if physics.cutoff_s is None and not isinstance(physics.at.lap, RaceEnd):
        return [], f"race {race.race_id} has no usable cutoff"

    laps = physics.laps
    required = {
        "visible_at_s",
        "driver_number",
        "lap_number",
        "lap_time_s",
        "tyre_life",
        "compound",
        "stint",
        "is_pit_in_lap",
        "is_pit_out_lap",
        "track_status",
    }
    missing = required.difference(laps.columns)
    if missing:
        return [], f"race {race.race_id} is missing lap evidence: {', '.join(sorted(missing))}"

    rows: list[_FitRow] = []
    for record in laps.to_dict(orient="records"):
        visible_at = _finite_float(record.get("visible_at_s"))
        if visible_at is None:
            continue
        cutoff = physics.cutoff_s
        if cutoff is not None and visible_at > cutoff:
            continue
        lap_time = _finite_float(record.get("lap_time_s"))
        age = _finite_float(record.get("tyre_life"))
        stint = _finite_float(record.get("stint"))
        driver_value = _finite_float(record.get("driver_number"))
        lap_value = _finite_float(record.get("lap_number"))
        compound_value = record.get("compound")
        compound = compound_value.upper() if isinstance(compound_value, str) else ""
        if (
            lap_time is None
            or lap_time <= 0
            or age is None
            or age < 0
            or stint is None
            or driver_value is None
            or not driver_value.is_integer()
            or lap_value is None
            or not lap_value.is_integer()
            or lap_value < 2
            or bool(record.get("is_pit_in_lap"))
            or bool(record.get("is_pit_out_lap"))
            or slow_status(record.get("track_status"))
            or compound not in DRY_COMPOUNDS
        ):
            continue
        driver, lap_no = int(driver_value), int(lap_value)
        try:
            model.parameters.for_driver(driver)
        except ValueError:
            continue
        rows.append(
            _FitRow(
                model=model,
                race_id=race.race_id,
                season=race.season,
                cutoff_s=cutoff,
                driver=driver,
                lap=lap_no,
                compound=compound,
                tire_age=age,
                observed_s=lap_time,
                group=(race.race_id, driver),
            )
        )
    rows.sort(key=lambda row: (row.race_id, row.lap, row.driver))
    return rows, None


def _lap_prediction(row: _FitRow, scale: float) -> float:
    scenario = row.model.parameters.for_driver(row.driver)
    fuel = max(
        0.0,
        scenario.fuel_kg - scenario.fuel_burn_kg_per_lap * (row.lap - 1),
    )
    grip = min(
        3.0,
        scenario.grip_mu * row.model.compound_grip[row.compound],
    )
    return row.model._lap_mean(
        scenario=scenario,
        mass_kg=scenario.mass_kg + fuel,
        grip_mu=grip,
        power_mass_scale=scale,
    )


def _group_indices(rows: Sequence[_FitRow]) -> tuple[NDArray[np.int64], int]:
    groups = sorted({row.group for row in rows})
    index = {group: i for i, group in enumerate(groups)}
    return np.asarray([index[row.group] for row in rows], dtype=np.int64), len(groups)


def _center_by_group(
    values: NDArray[np.float64], group_index: NDArray[np.int64], n_groups: int
) -> NDArray[np.float64]:
    counts = np.bincount(group_index, minlength=n_groups).astype(np.float64)
    means = np.bincount(group_index, weights=values, minlength=n_groups) / counts
    return values - means[group_index]


def _sensitivity(
    rows: Sequence[_FitRow], scale: float, bounds: tuple[float, float]
) -> NDArray[np.float64]:
    low, high = bounds
    radius = min(1e-4 * max(1.0, abs(scale)), (high - low) / 4.0, scale - low, high - scale)
    if radius <= 0:
        scale = 0.5 * (low + high)
        radius = min(1e-4 * max(1.0, abs(scale)), (high - low) / 4.0)
    left = np.asarray([_lap_prediction(row, scale - radius) for row in rows], dtype=np.float64)
    right = np.asarray([_lap_prediction(row, scale + radius) for row in rows], dtype=np.float64)
    return (right - left) / (2.0 * radius)


def _design_diagnostics(
    sensitivity: NDArray[np.float64], group_index: NDArray[np.int64], n_groups: int
) -> tuple[int, float | None, NDArray[np.float64]]:
    n = len(sensitivity)
    intercepts = np.zeros((n, n_groups), dtype=np.float64)
    intercepts[np.arange(n), group_index] = 1.0
    design = np.column_stack((intercepts, sensitivity))
    norms = np.linalg.norm(design, axis=0)
    if np.any(norms == 0) or not np.isfinite(norms).all():
        return 0, None, np.empty(0, dtype=np.float64)
    design /= norms
    try:
        singular = np.linalg.svd(design, compute_uv=False)
    except np.linalg.LinAlgError:
        return 0, None, np.empty(0, dtype=np.float64)
    if not len(singular) or singular[0] <= 0:
        return 0, None, np.empty(0, dtype=np.float64)
    tolerance = singular[0] * max(design.shape) * np.finfo(np.float64).eps
    rank = int(np.sum(singular > tolerance))
    condition = float(singular[0] / singular[-1]) if rank == design.shape[1] else None
    return rank, condition, _center_by_group(sensitivity, group_index, n_groups)


def fit_effective_power_mass_scale(
    models: Sequence[PointMassPaceModel],
    *,
    declared_assumption: float = 1.0,
    bounds: tuple[float, float] = (0.75, 1.5),
) -> PointMassFitReport:
    """Fit only the common effective tractive-power-to-mass multiplier.

    Inputs are already prepared, immutable `PointMassPaceModel` objects. Eligibility uses only
    cutoff-visible clean lap fields; race/driver offsets are projected out as nuisance terms and
    are neither returned nor applied to prediction.
    """
    if (
        isinstance(declared_assumption, bool)
        or not math.isfinite(float(declared_assumption))
        or len(bounds) != 2
        or not all(math.isfinite(float(value)) for value in bounds)
        or bounds[0] <= 0
        or bounds[0] >= bounds[1]
    ):
        raise ValueError("declared assumption and ordered positive fit bounds must be finite")
    assumption = float(declared_assumption)
    fit_bounds = (float(bounds[0]), float(bounds[1]))
    if not fit_bounds[0] <= assumption <= fit_bounds[1]:
        raise ValueError("declared assumption must lie inside the inclusive fit bounds")
    inputs = tuple(models)
    if not inputs:
        return _empty_report(
            reason="no prepared PhysicsInput models were supplied",
            declared_assumption=assumption,
            bounds=fit_bounds,
        )
    if not all(isinstance(model, PointMassPaceModel) for model in inputs):
        raise TypeError("models must contain prepared PointMassPaceModel values")

    ordered_models = tuple(sorted(inputs, key=lambda model: model.physics_input.race.race_id))
    race_ids = tuple(model.physics_input.race.race_id for model in ordered_models)
    if len(race_ids) != len(set(race_ids)):
        return _empty_report(
            reason="each training race may appear only once",
            declared_assumption=assumption,
            bounds=fit_bounds,
            race_ids=tuple(sorted(set(race_ids))),
        )
    cutoffs = tuple(
        (model.physics_input.race.race_id, model.physics_input.cutoff_s) for model in ordered_models
    )
    for model in ordered_models:
        race = model.physics_input.race
        if race.out_of_sample or race.season not in _FIT_SEASONS:
            reason = (
                f"race {race.race_id} is out-of-sample"
                if race.out_of_sample
                else f"race {race.race_id} is outside the 2023-2025 training range"
            )
            return _empty_report(
                reason=reason,
                declared_assumption=assumption,
                bounds=fit_bounds,
                race_ids=race_ids,
                cutoffs=cutoffs,
            )
        if not math.isclose(
            model.parameters.effective_power_mass_scale, assumption, rel_tol=0.0, abs_tol=1e-12
        ):
            return _empty_report(
                reason="training models do not share the caller's declared scale assumption",
                declared_assumption=assumption,
                bounds=fit_bounds,
                race_ids=race_ids,
                cutoffs=cutoffs,
            )

    rows: list[_FitRow] = []
    for model in ordered_models:
        eligible, error = _eligible_rows(model)
        if error is not None:
            return _empty_report(
                reason=error,
                declared_assumption=assumption,
                bounds=fit_bounds,
                race_ids=race_ids,
                cutoffs=cutoffs,
            )
        rows.extend(eligible)
    rows.sort(key=lambda row: (row.race_id, row.lap, row.driver))
    eligible_races = tuple(sorted({row.race_id for row in rows}))
    if not rows:
        return _empty_report(
            reason="no cutoff-visible clean lap rows carry sufficient fit evidence",
            declared_assumption=assumption,
            bounds=fit_bounds,
            race_ids=eligible_races,
            cutoffs=cutoffs,
        )

    effective_low = max(
        500_000.0 / _scenario.power_w
        for model in ordered_models
        for _scenario in model.parameters.scenarios
    )
    effective_high = min(
        1_000_000.0 / _scenario.power_w
        for model in ordered_models
        for _scenario in model.parameters.scenarios
    )
    fit_bounds = (max(fit_bounds[0], effective_low), min(fit_bounds[1], effective_high))
    if fit_bounds[0] >= fit_bounds[1] or not fit_bounds[0] <= assumption <= fit_bounds[1]:
        return _empty_report(
            reason="fit bounds do not overlap the registered effective-power range",
            declared_assumption=assumption,
            bounds=fit_bounds,
            race_ids=eligible_races,
            cutoffs=cutoffs,
            n_laps=len(rows),
        )

    group_index, n_groups = _group_indices(rows)
    derivative = _sensitivity(rows, assumption, fit_bounds)
    rank, condition, _centered_derivative = _design_diagnostics(derivative, group_index, n_groups)
    design_columns = n_groups + 1
    if rank < design_columns or condition is None or condition > _COND_LIMIT:
        reason = (
            f"cutoff-visible sensitivity design is rank deficient ({rank}/{design_columns})"
            if rank < design_columns
            else f"sensitivity condition number exceeds {_COND_LIMIT:g}"
        )
        return _empty_report(
            reason=reason,
            declared_assumption=assumption,
            bounds=fit_bounds,
            race_ids=eligible_races,
            cutoffs=cutoffs,
            n_laps=len(rows),
            sensitivity_rank=rank,
            sensitivity_condition=condition,
        )

    observed = np.asarray([row.observed_s for row in rows], dtype=np.float64)

    def objective(scale: float) -> float:
        predicted = np.asarray([_lap_prediction(row, scale) for row in rows], dtype=np.float64)
        residual = _center_by_group(observed - predicted, group_index, n_groups)
        return float(np.dot(residual, residual))

    try:
        result = minimize_scalar(
            objective,
            method="bounded",
            bounds=fit_bounds,
            options={"xatol": _OPT_XTOL, "maxiter": 500},
        )
    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
        return _empty_report(
            reason=f"bounded scalar fit failed: {type(exc).__name__}",
            declared_assumption=assumption,
            bounds=fit_bounds,
            race_ids=eligible_races,
            cutoffs=cutoffs,
            n_laps=len(rows),
            sensitivity_rank=rank,
            sensitivity_condition=condition,
        )
    if (
        not result.success
        or not math.isfinite(float(result.fun))
        or not math.isfinite(float(result.x))
    ):
        return _empty_report(
            reason="bounded scalar fit did not converge to a finite result",
            declared_assumption=assumption,
            bounds=fit_bounds,
            race_ids=eligible_races,
            cutoffs=cutoffs,
            n_laps=len(rows),
            sensitivity_rank=rank,
            sensitivity_condition=condition,
        )

    low, high = fit_bounds
    low_loss, high_loss = objective(low), objective(high)
    endpoint_tol = max(1e-12, abs(float(result.fun)) * 1e-12)
    boundary_value = None
    if abs(float(result.x) - low) <= _OPT_XTOL * 2 or low_loss <= float(result.fun) + endpoint_tol:
        boundary_value = low
    elif (
        abs(float(result.x) - high) <= _OPT_XTOL * 2
        or high_loss <= float(result.fun) + endpoint_tol
    ):
        boundary_value = high
    if boundary_value is not None:
        return PointMassFitReport(
            status="boundary_limited",
            candidate_term=_CANDIDATE_TERM,
            unit="dimensionless",
            declared_assumption=assumption,
            candidate_scale=None,
            bounds=fit_bounds,
            covariance=None,
            residual_variance_s2=None,
            residual_support_available=False,
            residual_support_laps=0,
            residual_support_races=0,
            sensitivity_rank=rank,
            sensitivity_condition=condition,
            n_races=len(eligible_races),
            n_laps=len(rows),
            race_ids=eligible_races,
            cutoffs=cutoffs,
            cutoff_policy="visible_at_s <= supplied cutoff_s; equality is included",
            boundary_value=boundary_value,
        )

    fitted = float(result.x)
    residual = _center_by_group(
        observed - np.asarray([_lap_prediction(row, fitted) for row in rows], dtype=np.float64),
        group_index,
        n_groups,
    )
    dof = len(rows) - n_groups - 1
    support = (
        len(rows) >= _MIN_RESIDUAL_ROWS and len(eligible_races) >= _MIN_RESIDUAL_RACES and dof > 0
    )
    residual_variance = float(np.dot(residual, residual) / dof) if support else None
    fitted_derivative = _sensitivity(rows, fitted, fit_bounds)
    centered_fitted_derivative = _center_by_group(fitted_derivative, group_index, n_groups)
    information = float(np.dot(centered_fitted_derivative, centered_fitted_derivative))
    covariance = (
        residual_variance / information
        if residual_variance is not None and information > 0 and math.isfinite(information)
        else None
    )
    return PointMassFitReport(
        status="identified",
        candidate_term=_CANDIDATE_TERM,
        unit="dimensionless",
        declared_assumption=assumption,
        candidate_scale=fitted,
        bounds=fit_bounds,
        covariance=covariance,
        residual_variance_s2=residual_variance,
        residual_support_available=support,
        residual_support_laps=len(rows) if support else 0,
        residual_support_races=len(eligible_races) if support else 0,
        sensitivity_rank=rank,
        sensitivity_condition=condition,
        n_races=len(eligible_races),
        n_laps=len(rows),
        race_ids=eligible_races,
        cutoffs=cutoffs,
        cutoff_policy="visible_at_s <= supplied cutoff_s; equality is included",
    )
