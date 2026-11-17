---
phase: "08"
plan: "05"
subsystem: evaluation
tags: [holdout, blocked, schedule-metadata, disclosure]
status: blocked
dependency_graph:
  requires: [08-04 holdout lock, evaluator, and future-data guards]
  provides: [one failed preflight record, explicit holdout blocker, DEC-126]
  affects: [08-06 validation, Phase 8 completion]
tech_stack:
  added: []
  patterns: [fail closed when ex-ante schedule horizon is unavailable]
key_files:
  created: [.planning/phases/08-markov-regimes-full-backtest/08-05-SUMMARY.md]
  modified: [DECISIONS.md, .planning/phases/08-markov-regimes-full-backtest/08-VALIDATION.md]
decisions: [DEC-126]
metrics:
  completed_date: 2026-11-17
  score_invocations: 1
  reports_produced: 0
actuals:
  tasks: 0
  commits: 0
---

# Phase 08 Plan 05: Locked Holdout Evaluation Blocker

The prescribed holdout score stopped at schedule preflight because the locked 2026-09 event lacks scheduled race distance metadata; no result access, score, or report occurred.

## Execution Record

The exact prescribed command was invoked once:

```text
uv run f1si holdout --score --output reports/backtest/phase-08-holdout.json --n 1000 --risk 0.5 --seed 0
```

It exited 1 with `ValueError: Scheduled race distance is unavailable for 2026-09.` The evaluator opened only a cutoff-visible feature snapshot before raising. It did not call the final-classification/result accessor. `reports/backtest/phase-08-holdout.json` was not created, and the read-only verifier was not run because there is no report.

Local cutoff-visible metadata has no `scheduled_laps` values for the 2026 holdout events, and the committed holdout lock has no per-race distances. For locked event 2026-16, local calendar metadata identifies Sepang but supplies no authoritative ex-ante scheduled horizon. No observed 2026 lap count or outcome was used to fill this gap. No horizon was guessed or borrowed.

## Procedural Exposure and Limitation

During schedule research, search result snippets displayed 2026 outcome information. An opened FIA media-kit PDF displayed season classifications adjacent to its schedule table. No outcome values were copied into code, lock settings, metrics, tuning, or any report. The outcome display exposure means any later evaluation must be described as **pre-registered but retrospectively unblinded**, never blind.

DEC-126 records the decision to keep the score pending until authoritative ex-ante schedule metadata is available for the locked event. Do not change the holdout sample, cutoff, settings, model, metrics, or schema to bypass this blocker. Do not retry the one-time score. The Phase 8 holdout outcome and Phase 8 completion remain pending.

## Verification

- Score invocation count: 1; failed before result access.
- Holdout report: absent; no metrics produced.
- `--verify-existing`: not run because no report exists.
- No 2026 final classifications or race-result values were accessed for scoring or tuning.

## Deferred Work

- Obtain and review authoritative ex-ante scheduled-lap/distance metadata for 2026-16 without consulting results.
- Only after an approved lock-compatible schedule metadata change is committed, determine whether the one-score boundary can still be honored; this summary does not authorize a retry.
- Complete report-linked public documentation, holdout verification, full validation, and exact-head CI only if a valid report is produced under the registered boundary.
