---
phase: 10-point-mass-pacemodel
verified: 2026-11-18T10:02:09Z
status: passed
score: 17/17 must-haves verified
covered_files:
  - .planning/phases/10-point-mass-pacemodel/10-01-PLAN.md
  - .planning/phases/10-point-mass-pacemodel/10-01-SUMMARY.md
  - .planning/phases/10-point-mass-pacemodel/10-02-PLAN.md
  - .planning/phases/10-point-mass-pacemodel/10-02-SUMMARY.md
  - .planning/phases/10-point-mass-pacemodel/10-03-PLAN.md
  - .planning/phases/10-point-mass-pacemodel/10-03-SUMMARY.md
  - .planning/phases/10-point-mass-pacemodel/10-PHASE-REPORT.md
  - .planning/phases/10-point-mass-pacemodel/10-REVIEW-DISPOSITION.md
  - .planning/phases/10-point-mass-pacemodel/10-REVIEW.md
  - .planning/phases/10-point-mass-pacemodel/10-SECURITY.md
  - .planning/phases/10-point-mass-pacemodel/10-VALIDATION.md
  - docs/explained/phase-09.md
  - src/f1si/pace/point_mass.py
  - src/f1si/pace/point_mass_fit.py
  - tests/pace/point_mass_truth.py
  - tests/pace/test_point_mass.py
  - tests/pace/test_point_mass_fit.py
  - tests/pace/test_point_mass_recovery.py
  - tests/pace/test_point_mass_report.py
covered_digest: "v3:sha256:ee03aefb2b3864882f8f3b4ec54cec0ad8f0b2108b3e544737c07ff9b016310b"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 10: Point-Mass PaceModel Verification Report

**Phase Goal:** Users can obtain a deterministic geometry-driven lap-time mean and uncertainty through the existing PaceModel contract, with identifiable effective inputs and physical behavior independently checked.

