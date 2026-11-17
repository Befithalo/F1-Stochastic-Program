---
phase: 03-monte-carlo-simulator
plan: 06
subsystem: cli
tags: [cli, simulate, plot, safety-car]
requires:
  - phase: 03-04
    provides: NumpySimulator, SafetyCarModel
  - phase: 03-05
    provides: benchmark and variance-reduction evidence
provides:
  - f1si.plots.simulate (SimPlotData, prepare_sim_plot_data, build_sim_figure, render_sim_plot, sim_file_name)
  - f1si simulate command (_cmd_simulate)
  - DEC-085
affects: [03-07]
key-files:
  created:
    - src/f1si/plots/simulate.py
    - tests/plots/test_simulate_plot.py
    - tests/test_cli_simulate.py
  modified:
    - src/f1si/cli.py
    - docs/explained/phase-03.md
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-085: hindsight rule, input bounds, warm-up excluded from runtime, limitations printed"
requirements-completed: [SIM-01, REG-01]
completed: 2026-11-12
---

# Phase 3 Plan 06: The simulate command Summary

`uv run f1si simulate SLUG --driver CODE [--lap N] [--n 50000] [--seed 0]` prints a driver's finishing-position distribution with the safety-car rate and its source, plan sources and the runtime, and writes `reports/sim-<slug>-<DRV>-lap<N>.png`.

## Commits

- Task 1: 08dcd02 - plot module (pyplot-free, validated file name)
- Task 2: 88e2b62 - `simulate` subcommand, tests, DEC-085 (MIN_ENTRIES = 85), tour entries

## Real run, Bahrain 2023 (local cache)

`uv run python -m f1si simulate bahrain-2023 --driver ALO`:

```
Bahrain Grand Prix 2023: ALO, simulated from lap 0 of 57
This is a hindsight simulation: the pace fit uses the whole race. It makes no claim of foresight.
Safety car rate: 1.00% per lap (source: prior only: no earlier races), 90% interval [0.27%, 2.09%], typical safety car length 4 laps
Plans: 19 from the free-track optimizer, 1 fallback (optimizer refused: The pace model cannot price PIA: Driver number 81 was not in the pace fit. ...)
Note: PIA: not in the fit, pace-offset SD set to the field spread 0.606 s
Note: driver 81 not in the fit: field-average pace
Limitations: rivals follow the free-track best plan (D-10) and no retirements are simulated (D-09).
P3 3.3%  P4 74.0%  P5 16.6%  P6 4.0%  P7 1.4%  P8 0.4%  P9 0.1%  (others 0.0%)
mean 4.28, median 4.0, 90% interval 4 to 6
Safety car in 43.6% of simulated races
runtime: 1.6 s for 50000 races
Wrote reports\sim-bahrain-2023-ALO-lap0.png.
```

`--lap 20`: "Simulation after lap 20: only data known at that lap is used."; 20 optimizer plans, 0 fallback; note "driver PIA: retired or lapped, placed last"; ALO P4 5.8%, P5 38.5%, P6 25.1%, P7 17.5%, P8 12.8%; mean 5.93, median 6.0, 90% interval 4 to 8; safety car in 30.9% of races; runtime 0.9 s. Both PNGs were written; `reports/` is gitignored, nothing under it is committed.

The SC share of 43.6% matches `1 - 0.99^57` (0.436) as in plan 03-05.

## Deviations from Plan

**1. [Test design] Seed-difference test cannot use finishing rows on the synthetic race**
- On the long synthetic race the grid never reshuffles in the simulation (verified: a mid-field driver finishes at one position in 100% of 5,000 races), so the plan's "a different seed changes at least one row at n = 2000" cannot hold for the finishing rows. The test compares the whole block from the first probability row through the safety-car share line: equal for equal seeds, different for different seeds (the SC share moves). No bound was relaxed; real Bahrain rows do vary.

**2. [Minor] `--n abc` exits 2 via argparse**
- Non-numeric `--n` is rejected by argparse (exit 2, one-line usage error, no traceback) instead of the friendly exit-1 message. The test asserts non-zero and no traceback, as the plan's "exit non-zero" allows; every value refusal (`--n 1`, `--n 1000001`, `--lap -1`, `--seed -1`, bad or unknown driver) exits 1 with one line ending in `Try:`.

**3. [Minor] `--seed` default is 0 (the plan), not `DEFAULT_SEED`**
- The plan's interface says default 0; the CLI uses 0 and `DEFAULT_SEED` stays for `load`.

**4. [Minor] Hindsight label wording**
- Lowercase needle "hindsight simulation" required, so the line reads "This is a hindsight simulation: ...".

## Known Stubs

None.

## Threat Flags

None. T-03-16 to T-03-19 are mitigated and tested (file-name validation with `../x`, `--n` cap, snapshot and history both at `AsOf(race, N)`, one-line refusals). `grep` for `AsOfAccessor|RACE_END` in `sim/`, `regime/` and `plots/simulate.py` finds 0 hits.

## Verification

ruff check, ruff format --check, mypy strict pass; full suite 789 passed, 15 deselected (`-k "not network"`).

## Self-Check: PASSED
