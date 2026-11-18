---
phase: 10-point-mass-pacemodel
plan: 01
subsystem: pace-model
tags: [point-mass, pace-model, geometry, numpy, physical-forces]
requires:
  - phase: 09-data-and-geometry-readiness
    provides: digest-pinned geometry, cutoff-scoped PhysicsInput, parameter artifact references
provides:
  - Deterministic geometry-backed point-mass PaceModel using the existing prediction protocol
  - Bounded immutable per-driver physical scenarios and explicit compound grip multipliers
  - Closed-lap force envelope, speed solver, trapezoidal lap integration, and grid-refinement check
affects: [10-02-effective-fit, 10-03-synthetic-recovery, phase-11-tire-state, phase-12-hybrid-pace]
actuals:
  tokens: 7583
  tasks: 3
  commits: 4
  plan_head_before: 961d54bc50886e6a268c93b4d0a9137f5d122e31
  plan_head_after: f1ec19c68c87c3a8883881f0275d02fa56e88300
tech-stack:
  added: []
  patterns: [prepared immutable numerical inputs, cyclic quasi-static speed envelope, named bounded solver failure]
key-files:
  created: [src/f1si/pace/point_mass.py, tests/pace/test_point_mass.py]
  modified: [DECISIONS.md, .planning/config.json]
key-decisions:
  - DEC-145: bind prepared artifacts and explicit bounded scenarios before prediction
  - DEC-140/141: cyclic force envelope, 1e-5 m/s convergence, 1,000-pass cap, endpoint trapezoid, 0.1% refinement bound
patterns-established:
  - PointMassPaceModel predictions perform no I/O and preserve the existing vectorized PaceModel seam.
  - Geometry and solver arrays are immutable; bad physical ranges, artifact references, and locked races fail closed.
requirements-completed: [PHY-01, PHY-02]
coverage:
  - id: D1
    description: Predict deterministic finite mean and positive standard deviation arrays through the unchanged PaceModel interface.
    requirement: PHY-01
    verification:
      - kind: integration
        ref: tests/pace/test_point_mass.py::test_analytic_circle_deterministic_mean_sd_and_protocol
        status: pass
    human_judgment: false
  - id: D2
    description: Enforce bounded physical values, closed-lap force behavior, endpoint integration, seam closure, and cutoff-safe construction.
    requirement: PHY-02
    verification:
      - kind: unit
        ref: uv run pytest tests/pace/test_point_mass.py tests/conformance/test_protocols.py tests/geometry/test_profile.py -q
        status: pass
      - kind: unit
        ref: uv run mypy src/f1si/pace/point_mass.py
        status: pass
    human_judgment: false
duration: 19min
completed: 2026-11-18
status: complete
---

# Phase 10 Plan 01: Deterministic Point-Mass PaceModel Summary

**A prepared, geometry-driven point-mass model now returns deterministic lap-time means and declared uncertainty through the existing PaceModel contract.**

## Performance

- **Duration:** about 19 minutes
- **Tasks:** 3/3
- **Files changed:** 4
- **Ubuntu/Windows CI:** run for commit `3f8a355` was in progress when this summary was written.

## Accomplishments

- Added immutable per-driver scenarios with inclusive bounds for mass, fuel, fuel burn, power, drag, downforce, grip, and declared lap-time uncertainty.
- Added closed-lap acceleration/braking reachability with a speed-dependent force envelope, fixed convergence limits, finite straight terminal speed, and DEC-141 endpoint integration.
- Added a midpoint grid-refinement check and tests for protocol conformance, deterministic/batch-equivalent predictions, physical bounds, artifact matching, out-of-sample rejection, and future-row isolation.
- Left simulator, strategy, replay, backtest, and interface call sites unchanged. Added no packages and no UI work.
- Preserved the locked M1 baseline unchanged: podium Brier 0.055456 (grid 0.073693); top-10 Brier 0.144645 (grid 0.169086); inclusive P05–P95 coverage 82.26% (16,508/20,001); signed planned-stop timing error +1.174 laps; top-action agreement 17.22% (695 matched stops).

## Task Commits

1. **Task 1: Trace one analytic lap through the production PaceModel** — `2acf810` (`feat`)
2. **Task 2: Prove the cyclic force envelope and spatial integration** — `9895916` (`test`)
3. **Task 3: Lock fail-closed construction and shared protocol conformance** — `3f8a355` (`fix`), strict-mypy follow-up `f1ec19c` (`fix`)

## Files Created/Modified

- `src/f1si/pace/point_mass.py` — immutable prepared model, force solver, and lap integration.
- `tests/pace/test_point_mass.py` — analytic path, physical invariant, boundary, conformance, and cutoff tests.
- `DECISIONS.md` — DEC-145 records how scenarios, compound grip, fuel mass, and uncertainty are bound.
- `.planning/config.json` — records the user's explicitly approved main-branch workflow override required by the executor's commit guard.

## Decisions Made

- DEC-145 makes missing car/tire quantities explicit bounded scenarios and keeps tire wear unclaimed until the tire-state phase.
- DEC-140/141 provide the cyclic method and numerical limits; no additional dependencies or fitted absolute vehicle values were introduced.

## Deviations from Plan

**1. Execution configuration needed for the already authorized main-branch workflow.**
- **Found during:** Task 1
- **Issue:** The GSD commit guard blocks protected-branch commits unless `git.allow_default_branch_commits` is explicitly enabled; project configuration is `branching_strategy: none`, and the user authorized committing and pushing each task on main.
- **Fix:** Set `git.allow_default_branch_commits: true` in `.planning/config.json` and used the standard branch check before each task commit.
- **Files modified:** `.planning/config.json`
- **Verification:** The GSD protected-branch check returned `false`; all three task commits pushed successfully to `origin/main`.
- **Committed in:** `2acf810`

**2. [Rule 1 - Bug] Fixed strict-mypy failures reported by the first CI run.**
- **Found during:** Task 3 verification after push
- **Issue:** The new test helper annotations and dynamically parameterized `dataclasses.replace` calls failed the repository-wide strict mypy command on both CI platforms.
- **Fix:** Added explicit helper return annotations and typed the dynamic replacement call.
- **Files modified:** `tests/pace/test_point_mass.py`
- **Verification:** `uv run mypy`, the task verification suite, and ruff all pass locally; follow-up CI for `f1ec19c` is running.
- **Committed in:** `f1ec19c`

**Total deviations:** 1 configuration adjustment and 1 Rule 1 fix. **Impact:** Both were required to follow the authorized main-branch workflow and meet the repository's CI checks; model scope remains unchanged.

## Issues Encountered

- Initial red tests confirmed the production module was absent. The first green run exposed a test-side downforce-area unit mismatch; the fixture was aligned with the register's 200 km/h force-to-area conversion.
- GitHub CLI was not installed, so CI status was read through the public GitHub Actions API. Its first run found strict-mypy errors in the test file; the fix is pushed and its CI run is pending.

## User Setup Required

None.

## Next Phase Readiness

Plan 10-02 can now add the supported effective-term fit and deterministic uncertainty while using the prepared model seam. The model remains intentionally a scenario-based point-mass baseline; the planned fit and independent synthetic recovery are not yet complete.

---
*Phase: 10-point-mass-pacemodel*
*Completed: 2026-11-18*

## Self-Check: PASSED

- Production module, focused tests, and summary exist.
- Task commits `2acf810`, `9895916`, `3f8a355`, and `f1ec19c` are ancestors of HEAD.
