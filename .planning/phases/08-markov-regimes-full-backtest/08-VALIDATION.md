---
phase: "08"
slug: "markov-regimes-full-backtest"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-16"
---

# Phase 08 — Validation Strategy

> Validation contract for the regime model, its simulator integration, and the locked evaluation paths.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x with pytest-cov and Hypothesis |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/regime/test_markov.py tests/test_state_builder.py tests/sim/test_regime.py -q` |
| **Full suite command** | `uv run pytest --cov=f1si --cov-report=term` |
| **Estimated runtime** | ~300 seconds for the full suite; locked backtests are separate evaluation runs |

## Sampling Rate

- **After every task commit:** Run the focused automated command listed for that task.
- **After every plan wave:** Run all focused tests for the changed model, replay, backtest, and guard paths.
- **Before phase verification:** Run strict lint, format, type checks, full pytest, and CI on the exact pushed head.
- **Max feedback latency:** 60 seconds for focused unit tests; score runs may take longer and execute once per committed lock.

## Per-Requirement Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-* | 01 | 1 | REG-02 | T-08-01 | Transition fit uses only complete earlier in-sample feature rows; five-state rows are finite and normalized | unit/recovery/guard | `uv run pytest tests/regime/test_markov.py tests/guards/test_future_scramble.py -q` | New Markov test; existing guard | pending |
| 08-01-* | 01 | 1 | REG-03 | T-08-02 | Validated numeric state selects the locked per-regime pit cost without result-data access | unit/integration | `uv run pytest tests/test_state_builder.py tests/sim/test_regime.py -q` | Existing state test; new regime simulation test | pending |
| 08-02-* | 02 | 2 | BKT-03 | T-08-01 | Exactly the locked 20 in-sample races are scored with Phase 6 pairing and per-race/per-era denominators | unit/integration | `uv run pytest tests/backtest/test_walk_forward.py tests/backtest/test_scoring.py -q` | Existing backtest tests | pending |
| 08-03-* | 03 | 3 | BKT-05 | T-08-03 | Holdout lock is validated before the sole score; only the holdout evaluator imports the 2026 result door | unit/guard | `uv run pytest tests/backtest/test_holdout.py tests/guards/test_import_ban.py tests/guards/test_future_scramble.py -q` | New holdout test; existing guards | pending |

Task IDs, plan numbers, and waves are provisional until the plan set is finalized; update this map to match each executable task before phase execution.

## Wave 0 Requirements

No separate Wave 0 is needed. Existing pytest, fixtures, and guard infrastructure are in place. New test files must be created before their implementation within their owning tasks.

## Manual-Only Verifications

All phase success criteria have automated verification. The once-only locked scores are controlled automated evaluations, not manual-only checks. No UI review is in scope.

## Validation Sign-Off

- [ ] Every plan task has an automated verification command or an explicit Wave 0 dependency.
- [ ] No three consecutive tasks lack focused automated verification.
- [ ] No watch-mode flags are used.
- [ ] Full suite and CI pass on the exact pushed head.
- [ ] `nyquist_compliant: true` is set only after plan verification and successful execution.

**Approval:** pending
