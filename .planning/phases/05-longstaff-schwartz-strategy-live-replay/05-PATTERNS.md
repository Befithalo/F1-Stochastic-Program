# Phase 5: Longstaff-Schwartz Strategy & Live Replay - Pattern Map

**Mapped:** 2026-11-13  
**Files analyzed:** 9 likely new or modified source/test files  
**Analogs found:** 9 / 9 (all are role or partial matches; the backward LSM/path-branching algorithm has no existing implementation)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/f1si/strategy/longstaff.py` | strategy/service | transform | `src/f1si/strategy/free_track.py` | role-match |
| `src/f1si/interfaces.py` | model / public contract | transform | `src/f1si/interfaces.py` | exact |
| `src/f1si/sim/numpy_backend.py` | simulator/backend | streaming | `src/f1si/sim/numpy_backend.py` | exact |
| `src/f1si/cli.py` | controller / CLI | request-response | `src/f1si/cli.py` (`simulate`, `plan`) | exact |
| `tests/strategy/test_longstaff.py` | test | transform | `tests/strategy/test_free_track.py` | role-match |
| `tests/test_cli_replay.py` | test | request-response | `tests/test_cli_simulate.py` | role-match |
| `tests/conformance/suites.py` | test utility | transform | `tests/conformance/suites.py` | exact |
| `tests/guards/consumers.py` | test utility / registry | request-response | `tests/guards/consumers.py` | exact |
| `tests/guards/test_future_scramble.py` | test | request-response | `tests/guards/test_future_scramble.py` | exact |

The concrete filenames for the new strategy and replay tests follow the phase validation map and research. The simulator seam may require additional internal files after planning chooses between an opt-in path history, resume API, or callback; the analog below is limited to existing simulation state and draw layout.

## Pattern Assignments

### `src/f1si/strategy/longstaff.py` (strategy, transform)

**Analog:** `src/f1si/strategy/free_track.py` (tracked)

**Imports and dependency boundary** (lines 35-44):
```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

from f1si.interfaces import DRY_COMPOUNDS, PaceModel, PitDecision, Plan
from f1si.state import CarState, RaceState
```

**Policy contract and deterministic result construction** (`free_track.py`, lines 105-121):
```python
def decide(self, state: RaceState, *, driver: str) -> PitDecision:
    """Rank every legal plan; pit now iff the best plan stops on the car's next lap."""
    plans = self.rank_plans(state, driver=driver)
    best = plans[0]
    pit_now = (
        bool(best.stop_laps) and best.stop_laps[0] == state.laps_done_of(state.car(driver)) + 1
    )
    return PitDecision(
        driver=driver,
        lap=state.lap,
        pit_now=pit_now,
        compound=best.compounds[0] if pit_now else None,
        best_plan=best,
        ranked_plans=plans,
    )
