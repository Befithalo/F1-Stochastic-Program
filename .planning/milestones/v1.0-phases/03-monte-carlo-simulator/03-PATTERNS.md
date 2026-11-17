# Phase 3: Monte Carlo Simulator - Pattern Map

**Mapped:** 2026-11-12
**Files analyzed:** 30 new or modified files
**Analogs found:** 26 / 30 (4 have no codebase analog; see "No Analog Found")

All excerpts are from the working tree at HEAD 09704ab. Line numbers refer to files as read in this session.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pyproject.toml`, `uv.lock` (modify: scipy, numba, scipy-stubs) | config | n/a | itself (Phase 2 left numpy/pandas/matplotlib only) | exact |
| `src/f1si/sim/__init__.py`, `src/f1si/regime/__init__.py` (new) | config | n/a | `src/f1si/plots/__init__.py`, `src/f1si/pace/__init__.py` | exact |
| `src/f1si/sim/numpy_backend.py` (new: `NumpySimulator`) | service (SimulatorBackend) | batch (Monte Carlo) | `tests/conformance/registry.py::NoisySimulator` (contract) + `strategy/free_track.py::FreeTrackOptimizer` (class shape, injected `PaceModel`) | role-match |
| `src/f1si/sim/kernel.py` (new: `@njit lap_step`) | utility | transform / batch | none for numba; `free_track.py::price_plan_slow` is the plain-Python reference style | no analog (numba) |
| `src/f1si/sim/draws.py` (new: Sobol/antithetic/CRN layout) | utility | transform | `src/f1si/rng.py` (spawn doctrine) | partial |
| `src/f1si/sim/plans.py` (new: plan resolution, fallback, diagnostics) | service | batch | `strategy/free_track.py` (`rank_plans`, `PlanRefusedError`) | role-match |
| `src/f1si/sim/constants.py` (new) | config | n/a | `strategy/free_track.py` lines 46-47 (`Final` constants), `pace/linear.py` lines 73-83 | exact |
| `src/f1si/regime/sc_rate.py` (new: `estimate_sc_rate(History)`) | service (consumer of History) | transform | `pace/linear.py::measure_pit_loss` (pure fn of snapshot returning frozen estimate) | role-match |
| `src/f1si/interfaces.py` (modify: extend `SimulationResult`) | model | n/a | itself lines 110-119 | exact |
| `src/f1si/state.py` (modify: regime, `pit_loss_s["sc"]`, optional `pace_offset_sd`, `sc_laps_elapsed`) | model + builder | transform | itself; precedent for optional keys = `laps_done` (DEC-073) | exact |
| `src/f1si/pace/linear.py` (modify: `FitReport.driver_offset_se`, `LinearPaceFit.pace_offset_se`) | service | transform | `LinearPaceFit.wear_se` / `pace_offset` (lines 160-175) | exact |
| `src/f1si/synthetic/generator.py` (modify: SC spec, byte-identical defaults) | utility | file-I/O / transform | `_vsc_events`, `_track_status_table`, `vsc_laps` field (lines 73-74, 126-147, 297-298) | exact |
| `src/f1si/plots/simulate.py` (new) | component (plot) | file-I/O | `src/f1si/plots/wear.py` | exact |
| `src/f1si/cli.py` (modify: `simulate` subcommand) | controller | request-response | `_cmd_plan` / `_cmd_wear` / `main` | exact |
| `tests/sim/test_simulate_state.py`, `test_overtaking.py`, `test_kernel.py`, `test_crn_and_plans.py`, `test_state_start.py`, `test_safety_car.py`, `test_sc_frequency.py`, `test_reproducibility.py`, `test_draws.py` (new) | test | transform | `tests/strategy/test_free_track*.py`, `tests/pace/test_linear_recovery.py`, `tests/conformance/suites.py` | role-match |
| `tests/sim/test_benchmark.py` (new) | test | batch | `tests/conformance/registry.py::_free_track` (builds the 57-lap state) | partial |
| `tests/sim/test_variance_reduction.py` (new) | test | batch | none (multi-seed statistics); use `make_rng` seeding style from `tests/conftest.py` | no analog |
| `tests/regime/test_sc_rate.py` (new) | test | transform | `tests/pace/test_linear_recovery.py` + `tests/conftest.py::build_long_db` | role-match |
| `tests/test_cli_simulate.py` (new) | test | request-response | `tests/test_cli_wear_plan.py` | exact |
| `tests/plots/test_simulate_plot.py` (new) | test | file-I/O | `tests/plots/test_wear_plot.py` | exact |
| `tests/real/test_simulate_bahrain.py` (new, opt-in `network`) | test | request-response | `tests/real/test_wear_bahrain.py` | exact |
| `tests/conformance/registry.py` (modify: `SIMULATORS["numpy_sim"]`) | config (registry) | n/a | `_free_track` factory + `_noisy_simulator` (lines 143-159, 170-172) | exact |
| `tests/conformance/stubs.py`, `NoisySimulator` (modify: new `SimulationResult` fields) | test double | n/a | itself | exact |
| `tests/guards/consumers.py` (modify: `sc_rate` consumer, `DESIGNATED_MODULES`, `CONSUMED`/`EXEMPT`) | config (registry) | n/a | itself lines 52-157 | exact |
| `tests/conftest.py` (modify: SC-history fixture) | test fixture | file-I/O | `long_specs` / `build_long_db` / `long_synthetic_*` (lines 45-82) | exact |
| `tests/test_state_builder.py`, `tests/test_state.py` (modify) | test | transform | themselves (Pitfall 7: `regime == {"green": 1.0}`, `set(pit_loss_s) == {"green"}`) | exact |
| `tests/test_synthetic.py` (modify: SC default byte-identical) | test | transform | itself | exact |
| `tests/test_docs.py`, `tests/test_decisions_log.py` (modify) | test | n/a | themselves (`MIN_ENTRIES = 73` at line 44) | exact |
| `DECISIONS.md` (append DEC-074..), `docs/explained/phase-03.md`, `README.md` | docs | n/a | DEC-068..073, `docs/explained/phase-02.md`, README `wear`/`plan` lines | exact |

## Pattern Assignments

### `src/f1si/sim/numpy_backend.py` (service / SimulatorBackend, batch Monte Carlo)

**Analog A (contract + test double):** `tests/conformance/registry.py` lines 89-105 (`NoisySimulator`), and `src/f1si/interfaces.py` lines 154-170 (`SimulatorBackend`).

**Signature to implement exactly** (interfaces.py 158-165):
```python
def simulate(
    self,
    state: RaceState,
    *,
    n_races: int,
    rng: np.random.Generator,
    plans: Mapping[str, Plan] | None = None,
) -> SimulationResult:
```
Conformance suite (`tests/conformance/suites.py` lines 148-177) requires: `isinstance(sim, SimulatorBackend)`; shape `(n_races, n_cars)` in `state.cars` order; `finish_positions` int64 and `total_time_s` float64, finite; each row a permutation of `1..n_cars`; `state.to_json()` unchanged; same `make_rng(7)` seed gives bit-identical arrays. Sort positions like the double does (registry.py 104):
```python
positions = (np.argsort(np.argsort(total, axis=1), axis=1) + 1).astype(np.int64)
```
Use a stable argsort (`kind="stable"`) so ties resolve deterministically.

**Analog B (class with injected PaceModel, validation in `__init__`, `Final` constants):** `src/f1si/strategy/free_track.py` lines 85-103.
```python
class FreeTrackOptimizer:
    def __init__(self, model: PaceModel, *, compounds: Sequence[str], min_stint_laps: int = MIN_STINT_LAPS) -> None:
        if min_stint_laps < 1:
            raise ValueError(f"min_stint_laps must be >= 1, got {min_stint_laps}")
        self._model = model
        self._compounds = tuple(sorted({str(c).upper() for c in compounds}))
