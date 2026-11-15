---
phase: "06"
slug: "mvp-backtest-streamlit-view-readme"
status: draft
nyquist_compliant: false
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
| 06-02-01 | 02 | 2 | BKT-02 | T-06-03 | Brier masks, neutral past-only baseline, interval endpoints, equal-race means, and paired bootstrap semantics are exact | unit | `uv run python -m pytest tests/backtest/test_metrics.py -q` | yes | passed (7 metrics tests at 87610f9; scorer API RED contract was added later by bf07561 for Plan 06-04) |
| 06-03-01 | 03 | 3 | BKT-02 | T-06-13 | Every strategy option carries same-draw podium/top-10 probabilities and inclusive inverted-CDF P05/P95 summaries before prediction freeze; no raw draws or results access | unit/integration | `uv run python -m pytest tests/strategy/test_longstaff.py -q` | yes | passed (17 tests) |
| 06-04-01 | 04 | 4 | BKT-02 | T-06-04 | `test_preflight_requires_all_ten_races_before_scoring`, `test_incomplete_trace_stops_before_results_open_or_score`, and `test_predictions_freeze_before_first_results_open_and_score` prove all-ten preflight, fail-closed trace validation, and full eligible prediction freeze before first ResultsAccessor access or scoring | integration | `uv run python -m pytest tests/backtest/test_metrics.py -x -q` | yes (Wave 0-created; Plan 06-04 adds cases) | passed (included in 48-test focused run) |
| 06-04-02 | 04 | 4 | BKT-02 | T-06-14 | `test_backtest_report_incomplete_cache_writes_no_completed_report` proves nonzero exit and no new or overwritten completed report; JSON preserves the ten IDs, paired Brier/interval metrics, denominators, seeds and conventions | integration/CLI | `uv run python -m pytest tests/backtest/test_metrics.py tests/backtest/test_walk_forward.py tests/test_cli.py -x -q` | yes | passed (48 focused tests) |
| 06-05-01 | 05 | 5 | BKT-04 | T-06-05 | Every actual stop matches once to the latest strictly earlier recommendation; intervals resample races | integration | `uv run python -m pytest tests/backtest/test_strategy.py -q` | yes | green (7 passed) |
| 06-05-02 | 05 | 5 | BKT-04 | T-06-06 | Wear coverage/bias/own-laps evidence uses a labeled leave-current-stint-out proxy and does not tune the filter | unit/integration | `uv run python -m pytest tests/backtest/test_wear_diagnostic.py tests/backtest/test_strategy.py -q` | yes | green (11 passed) |
| 06-06-01 | 06 | 6 | UI-01 | T-06-SC | Reviewed dependency is locked; catalog controls/defaults call the shared builder and the page shows the measured ten-race summary | app/service smoke | `uv run python -m pytest tests/app/test_app.py -q`<br>`uv lock --check`<br>`rg -q 'uv sync --locked' .github/workflows/ci.yml` | yes | green (23 passed; lock and CI checks passed) |
| 06-06-02 | 06 | 6 | UI-01 | T-06-07 | Eight UI truths, proxy/fallback labels, and stale-output suppression hold across states/layouts | app/state | `uv run python -m pytest tests/app/test_app.py -q` | yes | green (23 passed) |
| 06-07-01 | 07 | 7 | UI-02 | T-06-08 | README/explainer claims match the measured report and preserve assumptions, denominators, and provider licensing | docs regression | `uv run python -m pytest tests/test_docs.py -x -q` | existing | green (22 passed) |
| 06-07-02 | 07 | 7 | UI-02 | T-06-09 | Phase 6 method decisions and publication claims are guarded by documentation tests | docs regression | `uv run python -m pytest tests/test_docs.py tests/test_decisions_log.py -x -q` | existing | green (52 passed) |
| 06-08-01 | 08 | 8 | UI-01 | — | Selected-cutoff finish draws drive a neutral distribution and labeled finish-mean summary; full caption and chart typography follow the contract | app/plot regression | `uv run python -m pytest tests/app/test_app.py tests/plots/test_simulate_plot.py -q` | yes | pass (35 focused tests; included in full suite) |
| 06-08-02 | 08 | 8 | UI-01 | T-06-15 | The real first-ranked row retains its Basis; replay errors use fixed recovery copy; risk endpoints/value and the safety-car marker meet the contract | app/state regression | `uv run python -m pytest tests/app/test_app.py -q` | yes | pass (30 app tests; included in full suite) |
| 06-08-03 | 08 | 8 | UI-01 | — | Rendered desktop/narrow geometry and changed-selection states are inspected in a live browser | manual UI | Browser at 1440×900 and 390×844, per instructions below | yes | pending: no browser surface available in this executor session |

---

## Wave 0 Requirements

