---
phase: 1
slug: foundation-data
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-10-22
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `01-RESEARCH.md` §Validation Architecture. Data source is OpenF1 + Jolpica (CONTEXT D-08, revised).
> Task IDs filled by the planner on 2026-10-22 (plans 01-01..01-09, see SKELETON.md).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x + hypothesis 6.170.x (+ pytest-cov, advisory) |
| **Config file** | `pyproject.toml` `[tool.pytest]` (created by 01-01-T1) |
| **Quick run command** | `uv run pytest -x -q` (synthetic only) |
| **Full suite command** | `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run pytest` |
| **Real-data command** | `uv run pytest -m network -v` (never in push CI) |
| **Estimated runtime** | ~30 seconds (quick), ~90 seconds (full) |

Executor shell note: prefix commands with `export PATH="$HOME/.local/bin:$PATH";` (uv is installed in 01-01-T3, after the agent shell started).

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q` (pre-commit runs ruff automatically)
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite green, push CI green on ubuntu and windows, plus one local real-data run (`uv run f1si load`, `uv run f1si plot bahrain-2023`, `uv run pytest -m network`)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Task ID format: `PP-NN-Tk` = plan 01-NN, task k.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-T1, 01-02-T1 | 01-01, 01-02 | 1, 2 | FND-01 | T-01-SC | locked deps | smoke | `uv run pytest tests/test_smoke.py` + `uv run mypy` | ❌ W0 (01-01-T1) | ⬜ pending |
| 01-01-T1, 01-02-T3, 01-09-T3 | 01-01, 01-02, 01-09 | 1, 2, 6 | FND-02 | T-01-SC, T-01-02, T-01-46 | `uv sync --locked` in CI; `contents: read` | CI observation | GitHub Actions `CI` run status for HEAD via `api.github.com/.../actions/runs?head_sha=` (ubuntu + windows, canary step) | ❌ W0 (01-01-T1) | ⬜ pending |
| 01-02-T1, 01-02-T2, 01-04-T1 | 01-02, 01-04 | 2, 3 | FND-03 | T-01-18 | no global/unseeded RNG | unit + guard | `uv run pytest tests/test_rng.py tests/guards/test_import_ban.py` + ruff `NPY002` | ❌ | ⬜ pending |
| 01-04-T2 (+01-07-T2, 01-08-T2, 01-09-T2) | 01-04 | 3 | FND-04 | — | N/A | doc test | `uv run pytest tests/test_decisions_log.py` | ❌ | ⬜ pending |
| 01-02-T2, 01-03-T1, 01-03-T2, 01-05-T1, 01-05-T2, 01-07-T1 | 01-02, 01-03, 01-05, 01-07 | 2, 3, 4 | DAT-01 | T-01-06, T-01-07, T-01-11, T-01-21, T-01-32 | parameter binding; transactional write; response + schema validation | integration | `uv run pytest tests/data/test_loader.py tests/data/test_db_roundtrip.py tests/data/test_derive.py tests/data/test_http.py tests/data/test_jolpica.py tests/data/test_openf1.py` | ❌ | ⬜ pending |
| 01-07-T2, 01-09-T1 | 01-07, 01-09 | 4, 6 | DAT-01 (real) | T-01-23, T-01-33 | pacing + backoff on 429 | integration (network) | `uv run pytest -m network tests/real/test_bahrain_2023.py` (+ smoke `uv run f1si load --seasons 2023 --only bahrain-2023`) | ❌ | ⬜ pending |
| 01-08-T1, 01-08-T2 | 01-08 | 5 | DAT-02 | T-01-37, T-01-38 | output path from catalog slug + validated codes | unit + integration | `uv run pytest tests/plots/test_stint_plot.py tests/test_cli.py::test_plot_command` | ❌ | ⬜ pending |
| 01-06-T1 | 01-06 | 4 | DAT-03 | T-01-27, T-01-28, T-01-30 | snapshot ≤ cutoff; lap 0 pre-race only; RACE_END has no results; history earlier only; 2026 raises | unit | `uv run pytest tests/data/test_asof.py tests/data/test_doors.py` | ❌ | ⬜ pending |
| 01-04-T1, 01-04-T2, 01-06-T2, 01-08-T2 | 01-04, 01-06, 01-08 | 3, 4, 5 | DAT-04 | T-01-16, T-01-17, T-01-27, T-01-31, T-01-39 | import scan empty; scramble-invariant; meta-test catches planted leaks; CI canary | guard | `uv run pytest tests/guards` | ❌ | ⬜ pending |
| 01-02-T1, 01-02-T2, 01-06-T1 | 01-02, 01-06 | 2, 4 | DAT-05 | T-01-29 | 2026 locked behind its own door | unit | `uv run pytest tests/test_eras.py tests/test_cli.py::test_races_lists_era tests/data/test_asof.py` | ❌ | ⬜ pending |
| 01-09-T2 | 01-09 | 6 | UI-03 | — | N/A | doc test | `uv run pytest tests/test_docs.py` | ❌ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Created inside the plans (test-first tasks), not as a separate wave:

- [ ] `pyproject.toml`, `.python-version`, `src/f1si/__init__.py` — 01-01-T1; `uv.lock` — 01-02-T1 (FND-01)
- [ ] `tests/conftest.py` — synthetic dataset fixtures (3 in-sample races + 1 locked 2026 race), session-scoped — 01-02-T2
- [ ] `src/f1si/synthetic/` generator — 01-02-T2 (laps), 01-03-T1 (all tables)
- [ ] `tests/guards/import_scan.py` + `tests/fixtures/leaky_consumer.py` — 01-04-T1; `tests/guards/{scramble,consumers}.py` + `tests/fixtures/leaky_through_accessor.py` — 01-06-T2
- [ ] `.github/workflows/ci.yml` (FND-02), `.pre-commit-config.yaml` (D-13) — 01-01-T1; canary step — 01-04-T2
- [ ] Framework install: `uv sync` — 01-02-T1 (after uv and Python 3.12 are installed in 01-01-T3)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full 2023–2026 load from the real APIs | DAT-01 / SC2 | ~20–30 min of rate-limited network calls; not suitable for CI | Run by the executor in 01-09-T1 (background); owner check: `uv run f1si races` lists ~87 races with eras |
| Bahrain 2023 plot looks right | DAT-02 / SC3 | Visual judgment | 01-08-T2 human-check: `uv run f1si plot bahrain-2023`; open `reports/bahrain-2023.png`; 20 panels, compound colors, faded slow laps |
| CI green on GitHub | FND-02 / SC1 | Needs the owner's first push (GitHub sign-in) | 01-02-T3 checkpoint; final state verified via the Actions API in 01-09-T3 |
| Dependency list sanity check | supply chain | slopcheck unavailable (no Python at research time) | 01-01-T2 blocking human checkpoint: owner confirms each package name in `pyproject.toml` on pypi.org |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (created test-first inside the owning tasks)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (quick run; scramble property test capped at 20 examples)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending execution
