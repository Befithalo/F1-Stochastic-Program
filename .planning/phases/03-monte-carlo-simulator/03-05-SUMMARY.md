---
phase: 03-monte-carlo-simulator
plan: 05
subsystem: sim
tags: [benchmark, variance-reduction, sobol, antithetic]
requires:
  - phase: 03-04
    provides: NumpySimulator
provides:
  - tests/sim/test_benchmark.py (SIM-02)
  - tests/sim/test_variance_reduction.py (SIM-03)
  - DEC-083, DEC-084
affects: [03-06, 03-07]
key-files:
  created:
    - tests/sim/test_benchmark.py
    - tests/sim/test_variance_reduction.py
  modified:
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-083: Sobol+antithetic variance ratios measured over 120 seeds"
  - "DEC-084: 50,000 x 20 x 57 benchmark, warm-up excluded"
requirements-completed: [SIM-02, SIM-03]
completed: 2026-11-12
---

# Phase 3 Plan 05: Benchmark and variance reduction Summary

SIM-02 and SIM-03 are proven by default-selection tests: 50,000 races (20 cars, 57 laps) take about 1.4 s, and Sobol plus antithetic sampling has 3 to 16 times lower estimator variance than plain Monte Carlo.

## Commits

- Task 1: ca01afc - benchmark test
- Task 2: 71030be - variance-reduction test, DEC-083, DEC-084 (MIN_ENTRIES = 84)

## Measurements (local)

- Benchmark, 50,000 races, warm-up excluded: 1.448, 1.380, 1.494 s (budget 10 s, about 6x headroom). No source optimisation was needed; `numpy_backend.py` and `draws.py` are unchanged.
- Variance ratios var(none)/var(sobol_antithetic), R = 120, N = 1024, 10 cars, 30 laps: mean finish 4.54, mean total time 16.43, SC share 3.19, P(top 5) 4.22 (report only).
- Asserted margins (about 75% of measured): 3.4, 12.0, 2.4.

## Deviations from Plan

**1. [Test design] The variance state is made contested**
- The default synthetic grid has pace offsets sorted by grid slot, so nobody passes and finishing positions are deterministic (estimator variance 0, ratio meaningless). The test state uses 0.5 s gaps and mixed pace offsets (SD 0.2 s). Not a weakening: margins are well above the plan's floors (1.10, 1.10, 1.5).

**2. [Minor] Benchmark SC-share assertion is 0.1 absolute, not 0.03**
- Safety cars cannot start during an active SC, so the share is below `1 - 0.99**57`; the test asserts the share lies in (0.2, 0.5) and within 0.1 of the naive value. Looser than the plan's 0.03.

**3. [Finding] P(top 5) also benefits (4.22)**
- RESEARCH Pitfall 8 expected little gain; it stays report-only as planned, and DEC-083 notes it.

## Known Stubs

None.

## Threat Flags

None.

## Verification

ruff check, ruff format --check, mypy strict pass; full suite 767 passed, 15 deselected (`-k "not network"`). CI timings on Ubuntu and Windows remain a manual verifier check.

## Self-Check: PASSED