```

Keep the policy a pure consumer of `RaceState`; put data access in the replay driver. Reuse the existing `PitDecision` / `Plan` representation and deterministic ordering conventions. LSM itself is new: implement a genuine reverse-time conditional-mean continuation regression and pathwise stop/continue comparison, not just a rank of fixed forced schedules. Use `numpy.linalg.lstsq` and rank-aware fallback per RESEARCH.md. Keep the CVaR blend solely in current-cutoff option ranking; it is not the LSM regression target.

**Validation/refusal pattern** (`free_track.py`, lines 123-142, 177-184): validate the driver/state at the public method boundary, wrap model pricing `ValueError` as a domain-specific refusal with actionable wording, reject an empty legal candidate set explicitly, and sort candidates on stable explicit tie-break keys.

### `src/f1si/interfaces.py` (public contract, transform)

**Analog:** itself (tracked)

`SimulationResult` is a frozen value object (`interfaces.py`, lines 120-144); append new optional fields after existing fields and retain `finish_positions` / `total_time_s` as the first two positional fields. `SimulatorBackend.simulate` takes keyword-only `n_races`, injected `rng`, and optional forced `plans` (`interfaces.py`, lines 179-194). `StrategyPolicy.decide(state, *, driver)` has no RNG parameter and promises deterministic behavior without mutating state (`interfaces.py`, lines 167-175). Preserve these public contracts while designing the minimal opt-in path checkpoint/branch seam; do not expose policy-level data access.

### `src/f1si/sim/numpy_backend.py` (backend, streaming)

**Analog:** itself (tracked); draw-stability details also in `src/f1si/sim/draws.py` (tracked) and `tests/sim/test_crn_and_plans.py` (tracked).

**Common-random-number draw layout** (`numpy_backend.py`, lines 245-263):
```python
sc_params, passing, noise = make_streams(rng, d_sc)
n_draw = len(DRAW_COMPOUNDS)
block = uniform_block(self._mode, n_sim + n_cars + n_draw, n, sc_params)
u_sc_all = np.ascontiguousarray(block[:, :n_sim])
z_off = np.ascontiguousarray(normal_from_uniform(block[:, n_sim : n_sim + n_cars]))
z_slots = normal_from_uniform(block[:, n_sim + n_cars :])
```

The fixed compound-name slot layout is documented in that block as preventing plans from shifting other compounds' draws (DEC-087). Preserve stable scenario/draw identity between branches where feasible. Existing simulator path state is initialized as per-race arrays (`numpy_backend.py`, lines 286-303): `order`, `clock`, `age`, `comp`, `stops_done`, `pit_paid`, stop history, safety-car remaining/freshness, and optional recorded clocks. Kernel advancement is performed lap-by-lap in lines 305-352. Extend this path cautiously: research recommends decision-time state plus branch/resume support, with full path storage opt-in rather than an unbounded default result payload.

**Regression evidence:** `tests/sim/test_crn_and_plans.py`, lines 52-73, runs alternative forced plans with the same `make_rng(9)` seed and asserts unchanged rival times and identical safety-car masks. Follow that style for branch identity and common-random-number tests.

### `src/f1si/cli.py` (CLI controller, request-response)

**Analog:** itself (tracked), especially `simulate` parser (`cli.py`, lines 153-185) and `_cmd_simulate` (`cli.py`, lines 610-685).

**Imports/parser pattern** (`cli.py`, lines 19-31, 54-59): import the as-of module, data refusal types, typed contracts, simulator/state builders, and `make_rng`; register a subcommand in `build_parser` with explicit `slug`, `--driver`, optional `--lap`, simulation-count, risk, and seed help. Use plain text output helpers such as `_print_table` (`cli.py`, lines 393-397).

**As-of composition** (`cli.py`, lines 637-668):
```python
accessor = asof.AsOfAccessor(db)
try:
    end = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
    laps_total = int(end.laps["lap_number"].max())
    if lap is None:
        fit_snapshot = end
        state_snapshot = accessor.snapshot(asof.AsOf(race_id, 0))
        history = accessor.history(asof.AsOf(race_id, 0))
    elif lap >= laps_total:
        return _refuse("Nothing to simulate: the race is over ...")
    else:
        fit_snapshot = state_snapshot = accessor.snapshot(asof.AsOf(race_id, lap))
        history = accessor.history(asof.AsOf(race_id, lap))
except OutOfSampleLockedError as err:
    return _refuse(f"{err} ...")
