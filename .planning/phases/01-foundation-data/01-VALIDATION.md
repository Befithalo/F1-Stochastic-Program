---
phase: 1
slug: foundation-data
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-22
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `01-RESEARCH.md` §Validation Architecture. Data source is OpenF1 + Jolpica (CONTEXT D-08, revised).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x + hypothesis 6.170.x (+ pytest-cov, advisory) |
| **Config file** | `pyproject.toml` `[tool.pytest]` (Wave 0 creates it) |
| **Quick run command** | `uv run pytest -x -q` (synthetic only) |
| **Full suite command** | `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run pytest` |
| **Real-data command** | `uv run pytest -m network -v` (never in push CI) |
| **Estimated runtime** | ~30 seconds (quick), ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q` (pre-commit runs ruff automatically)
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite green, push CI green on ubuntu and windows, plus one local real-data run (`uv run f1si load`, `uv run f1si plot bahrain-2023`, `uv run pytest -m network`)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Task IDs are filled in by the planner. Each row maps a requirement to its automated proof.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 1 | FND-01 | — | N/A | smoke | `uv run pytest tests/test_smoke.py` + `uv run mypy` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | FND-02 | supply chain | `uv sync --locked` in CI | CI observation | GitHub Actions `CI` run status on push (ubuntu + windows) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | FND-03 | — | N/A | unit + guard | `uv run pytest tests/test_rng.py` + ruff `NPY002` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | FND-04 | — | N/A | doc test | `uv run pytest tests/test_decisions_log.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DAT-01 | SQL injection, input validation | parameter binding; response validation | integration | `uv run pytest tests/data/test_loader.py tests/data/test_db_roundtrip.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DAT-01 (real) | rate limits | backoff on 429 | integration (network) | `uv run pytest -m network tests/real/test_bahrain_2023.py` | ❌ | ⬜ pending |
| TBD | TBD | TBD | DAT-02 | file paths | output path from catalog slug only | unit + integration | `uv run pytest tests/plots/test_stint_plot.py tests/test_cli.py::test_plot_command` | ❌ | ⬜ pending |
| TBD | TBD | TBD | DAT-03 | look-ahead | snapshot ≤ cutoff; lap 0 pre-race only; RACE_END has no results; history earlier only; 2026 raises | unit | `uv run pytest tests/data/test_asof.py` | ❌ | ⬜ pending |
| TBD | TBD | TBD | DAT-04 | look-ahead | import scan empty; scramble-invariant; meta-test catches planted leak | guard | `uv run pytest tests/guards` | ❌ | ⬜ pending |
| TBD | TBD | TBD | DAT-05 | — | N/A | unit | `uv run pytest tests/test_eras.py tests/test_cli.py::test_races_lists_era` | ❌ | ⬜ pending |
| TBD | TBD | TBD | UI-03 | — | N/A | doc test | `uv run pytest tests/test_docs.py` | ❌ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml`, `uv.lock`, `.python-version`, `src/f1si/__init__.py` — scaffold (FND-01)
- [ ] `tests/conftest.py` — synthetic dataset fixture (3 in-sample races + 1 locked 2026 race), session/module scoped
- [ ] `src/f1si/synthetic/` generator (needed before any data test)
- [ ] `tests/guards/` import scan, scramble harness, consumer registry + `tests/fixtures/leaky_consumer.py`
- [ ] `.github/workflows/ci.yml` (FND-02), `.pre-commit-config.yaml` (D-13)
- [ ] Framework install: `uv sync` (after uv and Python 3.12 are installed)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full 2023–2026 load from the real APIs | DAT-01 / SC2 | ~20–25 min of rate-limited network calls; not suitable for CI | `uv run f1si load`; then `uv run f1si races` lists ~87 races with eras |
| Bahrain 2023 plot looks right | DAT-02 / SC3 | Visual judgment | `uv run f1si plot bahrain-2023`; open `reports/bahrain-2023.png`; 20 panels, compound colors, faded slow laps |
| CI green on GitHub | FND-02 / SC1 | Needs the user's push to the remote | Push `main`; check both OS jobs pass in the Actions tab |
| Dependency list sanity check | supply chain | slopcheck unavailable (no Python at research time) | User/executor confirms each package name in `pyproject.toml` is the well-known project |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