**Verified:** 2026-11-18T10:02:09Z  
**Status:** passed  
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Callers can request deterministic lap-time means and uncertainty through the existing PaceModel contract using geometry, effective power, drag, downforce, grip, and declared mass/fuel inputs. | VERIFIED | `PointMassPaceModel.predict` computes arrays from the prepared `PhysicsInput`; `test_analytic_circle_deterministic_mean_sd_and_protocol` verifies shape, finite deterministic output, and protocol conformance. |
| 2 | Known synthetic trajectories recover identifiable parameters within tolerance, and physical invariants and independent sensitivities behave as documented. | VERIFIED | `test_independent_truth_recovers_only_effective_scale_within_five_percent`, `test_one_at_a_time_physical_sensitivities_preserve_expected_direction`, and `test_track_shape_curvature_change_changes_closed_lap_without_mutating_source` pass. |
| 3 | A caller can construct an immutable geometry-backed PaceModel and receive deterministic finite mean and standard-deviation arrays with the existing input shape. | VERIFIED | `PointMassPaceModel` and parameter records are frozen; `test_analytic_circle_deterministic_mean_sd_and_protocol` and `test_empty_batch_and_unknown_identifiers_fail_closed` exercise shape, repeatability, and empty input behavior. |
| 4 | The cyclic speed envelope converges within the declared tolerance, respects the force envelope, and integrates travel time using the declared trapezoid rule. | VERIFIED | `test_profile_counts_closed_seam_once_and_refinement_is_bounded` and `test_solver_force_envelope_and_segment_integration` exercise closure, refinement, force limits, and segment integration. |
| 5 | Model construction binds digest-validated geometry, cutoff-scoped physics input, and season-matched scenarios before prediction. | VERIFIED | Constructor checks artifact references and race/scenario season equality; `test_point_mass_references_must_match`, `test_model_rejects_vehicle_scenario_from_another_season`, and `test_out_of_sample_physics_input_is_rejected` cover the boundary. |
| 6 | Physical bounds are inclusive, the next representable value outside fails, empty predictions preserve float64 shape, and numerical values remain finite SI values. | VERIFIED | `test_physical_scenario_bounds_are_inclusive_and_next_float_fails`, `test_empty_batch_and_unknown_identifiers_fail_closed`, and the seeded truth generator's SI contract test exercise these conditions. |
| 7 | Adjacent intervals share one endpoint, the seam is counted once, and zero-length intervals are rejected. | VERIFIED | `test_profile_counts_closed_seam_once_and_refinement_is_bounded` and the GeometryProfile validation suite cover cyclic adjacency and degenerate intervals. |
| 8 | Only the declared effective tractive-power-to-mass scale is fitted, and rank/condition failures remain explicitly unidentifiable. | VERIFIED | `fit_effective_power_mass_scale` exposes one candidate term; `test_rank_deficient_panel_is_unidentifiable_and_keeps_assumption` and `test_empty_panel_is_explicitly_unidentifiable_and_keeps_assumption` exercise the gates. |
| 9 | Absolute vehicle, fuel, drag, downforce, and grip values remain scenario assumptions rather than team-specific recovered values. | VERIFIED | Fit output lists absolute assumptions; `test_fit_report_keeps_absolute_vehicle_terms_as_assumptions` asserts no result or classification fields leak into serialized diagnostics. The report labels its values as analyst assumptions. |
| 10 | Standard deviation is deterministic and separates supported parameter uncertainty from residual variance. | VERIFIED | `test_first_order_uncertainty_reports_separate_deterministic_components`, `test_active_set_change_selects_bounded_sigma_points`, and residual-support tests cover both uncertainty branches and their support limits. |
| 11 | The fit uses only visible, in-sample 2023–2025 training laps at the supplied cutoff and excludes outcomes, future rows, 2026 data, and holdout targets. | VERIFIED | `_eligible_rows` checks out-of-sample status, season, visibility timestamp, and cutoff. `test_cutoff_equality_is_included_and_reported`, `test_post_cutoff_rows_and_values_leave_fit_report_unchanged`, and `test_fit_rejects_races_outside_the_training_seasons` pass; source imports no results/classification module. |
| 12 | Empty panels and inclusive-bound optima are classified explicitly, and row permutation leaves canonical diagnostics unchanged. | VERIFIED | `test_empty_panel_is_explicitly_unidentifiable_and_keeps_assumption`, `test_bound_optimum_is_boundary_limited_and_does_not_replace_assumption`, and `test_training_row_and_model_permutation_leave_report_unchanged` pass. |
| 13 | Synthetic truth is generated by independent test-side equations and recovers only the registered identifiable multiplier. | VERIFIED | `point_mass_truth.py` defines its own constant-curvature force balance and imports no production solver or fit code; seeded recovery and unexcited-truth tests pass. |
| 14 | Independent parameter and track-shape changes, grid refinement, and closed-loop behavior are reproducible without using production code to create truth data. | VERIFIED | Physical sensitivity, curvature-shape, seam, refinement, and recovery tests pass using the independent truth fixture. |
| 15 | The Phase 10 report preserves the fixed M1 baseline and denominators, PAC-06 disclosure, assumptions and identifiability limits, the 50,000-race budget, and passing Ubuntu/Windows CI evidence. | VERIFIED | All three `test_point_mass_report.py` contract tests pass; the report links green run #44275275671 on code commit `f53183e` for Ubuntu and Windows. |
| 16 | Recovery accepts relative error at or below 5%, uses finite SI float64 values and a fixed seed, and makes no claim for unidentifiable terms. | VERIFIED | `test_truth_generator_is_independent_seeded_and_records_si_contract`, `test_five_percent_recovery_boundary_is_inclusive`, and `test_unexcited_truth_returns_unidentifiable_without_an_arbitrary_estimate` pass. |
| 17 | Adjacent intervals close once and canonical ordering makes fit diagnostics invariant to training-row permutations. | VERIFIED | `test_profile_counts_closed_seam_once_and_refinement_is_bounded` and `test_training_row_and_model_permutation_leave_report_unchanged` pass. |

