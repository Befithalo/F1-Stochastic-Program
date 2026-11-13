---
phase: 04-kalman-tire-filter
plan: 04
subsystem: cli
tags: [kalman, cli, plot, as-of-replay, look-ahead-guard]
requires: ["04-02", "04-03"]
provides:
  - "f1si wear-filter SLUG --driver CODE [--lap N] with per-lap as-of replay"
  - "f1si.plots.wear_filter (prepare/build/render/file name)"
  - "kalman.CutoffRow and kalman.cutoff_row"
  - "race_state_filter scramble consumer"
affects: [04-05]
tech-stack:
  added: []
  patterns: ["fresh snapshot + fit + filter per cutoff", "first-seen row per driver lap"]
key-files:
  created:
    - src/f1si/plots/wear_filter.py
    - tests/plots/test_wear_filter_plot.py
    - tests/test_cli_wear_filter.py
  modified:
    - src/f1si/pace/kalman.py
    - src/f1si/cli.py
    - tests/guards/consumers.py
    - docs/explained/phase-04.md
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-095: one snapshot, one fit and one filter run per lap cutoff; newest-visible-row semantics for cars behind the leader"
requirements-completed: []
duration: ~2h
completed: 2026-11-13
---

# Phase 4 Plan 04: wear-filter command and chart Summary

**`f1si wear-filter` replays a race lap by lap, building a fresh as-of snapshot, pace fit and Kalman filter at every cutoff, prints labelled prior sources and per-lap rate estimates with 95% intervals, and writes the band chart.**

## Tasks

| Task | Commit | Result |
|------|--------|--------|
| 1 cutoff_row + plot module | 1b52bd4 | `CutoffRow`, `cutoff_row`, `plots/wear_filter.py` (Figure API), 7 plot tests, guard EXEMPT entries, explainer bullet |
| 2 wear-filter command | e537497 | subparser, `_cmd_wear_filter`, `_prior_switch_notes`, 9 CLI tests incl. one recording snapshot cutoffs 1..N |
| 3 guards, DEC-095, gate | b975d72 | `race_state_filter` consumer (`build_race_state(wear_filter=...)`), DEC-095, MIN_ENTRIES 95, newest-row fix, legend/hindsight readability |

## Real Bahrain 2023 demo (ALO, full race)

- Replay: 57 laps in 8.1 to 8.4 s (about 15 s wall time with start-up). Per-lap snapshot, fit and filter, no reuse.
- The band narrows within the stints: HARD stint 2 has a half-width of about 0.074 s/lap at its first used lap (race lap 16) and about 0.045 by race lap 30; HARD stint 3 goes from 0.060 (lap 36) to about 0.040 (lap 56).
- Stint 1 (SOFT) shows the early-fit bias the D-19 lines are meant to expose: the rate prior was "prior only" (generic 0.10 s/lap) until lap 13, when the fit first identified SOFT with 0.255 +/- 0.041 s/lap, and the estimate jumps from 0.17 to 0.26. The band stepped, it did not narrow there. The Phase 2 hindsight values are SOFT +0.122 and HARD +0.121 s/lap, so the lap-14 fit prior (0.255) was biased high against hindsight. Reported as measured; the command prints a "band can step here" note at the switch lap.
- D-19 prior lines printed: lap 14 SOFT +0.255 +/- 0.041 (fit), lap 20 HARD +0.129 +/- 0.035 (fit), lap 30 HARD +0.136 +/- 0.031 (fit).
- Chart reviewed visually: `reports/wear-filter-bahrain-2023-ALO.png` (git-ignored output).

## Verification (full gate)

- `ruff check .`, `ruff format --check .`, `mypy`: clean (141 source files).
- Full suite: **914 passed, 9 failed, 1 error, 19 deselected** (5m42s). The 9 failures are the 8 known environment-only ones (5 in tests/test_import_order.py, 3 existing `test_module_imports_without_pyplot`) plus my new `tests/plots/test_wear_filter_plot.py::test_module_imports_without_pyplot`, which spawns `sys.executable -I` and fails identically (`No module named 'f1si'`); I checked by hand with the shim that importing `f1si.plots.wear_filter` does not load `matplotlib.pyplot`. The error is the known db lock test. Nothing else failed.
- Guards: 191 passed including the new filter-fed scramble consumer.
- Existing CLI tests (test_cli, test_cli_simulate, test_cli_wear_plan) pass; `f1si wear-filter --help` shows `--driver` and `--lap`.

## Deviations from Plan

**1. [Rule 1 - Bug] `cutoff_row` semantics: newest visible row, not the row for race lap == cutoff.**
- **Found during:** Task 2 real-data demo (synthetic tests passed, Bahrain gave no rows at all).
- **Issue:** the as-of door shows a lap only once the leader's cutoff lap has passed it, so a car behind the leader never has lap L visible at cutoff L; its newest lap is L-1. The plan's "row whose race_lap == cutoff_lap" returned None for every cutoff.
- **Fix:** `cutoff_row` returns the driver's newest row with race_lap <= cutoff. The CLI keeps each driver lap the first time it appears (what a live system showed then) so laps are not duplicated. Recorded in DEC-095. `CutoffRow.row.race_lap` may be below `cutoff_lap`.
- **Files:** src/f1si/pace/kalman.py, src/f1si/cli.py, tests/plots/test_wear_filter_plot.py. **Commit:** b975d72.

**2. [Rule 1] argparse help `95% band` needed `%%`** (a `%b` crashed `--help`); fixed in e537497.

**3. Chart readability (not in plan):** pale HARD stints and their hindsight line were invisible; hindsight lines are drawn dark and the legend uses edged patches. Mypy errors in the first plot-test commit 1b52bd4 were fixed in e537497 (the pre-commit hook does not run mypy).

Stint header prints "rate prior: fit (began as prior only: ...)" when the source changed inside a stint.

## Known Stubs

None.

## Threat surface

No new surface. T-04-13 (slug and driver regexes before the file name, tested with unsafe values), T-04-14 (driver regex, lap >= 0, unknown driver message, friendly exit 1, 2026 refused), T-04-15 (cutoffs 1..N recorded by test; filter-fed scramble consumer) mitigated. T-04-16 accepted: runtime printed and measured above.

## Self-Check: PASSED

Commits 1b52bd4, e537497, b975d72 exist; created files present.
