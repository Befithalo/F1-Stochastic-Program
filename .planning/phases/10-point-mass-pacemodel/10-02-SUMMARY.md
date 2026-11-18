---
phase: 10-point-mass-pacemodel
plan: 02
subsystem: pace
tags: [point-mass, effective-parameter-fit, uncertainty, cutoff-safety]
requires:
  - phase: 10-point-mass-pacemodel
    provides: deterministic cyclic point-mass PaceModel and validated physical scenarios
provides:
  - Cutoff-safe bounded fit report for the effective tractive-power-to-mass multiplier
  - Deterministic active-set checked parameter uncertainty and separately supported residual variance
  - Canonical, future-row-invariant fit diagnostics
affects: [phase-10-synthetic-recovery, phase-11, phase-12]
actuals:
  tokens: 13694
  tasks: 3
  commits: 5
tech-stack:
  added: []
  patterns: [bounded scalar fit with rank and condition gates, deterministic active-set checked uncertainty propagation]
key-files:
  created: [src/f1si/pace/point_mass_fit.py, tests/pace/test_point_mass_fit.py]
  modified: [src/f1si/pace/point_mass.py, tests/pace/test_point_mass.py]
key-decisions:
  - Only the common effective power-to-mass scale is fit; absolute vehicle and tire quantities remain sourced scenario assumptions.
  - Residual variance is reported only with at least 30 clean laps from at least three eligible races.
  - Inclusive cutoff filtering and canonical row sorting are enforced before objective construction.
patterns-established:
  - Fit reports retain explicit rank, condition, cutoff, support, and identifiability diagnostics.
  - Prediction uncertainty is deterministic and reports parameter and residual components separately.
requirements-completed: [PHY-01, PHY-02]
coverage:
  - id: D1
    description: Cutoff-safe fit of one identifiable effective power-to-mass multiplier, preserving assumptions when the candidate is unidentifiable or boundary-limited.
    requirement: PHY-02
    verification:
      - kind: unit
        ref: "uv run pytest tests/pace/test_point_mass_fit.py -k 'fit or identifiability or assumption' -q"
        status: pass
    human_judgment: false
  - id: D2
    description: Deterministic uncertainty propagation with independent parameter and residual variance diagnostics.
    requirement: PHY-01
    verification:
      - kind: unit
        ref: "uv run pytest tests/pace/test_point_mass.py tests/pace/test_point_mass_fit.py -q"
        status: pass
    human_judgment: false
  - id: D3
    description: Inclusive cutoff, future-row invariance, out-of-sample rejection, and row-order invariant fit reports.
    requirement: PHY-02
    verification:
      - kind: unit
        ref: "uv run pytest tests/pace/test_point_mass_fit.py -k 'cutoff or future_rows or permutation or out_of_sample' -q"
        status: pass
    human_judgment: false
duration: 20min
completed: 2026-11-18
status: complete
---

# Phase 10 Plan 02: Fit the Effective Pace Scale Summary

**The fit now identifies one cutoff-safe effective power-to-mass scale and reports deterministic uncertainty without treating hidden car values as measured.**

## Performance

- **Duration:** 20 minutes
- **Started:** 2026-11-18 07:05 UTC
- **Completed:** 2026-11-18 07:25 UTC
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added an immutable `PointMassFitReport` and bounded scalar fitting path over prepared 2023–2025 `PhysicsInput` snapshots, with rank/condition gates, inclusive-bound handling, and explicit unidentifiable outcomes.
- Added deterministic first-order and bounded symmetric sigma-point uncertainty propagation. Parameter covariance and residual variance remain separately inspectable; residual variance requires the declared 30-lap, three-race support.
- Verified inclusive cutoff equality, future-row perturbation invariance, out-of-sample rejection, and canonical row-order invariance.

## Task Commits

1. **Task 1 tests:** `f46c51b` (fit contract tests and RED evidence)
2. **Task 1 implementation:** `a850b95` (effective scale fit)
3. **Task 2 tests:** `36e69a4` (uncertainty branch tests and RED evidence)
4. **Task 2 implementation:** `246e85e` (deterministic uncertainty)
5. **Task 3 tests:** `a446078` (cutoff and row-order invariance)

## Files Created/Modified

- `src/f1si/pace/point_mass_fit.py` — fit report, cutoff-safe fit, identifiability, covariance, and residual-support diagnostics.
- `src/f1si/pace/point_mass.py` — effective-scale application and deterministic uncertainty propagation.
- `tests/pace/test_point_mass_fit.py` — fit, cutoff, identifiability, uncertainty, and residual support tests.
- `tests/pace/test_point_mass.py` — uncertainty branch tests.

## Decisions Made

Only the declared effective multiplier is eligible for fitting. Absolute power, mass, fuel, drag, downforce, grip, and tire values remain scenario assumptions. Residual variance remains unavailable below the preregistered support threshold.

## Deviations from Plan

Task 3's inclusive cutoff and canonical sorting behavior was already present from Task 1 because it is needed to produce deterministic fit diagnostics. Task 3 therefore added the planned regression tests without rewriting correct implementation. No scope or method deviation.

## Issues Encountered

None. The full plan test command passed: 31 tests passed, with one existing pandas deprecation warning.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Ready for 10-03: independent synthetic truth generation, recovery and sensitivity tests, and the fixed-baseline Phase 10 report. Phase 10 requirements remain shared with 10-03 and will be closed after that plan.

---
*Phase: 10-point-mass-pacemodel*
*Completed: 2026-11-18*