---
phase: 02-interfaces-linear-tire-wear-free-track-optimizer
plan: 03
subsystem: state
tags: [race-state, builder, wear-plot, look-ahead-guard]
requires: ["02-01", "02-02"]
provides:
  - "f1si.state.build_race_state(snapshot, fit, *, laps_total, pit_loss_s) -> RaceState"
  - "f1si.plots.wear: WearPlotData, prepare_wear_plot_data, build_wear_figure, render_wear_plot, wear_file_name"
  - "f1si wear writes reports/wear-<slug>.png"
affects: [02-04, 02-05]
key-files:
  created:
    - src/f1si/plots/wear.py
    - tests/test_state_builder.py
    - tests/plots/test_wear_plot.py
  modified:
    - src/f1si/state.py
    - src/f1si/cli.py
    - tests/guards/consumers.py
    - tests/test_import_order.py
    - tests/test_cli_wear_plan.py
    - docs/explained/phase-02.md
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-067 RaceState builder rules and laps_total"
requirements-completed: [INT-03, PAC-01]
completed: 2026-11-11
---

# Phase 2 Plan 03: RaceState builder and wear PNG Summary

One pure `build_race_state` (snapshot plus `LinearPaceFit` to `RaceState`, None where unknown, gaps None when <= 0) and a pyplot-free wear PNG written by `f1si wear`, both registered with the look-ahead scramble guard.

## Tasks

| Task | Commit | Result |
|------|--------|--------|
| 1: build_race_state + scramble consumer `race_state` | 72cc786 | state.py, tests/test_state_builder.py, import-order tests, consumers |
| 2: wear PNG and CLI | d0d878f | plots/wear.py, wear_plot_data consumer, `Wrote ...` line |
| 3: DEC-067 | 6cdc6e1 | MIN_ENTRIES 67 |

## Real cache (Bahrain 2023)

RaceState at lap 0, 20 and RACE_END (laps_total 57): 20 cars each, leader VER. `f1si wear bahrain-2023` wrote `reports/wear-bahrain-2023.png`: HARD (+0.121) and SOFT (+0.125) panels each with a line and a visible slope band, MEDIUM "not enough data" panel, driver legend, caption. Looked right.

## Deviations from Plan

1. **Builder tests in a new file** `tests/test_state_builder.py` instead of appending to `tests/test_state.py` (new top-level imports; keeps test_state.py untouched).
2. **Tasks 1 and 2 red tests not committed separately** (same practice as 02-02).
3. `state.py` now imports pandas (plus `f1si.data.asof.RaceSnapshot` and `f1si.pace.linear`); no AsOfAccessor/RACE_END import. The module docstring was updated.
4. The `race_state` consumer returns JSON, dict, one `CarState` and the position array (not the gap array, since NaN != NaN breaks the exact scramble comparison).

## Known Stubs

None. regime and pit_loss_s are documented placeholders (D-13).

## Notes for later plans

- `build_race_state(snapshot, fit, *, laps_total, pit_loss_s)`; the CLI plan command should pass `laps_total` = max laps_done from a RACE_END snapshot and `pit_loss_s` = `measure_pit_loss(...).median_s`. A lap-0 state with a fit taken from a different (later) snapshot is allowed; the fit is only used for lookups.
- `tire_age` = laps already on the tyres at the cutoff; the next lap has age tire_age + 1.
- Positions are contiguous from 1 for cars with a finished lap; cars are ordered by position.
- DECISIONS: next free DEC-068; MIN_ENTRIES 67.
- Docs tour already names plots/wear.py; new modules must be added in the same task.
- `reports/` is not tracked by git (PNG left untracked/ignored).
- Full gate: ruff check, ruff format --check, `python -m mypy` clean; 630 tests pass.

## Self-Check: PASSED
