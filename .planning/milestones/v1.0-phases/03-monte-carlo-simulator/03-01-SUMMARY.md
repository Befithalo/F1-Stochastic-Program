---
phase: 03-monte-carlo-simulator
plan: 01
subsystem: regime
tags: [scipy, numba, safety-car, beta-binomial, synthetic-data]
requires:
  - phase: 02
    provides: History door, synthetic generator, scramble guard
provides:
  - scipy, numba, scipy-stubs locked in uv.lock
  - Synthetic generator safety-car spec (sc_laps, sc_duration_laps, sc_slowdown_factor)
  - estimate_sc_rate(History) -> ScRateEstimate (REG-01)
  - sc_history_db fixture and sc_rate scramble consumer
affects: [03-02, 03-03, 03-04, 03-05, 03-06, 03-07]
tech-stack:
  added: [scipy 1.18.1, numba 0.68.1, llvmlite 0.50.0, scipy-stubs 1.18.1.1]
  patterns: [frozen estimate dataclass with prior-only flag, default fixtures pinned by SHA-256]
key-files:
  created:
    - src/f1si/regime/__init__.py
    - src/f1si/regime/sc_rate.py
    - tests/regime/test_sc_rate.py
    - tests/guards/test_sc_rate_scramble.py
    - docs/explained/phase-03.md
  modified:
    - pyproject.toml
    - uv.lock
    - src/f1si/synthetic/generator.py
    - tests/conftest.py
    - tests/test_synthetic.py
    - tests/guards/consumers.py
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-074: scipy, numba, scipy-stubs; Numba lap kernel allowed"
  - "DEC-075: Beta(3, 297) prior, edge-rule deployments, median duration with fallback 4"
requirements-completed: [REG-01]
duration: ~1h
completed: 2026-11-12
---

# Phase 3 Plan 1: Safety-car rate (REG-01) Summary

Beta-Binomial per-lap safety-car rate and median duration estimated from earlier races only, with scipy/numba locked and a safety-car spec added to the synthetic generator.

## Tasks

| Task | Commit | Result |
|------|--------|--------|
| 1. scipy, numba, scipy-stubs, DEC-074 | 178e8cc | Locked; Sobol and njit smoke check pass from the project .venv; mypy strict still passes |
| 2. Generator SC spec, SC-history fixture | 7f04d33 | Status "4" rows, race-control row, 1.4x laps; default fixtures byte-identical (digests pinned before the edit) |
| 3. estimate_sc_rate, tests, consumer, explainer, DEC-075 | ada7c04 | 7 behaviors tested; scramble consumer registered |

## Deviations from Plan

**1. [Rule 1 - test design] Recovery test uses 100-lap races, not 40-lap races**
- **Found during:** Task 3
- **Issue:** With 24 races x 40 laps (920 laps), the prior Beta(3, 297) still shrinks the posterior toward 1%, and the 90% interval contained the true 2.5% in only 3 of 5 seeds. Estimator behaves as designed (shrinkage), the test sample was too small.
- **Fix:** 24 races x 100 laps x 4 drivers (2300 laps in history); one-lap SCs (sc_duration_laps=1) so deployments per race lap are exactly i.i.d. Bernoulli(0.025) and cannot overlap. Result: 5 of 5 seeds covered. Logged in DEC-075. The 24-race and 4-driver sizes are as planned.
- **Files:** tests/regime/test_sc_rate.py

**2. [Minor] Digest function includes table names**
- The pinned SHA-256 digests hash table name plus `hash_pandas_object` bytes per table (sorted by name); `np.asarray(...)` is used so mypy strict accepts `.tobytes()`.

**3. [Minor] Duration clipped to at least 1 lap, lower median**
- A measured SC shorter than one leader lap counts as 1; the median of an even count is the lower middle value (an observed length). Both documented in the module docstring.

## Local environment

scipy and numba import and run from the project .venv on this machine (no Application Control block). CI (Ubuntu and Windows) remains the real gate and has not run yet for these commits (assumption A5).

## Known Stubs

docs/explained/phase-03.md is an intentional stub completed in plan 03-07.

## Verification

`uv run ruff check .`, `uv run ruff format --check .`, `uv run python -m mypy` pass; full suite 700 passed, 13 deselected (network).

## Self-Check: PASSED

Files exist (sc_rate.py, test_sc_rate.py, test_sc_rate_scramble.py, phase-03.md); commits 178e8cc, 7f04d33, ada7c04 exist.
