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
| **Quick run command** | `uv run pytest tests/test_cli_replay.py tests/regime/test_markov.py tests/test_state_builder.py tests/sim/test_safety_car.py -q` |
| **Full suite command** | `uv run pytest --cov=f1si --cov-report=term` |
| **Estimated runtime** | ~300 seconds for the full suite; locked backtests are separate evaluation runs |

## Sampling Rate

- **After every task commit:** Run the focused automated command listed for that task.
- **After every plan wave:** Run all focused tests for the changed model, replay, backtest, and guard paths.
- **Before phase verification:** Run strict lint, format, type checks, full pytest, and CI on the exact pushed head.
- **Max feedback latency:** 60 seconds for focused unit tests; score runs may take longer and execute once per committed lock.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | REG-02, REG-03 | T-08-01 | Bahrain replay carries cutoff regime through the numeric simulator and changes the controlled SC recommendation | replay/integration | `uv run pytest tests/test_cli_replay.py -q` | Existing + extended | pending |
| 08-01-02 | 01 | 1 | REG-02, REG-03 | T-08-02 | State serialization, numeric validation, all five costs, and SC-only mechanics are covered | state/simulation | `uv run pytest tests/test_state_builder.py tests/sim/test_safety_car.py -q` | Existing + extended | pending |
| 08-02-01 | 02 | 2 | REG-02 | T-08-06 | Label precedence, seeded known-matrix recovery, smoothing, and race boundaries are verified | unit/recovery | `uv run pytest tests/regime/test_markov.py -q` | New Markov test | pending |
| 08-02-02 | 02 | 2 | REG-03 | T-08-06 | Regime costs and DEC-121..123 measurement/assumption wording match the locks | cost/decision | `uv run pytest tests/test_state_builder.py tests/sim/test_safety_car.py tests/test_decisions_log.py -q` | Existing + extended | pending |
| 08-03-01 | 03 | 3 | BKT-03 | T-08-03 | Exact 20-race sample/settings and holdout one-shot boundary are committed before predictions | lock/preflight | `uv run pytest tests/backtest/test_walk_forward.py -q` | Existing + extended | pending |
| 08-03-02 | 03 | 3 | BKT-03 | T-08-03 | Prediction/result ordering, Phase 6 metrics, race/era denominators, and read-only verification are tested | runner/metrics | `uv run pytest tests/backtest/test_walk_forward.py tests/backtest/test_metrics.py -q` | Existing + extended | pending |
| 08-03-03 | 03 | 3 | BKT-03 | T-08-03 | One committed in-sample report verifies against its lock with every registered row | locked evaluation | `uv run f1si backtest --report --output reports/backtest/phase-08.json --verify-existing` | New command path | pending |
| 08-04-01 | 04 | 4 | BKT-05 | T-08-04 | Feature-only fit and committed exact holdout lock fail closed before result access | evaluator/lock | `uv run pytest tests/backtest/test_holdout.py -q` | New holdout test | pending |
| 08-04-02 | 04 | 4 | BKT-05 | T-08-04 | Only the dedicated evaluator crosses the result door and future-scramble guards pass | import/future guard | `uv run pytest tests/guards/test_import_ban.py tests/guards/test_future_scramble.py -q` | Existing guards + extension | pending |
| 08-05-01 | 05 | 5 | BKT-05 | T-08-07 | One holdout report matches its committed lock and verifies without rescoring | locked evaluation | `uv run f1si holdout --verify-existing --output reports/backtest/phase-08-holdout.json` | New command path | pending |
| 08-05-02 | 05 | 5 | BKT-03, BKT-05 | T-08-07 | Public metrics match separate reports and retain per-race/per-era denominators and limitations | docs/report | `uv run pytest tests/test_docs.py -q` | Existing + extended | pending |
| 08-06-01 | 06 | 6 | REG-02, REG-03, BKT-03, BKT-05 | T-08-05 | DEC-121..125 and unresolved assumptions remain explicit and accurate | decision log | `uv run pytest tests/test_decisions_log.py -q` | Existing + extended | pending |
| 08-06-02 | 06 | 6 | REG-02, REG-03, BKT-03, BKT-05 | T-08-05 | Bahrain, focused paths, report verifiers, strict checks, full suite, and exact-head Ubuntu/Windows CI pass | full CI | focused phase pytest; both report verifiers; `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy`; `uv run pytest --cov=f1si --cov-report=term`; exact-head check-runs API | Existing CI | pending |

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
