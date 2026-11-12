---
phase: 03-monte-carlo-simulator
plan: 04
subsystem: sim
tags: [simulator, plans, borrow, safety-car, crn, conformance]
requires:
  - phase: 03-03
    provides: draw layer and lap kernel
provides:
  - f1si.sim.plans (resolve_plans, fallback_plan)
  - f1si.sim.borrow (BorrowedPace)
  - f1si.sim.numpy_backend (NumpySimulator, SafetyCarModel)
  - SIMULATORS["numpy_sim"] conformance registration
affects: [03-05, 03-06, 03-07]
key-files:
  created:
    - src/f1si/sim/plans.py
    - src/f1si/sim/borrow.py
    - src/f1si/sim/numpy_backend.py
    - tests/sim/conftest.py
    - tests/sim/test_plans.py
    - tests/sim/test_borrow.py
    - tests/sim/test_simulate_state.py
    - tests/sim/test_reproducibility.py
    - tests/sim/test_state_start.py
    - tests/sim/test_crn_and_plans.py
    - tests/sim/test_safety_car.py
    - tests/sim/test_sc_frequency.py
  modified:
    - tests/conformance/registry.py
    - docs/explained/phase-03.md
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-081: forced plans exact, optimizer best plan, PlanRefusedError fallback, opportunistic SC stops only for free cars"
  - "DEC-082: leader-relative clocks, catch-up lap, retired cars placed last, borrowed pace"
requirements-completed: []
completed: 2026-11-12
---

# Phase 3 Plan 04: NumpySimulator end to end Summary

NumpySimulator turns a RaceState into n simulated finishes for every car (per-car plan resolution, borrowed pace for unfitted tyres and absent drivers, real-state start with catch-up lap, Numba lap loop with common-random-number draws), registered as `numpy_sim` in the conformance suite.

## Commits

- Task 1: 37b83a5 - plan resolution and pace borrow adapter
- Task 2: 6e8da0d - NumpySimulator, registry entry, validation/reproducibility tests
- Task 3: 8598335 - start-state, CRN, safety-car, SC-frequency tests; DEC-081, DEC-082 (MIN_ENTRIES = 82)

## What was verified

- A 20-car, 57-lap synthetic state gives permutation rows, finite times and a position distribution per driver; same seed is bit-identical, different seeds differ, a reused Generator gives fresh draws.
- Zero-noise hand case equals the `price_plan_slow` sum plus starting gap; the catch-up lap hand sum (laps_done 20/19) matches to 1e-9.
- Forced two-stop plan appears exactly in `stop_laps` and pays 2 x green; opportunistic stop moves to the SC start lap and pays the SC loss, forced does not move.
- CRN: with no contact and no SC, all other cars' times are bit-identical across two forced plans for one driver; SC masks are identical across plans at rate 0.15.
- SC: order frozen on SC laps, restart gaps equal `RESTART_SPACING_S`, the stop is cheaper than the green stop, an SC active at the cutoff starts the sim for `duration - elapsed` laps.
- REG-01 simulation half: no-SC share over 10 laps equals 0.98^10 within 4 sigma in all three variance-reduction modes; start frequency built from `estimate_sc_rate` matches within 4 sigma.

## Deviations from Plan

**1. [Minor] Mid-race test state uses the whole-race fit with the lap-20 snapshot**
- The plan asked for a fit from the lap-20 snapshot; `tests/sim/conftest.py` reuses the whole-race fit (like the registry and real Bahrain use), with the state taken at the cutoff. The lap-20 fixture is not used by a test yet.

**2. [Minor] Safety-car "cheaper stop" test compares stop cost, not raw totals**
- Raw totals are larger under SC because SC laps are 1.4x slower, so the test compares (stopper minus non-stopper total) at rate 1.0 versus rate 0.0. Same intent, valid comparison.

**3. [Minor] Restart-gap check uses atol 1e-9**
- Clock arithmetic (`lead + spacing * p`) differs from `RESTART_SPACING_S` by rounding; tolerance 1e-9 s.

**4. [Rule 1 - Bug, caught in testing] `np.full(..., dtype=np.str_)` truncates strings to one character**
- Found in `BorrowedPace` while writing its test; replaced with `np.repeat(np.array([name], dtype=np.str_), n)` (the pattern used in free_track.py).

No test bound was relaxed; no source defect beyond item 4 was exposed by Task 3 tests (all passed on first run).

## Known Stubs

None in code. `docs/explained/phase-03.md` remains an intentional stub until 03-07.

## Threat Flags

None. Input caps (MAX_RACES, MAX_CARS, MAX_LAPS), forced stop-lap and code validation, and array/index checks before the jitted call are implemented and tested (T-03-10, T-03-11); `numpy_backend.py` contains no accessor or rng-construction references (T-03-12, T-03-13).

## Requirements

SIM-01 and REG-01 are not marked complete: SIM-02/SIM-03 and the remaining Phase 3 work close after plan 03-05 (per orchestrator instruction).

## Verification

ruff check, ruff format --check, mypy strict pass; full suite 760 passed, 15 deselected (`-k "not network"`).

## Self-Check: PASSED
