---
phase: 07-bayesian-pace-model
plan: "04"
subsystem: replay-backtest
tags: [bayesian-pace, as-of, model-selection, walk-forward]
requires:
  - phase: 07-bayesian-pace-model
    provides: Converged Bayesian pace fitter and cutoff-safe training panel
provides:
  - Opt-in Bayesian pace selection for replay and registered backtests
  - Shared race/cutoff fit context with content-keyed bounded fit cache
  - Separate default report path for Bayesian scores
  - Replay, cache identity, report path, and future-scramble coverage
affects: [07-05, replay, backtest]
actuals:
  tokens: 10500
  tasks: 2
  commits: 1
tech-stack:
  added: []
  patterns: [one model fit per race cutoff, content-bound bounded cache, optional model-specific report path]
key-files:
  created: []
  modified:
    - src/f1si/cli.py
    - src/f1si/backtest/walk_forward.py
    - src/f1si/backtest/scoring.py
    - tests/test_cli_replay.py
    - tests/backtest/test_walk_forward.py
    - tests/guards/consumers.py
    - DECISIONS.md
key-decisions:
  - "Keep linear pace as the default; expose Bayesian pace as an explicit replay/backtest choice."
  - "Derive one fit seed per race/cutoff, shared across drivers, and cache by cutoff, panel content, model configuration, and seed."
  - "Write Bayesian full-report output to a separate default path so Phase 6 linear evidence cannot be overwritten."
requirements-completed: [PAC-05, RPL-01, BKT-01]
coverage:
  - id: D1
    description: Bayesian replay uses a current snapshot and earlier-only history at its selected cutoff.
    requirement: PAC-05
    verification:
      - kind: unit
        ref: tests/test_cli_replay.py::test_bayesian_replay_uses_cutoff_history_and_caches_only_matching_fit_identity
        status: pass
      - kind: integration
        ref: tests/backtest/test_walk_forward.py::test_registered_backtest_prediction_uses_bayesian_selected_context
        status: pass
    human_judgment: false
  - id: D2
    description: The registered walk-forward prepares one selected model context per race/cutoff and preserves linear defaults.
    requirement: BKT-01
    verification:
      - kind: integration
        ref: tests/backtest/test_walk_forward.py
        status: pass
    human_judgment: false
  - id: D3
    description: Bayesian selection does not change under future-row scrambling at the replay and policy seam.
    requirement: RPL-01
    verification:
      - kind: guard
        ref: tests/guards/test_future_scramble.py
        status: pass
    human_judgment: false
duration: 16min
completed: 2026-11-16
status: complete
---

# Phase 7 Plan 04: Cutoff-Local Bayesian Replay and Backtest Summary

**Replay and registered backtests can now select the converged Bayesian pace model at each cutoff while keeping linear behavior as the default.**

## Accomplishments

- Added `--pace-model linear|bayesian` to replay and backtest. The backtest scorer forwards the selection to the existing walk-forward runner and records Bayesian model metadata only for Bayesian reports.
- Each race/cutoff prepares one fit context and shares it across drivers. A bounded cache requires matching race, cutoff, panel content and current identity maps, model configuration, and seed. Fit seeds are shared across drivers at a cutoff.
- Kept full-report outputs separate by default: linear uses the Phase 6 report path and Bayesian uses `reports/backtest/phase-07-bayesian.json`. Bayesian cannot extend the Phase 6 linear diagnostics report.
- Added selected-model, history boundary, cache identity, real registered prediction-path, report routing, and future-scramble checks.
- Recorded DEC-117. No UI/UX files changed.

## Validation

- `tests/test_cli_replay.py tests/test_cli.py`: **55 passed**.
- `tests/backtest/test_walk_forward.py` plus the two new report-routing tests: **16 passed**.
- `tests/guards/test_future_scramble.py`: **51 passed**.
- `tests/test_decisions_log.py`: **30 passed**.
- Ruff, formatting, mypy on the changed source modules, and `git diff --check`: passed.

## Deviations and Resource Notes

- Full-report integration also required `src/f1si/backtest/scoring.py` and CLI report tests, beyond the original file list.
- The first future-scramble attempt used live ADVI fits throughout a 20-example property test and approached the machine's memory limit. It was stopped. The passing guard now constructs the real cutoff-local Bayesian training panel and exercises the Bayesian replay/policy/cache composition while substituting a deterministic cheap fitter in that property test. Operational ADVI convergence, recovery, and NUTS comparison remain validated by Plan03's dedicated tests.
- One walk-forward test mock initially rejected the new optional model arguments; the mock was updated and the full walk-forward module passed.

## Task Commit

- `db6a8f8` — `feat(07): add cutoff-local Bayesian replay selector`

## Next Plan Readiness

- Plan07-05 will commit the 2025 grouped target and scoring protocol before running its one-shot Bayesian versus linear evaluation.

---
*Phase: 07-bayesian-pace-model*
*Completed: 2026-11-16*