```
Constructor for the simulator: `NumpySimulator(model: PaceModel, *, sc: SafetyCarModel, compounds, wear_sd_by_compound, variance_reduction: Literal["none","antithetic","sobol_antithetic"] = "sobol_antithetic", ...)`. Validate and raise `ValueError` with the bad value in the message.

**Per-car lap origin (WR-01 / DEC-073) - copy this idiom** (free_track.py 69 and 112): each car's next lap is `state.laps_done_of(car) + 1`; tire age at that lap is `car.tire_age + 1`.
```python
for lap in range(state.laps_done_of(car) + 1, state.laps_total + 1):
    age += 1
```
`price_plan_slow` (free_track.py lines 54-82) is the exact hand-calculation reference to use in `tests/sim/test_state_start.py` and the zero-noise kernel test: after a stop on lap k the age resets to 0 and the next lap has age 1; `state.pit_loss_s["green"]` is added on the stop lap.

**Pace tables:** one `PaceModel.predict` call over `(car, lap, compound, age)` (RESEARCH Pattern 7). Keyword-only args `driver=`, `compound=`, `tire_age=`, `lap=` as int64 / `np.str_` arrays (interfaces.py 126-133). `LinearPaceFit.predict` raises `ValueError` for unfitted compound or driver (linear.py 196-206), so wrap in a borrow adapter and record borrowed pace in diagnostics.

**State to arrays:** use `state.to_arrays()` (state.py 265-291), which returns read-only struct-of-arrays with NaN for None, `-1` position, `""` compound.

**Randomness:** only `rng.spawn(k)` (rng.py docstring lines 6-9). Never `default_rng`, `SeedSequence` (import scan, `f1si.rng` only).

**Must not import** `f1si.data.asof` (takes `RaceState` only; no consumer entry needed).

---

### `src/f1si/sim/kernel.py` (utility, sequential per-lap kernel)

**Analog:** none for numba. Style references only:
- `price_plan_slow` (free_track.py 54-82) as the plain-Python oracle shape; expose `lap_step.py_func` and compare against jitted output (RESEARCH Pitfall 12, "Equivalence of jitted and Python kernel").
- Module docstring with the math and conventions, as in `state.py` lines 1-45 and `interfaces.py` lines 1-26.

Rules from RESEARCH: `@njit(cache=True)`, `fastmath=False`, no `parallel=True`, lap-major state arrays `(n_races, n_cars)`, draws generated unconditionally and indexed by car identity (CRN). mypy strict: `scipy-stubs` dev dependency; check how `njit` typing passes (`# type: ignore` only if mypy demands it).

---

### `src/f1si/sim/draws.py` (utility, QMC / antithetic draws)

