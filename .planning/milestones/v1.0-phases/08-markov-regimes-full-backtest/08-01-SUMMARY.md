---
phase: 08-markov-regimes-full-backtest
plan: "01"
subsystem: simulator
tags: [markov, regimes, replay, numpy, numba]
requires:
  - phase: 06-mvp-backtest-streamlit-view-readme
    provides: cutoff replay, RaceState, seeded simulator, and measured green pit-loss baseline
provides:
  - cutoff-safe five-state regime labels and earlier-race transition estimates
  - validated Markov state arrays and per-regime pit-loss inputs to the numeric simulator
  - deterministic Bahrain 2023 SC-versus-green replay regression
affects: [08-02, walk-forward-backtest, holdout-evaluation]
actuals:
  tokens: 4982
  tasks: 2
  commits: 4
plan_head_before: dc4d52d3d615d8e198ff4b86d7e0cf16a129fd4
plan_head_after: 8ae453792f60b6466152f2b131d40963287b16f4
tech-stack:
  added: []
  patterns: [history-only regime fitting, contiguous validated numeric kernel inputs, per-lap Markov transition draws]
key-files:
  created: [src/f1si/regime/markov.py]
  modified: [src/f1si/state.py, src/f1si/sim/kernel.py, src/f1si/sim/numpy_backend.py, src/f1si/cli.py, tests/test_cli_replay.py, tests/test_state_builder.py, tests/sim/test_safety_car.py]
key-decisions:
  - "Use green, vsc, sc, red, wet order and Dirichlet(1) smoothing for race-local one-lap transitions."
  - "Keep green pit loss measured; treat VSC at 0.75x and SC at 0.5x as assumptions, with red and wet at green cost."
  - "Require a one-hot cutoff regime when a Markov transition matrix is supplied; legacy states without a matrix retain the existing SC path."
patterns-established:
  - "Fit transitions only from the supplied earlier-race History and never connect states across races."
  - "Keep regime labels out of Numba and pass contiguous numeric matrices and costs into each simulated lap."
requirements-completed: [REG-02, REG-03]
coverage:
  - id: D1
    description: "Cutoff replay fits and passes a validated five-state transition model into simulation."
    requirement: REG-02
    verification:
      - kind: integration
        ref: "tests/test_cli_replay.py::test_replay_state_contains_validated_five_state_markov_inputs"
        status: pass
      - kind: e2e
        ref: "tests/test_cli_replay.py::test_bahrain_2023_controlled_safety_car_changes_top_action"
        status: pass
    human_judgment: false
  - id: D2
    description: "State serialization, validation, and stop charging preserve all five regime costs."
    requirement: REG-03
    verification:
      - kind: unit
        ref: "tests/test_state_builder.py and tests/sim/test_safety_car.py"
        status: pass
    human_judgment: false
metrics:
  duration: 27min
  completed: 2026-11-16
  files: 8
  status: complete
---

# Phase 8 Plan 01: Markov Replay Tracer Summary

Cutoff-visible regime labels and race-local transition estimates now reach the seeded Bahrain replay simulator, with per-regime pit costs and a deterministic SC recommendation change for Alonso.

## Performance

- **Duration:** 27 minutes
- **Started:** 2026-11-16T19:24:00Z (approximate)
- **Completed:** 2026-11-16T19:50:47Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added five-state labeling in the fixed `green, vsc, sc, red, wet` order and fit Dirichlet(1)-smoothed transitions from earlier races only, without cross-race transitions.
- Extended Markov-aware `RaceState` serialization and validation with a one-hot current regime, contiguous 5x5 probabilities, and five positive pit costs. The simulator samples transitions per lap and charges the active regime's cost.
- Kept linear pace as the replay default. The Bahrain 2023 lap-15 controlled regression changes ALO's top action from “wait and decide next lap” under green to “pit now (HARD)” under SC.

## Task Commits

1. **Task 1 RED test:** `f547782` — test(08-01): add replay Markov state regression
2. **Task 1 implementation:** `af55469` — feat(08-01): trace Markov regimes through replay simulation
3. **Task 2 tests:** `425c6fb` — test(08-01): cover state regime costs and validation
4. **Task 2 validation fix:** `8ae4537` — fix(08-01): require one-hot Markov state inputs

All four commits were pushed to the current branch. The RED evidence checker accepted the missing Markov-state assertion for Task 1 and the mixed-regime validation assertion for Task 2.

## Files Created/Modified

- `src/f1si/regime/markov.py` — cutoff-safe regime labeling and history-only transition estimation.
- `src/f1si/state.py` — Markov fields, validation, serialization, and replay-state construction.
- `src/f1si/sim/kernel.py` — per-lap state transitions, SC mechanics scoped to SC, and active-regime stop charges.
- `src/f1si/sim/numpy_backend.py` — contiguous Markov inputs and seeded transition draws.
- `src/f1si/cli.py` — cutoff replay history-to-estimator wiring.
- `tests/test_cli_replay.py` — replay state and controlled Bahrain regression.
- `tests/test_state_builder.py`, `tests/sim/test_safety_car.py` — round-trip, invalid-input, regime-cost, and SC-scope coverage.

## Decisions Made

- Transition priors are Dirichlet(1) for every destination in every source row; transition sequences are fit within each earlier race independently.
- Green pit loss remains measured. VSC at 0.75 times green and SC at 0.5 times green remain explicit assumptions; red and wet use green cost.
- Existing states without Markov arrays keep the previous safety-car model path. Markov-aware states require a one-hot starting label and both numeric arrays.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reject mixed current regimes in Markov-aware state**
- **Found during:** Task 2 validation tests
- **Issue:** `RaceState` accepted a split green/SC starting distribution even when a transition matrix was supplied, contrary to the plan's one-hot cutoff state.
- **Fix:** Require exactly one current regime with probability one, and require transition and cost arrays together.
- **Files modified:** `src/f1si/state.py`
- **Verification:** `uv run pytest tests/test_state_builder.py tests/sim/test_safety_car.py -q` (25 passed).
- **Committed in:** `8ae4537`

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Validation closes a correctness gap in the planned state boundary; no unrelated scope was added.

## Verification

- `uv run pytest tests/test_cli_replay.py -q` — 28 passed in 308.20 s.
- `uv run pytest tests/test_state_builder.py tests/sim/test_safety_car.py -q` — 25 passed in 4.59 s.
- `uv run pytest tests/test_state_builder.py::test_markov_state_requires_a_one_hot_cutoff_regime -q` — 1 passed.
- Commit hooks: Ruff check and Ruff format passed for all task commits.

Only the cutoff snapshot and earlier-history path for Bahrain 2023 were used in the replay regression. No 2026 outcome was accessed. No UI/UX files were changed.

## Next Phase Readiness

Plan 08-02 can add synthetic transition recovery and expanded cutoff-label coverage. The tracer exposes the numeric state fields and keeps the holdout boundary unchanged.

## Self-Check: PASSED

All eight source and test files plus this summary exist, and all four task commit hashes are ancestors of the current HEAD.

---
*Phase: 08-markov-regimes-full-backtest*
*Completed: 2026-11-16*
