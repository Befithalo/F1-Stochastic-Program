---
phase: 10-point-mass-pacemodel
plan: 03
subsystem: pace
tags: [point-mass, synthetic-truth, identifiability, phase-report]
requires:
  - phase: 10-point-mass-pacemodel
    provides: deterministic point-mass PaceModel and cutoff-safe effective-scale fitting
provides:
  - Independent test-side point-mass truth generator and effective-scale recovery evidence
  - One-at-a-time physical and track-shape sensitivity checks
  - Fixed-baseline Phase 10 report with real-data limitations and CI evidence
affects: [phase-11-tire-state, phase-12-hybrid-pace]
actuals:
  tokens: 9100
  tasks: 3
  commits: 6
tech-stack:
  added: []
  patterns: [independent closed-form truth generation, identifiability-limited recovery, fixed-baseline closeout report]
key-files:
  created:
    - tests/pace/point_mass_truth.py
    - tests/pace/test_point_mass_recovery.py
    - tests/pace/test_point_mass_report.py
    - .planning/phases/10-point-mass-pacemodel/10-PHASE-REPORT.md
  modified:
    - src/f1si/pace/point_mass_fit.py
    - tests/pace/test_point_mass.py
    - tests/pace/test_point_mass_fit.py
    - docs/explained/phase-09.md
key-decisions:
  - "Independent synthetic evidence recovers only the declared effective power-to-mass scale; absolute vehicle values remain assumptions."
  - "Prepared completed PhysicsInput snapshots use their lap_end_s as the visibility cutoff when they have no visible_at_s field."
  - "Every driver scenario must match the prepared race season; compound grip inputs are normalized to stored floats."
  - "The real-data diagnostic is boundary-limited and retains its declared assumption instead of claiming a physical calibration."
patterns-established:
  - "Truth fixtures implement their own equations and do not call production solver or fitting helpers."
  - "A point-mass model binds scenario seasons to its prepared race, and the fitter retains a defensive per-driver season check."
  - "Reports copy fixed M1 values and disclose real-data, identifiability, runtime, and CI limits."
requirements-completed: [PHY-01, PHY-02]
coverage:
  - id: D1
    description: "Independent seeded synthetic trajectories recover only the identifiable effective scale within the inclusive five-percent tolerance."
    requirement: PHY-02
    verification:
      - kind: unit
        ref: "uv run pytest tests/pace/test_point_mass_recovery.py -q"
        status: pass
    human_judgment: false
  - id: D2
    description: "Independent parameter and track-shape changes preserve physical direction, cyclic closure, and geometry immutability."
    requirement: PHY-01
    verification:
      - kind: unit
        ref: "uv run pytest tests/pace/test_point_mass.py tests/pace/test_point_mass_recovery.py -k 'sensitivity or track_shape or recovery or invariant or adjacency' -q"
        status: pass
    human_judgment: false
  - id: D3
    description: "The phase report preserves the fixed M1 baseline and PAC-06 disclosure and records Phase 10 methods, assumptions, limits, and passing CI evidence."
    verification:
      - kind: unit
        ref: "uv run pytest tests/pace/test_point_mass_report.py -q"
        status: pass
      - kind: integration
        ref: "GitHub Actions CI run 44265729419 on commit 3712f759f0306767db2ebf515076c043603a0399 (Ubuntu and Windows)"
        status: pass
    human_judgment: false
  duration: 155min
completed: 2026-11-18
status: complete
---

# Phase 10 Plan 03: Independent Recovery and Closeout Summary

**Independent synthetic evidence verifies the identifiable pace scale, while the report keeps real-data limits and the fixed M1 baseline explicit.**

## Performance

- **Duration:** 155 minutes
- **Started:** 2026-11-18 07:26 UTC
- **Completed:** 2026-11-18 10:01 UTC
- **Tasks:** 3
- **Files modified:** 8 plan deliverables, plus the summary and GSD state metadata

## Accomplishments

- Added an independent, fixed-seed test-side truth generator. It computes closed-lap targets without production solver or fitting helpers and recovers the known effective scale to below 0.01% error over the predeclared `[1.0, 1.15]` fit interval.
- Verified unidentifiable cases retain the assumption, the 5% recovery boundary is inclusive, and one-at-a-time power, mass, drag, grip, downforce, and track-shape changes move the physical solution in the expected direction.
- Closed both standard-depth review findings: the model and fit reject cross-season scenarios, and numeric compound-grip values are normalized before storage.
- Published the Phase 10 report with exact copied M1 metrics and denominators, PAC-06 still unmet, DEC-140/141 methods, the unchanged 50,000-race budget, and the boundary-limited real-data diagnostic.

