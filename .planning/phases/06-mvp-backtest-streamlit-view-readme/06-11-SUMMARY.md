---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "11"
subsystem: data, ui
tags: [fastf1, scheduled-laps, streamlit, bahrain-replay, uncertainty-charts]
requires:
  - phase: 06-08
    provides: same-sample quantile dotplot and selected-driver fan chart
  - phase: 06-09
    provides: Phase 06 catalog policy and design contract
provides:
  - FastF1-backed scheduled-lap metadata and auditable winner-lap fallback for all 70 eligible cached races
  - Bahrain 2023 default replay with race and driver pickers and live charts at laps 15 and 40
  - Corrected replay-first Streamlit layout, copy, responsive chart rendering, and viewport evidence
affects: [06-10, streamlit, ui-01]
actuals:
  tasks: 3
  commits: 1
tech-stack:
  added: [FastF1 3.8.x]
  patterns: [scheduled-lap provenance, cache-safe metadata backfill, responsive uncertainty plots]
key-files:
  created:
    - tests/data/test_scheduled_laps.py
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-11-lap-count-backfill.csv
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-11-bahrain-lap15-1440.png
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-11-bahrain-lap15-390.png
  modified:
    - src/f1si/data/loader.py
    - src/f1si/data/_db.py
    - src/f1si/cli.py
    - src/f1si/app.py
    - src/f1si/plots/simulate.py
    - tests/app/test_app.py
    - tests/plots/test_simulate_plot.py
    - pyproject.toml
    - uv.lock
key-decisions:
  - "Prefer Session.total_laps and use the winner's completed laps only when the session total is unavailable; persist source provenance."
  - "Keep purple on the recommended strategy only; an overall-best lap is not shown."
  - "Keep the final owner acceptance checkpoint in Plan 06-10 open after technical verification."
patterns-established:
  - "Update only scheduled-lap fields for complete 2023-2025 in-sample race metadata; preserve the 2026 out-of-sample boundary."
  - "Use compact chart figures at phone widths while retaining the same simulation output."
requirements-completed: [UI-01]
coverage:
  - id: D1
    description: "All eligible cached races have positive, provenance-tagged scheduled-lap counts and the 2026 out-of-sample rows are unchanged."
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/data/test_scheduled_laps.py; tests/test_cli.py"
        status: pass
      - kind: other
        ref: "uv run f1si backfill-scheduled-laps --output .planning/phases/06-mvp-backtest-streamlit-view-readme/06-11-lap-count-backfill.csv; 70 valid, 0 unresolved"
        status: pass
    human_judgment: false
  - id: D2
    description: "Bahrain 2023 renders the quantile dotplot and forward-position fan chart from live simulation output at laps 15 and 40."
    requirement: UI-01
    verification:
      - kind: manual_procedural
        ref: "Live Streamlit replay; app review in 06-UI-REVIEW.md"
        status: pass
      - kind: unit
        ref: "tests/app/test_app.py; tests/plots/test_simulate_plot.py"
        status: pass
    human_judgment: true
    rationale: "Owner acceptance of the rendered replay remains a separate blocking checkpoint in Plan 06-10."
  - id: D3
    description: "Desktop and phone renders follow the approved color, tabular-number, copy, and layout rules."
    requirement: UI-01
    verification:
      - kind: automated_ui
        ref: "06-11-bahrain-lap15-1440.png; 06-11-bahrain-lap15-390.png; full-chart screenshots and 06-UI-REVIEW.md"
        status: pass
    human_judgment: true
    rationale: "The user requested a final approval after reviewing the populated 1440px and 390px views."
duration: 1h 46m
completed: 2026-11-15
status: complete
---

# Phase 6 Plan 11: Bahrain replay and scheduled-lap recovery

**The Streamlit replay now opens on Bahrain 2023 with real chart output, after all 70 eligible cached races received verified lap horizons.**

## Performance

- **Duration:** 1 hour 46 minutes (from the gap-closure plan commit to exact-head CI completion)
- **Started:** 2026-11-15T08:42:58Z
- **Completed:** 2026-11-15T10:26:48Z (remote gate completion; closeout recorded 2026-11-15)
- **Tasks:** 3
- **Implementation artifacts changed:** 18

