---
phase: 07-bayesian-pace-model
plan: "05"
subsystem: pace-evaluation
tags: [bayesian-pace, holdout, reporting]
requires:
  - phase: 07-bayesian-pace-model
    provides: Cutoff-local Bayesian pace fit and opt-in replay/backtest integration
provides:
  - Pre-registered one-shot 2025 next-lap evaluation report
  - Public documentation of the measured outcome and unmet PAC-06 gate
affects: [phase-07-closeout, phase-08]
tech-stack:
  added: []
  patterns: [locked chronological holdout, independent cutoff worker processes, paired target scoring]
key-files:
  created:
    - reports/pace/phase-07.json
    - docs/phases/07-bayesian-pace-model.md
  modified:
    - src/f1si/backtest/pace_evaluation.py
    - DECISIONS.md
    - README.md
    - docs/explained/phase-07.md
    - tests/backtest/test_bayesian_accuracy.py
    - tests/test_docs.py
    - tests/test_decisions_log.py
key-decisions:
  - "Run the committed 2025 race group once and retain every race in the denominator, including 2025-01 with zero paired targets."
  - "Record PAC-06 as unmet because Bayesian MAE was 47.993% higher than the linear baseline; do not tune or rerun the holdout."
  - "Keep the real-data between-era effect unidentified because the evaluated rows all belong to one regulation era."
requirements-completed: [PAC-05, UI-03]
requirements-not-met: [PAC-06]
duration: 41min
completed: 2026-11-16
status: complete
---

# Phase 7 Plan 05: Locked Bayesian Pace Evaluation Summary

**The locked score is published with its actual result: the Bayesian model did not meet the real-data improvement gate.**

## Accomplishments

- Committed the chronological 2025 race group and exact target protocol before scoring.
- Isolated each cutoff fit in a short-lived worker process; all 74 fits completed with no failures.
- Ran the score once and verified the existing report read-only afterward.
- Reported 1,348 paired targets (1,344 unique driver-target laps), with race-level denominators and fit diagnostics.
- Recorded linear MAE 0.364033 seconds and Bayesian MAE 0.538745 seconds. Bayesian MAE was 47.993% higher; PAC-06 is not met.
- Updated README, Phase 7 explainer, phase summary, decision log, and report-backed documentation tests.

## Verification

- uv run python -m f1si.backtest.pace_evaluation --verify-existing — passed; confirmed lock digest and existing report without rescoring.
- uv run pytest tests/backtest/test_bayesian_accuracy.py tests/test_decisions_log.py tests/test_docs.py -q — 61 passed.

## Limitations

- 2025-01 remains in the registered race group but contributed zero paired clean next-lap targets; 2025-02 contributed 776 and 2025-03 contributed 572.
- All real rows belong to the 2022–2025 ground-effect era, so the real evaluation cannot identify a between-era effect.
- PAC-06 remains unmet. The locked sample and model were not changed after observing the result.
