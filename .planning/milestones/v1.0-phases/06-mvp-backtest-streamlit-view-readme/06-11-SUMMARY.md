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

The current strategy engine uses the selected cached race and 1,000 simulations:

```text
uv run f1si --data-dir data replay bahrain-2023 --driver ALO --lap 15 --n 1000
  pit in 1 lap (MEDIUM); mean finish 7.291; worst-10% average 15.320

uv run f1si --data-dir data replay bahrain-2023 --driver ALO --lap 40 --n 1000
  stay out; mean finish 4.512; worst-10% average 6.160
```

At lap 15, the optimizer ranks all 13 available stop timings and compounds; the selected plan is a stop on lap 16. The 50,000-simulation convergence check keeps the same action, with mean P7.295 and CVaR10 P15.193. At lap 40 Alonso has already used two stops, so `Stay out` is the sole legal action. The live Streamlit page rendered the 100-point quantile dotplot and position fan chart from real replay simulation outputs at both laps. The quantile unit test checks all 100 dots against a known distribution.

## Screenshots and Audit

- Desktop capture, 1440x2800: `06-11-bahrain-lap15-1440.png`
- Phone capture, 390x5200: `06-11-bahrain-lap15-390.png`
- Full charts, desktop width: `06-11-bahrain-lap15-1440-full-charts.png` (1440x1700)
- Full charts, phone width: `06-11-bahrain-lap15-390-full-charts.png` (390x1300)
- Findings, fixes, and final inspection: `06-UI-REVIEW.md`

The current captures show Bahrain 2023 at lap 15 with all four charts, the full ranked strategy table, and the evaluation. The 390px table keeps all metrics in a compact two-column format. Both widths fit without horizontal overflow.

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

## Follow-up after owner review request

This section records the later strategy-engine and Part 2 view changes in the current working tree. The exact-head GitHub Actions run above validates the earlier implementation commit; it does not include these follow-up edits.

### Part 1: engine and data findings

- The 70 eligible cached races all have positive, provenance-tagged lap horizons. Every one used the approved winner-laps fallback because FastF1 session totals were unavailable. The 17 out-of-sample 2026 rows are unchanged.
- DEC-105 records the three pre-start reduced-distance cases: 2023 Italy (53 to 51), 2024 São Paulo (71 to 69), and 2025 Australia (58 to 57).
- Bahrain 2023 after lap 15, ALO, risk 0.5, seed 0:

| Simulations | Mean finish | CVaR10 | Recommended action | Runtime |
|---:|---:|---:|---|---:|
| 1,000 | 7.291 | 15.320 | Pit in 1 lap (Medium) | 2.074 s |
| 10,000 | 7.286 | 15.264 | Pit in 1 lap (Medium) | 4.629 s |
| 50,000 | 7.295 | 15.193 | Pit in 1 lap (Medium) | 17.178 s |

The stable action across those counts is a Monte Carlo convergence result, not calibration. Lap-15 information underestimates ALO's actual P3 by about 4.3 places; retirements remain unmodeled.

| Driver | Predicted mean | Actual finish |
|---|---:|---:|
| ALB | 12.57 | P10 |
| ALO | 7.29 | P3 |
| BOT | 9.61 | P8 |
| DEV | 14.09 | P14 |
| GAS | 12.94 | P9 |
| HAM | 6.60 | P5 |
| HUL | 12.73 | P15 |
| LEC | 4.23 | DNF |
| MAG | 17.02 | P13 |
| NOR | 12.56 | P17 |
| OCO | 9.95 | DNF |
| PER | 3.15 | P2 |
| PIA | 15.34 | DNF |
| RUS | 8.34 | P7 |
| SAI | 5.85 | P4 |
| SAR | 13.37 | P12 |
| STR | 7.23 | P6 |
| TSU | 12.05 | P11 |
| VER | 1.90 | P1 |
| ZHO | 14.34 | P16 |

These 1,000-simulation predictions use cutoff-safe inputs; actual results are read only by the regression test after prediction generation. The top-five sanity test passes its within-five-places bound.

### Part 2: view and latest verification

- Replaced the plotting path with Altair and populated the trace, stint, quantile-dot, and fan charts from real Bahrain replay data. Added a known-distribution test for all 100 quantile dots. Reworked the app around the recommendation and compact results, with no bordered cards, plain strategist copy, tabular result values, sentence-case headings, and purple reserved for the recommended strategy.
- Latest screenshots are `06-11-bahrain-lap15-1440.png` (1440 px) and `06-11-bahrain-lap15-390.png` (390 px). Both show all four charts. The 390 px view has no horizontal overflow and retains all strategy metrics in its two-column table. Controls use two compact rows on phone width and one row on desktop.
- Contrast measured against the dark background: main text 13.75:1; captions at least 6.35:1; recommendation purple 7.18:1; team colors at least 3.12:1; tire colors at least 5.96:1; timing colors at least 6.35:1. The fan-chart bands measure 4.06:1 or higher.
- The remaining template-like pieces are native Streamlit picker/slider controls and the deliberately plain evaluation table. No color, tabular-number, prohibited-copy, or horizontal-overflow violations remain in the audited views.
- Final local checks: `uv sync --locked`, Ruff lint, Ruff format check, and mypy pass; the full suite reports **1,106 passed, 27 deselected** in 16:29; both live Bahrain network-marked regression tests pass. The direct-import and private-storage-re-export canaries were each planted and caught, and the clean import guard passes after their removal. GitHub Actions was not run on this uncommitted follow-up tree.

