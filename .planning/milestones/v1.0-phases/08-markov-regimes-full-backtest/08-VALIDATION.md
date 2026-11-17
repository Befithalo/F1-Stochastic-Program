---
phase: "08"
slug: "markov-regimes-full-backtest"
status: validated
nyquist_compliant: true
wave_0_complete: true
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
| **Estimated runtime** | ~25 minutes for the full suite; locked backtests are separate evaluation runs |

## Sampling Rate

- **After every task commit:** Run the focused automated command listed for that task.
- **After every plan wave:** Run all focused tests for the changed model, replay, backtest, and guard paths.
- **Before phase verification:** Run strict lint, format, type checks, full pytest, and CI on the exact pushed head.
- **Max feedback latency:** 60 seconds for focused unit tests; score runs execute once per committed lock.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | REG-02, REG-03 | T-08-01 | Bahrain replay carries cutoff regime through the numeric simulator and changes the controlled SC recommendation | replay/integration | `uv run pytest tests/test_cli_replay.py -q` | Existing + extended | passed in focused suite |
| 08-01-02 | 01 | 1 | REG-02, REG-03 | T-08-02 | State serialization, numeric validation, all five costs, and SC-only mechanics are covered | state/simulation | `uv run pytest tests/test_state_builder.py tests/sim/test_safety_car.py -q` | Existing + extended | passed in focused suite |
| 08-02-01 | 02 | 2 | REG-02 | T-08-06 | Label precedence, seeded known-matrix recovery, smoothing, and race boundaries are verified | unit/recovery | `uv run pytest tests/regime/test_markov.py -q` | New Markov test | passed in focused suite |
| 08-02-02 | 02 | 2 | REG-03 | T-08-06 | Regime costs and DEC-121..123 measurement/assumption wording match the locks | cost/decision | `uv run pytest tests/test_state_builder.py tests/sim/test_safety_car.py tests/test_decisions_log.py -q` | Existing + extended | passed in focused suite |
| 08-03-01 | 03 | 3 | BKT-03 | T-08-03 | Exact 20-race sample/settings and holdout one-shot boundary are committed before predictions | lock/preflight | `uv run pytest tests/backtest/test_walk_forward.py -q` | Existing + extended | passed in focused suite |
| 08-03-02 | 03 | 3 | BKT-03 | T-08-03 | Prediction/result ordering, Phase 6 metrics, race/era denominators, and read-only verification are tested | runner/metrics | `uv run pytest tests/backtest/test_walk_forward.py tests/backtest/test_metrics.py -q` | Existing + extended | passed in focused suite |
| 08-03-03 | 03 | 3 | BKT-03 | T-08-03 | One committed in-sample report verifies against its lock with every registered row | locked evaluation | `uv run f1si backtest --report --output reports/backtest/phase-08.json --verify-existing` | Existing report | passed; read-only |
| 08-04-01 | 04 | 4 | BKT-05 | T-08-04 | Feature-only fit and committed exact holdout lock fail closed before result access | evaluator/lock | `uv run pytest tests/backtest/test_holdout.py -q` | New holdout test | passed in focused suite |
| 08-04-02 | 04 | 4 | BKT-05 | T-08-04 | Only the dedicated evaluator may cross the result door; future-scramble guards pass | import/future guard | `uv run pytest tests/guards/test_import_ban.py tests/guards/test_future_scramble.py -q` | Existing guards + extension | passed in focused suite |
| 08-05-01 | 05 | 5 | BKT-05 | T-08-07 | One holdout report matches its committed lock and verifies without rescoring | locked evaluation | `uv run f1si holdout --verify-existing --output reports/backtest/phase-08-holdout.json` | Existing report | passed after read-only verifier correction |
| 08-05-02 | 05 | 5 | BKT-03, BKT-05 | T-08-07 | Public metrics match separate reports and retain per-race denominators and limitations | docs/report | `uv run pytest tests/test_docs.py -q` | Existing + extended | passed: 28 tests |
| 08-06-01 | 06 | 6 | REG-02, REG-03, BKT-03, BKT-05 | T-08-05 | DEC-121..129, assumptions, and the Phase 7 PAC-06 miss remain explicit and accurate | decision log | `uv run pytest tests/test_decisions_log.py -q` | Existing + extended | passed in focused and full suites |
| 08-06-02 | 06 | 6 | REG-02, REG-03, BKT-03, BKT-05 | T-08-05 | Focused paths, read-only report checks, strict checks, full pytest, and exact-head CI are recorded | phase validation | commands below | Existing + extended | local checks and exact-head Ubuntu/Windows CI passed |

