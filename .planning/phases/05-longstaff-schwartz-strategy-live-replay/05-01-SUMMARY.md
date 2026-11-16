---
phase: 05-longstaff-schwartz-strategy-live-replay
plan: 01
subsystem: strategy
tags: [longstaff-schwartz, numpy, cvar, replay]

requires:
  - phase: 02-interfaces-linear-tire-wear-free-track-optimizer
    provides: StrategyPolicy, PitDecision, Plan, and RaceState contracts
  - phase: 03-monte-carlo-simulator
    provides: NumpySimulator, indexed scenario draws, and common-random-number behavior
  - phase: 04-kalman-tire-filter
    provides: cutoff-local wear estimates for RaceState construction
provides:
  - Pathwise backward conditional-mean stopping policy with seeded scenario branches
  - Selected-cutoff replay CLI with validated inputs and CVaR-aware option evidence
affects: [05-02, 05-03]

actuals:
  tokens: 11124
  tasks: 2
  commits: 7
commits: 7
plan_head_before: d6e4207692c8b3ce877c754a1aa74b61903528c9
plan_head_after: a0aefff25155f6b77c5c0a98718a4f7f21604e50

tech-stack:
  added: []
  patterns:
    - Private opt-in simulator checkpoint capture for path-aligned branch analysis
    - Seed-cloned branch generators preserve indexed common scenarios
key-files:
  created:
    - src/f1si/strategy/longstaff.py
    - tests/strategy/test_longstaff.py
    - tests/test_cli_replay.py
  modified:
    - src/f1si/sim/numpy_backend.py
    - src/f1si/cli.py
    - .planning/STATE.md
key-decisions:
  - "D-01/D-02/D-08: regress conditional mean continuation; rank current actions with (1-risk)*mean + risk*CVaR10, default risk 0.5."
  - "[ASSUMED] Use an intercept and normalized cutoff-visible basis; fall back to the intercept mean for undersized or rank-deficient samples."
  - "Keep score-only reasons when evidence does not support a specific race narrative."
requirements-completed: [STR-01, STR-02, STR-03, STR-04, RPL-02]
coverage:
  - id: D1
    description: Backward conditional-mean LSM and deterministic pathwise stop/continue policy
    requirement: STR-01
    verification:
      - kind: unit
        ref: tests/strategy/test_longstaff.py
        status: pass
    human_judgment: false
  - id: D2
    description: Selected-cutoff replay ranks timing actions with mean, spread, CVaR10, score, and a grounded reason
    requirement: STR-02
    verification:
      - kind: integration
        ref: tests/test_cli_replay.py
        status: pass
    human_judgment: false
  - id: D3
    description: Cached Bahrain 2023 replay smoke for a known driver
    requirement: RPL-02
    verification:
      - kind: manual_procedural
        ref: 05-03-PLAN.md cached Bahrain smoke
        status: unknown
    human_judgment: true
    rationale: Plan 03 owns the cache-backed smoke; this plan validates the selected-cutoff command on synthetic cache fixtures.

duration: 9min
completed: 2026-11-13
status: complete
---

# Phase 5 Plan 1: Selected-Cutoff Longstaff-Schwartz Summary

**A seeded pathwise LSM policy now ranks selected-cutoff pit actions by finishing-position mean and exact worst-decile CVaR.**

## Performance

- **Duration:** 9 minutes
- **Started:** 2026-11-13T15:33:33Z
- **Completed:** 2026-11-13T15:42:32Z
- **Tasks:** 2
- **Files modified:** 7 before this summary

## Accomplishments

- Added private per-lap interaction-state checkpoints and same-seed branch replay without changing the public simulator protocol or default `SimulationResult` layout.
- Added reverse-time least-squares continuation fitting and per-path stop/continue decisions, then ranked current timing choices with the locked mean/CVaR10 blend.
- Added `f1si replay --lap N`, which builds one cutoff-local snapshot, fit, filter result, and `RaceState`, validates catalog/range/risk/count inputs, and prints the ranked evidence and reason.
- Covered continuation recovery, rank fallback, common draws, exact fractional CVaR, risk rank shift, deterministic policy behavior, late boundaries, ties, and CLI refusals.

