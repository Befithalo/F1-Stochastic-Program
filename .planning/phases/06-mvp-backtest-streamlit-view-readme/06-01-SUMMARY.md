---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "01"
subsystem: evaluation
tags: [walk-forward, backtest, as-of, future-scramble, cli]

# Dependency graph
requires:
  - phase: 05-longstaff-schwartz-strategy-live-replay
    provides: Shared cutoff-local replay builder and strategy distributions
  - phase: 01-foundation
    provides: AsOfAccessor, frozen calendar metadata, and future-scramble guards
provides:
  - Calendar-locked ten-race registration with complete-cache preflight
  - Cutoff-local prediction-only tracer CLI and immutable full prediction trace
  - Registered walk-forward cutoff consumer protected by future-scramble tests
affects: [06-02-backtest-scoring, BKT-01]

# Actuals (#2632)
actuals:
  tokens: 5099
  tasks: 2
  commits: 3
commits: 3
plan_head_before: ff27895384ae0b2b5f1118265aa0013f9405bd02
plan_head_after: 3c14ee86f82e2a06eb1bb5b269f115ff528a9650

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Calendar-first immutable race registration and all-race preflight
    - Seed derived from race, driver, cutoff, and base seed for repeatable predictions
    - Frozen tuple of per-driver, per-cutoff prediction rows before later scoring

key-files:
  created:
    - src/f1si/backtest/__init__.py
    - src/f1si/backtest/walk_forward.py
  modified:
    - src/f1si/cli.py
    - tests/backtest/test_walk_forward.py
    - tests/guards/consumers.py

key-decisions:
  - "Lock the first four calendar rounds of 2023, the first three of 2024, and the first three of 2025 before scoring."
  - "Use scheduled race distance and cutoff-visible entrants; rebuild each prediction through the shared replay cutoff builder."
  - "Keep the result-access and scoring boundary outside this prediction-only plan."

patterns-established:
  - "The cache preflight runs once before the prediction runner starts; missing IDs are reported together."
  - "The registered consumer maps the RACE_END harness marker to the final eligible cutoff without reading future rows."

requirements-completed: [BKT-01]
coverage:
  - id: D1
    description: Ten calendar-registered races must be complete before the CLI emits a prediction-only row.
    requirement: BKT-01
    verification:
      - kind: integration
        ref: tests/backtest/test_walk_forward.py#test_reference_cli_returns_prediction_row_after_full_preflight
        status: pass
      - kind: unit
        ref: tests/backtest/test_walk_forward.py#test_incomplete_sample_stops_before_prediction_or_results_access
        status: pass
    human_judgment: false
  - id: D2
    description: The full trace visits all registered drivers and eligible cutoffs in order and passes future-scramble checks.
    requirement: BKT-01
    verification:
      - kind: integration
        ref: tests/backtest/test_walk_forward.py#test_full_runner_freezes_every_driver_and_cutoff_in_order
        status: pass
      - kind: integration
        ref: "uv run python -m pytest tests/backtest/test_walk_forward.py tests/guards/test_future_scramble.py -x -q"
        status: pass
      - kind: integration
        ref: "uv run python -m pytest tests/guards tests/test_decisions_log.py -x -q"
        status: pass
    human_judgment: false

# Metrics
duration: 27m
started: 2026-11-14T02:43:00Z
completed: 2026-11-14
status: complete
---

# Phase 6 Plan 1: Fixed-Sample Walk-Forward Predictions Summary

**The ten-race walk-forward path now gates on complete caches and freezes seeded, cutoff-local predictions for every eligible driver and lap before scoring is introduced.**

## Performance

- **Duration:** 27 minutes
- **Started:** 2026-11-14T02:43:00Z
- **Completed:** 2026-11-14T03:10:35Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Registered the fixed calendar sample: Bahrain, Saudi Arabian, Australian, and Azerbaijan 2023; Bahrain, Saudi Arabian, and Australian 2024; Australian, Chinese, and Japanese 2025.
- Added a full-sample completeness preflight and `f1si backtest --race 2023-01 --driver ALO --lap 0` prediction-only route.
- Extended the runner across every driver and strategy-eligible cutoff, returning an immutable prediction tuple and registering its cutoff consumer with the future-scramble guard.

## Task Commits

1. **Task 1 RED: Register the backtest CLI behavior test** - `5f4281f` (`test`)
2. **Task 1 GREEN: Add cache-gated cutoff prediction** - `4575924` (`feat`)
3. **Task 2: Freeze the complete walk-forward prediction set** - `3c14ee8` (`feat`)

## Files Created/Modified

- `src/f1si/backtest/__init__.py` - Exposes the fixed registration and immutable row/trace types.
- `src/f1si/backtest/walk_forward.py` - Implements cache preflight, single-cutoff prediction, full trace generation, and the scramble consumer.
- `src/f1si/cli.py` - Adds the backtest command and keeps cache accessor construction in the CLI composition layer.
- `tests/backtest/test_walk_forward.py` - Covers registration, preflight, prediction-only output, ordering, and 2026 refusal.
- `tests/guards/consumers.py` - Registers the cutoff consumer for look-ahead checks.

## Decisions Made

- Used calendar order and the fixed 4/3/3 year split for the registered race set.
- Used scheduled distance from race metadata and cutoff-visible entries; each prediction reuses the existing replay builder with its own snapshot and strictly earlier history.
- Kept final-results access and scoring out of the walk-forward module.

## TDD Gate Compliance

- **RED:** `test_backtest_command_is_registered` failed on the missing parser command. The JUnit evidence was validated as `RED_EVIDENCE_OK`; the assertion failed for the planned behavior rather than collection or setup.
- **GREEN:** Commit `4575924` registered the route and made the focused suite pass.
- **Task 2:** Expanded the runner and guard registration in commit `3c14ee8`; verification confirms chronological cutoffs, immutable predictions, and future-row invariance.

## Deviations from Plan

**1. [Rule 1 - Bug] Kept the registered consumer inside strategy-eligible cutoffs**
- **Found during:** Task 2
- **Issue:** The future-scramble harness supplies `RACE_END` and the final completed lap, neither of which can be treated as an ordinary strategy decision cutoff.
- **Fix:** Resolve `RACE_END` to the final scheduled eligible cutoff and clamp the final-lap probe to that cutoff, using scheduled race metadata rather than future observations.
- **Files modified:** `src/f1si/backtest/walk_forward.py`
- **Verification:** Both required guard commands pass, including the full future-scramble cutoff grid.
- **Committed in:** `3c14ee8`

**Total deviations:** 1 auto-fixed (Rule 1). The adjustment keeps the registered consumer aligned with the plan's cutoff eligibility rule.

## Verification

- `uv run python -m pytest tests/backtest/test_walk_forward.py -q` - 6 passed after Task 1.
- `uv run python -m pytest tests/guards tests/test_decisions_log.py -x -q` - 224 passed.
- `uv run python -m pytest tests/backtest/test_walk_forward.py tests/guards/test_future_scramble.py -x -q` - 58 passed.
- Ruff check and format checks passed for the modified Python files.

## User Setup Required

None.

## Next Phase Readiness

Plan 06-02 can consume the immutable prediction trace and add the isolated final-results scoring layer. The prediction runner does not import or call result accessors or scorers.

---
*Phase: 06-mvp-backtest-streamlit-view-readme*
*Completed: 2026-11-14*

## Self-Check: PASSED

- SUMMARY.md exists at the required phase path.
- Task commits `5f4281f`, `4575924`, and `3c14ee8` are ancestors of HEAD.
