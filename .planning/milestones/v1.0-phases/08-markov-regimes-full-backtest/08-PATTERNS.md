# Phase 8: Markov Regimes & Full Backtest - Pattern Map

**Mapped:** 2026-11-16
**Files analyzed:** 17 source, test, and guard paths named in the context/research
**Analogs found:** 16 / 17 (the dedicated holdout evaluator has no existing implementation)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/f1si/regime/markov.py` (new) | model / utility | transform | `src/f1si/regime/sc_rate.py` | role-match |
| `src/f1si/state.py` | model / builder | transform | `RaceState` and `build_race_state` in the same file | exact |
| `src/f1si/sim/kernel.py` | simulation engine | transform | `lap_step` in the same file | exact |
| `src/f1si/sim/numpy_backend.py` | simulator adapter | request-response | `NumpySimulator.simulate` in the same file | exact |
| `src/f1si/cli.py` | replay composition | request-response | `_prepare_replay_context` in the same file | exact |
| `src/f1si/backtest/walk_forward.py` | backtest runner | batch | current fixed-sample prediction runner in the same file | exact |
| `src/f1si/backtest/scoring.py` | report/scoring | batch | registered-sample scorer in the same file | exact |
| `src/f1si/evaluation/holdout.py` (new) | evaluator / controller | batch | `src/f1si/backtest/pace_evaluation.py` lock-validation and score-layer patterns | role-match; no OOS analog |
| `src/f1si/data/asof.py` (possible extension) | data access | request-response | `AsOfAccessor.snapshot` / `history` | exact |
| `tests/regime/test_markov.py` (new) | test | transform | `tests/regime/test_sc_rate.py` | role-match |
| `tests/test_state_builder.py` | test | transform | existing builder and cutoff tests | exact |
| `tests/sim/test_regime.py` (new) | test | transform | `tests/sim/test_safety_car.py` | role-match |
| `tests/backtest/test_walk_forward.py` | test | batch | fixed-sample, preflight, and prediction-boundary tests | exact |
| `tests/backtest/test_holdout.py` (new) | test | batch | `tests/backtest/test_walk_forward.py` plus import guard tests | role-match |
| `tests/guards/consumers.py` | test registry | transform | registered as-of consumers | exact |
| `tests/guards/import_scan.py` | guard | transform | restricted-import policy | exact |
| `tests/guards/test_future_scramble.py` | guard test | transform | consumer full-grid and future-scramble tests | exact |

The report/lock artifact paths are specified by D-04/D-05, but no Phase 8 filenames or schema exist yet. Follow the Phase 6 report and Phase 7 lock conventions when the planner chooses those artifact names. Keep 2026 output in a separate report from the 20-race in-sample result.

## Pattern Assignments

### `src/f1si/regime/markov.py` (model, transform)

**Analog:** `src/f1si/regime/sc_rate.py`

The estimator is a pure function over an already-cut `History`, not an accessor. The existing pattern documents the boundary and obtains tables from the supplied value:

```python
def estimate_sc_rate(history: History) -> ScRateEstimate:
    """Estimate ... from the races in `history`."""
    track = history.track_status
    cut = history.lap_cutoffs
