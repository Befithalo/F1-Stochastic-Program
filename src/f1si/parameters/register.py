"""Versioned fitted-effective and hidden-assumption records for M2 physics (PAR-01)."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from f1si.pace.linear import LinearPaceFit

REGISTER_VERSION = "m2-physics-parameters-v1"
_SEASONS = ("2023", "2024", "2025")
_CONSTRAINT_STATES = {"constraint", "assumption", "observation"}


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class ParameterRecord:
    """One effective pace coefficient or one deliberately unmeasured physical quantity."""

    name: str
    classification: str
    value: float | None = None
    evidence: tuple[Mapping[str, str], ...] = ()
    season_bounds: Mapping[str, Any] | None = None
    uncertainty: Mapping[str, Any] | None = None
    sensitivity_status: str = "not_evaluated"
    constraint_status: str = "assumption"
    unit: str = "unspecified"
    description: str = ""
    register_version: str = REGISTER_VERSION
    metadata: Mapping[str, Any] = MappingProxyType({})

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("parameter name must be non-empty")
        if self.classification not in {"fitted_effective", "hidden_assumption"}:
            raise ValueError("classification must be fitted_effective or hidden_assumption")
        if self.constraint_status not in _CONSTRAINT_STATES:
            raise ValueError("constraint_status must be constraint, assumption, or observation")
        if not self.register_version.strip() or not self.sensitivity_status.strip():
            raise ValueError("register version and sensitivity status must be non-empty")
        if self.value is not None and not math.isfinite(float(self.value)):
            raise ValueError("parameter values must be finite when present")
        citations = tuple(_freeze(dict(item)) for item in self.evidence)
        bounds = None if self.season_bounds is None else _freeze(dict(self.season_bounds))
        uncertainty = None if self.uncertainty is None else _freeze(dict(self.uncertainty))
        metadata = _freeze(dict(self.metadata))
        if self.classification == "hidden_assumption":
            if self.value is not None:
                raise ValueError("hidden assumptions cannot carry a recovered point value")
            if not citations:
                raise ValueError("hidden assumptions require evidence references")
            if not bounds:
                raise ValueError("hidden assumptions require season-specific bounds")
            if uncertainty is None:
                raise ValueError("hidden assumptions require an uncertainty description")
            if self.constraint_status == "observation":
                raise ValueError("hidden assumptions cannot be classified as observations")
        elif self.value is None and self.sensitivity_status not in {
            "unidentified",
            "insufficient_evidence",
        }:
            raise ValueError("an unvalued effective term must be explicitly unidentified")
        object.__setattr__(self, "evidence", citations)
        object.__setattr__(self, "season_bounds", bounds)
        object.__setattr__(self, "uncertainty", uncertainty)
        object.__setattr__(self, "metadata", metadata)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible record without mutable aliases to registry internals."""
        return {
            "name": self.name,
            "classification": self.classification,
            "value": self.value,
            "unit": self.unit,
            "evidence": [_plain(reference) for reference in self.evidence],
            "season_bounds": _plain(self.season_bounds),
            "uncertainty": _plain(self.uncertainty),
            "sensitivity_status": self.sensitivity_status,
            "constraint_status": self.constraint_status,
            "description": self.description,
            "register_version": self.register_version,
            "metadata": _plain(self.metadata),
        }


