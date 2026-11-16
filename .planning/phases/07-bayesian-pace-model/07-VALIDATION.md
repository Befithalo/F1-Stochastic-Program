---
phase: "07"
slug: "bayesian-pace-model"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-16"
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x with pytest-cov |
| **Config file** | pyproject.toml |
| **Quick run command** | uv run pytest tests/pace/test_bayesian_model.py -q |
| **Full suite command** | uv run pytest --cov=f1si --cov-report=term |
| **Estimated runtime** | ~300 seconds including the bounded NUTS reference |

## Sampling Rate

- **After every task commit:** Run the task's focused automated command below.
- **After every plan wave:** Run that plan's full verification command.
- **Before phase verification:** Run the full suite, strict type/lint/format checks, and CI on the exact pushed head.
- **Max feedback latency:** 30 seconds for routine unit tests; the dedicated NUTS reference test may exceed this budget and runs only at its named task.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | PAC-05 | — | Deterministic finite fit; explicit failure | unit/conformance | uv run pytest tests/pace/test_bayesian_model.py tests/conformance/test_suites.py -q | Created | pass |
| 07-01-02 | 01 | 1 | PAC-05 | — | Shared uncertainty is drawn once | integration | uv run pytest tests/sim/test_bayesian_pace.py tests/test_state_builder.py -q; uv run pytest tests/sim/test_reproducibility.py -q | Created | pass |
| 07-02-01 | 02 | 2 | PAC-05, DAT-03, DAT-04 | T-07-01 | No future rows/results enter fit | unit/guard | uv run pytest tests/pace/test_bayesian_training.py -q; uv run pytest tests/guards/test_future_scramble.py -q | Created | pass |
| 07-02-02 | 02 | 2 | PAC-05, DAT-05 | T-07-01 | Stable identities and era boundary | unit | uv run pytest tests/pace/test_bayesian_model.py tests/pace/test_bayesian_training.py -q | Created | pass |
| 07-03-01 | 03 | 3 | PAC-06 | — | Failed inference is reported | unit | uv run pytest tests/pace/test_bayesian_model.py -q | Created | pass |
| 07-03-02 | 03 | 3 | PAC-06 | — | Synthetic truth and uncertainty are measured | recovery/reference | uv run pytest tests/pace/test_bayesian_recovery.py -q | Created | pass |
| 07-04-01 | 04 | 4 | PAC-05, RPL-01, BKT-01 | T-07-01 | Same-cutoff history and snapshot | integration | uv run pytest tests/test_cli_replay.py tests/backtest/test_walk_forward.py tests/guards/test_future_scramble.py -q | Existing + TDD | pass |
| 07-04-02 | 04 | 4 | PAC-05, RPL-01 | T-07-01 | Future scramble leaves output unchanged | guard | uv run pytest tests/guards/test_future_scramble.py -q | Existing | pass |
| 07-05-01 | 05 | 5 | PAC-06 | T-07-01 | Lock race/sample before scoring | unit | uv run pytest tests/backtest/test_bayesian_accuracy.py -q | TDD task | pending |
| 07-05-02 | 05 | 5 | PAC-05, PAC-06, UI-03 | — | Publish actual result and denominator | docs/evaluation | uv run pytest tests/backtest/test_bayesian_accuracy.py tests/test_decisions_log.py tests/test_docs.py -q | TDD task | pending |

## Wave 0 Requirements

Existing pytest, synthetic fixtures, shared PaceModel conformance checks, and future-scramble infrastructure cover the test harness. Each new test file is created first within its own TDD task; no separate Wave 0 task is needed.

## Manual-Only Verifications

All Phase 7 acceptance criteria are automated. No UI review or manual checkpoint is in scope.

## Validation Sign-Off

- [ ] All tasks have automated verification.
- [ ] Sampling continuity: every task has a focused automated command.
- [x] Wave 0 is not needed; existing test infrastructure is in place.
- [x] No watch-mode flags.
- [ ] Full suite and exact-head CI pass.
- [ ] nyquist_compliant: true set after plan verification and successful execution.

**Approval:** pending