## Accomplishments

- Added FastF1 session lap retrieval, preferring `Session.total_laps` and falling back to the winner's completed `Laps`. All 70 eligible 2023-2025 cached races resolved to positive counts; all 70 used the explicitly allowed winner fallback. The 17 2026 out-of-sample rows stayed untouched.
- Added an idempotent `backfill-scheduled-laps` CLI operation, provenance output, write-boundary tests, CLI tests, and a regression that every eligible race has a lap count.
- Set the replay page default to Bahrain 2023, ALO, after lap 15, with race and driver pickers. The live app rendered both charts from 1,000 real simulation outputs at laps 15 and 40.
- Reordered the page so the recommendation, one-sentence reason, and uncertainty charts lead; moved the ten-race evaluation below them into one compact results table.
- Removed middle-dot labels and prohibited jargon, applied the required three-decimal Brier wording, retained the 83% coverage result and 85-95% target, and made the empty state two recovery sentences.
- Fixed the live-audit issues with slider wrapping, chart label sizing, legend fit, purple overuse, and strategist-facing copy. The final 1440px and 390px audits found no remaining color, tabular-number, or copy violations.

## Replay Evidence

The direct replay command used the selected cached race and 1,000 simulations:

```text
uv run f1si --data-dir data replay bahrain-2023 --driver ALO --lap 15 --n 1000
  Stay out; mean finish 18.595; worst-10% average 20.000

uv run f1si --data-dir data replay bahrain-2023 --driver ALO --lap 40 --n 1000
  Stay out; mean finish 4.512; worst-10% average 6.160
```

The live Streamlit page rendered the 100-point quantile dotplot and position fan chart from those selected-cutoff simulation results at both laps. The quantile unit test also checks all 100 points against a known distribution.

## Screenshots and Audit

- Standard desktop capture, 1440x900: `06-11-bahrain-lap15-1440.png`
- Standard phone capture, 390x844: `06-11-bahrain-lap15-390.png`
- Full charts, desktop width: `06-11-bahrain-lap15-1440-full-charts.png` (1440x1700)
- Full charts, phone width: `06-11-bahrain-lap15-390-full-charts.png` (390x1300)
- Findings, fixes, and final inspection: `06-UI-REVIEW.md`

The standard captures show the page at the requested viewport heights with Bahrain 2023 at lap 15. The full-chart captures show both uncertainty charts in full. At 390px, the content and chart images fit without horizontal overflow.

## Verification

- Backfill rerun: **70 eligible, 0 updated, 70 already valid, 0 unresolved**.
- Focused Phase 06 checks: **83 passed**.
- Full local suite: **1,117 passed, 25 deselected**.
- Ruff check, Ruff format check, full mypy, `uv lock --check`, and `git diff --check`: passed.
- Exact implementation head: `afa2aeee9fd888bba452a0c7103fe9062531a0bb` (`fix(06): complete Bahrain replay and responsive chart audit`).
- Exact-head GitHub Actions run [43702390713](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43702390713): Ubuntu job [132776132845](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43702390713/job/132776132845) passed; Windows job [132776133125](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43702390713/job/132776133125) passed. Both ran dependency sync, Ruff, formatting, mypy, pytest, and the import-boundary canary.

## Decisions and Deviations

- The resolver/backfill functions live in the existing `src/f1si/data/loader.py` instead of a new `src/f1si/data/sources/fastf1_schedule.py` module. A separate module conflicted with the repository's data-layer import guard and documentation source tour; keeping the functions in the existing data door preserved those boundaries. The backfill behavior and tests are unchanged.
- FastF1 did not expose positive `Session.total_laps` values for these cached sessions, so the approved winner-result fallback supplied all 70 values and records provenance for each.
- Purple remains limited to the recommended strategy and its charts. No overall-best lap is shown; if added later, it must use a neutral `Best` label.

## Next Phase Readiness

Plan 06-11 is complete. Plan 06-10 remains the blocking owner checkpoint. Technical verification and screenshots are recorded, but the Phase 06 UI is not marked owner-approved; the user must review the populated desktop and phone views and explicitly approve them.

---
*Phase: 06-mvp-backtest-streamlit-view-readme*
*Completed: 2026-11-15*
