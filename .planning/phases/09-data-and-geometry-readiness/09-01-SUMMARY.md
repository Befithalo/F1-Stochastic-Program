---
phase: 09-data-and-geometry-readiness
plan: 01
subsystem: testing
tags: [pytest, physics-input, geometry, parameters, nyquist]

# Dependency graph
requires: []
provides:
  - Collection-ready cutoff, provenance, catalog-audit, and bounded-probe acceptance contracts
  - Collection-ready geometry digest, confinement, and quality acceptance contracts
  - Collection-ready effective-parameter, assumption, sensitivity, and closeout contracts
affects: [09-02, 09-03, 09-04]

# Actuals
actuals:
  tokens: 6900
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns: ["Import production APIs inside test bodies so Wave 0 contracts collect before implementation"]

key-files:
  created:
    - tests/data/test_physics_input.py
    - tests/data/test_coverage_audit.py
    - tests/geometry/test_profile.py
    - tests/parameters/test_register.py
  modified:
    - .planning/phases/09-data-and-geometry-readiness/09-VALIDATION.md

key-decisions:
  - "Use collection-only verification in Wave 0; later implementation plans turn the contracts green."
  - "Exercise the public RaceSnapshot and PhysicsInput boundary, with exact-cutoff inclusion and future-row perturbation invariance."

patterns-established:
  - "Optional input and geometry contracts import not-yet-created APIs only inside test functions."
  - "Use temporary synthetic geometry bytes for digest and quality failures; do not copy the candidate track asset into tests."

requirements-completed: [DAT-01, GEO-01, PAR-01]

coverage:
  - id: D1
    description: "Cutoff-safe PhysicsInput, channel provenance, fallback, catalog audit, and bounded Bahrain probe contracts collect."
    requirement: DAT-01
    verification:
      - kind: unit
        ref: "uv run pytest tests/data/test_physics_input.py tests/data/test_coverage_audit.py --collect-only -q"
        status: pass
    human_judgment: false
  - id: D2
    description: "Versioned geometry provenance, digest, confinement, and quality contracts collect."
    requirement: GEO-01
    verification:
      - kind: unit
        ref: "uv run pytest tests/geometry/test_profile.py --collect-only -q"
        status: pass
    human_judgment: false
  - id: D3
    description: "Effective-versus-assumed parameters, evidence sensitivity, and exact closeout-baseline contracts collect."
    requirement: PAR-01
    verification:
      - kind: unit
        ref: "uv run pytest tests/parameters/test_register.py --collect-only -q"
        status: pass
    human_judgment: false

# Metrics
duration: 11min
completed: 2026-11-17
status: complete
---

# Phase 9 Plan 01 Summary

**All three Phase 9 acceptance suites now collect before implementation begins.**

## Performance

- **Duration:** about 11 minutes
- **Tasks:** 3
- **Files created:** 4 test modules
- **Acceptance cases collected:** 32

## Accomplishments

- Added cutoff visibility, timestamp provenance, immutable prepared-input, fallback, and results/holdout boundary contracts.
- Added all-catalog channel totals and a one-session, three-channel Bahrain probe contract with explicit unavailable reporting.
- Added geometry digest, path confinement, units, loop, finite-coordinate, width, distance, and curvature failure contracts.
- Added fitted-effective versus hidden-assumption, uncertainty, numeric sensitivity, and exact M1 closeout-baseline contracts.
- Marked Wave 0 green and Nyquist compliant in `09-VALIDATION.md`.

## Task Commits

1. **Task 1: Define cutoff-safe PhysicsInput and coverage contracts** — `4ba5bc6`, followed by coverage edge-case completion in `090faa0`.
2. **Task 2: Define Bahrain profile integrity contracts** — `66368f1`, followed by geometry edge-case completion in `090faa0`.
3. **Task 3: Define parameter register and sensitivity contracts** — `06faef7`, followed by closeout-contract completion in `090faa0`.

## Verification

- `uv run pytest tests/data/test_physics_input.py tests/data/test_coverage_audit.py --collect-only -q` — **9 collected**.
- `uv run pytest tests/geometry/test_profile.py --collect-only -q` — **13 collected**.
- `uv run pytest tests/parameters/test_register.py --collect-only -q` — **10 collected**.
- `uv run ruff check` on all changed Python files — **passed**.
- `uv run ruff format --check` on all changed Python files — **passed**.
- Evaluation-scope check for plan 09-01 — **passed**, with four task commits found.

## Deviations and Issues

- Contract edge cases were strengthened after the first collection pass; all remain collection-only until plans 09-02 through 09-04 provide their APIs.
- The M1 CI failure exposed stale executable paths to evaluation locks after milestone archiving. The code and test references were corrected in separate prerequisite commit `f923e66`; all 89 focused backtest tests passed afterward.
- A pre-fix full-suite run is still in progress. It predates the archive-path correction and is not counted as post-fix validation; the full suite will be run again at the Phase 9 gate.

## Self-Check: PASSED

- All four created test modules exist and collect the expected 32 cases.
- The three verification commands listed above pass.
- The plan scope check found task commits on the current branch.

## Next Plan Readiness

Plan 09-02 can implement the prepared input, optional channel path, catalog audit, and bounded Bahrain probe against these contracts. Geometry and parameter suites are ready for plans 09-03 and 09-04.

---
*Plan: 09-01*
*Completed: 2026-11-17*
