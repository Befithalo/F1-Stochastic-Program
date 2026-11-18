---
phase: 10-point-mass-pacemodel
reviewed: 2026-11-18T09:17:49Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - src/f1si/pace/point_mass.py
  - src/f1si/pace/point_mass_fit.py
  - tests/pace/test_point_mass.py
  - tests/pace/test_point_mass_fit.py
  - tests/pace/point_mass_truth.py
  - tests/pace/test_point_mass_recovery.py
  - tests/pace/test_point_mass_report.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-11-18T09:17:49Z  
**Depth:** standard  
**Files Reviewed:** 7  
**Status:** issues_found

## Summary

Reviewed the point-mass solver, effective-scale fitter, and their Phase 10 tests against the three plans and summaries. The fitter can use driver parameters declared for a different season than the training race, which can contaminate calibration; model construction also accepts numeric-like compound-grip values without storing their validated float conversion, so a value such as a numeric string fails later during prediction.

## Critical Issues

### CR-01: [BLOCKER] Fit accepts scenarios from a different season

**File:** `src/f1si/pace/point_mass_fit.py:153-156, 219-223`
**Issue:** Fit eligibility checks that a race is within 2023-2025 and that a driver has a scenario, but it never checks `scenario.season` against `race.season`. `PointMassPaceModel` likewise does not bind scenario seasons to `physics_input.race.season`. Consequently, a 2025 race can be fitted using 2023 assumptions, contrary to the plan's wrong-season rejection contract, and the resulting scale/covariance can be attributed to the wrong scenario.
**Fix:** Reject model construction when any scenario's season differs from the prepared race season, and retain a defensive check in `_eligible_rows` before accepting a driver's row. Add a regression using a supported race with a supported but mismatched scenario season; it should return an unidentifiable report or fail construction.

## Warnings

### WR-01: Compound-grip values are validated as floats but stored unconverted

**File:** `src/f1si/pace/point_mass.py:386-394`
**Issue:** The constructor calls `float(value)` to validate each multiplier, then stores the original object in `compound_grip`. Thus a float-convertible value such as `"1.1"` passes construction but later causes a `TypeError` in `predict` when multiplied by `scenario.grip_mu`. Normalize once and store the normalized floats, or reject values that are not actual supported numeric types.
**Fix:** Build the stored mapping as `{compound: float(value) ...}` after validation, then wrap that normalized mapping in `MappingProxyType`.

---

_Reviewed: 2026-11-18T09:17:49Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
