---
phase: 03-monte-carlo-simulator
plan: 07
subsystem: docs
tags: [explainer, readme, real-data, gate]
requires:
  - phase: 03-06
    provides: simulate command
provides:
  - docs/explained/phase-03.md (complete Phase 3 explainer, UI-03)
  - README simulate command and Phase 3 link
  - tests/test_docs.py phase-03 needles and tour test
  - tests/real/test_simulate_bahrain.py (opt-in, network marker)
key-files:
  created:
    - tests/real/test_simulate_bahrain.py
  modified:
    - docs/explained/phase-03.md
    - README.md
    - tests/test_docs.py
key-decisions: []
requirements-completed: [SIM-01, SIM-02, SIM-03, REG-01]
completed: 2026-11-12
---

# Phase 3 Plan 07: Explainer, README and real Bahrain check Summary

The Phase 3 explainer is complete with numbers re-run now on the local cache, the README documents `simulate`, and an opt-in test exercises the simulator on real Bahrain 2023 data.

## Commits

- Task 2 (done first, independent of the docs): b5d2239 - opt-in real-data test
- Task 1: 55b0fca - explainer, README, docs test

## Real numbers (re-run in this plan)

`uv run python -m f1si simulate bahrain-2023 --driver ALO`: SC rate 1.00% per lap, prior only, 90% interval [0.27%, 2.09%], length 4 laps; P3 3.3%, P4 74.0%, P5 16.6%, P6 4.0%, P7 1.4%; mean 4.28, median 4.0, 90% interval 4 to 6; SC in 43.6% of races; 1.9 s for 50,000 races. `--lap 20`: mean 5.93, median 6.0, interval 4 to 8, SC in 30.9%, 0.9 s. These match plan 03-06.

Honest comparison written into the explainer: Alonso really finished P3; the hindsight interval (4 to 6) does not contain it, so the interval looks narrow. Phase 6 will test interval coverage.

## Gate

- `uv run ruff check .`: passed
- `uv run ruff format --check .`: passed (135 files)
- `uv run python -m mypy`: passed (129 files)
- `uv run python -m pytest -q`: 792 passed, 19 deselected (network)
- `uv run python -m pytest -m network tests/real/test_simulate_bahrain.py -q`: 6 passed (5.5 s)

## Deviations from Plan

**1. [Rule 1 - test design] Pole-sitter check uses the lap-5 state**
- At lap 0 the state has no positions (None; timing has not started), so "position 1 at lap 0" does not exist. The test (`test_leader_beats_last_car`) takes the state after lap 5 and asserts the leader's mean finish beats the last-running car's. Intent unchanged, no bound relaxed.

**2. [Finding] P(top 5) variance ratio**
- The plan expected the explainer to say P(top 5) does not improve; DEC-083 measured 4.22 (improved, report-only). The explainer states the measured value.

**3. [Minor] Test order**
- Task 2 file was committed before Task 1 (they are independent).

No test bounds were relaxed. No source files changed.

## Known Stubs

None. The explainer stub from earlier plans is now complete.

## Manual-only checks for the verifier

- Open `reports\sim-bahrain-2023-ALO-lap0.png` and judge readability.
- Read the benchmark timing in the GitHub Actions log on Ubuntu and Windows.
- CI (Ubuntu and Windows) must be green before the phase counts as done; scipy/numba import on the Windows runner is assumption A5. Not pushed by this plan.

## Self-Check: PASSED

Files exist (phase-03.md, README.md, test_docs.py, test_simulate_bahrain.py); commits b5d2239 and 55b0fca exist.
