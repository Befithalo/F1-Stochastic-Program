"""Contracts distinguishing evidence-backed effective terms from physical assumptions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_register_classifies_effective_terms_and_hidden_assumptions(
    long_synthetic_db: Path,
) -> None:
    from f1si.parameters.register import build_register

    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.pace.linear import fit_linear_pace

    fit = fit_linear_pace(AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 40)))
    register = build_register(fits=[fit], season="2023")
    records = {record.name: record for record in register.records}

    assert records["fuel_s_per_lap"].classification == "fitted_effective"
    assert records["fuel_s_per_lap"].evidence
    assert records["fuel_s_per_lap"].uncertainty is not None
    for hidden in ("mass_kg", "power_w", "drag_area_m2", "downforce_n", "grip_mu"):
        assert records[hidden].classification == "hidden_assumption"
        assert records[hidden].value is None
        assert records[hidden].evidence
        assert records[hidden].season_bounds
        assert records[hidden].uncertainty is not None


def test_register_does_not_label_unidentified_terms_as_recovered(long_synthetic_db: Path) -> None:
    from f1si.parameters.register import build_register

    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.pace.linear import fit_linear_pace

    fit = fit_linear_pace(AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 10)))
    register = build_register(fits=[fit], season="2023")

    assert all(
        record.value is None
        for record in register.records
        if record.name == "fuel_s_per_lap" and not fit.is_identified
    )
    assert "recovered" not in register.to_json().lower()


def test_evidence_sensitivity_is_numeric_and_predictive_sensitivity_is_pre_solver(
    long_synthetic_db: Path,
) -> None:
    from f1si.parameters.report import build_sensitivity_report

    report = build_sensitivity_report(long_synthetic_db)

    assert report["evidence_sensitivity"]["eligible_race_count"] > 0
    assert report["evidence_sensitivity"]["sample_count"] > 0
    assert report["predictive_lap_time_sensitivity"] == "not_estimable_pre_solver"
    assert all(race_id.startswith(("2023-", "2024-", "2025-")) for race_id in report["race_ids"])
    assert "results" not in json.dumps(report).lower()


def test_closeout_contract_carries_coverage_and_exact_m1_baseline(tmp_path: Path) -> None:
    from f1si.parameters.report import render_phase_report

    sensitivity = {
        "evidence_sensitivity": {"eligible_race_count": 1, "sample_count": 50},
        "predictive_lap_time_sensitivity": "not_estimable_pre_solver",
    }
    coverage = {
        "local_cache": {
            "catalog_complete_races": 1,
            "channels": {"weather": {}, "car_data": {}, "location": {}},
        },
        "bahrain_2023_probe": {"status": "unavailable", "reason": "service returned no rows"},
    }

    rendered = render_phase_report(sensitivity, coverage)

    assert "0.055456" in rendered
    assert "0.073693" in rendered
    assert "0.144645" in rendered
    assert "0.169086" in rendered
    assert "82.26%" in rendered
    assert "16,508/20,001" in rendered
    assert "+1.174" in rendered
    assert "17.22%" in rendered
    assert "PAC-06 remains unmet" in rendered
    assert "not_estimable_pre_solver" in rendered


@pytest.mark.parametrize("name", ["mass_kg", "power_w", "drag_area_m2", "grip_mu"])
def test_hidden_physical_parameter_requires_evidence_bounds_and_uncertainty(name: str) -> None:
    from f1si.parameters.register import ParameterRecord

    with pytest.raises((TypeError, ValueError)):
        ParameterRecord(
            name=name,
            classification="hidden_assumption",
            value=1.0,
            evidence=(),
            season_bounds=None,
            uncertainty=None,
        )
