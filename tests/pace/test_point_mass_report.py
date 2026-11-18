"""Closeout-report contract for Phase 10's fixed evidence and limits."""

from __future__ import annotations

import re
from pathlib import Path

REPORT = Path(__file__).parents[2] / ".planning/phases/10-point-mass-pacemodel/10-PHASE-REPORT.md"


def test_phase_report_copies_fixed_m1_baseline_and_pac06_status() -> None:
    report = REPORT.read_text(encoding="utf-8")

    assert "Copied unchanged from `.planning/M1-BASELINE.md`; not recomputed." in report
    for value in (
        "0.055456",
        "0.073693",
        "0.144645",
        "0.169086",
        "82.26%",
        "16,508/20,001",
        "+1.174 laps",
        "695 matched stops",
        "17.22%",
    ):
        assert value in report
    assert "PAC-06 remains unmet" in report
    assert "0.538745 s" in report
    assert "0.364033 s" in report
    assert "-47.99%" in report
    assert "retune" in report.lower()
    assert "rescor" in report.lower()


def test_phase_report_records_method_recovery_limits_and_runtime_budget() -> None:
    report = REPORT.read_text(encoding="utf-8")

    for value in (
        "1e-5 m/s",
        "1,000 forward/backward passes",
        "0.1%",
        "xatol=1e-8",
        "maxiter=500",
        "1e6",
        "30 clean laps",
        "three distinct races",
        "plus/minus sqrt(p)",
        "10%",
        "boundary_limited",
        "scenario_only",
        "residual variance unavailable",
        "1.079989",
        "5% relative tolerance",
        "50,000-race budget",
    ):
        assert value in report
    assert "assumption" in report.lower()
    assert "unidentifiable" in report.lower()
    assert "2026 report" not in report.lower()
    assert "locked target" not in report.lower()


def test_phase_report_links_green_ubuntu_and_windows_runs_for_one_code_commit() -> None:
    report = REPORT.read_text(encoding="utf-8")
    commit_match = re.search(r"Final code commit: `([0-9a-f]{7,40})`", report)
    assert commit_match is not None
    commit = commit_match.group(1)

    for platform in ("Ubuntu", "Windows"):
        assert re.search(
            rf"{platform}.*run #[0-9]+.*`{re.escape(commit)}`.*success",
            report,
            re.IGNORECASE,
        )
        assert re.search(
            rf"{platform}.*https://github\.com/.+/actions/runs/[0-9]+",
            report,
            re.IGNORECASE,
        )
