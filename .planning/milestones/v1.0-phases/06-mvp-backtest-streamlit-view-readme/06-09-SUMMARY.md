---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "09"
subsystem: ui
tags: [streamlit, matplotlib, dashboard, responsive]

requires:
  - phase: 06-07
    provides: fixed report values and approved Phase 6 result semantics
provides:
  - graphite/slate Streamlit theme and compact complete evaluation scorecard
  - responsive replay controls, chart, companion cards, and ranked strategy layout
  - dark selected-cutoff finishing chart with neutral bars and an accurately labeled mean
affects: [phase-06-browser-validation, phase-06-ui-review]

actuals:
  tokens: 8674
  tasks: 2
  commits: 4
plan_head_before: 1d6e42193eeb052b0437836be7ffa322072ccf0e
plan_head_after: 1d951514d25019111aa90ce1be98580a7411ca93

tech-stack:
  added: []
  patterns:
    - keyed bordered Streamlit containers with scoped responsive CSS
    - direct Matplotlib Figure styling for dark card and PNG surfaces

key-files:
  created:
    - .streamlit/config.toml
  modified:
    - src/f1si/app.py
    - src/f1si/plots/simulate.py
    - tests/app/test_app.py
    - tests/plots/test_simulate_plot.py

key-decisions:
  - Keep the global Streamlit highlight neutral and scope racing red to the primary action and existing semantic signals.
  - Keep the full scorecard grouped together, including team intervals and all sample counts.
  - Leave real desktop/narrow visual acceptance to the blocking browser checkpoint in Plan 06-10.

patterns-established:
  - Dashboard sections use keyed, bordered containers and graphite/slate surfaces.
  - The chart's mean marker is computed from the selected replay's finish draws, never the cutoff lap.

requirements-completed: [UI-01]
coverage:
  - id: D1
    description: Dark finishing distribution with neutral bars and a selected-cutoff mean marker.
    requirement: UI-01
    verification:
      - kind: unit
        ref: tests/plots/test_simulate_plot.py#test_selected_finish_summary_uses_neutral_bars_accent_marker_and_readable_roles
        status: pass
      - kind: unit
        ref: tests/app/test_app.py#test_selected_replay_chart_uses_its_finish_draws_and_shows_full_explanation
        status: pass
    human_judgment: false
  - id: D2
    description: Complete graphite/slate dashboard with report-backed scorecard, controls, companion cards, and strategy table.
    requirement: UI-01
    verification:
      - kind: automated_ui
        ref: tests/app/test_app.py#test_scorecard_renders_complete_fixed_report_values_together
        status: pass
      - kind: unit
        ref: tests/app/test_app.py#test_dark_theme_and_keyed_dashboard_styles_follow_the_ui_contract
        status: pass
    human_judgment: true
    rationale: Browser rendering, clipping, contrast, and responsive geometry require owner inspection in Plan 06-10.
  - id: D3
    description: Existing cutoff-safe and read-only replay semantics and report values remain intact.
    requirement: UI-01
    verification:
      - kind: unit
        ref: uv run python -m pytest tests/app/test_app.py tests/plots/test_simulate_plot.py -q
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-11-15
status: complete
---

# Phase 06 Plan 09: Graphite Dashboard Summary

**A dark motorsport replay dashboard with a compact measured scorecard, responsive control and result cards, and a readable selected-cutoff finishing chart.**

## Performance

- **Duration:** 13 minutes
- **Started:** 2026-11-15T03:23:09Z
- **Completed:** 2026-11-15T03:35:47Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added the dark graphite/slate Streamlit theme with a neutral global highlight and scoped red action/signal styling.
- Kept podium/top-10 model and grid scores, pooled coverage denominator, team intervals, and race/observation/stop counts together in the scorecard.
- Split the selected-cutoff chart, safety-car proxy, tire estimate, and ranked strategy table into readable responsive cards.
- Styled the chart canvas, plot area, neutral bars, legend, annotations, axes, and PNG background; the red mean still uses the selected finish draws.

## Task Commits

1. **Task 1 RED:** `853d75b` — `test(06-09): pin dark finishing chart and chart card`
2. **Task 1 GREEN:** `a063e80` — `feat(06-09): darken selected-cutoff finishing chart`
3. **Task 2 RED:** `d0e72b5` — `test(06-09): assert dashboard hierarchy and theme`
4. **Task 2 GREEN:** `1d95151` — `feat(06-09): build graphite replay dashboard hierarchy`

## Verification

- RED focused chart tests failed on the intended missing chart colors, white PNG background, and absent chart card.
- RED dashboard tests failed on the missing complete scorecard, dark theme, and graphite safety-car rail.
- `uv run python -m pytest tests/app/test_app.py tests/plots/test_simulate_plot.py -q` — **38 passed**.
- `uv run ruff check src/f1si/app.py src/f1si/plots/simulate.py tests/app/test_app.py tests/plots/test_simulate_plot.py` — passed.
- `uv run ruff format --check src/f1si/app.py src/f1si/plots/simulate.py tests/app/test_app.py tests/plots/test_simulate_plot.py` — passed.
- No package or lockfile changes.
- The local health endpoint at `127.0.0.1:8501` was unavailable from this executor session. Plan 06-10 must start/check the app before the owner browser review.

## Decisions Made

- Kept the site-wide Streamlit accent neutral; red remains on the update action and existing top-row, chart-mean, and safety-car signals.
- Kept report formatting and values intact while adding separate team-agreement and stop-timing metric cards inside the same scorecard.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Kept the risk-control regression check resilient to the nested form layout.**
- **Found during:** Task 2 (Build the complete graphite dashboard hierarchy and scoped theme)
- **Issue:** The existing assertion expected the submit call on one exact source line; nesting the form in the controls card required formatting the call across lines.
- **Fix:** Assert that the visible risk value appears before the form submit call and that the call retains the `Update replay` label.
- **Files modified:** `tests/app/test_app.py`
- **Verification:** Focused app and plot suite passed (38 tests).
- **Committed in:** `1d95151`

**Total deviations:** 1 auto-fixed (Rule 3)
**Impact on plan:** Preserved the control behavior check while allowing normal formatting; no product scope change.

## Next Phase Readiness

Plan 06-09 is complete. Plan 06-10 should run the full project gates, push and verify exact-head Ubuntu/Windows CI, start the local app, and keep the human desktop/narrow browser acceptance pending until the owner inspects the rendered page. No screenshot or human visual approval was inferred here.

## Self-Check: PASSED

- All five implementation and test files plus this summary exist.
- All four RED/GREEN task commits are ancestors of the current HEAD.
- The human browser gate remains pending for Plan 06-10.

---
*Phase: 06-mvp-backtest-streamlit-view-readme*
*Completed: 2026-11-15*
