---
phase: "08"
plan: "06"
subsystem: validation
tags: [nyquist, report-verification, ci, closeout]
status: complete
dependency_graph:
  requires: [08-01 through 08-05 implementations, both locked reports]
  provides: [decision regression, complete validation evidence, phase closeout]
  affects: [Phase 8 completion, M1 audit]
tech_stack:
  added: []
  patterns: [report verification without scoring, exact-head CI]
key_files:
  created: [.planning/phases/08-markov-regimes-full-backtest/08-06-SUMMARY.md]
  modified:
    - tests/test_decisions_log.py
    - tests/test_docs.py
    - README.md
    - docs/explained/phase-08.md
    - .planning/phases/08-markov-regimes-full-backtest/08-05-SUMMARY.md
    - .planning/phases/08-markov-regimes-full-backtest/08-VALIDATION.md
decisions: [DEC-121, DEC-122, DEC-123, DEC-124, DEC-125, DEC-126, DEC-127, DEC-128, DEC-129]
requirements-completed: [REG-02, REG-03, BKT-03, BKT-05]
metrics:
  completed_date: 2026-11-17
  task_count: 2
  focused_tests: 344
  documentation_holdout_decision_tests: 71
  full_tests_passed: 1243
  full_tests_deselected: 33
  total_coverage_percent: 87
  full_test_warnings: 8
  full_test_runtime_seconds: 1494.58
  exact_head_ci: pending_closeout_commit
actuals:
  tasks: 2
  commits: 1
---

# Phase 08 Plan 06: Final Validation and Decision Records

The locked 20-race in-sample report and separate nine-race 2026 holdout report verify read-only. Phase 8 implementation and local validation are complete; final exact-head Ubuntu and Windows CI is still required before Nyquist sign-off.

## Accomplishments

- Extended the decision-log regression through DEC-129 and verified all Phase 8 decision records and unresolved model assumptions.
- Fixed the holdout verifier to require every field named by the lock, accept only the known list-valued `predictions` extension emitted by the scorer, and reject unregistered top-level fields. The lock and scored report were not modified.
- Published separate 20-race in-sample and nine-race holdout metrics, report links, denominators, and the pre-registered-but-retrospectively-unblinded limitation.
- Updated the Phase 8 validation map for all thirteen plan tasks.
- No UI/UX scope was added.

## Validation

- Phase 8 focused set: 344 passed in 550.04 seconds.
- `uv run f1si backtest --report --output reports/backtest/phase-08.json --verify-existing` — passed read-only.
- `uv run f1si holdout --verify-existing --output reports/backtest/phase-08-holdout.json` — passed read-only.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — 192 files already formatted.
- `uv run mypy` — no issues in 178 source files.
- `uv run pytest --cov=f1si --cov-report=term` — 1,243 passed, 33 deselected, 8 warnings in 1,494.58 seconds; total coverage 87%.
- `uv run pytest tests/backtest/test_holdout.py tests/test_decisions_log.py -q` — 51 passed after the frozen prediction-row validation fix.
- Final pushed-head Ubuntu and Windows checks remain pending on the closeout commit.

## Results and Limits

The in-sample 2023–2025 report has podium Brier 0.05546 vs 0.07369 grid baseline, top-10 Brier 0.14465 vs 0.16909, 82.26% 90% finish-interval coverage, +1.174 laps signed stop-timing error, and 17.22% team-call agreement.

The holdout has podium Brier 0.06639, top-10 Brier 0.14948, 73.03% finish-interval coverage, +2.064 laps signed stop-timing error, and 1.87% team-call agreement. It was scored once with result access after a prior preflight-only failure. Because schedule research incidentally exposed outcomes before scoring, it is pre-registered but retrospectively unblinded, not blind. Do not tune or rescore.

Phase 7 PAC-06 remains unmet: its locked Bayesian pace evaluation had 0.538745 s MAE versus 0.364033 s for the linear baseline. The Phase 8 reports do not change that result.

## Self-Check

- Both report verifiers passed without opening data access or recomputing predictions.
- The holdout lock and report are unchanged by DEC-128 and DEC-129.
- The full local validation suite is green; exact-head CI is the only remaining Phase 8 validation gate.
