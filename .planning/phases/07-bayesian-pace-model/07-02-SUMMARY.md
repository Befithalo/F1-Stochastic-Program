---
phase: 07-bayesian-pace-model
plan: "02"
subsystem: pace
tags: [pymc, hierarchical-model, cutoff-safety, future-scramble]
requires:
  - phase: 07-bayesian-pace-model
    provides: Seeded BayesianPaceFit tracer and structural RaceState fit contract
provides:
  - Cutoff-safe clean-lap panel from earlier History and current RaceSnapshot
  - Stable driver/team/event/era/compound indexes and current-entry lookup
  - Centered partially pooled team, driver, event and era pace effects
  - Prior-driven group diagnostics for sparse current drivers and teams
affects: [07-03, 07-04, 07-05, replay, walk-forward-evaluation]
actuals:
  tokens: 7800
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns: [as-of panel from History and RaceSnapshot, sorted stable categorical indexes, centered non-centered group effects]
key-files:
  created:
    - src/f1si/pace/training.py
    - tests/pace/test_bayesian_training.py
  modified:
    - src/f1si/pace/bayesian.py
    - tests/pace/test_bayesian_model.py
    - tests/guards/consumers.py
key-decisions:
  - "The training builder receives only History and RaceSnapshot and never reads History.results."
  - "Team name remains a car-performance proxy, and 2023-2025 real rows provide only one observed era."
  - "Sparse or unseen current groups are included through population-centered priors and reported as prior-driven."
requirements-completed: [PAC-05, DAT-03, DAT-04, DAT-05]
coverage:
  - id: D1
    description: Historical and current clean laps are joined by race and entry identity without future rows.
    requirement: DAT-03
    verification:
      - kind: unit
        ref: tests/pace/test_bayesian_training.py
        status: pass
      - kind: unit
        ref: tests/guards/test_future_scramble.py
        status: pass
    human_judgment: false
  - id: D2
    description: The hierarchical model exposes centered effects and identifies sparse population-prior predictions.
    requirement: PAC-05
    verification:
      - kind: unit
        ref: tests/pace/test_bayesian_model.py
        status: pass
      - kind: unit
        ref: tests/pace/test_bayesian_training.py
        status: pass
    human_judgment: false
duration: 15min
completed: 2026-11-16
status: complete
---

# Phase 7 Plan 02: Cutoff-Safe Training and Hierarchy Summary

Training now assembles clean historical and cutoff-visible laps into stable identity groups, and the PyMC fit uses those groups in a partially pooled pace hierarchy.

## Performance

- **Duration:** about 15 minutes
- **Started:** 2026-11-16 09:15 UTC
- **Completed:** 2026-11-16 09:30 UTC
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Built a panel from earlier in-sample History and completed clean laps in the current RaceSnapshot, joined on race and driver number.
- Reused the linear model's clean-lap classifier and added an explicit current-lap-end cutoff check.
- Registered the panel consumer with the future-scramble harness; all 51 guard tests passed on the synthetic grid.
- Added centered team/car, stable driver, fresh-compound, wear, fuel-proxy, event, and regulation-era terms to the seeded PyMC model.
- Added shrinkage diagnostics for sparse and unseen current drivers and teams, while keeping the 2026 boundary locked.

## Task Commits

1. **Task 07-02-01: Assemble cutoff-safe lap panels from History and snapshot** - `e184cef`
2. **Task 07-02-02: Fit the centered partially pooled pace hierarchy** - `4579c87`

## Decisions Made

- Historical row seasons come from the race calendar key and are mapped through the existing era table. The 2023-2025 in-sample seasons all map to the same ground-effect era.
- Current-only groups enter the centered group model with population priors and are tagged as prior-driven when their clean-row count is below the declared threshold.

## Deviations from Plan

None.

## Issues Encountered

- The full future-scramble grid takes about three minutes because it rebuilds the synthetic cache for every race/cutoff. It passed all registered consumers.
- The short ADVI fit tests emit a PyTensor loop-fusion performance warning on Windows; fitted values remain finite and deterministic.

## User Setup Required

None.