**Analog:** `src/f1si/rng.py` (spawn doctrine, lines 6-9 and 22-30) for the seed-handling idiom; Sobol itself has no analog.
```python
def make_rng(seed: int) -> np.random.Generator:
    if isinstance(seed, bool) or seed < 0:
        raise ValueError(f"seed must be a non-negative integer, got {seed!r}")
    return np.random.default_rng(seed)
```
Copy the validation style (reject bool, negative, non-int with a message quoting the value). RESEARCH code to adopt:
```python
def sobol_pairs(d: int, n: int, child: np.random.Generator) -> NDArray[np.float64]:
    h = (n + 1) // 2
    m = max(1, math.ceil(math.log2(h)))
    u = qmc.Sobol(d=d, scramble=True, rng=child).random_base2(m)[:h]
    return np.concatenate([u, 1.0 - u])[:n]
```
Use `rng=` not `seed=` (pyproject turns `DeprecationWarning` from `f1si` into an error). Clip before `norm.ppf`: `np.clip(u, 1e-12, 1 - 1e-12)`.

---

### `src/f1si/sim/plans.py` (service, per-car plan resolution)

**Analog:** `src/f1si/strategy/free_track.py` (`FreeTrackOptimizer.rank_plans`, `PlanRefusedError`).

**Use for non-forced cars (D-10):** `FreeTrackOptimizer(fit, compounds=fit.fitted_compounds).rank_plans(state, driver=code)[0]` once per call (not per race).

**Refusal handling pattern** (free_track.py 50-51 and 127-141): the optimizer raises `PlanRefusedError(ValueError)`; catch it per car, build the documented fallback plan, and record `(driver, "optimizer" | "fallback", reason)` in diagnostics.
```python
class PlanRefusedError(ValueError):
    """The optimizer will not plan for this driver; the message says why and what to do next."""
```
Fallback rule (D-10): one stop near the middle of the car's remaining laps, onto a fitted compound not in `car.compounds_used`; else no further stop. Respect `MIN_STINT_LAPS` / `MAX_TOTAL_STOPS` (free_track.py 46-47; import them, do not redefine). `Plan.__post_init__` (interfaces.py 59-75) enforces strictly increasing stop laps >= 1 and equal tuple lengths; build fallback plans through `Plan(...)` so it validates.

**Forced plans (D-11):** a `plans[code]` entry must be followed exactly; validate with `state.car(code)` (state.py 247-259) which raises the friendly "Unknown driver code ... Codes in this state: ..." `ValueError`.

---

### `src/f1si/sim/constants.py` (config)

**Analog:** `pace/linear.py` lines 73-83 and `free_track.py` 46-47: named `Final` constants, one per line, each with a DEC reference comment.
```python
MIN_CLEAN_LAPS_PER_COMPOUND: Final = 30
CI_Z: Final = 1.96
DEFAULT_PIT_LOSS_S: Final = 22.0
```
Suggested names/values from RESEARCH (all `[ASSUMED]`, justify in DEC): `MIN_GAP_S=0.5`, `THRESHOLD_S=0.3`, `SCALE_S=0.25`, `PASS_COST_S=0.3`, `SC_SLOWDOWN=1.4`, `SC_PIT_RATIO=0.5`, `RESTART_SPACING_S=1.0`, `SC_STOP_WINDOW_LAPS=5`, `SC_FALLBACK_DURATION_LAPS=4`, `START_SPACING_S=0.8`. Reuse the generator's `vsc_slowdown_factor` default 1.4 value, not its symbol.

---

### `src/f1si/regime/sc_rate.py` (service, History -> frozen estimate)

**Analog:** `src/f1si/pace/linear.py::measure_pit_loss` (line 548) with `PitLossEstimate` (lines 119-129): a pure public function returning a frozen dataclass of plain Python values, with a "default/prior" flag (`is_default`) when no data exists.
```python
@dataclass(frozen=True)
class PitLossEstimate:
    median_s: float
    p10_s: float
    p90_s: float
    n_stops: int
    n_slow_excluded: int
    n_unusable: int
    is_default: bool
```
Mirror as `ScRateEstimate(rate_per_lap, ci_low, ci_high, n_deployments, n_laps, duration_laps, n_durations, source: Literal[...] / is_prior_only: bool)`. Floats and ints only (no ndarrays) so the scramble comparator `_compare` matches exactly.

**Input type:** `History` from `f1si.data._snapshot` (re-exported by `f1si.data.asof`); fields `races, entries, laps, track_status, race_control, weather, lap_cutoffs, results` (`_snapshot.py` lines 115-127). Take `History`, never `AsOfAccessor`. Type-only import is fine: `from f1si.data.asof import History`. Must not name `AsOfAccessor`, `RACE_END`, `RaceEnd` (test `test_only_the_drivers_name_the_accessor_in_src`).

**Edge rule** (RESEARCH Pattern 4 / code example) - copy verbatim, applied per race after sorting by `["t_s", "seq"]`:
```python
prev = None
for status in ts.sort_values(["t_s", "seq"])["status"]:
    if status == "4" and prev in (None, "1", "2", "6", "7"):
        deployments += 1
    prev = status
```
Exposure laps: `lap_cutoffs.groupby("race_id")["lap"].max()` summed over races that have track-status rows. Duration: leader laps between deployment and next status != "4" using `count(cutoff_s <= t) - 1`; exclude red-flag ends and never-ending SCs; median if >= 5 events else 4. Empty history (Bahrain 2023, `history.races == []`) returns the prior (`Beta(3, 297)`) with the prior-only flag; handle empty DataFrames without raising (scramble consumer runs at every cutoff).

