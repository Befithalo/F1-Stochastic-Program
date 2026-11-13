---
phase: 04-kalman-tire-filter
plan: 01
subsystem: pace
tags: [kalman, tyre-wear, bayesian-regression, joseph-form, reference-fixture]
requires: []
provides:
  - "f1si.pace.kalman: WearPrior, WearFilter, LapUpdate, FilterSnapshot, posterior_rate_sd, GATE_Z, GATE_MIN_USED, DIFFUSE_LEVEL_SD"
  - "Phase 3 simulator reference fixture (arrays + sha256) and its guard test"
affects: [04-02, 04-03, 04-04, 04-05]
tech-stack:
  added: []
  patterns: ["Joseph-form Kalman update with symmetrisation", "closed-form regression oracle in tests"]
key-files:
  created:
    - src/f1si/pace/kalman.py
    - tests/sim/test_phase3_reference.py
    - tests/fixtures/phase3_reference.npz
    - tests/fixtures/phase3_reference.json
    - tests/pace/test_kalman_math.py
    - tests/pace/test_kalman_incremental.py
    - tests/pace/test_kalman_narrowing.py
    - tests/pace/test_kalman_gate.py
    - docs/explained/phase-04.md
  modified:
    - tests/guards/consumers.py
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-088: three-state [level, rate, fuel_dev] filter, dynamic F/H form, equals Bayesian regression at q = 0"
  - "DEC-089: q = 0 default, q > 0 accepted with stated limits"
  - "DEC-090: skipped laps predict only; gate 3.0 SD from the 3rd used lap, never twice in a row"
requirements-completed: [PAC-03]
duration: ~1h
completed: 2026-11-13
---

# Phase 4 Plan 01: Kalman array core and Phase 3 reference Summary

**Pure-array three-state Joseph-form Kalman filter for the tyre-wear rate (fuel nuisance state, outlier gate), proven equal to closed-form Bayesian regression to 1e-9, plus a stored Phase 3 simulator reference captured from unmodified code.**

## Tasks

| Task | Commit | Result |
|------|--------|--------|
| 1 Phase 3 reference | af08a1c | 256 races, seed 20260101, 6 cars, SC on, wear draws on; npz + sha256 json; 3 tests |
| 2 Kalman core, registry, explainer skeleton, DEC-088..090 | 47ea72b | `src/f1si/pace/kalman.py`, EXEMPT entries, MIN_ENTRIES 90 |
| 3 Unit tests | 03ddb9c | math 8, incremental 4, narrowing 6, gate 10 test functions (65 tests with parametrisation, incl. registry) |

`git diff -- src/f1si/sim` was empty at capture and still is.

## Verification

- Filter vs closed-form regression: mean and 3x3 covariance, rtol 1e-9, 60 random priors, 2 to 12 laps.
- `WearFilter.rate_sd` after 7 laps (tau 0.02, fuel_sd 0.02, sigma 0.15) equals `posterior_rate_sd` = 0.0173 to 1e-9; RESEARCH cells 0.0094, 0.0163, 0.0206, 0.0247 reproduced.
- ruff check, ruff format --check, mypy: clean.
- Full suite: 846 passed, 8 failed, 1 error, 19 deselected. The 8 failures and 1 error are exactly the known environment-only set (5 in tests/test_import_order.py, 3 `test_module_imports_without_pyplot` in tests/plots, and the db lock error), all `ModuleNotFoundError: No module named 'f1si'` from `sys.executable -I`.

## Deviations from Plan

None in behaviour. Notes:

- The plan names `tests/guards/consumers.py` EXEMPT entries for properties; the registry enumerates functions only, so entries exist for `observe`, `snapshot` and `posterior_rate_sd`.
- Tests that compare against the oracle use data noise clipped at 2 SD (and assert zero gate rejections) so the outlier gate cannot change the used set. The first attempt with unclipped noise showed the gate rejecting an honest 3.3 SD draw; the gate was right and no tolerance was changed.
- The phase 3 reference has a constant finish order (one unique row of 256) because the hand-built pace is noiseless; `total_time_s` varies (SD about 50 s per car across races, from safety cars and wear draws), so the array gate still detects any change.

## Known Stubs

None. The docs page is an intentional skeleton completed by plan 04-05.

## Self-Check: PASSED

Files and commits af08a1c, 47ea72b, 03ddb9c exist.
