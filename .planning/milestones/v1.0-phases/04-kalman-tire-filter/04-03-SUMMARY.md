---
phase: 04-kalman-tire-filter
plan: 03
subsystem: sim
tags: [kalman, simulator, wear, state, crn, numba]
requires: ["04-01", "04-02"]
provides:
  - "CarState.wear_source and build_race_state(wear_filter=...)"
  - "kernel wear_age_off parameter; virtual compound columns for filter cars in NumpySimulator"
  - "draws.car_wear_draws (fifth spawned stream)"
affects: [04-04, 04-05]
tech-stack:
  added: []
  patterns: ["virtual compound column with per-column age offset", "fifth spawned stream used only when needed"]
key-files:
  created:
    - tests/sim/test_filter_cars.py
  modified:
    - src/f1si/state.py
    - src/f1si/sim/kernel.py
    - src/f1si/sim/draws.py
    - src/f1si/sim/numpy_backend.py
    - tests/sim/test_kernel.py
    - tests/test_state.py
    - tests/test_state_builder.py
    - DECISIONS.md
    - tests/test_decisions_log.py
    - docs/explained/phase-04.md
key-decisions:
  - "DEC-093: wear_source field, JSON key only for filter, builder cutoff check, prior-only entries ignored"
  - "DEC-094: virtual compound columns + wear_age_off; SD scales with laps run after the cutoff; real tyre age kept"
requirements-completed: []
duration: ~1h30m
completed: 2026-11-13
---

# Phase 4 Plan 03: Filter results into the simulator Summary

**A car's filtered wear rate and SD now drive its current-tyre laps in the NumPy simulator through one new kernel parameter (`wear_age_off`) and a virtual compound column, while "fit" cars stay byte-identical to the stored Phase 3 reference.**

## Tasks

| Task | Commit | Result |
|------|--------|--------|
| 1 State plumbing, DEC-093 | 779d387 | `CarState.wear_source` (default "fit"), `build_race_state(wear_filter=)` with cutoff-lap check; 7 new tests |
| 2 Simulator integration | 135e492 | kernel +1 parameter and 1 expression; `car_wear_draws`; `_filter_eligible` and `_filter_car_columns` in numpy_backend |
| 3 Behaviour tests, DEC-094 | 634fa81 | 11 tests in `tests/sim/test_filter_cars.py`; DEC-094; MIN_ENTRIES 94; explainer sentence |

## Verification

- Phase 3 reference array and hash tests pass unchanged; `git diff src/f1si/sim/constants.py` is empty; kernel diff is the parameter, its docstrings and the wear expression only; `draws.py` diff is one added function.
- Existing tests changed only in `run` of tests/sim/test_kernel.py (zeros `wear_age_off` default); no assertion changed.
- ruff check, ruff format --check, mypy: clean.
- Full suite: 898 passed, 8 failed, 1 error, 19 deselected. The 8 failures and the 1 error are exactly the known environment-only set (5 in tests/test_import_order.py, 3 `test_module_imports_without_pyplot`, the db lock error). I checked by hand with the shim that the four import orders of `f1si.state` work and `f1si.interfaces` alone does not load `f1si.state`, so the new `f1si.state -> f1si.pace.kalman` import created no cycle.

## Deviations from Plan

- **[Rule 2 note] T-04-11 SD check.** The plan said to add a finite non-negative SD check to `CarState` if missing. I added it, then removed it: the existing hypothesis round-trip test generates negative `wear_sd`, and the honesty rules forbid changing existing assertions. The check lives in the simulator's eligibility rule instead (a car with a non-finite or negative SD behaves as a fit car). Recorded in DEC-093/DEC-094.
- The mean-finish half of the direction test uses its own closer scenario (1 s spacing, 20 laps) because the exact-mean half needs cars 60 s apart.
- The `real_name_of` mapping from the plan was not needed: virtual columns are applied after `_start`, so every comp-name lookup there still sees real indices.

## Known Stubs

None.

## Threat surface

No new surface. T-04-09 (wear_source validated), T-04-10 (one column per car, `_check_kernel_inputs` extended to `wear_sd`, `wear_age_off`, `z_wear` shapes and dtype) and T-04-11 (eligibility) mitigated.

## Self-Check: PASSED

Commits 779d387, 135e492, 634fa81 exist; tests/sim/test_filter_cars.py present.
