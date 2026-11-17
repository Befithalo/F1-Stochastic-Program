---
phase: 03-monte-carlo-simulator
plan: 02
subsystem: state
tags: [safety-car, race-state, simulation-result, conformance, parameter-uncertainty]
requires:
  - phase: 03-01
    provides: estimate_sc_rate, SC history fixture
provides:
  - build_race_state reads SC regime at the cutoff; pit_loss_s["sc"] placeholder
  - RaceState.sc_laps_elapsed, CarState.pace_offset_sd, FitReport.driver_offset_se
  - SimulationResult diagnostics (sc_lap_mask, stop_laps, pit_loss_paid_s, plan_sources, diagnostics, clock_s) and PlanSource
  - Conformance check and planted stub WrongDiagnosticsShapeSim
affects: [03-03, 03-04, 03-05, 03-06, 03-07]
key-files:
  modified:
    - src/f1si/state.py
    - src/f1si/pace/linear.py
    - src/f1si/interfaces.py
    - tests/conformance/suites.py
    - tests/conformance/stubs.py
    - tests/conformance/test_suites.py
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-076: regime {sc:1.0} only while status 4 is latest; sc_laps_elapsed optional field; SC pit loss = 0.5 x green placeholder until Phase 8"
  - "DEC-077: offset SE plumbing, one shared wear draw per compound per race (refines D-12), SimulationResult diagnostics"
requirements-completed: [SIM-01, REG-01]
completed: 2026-11-12
---

# Phase 3 Plan 02: SC regime and result diagnostics Summary

The state builder now reads the safety-car regime and pace-offset uncertainty as of the cutoff, and `SimulationResult` carries optional diagnostics checked by the conformance suite.

## Commits

- Task 1: c4d646d - SC regime, sc_laps_elapsed, pace-offset SE in the state builder
- Task 2: afc7869 - SimulationResult diagnostics, conformance check, DEC-076/077 (MIN_ENTRIES = 77)

## Deviations from Plan

None in substance. A prior executor stalled after writing Task 2 edits uncommitted; they were reviewed against the plan, found complete, normalised from CRLF to LF, and committed. The full gate passed (ruff, ruff format, mypy, 709 tests passed, 13 deselected).

## Known Stubs

None.

## Self-Check: PASSED