```

For live replay, rebuild snapshot, pace fit, wear filter and `RaceState` at every cutoff through the same helper/path used by `--lap N`; the exception in current `simulate` that allows a hindsight fit must not be copied. Keep the accessor in CLI/replay orchestration and pass only `RaceState` to policy. Validate finite/ranged risk and lap/driver inputs, normalize driver codes, return friendly refusals for expected data/fit limits, and avoid traceback for these cases. Existing `main` catches expected `ValueError` based on `_FRIENDLY_VALUE_ERRORS` near line 61; update its command set if needed.

### `tests/strategy/test_longstaff.py` (unit/conformance tests)

**Analog:** `tests/strategy/test_free_track.py` (tracked)

`test_free_track.py`, lines 12-19, imports the public decision/value types and the policy under test. Lines 22-40 define a small deterministic synthetic `PaceModel`; lines 43-78 construct a compact hand-authored `RaceState`. Prefer this isolated fixture style for synthetic continuation recovery and risk-ranking distributions. The file includes explicit legality and edge cases; add focused checks for regression rank/fallback, CVaR tail orientation/fractional boundary, risk endpoints and rank change, deterministic reasons, and repeated `decide` identity. Add the new policy to the shared suite rather than duplicating its contract assertions.

### `tests/test_cli_replay.py` (CLI integration test)

**Analog:** `tests/test_cli_simulate.py` (tracked)

`test_cli_simulate.py`, lines 18-30, has `_run` and race-driver helpers; lines 33-79 exercise successful hindsight and selected-lap behavior against synthetic cache fixtures and `capsys`. For replay tests, check all-cutoff rows, `--lap N` equality with that row, driver selection, useful refusal messages and deterministic output. Existing fixtures and database helpers are preferable to new bespoke cache setup.

### `tests/conformance/suites.py` (shared conformance utility)

**Analog:** itself (tracked)

Add Longstaff policy registration to the existing strategy suite and use the shared `StrategyPolicy` behavior assertions, including same-input determinism and no state mutation. `StrategyPolicy` contract is in `src/f1si/interfaces.py:167-175`; test registration and implementation should remain centralized in the conformance harness rather than creating a policy-only variant.

### `tests/guards/consumers.py` and `tests/guards/test_future_scramble.py` (guard registry and test)

**Analogs:** themselves (tracked)

`consumers.py`, lines 1-21, documents the registry contract: each consumer is callable as `(db_path, at) -> output` and new as-of consumers must be registered. Existing consumers compose `AsOfAccessor(db_path).snapshot(at)` and downstream transforms (lines 24-31, 54-80). Add replay's state/decision consumer through a registry callable that takes an `AsOf` cutoff and derives all inputs from that cutoff. The property harness in `test_future_scramble.py`, lines 145-165, samples registered consumers and checks output equality after scrambling future rows; its full-grid guard at lines 182-195 covers every in-sample race/cutoff. Keep replay logic out of the strategy module so this guard can prove it ignores unseen data.

## Shared Patterns

### Typed immutable contracts and deterministic policy
**Sources:** `src/f1si/interfaces.py:43-108,120-144,167-194`; `src/f1si/strategy/free_track.py:105-121`  
**Apply to:** new strategy API and simulator result extensions. Keep typed value objects frozen, preserve established positional fields, and maintain `decide(state, *, driver)` with deterministic output and no mutation.

### Seeded simulation and comparable alternatives
**Sources:** `src/f1si/rng.py:1-30`; `src/f1si/sim/numpy_backend.py:245-263`; `tests/sim/test_crn_and_plans.py:52-73`  
**Apply to:** all candidate action estimates and path branches. CLI creates seeded generators via `make_rng`; library receives an injected `Generator`; stable draw slots let alternatives share scenarios. Do not advance a persistent policy RNG across repeated equivalent `decide` calls.

### As-of replay and no-look-ahead
**Sources:** `src/f1si/data/asof.py:1-23`; `src/f1si/cli.py:637-668`; `tests/guards/consumers.py:1-7,76-80`  
**Apply to:** replay driver and registered guard consumer. Rebuild each cutoff from `AsOfAccessor`; no current-race results, future laps, or full-race hindsight fit may feed a replay recommendation. Strategy sees `RaceState` only.

### Friendly expected-error handling
**Sources:** `src/f1si/cli.py:61-62,620-635,654-672`; `src/f1si/strategy/free_track.py:123-142,177-182`  
**Apply to:** new CLI and strategy validation. Reject invalid driver/lap/risk/sample inputs before computation, use `_refuse` for expected CLI errors, and use actionable domain errors for unsupported states or no legal action.

## No Analog Found

| Capability | Reason |
|------------|--------|
| Backward LSM regression over simulated race paths with conditional continuation values | No existing optimal-stopping strategy or pathwise branch/resume API exists. `free_track.py` is only a strategy contract/legality analog; `numpy_backend.py` exposes evolving mutable path arrays but currently returns terminal outcomes and optional clocks. Use RESEARCH.md's algorithm and let planning select the smallest simulator seam. |

## Metadata

**Analog search scope:** `src/f1si/{strategy,sim,data}`, `src/f1si/{cli.py,interfaces.py,state.py,rng.py}`, `tests/{strategy,sim,conformance,guards}`, existing CLI tests.  
**Tracked-source gate:** named code analogs were verified with `git ls-files`; no install/runtime mirror paths are referenced.  
**Pattern extraction date:** 2026-11-13