- [x] `tests/backtest/test_walk_forward.py` — frozen race list, cutoff ordering, earlier-history boundary, prediction-only tracer, future-scramble equality, and 2026 refusal.
- [x] `tests/backtest/test_metrics.py` — Brier score, past-only grid baseline, discrete interval endpoints, equal-race aggregation, deterministic race-cluster bootstrap, and prediction-freeze-before-scoring event order.
- [x] `tests/backtest/test_strategy.py` — event-to-pre-event recommendation matching, stop-timing error, and seeded race-cluster intervals.
- [x] `tests/backtest/test_wear_diagnostic.py` — leave-current-stint-out proxy, wear-band coverage denominator, early-fit bias, and own-laps evidence.
- [x] `tests/app/test_app.py` — required page controls/displays, cutoff-safe wiring, proxy/fallback labels, and all approved empty/loading/error/partial/layout states.

Plan 06-00 creates the five initial test files. `tests/guards/consumers.py` is updated in Plan 06-01. Plan 06-04 adds its scorer cases to the existing Wave 0-created `tests/backtest/test_metrics.py` and CLI report cases to the existing `tests/test_cli.py`; the approved Streamlit dependency/lock work is in Plan 06-06.

### Wave 0 execution record

- Both exact AST checks passed. Repository Ruff check and format check passed.
- Full pytest collection is temporarily blocked by the missing scoring, team-strategy, and wear-diagnostic modules assigned to Plans 06-04 and 06-05; the Streamlit dependency and app are assigned to Plan 06-06. Mypy likewise reports not-yet-created backtest modules. Re-run the full suite and mypy after their implementation waves.

### Wave 1 execution record

- Walk-forward tests passed (7); guards plus the decision log passed (224); the final walk-forward and future-scramble run passed (58). Ruff check and format check passed.
- Full pytest collection still cannot start because the scorer, team strategy, and wear-proxy modules are scheduled for Waves 4 and 5. Mypy reports only those missing future-wave modules; rerun both gates as those modules land.

### Wave 3 execution record

- The same-draw distribution summary tests passed (17). `python -m compileall -q src` passed.
- Full pytest collection remains blocked because `f1si.backtest.strategy` is assigned to Plan 06-05; rerun the full suite after that module lands.
- Post-wave schema-drift and UI-safety gates passed. The codebase-drift check was skipped because the repository has no `STRUCTURE.md`.

### Wave 4 execution record

- The default fixed-sample report completed successfully in 1h18m49s using four workers and published all ten locked races, 10,942 Brier observations, 9,602 classified finishers, and 8,004 covered intervals with the declared seeds, simulation count, and bootstrap convention. Serial and four-worker output matched exactly in the representative 80-row, 1,000-simulation benchmark (170.036s vs 83.739s; 2.03x faster).
- The focused Plan 06-04 suite passed (48 tests). Source compilation, Ruff check, Ruff format check, and `uv run mypy src` passed.
- Full pytest collection remains blocked by `f1si.backtest.strategy`, scheduled for Plan 06-05. Full strict mypy reports only the not-yet-created `f1si.backtest.strategy` and `f1si.backtest.wear_diagnostic` modules, also scheduled for Plan 06-05; rerun both gates after that plan.
- Schema-drift passed; UI safety gate found no UI files; codebase-drift was skipped because the repository has no `STRUCTURE.md`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The one-page dashboard shows the fixed-sample metrics and is readable as controls update the selected race, driver, cutoff, and risk | UI-01 | Automated app tests verify wiring and defaults but do not replace visual inspection of the rendered page | Run `uv run python -m streamlit run src/f1si/app.py`; confirm the measured ten-race summary, default Bahrain 2023 / ALO view, move the lap and risk controls, and confirm all required panels update without exposing final results. |
| The UI review fixes render at desktop and narrow widths without clipping, and changed controls map to the shown cutoff | UI-01 | Streamlit's real widget dimensions and responsive browser layout cannot be established by AppTest or source assertions alone | Open the running Streamlit page in a browser at 1440×900 and 390×844. Submit the default selection, then change race, driver, cutoff, and risk to another valid selection. At both widths inspect the populated layout, table scrolling, TOP marker and Basis, risk endpoints/value, neutral chart bars, finish-summary label, chart caption, wrapping, and clipping. Do not modify the real cache to manufacture empty/loading/error states; AppTest and source/helper assertions for those contracts are recorded separately. Record viewport-specific observations or screenshots. |

---

## Validation Sign-Off

- [x] Every task has a runnable `<automated>` verify or an ordered Wave 0 dependency that creates its test file first.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all five missing test references with parse checks; behavior runs with the implementation tasks.
- [x] Wave 0 execution has created all five test files and both AST checks passed (`wave_0_complete: true`).
- [x] No watch-mode flags.
- [x] Feedback latency < 120s for focused tests.
- [ ] Set `nyquist_compliant: true` after the Phase 6 UI follow-up tests and manual viewport check are resolved.

**Validation:** prior Phase 6 task map validated 2026-11-14; UI-review follow-up automated checks pass, while live viewport inspection remains pending.

## Validation Audit 2026-11-14

| Metric | Count |
|---|---|
| Gaps found | 6 |
| Resolved | 6 |
| Escalated | 0 |

## UI Review Follow-up (2026-11-14)