**Score:** 17/17 truths verified (0 present, behavior-unverified)

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/f1si/pace/point_mass.py` | Deterministic solver, immutable model, and uncertainty propagation | VERIFIED | Constructor, cyclic envelope, lap integration, `predict`, and uncertainty paths are implemented and exercised. |
| `src/f1si/pace/point_mass_fit.py` | Cutoff-safe effective-scale fit with identifiability diagnostics | VERIFIED | One-term bounded fit, season/cutoff filtering, rank/condition checks, and residual support gates are wired. |
| `tests/pace/point_mass_truth.py` | Independent synthetic truth generator | VERIFIED | Standalone test-side equations and seeded SI truth records. |
| `tests/pace/test_point_mass.py` | Solver, physical, uncertainty, and PaceModel contract checks | VERIFIED | Named behavior tests cover construction through prediction. |
| `tests/pace/test_point_mass_fit.py` | Cutoff, identifiability, covariance, and fit boundary checks | VERIFIED | Named behavior tests cover filtering and reports. |
| `tests/pace/test_point_mass_recovery.py` | Independent recovery and sensitivity checks | VERIFIED | Fixed-seed recovery, tolerance boundary, and unidentifiable cases pass. |
| `tests/pace/test_point_mass_report.py` | Fixed baseline and disclosure contract | VERIFIED | 3 tests pass against the final report text. |
| `.planning/phases/10-point-mass-pacemodel/10-PHASE-REPORT.md` | Evidence-backed phase report | VERIFIED | Fixed M1 metrics, PAC-06 status, limitations, method, runtime, and final code CI are recorded. |
| `docs/explained/phase-09.md` | File tour coverage for new modules | VERIFIED | Both new point-mass modules are documented; the documentation suite passed. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `PointMassPaceModel` construction | `GeometryProfile`, `PhysicsInput`, `PointMassParameters` | Reference, cutoff, season, and scenario checks | VERIFIED | The model validates the prepared artifacts and binds a matching scenario set before prediction. |
| `PointMassPaceModel.predict` | Cyclic envelope and lap integration | Per-row inputs select scenario, compound grip, mass/fuel, and call the numerical path | VERIFIED | Returned means and standard deviations preserve input row order and shape. |
| `fit_effective_power_mass_scale` | `PhysicsInput.laps` and `PointMassPaceModel` | `_eligible_rows` filters eligible rows; `_lap_prediction` evaluates the one-dimensional candidate | VERIFIED | Exact-cutoff rows are retained; future/out-of-range rows are excluded. |
| Independent truth generator | Effective-scale fitter | Independently computed targets and preregistered fit bounds | VERIFIED | The truth module imports no production pace solver or fitting helper. |
| Phase report | Locked M1 baseline and final code CI | Fixed copied values plus linked CI run | VERIFIED | Report contract tests enforce the exact baseline, disclosures, and CI links. |

## Data-Flow Trace

| Artifact | Data variable | Source | Produces real data | Status |
|---|---|---|---|---|
| `PointMassPaceModel.predict` | Geometry arrays, driver/compound/tire inputs, deterministic mean and SD | Prepared geometry, `PhysicsInput`, and declared scenario parameters | Uses validated track/input records and analyst scenario assumptions | VERIFIED |
| Fit pipeline | Visible lap observations, candidate effective scale, diagnostics | Cutoff-scoped 2023–2025 `PhysicsInput` snapshots | Yes, only eligible training observations | VERIFIED |
| Synthetic recovery | SI lap targets and known effective scale | Independent fixed-seed test generator | No; synthetic | VERIFIED |

## Behavioral Spot-Checks

| Behavior | Command or evidence | Result | Status |
|---|---|---|---|
| Point-mass solver, fit, recovery, and report contract | `uv run pytest tests/pace/test_point_mass.py tests/pace/test_point_mass_fit.py tests/pace/test_point_mass_recovery.py tests/pace/test_point_mass_report.py -q` | 47 passed, 1 warning | VERIFIED |
| Updated report contract | `uv run pytest tests/pace/test_point_mass_report.py -q` | 3 passed | VERIFIED |
| Full Linux checks | GitHub Actions run #44275275671 | Ruff, formatting, mypy, full pytest, and canary succeeded | VERIFIED |
| Full Windows checks | GitHub Actions run #44275275671 | Ruff, formatting, mypy, and full pytest succeeded; Linux-only canary skipped | VERIFIED |

## Requirements Coverage

| Requirement | Source plan | Description | Status | Evidence |
|---|---|---|---|---|
| PHY-01 | 10-01, 10-02, 10-03 | Deterministic lap-time mean and uncertainty through PaceModel with physical inputs | VERIFIED | Prediction, cyclic physics, deterministic uncertainty, and report contract tests pass. |
| PHY-02 | 10-01, 10-02, 10-03 | Identifiable parameter recovery and independently checked physical behavior | VERIFIED | Cutoff/identifiability, independent recovery, sensitivity, and closure tests pass. |

## Anti-Patterns Found

None in the changed implementation or test paths. Fit code reads prepared pace inputs and does not import results/classification artifacts; the review’s season-binding and grip-normalization findings are fixed and recorded in `10-REVIEW-DISPOSITION.md`.

## Human Verification Required

None. All phase truths are covered by deterministic behavior tests and machine-reported CI.

## Gaps Summary

No phase-goal or plan must-haves remain open. The real-data diagnostic is boundary-limited and preserves its declared scale assumption; absolute vehicle values remain assumptions. These are documented model limits, not missing behavior in the phase goal.

---

_Verified: 2026-11-18T10:02:09Z_  
_Verifier: Codex (inline GSD verifier workflow)_
