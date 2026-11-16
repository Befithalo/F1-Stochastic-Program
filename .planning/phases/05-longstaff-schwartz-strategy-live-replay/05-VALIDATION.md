---
phase: "05"
slug: "longstaff-schwartz-strategy-live-replay"
status: pending_exact_head_ci
nyquist_compliant: false
wave_0_complete: true
created: "2026-11-13"
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest >=9.1,<10 |
| Config file | pyproject.toml |
| Quick run command | uv run python -m pytest -q tests/strategy/test_longstaff.py |
| Full suite command | uv run python -m pytest -q |
| Estimated runtime | 519 seconds from the Phase 5 full-suite run |

**Environment constraint (resolved locally):** Windows Application Control blocked the uv-managed Python child with OS error 4551. Official PSF-signed CPython 3.12.10 is now installed at `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` and its Authenticode signature verified as valid. Run local checks with `uv run --python <signed-python.exe> python -m ...`; the earlier blocked process is not counted as a pass.

---

## Sampling Rate

- After every task commit: run the focused test command listed for that task.
- After every plan wave: run the full pytest suite, ruff check, ruff format check, and strict mypy.
- Before phase verification: require green CI, the replay future-scramble guard, and a successful Bahrain replay in an authorized Python environment.
- Max feedback latency: target under 10 seconds for focused tests; the full suite is expected to take about 5m30s.

---

## Per-Task Verification Map

Plan and task IDs below match the finalized Phase 05 plans. Existing tests and verification evidence cover every task; no new test file was needed in this audit.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Test Files / Evidence | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|----------------------|--------|
| 05-01-01 | 05-01 | 1 | STR-01, RPL-02 | T-05-02, T-05-03 | Synthetic paths recover conditional-mean continuation; pathwise stopping and common draws are tested; selected-cutoff replay uses an as-of RaceState and refuses invalid input before simulation. | unit + CLI integration | `uv run python -m pytest -q tests/strategy/test_longstaff.py tests/test_cli_replay.py` | `tests/strategy/test_longstaff.py`, `tests/test_cli_replay.py` | pass |
| 05-01-02 | 05-01 | 1 | STR-02, STR-03, STR-04 | T-05-01, T-05-02 | Legal timing actions expose mean, spread, exact CVaR10 and score; risk bounds, rank changes, stable ordering and evidence-grounded reasons are covered. | unit + CLI integration | `uv run python -m pytest -q tests/strategy/test_longstaff.py tests/test_cli_replay.py` | `tests/strategy/test_longstaff.py`, `tests/test_cli_replay.py` | pass |
| 05-02-01 | 05-02 | 2 | RPL-01, RPL-02 | T-05-02, T-05-03 | Full replay prints ordered cutoff results, selected replay matches its full-replay row, and expected refusal paths include rejecting `--n > MAX_RACES` before race lookup or state construction. | CLI integration | `uv run python -m pytest tests/test_cli_replay.py tests/test_cli.py tests/test_cli_simulate.py -x -q` | `tests/test_cli_replay.py::test_replay_rejects_simulation_count_above_limit_before_loading_race`, `tests/test_cli.py`, `tests/test_cli_simulate.py` | pass |
| 05-02-02 | 05-02 | 2 | RPL-01, STR-01 | T-05-02 | Replay is registered as a future-scramble consumer and LongstaffSchwartzPolicy runs the shared StrategyPolicy conformance suite. | guard + conformance | `uv run python -m pytest tests/guards tests/test_decisions_log.py -x -q`; `uv run python -m pytest tests/conformance -x -q` | `tests/guards/consumers.py`, `tests/guards/test_future_scramble.py`, `tests/guards/test_consumer_registry.py`, `tests/conformance/test_suites.py` | pass |
| 05-03-01 | 05-03 | 3 | STR-04, RPL-02 | T-05-01, T-05-03 | Explainer, README, decision records and CLI help document actual behavior, accepted inputs and limitations; docs tests assert the tour and replay contract. | docs + CLI integration | `uv run python -m pytest tests/test_docs.py tests/test_decisions_log.py -x -q` | `tests/test_docs.py`, `tests/test_decisions_log.py`, `tests/test_cli_replay.py` | pass |
| 05-03-02 | 05-03 | 3 | RPL-02 | T-05-02 | The full lint, format, type and test gate passes; cached Bahrain full and selected replay smoke is separately recorded. | full automated gate + manual smoke | `uv run ruff check .`; `uv run ruff format --check .`; `uv run python -m mypy`; `uv run python -m pytest` | GitHub Actions run 43502700902; cached Bahrain evidence in 05-03-SUMMARY.md | pass |
| 05-04-01 | 05-04 | 4 | RPL-01 | T-05-05 | Sparse fallback uses only the cutoff snapshot, exposes generic-prior basis and broad uncertainty, and returns ranked finite options for lap 0 and a sparse cutoff; selected and full output agree at laps 0 and 5. | model + CLI integration | `uv run python -m pytest -q tests/test_cli_replay.py` | `tests/test_cli_replay.py::test_sparse_fallback_replay_returns_ranked_options_at_lap_zero_and_fallback_lap`; `::test_sparse_fallback_noise_floor_is_generic_at_lap_zero`; `::test_sparse_fallback_uses_cutoff_clean_residuals_and_robust_noise`; selected/full equality tests | green |
| 05-04-02 | 05-04 | 4 | STR-04, RPL-01 | T-05-05 | DEC-101, README, and explainer disclose cutoff-visible residuals, DEC-091 generic priors, assumed 1.0 s offset SD, and uncalibrated limits; existing tour, wording, and decision sequence assertions remain active. | docs + decision-log integration | `uv run python -m pytest tests/test_docs.py tests/test_decisions_log.py -x -q` | `tests/test_docs.py`; `tests/test_decisions_log.py`; 05-04-SUMMARY.md focused docs/replay/decision run | green |
| 05-04-03 | 05-04 | 4 | RPL-01, RPL-02 | T-05-05 | Registered replay consumer compares fallback status, all ranked metrics, and reason after future-row scrambling; existing full-grid, metadata, and locked-race guards remain in the guard suite. | property/integration + full quality gate | `uv run python -m pytest tests/guards/test_future_scramble.py tests/guards/test_consumer_registry.py tests/test_cli_replay.py -x -q`; `uv run ruff check .`; `uv run ruff format --check .`; `uv run python -m mypy`; `uv run python -m pytest` | `tests/guards/test_future_scramble.py::test_strategy_replay_fallback_ignores_future_at_sparse_cutoff`; 05-04-SUMMARY.md records 93 focused guard/replay tests, 989 passed/25 deselected, Ruff/format/mypy green | local green; exact-head cross-platform CI pending |

