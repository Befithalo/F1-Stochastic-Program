---
phase: "06"
slug: "mvp-backtest-streamlit-view-readme"
status: approved
nyquist_compliant: true
wave_0_complete: true
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
| 06-00-01 | 00 | 0 | BKT-01/BKT-02/BKT-04 | T-06-10 | Backtest test contracts cover cache refusal, cutoff order, prediction freeze before scoring, metric integrity, event alignment, and proxy boundaries | test-contract syntax | `uv run python -c "import ast,pathlib; ps=[pathlib.Path(p) for p in ['tests/backtest/test_walk_forward.py','tests/backtest/test_metrics.py','tests/backtest/test_strategy.py','tests/backtest/test_wear_diagnostic.py']]; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in ps]; assert all(p.is_file() for p in ps)"` | yes | passed |
| 06-00-02 | 00 | 0 | UI-01 | T-06-12 | App test contract covers approved controls, cutoff-safe displays, proxy/fallback labels, and all empty/loading/error/partial/layout states | test-contract syntax | `uv run python -c "import ast,pathlib; p=pathlib.Path('tests/app/test_app.py'); ast.parse(p.read_text(encoding='utf-8'), filename=str(p)); assert p.is_file()"` | yes | passed |
| 06-01-01 | 01 | 1 | BKT-01 | T-06-01 | Ten fixed race IDs and full-cache preflight precede a prediction-only tracer row | integration | `uv run python -m pytest tests/backtest/test_walk_forward.py -q` | yes | passed (7 tests) |
| 06-01-02 | 01 | 1 | BKT-01 | T-06-02 | Every prediction uses its cutoff snapshot and earlier history; all ten races freeze before results access/scoring; future-scramble output is invariant; 2026 stays locked | integration/property | `uv run python -m pytest tests/guards tests/test_decisions_log.py -x -q`<br>`uv run python -m pytest tests/backtest/test_walk_forward.py tests/guards/test_future_scramble.py -x -q` | yes | passed (224 + 58 tests) |
| 06-02-01 | 02 | 2 | BKT-02 | T-06-03 | Brier masks, neutral past-only baseline, interval endpoints, equal-race means, and paired bootstrap semantics are exact | unit | `uv run python -m pytest tests/backtest/test_metrics.py -q` | yes | passed (7 tests) |
| 06-02-02 | 02 | 2 | BKT-02 | T-06-04 | Complete eligible ten-race/cutoff set carries compact selected-draw probabilities and P05/P95 endpoints before results access or scoring; report has required metrics and denominators | integration | `uv run python -m pytest tests/backtest/test_metrics.py tests/backtest/test_walk_forward.py tests/strategy/test_longstaff.py -x -q` | yes | pending (scope amendment awaits plan checker) |
| 06-03-01 | 03 | 3 | BKT-04 | T-06-05 | Every actual stop matches once to the latest strictly earlier recommendation; intervals resample races | integration | `uv run python -m pytest tests/backtest/test_strategy.py -q` | yes | pending |
| 06-03-02 | 03 | 3 | BKT-04 | T-06-06 | Wear coverage/bias/own-laps evidence uses a labeled leave-current-stint-out proxy and does not tune the filter | unit/integration | `uv run python -m pytest tests/backtest/test_wear_diagnostic.py tests/backtest/test_strategy.py -q` | yes | pending |
| 06-04-01 | 04 | 4 | UI-01 | T-06-SC | Reviewed dependency is locked; catalog controls/defaults call the shared builder and the page shows the measured ten-race summary | app/service smoke | `uv run python -m pytest tests/app/test_app.py -q`<br>`uv lock --check`<br>`rg -q 'uv sync --locked' .github/workflows/ci.yml` | yes | pending |
| 06-04-02 | 04 | 4 | UI-01 | T-06-07 | Eight UI truths, proxy/fallback labels, and stale-output suppression hold across states/layouts | app/state | `uv run python -m pytest tests/app/test_app.py -q` | yes | pending |
| 06-05-01 | 05 | 5 | UI-02 | T-06-08 | README/explainer claims match the measured report and preserve assumptions, denominators, and provider licensing | docs regression | `uv run python -m pytest tests/test_docs.py -x -q` | existing | pending |
| 06-05-02 | 05 | 5 | UI-02 | T-06-09 | Phase 6 method decisions and publication claims are guarded by documentation tests | docs regression | `uv run python -m pytest tests/test_docs.py tests/test_decisions_log.py -x -q` | existing | pending |

---

## Wave 0 Requirements

- [ ] `tests/backtest/test_walk_forward.py` — frozen race list, cutoff ordering, earlier-history boundary, prediction-only tracer, future-scramble equality, and 2026 refusal.
- [ ] `tests/backtest/test_metrics.py` — Brier score, past-only grid baseline, discrete interval endpoints, equal-race aggregation, deterministic race-cluster bootstrap, and prediction-freeze-before-scoring event order.
- [ ] `tests/backtest/test_strategy.py` — event-to-pre-event recommendation matching, stop-timing error, and seeded race-cluster intervals.
- [ ] `tests/backtest/test_wear_diagnostic.py` — leave-current-stint-out proxy, wear-band coverage denominator, early-fit bias, and own-laps evidence.
- [ ] `tests/app/test_app.py` — required page controls/displays, cutoff-safe wiring, proxy/fallback labels, and all approved empty/loading/error/partial/layout states.

Plan 06-00 creates all five missing test files. `tests/guards/consumers.py` is updated in Plan 06-01, and the approved Streamlit dependency/lock work is in Plan 06-04.

### Wave 0 execution record

- Both exact AST checks passed. Repository Ruff check and format check passed.
- Full pytest collection is temporarily blocked by the missing `f1si.backtest` modules assigned to Plans 06-01 through 06-03. Mypy likewise reports only those not-yet-created backtest modules. Re-run the full suite and mypy after their implementation waves.

### Wave 1 execution record

- Walk-forward tests passed (7); guards plus the decision log passed (224); the final walk-forward and future-scramble run passed (58). Ruff check and format check passed.
- Full pytest collection still cannot start because the scoring, team strategy, and wear-proxy modules are scheduled for Waves 2 and 3. Mypy reports only those missing future-wave modules; rerun both gates as those modules land.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The one-page dashboard shows the fixed-sample metrics and is readable as controls update the selected race, driver, cutoff, and risk | UI-01 | Automated app tests verify wiring and defaults but do not replace visual inspection of the rendered page | Run `uv run python -m streamlit run src/f1si/app.py`; confirm the measured ten-race summary, default Bahrain 2023 / ALO view, move the lap and risk controls, and confirm all required panels update without exposing final results. |

---

## Validation Sign-Off

- [x] Every task has a runnable `<automated>` verify or an ordered Wave 0 dependency that creates its test file first.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all five missing test references with parse checks; behavior runs with the implementation tasks.
- [x] Wave 0 execution has created all five test files and both AST checks passed (`wave_0_complete: true`).
- [x] No watch-mode flags.
- [x] Feedback latency < 120s for focused tests.
- [x] `nyquist_compliant: true` set in frontmatter because all verification paths are runnable or ordered behind Wave 0 creation.

**Approval:** approved 2026-11-14
