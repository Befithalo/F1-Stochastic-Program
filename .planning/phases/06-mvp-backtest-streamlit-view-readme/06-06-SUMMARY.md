---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "06"
subsystem: ui
tags: [streamlit, replay, as-of, cache, app-test]
requires:
  - phase: 06-05
    provides: Team-call comparison, ten-race measured report, and completed replay inputs
  - phase: 06-01
    provides: Shared cutoff-safe replay builder and eligible race registry
provides:
  - Locked Streamlit runtime dependency and CI lockfile assertion
  - One-page read-only replay view with catalog-backed controls and measured ten-race summary
  - Selected cutoff strategy, finishing fan chart, safety-car proxy, tire estimate, reason, and risk
  - Empty, loading, error, partial, zero/one/many, and responsive layout behavior
affects: [UI-01, phase-06-readme]
tech-stack:
  added: [streamlit>=1.67,<2]
  patterns:
    - Streamlit cache_data keys include selected replay settings, cache path and cache/model identity
    - AppTest checks page copy and state contracts without opening final-results access
key-files:
  created:
    - src/f1si/app.py
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-06-01-red.json
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-06-01-red.xml
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-06-02-red.json
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-06-02-red.xml
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/deferred-items.md
  modified:
    - pyproject.toml
    - uv.lock
    - tests/app/test_app.py
    - .planning/WINDOWS.md
key-decisions:
  - "Keep report metrics fixed and separate from the selected replay so empty and failed selections cannot alter evaluation evidence."
  - "Use the shared replay cutoff builder and read-only as-of accessor; exclude final-results access from the page."
  - "Key immutable cached outputs by every selected replay input, data path, cache metadata, and replay model source digest."
  - "Show sparse or prior-driven results as UNCALIBRATED and preserve unaffected panels when strategy output is unavailable."
requirements-completed: [UI-01]
coverage:
  - id: D1
    description: "The locked dependency and CI install gate support the single-page Streamlit runtime."
    requirement: UI-01
    verification:
      - kind: integration
        ref: "uv lock --check"
        status: pass
      - kind: other
        ref: ".github/workflows/ci.yml: uv sync --locked"
        status: pass
    human_judgment: false
  - id: D2
    description: "Catalog controls and the fixed ten-race report lead to a populated cutoff-safe replay with ranked actions and all requested panels."
    requirement: UI-01
    verification:
      - kind: unit
        ref: "uv run python -m pytest tests/app/test_app.py -q (22 passed)"
        status: pass
      - kind: automated_ui
        ref: "Streamlit AppTest default Bahrain 2023 / ALO submit (13 action rows, no exceptions)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Empty, failure, partial, option-count, wrapping, scrolling, and responsive contracts are explicit and tested."
    requirement: UI-01
    verification:
      - kind: automated_ui
        ref: "tests/app/test_app.py: empty-cache AppTest, state helpers, and responsive CSS contract"
        status: pass
      - kind: manual_procedural
        ref: "Narrow viewport visual inspection from 06-06-PLAN.md"
        status: unknown
    human_judgment: true
    rationale: "The executor environment had no browser surface for an actual narrow-viewport inspection; the Streamlit server and AppTest ran successfully."
# Actuals use changed-line characters / 4 on the realized plan diff, not model token usage.
actuals:
  tokens: 18452
  tasks: 2
  commits: 4
commits: 4
plan_head_before: dfbd9cabf437b5e2667536109456a4792076438a
plan_head_after: 4f428df59d5dab8ca07685b7c2a92906ef387291
metrics:
  duration: 12min
  completed: 2026-11-14
status: complete
---

# Phase 06 Plan 06: One-page Streamlit Replay Summary

**The page now presents measured ten-race evidence beside a read-only Bahrain 2023 / ALO cutoff replay, with explicit fallback and unavailable states.**

## Performance

- **Duration:** 12 minutes
- **Started:** 2026-11-14T10:29:04Z
- **Completed:** 2026-11-14T10:40:46Z
- **Tasks:** 2
- **Files modified:** 8 plan outputs (including TDD evidence); one deferred-items note records an unrelated existing guard failure.

## Accomplishments