**Beta interval:** `scipy.stats.beta.ppf([0.05, 0.95], a, b)`.

**Registry:** a new public function in a designated module needs a consumer (see `tests/guards/consumers.py` section).

---

### `src/f1si/interfaces.py` (modify: `SimulationResult`)

**Analog:** itself, lines 110-119.
```python
@dataclass(frozen=True, eq=False)
class SimulationResult:
    finish_positions: NDArray[np.int64]
    total_time_s: NDArray[np.float64]
```
Add new fields AFTER these two with defaults (`None`), keep `eq=False`, do not reorder or rename (module docstring lines 21-22 forbids changing the two). Needed because `NoisySimulator` builds it with keywords (registry.py 105) and stubs may slice both fields positionally (RESEARCH Pitfall 9). New fields (D-19): `sc_lap_mask: NDArray[np.bool_] | None`, `stop_laps`, `pit_loss_paid_s`, `plan_sources`/diagnostics. Docstring must update the "provisional" note.

---

### `src/f1si/state.py` (modify: regime, SC pit loss, optional fields)

**Analog:** itself. Optional-key precedent (state.py 65-81, 359):
```python
_OPTIONAL_CAR_KEYS: Final = ("laps_done",)
...
laps_done=raw.get("laps_done"),
```
`_check_keys("RaceState JSON car", raw, _CAR_KEYS, optional=_OPTIONAL_CAR_KEYS)` (state.py 341, 388-399).

For `CarState.pace_offset_sd: float | None = None`: append to `_CAR_KEYS` and `_OPTIONAL_CAR_KEYS`, add to `_OPTIONAL_FLOATS` (line 82-88) so `__post_init__` runs `_check_float`, add to `to_json_dict` (lines 300-315), `from_json_dict` (`raw.get(...)`), and `CarArrays`/`to_arrays` if the simulator needs it. Update the `CAR_KEYS` pin in `tests/test_state.py`.

For `RaceState.sc_laps_elapsed: int = 0` (Pitfall 6, optional): add to `_STATE_KEYS` as optional, validate with `_check_int` >= 0 in `__post_init__` (state.py 219-241), and serialize.

**Builder change** (`build_race_state`, lines 424-543): currently
```python
regime={"green": 1.0},
pit_loss_s={"green": pit_loss_s},
```
Change to: read `snapshot.track_status` (a DataFrame with `status` and `t_s`; as-of filtered by the door) and decide whether status "4" is the latest at the cutoff; set `regime={"sc": 1.0}` if so; `pit_loss_s={"green": pit_loss_s, "sc": pit_loss_s * SC_PIT_RATIO}` (placeholder; docstring lines 34-38 must be rewritten to say the SC key is a documented placeholder until Phase 8). The SC ratio constant lives where `state.py` can import it without a cycle: put `SC_PIT_RATIO` in `f1si/sim/constants.py` only if `f1si.sim` does not import `f1si.state` at import time, otherwise define it in `state.py`. Prefer the latter (interfaces.py/state.py cycle precedent, DEC-061).

Also add wear SE for other compounds? No: pass `wear_sd_by_compound` to the simulator constructor built from `fit.wear_se` (RESEARCH Pattern 5). `pace_offset_sd` comes from the new `fit.pace_offset_se(number)`.

**Tests to update (Pitfall 7):** `tests/test_state_builder.py` asserts `dict(state.regime) == {"green": 1.0}` and `set(state.pit_loss_s) == {"green"}`; `tests/guards/consumers.py::race_state` (lines 74-88) exercises the builder under scramble and stays green because the SC read uses only the snapshot.

---

### `src/f1si/pace/linear.py` (modify: offset SE)

**Analog:** `LinearPaceFit.wear_se` and `pace_offset` (lines 160-175).
```python
def wear_se(self, compound: str) -> float | None:
    """Standard error of the wear rate; this fills `RaceState` `wear_sd` (D-04)."""
    for c in self.report.compounds:
        if c.compound == compound:
            return c.se
    return None
```
Add `FitReport.driver_offset_se: Mapping[int, float] = field(default_factory=dict)` AFTER existing fields (line 110-116 shows `driver_offsets: Mapping[int, float]` is already set at construction in `fit_linear_pace` line 527 and in `_unidentified` line 233, where `driver_offsets={}`); fill from `se[:nd]` at line 527; add `LinearPaceFit.pace_offset_se(driver_number) -> float | None` and register it in `EXEMPT` ("pure lookup of already fitted values", same wording as `wear_se` in consumers.py line 148). Because `f1si.pace.linear` is a designated module, an unregistered new public method fails `test_consumer_registry.py`.

---

### `src/f1si/synthetic/generator.py` (modify: optional SC spec)

**Analog:** the VSC machinery in the same file.

