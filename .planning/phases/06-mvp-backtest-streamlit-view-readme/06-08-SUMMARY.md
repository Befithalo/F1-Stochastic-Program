---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "08"
subsystem: ui
tags: [streamlit, uncertainty-charts, matplotlib, simulation, responsive]
requires:
  - phase: 06-06
    provides: cutoff-safe selected replay and one-page Streamlit view
  - phase: 06-09
    provides: approved Phase 6 visual contract and scheduled-lap catalog policy
provides:
  - 100 same-sample midpoint finish quantiles per ranked option
  - recommended-strategy forward position history and compact fan bands
  - finish quantile dotplot and cutoff-safe position fan chart
  - brief-aligned colors, copy, tire/timing colors, and tabular numerals
  - desktop and phone viewport audit with findings
affects: [06-10, streamlit, ui-01]
actuals:
  tasks: 3
  commits: 34
plan_head_before: 11dcaaa7a0d0015fae9b887e74005fce423a2c04
plan_head_after: c52d981f80ed4305ce39640aeeb80d8f05e21324
tech-stack:
  added: []
  patterns: [opt-in simulation history, compact empirical quantiles, semantic design tokens]
key-files:
  created: [src/f1si/plots/simulate.py, .planning/phases/06-mvp-backtest-streamlit-view-readme/06-08-SUMMARY.md]
  modified: [.streamlit/config.toml, src/f1si/app.py, src/f1si/interfaces.py, src/f1si/sim/numpy_backend.py, tests/app/test_app.py, tests/plots/test_simulate_plot.py, tests/sim/test_simulate_state.py, tests/strategy/test_longstaff.py, .planning/WINDOWS.md]
key-decisions:
  - "Retain only 100 compact empirical quantiles per option; keep full samples local to scoring."
  - "Record simulated position history only for the selected recommended driver when explicitly requested."
  - "Reserve purple for the recommended strategy; use neutral fog for mean and any Best lap marker."
patterns-established:
  - "Optional simulation diagnostics allocate no position-history matrix on the default path."
  - "Uncertainty chart inputs are reduced to compact summaries before they reach the Streamlit renderer."
requirements-completed: [UI-01]
coverage:
  - id: D1
    description: "Each ranked option exposes 100 empirical midpoint finish quantiles and the selected recommendation has forward-simulated position bands."
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/plots/test_simulate_plot.py; tests/strategy/test_longstaff.py; tests/sim/test_simulate_state.py"
        status: pass
      - kind: integration
        ref: "tests/app/test_app.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "The Streamlit page follows the approved visual and copy contract at desktop and phone widths."
    requirement: UI-01
    verification:
      - kind: automated_ui
        ref: "Edge rendered audit at 1440x900 and 390x844; see viewport findings below"
        status: pass
    human_judgment: true
    rationale: "The local catalog has no supported scheduled lap horizon, so the actual chart-bearing replay could not be submitted for a live visual review."
duration: 42m
completed: 2026-11-15
status: complete
---

# Phase 6 Plan 08: Cutoff-safe uncertainty charts summary

**The selected replay now has compact finish quantiles and a forward-simulated position fan chart, styled to the approved Phase 6 visual contract.**

## Performance

- **Duration:** 42 minutes
- **Started:** 2026-11-15T06:33:39Z
- **Completed:** 2026-11-15T07:15:27Z
- **Tasks:** 3
- **Files modified:** 9 implementation/test files, plus this summary and the planning ledger

## Accomplishments

- Added a 100-point midpoint empirical quantile series to each ranked option from its own scoring sample, plus a test proving all 100 plotted dots match the expected quantiles for a known distribution.
- Added opt-in per-lap simulated positions for the selected recommended driver and reduced that history to percentile bands before rendering the forward-position fan chart.
- Applied the UI-SPEC color tokens, tire and timing colors, tabular figures, sentence-case copy, neutral `Best` semantics, and simulation-count captions. Purple is reserved for the recommended strategy.

## Task Commits

Implementation for the overlapping chart and presentation tasks landed together in `c52d981`.

1. **Task 1: Trace the recommended cutoff strategy into a real forward-position fan chart** - `91f81d2`, `49ffdf4`, `c52d981`
2. **Task 2: Add same-sample compact quantiles for each ranked finish distribution** - `a08b1cc`, `1a38209`
3. **Task 3: Apply the visual contract and inspect the page at both required widths** - `c52d981`

## Verification

- `uv run ruff check src/f1si/app.py src/f1si/interfaces.py src/f1si/sim/numpy_backend.py src/f1si/plots/simulate.py tests/app/test_app.py tests/plots/test_simulate_plot.py tests/sim/test_simulate_state.py tests/strategy/test_longstaff.py` — passed.
- `uv run python -m pytest tests/app/test_app.py tests/plots/test_simulate_plot.py tests/strategy/test_longstaff.py tests/sim/test_simulate_state.py -q` — **73 passed**.
- `uv run python -m py_compile src/f1si/app.py` — passed.
- Streamlit health endpoint returned `ok`; the app remains running at `http://127.0.0.1:8501`.

## Viewport Audit

The page was inspected in a real Edge rendering session at both requested viewport sizes. CUA exposed no browser surface, so the audit used local Edge through its headless/CDP interface.

