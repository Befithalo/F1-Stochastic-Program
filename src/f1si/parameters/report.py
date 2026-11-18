"""Generate a cutoff-safe parameter evidence report and Phase 9 closeout."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from f1si.data import schema
from f1si.data.asof import RaceSnapshot
from f1si.pace.linear import fit_linear_pace
from f1si.parameters import REGISTER_VERSION, build_register
from f1si.parameters.sensitivity import METHOD_VERSION, evidence_digest, summarize_evidence

REPORT_VERSION = "m2-parameter-evidence-v1"


def _schema_digest() -> str:
    contract = {
        name: {
            "columns": [
                {"name": col.name, "type": col.sql_type, "nullable": col.nullable}
                for col in spec.columns
            ],
            "key": list(spec.key),
            "visibility": spec.visibility,
            "optional": spec.optional,
        }
        for name, spec in sorted(schema.TABLES.items())
    }
    payload = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_sensitivity_report(
    snapshots: Sequence[tuple[str, RaceSnapshot]], *, cache_file_name: str
) -> dict[str, Any]:
    """Fit provided in-sample end snapshots; callers own cache and cutoff access."""
    if not snapshots:
        raise ValueError("catalog precondition failed: no complete in-sample races from 2023-2025")
    race_ids_in = [race_id for race_id, _snapshot in snapshots]
    if len(set(race_ids_in)) != len(race_ids_in):
        raise ValueError("sensitivity snapshots must have unique race IDs")
    invalid = [
        race_id
        for race_id, snapshot in snapshots
        if snapshot.race.race_id != race_id
        or snapshot.at.race_id != race_id
        or not 2023 <= snapshot.race.season <= 2025
        or snapshot.race.out_of_sample
        or snapshot.cutoff_s is not None
    ]
    if invalid:
        raise ValueError(
            "sensitivity report accepts only in-sample 2023-2025 RACE_END snapshots; "
            f"invalid races: {', '.join(invalid)}"
        )

    fits: list[tuple[str, Any]] = []
    fit_evidence: list[dict[str, Any]] = []
    race_ids: list[str] = []
    sample_count = 0
    for race_id, snapshot in snapshots:
        fit = fit_linear_pace(snapshot)
        fits.append((race_id, fit))
        race_ids.append(race_id)
        sample_count += int(fit.report.n_clean)
        fit_evidence.append(
            {
                "race_id": race_id,
                "lap_rows": len(snapshot.laps),
                "clean_laps": int(fit.report.n_clean),
                "identified": bool(fit.is_identified),
                "fuel_s_per_lap": fit.report.fuel_s_per_lap,
                "fuel_se": fit.report.fuel_se,
                "wear": [
                    {
                        "compound": term.compound,
                        "estimate": term.wear_s_per_lap,
                        "se": term.se,
                        "n_laps": term.n_laps,
                    }
                    for term in fit.report.compounds
                ],
            }
        )

    evidence = summarize_evidence(
        fits, eligible_race_count=len(snapshots), sample_count=sample_count
    )
    register = build_register(
        fits=[fit for _, fit in fits],
        race_ids=[race_id for race_id, _ in fits],
        season="2023-2025",
    )
    return {
        "report_version": REPORT_VERSION,
        "method_version": METHOD_VERSION,
        "register_version": REGISTER_VERSION,
        "cache": {
            "file_name": cache_file_name,
            "schema_contract_sha256": _schema_digest(),
            "race_evidence_sha256": evidence_digest(fit_evidence),
        },
        "evidence_set": {
            "seasons": [2023, 2024, 2025],
            "race_count": len(race_ids),
            "race_ids": race_ids,
            "snapshot": "RACE_END through AsOfAccessor.snapshot",
            "fit_input": "snapshot laps only",
            "out_of_sample_included": False,
        },
        "race_ids": race_ids,
        "evidence_sensitivity": evidence,
        "predictive_lap_time_sensitivity": "not_estimable_pre_solver",
        "parameter_register": register.to_dict(),
    }


def _endpoint_rows(coverage: dict[str, Any]) -> str:
    endpoints = coverage.get("endpoints", {})
    if coverage.get("status") != "available":
        status = coverage.get("status", "unavailable")
        reason = coverage.get("reason", "no reason recorded")
        return f"Probe status: {status}; {reason}."
    rows = []
    for endpoint in ("/car_data", "/location", "/weather"):
        item = endpoints.get(endpoint, {})
        rows.append(
            f"{endpoint}: {item.get('row_count', 0)} rows, "
            f"alignment {item.get('race_clock_alignment', 'unavailable')}, "
            f"valid source timestamps {item.get('valid_timestamp_fraction', 0):.1%}."
        )
    return " ".join(rows)


def render_phase_report(sensitivity: dict[str, Any], coverage: dict[str, Any]) -> str:
    """Render fixed baseline, local coverage, single probe, and scope disclosures."""
    local = coverage.get("local_cache", {})
    channels = local.get("channels", {})
    eligible_races = sensitivity["evidence_sensitivity"]["eligible_race_count"]
    clean_samples = sensitivity["evidence_sensitivity"]["sample_count"]
    fuel = sensitivity["evidence_sensitivity"].get("terms", {}).get("fuel_s_per_lap", {})
    loo_changes = [
        item["change_from_full"]
        for item in fuel.get("leave_one_race_out", [])
        if item["change_from_full"] is not None
    ]
    loo_span = (
        f"{min(loo_changes):+.5f} to {max(loo_changes):+.5f} s/lap"
        if loo_changes
        else "unavailable"
    )
    fuel_summary = (
        (
            f"- Effective lap-number pace slope: {fuel['pooled_estimate']:.5f} s/lap "
            f"(SE {fuel['coefficient_standard_error']:.5f}; "
            f"95% CI {fuel['ci_95'][0]:.5f} to {fuel['ci_95'][1]:.5f}; "
            f"identified in {fuel['identified_race_count']}/{eligible_races} races)."
        )
        if fuel.get("pooled_estimate") is not None
        else "- Effective lap-number pace slope: unidentified in this evidence set."
    )
    weather = channels.get("weather", {})
    car_data = channels.get("car_data", {})
    location = channels.get("location", {})
    probe = coverage.get("bahrain_2023_probe", {})
    lines = [
        "# Phase 9 Report — Data and Geometry Readiness",
        "",
        "## Parameter evidence",
        "",
        f"- Eligible complete 2023-2025 in-sample races: {eligible_races}.",
        f"- Clean lap samples used: {clean_samples}.",
        fuel_summary,
        f"- Leave-one-race-out estimate change: {loo_span}.",
        f"- Predictive lap-time sensitivity: `{sensitivity['predictive_lap_time_sensitivity']}`.",
        "- The register separates observable effective pace coefficients from hidden "
        "vehicle, fuel, and tire assumptions.",
        "- The screen measures coefficient stability; it does not recover physical parameters.",
        "",
        "## Data and geometry readiness",
        "",
        f"- DAT-01: complete catalog audit covers {local.get('catalog_complete_races', 0)} races.",
        f"- Weather: {weather.get('races_present', 0)} races / {weather.get('row_count', 0)} rows.",
        f"- Car: {car_data.get('races_present', 0)} races / {car_data.get('row_count', 0)} rows.",
        f"- GPS: {location.get('races_present', 0)} races / {location.get('row_count', 0)} rows.",
        (f"- Single bounded Bahrain 2023 probe: {_endpoint_rows(probe)}"),
        (
            "- GEO-01: pinned Sakhir profile passed its digest, unit, and geometry checks. "
            "The raw CSV remains local pending rights clarity."
        ),
        "",
        "## Fixed M1 baseline",
        "",
        "Copied unchanged from `.planning/M1-BASELINE.md`; not recomputed for M2.",
        "",
        (
            "- Podium Brier: 0.055456 (grid baseline 0.073693); "
            "20 race-weighted means, 22,213 observations."
        ),
        (
            "- Top-10 Brier: 0.144645 (grid baseline 0.169086); "
            "20 race-weighted means, 22,213 observations."
        ),
        (
            "- Inclusive P05-P95 finish-interval coverage: 82.26%; "
            "16,508/20,001 classified finishers."
        ),
        ("- Signed planned-stop timing error: +1.174 laps; 695 matched stops across 20 races."),
        (
            "- Top-action agreement with observed team calls: 17.22%; "
            "695 matched stops across 20 races."
        ),
        "",
        "## Locked boundaries",
        "",
        "- PAC-06 remains unmet: Bayesian MAE 0.538745 s versus linear pace 0.364033 s.",
        "  Do not retune or rescore this gate.",
        "- Keep the separate 2026 report outside M2 tuning.",
        "- Preserve the 50,000-race budget and existing `PaceModel` consumer contract.",
        "- No geometry or parameter lookup occurs in the per-lap prediction path.",
        "",
    ]
    return "\n".join(lines)
