---
phase: 02-interfaces-linear-tire-wear-free-track-optimizer
plan: 04
subsystem: strategy
tags: [optimizer, pit-plan, cli, conformance]
requires: ["02-01", "02-02", "02-03"]
provides:
  - "f1si.strategy.free_track: FreeTrackOptimizer, PlanRefusedError, price_plan_slow, MIN_STINT_LAPS, MAX_TOTAL_STOPS"
  - "f1si plan SLUG [--driver CODE] [--lap N]"
  - "POLICIES['free_track'] conformance entry"
affects: [02-05]
key-files:
  created:
    - src/f1si/strategy/__init__.py
    - src/f1si/strategy/free_track.py
    - tests/strategy/__init__.py
    - tests/strategy/test_free_track.py
  modified:
    - src/f1si/cli.py
    - tests/conformance/registry.py
    - tests/test_cli_wear_plan.py
    - docs/explained/phase-02.md
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-068 Free-track plan rules and conventions"
  - "DEC-069 Plan cutoff policy and analytic ground truth"
requirements-completed: [PAC-02, INT-02]
completed: 2026-11-11
---

# Phase 2 Plan 04: Free-track optimizer and `plan` command Summary

Brute-force 1- and 2-stop optimizer that prices every legal plan through `PaceModel.predict` prefix sums, proven against hand-built analytic optima and a slow lap-by-lap reference, exposed as `f1si plan`.

## Tasks

| Task | Commit | Result |
|------|--------|--------|
| 1: FreeTrackOptimizer + tests + conformance entry | 3246e72 | strategy/free_track.py, 12 tests (3 analytic cases, hypothesis equivalence, legality, edges, size/speed), POLICIES["free_track"], docs tour bullet |
| 2: `plan` command | 1130bd2 | hindsight and `--lap N` modes, wet refusal, "Compared against" line, 8+ CLI tests |
| 3: DEC-068, DEC-069 | 8d83d9f | MIN_ENTRIES 69 |

## Real Bahrain 2023 output (ALO)

Hindsight (`plan bahrain-2023 --driver ALO`): label shown, starting SOFT age 3, pit loss 24.4 s (42 stops). Best 1-stop: lap 26 SOFT > HARD, 1:34:16.1 (rank 1083, +12.9 s). Best 2-stop and best overall: laps 17, 37 SOFT > HARD > HARD, 1:34:03.1. Compared against: ALO's actual SOFT > HARD > HARD, stops 14, 34, priced 1:34:03.9 (+0.8 s versus the best plan).

`--lap 30`: HARD, 15 laps old, 1 stop done, pit loss 24.5 s. Best overall: stop on lap 36 to HARD (0:43:55.5); no further stop is +35.6 s. "Actual strategy so far: SOFT > HARD, stops on laps 14 (visible stints only; not priced)".

`--lap 5`: exit 1, "Cannot plan: not enough laps yet to fit wear after lap 5 (...); try --lap 20."

## Deviations from Plan

1. **[Rule 1 - Bug] NumPy string truncation.** `np.full(n, "HARD", dtype=np.str_)` makes a `<U1` array ("H"); replaced with `np.repeat(np.array([name], dtype=np.str_), n)`. Found by the first test run.
2. **Hypothesis property skips states with no legal plan** (`assume(False)` on `PlanRefusedError`), since too few laps left is a valid refusal.
3. **CLI messages**: the "race is over" text starts "Nothing to plan: the race is over after lap N" so the lowercase phrase is present.
4. Red tests were not committed separately (same practice as 02-02/02-03).
5. The wet-stint test uses a `_WetSource` wrapper around `SyntheticSource` (driver 11 / BBB, stint 2 set to INTERMEDIATE); generator unchanged.

## Known Stubs

None.

## Notes for plan 02-05

- Gate at end of this plan: ruff check, ruff format --check, `python -m mypy` clean; 654 passed, 8 deselected (opt-in).
- New public pieces to explain: `f1si/strategy/free_track.py` (already in the tour), `f1si plan`. README needles still deferred: mention `f1si plan`, free-track lower bound, hindsight label.
- Opt-in real Bahrain test can assert: ALO hindsight best total about 1:34:03, best 2-stop beats best 1-stop by about 13 s, `--lap 5` exits 1.
- Plan numbering: stop lap k = in-lap; "RANK" in tables is the position in the full ranked list (best 1-stop is rank 1083 at Bahrain because 2-stops win).
- The hindsight command refuses any driver with a non-dry compound in race-end stints or laps.
- CLI uses `fit.fitted_compounds` (HARD, SOFT at Bahrain; MEDIUM lacks data); unfitted compounds make the actual-strategy comparison say it cannot be priced.
- DECISIONS: next free DEC-070, MIN_ENTRIES 69.

## Self-Check: PASSED