## Task Commits

1. **Tasks 1-2: independent truth, recovery, and physical sensitivities** - `676df7c`
2. **Prepared-input cutoff integration fix** - `80f0d14`, `77920aa`, `2335379`
3. **Documentation coverage fix** - `3712f75`
4. **Code-review fixes: season binding and grip normalization** - `f53183e`
5. **Task 3 report contract and final planning artifacts** - included in the final closeout commit

**Plan metadata:** included in the final closeout commit.

## Files Created/Modified

- `tests/pace/point_mass_truth.py` - independent analytic closed-lap generator and truth record.
- `tests/pace/test_point_mass_recovery.py` - recovery, identifiability, tolerance-boundary, and track-shape checks.
- `tests/pace/test_point_mass.py` - separate physical-parameter direction checks.
- `src/f1si/pace/point_mass_fit.py` and `tests/pace/test_point_mass_fit.py` - completed-snapshot visibility fallback and its regression.
- `tests/pace/test_point_mass_report.py` and `.planning/phases/10-point-mass-pacemodel/10-PHASE-REPORT.md` - report contract and closeout evidence.
- `docs/explained/phase-09.md` - added the two new pace modules to the file-by-file tour.

## Decisions Made

- Synthetic recovery is evidence for the one identifiable effective power-to-mass scale, not absolute engine, mass, aero, grip, fuel, or tire values.
- The real-data sample is a fit-path diagnostic only. Its boundary-limited result retains the declared scale assumption and emits no candidate or covariance.
- Completed prepared snapshots use `lap_end_s` as the cutoff visibility time when `visible_at_s` is absent.

## Deviations from Plan

### Auto-fixed integration issues

**1. Completed Phase 9 snapshots used a different visibility timestamp field.**
- **Found during:** Task 1 real-data fit-path diagnostic.
- **Issue:** Prepared `PhysicsInput` snapshots from the existing data path expose `lap_end_s`, so the fit otherwise discarded every eligible lap.
- **Fix:** Added a `lap_end_s` fallback and a regression test.
- **Verification:** The regression failed before the fix; point-mass fit tests and the full suite passed after the change, except for the subsequently fixed documentation coverage failure.
- **Committed in:** `80f0d14`, `77920aa`.

**2. A concrete `RaceEnd` type check crossed the prepared-input boundary.**
- **Found during:** Full-suite consumer import guard.
- **Issue:** Importing `RaceEnd` into the fit module violated the boundary enforced by the repository's consumer guard.
- **Fix:** Trust the immutable prepared `PhysicsInput` snapshot contract and remove the unnecessary concrete sentinel type check.
- **Verification:** The guard, point-mass fit tests, Ruff, and mypy passed; CI runs the full suite and canary.
- **Committed in:** `2335379`.

**3. The full-suite documentation tour did not list new modules.**
- **Found during:** Full-suite documentation coverage test.
- **Issue:** `test_tour_covers_every_module` reported the two new point-mass files as missing.
- **Fix:** Added both module descriptions to the Phase 9 explainer.
- **Verification:** All 30 documentation tests pass; CI run 44265729419 checks the complete suite on Ubuntu and Windows.
- **Committed in:** `3712f75`.

**4. **Code review found scenario-season and numeric-normalization gaps.**
- **Found during:** Required standard-depth Phase 10 code review.
- **Issue:** A model could fit a race using a driver scenario from another season, and float-convertible compound grip values were stored without normalization.
- **Fix:** Bind all scenarios to the prepared race season, retain a defensive fit-row season check, normalize compound-grip values once, and add regression tests.
- **Verification:** 47 focused point-mass tests pass; Ruff, formatting, and mypy pass. Full two-platform CI run #44275275671 passed on commit `f53183e`.
- **Committed in:** `f53183e`.

**Total deviations:** 4 corrective integration, documentation, and review fixes.
**Impact on plan:** Each fix was needed for Phase 10 integration, import boundaries, or repository-wide documentation completeness.

## Issues Encountered

The synthetic objective is piecewise flat outside its sensitivity region. The recovery fixture therefore records its fit bounds in advance and demonstrates recovery only inside `[1.0, 1.15]`; it does not claim global identifiability.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 10 provides a deterministic physical PaceModel and a test-backed effective-scale fit contract for Phase 11. Absolute car and tire quantities remain assumptions, and the separate 2026 report remains excluded from calibration and closeout.

---
*Phase: 10-point-mass-pacemodel*
*Completed: 2026-11-18*