## Wave 0 Requirements

- [x] `tests/strategy/test_longstaff.py` covers conditional-mean continuation recovery, pathwise stopping, same-checkpoint/common-draw branches, rank-aware fallback, CVaR orientation and fractional boundary, risk endpoints, deterministic reasons, and policy behavior.
- [x] `tests/test_cli_replay.py` covers selected and all-cutoff replay, selected-lap equality, driver selection, and expected refusal paths.
- [x] `tests/guards/consumers.py` registers the replay consumer; future-scramble and consumer-registry tests exercise the registration.
- [x] `tests/conformance` runs Longstaff-Schwartz through the shared StrategyPolicy suite.
## Security Coverage

The project security gate is ASVS L1 with a high-severity block threshold. This CLI phase adopts the applicable versioned controls below as a focused verification contract, not as a certification claim. Control definitions are from ASVS 5.0.0.

| ASVS 5.0.0 Control | Phase evidence required | Validation |
|--------------------|-----------------------|------------|
| `v5.0.0-2.1.1` — document input rules | CLI help/README state the accepted race and driver identifiers, lap rules, positive simulation count, finite risk range [0,1], and risk default 0.5 | `tests/test_docs.py`; `tests/test_decisions_log.py` |
| `v5.0.0-2.2.1` — validate decision-bearing input against allowlists/ranges | Reject unknown race/driver, invalid lap/count, NaN/infinity, and risk outside [0,1] before simulation | `tests/strategy/test_longstaff.py`; `tests/test_cli_replay.py` |
| `v5.0.0-2.2.2` — enforce validation at the trusted service layer | Policy and replay entry points enforce the same finite/range/catalog rules even when called without parser help | `tests/strategy/test_longstaff.py`; `tests/test_cli_replay.py` |
| `v5.0.0-1.2.4` — parameterize database queries, when changed | Keep current-race data behind `AsOfAccessor`; any query added in this phase binds values and does not interpolate race/driver text | Replay integration tests and source review of any query changes |
| `v5.0.0-1.2.5` — prevent OS command injection | Replay does not invoke a shell or build an OS command from CLI values; race/driver lookup uses existing catalog APIs | `tests/test_cli_replay.py` refusal cases and source review |

