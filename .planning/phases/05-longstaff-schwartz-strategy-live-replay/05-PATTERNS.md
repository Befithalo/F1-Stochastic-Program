# Phase 5: Longstaff-Schwartz Strategy & Live Replay - Pattern Map

**Mapped:** 2026-11-13  
**Files analyzed:** 8 anticipated new/modified implementation and test files  
**Analogs found:** 8 / 8 (some implementation details remain intentionally undecided)

The phase documents explicitly point to the policy under `src/f1si/strategy/` and replay through `src/f1si/cli.py`. Research also calls out an output/interface extension, simulator path support, conformance registration, and future-scramble registration. Test paths below follow the focused paths named in RESEARCH.md; adapt if planning chooses another test layout. Every analog named here was verified with `git ls-files` and is tracked.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/f1si/strategy/longstaff.py` (new; exact module name discretionary) | strategy/service | transform, request-response | `src/f1si/strategy/free_track.py` | role-match |
| `src/f1si/interfaces.py` (modified if scored outputs/path result are added) | model / contract | transform | `src/f1si/interfaces.py` (`PitDecision`, `SimulationResult`) | exact |
| `src/f1si/sim/numpy_backend.py` (possible modification for training paths) | service | batch / transform | `src/f1si/sim/numpy_backend.py` | exact |
| `src/f1si/cli.py` | controller / CLI | request-response, file-I/O | `src/f1si/cli.py` (`wear-filter` replay) | exact |
| `tests/strategy/test_longstaff.py` (new) | test | transform | `tests/strategy/test_free_track.py` | role-match |
| `tests/test_cli_replay.py` (new) | test | request-response, file-I/O | `tests/test_cli_wear_filter.py` | role-match |
| `tests/conformance/test_suites.py` (modified to register policy case) | test | transform | `tests/conformance/suites.py` | role-match |
| `tests/guards/consumers.py` (modified to register replay consumer) | test / registry utility | file-I/O, transform | `tests/guards/consumers.py` | exact |

Research also raises possible simulator-kernel changes if pathwise state cannot be produced through the existing backend. Inspect `src/f1si/sim/kernel.py` before planning that change; its need and exact output shape are unresolved. The phase does not establish a separate replay module, so keep accessor ownership in the CLI unless planning chooses a driver module.

## Pattern Assignments

### `src/f1si/strategy/longstaff.py` (strategy, transform/request-response)

**Analog:** `src/f1si/strategy/free_track.py`

**Imports and pure boundary** (lines 35-44):
```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

from f1si.interfaces import DRY_COMPOUNDS, PaceModel, PitDecision, Plan
from f1si.state import CarState, RaceState
```

Reuse the module's principle: strategy gets a `RaceState` and injected model/simulator, not an accessor. Keep the `decide(state, *, driver)` signature in `src/f1si/interfaces.py:167-175`.

**Decision construction** (`free_track.py`, lines 107-121):
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

**Legality, deterministic ranking, refusal** (`free_track.py`, lines 131-184): `rank_plans` starts with `state.car(driver)`, uses `state.laps_done_of(car)`, derives remaining distance and used compounds, raises `PlanRefusedError` with an actionable explanation if no legal rows exist, sorts by stable explicit keys, and returns immutable `Plan` values. Preserve the existing per-car lap convention and legal-plan rules rather than copying free-track optimization's objective unchanged.

**Randomness:** `src/f1si/sim/numpy_backend.py:166-173` takes `rng: np.random.Generator`; policy calls must derive/reset a seeded generator per decision to keep repeated `decide` calls deterministic. `src/f1si/sim/draws.py:15-20,88-95` documents unconditional indexed draws and spawned child streams. Reuse simulator CRN behavior for comparing options; do not seed global NumPy state.

### `src/f1si/interfaces.py` (model/contract, transform)

**Analog:** same file, tracked and authoritative for immutable public value objects.

**Frozen dataclass validation** (lines 83-107):
```python
@dataclass(frozen=True)
class PitDecision:
    driver: str
    lap: int
    pit_now: bool
    compound: str | None
    best_plan: Plan
    ranked_plans: tuple[Plan, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "ranked_plans", tuple(self.ranked_plans))
        if not self.ranked_plans:
            raise ValueError("ranked_plans must hold at least one plan")
        if self.ranked_plans[0] != self.best_plan:
            raise ValueError("best_plan must equal ranked_plans[0]")