## Task Commits

1. **Task 1: Tracer — selected-cutoff pathwise LSM recommendation** — `bc0d615` (initial implementation) and `0d08773` (CRN and tracer fixes).
2. **Task 2: Rank every required action with exact CVaR and grounded reasons** — `713bf43` and `dd8e5d5` (test commits), `ba941e0` (implementation), and `a0aefff` (catalog refusal guard test).

**Checkpoint documentation:** `b76e5f2` (recorded tracer verification and the early-cutoff limitation).

## Files Created/Modified

- `src/f1si/strategy/longstaff.py` — policy result types, conditional-mean recursion, CVaR scoring, deterministic ordering, and score-only reason.
- `src/f1si/sim/numpy_backend.py` — private path checkpoint capture and reproducible branch runs.
- `src/f1si/cli.py` — replay parser, trusted input checks, as-of state construction, and text output.
- `tests/strategy/test_longstaff.py` and `tests/test_cli_replay.py` — synthetic algorithm, policy, boundary, and CLI coverage.
- `.planning/STATE.md` and `05-01-CHECKPOINT.md` — execution tracking and the Plan 05-02 handoff.

## Decisions Made

- Continuation regression targets conditional mean finishing position. CVaR is used only for current-cutoff ranking, not as a dynamically CVaR-optimal stopping objective.
- **[ASSUMED]** The regression basis uses normalized position, leader-relative clock gap, tire age, remaining laps, stops completed, and safety-car status. Undersized or rank-deficient data uses an intercept-only conditional mean.
- Stop timing is limited by the existing five-lap minimum final-stint rule; tied options sort by score, mean, CVaR10, stop lap, then compound, with stay-out last.

## Verification

- `uv run --python C:/Users/befit/AppData/Local/Programs/Python/Python312/python.exe python -m pytest -q tests/strategy/test_longstaff.py tests/test_cli_replay.py` — **26 passed**.
- `uv run --python C:/Users/befit/AppData/Local/Programs/Python/Python312/python.exe ruff check src/f1si/cli.py src/f1si/strategy/longstaff.py tests/strategy/test_longstaff.py tests/test_cli_replay.py` — passed.
- `uv run --python C:/Users/befit/AppData/Local/Programs/Python/Python312/python.exe ruff format --check src/f1si/cli.py src/f1si/strategy/longstaff.py tests/strategy/test_longstaff.py tests/test_cli_replay.py` — passed.
- `git diff --check` — passed.

Task 2's RED run produced the intended assertion failure for the late-race legal-stop boundary (22 passed, 1 failed). After enforcing the five-lap minimum, the final focused run passed all 26 tests.

The first focused pytest launch was blocked by Windows Application Control (OS error 4551). The tests were rerun successfully with the official signed user-local CPython 3.12.10 interpreter; the earlier blocked attempt is not treated as a pass.

## Deviations from Plan

None. The initial Python launch restriction was resolved with the authorized signed interpreter, and the plan's test command subsequently passed.

## Known Limitations and Next-Plan Handoff

The synthetic replay fit is not identified until lap 35. This plan's end-to-end selected-cutoff test therefore uses lap 35; earlier cutoffs currently refuse when no dry compound is identified. Plan 05-02 must handle those cutoffs using only data visible at each cutoff and must not use future race laps to identify a fit. The cache-backed Bahrain smoke remains scheduled in Plan 05-03.

## Threat Flags

None beyond the plan's T-05-01 and T-05-03 controls. Replay inputs are resolved through the existing race catalog and entrant data, and no shell command is built from CLI text.

## Self-Check: PASSED

- All listed source, test, summary, and checkpoint files exist.
- All seven commits listed for Plan 05-01 are ancestors of the current branch HEAD.
- `gsd-tools check evaluation-scope --plan 05-01 --commits-only --raw` resolved with no missing or unreachable commits.
- Focused pytest, Ruff check, Ruff format check, and `git diff --check` passed.

---
*Phase: 05-longstaff-schwartz-strategy-live-replay*
*Plan: 01*
*Completed: 2026-11-13*
