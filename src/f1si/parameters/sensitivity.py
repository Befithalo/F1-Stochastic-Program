"""Numerical stability screens for observable pace coefficients.

This module deliberately reports fit stability only. It does not map fitted pace slopes to
absolute vehicle, fuel-mass, aerodynamic, or tire properties.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from typing import Any

from f1si.pace.linear import LinearPaceFit

METHOD_VERSION = "race-equal-weight-loo-v1"


def _estimate_rows(
    fits: Iterable[tuple[str, LinearPaceFit]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fuel: list[dict[str, Any]] = []
    wear: list[dict[str, Any]] = []
    for race_id, fit in fits:
        report = fit.report
        if report.fuel_s_per_lap is not None and report.fuel_se is not None:
            fuel.append(
                {
                    "race_id": race_id,
                    "estimate": float(report.fuel_s_per_lap),
                    "standard_error": float(report.fuel_se),
                    "ci_95": [float(report.fuel_ci_low), float(report.fuel_ci_high)],
                    "sample_count": int(report.n_clean),
                    "identified": True,
                }
            )
        for term in report.compounds:
            wear.append(
                {
                    "race_id": race_id,
                    "term": f"wear_s_per_lap:{term.compound}",
                    "estimate": float(term.wear_s_per_lap),
                    "standard_error": float(term.se),
                    "ci_95": [float(term.ci_low), float(term.ci_high)],
                    "sample_count": int(term.n_laps),
                    "stint_count": int(term.n_stints),
                    "identified": True,
                }
            )
    return fuel, wear


def _summarize_term(
    term: str,
    rows: list[dict[str, Any]],
    *,
    eligible_race_count: int,
    sample_count: int,
) -> dict[str, Any]:
    if not rows:
        return {
            "term": term,
            "status": "unidentified",
            "eligible_race_count": eligible_race_count,
            "identified_race_count": 0,
            "sample_count": sample_count,
            "pooled_estimate": None,
            "coefficient_standard_error": None,
            "within_fit_standard_error_rms": None,
            "ci_95": None,
            "leave_one_race_out": [],
        }

    estimate = sum(row["estimate"] for row in rows) / len(rows)
    within_se = math.sqrt(sum(row["standard_error"] ** 2 for row in rows) / len(rows))
    between_se = (
        math.sqrt(
            sum((row["estimate"] - estimate) ** 2 for row in rows) / (len(rows) - 1) / len(rows)
        )
        if len(rows) > 1
        else 0.0
    )
    coefficient_se = math.sqrt(within_se**2 + between_se**2)
    loo: list[dict[str, Any]] = []
    for held in rows:
        rest = [row for row in rows if row["race_id"] != held["race_id"]]
        loo_estimate = sum(row["estimate"] for row in rest) / len(rest) if rest else None
        loo.append(
            {
                "excluded_race_id": held["race_id"],
                "pooled_estimate": loo_estimate,
                "change_from_full": None if loo_estimate is None else loo_estimate - estimate,
            }
        )
    return {
        "term": term,
        "status": "identified",
        "eligible_race_count": eligible_race_count,
        "identified_race_count": len(rows),
        "sample_count": sample_count,
        "pooled_estimate": estimate,
        "coefficient_standard_error": coefficient_se,
        "within_fit_standard_error_rms": within_se,
        "between_race_standard_error": between_se,
        "ci_95": [estimate - 1.96 * coefficient_se, estimate + 1.96 * coefficient_se],
        "per_race": rows,
        "leave_one_race_out": loo,
    }


def summarize_evidence(
    fits: Iterable[tuple[str, LinearPaceFit]], *, eligible_race_count: int, sample_count: int
) -> dict[str, Any]:
    """Summarize equal-race coefficient estimates and leave-one-race-out changes."""
    fit_rows = list(fits)
    fuel_rows, wear_rows = _estimate_rows(fit_rows)
    fuel = _summarize_term(
        "fuel_s_per_lap",
        fuel_rows,
        eligible_race_count=eligible_race_count,
        sample_count=sample_count,
    )
    wear_terms = sorted({row["term"] for row in wear_rows})
    wear = {
        term: _summarize_term(
            term,
            [row for row in wear_rows if row["term"] == term],
            eligible_race_count=eligible_race_count,
            sample_count=sum(row["sample_count"] for row in wear_rows if row["term"] == term),
        )
        for term in wear_terms
    }
    return {
        "eligible_race_count": eligible_race_count,
        "sample_count": sample_count,
        "identified_race_count": fuel["identified_race_count"],
        "coefficient_standard_error": fuel["coefficient_standard_error"],
        "leave_one_race_out": fuel["leave_one_race_out"],
        "terms": {"fuel_s_per_lap": fuel, **wear},
        "pooling": "equal race weight; no race with more laps receives extra weight",
        "diagnostic_scope": "coefficient stability, not physical parameter recovery",
    }


def evidence_digest(rows: Iterable[Mapping[str, Any]]) -> str:
    """Hash stable, cutoff-safe race identifiers and fit summaries for report provenance."""
    canonical = json.dumps(list(rows), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
