---
phase: "08"
slug: "markov-regimes-full-backtest"
status: blocked
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
| 08-05-01 | 05 | 5 | BKT-05 | T-08-07 | One holdout report matches its committed lock and verifies without rescoring | locked evaluation | `uv run f1si holdout --verify-existing --output reports/backtest/phase-08-holdout.json` | New command path | blocked: no report produced; score preflight failed |
| 08-05-02 | 05 | 5 | BKT-03, BKT-05 | T-08-07 | Public metrics match separate reports and retain per-race/per-era denominators and limitations | docs/report | `uv run pytest tests/test_docs.py -q` | Existing + extended | partial: 27 docs tests pass; holdout metrics publication pending because report absent |
| 08-06-01 | 06 | 6 | REG-02, REG-03, BKT-03, BKT-05 | T-08-05 | DEC-121..126 and unresolved assumptions remain explicit and accurate | decision log | `uv run pytest tests/test_decisions_log.py -q` | Existing + extended | passed: 30 passed |
| 08-06-02 | 06 | 6 | REG-02, REG-03, BKT-03, BKT-05 | T-08-05 | Independent focused paths and checks recorded; report-dependent checks remain pending | partial validation | focused safe pytest set: 309 passed; post-fix focused tests: 64 passed; docs tests: 27 passed; full pytest: 1,227 passed; in-sample report verifier, Ruff lint/format, and mypy passed; holdout verifier unavailable; exact-head CI recorded below | Existing CI | partial; phase incomplete |

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
**Phase status:** incomplete; 08-05 holdout score and report are blocked. No final-classification access occurred during the sole failed score preflight; no score or report was produced. The execution is not Nyquist compliant.

## Executed Independent Validation (2026-11-17)

The following 08-06 checks do not require the missing holdout report and were run:

| Command | Result |
|---------|--------|
| `uv run pytest tests/test_decisions_log.py -q` | Passed, 30 tests in 0.28s |
| `uv run pytest tests/test_cli_replay.py tests/test_state_builder.py tests/sim/test_safety_car.py tests/regime/test_markov.py tests/backtest/test_walk_forward.py tests/backtest/test_metrics.py tests/backtest/test_holdout.py tests/guards/test_import_ban.py tests/guards/test_future_scramble.py tests/test_decisions_log.py -q` | Passed, 309 tests in 542.71s |
| `uv run pytest tests/backtest/test_holdout.py tests/test_cli_replay.py tests/test_decisions_log.py -q` | Passed after typing fixes, 64 tests in 301.18s |
| `uv run pytest tests/test_docs.py -q` | Passed, 27 tests in 0.21s; Phase 8 docs explicitly state the holdout is pending and has no metrics |
| `uv run f1si backtest --report --output reports/backtest/phase-08.json --verify-existing` | Passed: verified committed in-sample report; read-only |
| `uv run ruff check .` | Passed: All checks passed |
| `uv run ruff format --check .` | Passed: 191 files already formatted |
| `uv run mypy` | Passed after minimal typing fixes: Success, no issues found in 178 source files |
| `uv run pytest --cov=f1si --cov-report=term` | Passed: 1,227 passed, 33 deselected, 8 PyTensor warnings, 1,505.01s; total coverage 87% |
| Exact-head GitHub Actions query | On `e8040382f4d4d6dc89eff93b4d6628c253ef7200`, `checks (ubuntu-latest)` and `checks (windows-latest)` both completed successfully |

The documentation tests passed without introducing any fabricated holdout figures. The in-sample report verified; the holdout report verifier cannot run because no report exists. The recorded CI result applies to exact pushed head `e8040382f4d4d6dc89eff93b4d6628c253ef7200`; this validation metadata update will trigger a new exact-head CI run. Final Nyquist sign-off remains pending because the holdout score/report is absent. `nyquist_compliant: false` remains in force.

## Holdout Blocker and Evaluation Limitation

The prescribed command was invoked exactly once: `uv run f1si holdout --score --output reports/backtest/phase-08-holdout.json --n 1000 --risk 0.5 --seed 0`. It exited 1 during schedule preflight with `ValueError: Scheduled race distance is unavailable for 2026-09.` It opened only a cutoff-visible feature snapshot and failed before any final-classification/result call. The report path remains absent; `--verify-existing` was not run because there is no report to verify.

Local cutoff-visible metadata has no scheduled-laps values for the 2026 holdout rounds, and the committed lock contains no per-race schedule distances. No authoritative ex-ante scheduled-lap or distance metadata for locked event 2026-16 (Sepang) was found in local project calendar metadata. The horizon must not be inferred from observed 2026 laps or guessed. DEC-126 records this decision and leaves the holdout and phase incomplete.

Two incidental outcome-display exposures occurred during schedule research: search result snippets displayed 2026 outcomes, and an opened FIA media-kit PDF displayed season classifications adjacent to its schedule table. No outcome values were copied into code, locks, metrics, tuning, or reports. These exposures mean any eventual evaluation must be called pre-registered but retrospectively unblinded, not blind. No scoring was produced.