```

Source: `src/f1si/regime/sc_rate.py:107-120`.

For the new model, retain that pure-input boundary; count adjacent labels within each race, never across race boundaries. Validate the five-by-five numeric matrix before it reaches Numba. `tests/regime/test_sc_rate.py:96-114` shows how to construct a small explicit `History` fixture; `:117-138` shows table-driven status edge cases. Use its seeded synthetic-source setup (`:181-220`) as a guide for reproducible recovery tests, but compare matrix estimates with a stated tolerance because Dirichlet(1) smoothing adds bias.

### `src/f1si/state.py` (shared model and state builder)

**Analog:** `RaceState` validation and `build_race_state` in the target file.

`RaceState.__post_init__` freezes the mappings and validates nonnegative probability mass and positive pit losses (`src/f1si/state.py:250-267`). The builder accepts an immutable cutoff snapshot and measured green baseline (`:501-508`); its current binary regime and two-entry cost map are assembled at `:648-655`.

Keep observation labeling at this snapshot boundary: D-01 priority is red, SC, VSC, wet, green, with rain and track status visible at the same cutoff. Preserve the plain serializable state contract and make the builder consume fitted transition/cost inputs explicitly; do not let `RaceState` reach into storage. Existing validation should be generalized to the five-state representation rather than bypassed.

**Test analog:** `tests/test_state_builder.py:209-220` checks the regime at cutoffs before/during/after SC. The new tests should similarly cover label precedence, VSC-ending, rain visibility, and all five pit-loss values. `tests/test_state_builder.py:73-128` is the pattern for constructing a cutoff-specific integration fixture and asserting resulting tire/state fields.

### `src/f1si/sim/kernel.py` and `src/f1si/sim/numpy_backend.py` (simulation engine and adapter)

**Analogs:** `lap_step` in `src/f1si/sim/kernel.py`; draw conversion and call dispatch in `src/f1si/sim/numpy_backend.py`.

The hot loop currently receives numeric arrays and a pre-generated safety-car uniform (`src/f1si/sim/kernel.py:74-100`); it updates SC state from that uniform and applies the active regime's pit loss (`:131-151`). The Python adapter creates a fixed-size uniform block and passes contiguous arrays to the kernel (`src/f1si/sim/numpy_backend.py:335-339,397-425`).

Keep strings, pandas, and mapping lookups outside the `@njit` path. Pass integer regime indices, a contiguous probability matrix, and numeric pit-cost data. Reuse the existing uniform draw dimension if possible, preserving the explicit generator and common-random-number layout. Existing simulator behavior for SC restart/opportunistic stops remains a constraint; D-01..D-03 do not define new wet-pace or red-flag suspension mechanics.

**Test analog:** `tests/sim/test_safety_car.py:37-57` asserts costs paid for forced/opportunistic stops; `:59-86` checks SC lap masks, order, and the cheaper stop. Use deterministic fixtures and assert the cost for the active simulated regime.

### `src/f1si/cli.py` (replay composition)

**Analog:** `_prepare_replay_context` in `src/f1si/cli.py` (`:1028,1099-1190`); current regime/state calls are at `:1118-1124` and `:1161-1164`.

Keep the data orchestration at the composition layer: obtain snapshot and earlier history via the as-of accessor, fit the model, measure green pit loss, build state, and pass prepared inputs to the simulator. Do not put raw table or results access in the regime model. Preserve the existing replay path so Bahrain 2023 still uses the same public interface.

### `src/f1si/backtest/walk_forward.py` and `src/f1si/backtest/scoring.py` (prediction and report layers)

**Analogs:** `run_walk_forward`, `_predict_cutoff_rows`, and `_predict_from_accessor` in `src/f1si/backtest/walk_forward.py`; scorer functions in `src/f1si/backtest/scoring.py`.

`walk_forward.py:89-132` prepares one context per cutoff and iterates driver rows; `:169-215` rejects unregistered races, uses the cutoff snapshot, and returns prediction-only rows. Its full runner preflights the frozen sample and advances races/cutoffs in registered order (`:275-315`). Preserve this prediction/results separation. `tests/backtest/test_walk_forward.py:66-76` proves preflight fails before prediction, and `:187-194` asserts the runner has no results/scoring imports. `:409-418` is the out-of-sample rejection pattern.

Extend the registered race set and report denominators without changing Phase 6 metric masks, equal-race weighting, seed derivation, or the 1,000-simulation settings. Keep empty/unavailable race rows visible. The 2023-2025 sample is a single `ground_effect_2022_2025` era; report the 2026 holdout separately as `reg_2026`.

### `src/f1si/evaluation/holdout.py` (new evaluator)

**Closest analog:** `src/f1si/backtest/pace_evaluation.py` lock and score separation; no current OOS evaluator exists.

`pace_evaluation.py:75-131` reads a versioned lock, validates frozen race IDs/settings, then returns its digest before any result scoring. Reuse the fail-closed protocol structure, but do not import its result accessor for this task. The only 2026 result door is `OutOfSampleAccessor.final_classification` from `src/f1si/data/out_of_sample.py:1-5,26-61`, and the file explicitly reserves import to `f1si.evaluation.holdout`.

**Critical data-path constraint:** `AsOfAccessor._check` rejects an out-of-sample anchor (`src/f1si/data/asof.py:92-110`), and `.history` contains only races earlier than its anchor (`:112-121`). A 2026 holdout evaluator cannot obtain fitting history by calling `history(AsOf("2026-09", ...))`; history anchored at the final 2025 race omits that race. Before any result access, use a supported feature-only route to build the 2023-2025 transition sequences (research recommends complete in-sample `RACE_END` snapshots), and keep `OutOfSampleAccessor` imports/results calls inside the evaluator. Extend import/future-scramble guards for that intended route. Do not read raw cache storage to work around the boundary.

The protocol should verify the committed 2026-09..17 lock and all implementation artifacts before the one score, then verify the existing report read-only without rescoring.

### Guard and test changes

**Analogs:** `tests/guards/consumers.py:28-35,222-278` registers data consumers and records which public functions must be covered; `tests/guards/test_future_scramble.py:196-204,260-297` exercises every registered consumer and asserts locked races raise. `tests/guards/import_scan.py` is the policy source for the restricted out-of-sample import; update its allowlist only for the evaluator justified by D-05.

Use a synthetic transition sequence with a seeded NumPy generator for recovery and assert row normalization separately from recovery tolerance. Add a future-scramble consumer for any new path that reads `AsOfAccessor` snapshots, and assert that the holdout prediction path cannot import/read final outcomes. Do not register the pure transition-matrix math function as a data consumer; register the function that actually accepts an accessor or database path.

## Shared Patterns

### Cutoff visibility and data access

**Sources:** `src/f1si/data/asof.py:86-121`, `tests/guards/consumers.py:28-35,243-278`
Model functions consume snapshots/history values; only replay/backtest/evaluation composition owns accessors. Register each new accessor consumer for future-scramble coverage.

### Reproducible stochastic simulation

**Sources:** `src/f1si/sim/numpy_backend.py:335-339,397-425`, `tests/sim/test_safety_car.py:37-56`
Generate explicit seeded uniform blocks in Python, pass numeric arrays into Numba, and assert measurable costs/trajectories with deterministic fixtures.

### Fail-closed evaluation

**Sources:** `src/f1si/backtest/pace_evaluation.py:75-131`, `tests/backtest/test_walk_forward.py:58-76,187-194,409-418`
Validate frozen IDs/settings before scoring; fail before predictions on incomplete samples; keep prediction and final-result scoring in separate modules.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/f1si/evaluation/holdout.py` | evaluator | batch | No current evaluator is permitted to access the protected 2026 results door; use the lock-validation pattern from `pace_evaluation.py` and add guard coverage. |

## Metadata

**Analog search scope:** `src/f1si/{regime,state,sim,cli,backtest,data}` and `tests/{regime,sim,backtest,guards}`
**Tracked-source check:** all analogs named above are tracked files (`git ls-files -- <path>` returned a path).
**Pattern extraction date:** 2026-11-16