Spec fields (lines 73-74):
```python
vsc_laps: tuple[int, ...] = ()
vsc_slowdown_factor: float = 1.4
```
Add `sc_laps: tuple[int, ...] = ()` (deployment laps) and `sc_duration_laps: int = 4` with defaults that leave every existing fixture byte-identical. Add `sc_laps` to `SyntheticTruth` with a default (line 89-99 shows required fields; truth is built at line ~345 `vsc_laps=spec.vsc_laps`, so supply it there).

Event emission - copy `_vsc_events` (lines 126-138) and add `_sc_events` emitting `(deployed, "4", "SAFETY CAR DEPLOYED")` and `(ending, "1", "TRACK CLEAR")`; merge with VSC events and sort by time in `_track_status_table` (lines 141-147; note `seq` is `enumerate(..., start=1)` over the merged sorted list). In `_race_control_table` (line 173-177) mirror the `SafetyCar` category row for the SC deployed message.
```python
deployed = float(on_lap["lap_start_s"].min()) + 1.0
ending = float(on_lap["lap_end_s"].max()) - 1.0
events.append((deployed, "6", "VIRTUAL SAFETY CAR DEPLOYED"))
```
Lap-time effect (line 297-298): `if lap in spec.vsc_laps: time_s *= spec.vsc_slowdown_factor`; add an analogous `if lap in sc_lap_set: time_s *= SC_SLOWDOWN`. Do NOT draw extra random numbers from `rng` when `sc_laps == ()` (stream must stay identical). Recovery test (D-06) draws its own Bernoulli SC laps in the test, per RESEARCH Wave 0 ("generator stream unchanged").

---

### `src/f1si/plots/simulate.py` (plot component, file-I/O)

**Analog:** `src/f1si/plots/wear.py` - copy the prepare / build / render / file-name split exactly.

**Imports** (wear.py 16-33):
```python
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
```
Reuse `EDGE_COLOR` from `f1si.plots.stints`; no `pyplot` (checked by `test_no_pyplot_in_src` across all of `src`).

**Data object** (wear.py 40-50): `@dataclass(frozen=True, eq=False) class SimPlotData` with `title, slug, driver, lap, probabilities (tuple/array of P1..Pn), mean, median, interval, caption`. Pure `prepare_sim_plot_data(result_column, ...)`: it takes arrays, not a snapshot, so it is not a designated module function.

**Figure** (wear.py 128-131, 191-193): `fig = Figure(figsize=..., layout="constrained")`, `ax = fig.subplots(...)`, `fig.suptitle(data.title)`, `fig.supxlabel(data.caption, fontsize=6, wrap=True)`; bars via `ax.bar(positions, probs, color=..., edgecolor=EDGE_COLOR)`.

**Render and file name** (wear.py 196-211):
```python
def render_wear_plot(data: WearPlotData, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    build_wear_figure(data).savefig(out_path, dpi=120)
    return out_path

def wear_file_name(slug: str) -> str:
    if not _SLUG.match(slug):
        raise ValueError(f"Unsafe race slug for a file name: {slug!r}")
    return f"wear-{slug}.png"
```
`sim_file_name(slug, driver, lap)` must validate `_SLUG = ^[a-z0-9-]+$`, driver `^[A-Z]{3}$`, `lap` int >= 0, and return `f"sim-{slug}-{driver}-lap{lap}.png"` (D-16; V12 in RESEARCH Security).

**Registry:** `build_*_figure`, `render_*`, `*_file_name` are EXEMPT only if `f1si.plots.simulate` is added to `DESIGNATED_MODULES`; because it takes no snapshot, simplest is to leave it OUT of `DESIGNATED_MODULES` (as `laps.py` precedent, 02-PATTERNS planner note).

---

### `src/f1si/cli.py` (modify: `simulate` subcommand)

**Analog:** `_cmd_plan` (lines 393-460) and `_cmd_wear` (218-303); `main` dispatch (531-574).

**Subparser** (lines 122-137, copy shape):
```python
plan = sub.add_parser("plan", help="fastest free-track 1- and 2-stop pit plans for one driver")
plan.add_argument("slug", metavar="SLUG", help="race slug (for example bahrain-2023)")
plan.add_argument("--driver", default=None, metavar="CODE", help="driver code, for example ALO ...")
plan.add_argument("--lap", type=int, default=None, metavar="N", help="... (default: hindsight plan using the whole race)")
```
Add `simulate` with `slug`, `--driver` (required per D-16), `--lap`, `--n` (`type=int`, default 50000), `--seed` (`type=int`, default `DEFAULT_SEED` or 0 per D-16 `--seed 0`; `DEFAULT_SEED` is imported already at line 42).

**Core flow to copy from `_cmd_plan`** (lines 393-431): `resolve_slug`, validate `--lap < 0` with `_refuse(... Try: uv run f1si simulate SLUG ...)`, `accessor.snapshot(AsOf(race_id, RACE_END))` to get `laps_total = int(end.laps["lap_number"].max())` (the CLI is the replay driver), hindsight branch (`lap is None`: fit on `end`, state from `AsOf(race_id, 0)`) vs `--lap N` branch, `OutOfSampleLockedError` -> `_refuse(f"{err} 2026 races are out-of-sample, ...")`, `fit_linear_pace`, refusal text when `not fit.is_identified` (copy lines 422-428 wording and "try --lap" hint), `measure_pit_loss`, `build_race_state(...)`, `_pick_driver(...)` for `--driver` validation (reuses `UnknownDriverError`).
```python
fit = fit_linear_pace(fit_snapshot)
if not fit.is_identified:
    retry = 20 if lap is None or lap < 10 else lap + 10
    ...
    return _refuse(f"Cannot plan: not enough laps yet to fit wear {shown} ({fit.report.message}); try --lap {retry}. ...")
```
**SC rate:** `history = accessor.history(asof.AsOf(race_id, lap or 0))` then `estimate_sc_rate(history)`. The CLI is the only module allowed to name the accessor. Print `"prior only: no earlier races"` when `is_prior_only`.

