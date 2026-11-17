---
phase: 02-interfaces-linear-tire-wear-free-track-optimizer
plan: 01
subsystem: interfaces
tags: [protocols, race-state, conformance, mypy-strict, json]
requires: []
provides:
  - "PaceModel, StrategyPolicy, SimulatorBackend runtime-checkable Protocols plus Plan, PitDecision, SimulationResult, DRY_COMPOUNDS"
  - "Frozen CarState/RaceState/CarArrays with exact JSON round trip"
  - "Conformance harness: suites, registries, planted stubs, mypy rejection proof"
affects: [02-02, 02-03, 02-04, 02-05]
tech-stack:
  added: []
  patterns: ["TYPE_CHECKING-only RaceState import", "unused-ignore trick for mypy rejection", "registry-driven conformance suites"]
key-files:
  created:
    - src/f1si/interfaces.py
    - src/f1si/state.py
    - tests/test_state.py
    - tests/test_import_order.py
    - tests/conformance/__init__.py
    - tests/conformance/suites.py
    - tests/conformance/registry.py
    - tests/conformance/stubs.py
    - tests/conformance/test_suites.py
    - tests/conformance/test_protocols.py
    - docs/explained/phase-02.md
  modified:
    - DECISIONS.md
    - tests/test_decisions_log.py
    - tests/test_docs.py
key-decisions:
  - "DEC-061: Protocol signatures (driver int key, no rng on decide, provisional SimulationResult, TYPE_CHECKING import)"
  - "DEC-062: RaceState layout, None-not-NaN JSON, placeholders regime/pit_loss_s"
requirements-completed: [INT-01, INT-02, INT-03]
duration: ~35 min
completed: 2026-11-11
---

# Phase 2 Plan 01: Interfaces and RaceState Summary

Three runtime-checkable Protocols, a frozen JSON-round-tripping RaceState, and a registry-driven conformance harness in which 17 planted single-defect stubs are each rejected for the right reason, with mypy strict proven to reject wrong signatures.

## Tasks

| Task | Commit | Result |
|------|--------|--------|
| 1 Contracts and RaceState | 7235c55 | interfaces.py, state.py, 26 tests (incl. hypothesis round trip, import order) |
| 2 Conformance harness | b997fca | suites, registry (3 dicts, 1 double each), 17 stubs, mypy proof |
| 3 DEC-061/062, docs test, explainer | 860ba3e | MIN_ENTRIES 62, docs test over all explainers, phase-02.md |

## Outcomes of the assumptions

- **A1:** `runtime_checkable` checks names only. A class with `predict(self, x)` passes `isinstance(..., PaceModel)` (tested).
- **A2:** mypy strict flags an unused `# type: ignore`. Removing one ignore in test_protocols.py made `mypy` fail with an arg-type error on the call, so the ignores are real proofs.

## Deviations from Plan

**1. [Rule 3 - Blocking] Windows Application Control blocks `uv run mypy`.** The mypy launcher exe is blocked (os error 4551) intermittently. Used `uv run python -m mypy`, which gives the identical strict result (77 files, no issues). The first `uv run mypy` call in Task 1 worked once, later calls were blocked.

**2. [Rule 3] File-level `# ruff: noqa: PT018` in tests/conformance/suites.py.** Compound asserts keep one defect keyword per message (the meta-tests match on the message start), so splitting them was not wanted.

**3. TDD commits.** Tests and implementation for Task 1 were committed together (feat), not as separate RED and GREEN commits.

Otherwise the plan was executed as written.

## Known Stubs

None. The only placeholders are the documented ones (regime, pit_loss_s with only "green", D-13).

## Notes for later plans

- Registering a real implementation: add one factory to PACE_MODELS, POLICIES or SIMULATORS in tests/conformance/registry.py (factory takes the long synthetic cache path, returns (object, probe/case)). Each probe/case must be valid for that implementation (e.g. real PaceModel needs driver numbers and compounds it was fitted on).
- Suite messages begin with a defect keyword; `PolicyCase.legal_compounds` is intersected with DRY_COMPOUNDS.
- Phase-02 explainer tour: plans 02-02 to 02-04 must add their new src modules to the tour in the same task (test_tour_covers_every_module takes the union).
- Full gate: 563 tests pass; ruff check and format clean.

## Self-Check: PASSED
