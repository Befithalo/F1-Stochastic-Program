---
phase: "06"
slug: "mvp-backtest-streamlit-view-readme"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-13"
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x and Hypothesis |
| **Config file** | `pyproject.toml`; shared fixtures in `tests/conftest.py` |
| **Quick run command** | `uv run python -m pytest tests/backtest -q` |
| **Full suite command** | `uv run python -m pytest` |
| **Estimated runtime** | Focused backtest checks under 2 minutes; full suite and cross-platform CI may take 30 minutes |

---

## Sampling Rate

- **After every task commit:** Run the focused tests listed by that task.
- **After every plan wave:** Run `uv run python -m pytest` and the repository Ruff, format, and strict mypy gates.
- **Before `$gsd-verify-work`:** Full suite and exact-head Ubuntu/Windows CI must be green.
- **Max feedback latency:** 120 seconds for focused backtest tests.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|--------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | BKT-01 | T-06-01 | Every prediction is built from its cutoff snapshot and earlier history; 2026 stays locked | integration/property | `uv run python -m pytest tests/backtest/test_walk_forward.py tests/guards/test_future_scramble.py -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | BKT-02 | T-06-02 | Final results are opened only by `f1si.backtest.scoring`; baseline uses earlier races only | unit/integration | `uv run python -m pytest tests/backtest/test_metrics.py -q` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | BKT-04 | T-06-03 | Each team-stop comparison uses a recommendation that predates the observed event | unit/integration | `uv run python -m pytest tests/backtest/test_strategy.py -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | UI-01 | T-06-04 | Catalog-backed controls call the shared cutoff-safe builder and label fallback/proxy output | app/service smoke | `uv run python -m pytest tests/app -q` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | UI-02 | T-06-05 | README reports only measured metrics, discloses hidden variables, and credits data providers | docs regression | `uv run python -m pytest tests/test_docs.py -q` | ✅ existing | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/backtest/test_walk_forward.py` — frozen race list, cutoff ordering, earlier-history boundary, future-scramble equality, and 2026 refusal.
- [ ] `tests/backtest/test_metrics.py` — Brier score, past-only grid baseline, discrete interval endpoints, equal-race aggregation, and deterministic race-cluster bootstrap.
- [ ] `tests/backtest/test_strategy.py` — event-to-pre-event recommendation matching, stop-timing error, and seeded race-cluster intervals.
- [ ] `tests/app/` — required page controls/displays and fallback, tire, and safety-car labels without requiring a live browser for metric logic.
- [ ] `tests/guards/consumers.py` — register each new public as-of consumer; confirm `tests/guards/import_scan.py` limits `f1si.data.results` to `f1si.backtest.scoring`.
- [ ] `pyproject.toml` and `uv.lock` — add the roadmap-required Streamlit dependency after the package identity review; keep the resolved dependency lock committed for `uv sync --locked` CI.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The one-page dashboard is readable and its controls update the selected race, driver, cutoff, and risk consistently | UI-01 | Automated app tests verify wiring and defaults but do not replace visual inspection of the rendered page | Run `uv run python -m streamlit run src/f1si/app.py`; confirm the default Bahrain 2023 / ALO view, move the lap and risk controls, and confirm all required panels update without exposing final results. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing test references.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 120s for focused tests.
- [ ] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
