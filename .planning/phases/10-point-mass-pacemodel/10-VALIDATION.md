---
phase: "10"
slug: "point-mass-pacemodel"
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-17"
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + Hypothesis |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/pace/test_point_mass.py tests/pace/test_point_mass_fit.py tests/pace/test_point_mass_recovery.py tests/pace/test_point_mass_report.py -q` |
| **Full suite command** | `uv run pytest --cov=f1si --cov-report=term` |
| **Estimated runtime** | Target under 60 seconds for focused point-mass tests; full-suite runtime is CI measured. |

## Sampling Rate

- **After every task commit:** Run the focused tests listed in the task's verification.
- **After every plan wave:** Run `uv run pytest tests/pace tests/conformance -q`.
- **Before phase closeout:** Full Ubuntu and Windows CI suites must pass.
- **Max feedback latency:** 60 seconds for focused tests.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-T01 | 10-01 | 1 | PHY-01 | T-10-01 | Model construction validates geometry/parameter refs and explicit SI scenarios; invalid inputs fail closed. | end-to-end | `uv run pytest tests/pace/test_point_mass.py -k "analytic_circle or deterministic_mean_sd or invalid_scenario" -q` | Yes | pass |
| 10-01-T02 | 10-01 | 1 | PHY-01 | T-10-03 | Closed-lap passes have a fixed iteration ceiling and enforce physical speed/force bounds. | physical invariant | `uv run pytest tests/pace/test_point_mass.py -k "cyclic or curvature_cap or force_envelope or interval_refinement" -q` | Yes | pass |
| 10-01-T03 | 10-01 | 1 | PHY-01, PHY-02 | T-10-02 | The unchanged PaceModel contract uses prepared immutable inputs; adjacent geometry closes once and degenerate intervals fail validation. | conformance/adjacency | `uv run pytest tests/pace/test_point_mass.py tests/conformance/test_protocols.py tests/geometry/test_profile.py -q` | Yes | pass |
| 10-02-T01 | 10-02 | 2 | PHY-01, PHY-02 | T-10-05 | Only the declared effective composite can be fit; empty panels and bound optima remain explicitly unidentifiable/boundary-limited. | fit/identifiability/boundary | `uv run pytest tests/pace/test_point_mass_fit.py -k "fit or identifiability or assumption" -q` | Yes | pass |
| 10-02-T02 | 10-02 | 2 | PHY-01 | T-10-06 | Parameter and residual variance remain separate and uncertainty method follows active-set plus 10% regime checks. | uncertainty | `uv run pytest tests/pace/test_point_mass.py tests/pace/test_point_mass_fit.py -k "uncertainty or active_set or residual_support" -q` | Yes | pass |
| 10-02-T03 | 10-02 | 2 | PHY-02 | T-10-04 | Exact-cutoff rows are allowed, future rows are inert, out-of-sample races are rejected, and fit output is row-order invariant. | cutoff/order property | `uv run pytest tests/pace/test_point_mass_fit.py -k "cutoff or future_rows or out_of_sample or row_order" -q` | Yes | pass |
| 10-03-T01 | 10-03 | 3 | PHY-02 | T-10-07 | Independent fixed-seed truth generation accepts recovery error at or below 5% and rejects unidentifiable recovery. | synthetic recovery/boundary | `uv run pytest tests/pace/test_point_mass_recovery.py -q` | Yes | pass |
| 10-03-T02 | 10-03 | 3 | PHY-02 | T-10-08 | One-at-a-time track/parameter sensitivity and physical invariants have documented directions; adjacent intervals close once. | metamorphic/adjacency | `uv run pytest tests/pace/test_point_mass.py tests/pace/test_point_mass_recovery.py -k "sensitivity or track_shape or recovery or invariant or adjacency" -q` | Yes | pass |
| 10-03-T03 | 10-03 | 3 | PHY-01, PHY-02 | T-10-09 | The report copies the locked M1 baseline, preserves PAC-06, confirms the budget, and records final two-platform CI evidence. | report contract | `uv run pytest tests/pace/test_point_mass_report.py -q` | Yes | pass |

## Requirement Edge Coverage

Shape overrides in DEC-142: PHY-01 is `numeric-range` (the existing PaceModel conformance suite owns vector order/shape); PHY-02 is `numeric-range` plus `collection` (bounded estimates over ordered lap/track sequences). The deterministic edge probe reports 7 applicable, 7 resolved, 0 unresolved, and 0 unclassified.

| Requirement / category | Predicate | Evidence and reason | Task |
|---|---|---|---|
| PHY-01 / boundary | Inclusive declared parameter bounds pass; the next representable float outside fails before solving. | D-05 and DEC-141 bounded scenario validation. | 10-01-T01 |
| PHY-01 / precision | Finite SI float64, no implicit rounding, finite straight terminal speed, endpoint reciprocal-speed trapezoid, 1e-5 m/s convergence, and at most 0.1% grid change. | D-01, D-03, DEC-140, DEC-141. | 10-01-T02 |
| PHY-02 / boundary | Fit optimum at an inclusive endpoint is `boundary_limited`; only recovery error up to 5% is accepted. | D-02, DEC-141, DEC-142; no boundary value is claimed recovered. | 10-02-T01, 10-03-T01 |
| PHY-02 / adjacency | Spatial intervals share endpoints, seam is counted once, zero-length intervals fail, and lap identities remain stable. | D-01 and Phase 9 GeometryProfile validation. | 10-01-T02, 10-01-T03, 10-03-T02 |
| PHY-02 / empty | Empty prediction batches return empty float64 arrays; one-row batches return one row; empty fit panels are unidentifiable. | Vectorized PaceModel contract and synthetic-fit scope. | 10-01-T01, 10-02-T01 |
| PHY-02 / ordering | Predictions preserve input order; canonical race/lap/driver ordering makes fit output invariant to row permutations. | D-03 deterministic prediction and ordered lap sequences. | 10-02-T03 |
| PHY-02 / precision | Fixed-seed independent truth uses finite SI float64 and the inclusive 5% recovery tolerance. | D-04 and DEC-141 recovery threshold. | 10-03-T01 |

## Wave 0 Requirements

- [x] `tests/pace/test_point_mass.py` - end-to-end, convergence, physical bounds, uncertainty, and PaceModel conformance for PHY-01.
- [x] `tests/pace/test_point_mass_fit.py` - effective-term identifiability, cutoff-boundary, future-row, and uncertainty-support tests for PHY-01/PHY-02.
- [x] `tests/pace/point_mass_truth.py` and `tests/pace/test_point_mass_recovery.py` - independent test-side generator and identifiable-term recovery/sensitivity coverage for PHY-02.
- [x] `tests/pace/test_point_mass_report.py` - exact M1 baseline and closeout disclosure contract.
- [x] Existing `tests/conformance/test_protocols.py` - shared PaceModel protocol suite is available for reuse.

## Manual-Only Verifications

None. Ubuntu and Windows CI status is machine-reported by the repository workflow and recorded for the final implementation commit.

## Validation Sign-Off

- [x] All final plan tasks have an automated command and a concrete failure condition.
- [x] All nine plan/task IDs and waves are represented in this map.
- [x] Wave 0 covers all new point-mass test files.
- [x] No watch-mode flags.
- [x] Focused feedback latency target is under 60 seconds.
- [x] `nyquist_compliant: true` is set after the final task/test map was validated.
- [x] Ubuntu and Windows CI are green for final implementation commit `f53183e` (run #44275275671).

**Approval:** validation complete; all task checks pass and both CI platforms are green on `f53183e`.

## Validation Audit 2026-11-18

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
