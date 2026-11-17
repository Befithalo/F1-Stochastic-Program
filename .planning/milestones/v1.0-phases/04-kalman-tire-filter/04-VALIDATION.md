---
phase: 4
slug: kalman-tire-filter
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-12
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + hypothesis, mypy strict, ruff 0.17.1 |
| **Config file** | `pyproject.toml` (`-m "not network"` by default, `--strict-markers`) |
| **Quick run command** | `uv run python -m pytest tests/pace tests/test_state.py tests/test_state_builder.py -x -q` |
| **Full suite command** | `uv run ruff check . ; uv run ruff format --check . ; uv run python -m mypy ; uv run python -m pytest` |
| **Estimated runtime** | about 90 seconds (the recovery tests are vectorised and run in about 1 s) |

---

## Sampling Rate

- **After every task commit:** run the quick command, the touched test file and `uv run python -m mypy`.
- **After every plan wave:** run the full suite command.
- **Before `/gsd:verify-work`:** the full suite must be green locally and on CI (Ubuntu and Windows).
- **Max feedback latency:** 90 seconds.

---

## Per-Task Verification Map

The planner fills in task IDs. The map from requirements to tests below is the contract.

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| PAC-03 | Joseph-form update equals closed-form Bayesian linear regression (mean and covariance) | unit | `uv run python -m pytest tests/pace/test_kalman_math.py -x` | ❌ W0 | ⬜ pending |
| PAC-03 | Updating lap by lap equals a batch update over a stint | property | `uv run python -m pytest tests/pace/test_kalman_incremental.py -x` | ❌ W0 | ⬜ pending |
| PAC-03 / SC1 | Posterior SD never increases on a measured lap and is unchanged on a skipped lap; `q > 0` widens the band | unit | `uv run python -m pytest tests/pace/test_kalman_narrowing.py -x` | ❌ W0 | ⬜ pending |
| PAC-03 | Laps that are not clean (lap 1, pit in/out, SC/VSC/red) do not update the filter; the gate starts at the 3rd used lap and never rejects twice in a row; reasons are counted | unit | `uv run python -m pytest tests/pace/test_kalman_gate.py -x` | ❌ W0 | ⬜ pending |
| PAC-04 / SC3 | Coverage of 95% intervals at each stint lap and pooled is within the binomial 99.9% band (N ≥ 1,000; truth drawn from the prior; fuel and noise known) | statistical | `uv run python -m pytest tests/pace/test_kalman_recovery.py::test_coverage -x` | ❌ W0 | ⬜ pending |
| PAC-04 | Coverage still holds when fuel comes from its prior | statistical | `uv run python -m pytest tests/pace/test_kalman_recovery.py::test_coverage_with_fuel_prior -x` | ❌ W0 | ⬜ pending |
| PAC-04 / SC2 (D-17) | The filter reaches Bayes-optimal accuracy: its posterior SD equals the closed form, its MC error matches the expected error within MC error, error at lap 8 is below error at lap 0, and the 10% figure is printed as a report | statistical | `uv run python -m pytest tests/pace/test_kalman_recovery.py -x` | ❌ W0 | ⬜ pending |
| PAC-04 / D-10 | Generator per-driver wear deviations: existing fixtures byte-identical when unset; the truth exposes the deviations | unit | `uv run python -m pytest tests/test_synthetic.py -x` | ✅ extend | ⬜ pending |
| SC1 | Real Bahrain 2023 ALO: the band narrows over the first laps of each stint | real data (opt-in) | `uv run python -m pytest -m network tests/real/test_wear_filter_bahrain.py` | ❌ W0 | ⬜ pending |
| SC4 / D-13 | The builder fills `wear_rate_s_per_lap`, `wear_sd` and `wear_source="filter"` from the filter; without the filter the output is identical to today; JSON round trip works; old JSON loads | unit | `uv run python -m pytest tests/test_state.py tests/test_state_builder.py -x` | ✅ extend | ⬜ pending |
| SC4 / D-14 | "fit" cars match a stored Phase 3 hash byte for byte; a higher filtered rate finishes worse; a larger SD widens the spread; CRN holds | unit | `uv run python -m pytest tests/sim/test_filter_cars.py -x` | ❌ W0 | ⬜ pending |
| D-14 | All Phase 3 simulator and conformance tests stay green unchanged | regression | `uv run python -m pytest tests/sim tests/conformance -x` | ✅ existing | ⬜ pending |
| D-09 | Future-scramble: the filter consumer ignores the future; the registry is complete | guard | `uv run python -m pytest tests/guards -x` | ✅ extend | ⬜ pending |
| D-15 | `f1si wear-filter` prints sources and per-lap rows, writes the PNG and gives friendly errors | CLI | `uv run python -m pytest tests/test_cli_wear_filter.py -x` | ❌ W0 | ⬜ pending |
| D-15 | PNG data, figure and file-name slug are safe | unit | `uv run python -m pytest tests/plots/test_wear_filter_plot.py -x` | ❌ W0 | ⬜ pending |
| D-16 | Explainer tour, README needles, DEC format and `MIN_ENTRIES` | docs | `uv run python -m pytest tests/test_docs.py tests/test_decisions_log.py -x` | ✅ update | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/pace/test_kalman_{math,incremental,narrowing,gate,recovery}.py`
- [ ] `tests/sim/test_filter_cars.py`, `tests/test_cli_wear_filter.py`, `tests/plots/test_wear_filter_plot.py`, `tests/real/test_wear_filter_bahrain.py`
- [ ] A stored Phase 3 reference hash (`finish_positions`, `total_time_s` for a fixed seed and state), captured BEFORE `numpy_backend.py` is touched
- [ ] Updates to `tests/guards/consumers.py`, `tests/test_decisions_log.py::MIN_ENTRIES` and the `tests/test_docs.py` needles
- [ ] No framework install is needed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The wear-filter PNG reads clearly | SC1 / D-15 | Visual check | Run `uv run f1si wear-filter bahrain-2023 --driver ALO` and open `reports/wear-filter-bahrain-2023-ALO.png` |
| The ALO interval with the filter at a mid-race lap (Phase 3 flag) | D-14 / specifics | Observation, not a gate | The verifier reports the width of ALO's 90% interval with and without the filter |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
