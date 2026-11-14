---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "02"
subsystem: evaluation
tags: [backtest, metrics, brier, bootstrap]

# Dependency graph
requires:
  - phase: 06-01
    provides: Frozen ten-race walk-forward prediction contract
provides:
  - Deterministic Brier, baseline-prior, interval, equal-race aggregation, and race-cluster bootstrap primitives
affects: [06-03, 06-04, BKT-02]

# Actuals
actuals:
  tokens: 4151
  tasks: 1
  commits: 2
plan_head_before: 937244b7530490839b9e2d1a36e43c1c57c6b32d
plan_head_after: 87610f968bde39c3e3d04f3c8bc4250c89dd286e

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Same-mask model and baseline scoring
    - Equal-race aggregation with paired seeded race-cluster resampling

key-files:
  created: []
  modified:
    - src/f1si/backtest/metrics.py
    - tests/backtest/test_metrics.py

key-decisions:
  - "Use neutral event-rate priors, five pseudo-observations for grid-position shrinkage, and inclusive NumPy inverted-CDF interval endpoints per D-02 through D-04."
  - "Keep this plan limited to deterministic metric primitives; final-results scoring/reporting remains in Plan 06-04."

requirements-completed: []
duration: not recorded
completed: 2026-11-13
status: complete
---

# Phase 6 Plan 2: Metric Primitives Summary

**Deterministic backtest metrics and race-cluster uncertainty primitives are implemented and their seven focused metric tests passed.**

## Accomplishments

- Implemented binary Brier scores, neutral and shrunk grid-position priors, inclusive discrete finish intervals, classified-finisher coverage denominators, equal-race aggregation, and seeded paired race-cluster intervals.
- The focused command `uv run python -m pytest tests/backtest/test_metrics.py -q` passed 7 metric tests after implementation commit `87610f9`.
- The later RED scorer API test from `bf07561` is a separate Plan 06-04 contract; it records that the scoring module is not yet present. The seven-test result predates that additional test and does not claim the scorer/report behavior.

## Task Commits

1. **Task 06-02-01 RED: Add failing Brier metrics contract** — `967889c` (`test`)
2. **Task 06-02-01 GREEN: Implement race-cluster metrics** — `87610f9` (`feat`)

## Scope Remaining

Plan 06-02 completes only the metric-primitives portion of BKT-02. D-09 selected-option distribution evidence is planned in 06-03, and the all-ten results-gated scoring/report path is planned in 06-04; therefore BKT-02 is not marked complete here.

---
*Phase: 06-mvp-backtest-streamlit-view-readme*
*Completed: 2026-11-13*
