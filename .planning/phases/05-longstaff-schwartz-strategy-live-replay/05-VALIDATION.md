---
phase: "05"
slug: "longstaff-schwartz-strategy-live-replay"
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| Estimated runtime | About 5m30s based on the previous full-suite run |

**Environment constraint:** The research pass found uv 0.13.5, but Windows Application Control blocked the Python child process with OS error 4551. Do not treat local test or replay execution as successful unless the runtime becomes available. Use CI or another authorized Python environment for automated validation.

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
| 05-01-01 | TBD | TBD | STR-01 | T-05-02 | Strategy receives only RaceState and preserves cutoff isolation | unit + conformance | uv run python -m pytest -q tests/strategy/test_longstaff.py tests/conformance/test_suites.py | New strategy tests; shared suite exists | pending |
| 05-01-02 | TBD | TBD | STR-02 | — | All actions use comparable scenarios and report the documented metrics | unit | uv run python -m pytest -q tests/strategy/test_longstaff.py -k cvar | New strategy tests | pending |
| 05-01-03 | TBD | TBD | STR-03 | T-05-01 | Risk input is bounded and finite; ranking endpoints are covered | unit | uv run python -m pytest -q tests/strategy/test_longstaff.py -k risk | New strategy tests | pending |
| 05-01-04 | TBD | TBD | STR-04 | T-05-02, T-05-03 | Reasons use cutoff-visible evidence and expected errors stay friendly | unit | uv run python -m pytest -q tests/strategy/test_longstaff.py -k reason | New strategy tests | pending |
| 05-01-05 | TBD | TBD | RPL-01 | T-05-02 | Every replay cutoff rebuilds its snapshot, fit, filter and state from that cutoff | integration + future-scramble | uv run python -m pytest -q tests/test_cli_replay.py tests/guards/test_future_scramble.py | New replay tests; guard exists | pending |
| 05-01-06 | TBD | TBD | RPL-02 | T-05-01, T-05-03 | Bahrain replay accepts known drivers and refuses invalid input without exposing a traceback | smoke + manual CLI | uv run f1si replay bahrain-2023 --driver ALO | New CLI coverage; local cache availability to confirm | pending |

---

## Wave 0 Requirements

- [ ] tests/strategy/test_longstaff.py — synthetic continuation-value recovery, fallback behavior, CVaR orientation and cutoff ties, risk endpoints, deterministic reasons.
- [ ] tests/test_cli_replay.py — all-cutoff replay, selected-lap equality, driver selection, and expected refusal paths.
- [ ] tests/guards/consumers.py — register the replay command's as-of data consumer.
- [ ] Extend tests/conformance so the Longstaff-Schwartz policy runs through the shared StrategyPolicy suite.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|------------------|
| Run a cached Bahrain 2023 replay for a real driver and inspect the complete recommendation table | RPL-02 | CI does not carry the user's local cache; the current Python runtime is blocked locally | In an authorized Python environment with the Bahrain cache present, run uv run f1si replay bahrain-2023 --driver ALO and uv run f1si replay bahrain-2023 --driver ALO --lap 20; confirm every cutoff is printed, lap 20 matches the full replay row, and each reason is one evidence-based sentence. |

---

## Validation Sign-Off

- [ ] All tasks have automated verification or Wave 0 dependencies.
- [ ] Sampling continuity has no three consecutive tasks without automated verification.
- [ ] Wave 0 covers all missing test files and registrations.
- [ ] No watch-mode flags.
- [ ] nyquist_compliant is true after all checks pass.
- [ ] CI is green on Windows and Ubuntu.

**Approval:** pending