## Wave 0 Requirements

No separate Wave 0 is needed. Existing pytest, fixtures, and guard infrastructure are in place. New test files were created before their implementation within their owning tasks.

## Manual-Only Verifications

All Phase 8 success criteria have automated verification. The once-only locked scores are controlled automated evaluations, not manual-only checks. No UI review is in scope.

## Executed Validation (2026-11-17)

| Command | Result |
|---------|--------|
| `uv run pytest tests/test_cli_replay.py tests/test_state_builder.py tests/sim/test_safety_car.py tests/regime/test_markov.py tests/backtest/test_walk_forward.py tests/backtest/test_metrics.py tests/backtest/test_holdout.py tests/guards/test_import_ban.py tests/guards/test_future_scramble.py tests/test_docs.py tests/test_decisions_log.py -q` | Passed: 344 tests in 550.04s |
| `uv run f1si backtest --report --output reports/backtest/phase-08.json --verify-existing` | Passed; read-only, no scoring |
| `uv run f1si holdout --verify-existing --output reports/backtest/phase-08-holdout.json` | Passed; read-only, no result access or scoring |
| `uv run ruff check .` | Passed: All checks passed |
| `uv run ruff format --check .` | Passed: 192 files already formatted |
| `uv run mypy` | Passed: no issues in 178 source files |
| `uv run pytest --cov=f1si --cov-report=term` | Passed: 1,243 passed, 33 deselected, 8 warnings, 1,494.58s; total coverage 87% |
| `uv run pytest tests/backtest/test_holdout.py tests/test_decisions_log.py -q` | Passed: 51 tests after DEC-129 prediction-row validation |
| Exact-head GitHub Actions | Run [44163005087](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/44163005087), SHA `9e2fd7575b29ceb1f1a2b6a8ce8aecd4f1fd919d`; `checks (ubuntu-latest)` and `checks (windows-latest)` both successful |

Both reports remain separate. The 20-race 2023–2025 report has 82.26% interval coverage and the 2026 holdout has 73.03%; do not pool these regulation-era samples. The holdout is pre-registered but retrospectively unblinded because schedule research incidentally displayed outcome information. The failed first invocation stopped before result access; the second produced the sole successful result-accessing score. Do not tune or rescore.

## Validation Sign-Off

- [x] Every plan task has an automated verification command or an explicit Wave 0 dependency.
- [x] No three consecutive tasks lack focused automated verification.
- [x] No watch-mode flags are used.
- [x] Both report verifiers, strict lint/format/type checks, and full pytest pass locally.
- [x] Exact-head Ubuntu and Windows CI pass on the final pushed head.
- [x] `nyquist_compliant: true` is set only after exact-head CI passes.

**Approval:** automated validation complete; judgment-tier prohibitions remain disclosed in Phase 8 verification.
**Phase status:** implementation and validation are complete; exact-head CI passed on Ubuntu and Windows. Phase 7 PAC-06 remains unmet and is not represented as passed. Phase 8 metrics are observational results, not calibration or competitive-superiority claims.

## Holdout Score and Evaluation Limitation

The exact score command was invoked twice: the first invocation failed at schedule preflight for 2026-09 and made no result-access call; after DEC-127 locked ex-ante schedule distances, the second completed with exactly one successful result-accessing score. It produced `reports/backtest/phase-08-holdout.json` for the nine locked races using linear pace, 1,000 simulations, seed 0, and risk 0.5. The report contains 11,352 prediction rows and 11,282 Brier observations. Its podium Brier is 0.06639, top-10 Brier is 0.14948, 90% interval coverage is 6,947/9,513 (73.03%), signed stop-timing error is +2.064 laps, and team-call agreement is 1.87% across 267 matched stops.

The first read-only verifier attempt revealed that the lock listed required fields while the score writer also emitted its known `predictions` extension. DEC-128 narrows the fix to that list-valued extension and continues to reject unknown fields. The later code review found malformed rows could still pass; DEC-129 validates each frozen prediction row against the exact emitted shape, types, locked schedule bounds, and probability/finish constraints. The report and lock are unchanged; verification remains read-only.

Search output and adjacent FIA media-kit classifications incidentally displayed outcome information during earlier schedule research. No displayed outcome values were copied into code, locks, metrics, or tuning. Describe this score as **pre-registered but retrospectively unblinded**, never blind. Do not change the sample, cutoffs, metrics, model, report, or score.