```

`SimulationResult` (lines 120-145) keeps its first two fields stable and places defaulted diagnostics after them. If adding metrics or path outputs, follow this trailing-default convention for compatibility. `StrategyPolicy.decide` (lines 167-175) explicitly guarantees no state mutation and deterministic repeat calls; preserve both.

### `src/f1si/sim/numpy_backend.py` (service, batch)

**Analog:** existing backend, especially constructor and `simulate` signature (lines 116-190).

**Injected backend and RNG** (lines 126-173):
```python
def __init__(
    self,
    model: PaceModel,
    *,
    sc: SafetyCarModel,
    compounds: Sequence[str],
    optimizer: FreeTrackOptimizer | None = None,
    wear_sd_by_compound: Mapping[str, float | None] | None = None,
    fitted_drivers: Sequence[int] | None = None,
    variance_reduction: VarianceReduction = "sobol_antithetic",
    record_clocks: bool = False,
) -> None:
    ...

def simulate(
    self,
    state: RaceState,
    *,
    n_races: int,
    rng: np.random.Generator,
    plans: Mapping[str, Plan] | None = None,
) -> SimulationResult:
    self._validate(state, n_races)
    ...
```

The `plans` argument forces comparable candidate strategies; diagnostics are gathered explicitly. Existing `SimulationResult.clock_s` is optional and cumulative-clock shaped (`interfaces.py:128-145`). Research flags that full per-path stopping-state features may not exist. If extending the simulator, preserve the caller-injected RNG, forced-plan seam, and default compatibility; inspect tracked `src/f1si/sim/kernel.py` for the per-lap state update before choosing where to collect path outputs. Do not add an accessor dependency to the simulator.

### `src/f1si/cli.py` (controller, request-response/file-I/O)

**Analog:** existing `_cmd_wear_filter` replay (`cli.py`, lines 775-832) and parser/dispatch (`65-85`, `898-929`).

**Validation and accessor ownership** (lines 779-808):
```python
try_line = f"Try: uv run f1si wear-filter {slug} --driver CODE --lap 20"
code = driver.upper()
if not _DRIVER_CODE.fullmatch(code):
    return _refuse(f"Driver codes are three capital letters, like VER; got {code}. {try_line}")
if lap is not None and lap < 0:
    return _refuse(f"--lap must be 0 or more, got {lap}. {try_line}")
db = paths.db_path(data_dir)
race_id = asof.resolve_slug(db, slug)
accessor = asof.AsOfAccessor(db)
...
for cutoff in range(1, last_lap + 1):
    snapshot = accessor.snapshot(asof.AsOf(race_id, cutoff))
    fit = fit_linear_pace(snapshot)
    results = filter_stints(snapshot, fit, driver_numbers=[number])