**`--n` bound** (RESEARCH V5): check `2 <= n <= 1_000_000` and `_refuse(...)` with a Try line.

**Output:** reuse `_print_table`, `_fmt_time`, `_HINDSIGHT_LABEL`-style constant (lines 306-323); label the no-`--lap` run "hindsight simulation". Time the simulate call with `time.perf_counter()` and print runtime. Write the PNG with `reports_dir / sim_file_name(race.slug, code, state.lap)`; the reports dir resolution is the `args.reports_dir if ... else paths.reports_dir()` idiom at lines 537-539.

**Dispatch edits (gotchas):**
- `_FRIENDLY_VALUE_ERRORS = frozenset({"plot", "wear", "plan"})` (line 46) -> add `"simulate"` so `ValueError` becomes a printed message and exit 1 (main lines 565-569).
- Add `if args.command == "simulate":` branch before the final `return _cmd_races(data_dir)` (line 550).
- Update the module docstring (lines 1-6).
- Imports are alphabetical one-per-module (ruff `I`).

---

### `tests/conformance/registry.py` (modify: register the simulator)

**Analog:** `_free_track` (lines 143-155) + `_noisy_simulator` (158-159) + `SIMULATORS` (170-172).
```python
def _free_track(long_db: Path) -> tuple[StrategyPolicy, PolicyCase]:
    accessor = AsOfAccessor(long_db)
    end = accessor.snapshot(AsOf("2023-01", RACE_END))
    fit = fit_linear_pace(end)
    pit = measure_pit_loss(end, fit)
    state = build_race_state(
        accessor.snapshot(AsOf("2023-01", 0)), fit, laps_total=57, pit_loss_s=pit.median_s
    )
    ...
SIMULATORS: Final[dict[str, Callable[[Path], tuple[SimulatorBackend, SimCase]]]] = {
    "noisy_simulator": _noisy_simulator,
}
```
Add `_numpy_sim(long_db)` building the same lap-0 state, a `NumpySimulator(fit, sc=SafetyCarModel(...), ...)`, `SimCase(state, 64)`; entry `"numpy_sim": _numpy_sim`. Keep `NoisySimulator` returning the extended `SimulationResult` (new fields default None, so it needs no change unless you want diagnostics). Check `tests/conformance/stubs.py` (`WrongShapeSim` slices both fields) and run mypy on it.

---

### `tests/guards/consumers.py` (modify)

**Analog:** itself. Add a consumer in the style of `pit_loss` (lines 68-71):
```python
def pit_loss(db_path: Path, at: AsOf) -> object:
    snapshot = AsOfAccessor(db_path).snapshot(at)
    return measure_pit_loss(snapshot, fit_linear_pace(snapshot))
```
->
```python
def sc_rate(db_path: Path, at: AsOf) -> object:
    """The safety-car rate and duration estimated from earlier races only."""
    return estimate_sc_rate(AsOfAccessor(db_path).history(at))
```
Then: `CONSUMERS["sc_rate"] = sc_rate`; `DESIGNATED_MODULES += ("f1si.regime.sc_rate",)`; `CONSUMED["f1si.regime.sc_rate.estimate_sc_rate"] = "sc_rate"`; any other public function in that module goes in `EXEMPT` with >= 4 words of reason (e.g. `"pure math of counts, reads no race data"`). Also add `EXEMPT["f1si.pace.linear.LinearPaceFit.pace_offset_se"]`. If `build_race_state` now reads `track_status`, the existing `race_state` consumer covers it. Pitfall 10: the scramble tests use the 4-race synthetic db whose earlier race has a VSC but no SC; register a case whose earlier races contain `sc_laps` (new fixture in conftest).

---

### `tests/conftest.py` (modify: SC history fixture)

**Analog:** `long_specs` / `build_long_db` / `long_synthetic_*` (lines 45-82).
```python
def long_specs() -> tuple[SyntheticRaceSpec, ...]:
    return (SyntheticRaceSpec(2023, 1, "Long Grand Prix", n_drivers=20, n_laps=57, start_tyre_age=3),)

def build_long_db(folder: Path, seed: int) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    load_races(SyntheticSource(long_specs(), rng=make_rng(seed)), paths.db_path(folder), (2023,),
               now=datetime(2026, 10, 22, tzinfo=UTC), echo=lambda _line: None)
    return paths.db_path(folder)
```
Add `sc_history_specs()` (several races with `sc_laps`, plus a final "current" race) and a session fixture `sc_history_db` built the same way via `SyntheticSource(specs, rng=...)`. Do not change `long_specs()` (all Phase 2 tests and the benchmark state depend on it).

---

### `tests/test_cli_simulate.py` (test, request-response)

