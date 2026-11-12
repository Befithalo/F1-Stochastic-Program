---
phase: 02-interfaces-linear-tire-wear-free-track-optimizer
plan: 02
subsystem: pace
tags: [ols, tyre-wear, fuel, identification, pit-loss, cli]
requires: ["02-01"]
provides:
  - "f1si.laps: shared clean-lap rule (fade_reason, slow_status, FADE_TRACK_CODES)"
  - "f1si.pace.linear: fit_linear_pace, LinearPaceFit (a PaceModel), FitReport, CompoundFit, measure_pit_loss, PitLossEstimate"
  - "uv run f1si wear SLUG [--lap N]"
  - "long synthetic fixtures (long_synthetic_data_dir, long_synthetic_db, long_synthetic_truth, build_long_db)"
affects: [02-03, 02-04, 02-05]
tech-stack:
  added: []
  patterns: ["SVD rank check naming unidentified parameters", "design matrix rebuilt every trim pass"]
key-files:
  created:
    - src/f1si/laps.py
    - src/f1si/pace/__init__.py
    - src/f1si/pace/linear.py
    - tests/pace/test_clean_laps.py
    - tests/pace/test_linear_recovery.py
    - tests/pace/test_identification.py
    - tests/test_cli_wear_plan.py
  modified:
    - src/f1si/plots/stints.py
    - src/f1si/cli.py
    - tests/conftest.py
    - tests/conformance/registry.py
    - tests/conformance/test_suites.py
    - tests/guards/consumers.py
    - docs/explained/phase-02.md
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-063 joint OLS fit with refusal on rank deficiency"
  - "DEC-064 clean laps are what the plot fades"
  - "DEC-065 no compound offset; fuel as measured"
  - "DEC-066 pit loss from in-laps and out-laps"
requirements-completed: [PAC-01, INT-02]
completed: 2026-11-11
---

# Phase 2 Plan 02: Linear wear fit, pit loss and `f1si wear` Summary

One OLS over clean laps with a per-driver intercept, a shared fuel slope and a per-compound wear slope that recovers synthetic truth within 3 SE, refuses to print unidentified numbers, measures green-flag pit loss, and is exposed as `f1si wear`.

## Tasks

| Task | Commit | Result |
|------|--------|--------|
| 1 and 2: clean-lap rule, fixtures, fit, pit loss, registrations | 22458e5 | laps.py, pace/linear.py, recovery/identification tests, conformance entry `linear_fit`, scramble consumers `linear_fit` and `pit_loss` |
| 3: `wear` command, DEC-063..066 | f777656 | cli.py, MIN_ENTRIES 66 |

## Bahrain 2023 (real cache)

`wear bahrain-2023`: HARD +0.121 s/lap (0.113 to 0.128, 496 laps), SOFT +0.125 (0.118 to 0.133, 369 laps), MEDIUM not enough data. Fuel -0.078 s/lap (-0.081 to -0.076), outside the literature range, sentence printed. Pit loss median 24.4 s over 42 green-flag stops (10-90%: 23.6 to 34.3). 865 clean laps, 19 drivers. Dropped: pit in 50, pit out 50, outlier 41, lap 1 20, SC/VSC/red 19, compound with too few laps 8, no lap time 3, driver with too few laps 2.

## Deviations from Plan

1. **Tasks 1 and 2 committed together.** The docs tour test requires linear.py to be named once laps.py is, and the red tests were never committed failing (the plan says that is not required). Tests were confirmed to need the new module, then everything went green in one pass. One commit instead of two.
2. **Identification test uses MEDIUM, not HARD.** MEDIUM has fewer clean laps (about 26.5 per driver) than HARD (about 27.5), so raising MIN_CLEAN_LAPS_PER_COMPOUND just above the MEDIUM count removes only MEDIUM. Raising it above HARD would remove both. With only HARD left, fuel and wear are collinear, so the fit is correctly unidentified (asserted).
3. **`dropped` includes "outlier"** as a reason (n_trimmed is also kept separately), so the CLI does not add it twice. Extra reasons "compound with too few laps" and "driver with too few laps" appear in `dropped`.
4. **Hint on an unidentified `--lap N`** suggests `--lap max(N+20, 40)` (so `--lap 20` suggests `--lap 40`), not a literal 20, which would repeat the failing command.
5. **Commit trailer** uses "Claude Sonnet 5.5" per the session attribution instruction (the task prompt said Opus 5.5); the first commit was amended to match.
6. **`uv run f1si ...` is blocked** by Windows Application Control (os error 4551); verified with `uv run python -m f1si ...`.

## Known Stubs

None. `reports_dir` is accepted by `_cmd_wear` but unused until plan 02-03 writes the wear PNG.

## Notes for later plans

- `LinearPaceFit.wear_se(compound)` gives the wear SD for `RaceState` `wear_sd`; `pace_offset(driver_number)` gives the centred driver offset; `wear_rate`, `fitted_compounds`, `fuel_effect`, `is_identified` exist. `fit.report.sigma_s` is the predict SD.
- `predict` raises ValueError for an unidentified fit, an unfitted compound or an unknown driver. SOFT is not fitted on the long synthetic race (start MEDIUM, then HARD); synthetic probes must use MEDIUM and HARD.
- `measure_pit_loss(snapshot, fit)` returns `PitLossEstimate`; `is_default` is True with 22.0 s when nothing is usable.
- `pace/linear.py` imports no `f1si.state`; plan 02-03 may import `pace.linear` from `state.py` or the builder. The CLI imports `DEFAULT_PIT_LOSS_S`, `FUEL_SANITY_RANGE`, `MIN_*` from it.
- Fixtures: `build_long_db(folder, seed)`, `LONG_SLUG`, `LONG_RACE_ID` in tests/conftest.py; registry factories now receive `long_synthetic_db`.
- Docs tour already names laps.py and pace/linear.py; add new modules in the same task that creates them. DEC next free number: DEC-067; MIN_ENTRIES is 66.
- `_FRIENDLY_VALUE_ERRORS` in cli.py already contains "plan" for plan 02-04.
- Full gate: ruff check, ruff format --check, `python -m mypy` clean; 603 tests pass.

## Self-Check: PASSED
