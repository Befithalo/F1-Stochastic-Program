"""Contracts distinguishing evidence-backed effective terms from physical assumptions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_register_classifies_effective_terms_and_hidden_assumptions(
    long_synthetic_db: Path,
) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.pace.linear import fit_linear_pace
    from f1si.parameters.register import build_register

    fit = fit_linear_pace(AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 40)))
    register = build_register(fits=[fit], season="2023")
    records = {record.name: record for record in register.records}

    assert records["fuel_s_per_lap"].classification == "fitted_effective"
    assert records["fuel_s_per_lap"].evidence
    assert records["fuel_s_per_lap"].uncertainty is not None
    for hidden in (
        "mass_kg",
        "power_w",
        "drag_area_m2",
        "drag_coefficient",
        "downforce_n",
        "grip_mu",
        "starting_fuel_kg",
        "fuel_burn_kg_per_lap",
        "tire_friction_mu",
        "tire_heat_capacity_j_k",
        "tire_cooling_w_k",
    ):
        assert records[hidden].classification == "hidden_assumption"
        assert records[hidden].value is None
        assert records[hidden].evidence
        assert records[hidden].season_bounds
        assert records[hidden].uncertainty is not None
        assert records[hidden].sensitivity_status
        assert records[hidden].constraint_status in {"constraint", "assumption", "observation"}


def test_register_does_not_label_unidentified_terms_as_recovered(long_synthetic_db: Path) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.pace.linear import fit_linear_pace
    from f1si.parameters.register import build_register

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
    from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, catalog
    from f1si.parameters.report import build_sensitivity_report

    races = catalog(long_synthetic_db)
    eligible = races.loc[
        races["season"].astype(int).between(2023, 2025)
        & races["load_status"].eq("complete")
        & ~races["out_of_sample"].astype(bool)
    ].sort_values(["season", "round"])
    accessor = AsOfAccessor(long_synthetic_db)
    snapshots = [
        (str(race_id), accessor.snapshot(AsOf(str(race_id), RACE_END)))
        for race_id in eligible["race_id"].astype(str)
    ]
    report = build_sensitivity_report(snapshots, cache_file_name=long_synthetic_db.name)

    assert report["evidence_sensitivity"]["eligible_race_count"] > 0
    assert report["evidence_sensitivity"]["sample_count"] > 0
    assert report["evidence_sensitivity"]["identified_race_count"] >= 0
    assert report["evidence_sensitivity"]["coefficient_standard_error"] is not None
    assert report["evidence_sensitivity"]["leave_one_race_out"]
    assert report["predictive_lap_time_sensitivity"] == "not_estimable_pre_solver"
    assert all(race_id.startswith(("2023-", "2024-", "2025-")) for race_id in report["race_ids"])
    assert "results" not in json.dumps(report).lower()


def test_parameter_report_refuses_mid_race_snapshots(long_synthetic_db: Path) -> None:
    from f1si.data.asof import AsOf, AsOfAccessor
    from f1si.parameters.report import build_sensitivity_report

    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf("2023-01", 40))

    with pytest.raises(ValueError, match="RACE_END snapshots"):
        build_sensitivity_report([("2023-01", snapshot)], cache_file_name=long_synthetic_db.name)


def test_closeout_contract_carries_coverage_and_exact_m1_baseline(tmp_path: Path) -> None:
    from f1si.parameters.report import render_phase_report

    sensitivity = {
        "evidence_sensitivity": {"eligible_race_count": 1, "sample_count": 50},
        "predictive_lap_time_sensitivity": "not_estimable_pre_solver",
    }
    coverage = {
        "local_cache": {
            "catalog_complete_races": 1,
            "channels": {
                "weather": {"row_count": 20},
                "car_data": {"row_count": 0},
                "location": {"row_count": 0},
            },
        },
        "bahrain_2023_probe": {
            "status": "unavailable",
            "reason": "service returned no rows",
            "endpoints": {
                endpoint: {"row_count": 0, "race_clock_alignment": "unavailable"}
                for endpoint in ("/car_data", "/location", "/weather")
            },
        },
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
    assert "complete catalog audit covers 1 races" in rendered
    assert "20 rows" in rendered
    assert "Probe status: unavailable." in rendered
    assert "Probe reason: service returned no rows." in rendered
    assert "/car_data: 0 rows, 0 usable, alignment unavailable" in rendered


def test_closeout_renders_partial_probe_endpoint_evidence_and_reasons() -> None:
    from f1si.parameters.report import render_phase_report

    sensitivity = {
        "evidence_sensitivity": {"eligible_race_count": 1, "sample_count": 50},
        "predictive_lap_time_sensitivity": "not_estimable_pre_solver",
    }
    coverage = {
        "bahrain_2023_probe": {
            "status": "unavailable",
            "reason": "bounded telemetry probe failed at /location: location endpoint unavailable",
            "endpoints": {
                "/car_data": {
                    "status": "available",
                    "row_count": 4,
                    "usable_row_count": 4,
                    "valid_timestamp_fraction": 1.0,
                    "race_clock_alignment": "aligned",
                },
                "/location": {
                    "status": "unavailable",
                    "reason": "request failed: location endpoint unavailable",
                    "row_count": 0,
                    "usable_row_count": 0,
                    "valid_timestamp_fraction": 0.0,
                    "race_clock_alignment": "unavailable",
                },
                "/weather": {
                    "status": "unavailable",
                    "reason": "not requested after /location failed",
                    "row_count": 0,
                    "usable_row_count": 0,
                    "valid_timestamp_fraction": 0.0,
                    "race_clock_alignment": "unavailable",
                },
            },
        }
    }

    rendered = render_phase_report(sensitivity, coverage)

    assert "/car_data: 4 rows, 4 usable, alignment aligned" in rendered
    assert "/location: 0 rows, 0 usable, alignment unavailable" in rendered
    assert "reason: request failed: location endpoint unavailable" in rendered
    assert "reason: not requested after /location failed" in rendered


@pytest.mark.parametrize(
    "name",
    ["mass_kg", "power_w", "drag_area_m2", "grip_mu", "starting_fuel_kg", "tire_heat_capacity_j_k"],
)
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