| Threat Ref | Threat | Required validation |
|------------|--------|---------------------|
| T-05-01 | Invalid replay bounds or non-finite/out-of-range risk input | Test malformed driver/lap/race inputs and NaN, infinity, and values outside [0,1]; expected failures are friendly and do not start simulation. |
| T-05-02 | Future-data leakage into strategy decisions | Keep data access in the replay driver, pass only cutoff-built RaceState to the policy, register the as-of consumer, and retain the future-scramble guard. |
| T-05-03 | User-controlled race/driver text reaches shell or query construction | Resolve names through existing catalog/argument APIs; test unknown identifiers and confirm no raw shell or SQL interpolation is introduced. |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions / Result |
|----------|-------------|------------|----------------------------|
| Run a cached Bahrain 2023 replay for a real driver and inspect the complete recommendation table | RPL-02 | CI does not carry the local race cache, so the real-data smoke remains separate from automated coverage. | Plan 05-03 passed: full replay printed 57 ordered cutoffs and selected lap 20 matched. Plan 05-04 passed: `f1si replay bahrain-2023 --driver ALO --n 12` printed 57 ascending rows (43 identified-fit, 14 fallback, no unavailable rows); selected laps 0 and 5 matched their full-replay blocks. This smoke is separate from pytest and CI. |

**Observed local smoke:** Plan 05-03's default-size replay had 41 identified-fit and 16 unavailable cutoffs; its post-fix `--n 12` run confirmed punctuation and lap-20 equivalence. Plan 05-04 closes the unavailable rows with fallback: its `--n 12` run reported 43 identified-fit and 14 fallback rows; laps 0 and 5 matched selected/full output. These are smoke observations, not calibration results.

## Validation Sign-Off

- [x] All tasks have automated verification or Wave 0 dependencies.
- [x] Sampling continuity has no three consecutive tasks without automated verification.
- [x] Wave 0 covers all missing test files and registrations.
- [x] No watch-mode flags.
- [x] Local Nyquist validation is complete; final full suite: 989 passed, 25 deselected; focused docs/replay/decision tests: 70 passed; Ruff, format, and mypy passed.
- [ ] Exact-head CI is pending: run 43530884555 used the implementation SHA but Windows hit the old 20-minute job timeout; the workflow timeout was raised to 30 minutes and the new exact-head run must finish both Ubuntu and Windows jobs.

**Historical CI evidence:** Plan 05-03's earlier phase head passed both jobs in run [43502700902](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43502700902). It does not validate Plan 05-04. The Plan 05-04 run [43530884555](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43530884555) was for implementation head `3f979f84f2ae81292230779402635d5b7b077e24`; Ubuntu passed, Windows was cancelled at the old 20-minute limit. The timeout is now 30 minutes; exact-head cross-platform completion remains pending.

**Approval:** pending exact-head Ubuntu/Windows CI completion

## Validation Audit 2026-11-13

| Metric | Count |
|---|---|
| Gaps found | 4 |
| Resolved | 4 |
| Escalated | 0 |

## Validation Audit 2026-11-14 — Plan 05-04

| Metric | Count |
|---|---:|
| Plan 05-04 tasks mapped to concrete tests/commands | 3/3 |
| Behavioral coverage gaps found | 0 |
| Local automated checks green | yes |
| Bahrain real-data smoke green | yes |
| Exact-head cross-platform CI | pending 30-minute timeout run |

No new test file was needed. The sparse model and CLI behaviors are exercised by the named tests in `tests/test_cli_replay.py`; the docs task is checked by existing docs and decision-log tests; fallback future-scramble coverage is explicit at a sparse cutoff and runs with the registered consumer/full-grid guard suite. Final local evidence is **989 passed, 25 deselected**, **70 focused docs/replay/decision tests passed**, and Ruff, format, and mypy passed. The real Bahrain smoke is separately recorded above. The exact-head CI gate is the sole outstanding validation item; do not mark the phase fully validated until both matrix jobs pass on the current implementation HEAD.