- Focused automated command: `uv run python -m pytest tests/app/test_app.py tests/plots/test_simulate_plot.py -q`.
- Focused command result: 36 passed. Full project suite: 1,095 passed, 25 deselected. `uv run ruff check .`, `uv run ruff format --check .`, and `uv run python -m mypy` passed on the follow-up changes.
- Exact-head GitHub Actions for Ubuntu and Windows has not run; it must run on the final pushed follow-up head.
- The local Streamlit server is running at `http://127.0.0.1:8501` and its health endpoint returned HTTP 200. The computer-use surface listed no browser or app, so manual-only acceptance remains pending. Source assertions and AppTest are not viewport evidence. No screenshot or geometry claim is recorded.
- `nyquist_compliant` remains `false`; Phase 6 UI validation cannot be signed off until the live browser inspection and exact-head CI are complete.

## D-11 Visual Redesign Validation (2026-11-14)

- Implementation and exact-head CI target: `41c0ce6f1ab8767c0e8c57e240ab7954300edf5d` (pushed to the Phase 06 branch).
- Focused app/plot suite on that SHA: 38 passed. Full project suite: 1,097 passed, 25 deselected on parent `7d4a59d`; the only subsequent source-control change before `41c0ce6` is a behavior-neutral test typing correction. Focused tests and strict mypy were rerun after that correction.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run python -m mypy`, and `uv lock --check` all pass at `41c0ce6`.
- Exact-head `ci.yml` run: [43674055392](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43674055392), head SHA `41c0ce6f1ab8767c0e8c57e240ab7954300edf5d`. Both `checks (ubuntu-latest)` and `checks (windows-latest)` completed successfully, including the full pytest step. The `gh` CLI was unavailable, so the workflow run and job conclusions were verified through GitHub's read-only Actions REST API.
- Streamlit is serving from the checked-out implementation at `http://127.0.0.1:8501`; `/_stcore/health` returned HTTP 200.
- Human visual acceptance at 1440×900 and 390×844 is pending. No screenshot or rendered-geometry claim is recorded. Browser review is limited to the populated layout and valid-selection transitions; empty-cache behavior is AppTest-rendered, while loading/error/partial contracts have source/helper assertions.
- `nyquist_compliant` remains `false` until exact-head CI and explicit owner approval of both rendered viewport sizes are evidenced.

## Phase 06 Final UI Gates (2026-11-15)

**Implementation SHA:** `9e39878b330faba04d6ca17efffc20e900e7d8e1` (`fix(06-08): align test fakes with chart interfaces`). This exact implementation head was pushed to `gsd/phase-06-mvp-backtest-streamlit-view-readme` before CI.

### Local gates

| Command | Result |
|---|---|
| `uv run python -m pytest tests/app/test_app.py tests/plots/test_simulate_plot.py tests/strategy/test_longstaff.py tests/sim/test_simulate_state.py -q` | **73 passed** in 7.67s |
| `uv run python -m pytest` | **1,106 passed, 25 deselected** in 577.86s |
| `uv run ruff check .` | Passed: all checks passed |
| `uv run ruff format --check .` | Passed: 167 files already formatted |
| `uv run python -m mypy` | Passed: no issues in 158 source files |
| `uv lock --check` | Passed: 81 packages resolved, lock is current |

### Exact-head Ubuntu and Windows CI

- `ci.yml` run [43691265704](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43691265704) completed successfully for the exact implementation SHA above (`head_sha` verified through GitHub Actions REST API; `gh` CLI unavailable).
- Ubuntu job [132742235359](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43691265704/job/132742235359): **success**.
- Windows job [132742235046](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43691265704/job/132742235046): **success**.

### Rendered viewport audit and fixes

The actual Streamlit page was rendered through local Edge/CDP at both sizes. The local cache has 70 eligible races, all with `scheduled_laps=None`, so a chart-bearing replay could not be submitted. The rendered schedule-unavailable state was inspected; chart geometry and quantile coordinates are covered by automated tests.

| Viewport | Final observation |
|---|---|
| 1440x900 | Report content and unavailable-state copy fit. The pooled-coverage denominator wraps fully; visible state colors are neutral, and copy uses sentence case. |
| 390x844 | Coverage labels and values wrap, vertical scrolling works, and `documentElement.scrollWidth` is 390 with no horizontal overflow. The scorecard stacks and unavailable-state copy remains readable. |

**Color, tabular-number, and copy violations found and corrected:**

- **Color:** Streamlit's default blue information panel was replaced with an escaped neutral pitwall note.
- **Color:** brown confidence-interval delta chips were replaced with neutral fog captions.
- **Tabular numbers and wrapping:** the desktop coverage denominator and mobile coverage label clipped; metric labels and values now wrap, and tabular numerals cover metrics, labels, captions, and risk endpoints.
- **Copy:** the range caption's en dash was replaced with the sentence-case wording `10th to 90th`.

No remaining color, tabular-number, or copy violation was visible in either rendered state. No overall-best lap appears on the page; if added later, it must use neutral fog and the `Best` label. The live app remains on `http://127.0.0.1:8501`; `/_stcore/health` returned HTTP 200 (`ok`).

**Owner acceptance:** pending. These automated gates and the empty-state viewport audit do not substitute for owner approval of the actual rendered page. A live chart-bearing viewport review remains unavailable until schedule horizons exist in the local cache.
