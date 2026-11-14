"""Contracts for the leave-current-stint-out, explicitly proxy wear diagnostic."""

from __future__ import annotations

import pandas as pd

from f1si.backtest.wear_diagnostic import build_leave_stint_out_reference, summarize_wear_proxy


def test_reference_excludes_every_lap_from_the_current_stint() -> None:
    laps = pd.DataFrame(
        {
            "driver": ["ALO"] * 6,
            "stint": [1, 1, 1, 2, 2, 2],
            "lap_number": [1, 2, 3, 4, 5, 6],
            "lap_time_s": [91.0, 91.2, 91.4, 92.0, 92.2, 92.4],
        }
    )
    reference = build_leave_stint_out_reference(laps, driver="ALO", stint=2)
    assert set(reference["lap_number"]) == {1, 2, 3}
    assert reference.attrs["label"] == "retrospective proxy"


def test_summary_labels_proxy_and_reports_coverage_denominator_bias_and_own_laps() -> None:
    rows = pd.DataFrame(
        {
            "race_id": ["r1", "r1", "r2"],
            "inside_proxy_band": [True, False, True],
            "early_fit_error_s_per_lap": [0.10, 0.20, -0.10],
            "current_stint_own_lap_share": [0.3, 0.4, 0.2],
        }
    )
    result = summarize_wear_proxy(rows)
    assert result["label"] == "retrospective proxy, not latent ground truth"
    assert result["coverage_denominator"] == 3
    assert result["early_fit_bias_s_per_lap"] != 0
    assert result["own_lap_evidence"] is not None


def test_diagnostic_returns_measurements_without_filter_parameter_updates() -> None:
    rows = pd.DataFrame(
        {
            "race_id": ["r"],
            "inside_proxy_band": [True],
            "early_fit_error_s_per_lap": [0.1],
            "current_stint_own_lap_share": [0.25],
        }
    )
    result = summarize_wear_proxy(rows)
    forbidden = ("updated_parameters", "fit_parameters", "tuned_filter")
    assert not any(key in result for key in forbidden)


def test_summary_exposes_race_level_coverage_bias_and_own_lap_evidence() -> None:
    rows = pd.DataFrame(
        {
            "race_id": ["r1", "r1", "r2"],
            "inside_proxy_band": [True, False, True],
            "early_fit_error_s_per_lap": [0.10, 0.30, -0.20],
            "current_stint_own_lap_share": [0.30, 0.50, 0.20],
        }
    )
    result = summarize_wear_proxy(rows)
    assert result["coverage_by_race"] == {
        "r1": {"covered": 1, "denominator": 2, "coverage": 0.5},
        "r2": {"covered": 1, "denominator": 1, "coverage": 1.0},
    }
    assert result["early_fit_bias_by_race"] == {"r1": 0.2, "r2": -0.2}
    assert result["own_lap_evidence"]["share_by_race"] == {"r1": 0.4, "r2": 0.2}