## Final owner-review correction — 2026-11-15

This section supersedes the earlier follow-up figures above for the engine, visual audit, test result, and screenshot sizes. The older values are retained as a record of what the review found before its fixes.

### Engine diagnosis and corrected replay

- The large `pit now (MEDIUM)` P10.4 versus `pit in 1 lap (MEDIUM)` P7.3 gap and the `pit in 4 laps` P7.4 to `pit in 5 laps` P9.9 jump came from the Longstaff stop decision comparing realized future finish noise path by path. The regression estimated conditional means, but the exercise choice then inspected the same path's realized finish. That introduced look-ahead selection; it was not evidence of a sudden traffic, pit-loss, or tire-wear effect.
- The stopping rule now compares conditional expected finishes using the simulated state available at that cutoff. Realized finishes are used only after the rule selects the strategy, to form its outcome distribution. Direct, fixed-plan checks are smooth around the questioned laps: `pit now (MEDIUM)` P10.400, lap 16 P10.233, lap 19 P9.941, lap 20 P9.878. Delayed policy options may continue to a later stop when the later state makes that preferable; their row is the expected result of that policy opportunity, not a promise that every scenario pits on that exact lap.
- The optimizer ranks all legal actions (stay out, pit now, and box in 1–5 laps for each available compound). The selected Bahrain lap-15 action is `pit in 1 lap (HARD)` at 1,000 simulations. A future-stop simulation test verifies that pitting at lap 16 is represented and tire age resets after the stop.
- Corrected Bahrain 2023 ALO convergence, after lap 15, risk 0.5, seed 0:

| Simulations | Mean finish | CVaR10 | Recommended action | Runtime |
|---:|---:|---:|---|---:|
| 1,000 | 8.477 | 16.680 | Pit in 1 lap (Hard) | 2.069 s |
| 10,000 | 8.484 | 16.730 | Pit in 4 laps (Medium) | 4.399 s |
| 50,000 | 8.482 | 16.693 | Pit in 4 laps (Medium) | 14.600 s |

The mean and tail estimates converge closely, while the recommended action differs at 1,000. The 50,000 run exceeds the 10-second target; optimization is recorded as M5 work. At 50,000, the model predicts ALO P8.482 versus actual P3, an underestimation of 5.482 places. Lap-15 inputs cannot see Aston Martin's full race pace, and retirements are not modeled. The model is not tuned using that result.

All 20 Bahrain lap-15 predicted means at 1,000 simulations and final result (actual classification is used only for this report and regression test):

| Driver | Predicted mean | Actual finish |
|---|---:|---:|
| VER | 2.364 | P1 |
| PER | 3.740 | P2 |
| LEC | 4.984 | DNF |
| SAI | 6.811 | P4 |
| HAM | 7.791 | P5 |
| STR | 8.397 | P6 |
| ALO | 8.477 | P3 |
| RUS | 9.235 | P7 |
| BOT | 11.073 | P8 |
| OCO | 11.299 | DNF |
| TSU | 13.212 | P11 |
| HUL | 13.654 | P15 |
| ALB | 13.758 | P10 |
| NOR | 14.076 | P17 |
| GAS | 14.332 | P9 |
| SAR | 14.527 | P12 |
| DEV | 15.185 | P14 |
| ZHO | 15.283 | P16 |
| PIA | 16.331 | DNF |
| MAG | 17.560 | P13 |

The sanity test builds all 20 predictions before looking at classification, then checks the five best model-ranked drivers with classified finishes. Retirees are excluded because retirement outcomes are not simulated. Each checked forecast is within five places; this is a narrow sanity check, not proof of overall calibration.

### Final view and verification

- Final full-page captures are `06-11-bahrain-lap15-1440.png` (1440×2800) and `06-11-bahrain-lap15-390.png` (390×4800), both with Bahrain 2023, ALO, lap 15 and all charts visible. Browser audit: document width equals viewport at both sizes, no console/page errors, no visible heading-anchor icons, no chart action toolbar, and no horizontal overflow. The phone probability strip visibly includes all five actions.
- The fan-chart bands use the recommended strategy's purple; the gap trace uses the selected driver's team color and light grey for other drivers. Labels are direct and unclipped, with the fan horizon ending at lap 57 and the gap trace at the cutoff. The stint view labels every driver and shows the recommended next stint with a purple outline.
- Final local suite: **1,113 passed, 27 deselected in 583.13 s**. The two deselected network tests were run separately and passed. Ruff, Ruff format, mypy, `uv lock --check`, and `git diff --check` pass on this tree.
- The test-count explanation and exact changed node IDs are in `06-11-TEST-COUNT-DIFF.md`. GitHub Actions for this final follow-up was pending at documentation time and must be verified against the pushed commit before closeout.