**Analog:** `tests/test_cli_wear_plan.py` (lines 1-70).
```python
def _run(data_dir: Path, tmp_path: Path, *args: str) -> int:
    return main(["--data-dir", str(data_dir), "--reports-dir", str(tmp_path), *args])

def test_wear_prints_the_table(long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "wear", LONG_SLUG) == 0
    out = capsys.readouterr().out
    for needle in (...):
        assert needle in out, needle
```
Cases: success (needles: "prior only: no earlier races", "hindsight simulation", "P1", runtime, PNG exists), `--lap 20` refusal (`== 1`, "Try: uv run f1si simulate long-2023"), negative lap, unknown driver, bad `--n`, unknown slug (`err.strip()` non-empty). Use `LONG_SLUG`, `long_synthetic_data_dir`; small `--n` (e.g. 200) for speed.

---

### `tests/plots/test_simulate_plot.py`, `tests/real/test_simulate_bahrain.py`

**Analogs:** `tests/plots/test_wear_plot.py` (prepared-data asserts, file name safety via `wear_file_name`, subprocess no-pyplot check: lines 1-50 and the rest of the file; copy the `subprocess.run([sys.executable, "-c", ...])` import test) and `tests/real/test_wear_bahrain.py` (opt-in `network` marker, skip when cache/race absent; open it before copying the skip pattern). Pyproject has `-m "not network"` and `--strict-markers`.

---

### `tests/sim/*` and `tests/regime/test_sc_rate.py`

**Analogs:**
- State from a long synthetic db: `tests/test_state_builder.py` lines 17-40 (`_snap`, `fit_linear_pace`, `build_race_state(..., laps_total=57, pit_loss_s=22.0)`).
- Recovery with known truth: `tests/pace/test_linear_recovery.py`; compare to `long_synthetic_truth` fixture (`tests/conftest.py` 79-82).
- Hand-calculated expectation: `price_plan_slow` (free_track.py 54-82) for a no-noise, SC-free two-car state; test file `tests/strategy/test_free_track_laps_done.py` is the analog for the `laps_done` 20/19 catch-up case.
- Reproducibility: use `make_rng(seed)` (not `np.random.default_rng`) per `tests/conftest.py` imports.
- Package files: each new test dir needs `__init__.py` (existing `tests/pace/__init__.py`, `tests/strategy/__init__.py`).
- Conformance-style assertions with defect keywords: `tests/conformance/suites.py` assertion messages ("shape:", "permutation:", "reproducible:").

**Benchmark** (RESEARCH "Benchmark test"): warm-up `simulate(n_races=64)` then `time.perf_counter()` around `n_races=50_000`; assert `< 10.0`; build state like `registry._free_track`. Docstring states warm-up exclusion (D-18).

---

### `tests/test_docs.py`, `tests/test_decisions_log.py`, `DECISIONS.md`, `docs/explained/phase-03.md`, `README.md`

**Analogs:** the Phase 2 versions (pattern recorded in 02-PATTERNS).
- `tests/test_decisions_log.py` line 44: `MIN_ENTRIES = 73` -> `73 + number of new DECs` (next free DEC-074); consecutive numbering enforced.
- DEC entry format (em dash heading, 8 bold labels): `## DEC-074 — <title>` with `**Date:** **Status:** **Context:** **Decision:** **Why:** **Alternatives rejected:** **Consequences:** **Refs:**`.
- `tests/test_docs.py` has `PHASE2 = ROOT / "docs" / "explained" / "phase-02.md"` (line 11) and README needles at lines 83-86 (`"uv run f1si wear bahrain-2023"`, `"docs/explained/phase-02.md"`). Add `PHASE3`, needles `"uv run f1si simulate bahrain-2023"`, `"docs/explained/phase-03.md"`, and require every new `src/f1si/**/*.py` module (`sim/numpy_backend.py`, `sim/kernel.py`, `sim/draws.py`, `sim/plans.py`, `sim/constants.py`, `regime/sc_rate.py`, `plots/simulate.py`) to appear in the `## File-by-file tour` of phase-03.md (test globs `src/f1si/**/*.py`, skipping `__init__.py`).
- DECs owed (from CONTEXT/RESEARCH): SC rate Beta-Binomial + prior; edge rule for deployments; SC fixed duration/fallback 4 (note measured median 3); SC effects (freeze, 1.4, restart 1.0 s, pit ratio 0.5 placeholder); regime at cutoff / `sc_laps_elapsed`; overtaking model and constants; no lapping/DNF; plan resolution and fallback; opportunistic SC stops; parameter sampling (shared per-compound wear draw refines D-12; offsets via `driver_offset_se`; independence caveat); borrow rule for unfitted compounds/drivers; Sobol + antithetic layout and CRN; odd-N pad-and-trim; Numba kernel (D-18) and scipy/numba/scipy-stubs deps; VR test design and measured ratios.

---

## Shared Patterns

### Plain-data inputs only (look-ahead rule)
**Source:** `tests/guards/test_consumer_registry.py` (access allowed only to `f1si.cli`, `f1si.data.asof`, `f1si.data._snapshot`); `src/f1si/state.py` docstring lines 18-21.
**Apply to:** `sim/*`, `regime/sc_rate.py`, `plots/simulate.py`, `state.py`.
Model code receives `RaceState`, `History` or `RaceSnapshot`, never `AsOfAccessor`/`RACE_END`/`RaceEnd`. The CLI reads `laps_total`, `history`, and snapshots, and passes plain data in.