@dataclass(frozen=True)
class ParameterRegister:
    """Immutable versioned list of identified effective terms and declared assumptions."""

    version: str
    season: str
    records: tuple[ParameterRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the complete versioned register as JSON-compatible values."""
        return {
            "schema_version": 1,
            "version": self.version,
            "season": self.season,
            "records": [record.to_dict() for record in self.records],
        }

    def to_json(self) -> str:
        """Serialize the register with stable key ordering."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False)


def _citation(uri: str, section: str, interpretation: str) -> Mapping[str, str]:
    return MappingProxyType({"uri": uri, "section": section, "interpretation": interpretation})


def _bounds(lower: float, upper: float, unit: str, basis: str) -> dict[str, Any]:
    return {
        season: {
            "lower": lower,
            "upper": upper,
            "unit": unit,
            "basis": basis,
        }
        for season in _SEASONS
    }


def _assumptions() -> tuple[ParameterRecord, ...]:
    fia_2023 = "https://www.fia.com/sites/default/files/fia_2023_formula_1_technical_regulations_-_issue_7_-_2023-08-31.pdf"
    fia_2024 = "https://www.fia.com/sites/default/files/fia_2024_formula_1_technical_regulations_-_issue_6_-_2024-04-30.pdf"
    fia_2025 = "https://www.fia.com/sites/default/files/fia_2025_formula_1_technical_regulations_-_issue_03_-_2025-04-07.pdf"
    openf1 = "https://openf1.org/docs/"
    missing_tire_measurements = _citation(
        openf1,
        "Car data, stints, and weather endpoint fields",
        "The public schema omits team mass, tire temperature, tire force, and thermal constants.",
    )
    regulation_evidence = (
        _citation(fia_2023, "Article 4.1", "2023 minimum car mass without fuel is 798 kg."),
        _citation(fia_2024, "Article 4.1", "2024 minimum car mass without fuel is 798 kg."),
        _citation(
            fia_2025,
            "Article 4.1",
            "2025 minimum car mass without fuel is 800 kg; heat-hazard increase may apply.",
        ),
    )
    shared_model_evidence = _citation(
        "https://www.fia.com/regulation/category/110/technical-regulations",
        "2023-2025 Formula 1 Technical Regulations, Articles 3-5",
        "Regulations constrain design, not team-specific effective values.",
    )
    specs: tuple[
        tuple[str, str, tuple[Mapping[str, str], ...], dict[str, Any], dict[str, Any], str, str],
        ...,
    ] = (
        (
            "mass_kg",
            "kg",
            regulation_evidence,
            {
                "2023": {
                    "lower": 798.0,
                    "upper": 900.0,
                    "lower_basis": "FIA minimum constraint",
                    "upper_basis": "analyst scenario bound",
                    "unit": "kg",
                },
                "2024": {
                    "lower": 798.0,
                    "upper": 900.0,
                    "lower_basis": "FIA minimum constraint",
                    "upper_basis": "analyst scenario bound",
                    "unit": "kg",
                },
                "2025": {
                    "lower": 800.0,
                    "upper": 900.0,
                    "lower_basis": "FIA minimum; heat-hazard increase may apply",
                    "upper_basis": "analyst scenario bound",
                    "unit": "kg",
                },
            },
            {
                "distribution": "uniform prior",
                "range": [798.0, 900.0],
                "uncertainty": (
                    "This is mass without fuel. The FIA minimum is a lower constraint; the "
                    "upper scenario bound is analyst-selected."
                ),
            },
            "constraint",
            "Unmeasured total vehicle mass; FIA minimum is a constraint, not a team measurement.",
        ),
        (
            "power_w",
            "W",
            (
                shared_model_evidence,
                _citation(
                    "https://api.fia.com/sites/default/files/documents/fia_2025_formula_1_technical_regulations_-_issue_03_-_2025-04-07.pdf",
                    "Article 5.3.2",
                    "The MGU-K is capped at 120 kW; this does not disclose total power output.",
                ),
            ),
            _bounds(
                500_000.0, 1_000_000.0, "W", "broad analyst prior; total power is not disclosed"
            ),
            {
                "distribution": "uniform prior",
                "range": [500_000.0, 1_000_000.0],
                "uncertainty": ("Broad solver sensitivity envelope; not fitted or team-specific."),
            },
            "assumption",
            "Total usable power is not identifiable from public lap times and speed samples.",
        ),
        (
            "drag_area_m2",
            "m^2",
            (shared_model_evidence, missing_tire_measurements),
            _bounds(0.7, 2.5, "m^2", "analyst aerodynamic scenario envelope"),
            {
                "distribution": "uniform prior",
                "range": [0.7, 2.5],
                "uncertainty": (
                    "Correlated with power, speed, and downforce; treat as a scenario parameter."
                ),
            },
            "assumption",
            "Effective drag area is hidden; it is confounded with power in straight-line speed.",
        ),
        (
            "drag_coefficient",
            "dimensionless",
            (shared_model_evidence,),
            _bounds(0.4, 1.6, "dimensionless", "analyst aerodynamic scenario envelope"),
            {
                "distribution": "uniform prior",
                "range": [0.4, 1.6],
                "uncertainty": ("Not independent of frontal area; use the product in the solver."),
            },
            "assumption",
            "Coefficient is not independently observed; use only with an explicit reference area.",
        ),
        (
            "downforce_n",
            "N at 200 km/h",
            (shared_model_evidence,),
            _bounds(10_000.0, 60_000.0, "N at 200 km/h", "analyst aerodynamic scenario envelope"),
            {
                "distribution": "uniform prior",
                "range": [10_000.0, 60_000.0],
                "uncertainty": (
                    "Reference-speed scaling is assumed; no team aero map is observed."
                ),
            },
            "assumption",
            "Downforce is a latent vehicle property and is not an observed force in the cache.",
        ),
        (
            "grip_mu",
            "dimensionless",
            (shared_model_evidence, missing_tire_measurements),
            _bounds(0.8, 3.0, "dimensionless", "broad combined tire/track grip scenario envelope"),
            {
                "distribution": "uniform prior",
                "range": [0.8, 3.0],
                "uncertainty": (
                    "Combined grip is not measured directly; environment and tire state affect it."
                ),
            },
            "assumption",
            "Combined tire/track grip is assumed, not measured from OpenF1 location or weather.",
        ),
        (
            "starting_fuel_kg",
            "kg",
            (shared_model_evidence,),
            _bounds(
                0.0, 150.0, "kg", "analyst mass-balance envelope; no public per-car starting mass"
            ),
            {
                "distribution": "uniform prior",
                "range": [0.0, 150.0],
                "uncertainty": ("No fuel mass is published; this range is for sensitivity only."),
            },
            "assumption",
            "Starting fuel mass is not inferred from the fitted fuel_s_per_lap pace coefficient.",
        ),
        (
            "fuel_burn_kg_per_lap",
            "kg/lap",
            (shared_model_evidence,),
            _bounds(
                0.5,
                3.0,
                "kg/lap",
                "analyst mass-balance envelope; no fuel-flow measurements in cache",
            ),
            {
                "distribution": "uniform prior",
                "range": [0.5, 3.0],
                "uncertainty": (
                    "The pace regression estimates seconds per lap, not mass burned per lap."
                ),
            },
            "assumption",
            "Fuel burn is not obtained by converting an observational seconds-per-lap slope.",
        ),
        (
            "tire_friction_mu",
            "dimensionless",
            (missing_tire_measurements,),
            _bounds(0.8, 3.0, "dimensionless", "broad analyst tire friction envelope"),
            {
                "distribution": "uniform prior",
                "range": [0.8, 3.0],
                "uncertainty": "No direct tire-force or tire-temperature field is available.",
            },
            "assumption",
            "Tire friction is latent; the M1 wear slope measures pace, not friction.",
        ),
        (
            "tire_heat_capacity_j_k",
            "J/K",
            (missing_tire_measurements,),
            _bounds(1_000.0, 100_000.0, "J/K", "broad analyst thermal-mass envelope"),
            {
                "distribution": "uniform prior",
                "range": [1_000.0, 100_000.0],
                "uncertainty": (
                    "Thermal capacity is absent from public timing, location, and weather channels."
                ),
            },
            "assumption",
            "Latent tire heat capacity; ambient or track temperature cannot identify it alone.",
        ),
        (
            "tire_cooling_w_k",
            "W/K",
            (missing_tire_measurements,),
            _bounds(10.0, 5_000.0, "W/K", "broad analyst thermal-loss envelope"),
            {
                "distribution": "uniform prior",
                "range": [10.0, 5_000.0],
                "uncertainty": (
                    "Cooling constants are not measured; use only in sensitivity scenarios."
                ),
            },
            "assumption",
            "A latent tire heat-loss coefficient, not an observed weather value.",
        ),
    )
    return tuple(
        ParameterRecord(
            name=name,
            classification="hidden_assumption",
            value=None,
            evidence=evidence,
            season_bounds=bounds,
            uncertainty=uncertainty,
            sensitivity_status="not_estimable_pre_solver",
            constraint_status=constraint_status,
            unit=unit,
            description=description,
            metadata={"team_specific": False, "is_measured": False},
        )
        for name, unit, evidence, bounds, uncertainty, constraint_status, description in specs
    )


def _effective_record(
    *,
    name: str,
    unit: str,
    estimates: list[tuple[str, float, float, int, int, float | None, float | None]],
    season: str,
    description: str,
) -> ParameterRecord:
    if not estimates:
        return ParameterRecord(
            name=name,
            classification="fitted_effective",
            value=None,
            evidence=(
                _citation(
                    "src/f1si/pace/linear.py",
                    "fit_linear_pace / FitReport",
                    "Fit is unidentifiable or the required clean stint evidence is insufficient.",
                ),
            ),
            season_bounds={"period": season, "lower": None, "upper": None, "unit": unit},
            uncertainty=None,
            sensitivity_status="unidentified",
            constraint_status="observation",
            unit=unit,
            description=description,
            metadata={"identified_race_count": 0, "sample_count": 0},
        )
    values = [item[1] for item in estimates]
    within_ses = [item[2] for item in estimates]
    pooled = sum(values) / len(values)
    between_se = (
        math.sqrt(sum((value - pooled) ** 2 for value in values) / (len(values) - 1) / len(values))
        if len(values) > 1
        else 0.0
    )
    within_rms = math.sqrt(sum(value * value for value in within_ses) / len(within_ses))
    pooled_within_se = math.sqrt(sum(value * value for value in within_ses)) / len(within_ses)
    combined_se = math.sqrt(pooled_within_se**2 + between_se**2)
    return ParameterRecord(
        name=name,
        classification="fitted_effective",
        value=pooled,
        evidence=(
            _citation(
                "src/f1si/pace/linear.py",
                "FitReport fuel_s_per_lap / CompoundFit wear_s_per_lap",
                "Equal-race mean from cutoff-safe snapshots; not mass, burn, or friction.",
            ),
        ),
        season_bounds={"period": season, "lower": None, "upper": None, "unit": unit},
        uncertainty={
            "standard_error": combined_se,
            "within_fit_standard_error_rms": within_rms,
            "pooled_within_standard_error": pooled_within_se,
            "between_race_standard_error": between_se,
            "ci_95": [pooled - 1.96 * combined_se, pooled + 1.96 * combined_se],
        },
        sensitivity_status="awaiting_leave_one_race_out_screen",
        constraint_status="observation",
        unit=unit,
        description=description,
        metadata={
            "identified_race_count": len(estimates),
            "sample_count": sum(item[3] for item in estimates),
            "race_ids": [item[0] for item in estimates],
            "per_race_estimates": [
                {
                    "race_id": race_id,
                    "value": estimate,
                    "standard_error": se,
                    "n_laps": sample_count,
                    "n_stints": stint_count,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                }
                for race_id, estimate, se, sample_count, stint_count, ci_low, ci_high in estimates
            ],
        },
    )


def build_register(
    *,
    fits: Iterable[LinearPaceFit],
    season: str | int,
    race_ids: Iterable[str] | None = None,
) -> ParameterRegister:
    """Build a register; only the existing effective fuel and compound-age fits receive values."""
    fit_rows = list(fits)
    ids = (
        list(race_ids)
        if race_ids is not None
        else [f"fit-{i + 1:03d}" for i in range(len(fit_rows))]
    )
    if len(ids) != len(fit_rows):
        raise ValueError("race_ids must have the same length as fits")
    period = str(season)
    fuel: list[tuple[str, float, float, int, int, float | None, float | None]] = []
    wear: dict[str, list[tuple[str, float, float, int, int, float | None, float | None]]] = (
        defaultdict(list)
    )
    for race_id, fit in zip(ids, fit_rows, strict=True):
        report = fit.report
        if report.fuel_s_per_lap is not None and report.fuel_se is not None:
            fuel.append(
                (
                    race_id,
                    report.fuel_s_per_lap,
                    report.fuel_se,
                    report.n_clean,
                    0,
                    report.fuel_ci_low,
                    report.fuel_ci_high,
                )
            )
        for compound in report.compounds:
            wear[compound.compound].append(
                (
                    race_id,
                    compound.wear_s_per_lap,
                    compound.se,
                    compound.n_laps,
                    compound.n_stints,
                    compound.ci_low,
                    compound.ci_high,
                )
            )
    records = [
        _effective_record(
            name="fuel_s_per_lap",
            unit="s/lap",
            estimates=fuel,
            season=period,
            description=(
                "Observed pace slope per lap; may include track evolution; not fuel mass or burn."
            ),
        )
    ]
    compounds = sorted(set(wear) | {"SOFT", "MEDIUM", "HARD"})
    records.extend(
        _effective_record(
            name=f"wear_s_per_lap:{compound}",
            unit="s/tyre-age-lap",
            estimates=wear.get(compound, []),
            season=period,
            description=(
                f"Observed compound-age slope for {compound}; not tire friction or temperature."
            ),
        )
        for compound in compounds
    )
    records.extend(_assumptions())
    return ParameterRegister(REGISTER_VERSION, period, tuple(records))