- Added the bounded `streamlit>=1.67,<2` runtime and regenerated `uv.lock`; CI continues to use `uv sync --locked`.
- Added one read-only page with race, driver, eligible cutoff and risk controls. The page defaults to Bahrain 2023, ALO, the middle available cutoff and risk 0.5.
- Displayed the fixed ten-race podium and top-10 Brier comparisons, finishing-interval coverage with its classified denominator, and race-cluster team-call intervals from the existing report.
- Routed selected replays through the shared cutoff builder. The page displays ranked actions, a finishing-position fan chart, the current safety-car probability proxy, tire uncertainty, reason and selected risk.
- Added exact empty/loading/error copy, fallback and unavailable labels, one-versus-many action labels, inline uncalibrated row status, and responsive wrapping/table-scroll rules.
- Verified a submitted default replay in Streamlit AppTest: no exceptions, 13 strategy actions visible, and all rows present.

## Task Commits

1. **Task 06-06-01 RED: Define the measured page and cache contract** - `71cfde5`
2. **Task 06-06-01 GREEN: Build the cutoff-safe Streamlit page** - `612948b`
3. **Task 06-06-02 RED: Cover states and responsive contracts** - `ec6f12c`
4. **Task 06-06-02 GREEN: Complete replay states and responsive layout** - `4f428df`

**Plan metadata:** captured in final GSD documentation commit `5dfef63`.

## Files Created/Modified

- `src/f1si/app.py` - Streamlit view, fixed report summary, cutoff-safe replay, cache identity and state rendering.
- `tests/app/test_app.py` - Report, control, empty-state, partial-state, cache and responsive layout contracts.
- `pyproject.toml`, `uv.lock` - Approved runtime dependency and locked resolution.
- `06-06-01-red.json` / `.xml`, `06-06-02-red.json` / `.xml` - Machine-checked TDD RED evidence.
- `.planning/phases/06-mvp-backtest-streamlit-view-readme/deferred-items.md` - Existing out-of-scope import-ban failure found during an extra guard run.

## Decisions Made

- Keep the measured report independent from the selected replay so the summary remains visible through empty, loading, error and partial states.
- Use `st.cache_data` with immutable display values and include race, driver, cutoff, risk, simulation count, seed, local cache path, cache metadata and model source digest in cache identity.
- Use the existing Figure-based simulation plot helpers; do not access `ResultsAccessor` or final classifications from the app.

## TDD Gate Compliance

- Task 06-06-01 RED evidence passed `gsd-tools check tdd-red-evidence`; the test failed on the absent page/report behavior. RED commit `71cfde5` preceded GREEN commit `612948b`.
- Task 06-06-02 RED evidence passed the same classifier; its target assertion failed because the singular/count action helper did not exist. RED commit `ec6f12c` preceded GREEN commit `4f428df`.
- Both RED evidence records include the semantic assessment and unchanged JUnit report.

## Deviations from Plan

The app and dependency work stayed within the planned scope. An additional read-only `tests/guards/test_import_ban.py` run exposed existing failures in `src/f1si/backtest/scoring.py` at lines 205, 238 and 319 due to direct `numpy.random.default_rng` imports. Those files are outside Plan 06-06 and were not changed; the finding is documented in `deferred-items.md` and the WINDOWS ledger.

## Verification

- `uv run python -m pytest tests/app/test_app.py -q` - 22 passed.
- `uv run ruff check src/f1si/app.py tests/app/test_app.py` - passed.
- `uv run ruff format --check src/f1si/app.py tests/app/test_app.py` - passed.
- `uv run mypy src/f1si/app.py` - passed.
- `uv lock --check` - passed.
- `rg -q 'uv sync --locked' .github/workflows/ci.yml` - passed.
- Streamlit AppTest submitted the default replay and found no app errors; 13 action rows rendered.
- The browser UI was unavailable for narrow-viewport visual inspection; the automated responsive contract passes and the manual check remains for phase UAT.

## Issues Encountered

- The full import-ban guard run reported two test failures against pre-existing calls in `backtest/scoring.py`; both are outside this plan and recorded for follow-up.

## User Setup Required

None - no external services or credentials are required.

## Next Phase Readiness

The single-page view is ready for the following Phase 06 README plan. Include the narrow viewport inspection in phase UAT.

## Self-Check: PASSED

- `src/f1si/app.py`, `tests/app/test_app.py`, `pyproject.toml`, and `uv.lock` exist at the plan head.
- RED and GREEN commits `71cfde5`, `612948b`, `ec6f12c`, and `4f428df` are ancestors of the plan head.
- The TDD RED evidence records are present and validated.

---
*Phase: 06-mvp-backtest-streamlit-view-readme*
*Completed: 2026-11-14*