```

For replay, rebuild fit, filter, and `RaceState` from that same `snapshot` within each cutoff iteration; `AsOfAccessor` stays in CLI/driver composition. The strategy receives only the resulting state. Keep expected failures friendly through `_refuse` and existing top-level exception dispatch (`cli.py:930-953`). Register parser and command dispatch next to existing subcommands (`65-85`, `898-929`); tabular output uses `_print_table` (`393-397`).

### `tests/strategy/test_longstaff.py` (test, transform)

**Analog:** `tests/strategy/test_free_track.py`.

Tests build small analytic states/models with local helpers, check numerical behavior against an independent reference where useful (`test_free_track.py:22-80,163-199`), then assert contract behavior without mutating state. The policy test pattern (`251-266`) is:
```python
before = state.to_json()
first = policy.decide(state, driver="AAA")
assert isinstance(first, PitDecision)
assert first == policy.decide(state, driver="AAA")
assert state.to_json() == before
```

Add focused cases for synthetic continuation recovery/fallback, worst-tail orientation and fractional CVaR convention, risk endpoints, deterministic reason, and refusal/legality. For shared contract checks, use `check_strategy_policy` rather than duplicating the shared assertions.

### `tests/test_cli_replay.py` (test, request-response/file-I/O)

**Analog:** `tests/test_cli_wear_filter.py`.

The analog invokes the public `main([...])` with fixture data and captures output. Its `_run` helper (lines 18-19) forwards the temp data directory, and its tests cover full replay, case-insensitive driver, selected `--lap`, friendly errors without tracebacks, and snapshot-per-cutoff behavior (lines 27-132). Follow that structure: assert both all-cutoff and selected-cutoff output, expected error status/text, and equality between the selected cutoff and that row in full replay.

### `tests/conformance/test_suites.py` (test, transform)

**Analog:** `tests/conformance/suites.py:116-146` defines `check_strategy_policy(policy, case)`, covering the protocol, return type, mutation, repeat determinism, driver/lap, legal compounds, and `best_plan` ordering. Register the new policy in the existing suite test harness rather than inventing a second contract suite. Concrete registration pattern is in tracked `tests/conformance/test_suites.py`; preserve its parameterized/factory case structure.

### `tests/guards/consumers.py` (test registry, file-I/O/transform)

**Analog:** existing `race_state_filter` consumer (`lines 93-111`):
```python
def race_state_filter(db_path: Path, at: AsOf) -> object:
    snapshot = AsOfAccessor(db_path).snapshot(at)
    fit = fit_linear_pace(snapshot)
    pit = measure_pit_loss(snapshot, fit)
    lap = at.lap if isinstance(at.lap, int) else 12
    results = filter_stints(snapshot, fit)
    state = build_race_state(
        snapshot,
        fit,
        laps_total=max(12, lap),
        pit_loss_s=pit.median_s,
        wear_filter=current_stint_snapshots(results),
    )
    return state.to_json(), state.to_json_dict(), state.to_arrays().position.tolist()
```

Each consumer is a deterministic `(db_path, at) -> output` registered in `CONSUMERS`; `tests/guards/test_future_scramble.py:145-160` samples the registry to prove future rows do not affect output. Add replay as an accessor consumer that returns recommendation/metrics for the requested cutoff, and register it in `CONSUMERS`. Keep its prepared input path on the same cutoff.

## Shared Patterns

### As-of isolation

**Source:** `src/f1si/data/asof.py:13-20,82-106`; CLI replay analog above.  
**Apply to:** replay composition and guard consumer.  
Accessor remains in replay driver; strategy and simulator receive state/value data only. A fresh snapshot is required per cutoff.

### Strategy contract and immutable state

**Source:** `src/f1si/interfaces.py:83-107,167-175`; `tests/conformance/suites.py:116-146`.  
**Apply to:** policy and its tests.  
Return `PitDecision`, preserve legal plans and best-first order, do not mutate `RaceState`, and make repeated decisions identical.

### Reproducible comparisons

**Source:** `src/f1si/sim/draws.py:15-20,88-95`; `src/f1si/sim/numpy_backend.py:28-39,166-173`.  
**Apply to:** all action valuation and continuation simulation.  
Use injected `Generator`, fixed call layout and CRN across plans when permitted; avoid global random calls.

### Friendly CLI refusals

**Source:** `src/f1si/cli.py:779-797,930-953`.  
**Apply to:** replay argument/data/strategy limitations.  
Validate lap and driver before work, use actionable `_refuse` text for expected limitations, and leave traceback behavior to `--debug`/existing exception policy.

## No Analog Found

| File/Concern | Reason |
|--------------|--------|
| Longstaff-Schwartz pathwise regression/training-state representation | No current strategy performs backward stopping regression. Research explicitly notes current simulation outputs final outcomes and optional clocks, not full pathwise race state. Use the existing simulator and contracts as integration patterns, but design this algorithm-specific seam from RESEARCH.md. |
| Dynamic CVaR continuation recursion | No existing risk-sensitive stopping policy exists. RESEARCH.md recommends explicitly scoping CVaR to current-cutoff candidate ranking unless a dynamic recursion is deliberately designed. |

## Metadata

**Analog search scope:** `src/f1si/strategy/`, `src/f1si/sim/`, `src/f1si/data/`, `src/f1si/pace/`, `src/f1si/cli.py`, and relevant strategy/CLI/conformance/guard tests.  
**Files scanned:** 15 tracked analogs and adjacent contract/test files.  
**Tracked-source gate:** all analog paths above were confirmed by `git ls-files`; no runtime mirror paths used.  
**Pattern extraction date:** 2026-11-13
