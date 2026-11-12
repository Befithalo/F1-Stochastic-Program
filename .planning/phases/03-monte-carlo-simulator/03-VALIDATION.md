---
phase: 3
slug: monte-carlo-simulator
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-12
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1 + hypothesis 6.170, mypy strict, ruff 0.17.1 |
| **Config file** | `pyproject.toml` (`[tool.pytest]`, default `-m "not network"`, `--strict-markers`) |
| **Quick run command** | `uv run python -m pytest tests/sim tests/regime tests/conformance -x -q` |
| **Full suite command** | `uv run ruff check . ; uv run ruff format --check . ; uv run python -m mypy ; uv run python -m pytest` |
| **Estimated runtime** | ~60–90 seconds (benchmark ~3 s, variance-reduction test ~5–10 s) |

---

## Sampling Rate

- **After every task commit:** Run the quick command for touched test directories, plus `uv run python -m mypy`
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite must be green locally and on CI (Ubuntu + Windows)
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

Task IDs are filled in by the planner; the requirement-to-test map below is the contract.

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| SIM-01 / SC1 | Long synthetic `RaceState` → finishing distribution for a driver; rows are permutations; shapes | integration | `uv run python -m pytest tests/sim/test_simulate_state.py -x` | ❌ W0 | ⬜ pending |
| SIM-01 / SC1 | Real Bahrain 2023: ALO distribution sums to 1 (opt-in) | integration (`network`) | `uv run python -m pytest -m network tests/real/test_simulate_bahrain.py` | ❌ W0 | ⬜ pending |
| SIM-01 | Simulator passes backend conformance suite (registered in `SIMULATORS`) | conformance | `uv run python -m pytest tests/conformance -x` | ✅ extend | ⬜ pending |
| SIM-01 | Pass probability monotone in pace gap; huge gap ≈ 1; equal pace small (D-08) | unit | `uv run python -m pytest tests/sim/test_overtaking.py` | ❌ W0 | ⬜ pending |
| SIM-01 | Jitted kernel equals `py_func`; hand-computed 2-car no-noise case | unit | `uv run python -m pytest tests/sim/test_kernel.py` | ❌ W0 | ⬜ pending |
| SIM-01 | Forced plan followed exactly; CRN: same seed + different forced plan leaves other cars' draws identical | unit / property | `uv run python -m pytest tests/sim/test_crn_and_plans.py` | ❌ W0 | ⬜ pending |
| SIM-01 | Follower catch-up lap, retired car, unfitted compound/driver borrow rule listed in diagnostics | unit | `uv run python -m pytest tests/sim/test_state_start.py` | ❌ W0 | ⬜ pending |
| SIM-02 / SC2 | 50,000 × 20 × 57 under 10 s, JIT warm-up excluded | benchmark | `uv run python -m pytest tests/sim/test_benchmark.py` | ❌ W0 | ⬜ pending |
| SIM-03 / SC4 | Lower variance (mean finish, total time, SC share) with Sobol+antithetic at equal N over R ≥ 100 seeds | statistical | `uv run python -m pytest tests/sim/test_variance_reduction.py` | ❌ W0 | ⬜ pending |
| SIM-03 | Draws: Sobol `rng=`, power-of-2 base, no UserWarning, antithetic pairs sum to 1, odd-N rule | unit | `uv run python -m pytest tests/sim/test_draws.py -W error` | ❌ W0 | ⬜ pending |
| D-15 / SC5 | Same seed → identical arrays; different seeds differ | unit | `uv run python -m pytest tests/sim/test_reproducibility.py` | ❌ W0 | ⬜ pending |
| REG-01 | SC-rate estimator recovers known rate within 90% interval; prior-only for first race; duration fallback 4 with < 5 events | unit | `uv run python -m pytest tests/regime/test_sc_rate.py` | ❌ W0 | ⬜ pending |
| REG-01 / D-06 | Simulated SC frequency matches input rate (binomial tolerance) | statistical | `uv run python -m pytest tests/sim/test_sc_frequency.py` | ❌ W0 | ⬜ pending |
| REG-01 | SC-rate function registered as scramble consumer; ignores the future | property | `uv run python -m pytest tests/guards` | ✅ extend | ⬜ pending |
| SC3 | Restart gaps equal spacing constant; stop under SC pays `pit_loss_s["sc"]`; order frozen on SC laps | unit | `uv run python -m pytest tests/sim/test_safety_car.py` | ❌ W0 | ⬜ pending |
| D-05 | Builder sets `regime {"sc": 1.0}` and `pit_loss_s["sc"]`; JSON round trip | unit | `uv run python -m pytest tests/test_state_builder.py tests/test_state.py` | ✅ update | ⬜ pending |
| D-06 | Synthetic generator SC spec emits status "4"; default fixtures byte-identical | unit | `uv run python -m pytest tests/test_synthetic.py` | ✅ extend | ⬜ pending |
| D-16 / D-17 | `f1si simulate` prints state, SC source, plan sources, P1..Pn, runtime; hindsight label; `--lap` refusal; writes PNG | integration | `uv run python -m pytest tests/test_cli_simulate.py` | ❌ W0 | ⬜ pending |
| D-16 | PNG data / figure / file-name slug safety | unit | `uv run python -m pytest tests/plots/test_simulate_plot.py` | ❌ W0 | ⬜ pending |
| D-20 / FND-04 | Explainer module tour, README needles, DEC format, `MIN_ENTRIES` bumped | unit | `uv run python -m pytest tests/test_docs.py tests/test_decisions_log.py` | ✅ update | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `uv add scipy numba`, `uv add --dev scipy-stubs`; `uv.lock` committed (CI uses `uv sync --locked`); import smoke check from `.venv`
- [ ] `tests/sim/`, `tests/regime/` packages with the files above
- [ ] Synthetic generator SC spec (defaulted fields; existing fixtures byte-identical) and a multi-race SC-history fixture with a known rate
- [ ] Update `tests/conformance/registry.py`, `tests/guards/consumers.py`, `tests/test_state_builder.py`, `tests/test_decisions_log.py::MIN_ENTRIES`, `tests/test_docs.py` README needles

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Finishing-distribution PNG reads clearly | SIM-01 / D-16 | Visual quality | Run `uv run f1si simulate bahrain-2023 --driver ALO`, open `reports/sim-bahrain-2023-ALO-lap0.png` |
| Benchmark under 10 s on CI runners | SIM-02 | Runner speed varies | Check the benchmark test timing in the GitHub Actions log (Ubuntu + Windows) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
