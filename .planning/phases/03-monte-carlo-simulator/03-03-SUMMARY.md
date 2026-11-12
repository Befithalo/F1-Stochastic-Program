---
phase: 03-monte-carlo-simulator
plan: 03
subsystem: sim
tags: [numba, sobol, antithetic, safety-car, overtaking, crn]
requires:
  - phase: 03-02
    provides: SC regime in RaceState, SimulationResult diagnostics
provides:
  - f1si.sim.constants (documented simulator constants)
  - f1si.sim.draws (Sobol/antithetic/iid blocks, make_streams for CRN)
  - f1si.sim.kernel (njit lap_step, pass_probability)
affects: [03-04, 03-05, 03-06, 03-07]
key-files:
  created:
    - src/f1si/sim/__init__.py
    - src/f1si/sim/constants.py
    - src/f1si/sim/draws.py
    - src/f1si/sim/kernel.py
    - tests/sim/__init__.py
    - tests/sim/test_draws.py
    - tests/sim/test_kernel.py
    - tests/sim/test_overtaking.py
  modified:
    - docs/explained/phase-03.md
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-078: dirty-air hold plus logistic pass chance"
  - "DEC-079: safety-car mechanics (frozen order, 1.4x leader time, restart compression, opportunistic stops)"
  - "DEC-080: Sobol+antithetic draw layout, per-lap spawned streams, CRN"
requirements-completed: []
completed: 2026-11-12
---

# Phase 3 Plan 03: Draw layer and lap kernel Summary

Scrambled-Sobol/antithetic draw layer with plan-independent per-lap streams, and a Numba lap-step kernel (pit loss, SC start/freeze/restart compression, dirty-air hold, logistic passing) equal to its pure-Python twin.

## Commits

- Task 1: dfd4348 - constants and draws
- Task 2: dd9994c - kernel, tests, DEC-078 to DEC-080 (MIN_ENTRIES = 80)

## Deviations from Plan

**1. [Rule 1 - plan inconsistency] Pass-curve constants moved to keep p(0) < 0.2 (orchestrator fix)**
- The plan's constants (THRESHOLD_S 0.3, SCALE_S 0.25) give p(0) = 0.231, so its "< 0.2" test could not hold. The executor first relaxed the test bound to 0.25; the orchestrator then reverted that and moved the curve instead (THRESHOLD_S 0.4, SCALE_S 0.2, p(0) = 0.119), because D-08 says equal pace rarely passes. Recorded in DEC-078; plan text updated.
- Files: tests/sim/test_overtaking.py

**2. [Minor] Kernel signature fixed by the executor**
- Argument order is documented in the `lap_step` docstring. Age table index is clamped to the last row to avoid out-of-range reads inside compiled code.

## Requirements

SIM-01, SIM-02, SIM-03 are not marked complete: they close after plans 03-04/03-05.

## Known Stubs

None (docs/explained/phase-03.md remains an intentional stub until 03-07).

## Verification

ruff check, ruff format, mypy strict pass; full suite 730 passed, 13 deselected.

## Self-Check: PASSED
