---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "00"
subsystem: testing
tags: [pytest, backtest, streamlit, evaluation]

requires:
  - phase: 05-longstaff-schwartz-strategy-live-replay
    provides: cutoff-safe replay behavior and strategy outputs covered by the new contracts
provides:
  - Four backtest and diagnostic contract modules for walk-forward, metrics, team stops, and wear proxy behavior
  - Streamlit page contract module for controls, outputs, safety boundaries, and UI states
affects: [06-01, 06-02, 06-03, 06-04]

actuals:
  tokens: 3615
  tasks: 2
  commits: 2
commits: 2
plan_head_before: 97f8c5b403c5fadd993c02bffbe6082b28e88523
plan_head_after: 944e1547aeaab03860da57e4820664e7af2ee7e9

tech-stack:
  added: []
  patterns: [pytest contracts, event-order assertions, Streamlit source and AppTest checks]

key-files:
  created:
    - tests/backtest/test_walk_forward.py
    - tests/backtest/test_metrics.py
    - tests/backtest/test_strategy.py
    - tests/backtest/test_wear_diagnostic.py
    - tests/app/test_app.py
  modified: []

key-decisions: []
patterns-established:
  - "Prediction freeze must precede any results access or scoring."
  - "Scoring and uncertainty assertions use identical masks and race-level aggregation."
  - "The app contract preserves the results-door boundary and approved state copy."

requirements-completed: []
coverage:
  - id: D1
    description: "Backtest and diagnostic acceptance contracts parse and cover the locked Phase 6 boundaries."
    verification:
      - kind: unit
        ref: "uv run python -c AST parse for four tests/backtest modules"
        status: pass
    human_judgment: false
  - id: D2
    description: "Streamlit page contract parses and names approved controls, outputs, safety boundary, and UI states."
    verification:
      - kind: unit
        ref: "uv run python -c AST parse for tests/app/test_app.py"
        status: pass
    human_judgment: false

metrics:
  duration: 6min
  completed: 2026-11-14
status: complete
---

# Phase 6 Plan 00: Test Contracts Summary

**Five parseable pytest modules now define the walk-forward, scoring, team-call, wear-proxy, and Streamlit acceptance contracts for Phase 6 implementation plans.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-11-14T02:36:21Z
- **Completed:** 2026-11-14T02:42:01Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added fixed-sample, completeness-preflight, chronological-cutoff, prediction-freeze, and 2026 refusal contracts.
- Added scoring contracts for binary outcomes, neutral and shrunken grid priors, discrete interval endpoints, coverage denominators, equal-race weighting, and seeded race-cluster uncertainty.
- Added one-to-one pre-event stop matching and leave-current-stint-out proxy measurement contracts.
- Added page contracts for catalog-backed controls, locked defaults, read-only results boundary, required panels, explicit states, and Streamlit test harness availability.

## Task Commits

1. **Task 06-00-01: Author backtest, scoring, event, and wear diagnostic test contracts** - e8a2ac4 (test)
2. **Task 06-00-02: Author the approved Streamlit page test contract** - 944e154 (test)

## Files Created/Modified

- tests/backtest/test_walk_forward.py - Fixed sample, preflight, freeze order, cutoff ordering, and out-of-sample contracts.
- tests/backtest/test_metrics.py - Binary scoring, baseline priors, interval semantics, race aggregation, and scoring gate contracts.
- tests/backtest/test_strategy.py - Strict pre-event matching and race-clustered team-call contracts.
- tests/backtest/test_wear_diagnostic.py - Current-stint exclusion, proxy labels, denominators, bias, and own-lap evidence contracts.
- tests/app/test_app.py - Controls, defaults, output, read-only boundary, and UI-state contracts.

## Decisions Made

None - followed the plan's locked contracts.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

The pre-commit Ruff hooks reported formatting and assertion-style issues on the first commit attempts. Those findings were corrected, and both task commits passed Ruff check and formatting hooks.

## Verification

- Task 06-00-01 exact AST verification: passed.
- Task 06-00-02 exact AST verification: passed.
- Task 06-00-01 AST verification rerun after formatting: passed.
- Behavioral tests were not run in Wave 0; the plan reserves them for the downstream implementation tasks.

## Next Phase Readiness

The five test modules exist and parse, so downstream Phase 6 implementation tasks can run their focused pytest commands. These contracts do not themselves complete BKT-01, BKT-02, BKT-04, or UI-01; those requirements remain with their implementation plans.

---
*Phase: 06-mvp-backtest-streamlit-view-readme*
*Completed: 2026-11-14*

## Self-Check: PASSED

- All five planned test modules exist.
- Task commits e8a2ac4 and 944e154 are ancestors of HEAD.