| Viewport | Findings |
| --- | --- |
| 1440x900 | The audited empty state and report content fit. The coverage denominator now wraps instead of truncating. Sentence-case copy and neutral state colors are visible. |
| 390x844 | No horizontal overflow (`documentElement.scrollWidth` stayed 390). Metric labels and values wrap; the page scrolls vertically to 1512px of main content. Full status copy remains readable. |

**Violations found and fixed:**

- **Color:** Streamlit's default blue `st.info` unavailable-state block was outside the approved palette; replaced it with a neutral, escaped pitwall note.
- **Color:** confidence-interval captions rendered in Streamlit delta chips with a brown background; replaced them with neutral fog captions.
- **Tabular numbers/layout:** the desktop coverage denominator and phone coverage label clipped their final characters; enabled wrapping and applied tabular numeral styles to metrics, labels, captions, and risk endpoints.
- **Copy:** the chart caption used an en dash in the range wording; changed it to the sentence-case text `10th to 90th`.

No remaining color, tabular-number, or copy violation was visible in the rendered states. No overall-best lap appears in this page; if shown later, it must remain neutral and use the `Best` label.

**Live chart limitation:** the local catalog contains 70 eligible races, all with `scheduled_laps=None`. The default Bahrain 2023 replay therefore cannot be submitted, and the two charts could not be inspected with live replay data. The UI correctly excludes unsupported races and displays its unavailable-schedule state. The quantile and chart geometry paths are covered by the focused tests. This remaining live-data check is recorded as an open `unrun-verify` item in `.planning/WINDOWS.md` for Phase 06-10.

## Files Created/Modified

- `.streamlit/config.toml` - light theme tokens.
- `src/f1si/app.py` - eligible race catalog, replay presentation, copy, color, and numeral styling.
- `src/f1si/interfaces.py` - optional simulated position history result.
- `src/f1si/sim/numpy_backend.py` - opt-in selected-driver position recording.
- `src/f1si/plots/simulate.py` - quantile dotplot and position fan chart.
- `tests/app/test_app.py` - cutoff-safe chart path and visual contract coverage.
- `tests/plots/test_simulate_plot.py` - known-distribution quantile coordinate checks.
- `tests/sim/test_simulate_state.py` - default-output invariance and opt-in history behavior.
- `tests/strategy/test_longstaff.py` - same-sample quantile behavior.
- `.planning/WINDOWS.md` - open record for the unavailable live-data verification.

## Decisions Made

- Keep full finish draws and position-history matrices local to analysis; expose only compact quantiles or percentile bands to the UI.
- The recommended strategy alone receives purple treatment. Neutral mean and safety-car markers remain fog; any overall-best lap is neutral and labeled `Best`.

## Deviations from Plan

- The CUA browser surface was unavailable, so viewport checks used local Edge rendering via CDP.
- No supported local scheduled-lap horizon was available. The explicit unavailable state was audited; live chart submission is tracked in the Windows ledger for Phase 06-10.
- Tasks 1 and 3 had overlapping implementation edits and were committed together in `c52d981` after their focused checks passed.

## Issues Encountered

The local event cache does not contain scheduled lap horizons for the 70 eligible races. The page now filters those races and presents the explicit unavailable-schedule state; the missing data prevented a live chart-bearing replay.

## User Setup Required

None.

## Next Phase Readiness

The app is running on port 8501 for Phase 06-10 final acceptance. That plan should repeat the chart-bearing viewport audit when a supported event is available in the local catalog.

---
*Phase: 06-mvp-backtest-streamlit-view-readme*
*Completed: 2026-11-15*

## Integration Follow-up: Plan 06-10 Findings

Plan 06-10's strict-mypy and focused-test gates found test fixtures that had not been updated with the new chart interfaces. The initial check reported four mypy errors: a missing `finish_quantiles` value in the `RankedOption` fake, the `NoisySimulator` protocol mismatch in the registry/conformance check, and an unannotated app accessor helper. The focused pytest run had three failures, all caused by the missing quantile value (70 passed).

Added a realistic 100-position quantile tuple to the backtest fake, aligned `NoisySimulator` and its direct conformance type check with the optional `position_history_driver` argument, and annotated the app test accessor. Strict mypy then exposed six inherited signature mismatches across simulator test doubles in `tests/conformance/stubs.py` and `tests/conformance/test_suites.py`; those doubles now accept and forward the optional keyword. No production behavior or validation state was changed.

Files updated: `tests/backtest/test_metrics.py`, `tests/conformance/registry.py`, `tests/conformance/test_protocols.py`, `tests/conformance/stubs.py`, `tests/conformance/test_suites.py`, and `tests/app/test_app.py`.

Verification after the fixes:

- `uv run python -m mypy` — passed, 158 source files checked.
- `uv run python -m pytest tests/backtest/test_metrics.py tests/conformance/test_protocols.py tests/conformance/test_suites.py tests/app/test_app.py -q` — **103 passed**.
- `uv run ruff check` on the six files above — passed.
- `uv run ruff format --check` on the six files above — passed.

## Self-Check: PASSED

- Summary file exists at the required Phase 06 path.
- Implementation commit `c52d981` is an ancestor of the current branch head.
- Streamlit health endpoint returned `ok` after the summary was written.
- Integration follow-up records the Plan 06-10 failures, test-only fixes, changed files, and passing verification without marking Phase 06 validation complete.
