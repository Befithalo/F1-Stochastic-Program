---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "03"
subsystem: strategy
tags: [longstaff, simulation, outcome-probabilities, empirical-intervals]

requires:
  - phase: 06-01
    provides: Cutoff-local StrategyAnalysis carried through frozen PredictionRow
provides:
  - RankedOption podium and top-10 probabilities from its own finish draws
  - Inclusive inverted-CDF P05/P95 finish-position endpoints
affects: [06-04, BKT-02]

actuals:
  tokens: 2010
  tasks: 1
  commits: 2
plan_head_before: 4de555ce6801e46543c0af86bd565bdad6aec8b4
plan_head_after: 8b77f3a84393a9a1a81326c465f3657da0b060e8

tech-stack:
  added: []
  patterns:
    - Same-draw compact distribution summaries retained with strategy options
key-files:
  created: []
  modified:
    - src/f1si/strategy/longstaff.py
    - tests/strategy/test_longstaff.py
key-decisions:
  - "Compute podium/top-10 mass and inverted-CDF endpoints directly from each option's existing finish-position sample."
  - "Keep full simulation arrays local to analyze and carry only compact summaries in the frozen prediction trace."
patterns-established:
  - "Use NumPy inverted_cdf quantiles for inclusive discrete finishing-position endpoints."
requirements-completed: []
coverage:
  - id: D1
    description: "Ranked strategy options expose same-draw probabilities and inclusive finish intervals without retaining draws."
    requirement: BKT-02
    verification:
      - kind: unit
        ref: "uv run python -m pytest tests/strategy/test_longstaff.py -q"
        status: pass
    human_judgment: false
duration: 12min
completed: 2026-11-13
status: complete
---

# Phase 6 Plan 3: Same-Draw Strategy Outcome Summaries

**Each ranked option now retains podium/top-10 probabilities and inclusive empirical finish endpoints computed from the same simulation draws used to rank it.**

## Performance

- **Duration:** 12 minutes
- **Tasks:** 1
- **Files modified:** 2
- **Task commits:** 2, measured from the persisted plan base

## Accomplishments

- Added podium and top-10 probabilities plus inclusive 5th/95th percentile finish positions to `RankedOption`.
- Kept the raw draw arrays local to `LongstaffSchwartzPolicy.analyze`; `PredictionRow` continues to carry only the compact `StrategyAnalysis`.
- Added controlled numeric tests covering distinct options, tied and non-tied inverted-CDF endpoints, and the frozen prediction trace.
- Verified with `uv run python -m pytest tests/strategy/test_longstaff.py -q` — 17 passed.

## Task Commits

1. **Task 06-03-01 RED: Add same-draw distribution contract tests** — `513d24b` (`test`)
2. **Task 06-03-01 GREEN: Add compact option outcome summaries** — `8b77f3a` (`feat`)

## TDD Evidence

- **RED:** JUnit evidence was accepted by `gsd-tools check tdd-red-evidence` (`RED_EVIDENCE_OK`). Both new contract tests executed and failed because `RankedOption.podium_probability` did not yet exist; 15 existing tests passed.
- **GREEN:** The planned focused pytest command passed all 17 tests after implementation.
- **REFACTOR:** None required.

## Decisions Made

- Summary values use each option's exact finishing-position sample, with cutoffs `<= 3` and `<= 10` and NumPy `method="inverted_cdf"` for endpoints.
- The plan contributes to BKT-02; final requirement completion remains with the later scoring/report plan.

## Deviations from Plan

None. The test fixture was adjusted to locate options by action because production ranking sorts by score.

## Issues Encountered

- The first RED commit attempt was stopped by the repository's Ruff formatting hook. The test formatting was corrected and the normal hooks passed on the subsequent commit; no hooks were bypassed.

## Next Phase Readiness

Plan 06-04 can consume the compact option probabilities and interval endpoints from each frozen prediction row before opening the scoring results boundary.

## Self-Check: PASSED

- Summary exists and both task commits (`513d24b`, `8b77f3a`) are ancestors of HEAD.
- `gsd-tools check evaluation-scope --plan 06-03 --commits-only` found both plan commits on this branch.
- The focused Longstaff verification passed all 17 tests; `longstaff.py` has no final-results accessor import.

---
*Phase: 06-mvp-backtest-streamlit-view-readme*
*Completed: 2026-11-13*
