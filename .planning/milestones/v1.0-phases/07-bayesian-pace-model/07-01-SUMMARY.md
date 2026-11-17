---
phase: 07-bayesian-pace-model
plan: "01"
subsystem: pace
tags: [pymc, bayesian, pace-model, simulator]
requires:
  - phase: 06-mvp-backtest-streamlit-view-readme
    provides: PaceModel contract, RaceState uncertainty fields, and seeded NumpySimulator
provides:
  - Locked PyMC 6.4 dependency and seeded BayesianPaceFit tracer
  - Structural fit-summary contract for build_race_state
  - Seeded end-to-end simulator coverage with shared pace and wear uncertainty
affects: [07-02, 07-03, 07-04, pace-training, replay]
actuals:
  tokens: 9800
  tasks: 2
  commits: 2
tech-stack:
  added: [pymc 6.4.0]
  patterns: [seeded full-rank ADVI, residual noise separated from shared state uncertainty]
key-files:
  created:
    - src/f1si/pace/bayesian.py
    - tests/pace/test_bayesian_model.py
    - tests/sim/test_bayesian_pace.py
  modified:
    - pyproject.toml
    - uv.lock
    - src/f1si/state.py
key-decisions:
  - "PaceModel.predict returns residual lap noise; driver and tire uncertainty remain shared RaceState draws."
  - "build_race_state consumes a narrow structural protocol so linear and Bayesian fits share the existing state path."
requirements-completed: [PAC-05]
coverage:
  - id: D1
    description: Seeded Bayesian pace fit implements the shared PaceModel prediction contract.
    requirement: PAC-05
    verification:
      - kind: unit
        ref: tests/pace/test_bayesian_model.py
        status: pass
      - kind: unit
        ref: tests/conformance/test_suites.py
        status: pass
    human_judgment: false
  - id: D2
    description: Bayesian shared parameter summaries flow through RaceState and the seeded simulator.
    requirement: PAC-05
    verification:
      - kind: integration
        ref: tests/sim/test_bayesian_pace.py
        status: pass
      - kind: integration
        ref: tests/test_state_builder.py
        status: pass
      - kind: integration
        ref: tests/sim/test_reproducibility.py
        status: pass
    human_judgment: false
duration: 24min
completed: 2026-11-16
status: complete
---

# Phase 7 Plan 01: Bayesian Pace Tracer Summary

The PyMC tracer now fits seeded lap-time arrays and flows through the existing PaceModel, RaceState, and NumpySimulator contracts.

## Performance

- **Duration:** about 24 minutes
- **Started:** 2026-11-16 08:51 UTC
- **Completed:** 2026-11-16 09:15 UTC
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added and locked PyMC 6.4, then implemented the seeded full-rank ADVI fit and compact posterior summaries.
- Kept the fit's per-lap standard deviation to residual noise while exposing shared driver and wear uncertainty through RaceState.
- Verified repeated-seed inference, PaceModel conformance, RaceState construction, simulator reproducibility, and the existing state-builder/reproducibility tests.

## Task Commits

1. **Task 07-01-01: Lock PyMC and add the seeded Bayesian PaceModel tracer** - `5deaf51`
2. **Task 07-01-02: Trace Bayesian state summaries through one simulator run** - `1a0bb69`

## Decisions Made

- The Bayesian fit uses the current simulation uncertainty ownership: shared driver and tire terms are sampled once from RaceState; residual lap variation is sampled each lap.
- The state builder accepts a narrow structural fit protocol, preserving existing LinearPaceFit callers and simulator APIs.

## Deviations from Plan

None.

## Issues Encountered

- PyTensor warned that the optional C++ compiler was not available on this Windows host. The CPU fallback worked and the focused tests passed.
- The existing simulator reproducibility file was run as its own focused pytest invocation because a multi-path invocation did not consistently include its local fixture; the isolated run passed.

## User Setup Required

None.
