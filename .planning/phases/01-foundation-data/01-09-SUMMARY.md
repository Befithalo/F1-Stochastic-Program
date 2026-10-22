---
phase: 01-foundation-data
plan: 09
subsystem: plots
tags: [matplotlib, figure-api, stint-plot, cli, scramble-consumer, decisions]

requires:
  - phase: 01-07
    provides: as-of door, RACE_END, consumers registry
  - phase: 01-08
    provides: real Bahrain 2023 in the cache
provides:
  - f1si.plots.stints (prepare_stint_plot_data, build_figure, render_stint_plot, plot_file_name)
  - "uv run f1si plot SLUG [--drivers CODE ...]" and global --reports-dir
  - stint_plot_data registered as a future-scramble consumer
  - DEC-050 Stint plot conventions
affects: [01-10, 01-11, phase-2]

tech-stack:
  added: []
  patterns:
    - "Pure data-prep function over a RaceSnapshot plus a Figure-API renderer (no pyplot)"
    - "Output file name from the catalog slug and validated driver codes, never the raw argument"

key-files:
  created:
    - src/f1si/plots/__init__.py
    - src/f1si/plots/stints.py
    - tests/plots/__init__.py
    - tests/plots/test_stint_plot.py
  modified:
    - src/f1si/cli.py
    - tests/test_cli.py
    - tests/guards/consumers.py
    - DECISIONS.md
    - tests/test_decisions_log.py

key-decisions:
  - "Laps are faded (alpha 0.25), not removed: lap 1, pit in, pit out, track status 4/5/6/7; y-range from clean laps"
  - "Panels ordered by grid position (pit-lane starters last); results never read"
  - "Laps with no lap time are skipped and counted in the command output"

requirements-completed: [DAT-02, DAT-03, FND-04]

duration: ~40 min
completed: 2026-10-22
---

# Phase 1 Plan 09: Stint Plot Summary

**`uv run f1si plot bahrain-2023` renders the real race as 20 small panels (lap time vs lap, coloured by tyre compound, slow laps faded, stint changes dotted) from a RACE_END snapshot through the as-of door, with the data step covered by the future-scramble test.**

## Accomplishments

- `prepare_stint_plot_data(snapshot, drivers=None)` is pure: grid-order panels, fade classes by priority (lap 1, pit in, pit out, SC/VSC/red), clean-lap y-range (min - 0.5 s to 98th percentile + 1.0 s), clipped points flagged, stint boundaries from the snapshot's stints, empty lap-0 snapshot gives an empty plot with range (0, 1).
- `build_figure` uses `matplotlib.figure.Figure` only (a test asserts importing the module never loads pyplot); at most 5 columns, shared axes, "^" at the panel edge for out-of-range points, dotted stint-change lines, legend.
- `f1si plot` and `--reports-dir`; errors are one line (unknown race with close matches, 2026 locked with the Phase 1 refusal, bad or unknown driver codes list the valid ones, missing cache).
- `stint_plot_data` added to `tests/guards/consumers.py`; the scramble test (unchanged) passes with it at every lap including lap 0 and RACE_END.
- DEC-050 "Stint plot conventions" appended; MIN_ENTRIES 50, D-15 added to REQUIRED_REFS. Every 01-07/01-08 "Decisions to log" item was already DEC-036..049 (matched by title), so nothing else was added.

## Real Bahrain 2023 run

```
Wrote reports\bahrain-2023.png (20 drivers; 3 laps without a time were skipped). Open it to see lap times by stint.
Wrote reports\bahrain-2023-alo-ham-ver.png (3 drivers; 0 laps without a time were skipped). Open it to see lap times by stint.
```

- `reports/bahrain-2023.png`: 2160 x 1344 px, about 288 KB, 20 panels in 4 rows of 5, VER P1 first through GAS P20. I looked at the image: red soft, white hard and yellow medium dots with dark edges, faded lap 1 / pit / VSC laps, up-arrows at the top edge, dotted stint lines, tyre-wear drift visible inside stints. Legend sits below the panels with a "Lap" label under each bottom-row panel.
- `reports/bahrain-2023-alo-ham-ver.png`: about 63 KB, 3 panels.
- The 3 pit in-laps with no OpenF1 lap end (01-08, DEC-048) have no lap time, so they are skipped and counted in the output line rather than drawn. A lap with a time but no compound would be drawn grey (covered in the module, not hit on Bahrain). PIA (P18) retired on lap 13 and shows a short panel.
- `git ls-files reports data` is empty.

## Task Commits

1. **Task 1: data preparation and renderer** - `a56f7ba` (feat)
2. **Layout fix found while viewing the real PNG (legend overlapped the x label)** - `d742550` (fix)
3. **Task 2: plot command, consumer, DEC-050** - `90d8f94` (feat)

Full suite 353 passed; ruff check, ruff format --check and mypy strict clean.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan expectations about lap 8 and pit-out clipping were wrong for the synthetic data**
- **Found during:** Task 1 tests
- **Issue:** The plan said every lap-8 point is "safety car/VSC/red", but cars that pit on lap 7 have their lap 8 as the pit-out lap, which has higher fade priority; and only the pit-out laps (not every lap-7 point) are clipped.
- **Fix:** Tests assert lap 8 is faded with reason in {VSC, pit out}, at least 3 are VSC, every pit-out point is clipped, and every clean point has no 4/5/6/7 status. The code follows the specified priority; nothing was weakened.
- **Commit:** a56f7ba

**2. [Rule 1 - Bug] Legend overlapped the shared "Lap" label**
- **Found during:** viewing the real PNG
- **Fix:** removed `supxlabel`; each lowest visible panel of a column carries its own "Lap" label (with tick labels on).
- **Commit:** d742550

**3. Small additions:** "v"-less handling uses "^" for any clipped point (also below range, which cannot occur for clean laps); extra CLI tests for race id lookup, bad driver code (no reports folder created) and missing cache; a test that importing the module does not load pyplot.

## Human checks (collected for the end of the phase)

- Open `reports\bahrain-2023.png` (File Explorer, double-click). Expect 20 panels in 4 rows of 5, VER P1 first; red SOFT, yellow MEDIUM, white HARD with dark edges; lap 1, pit laps and the VSC laps faded; pit laps as small up-arrows at the top; dotted vertical lines at stint changes; lap times drifting up inside each stint.

## Known Stubs

None.

## Threat Flags

None beyond the plan. T-01-37 (file name from catalog slug and validated codes, tested), T-01-38 (driver code regex plus membership check), T-01-39 (RACE_END snapshot through the door, plot imports only asof, consumer registered), T-01-40 (2026 refusal tested), T-01-41 (reports/ and data/ untracked) are implemented.

## Next Phase Readiness

Plan 01-10 can run the full multi-season load; the plot works on any cached in-sample race. The future-scramble registry now has 6 consumers.

## Self-Check: PASSED

- Files exist: src/f1si/plots/stints.py, tests/plots/test_stint_plot.py, reports/bahrain-2023.png (untracked).
- Commits a56f7ba, d742550, 90d8f94 exist on main.
