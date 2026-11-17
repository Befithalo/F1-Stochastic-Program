---
phase: "08"
plan: "05"
subsystem: evaluation
tags: [holdout, out-of-sample, schedule-metadata, disclosure]
status: complete
dependency_graph:
  requires: [08-04 holdout lock, evaluator, and future-data guards]
  provides: [one locked nine-race 2026 holdout report, read-only report verification]
  affects: [08-06 validation, Phase 8 completion]
tech_stack:
  added: []
  patterns: [locked ex-ante race schedule, one successful result-accessing score]
key_files:
  created: [reports/backtest/phase-08-holdout.json]
  modified:
    - src/f1si/evaluation/holdout.py
    - tests/backtest/test_holdout.py
    - DECISIONS.md
    - README.md
    - docs/explained/phase-08.md
    - .planning/phases/08-markov-regimes-full-backtest/08-VALIDATION.md
decisions: [DEC-126, DEC-127, DEC-128]
requirements-completed: [BKT-05]
metrics:
  completed_date: 2026-11-17
  score_invocations: 2
  successful_result_access_scores: 1
  reports_produced: 1
  races: 9
  prediction_rows: 11352
  brier_observations: 11282
  podium_brier: 0.0663854650899058
  top10_brier: 0.1494765222979027
  finish_interval_90_coverage: 0.7302638494691475
  finish_interval_covered: 6947
  finish_interval_classified: 9513
  matched_stop_events: 267
  observed_stop_events: 378
  signed_stop_timing_error_laps: 2.0636704119850187
  team_call_agreement: 0.018726591760299626
actuals:
  tasks: 2
  commits: 2
---

# Phase 08 Plan 05: Locked Holdout Evaluation Summary

The registered nine-race 2026 holdout has been scored once after an earlier feature-only schedule preflight failure. The report verifies against the unchanged lock without opening data access or recomputing predictions.

## Execution Record

The prescribed command was invoked twice in total:

```text
uv run f1si holdout --score --output reports/backtest/phase-08-holdout.json --n 1000 --risk 0.5 --seed 0
```

The first invocation exited before result access because 2026-09 had no scheduled-lap metadata. DEC-127 then added ex-ante schedule provenance for all nine locked events and the matching code/tests were committed. The second invocation completed and produced `reports/backtest/phase-08-holdout.json`. Predictions were frozen before the first final-classification request. The first invocation did not consume the single successful result-accessing score; there has been exactly one successful score and no rescore.

The locked report contains 11,352 prediction rows and 11,282 Brier observations. Its aggregate metrics are:

| Metric | Result |
|---|---:|
| Podium Brier | 0.06639 |
| Top-10 Brier | 0.14948 |
| 90% finish-interval coverage | 6,947/9,513 = 73.03% |
| Signed stop-timing error | +2.064 laps across 267 matched stops |
| Team-call agreement | 1.87% across 267 matched stops |

The 378 observed stop events and all nine locked race rows remain in the report. These 2026 metrics have no matched grid-baseline comparison.

## Verification and Verifier Correction

- `uv run f1si holdout --verify-existing --output reports/backtest/phase-08-holdout.json` first exposed a verifier schema bug: the report had all lock-required fields plus the known `predictions` extension emitted by the scorer.
- DEC-128 records the repair. The verifier now requires every locked field, accepts only the known list-valued `predictions` extension, rejects unknown top-level fields, and remains read-only.
- `uv run pytest tests/backtest/test_holdout.py tests/test_decisions_log.py -q` — 43 passed after the correction.
- `uv run ruff check src/f1si/evaluation/holdout.py tests/backtest/test_holdout.py tests/test_decisions_log.py` — passed.
- `uv run ruff format --check src/f1si/evaluation/holdout.py tests/backtest/test_holdout.py tests/test_decisions_log.py` — passed.
- The required `--verify-existing` command now passes without prediction, catalog, or result access.

## Evaluation Limitation

During prior schedule research, search output and adjacent FIA media-kit classifications incidentally displayed outcome information. No displayed values were used in the code, lock, metrics, or tuning. The score is therefore **pre-registered but retrospectively unblinded**, not blind. Do not tune or rescore the holdout.

The separate 20-race 2023–2025 report remains the in-sample evaluation; the nine-race 2026 report must not be pooled with it. The low holdout team-call agreement and interval coverage are reported as measured outcomes, not hidden or described as proof of calibration or model superiority.
