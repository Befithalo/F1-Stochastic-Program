---
phase: "09"
status: secured
asvs_level: 1
block_threshold: high
register_authored_at_plan_time: true
threats_open: 0
threats_closed: 18
reviewed: "2026-11-18"
---

# Phase 09 Security Verification

The Phase 9 threat register was authored in the plans and checked against the implementation. All 17 high-severity threat instances are mitigated; the one low-severity package-installation risk is accepted as planned. No package-manager or dependency changes were made.

| Threat | Severity | Status | Evidence |
|--------|----------|--------|----------|
| T-09-01, T-09-05, T-09-09, T-09-13 | High | Mitigated | As-of input preserves the inclusive cutoff and excludes future rows; `tests/data/test_physics_input.py` covers exact-cutoff and future-row perturbation behavior. |
| T-09-02, T-09-06, T-09-10, T-09-14 | High | Mitigated | Strict external payload parsing and isolated optional-channel quarantine; `tests/data/test_openf1.py` covers malformed, missing, and unavailable channels. |
| T-09-03, T-09-07, T-09-11, T-09-15 | High | Mitigated | Geometry paths remain confined, raw bytes are SHA-256 checked, provenance/rights/validation metadata is required, and malformed geometry fails closed; `tests/geometry/test_profile.py` covers these boundaries. |
| T-09-04, T-09-08, T-09-12, T-09-16 | High | Mitigated | Physics input rejects out-of-sample snapshots; evidence fitting uses only in-sample 2023–2025 `RACE_END` snapshots selected by the CLI; `tests/data/test_physics_input.py` and `tests/parameters/test_register.py` cover the boundary. |
| T-09-17 | High | Mitigated | Catalog audit compares all complete-race channel counts and the bounded Bahrain probe validates identity, inclusive time bounds, per-endpoint quality, and partial failure evidence; `tests/data/test_coverage_audit.py` covers the report. |
| T-09-SC | Low | Accepted | No dependency or package-manager changes were introduced; the phase uses the existing pytest, pandas, NumPy, and DuckDB stack. |

**Verdict:** SECURED at ASVS L1. There are no open threats at or above the configured high-severity block threshold. The low package-installation item is accepted in the Phase 9 plans and remains unchanged.