### Explicit rng, spawn only
**Source:** `src/f1si/rng.py` lines 6-30; `interfaces.py` lines 158-165.
**Apply to:** `sim/numpy_backend.py`, `sim/draws.py`, every test.
```python
sc_params, passing, noise, _spare = rng.spawn(4)
```
Only `f1si.rng.make_rng` may call `default_rng`; `np.random.seed`/`RandomState`/global `np.random` banned (ruff NPY002 + import scan). `Sobol(..., rng=child)` not `seed=`.

### Errors that say what to do next
**Source:** `cli.py` lines 218-241, 393-428, 388-390 (`_refuse`), 565-574 (main handlers).
**Apply to:** `cli.py simulate`, `sim` validation errors, `regime/sc_rate.py`.
Library raises `ValueError` (or subclass) quoting the bad value; CLI prints `str(err)` to stderr, returns 1, ends with `Try: uv run f1si simulate SLUG --driver CODE --lap N`.

### Frozen dataclasses with plain values
**Source:** `state.py` 111-162, `pace/linear.py` 86-130, `interfaces.py` 43-119.
**Apply to:** `ScRateEstimate`, `SafetyCarModel`, simulator diagnostics, `SimPlotData`.
`@dataclass(frozen=True)` (default `eq` when fields are scalars/tuples); `eq=False` when a field is an ndarray/DataFrame; validate in `__post_init__` with `ValueError(f"... got {x!r}")`; floats checked finite.

### Docstrings state the math; module docstring explains conventions
**Source:** `interfaces.py` lines 1-26, `state.py` lines 1-45, `plots/wear.py` lines 1-14.
**Apply to:** every new module. For the simulator: the lap-time model, the pass probability `p = logistic((delta - threshold_s)/scale_s)`, SC mechanics, which values are documented placeholders, the CRN layout, the Sobol dimension budget.

### Registered consumers, enforced
**Source:** `tests/guards/consumers.py` 97-157 and `tests/guards/test_consumer_registry.py`.
**Apply to:** `regime/sc_rate.py`, `pace/linear.py` new method, `state.py` changes.
Every public function / public method in a `DESIGNATED_MODULES` module is `CONSUMED` (consumer's `co_names` contains its name) or `EXEMPT` (reason >= 4 words); stale entries fail.

### Typing and lint
**Source:** `pyproject.toml` (ruff `E,W,F,I,B,UP,NPY,RUF,SIM,PT,N`, line length 100, mypy strict over `src` and `tests`).
**Apply to:** all new files. Avoid single-letter uppercase variable names (N806); `zip(..., strict=True)`; `Final` constants; `from __future__ import annotations` in modules with forward refs; `scipy-stubs` needed for mypy; locally run `uv run python -m mypy` / `uv run python -m f1si`.

### Docs and DECISIONS gate
**Source:** `tests/test_docs.py`, `tests/test_decisions_log.py`.
**Apply to:** every task that creates a `src/f1si` module (tour entry in the same task), every method choice (DEC entry, bump `MIN_ENTRIES`).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/f1si/sim/kernel.py` (`@njit` lap step) | utility | sequential per-race loop | No numba code exists; use RESEARCH Pattern 1 and the `py_func` equivalence test. `price_plan_slow` is only a style analog for a plain-Python oracle. |
| Sobol/antithetic generation in `sim/draws.py` | utility | transform | No QMC code or scipy usage exists yet (scipy not in `pyproject.toml`); use RESEARCH Pattern 3 and the code in "Spawned, plan-independent streams". |
| `tests/sim/test_variance_reduction.py` | test | statistical, multi-seed | No multi-seed variance-ratio test exists; use RESEARCH "D-14 test design" (R >= 100 seeds, N = 1024, `variance_reduction` switch, assert ratio >= 1.15 on mean finish, >= 2.0 on SC share, P(top 5) report-only). |
| Overtaking/pass model and SC mechanics inside the kernel | service | sequential | No traffic or race-flow simulation exists; free-track code ignores traffic by design. Use CONTEXT D-04/D-07 and RESEARCH constants. |

## Metadata

**Analog search scope:** `src/f1si/**` (35 files), `tests/**` (66 files), `.planning/phases/02-*/02-PATTERNS.md`
**Files read:** `interfaces.py`, `state.py`, `cli.py`, `plots/wear.py`, `strategy/free_track.py` (lines 40-150), `pace/linear.py` (lines 85-215), `synthetic/generator.py` (lines 50-180), `data/_snapshot.py` (History, 112-137), `rng.py`, `tests/conformance/{registry,suites}.py`, `tests/guards/consumers.py`, `tests/conftest.py`, `tests/test_cli_wear_plan.py` (1-70), `tests/test_state_builder.py` (1-60), `tests/plots/test_wear_plot.py` (1-50)
**Not read (open before copying):** `tests/conformance/stubs.py`, `tests/test_state.py`, `tests/real/test_wear_bahrain.py`, `tests/pace/test_linear_recovery.py`, `tests/strategy/test_free_track_laps_done.py`, `src/f1si/data/asof.py` (confirm `History` re-export)
**Pattern extraction date:** 2026-11-12
