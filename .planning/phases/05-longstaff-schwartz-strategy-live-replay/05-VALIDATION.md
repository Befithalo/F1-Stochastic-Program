---
phase: "05"
slug: "longstaff-schwartz-strategy-live-replay"
status: draft
nyquist_compliant: true
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

Plan and task IDs are provisional until the planner assigns the final plan structure.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | TBD | TBD | STR-01 | T-05-02 | Synthetic paths recover conditional continuation values; stopping is pathwise, checkpoint branches are reproducible, fallback is rank-aware, and policy conformance passes | unit + conformance | uv run python -m pytest -q tests/strategy/test_longstaff.py tests/conformance/test_suites.py | New strategy tests; shared suite exists | pass |
| 05-01-02 | TBD | TBD | STR-02 | — | Pit now, pit in 1-5 laps, and stay out use common scenarios and expose mean, spread, worst-decile CVaR, and blended score; fractional tail boundary and ties are covered | unit | uv run python -m pytest -q tests/strategy/test_longstaff.py | New strategy tests | pass |
| 05-01-03 | TBD | TBD | STR-03 | T-05-01 | Finite risk input is bounded to [0,1]; both endpoints and a sample that changes rank are covered | unit | uv run python -m pytest -q tests/strategy/test_longstaff.py | New strategy tests | pass |
| 05-01-04 | TBD | TBD | STR-04 | T-05-02 | Repeated same-state calls return the same evidence-based reason; reasons use cutoff-visible inputs and never invent future events | unit | uv run python -m pytest -q tests/strategy/test_longstaff.py | New strategy tests | pass |
| 05-01-05 | TBD | TBD | RPL-01 | T-05-02 | Every cutoff rebuilds snapshot, fit, filter output, and RaceState through AsOfAccessor; future-scramble and selected-lap equivalence pass | integration + future-scramble | uv run python -m pytest -q tests/test_cli_replay.py tests/guards/test_future_scramble.py | New replay tests; guard exists | pass |
| 05-01-06 | TBD | TBD | RPL-02 | T-05-01, T-05-03 | Bahrain replay accepts known drivers and refuses invalid input without exposing a traceback | smoke + manual CLI | uv run f1si replay bahrain-2023 --driver ALO | New CLI coverage; local cache availability to confirm | pass |

---

## Wave 0 Requirements

- [ ] tests/strategy/test_longstaff.py — synthetic conditional-mean continuation recovery, pathwise stopping, same-checkpoint/common-draw branch behavior, rank-aware fallback, CVaR orientation and fractional boundary, risk endpoints, deterministic reasons, and StrategyPolicy conformance.
- [ ] tests/test_cli_replay.py — all-cutoff replay, selected-lap equality, driver selection, and expected refusal paths.
- [ ] tests/guards/consumers.py — register the replay command's as-of data consumer.
- [ ] Extend tests/conformance so the Longstaff-Schwartz policy runs through the shared StrategyPolicy suite.

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

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|------------------|
| Run a cached Bahrain 2023 replay for a real driver and inspect the complete recommendation table | RPL-02 | CI does not carry the user's local cache; the current Python runtime is blocked locally | In an authorized Python environment with the Bahrain cache present, run uv run f1si replay bahrain-2023 --driver ALO and uv run f1si replay bahrain-2023 --driver ALO --lap 20; confirm every cutoff is printed, lap 20 matches the full replay row, and each reason is one evidence-based sentence. |

**Observed local smoke:** Both default-size commands exited 0. Full replay printed ordered cutoffs 0 through 56 (57 rows: 41 available and 16 explicitly unavailable while the cutoff-local pace fit was unsupported). The selected lap-20 block exactly matched the full-replay block. After adding punctuation to unavailable reasons, a second real-cache full replay at `--n 12` confirmed all 57 reasons end as sentences and lap 20 still matches. The default-size lap-20 recommendation was `pit in 5 lap(s) (HARD)` (mean 7.927, spread 1.567, CVaR10 10.742, score 9.334); these are one-run observations, not calibration results.

---

## Validation Sign-Off

- [x] All tasks have automated verification or Wave 0 dependencies.
- [x] Sampling continuity has no three consecutive tasks without automated verification.
- [x] Wave 0 covers all missing test files and registrations.
- [x] No watch-mode flags.
- [x] Local Nyquist validation is complete; full local suite and focused post-fix tests pass.
- [ ] CI is green on Windows and Ubuntu.

**CI evidence:** Current local branch `agent-05-01` is not present on `origin`, so its commits have no GitHub Actions run. The last observed run on `main` (`fcec2f2`, run [43390811407](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43390811407)) passed both Ubuntu and Windows; that run predates Phase 5 and is not evidence for these commits. No push was made.

**Approval:** pending current-branch CI
