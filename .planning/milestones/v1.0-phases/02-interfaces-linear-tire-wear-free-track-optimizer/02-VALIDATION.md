---
phase: 2
slug: interfaces-linear-tire-wear-free-track-optimizer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-11
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1 + hypothesis 6.170, mypy strict, ruff 0.17.1 |
| **Config file** | `pyproject.toml` (`[tool.pytest]`, testpaths `tests`, default `-m "not network"`) |
| **Quick run command** | `uv run pytest tests/pace tests/strategy tests/conformance tests/test_state.py -x -q` |
| **Full suite command** | `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run pytest` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick command for touched test directories, plus `uv run mypy`
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite must be green locally and on CI (Ubuntu + Windows)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Task IDs are filled in by the planner; the requirement-to-test map below is the contract.

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| INT-01 | Protocols exist; mypy strict accepts conformers and rejects a wrong stub (unused `# type: ignore[arg-type]` trick) | static + unit | `uv run mypy` ; `uv run pytest tests/conformance/test_protocols.py` | ❌ W0 | ⬜ pending |
| INT-02 | One suite per Protocol over a registry; planted stubs (wrong shape, NaN, mutation, nondeterminism, illegal compound, missing method) each fail | unit / meta | `uv run pytest tests/conformance -x` | ❌ W0 | ⬜ pending |
| INT-02 | Linear pace fit passes pace suite; free-track optimizer passes policy suite; simulator test double passes backend suite | unit | `uv run pytest tests/conformance` | ❌ W0 | ⬜ pending |
| INT-03 | `RaceState` built at lap 0, mid-race and last lap (synthetic; real Bahrain opt-in); frozen; JSON round trip matches BUILD_PLAN keys; placeholders documented | unit + hypothesis | `uv run pytest tests/test_state.py` | ❌ W0 | ⬜ pending |
| INT-03 | Builder registered as scramble consumer; output equal under future scramble | property | `uv run pytest tests/guards` | ✅ extend | ⬜ pending |
| PAC-01 | Synthetic recovery: fuel and per-compound wear within 3 SE of truth on a 57-lap / 20-driver spec | unit | `uv run pytest tests/pace/test_linear_recovery.py` | ❌ W0 | ⬜ pending |
| PAC-01 | Non-identification reported by parameter name; compound under minimum laps → "not enough data" | unit | `uv run pytest tests/pace/test_identification.py` | ❌ W0 | ⬜ pending |
| PAC-01 | Shared clean-lap rule: plot fade classes unchanged; fit drop counts by reason; MAD trimming deterministic | unit | `uv run pytest tests/pace tests/plots` | ❌ W0 / ✅ | ⬜ pending |
| PAC-01 | Real Bahrain (opt-in, `network`/cache marker): SOFT/HARD ≈ 0.08–0.17 s/lap, MEDIUM not enough data, fuel negative, pit loss median 22–28 s | integration | `uv run pytest tests/real/test_wear_bahrain.py -m network` | ❌ W0 | ⬜ pending |
| PAC-01 | `f1si wear` prints table, writes PNG, actionable errors | integration | `uv run pytest tests/test_cli_wear_plan.py` | ❌ W0 | ⬜ pending |
| PAC-02 | Closed-form plan price equals slow lap-by-lap price (hypothesis) | property | `uv run pytest tests/strategy/test_free_track.py` | ❌ W0 | ⬜ pending |
| PAC-02 | Analytic case recovers known best plan; enumeration best ≤ all plans; every plan legal; edge cases (2 stops done, short remainder, wet refusal, ties) | unit / property | `uv run pytest tests/strategy/test_free_track.py` | ❌ W0 | ⬜ pending |
| PAC-02 | `f1si plan` prints best 1-stop, best 2-stop, top 5, "compared against" line, hindsight label, refusal at early laps | integration | `uv run pytest tests/test_cli_wear_plan.py` | ❌ W0 | ⬜ pending |
| UI-03 | `docs/explained/phase-02.md` complete; docs test generalised across explainers | unit | `uv run pytest tests/test_docs.py` | ✅ update | ⬜ pending |
| FND-04 | New DEC entries pass the log format test | unit | `uv run pytest tests/test_decisions_log.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conformance/` — suites, registry, planted stubs, meta-tests, simulator test double
- [ ] `tests/pace/` — recovery, identification, clean-lap tests
- [ ] `tests/strategy/test_free_track.py`
- [ ] `tests/test_state.py`
- [ ] `tests/test_cli_wear_plan.py`, `tests/real/test_wear_bahrain.py` (opt-in)
- [ ] Generalise `tests/test_docs.py` to multiple explainers; extend `tests/guards/consumers.py` registry
- [ ] Long synthetic spec fixture (57 laps, 20 drivers, no VSC) and an analytic optimizer case
- [ ] Verify research assumptions A1 (runtime_checkable scope) and A2 (mypy strict flags unused ignores)

No framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Wear PNG is readable (panels per compound, fitted line + band) | PAC-01 | Visual judgment | `uv run f1si wear bahrain-2023`, open `reports/wear-bahrain-2023.png` |
| Real Bahrain numbers on the owner's machine | PAC-01, PAC-02 | Needs the local cache, not in CI | `uv run f1si wear bahrain-2023` ; `uv run f1si plan bahrain-2023 --driver ALO` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
