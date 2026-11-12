# Phase 4: Kalman Tire Filter - Pattern Map

**Mapped:** 2026-11-12
**Files analyzed:** 20 (7 new source/test-support modules, 6 modified source files, 7+ test files)
**Analogs found:** 19 / 20 (the Kalman math itself has no in-repo analog; use RESEARCH.md Pattern 1)

Line numbers refer to the repo at commit cc4a949. Run locally with `uv run python -m ...` (Windows blocks uv shims).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/f1si/pace/kalman.py` (NEW: `WearFilter`, priors resolver, snapshot adapter, result dataclasses) | model/service | transform (incremental + batch), snapshot-in | `src/f1si/pace/linear.py` (dataclasses, constants, snapshot-only, `CI_Z`, `_classify`) | role-match |
| `src/f1si/plots/wear_filter.py` (NEW: prepare / build / render / file name) | utility (plot) | transform | `src/f1si/plots/wear.py` | exact |
| `src/f1si/cli.py` (MOD: `wear-filter` subparser, `_cmd_wear_filter`, `main` dispatch, `_FRIENDLY_VALUE_ERRORS`) | controller (CLI) | request-response | `_cmd_wear` (l.260-345) + `_cmd_simulate` (l.585+) | exact |
| `src/f1si/state.py` (MOD: `CarState.wear_source`, `_CAR_KEYS`, JSON, `build_race_state(wear_filter=)`) | model | CRUD / serialization | same file: `laps_done`, `pace_offset_sd`, `sc_laps_elapsed` additions | exact |
| `src/f1si/sim/numpy_backend.py` (MOD: virtual compound columns) | service | batch / streaming draws | same file, `simulate` l.155-290 | exact (self) |
| `src/f1si/sim/draws.py` (MOD: `car_wear_stream` helper, no `make_streams` change) | utility | event-driven RNG | same file: `make_streams`, `normal_block` | exact (self) |
| `src/f1si/synthetic/generator.py` (MOD: per-driver wear deviation, truth fields) | service | transform | same file: Phase 3 `sc_laps` additions (defaulted fields) | exact (self) |
| `tests/guards/consumers.py` (MOD: `wear_filter` consumer, DESIGNATED_MODULES, CONSUMED, EXEMPT) | test-support | request-response | same file: `wear_plot_data`, `sc_rate` | exact |
| `tests/pace/test_kalman_math.py`, `_incremental.py`, `_narrowing.py`, `_gate.py` (NEW) | test | unit / property | `tests/pace/test_linear_recovery.py`, `tests/pace/test_clean_laps.py` | role-match |
| `tests/pace/test_kalman_recovery.py` (NEW: coverage, closed form, accuracy report) | test | statistical recovery | `tests/pace/test_linear_recovery.py` (coverage over seeds) | role-match |
| `tests/sim/test_filter_cars.py` (NEW) | test | unit | `tests/sim/test_crn_and_plans.py`, `tests/sim/test_reproducibility.py`, `tests/sim/conftest.py` (`hand_state`, `ZeroNoisePace`) | role-match |
| `tests/test_cli_wear_filter.py` (NEW) | test | CLI | `tests/test_cli_simulate.py`, `tests/test_cli_wear_plan.py` | exact |
| `tests/plots/test_wear_filter_plot.py` (NEW) | test | file-I/O | `tests/plots/test_wear_plot.py` | exact |
| `tests/real/test_wear_filter_bahrain.py` (NEW) | test | real-data | `tests/real/test_wear_bahrain.py` | exact |
| `tests/test_state.py`, `tests/test_state_builder.py`, `tests/test_synthetic.py` (MOD) | test | unit | themselves | exact (self) |
| `tests/test_docs.py`, `tests/test_decisions_log.py` (MOD: needles, `MIN_ENTRIES` 87 -> 87+n) | test | docs | themselves | exact (self) |
| `docs/explained/phase-04.md` (NEW) | docs | n/a | `docs/explained/phase-03.md` | exact |
| `DECISIONS.md` (MOD: DEC-088..094) | docs | n/a | DEC-086/087 entries | exact |
| `README.md` (MOD: `f1si wear-filter` needles) | docs | n/a | existing `uv run f1si simulate bahrain-2023` lines (test_docs.py l.79-97) | exact |
| Kalman recursion (Joseph form, 3-state) | math | transform | none in repo | NO ANALOG |

## Pattern Assignments

### `src/f1si/pace/kalman.py` (model/service, transform)

**Analog:** `src/f1si/pace/linear.py` (structure, constants, docstring style, snapshot-only discipline).

**Module docstring convention** (linear.py l.1-55): starts with a one-line purpose plus requirement and decision IDs, states the math in an indented block, then "Honesty rules", and ends with the sentence "The module sees only a `RaceSnapshot` (plain data), so at lap N it uses only laps visible at N." Copy this shape and put predict / update / gain / Joseph equations in the docstring (D-04), plus the closed form `Var_post = tau^2 - tau^4 / (tau^2 + sf^2 + sigma^2/Sxx)`.

**Imports pattern** (linear.py l.57-71):
```python
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from f1si.data.asof import RaceSnapshot
from f1si.interfaces import DRY_COMPOUNDS
from f1si.laps import fade_reason, slow_status
```
For kalman.py import `CI_Z`, `LinearPaceFit` from `f1si.pace.linear` (never a literal 1.96) and `fade_reason` from `f1si.laps`. Do NOT import `AsOfAccessor` (import scan allows it only in replay drivers and the CLI).

**Constants + frozen dataclasses** (linear.py l.73-131): module-level `Final` constants (`CI_Z: Final = 1.96`, `MAD_K`, ...), then `@dataclass(frozen=True)` result types holding plain Python values. Put the generic priors (SOFT 0.10, MEDIUM 0.08, HARD 0.06 rate mean, SD 0.05; fuel -0.05 +/- 0.025; sigma 0.30; `TAU_CAR = 0.03`; gate 3.0 SD from the 3rd used lap, never two rejections in a row) as `Final` constants, each commented `[ASSUMED]` with its DEC number.

**Clean-lap rule to reuse, not re-implement** (linear.py `_classify` l.253-290):
```python
reason = fade_reason(int(lap_no[i]), bool(pit_in[i]), bool(pit_out[i]), status[i])
if reason is None:
    if compound[i] is None or np.isnan(age[i]):
        reason = "no compound or tyre age"
    elif np.isnan(stint[i]):
        reason = "no stint"
    elif compound[i] not in DRY_COMPOUNDS:
        reason = "wet compound"
```
`_classify` is private to linear.py; either import it (same package, acceptable) or copy the column extraction idiom (`laps["lap_time_s"].astype("Float64").to_numpy(dtype=np.float64, na_value=np.nan)`, `laps["is_pit_in_lap"].fillna(False).astype(bool).to_numpy()`). Keep `fade_reason` as the single clean-lap definition (D-08).

**Priors source (as-of fit accessors)** (linear.py l.139-166): `fit.is_identified`, `fit.fitted_compounds`, `fit.fuel_effect`, `fit.wear_rate(c)`, `fit.wear_se(c)`, `fit.report.sigma_s`, `fit.report.fuel_se`. D-19 condition: use the fit only when `report.fuel_s_per_lap is not None` and compound in `fit.fitted_compounds`; prior SD = `sqrt(se**2 + TAU_CAR**2)`; label "prior only" otherwise (same wording idea as `_sc_source`, cli.py l.579-582).

**Public API shape (planner decision, from RESEARCH):** pure-array class `WearFilter` (reset per stint, `update(...)` incremental, batch helper) plus one snapshot adapter, for example `filter_stints(snapshot, fit) -> ...`, which is the only function that reads a snapshot and is the one registered as a consumer.

**Core Joseph-form update (no in-repo analog; copy from RESEARCH.md Pattern 1):**
```python
def update(x, P, h, y, r):            # h: (3,), r = sigma**2
    s = h @ P @ h + r
    k = P @ h / s
    innov = y - h @ x
    x = x + k * innov
    a = np.eye(3) - np.outer(k, h)
    P = a @ P @ a.T + r * np.outer(k, k)
    return x, 0.5 * (P + P.T), innov, s
```
Validate finite inputs and `q`, sigma, SDs > 0 with `raise ValueError(...)` in the style of `CarState._check_float` (state.py l.110). Reported SD = `sqrt(P[1,1])`, interval = `rate +/- CI_Z * sd`.

---

### `src/f1si/plots/wear_filter.py` (utility, transform)

**Analog:** `src/f1si/plots/wear.py` (exact; the CONTEXT says copy it).

**Imports** (wear.py l.16-33): `from __future__ import annotations`, `re`, `Mapping`, `dataclass`, `Path`, `Final`, `matplotlib`, `numpy`, `pandas`, `from matplotlib.figure import Figure`, then `COMPOUND_COLORS, EDGE_COLOR, UNKNOWN_COLOR` from `f1si.plots.stints`, `CI_Z` from `f1si.pace.linear`. Never import `pyplot` (DEC-050; `tests/plots/test_wear_plot.py` checks this via a subprocess).

**Slug and data container** (wear.py l.35, 40-50):
```python
_SLUG = re.compile(r"^[a-z0-9-]+$")

@dataclass(frozen=True, eq=False)
class WearPlotData:
    """Everything the renderer needs, as plain data (no snapshot, no fit)."""
    title: str
    slug: str
    ...
```

**Three-function split** (wear.py l.57, 128, 196):
```python
def prepare_wear_plot_data(snapshot: RaceSnapshot, fit: LinearPaceFit) -> WearPlotData: ...
def build_wear_figure(data: WearPlotData) -> Figure: ...
def render_wear_plot(data: WearPlotData, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    build_wear_figure(data).savefig(out_path, dpi=120)
    return out_path
```
Name the new ones `prepare_wear_filter_data`, `build_wear_filter_figure`, `render_wear_filter_plot`, `wear_filter_file_name`.

**Figure idioms** (wear.py l.131-132, 168-174, 190-192): `Figure(figsize=..., layout="constrained")`, `fig.subplots(...)`, `ax.fill_between(x, low, high, color=colour, alpha=0.35, zorder=2)`, dashed dark edge lines so a pale HARD band stays visible (`ax.plot(..., color=EDGE_COLOR, linewidth=0.7, linestyle="--")`), `fig.suptitle(data.title)`, `fig.supxlabel(data.caption, fontsize=6, wrap=True)`. Draw the Phase 2 hindsight compound rate as a dashed line labelled "hindsight"; draw stint boundaries as vertical lines (see `plots/stints.py` for stint-start handling).

**Title as-of vs full race** (wear.py l.60-63): `isinstance(snapshot.at.lap, int)` branch for "as of lap N" versus "full race".

**File name** (wear.py l.203-211):
```python
def wear_file_name(slug: str) -> str:
    if not _SLUG.match(slug):
        raise ValueError(f"Unsafe race slug for a file name: {slug!r}")
    return f"wear-{slug}.png"
```
New name: `wear-filter-<slug>-<DRV>.png`; also validate the driver code with `[A-Z]{3}` (`_DRIVER_CODE` in cli.py l.55).

---

### `src/f1si/cli.py` (controller, request-response)

**Analog:** `_cmd_wear` (l.260-345), `_cmd_simulate` (l.585-724), `main` (l.727-777).

**Subparser pattern** (l.118-129 for `wear`; l.146-179 for `simulate` with `--driver` required):
```python
wear = sub.add_parser("wear", help="fitted tyre wear (s/lap per compound), fuel effect and pit loss")
wear.add_argument("slug", metavar="SLUG", help="race slug (for example bahrain-2023)")
wear.add_argument("--lap", type=int, default=None, metavar="N", help="use only laps visible after the leader's lap N ...")
```
`wear-filter` takes `slug`, `--driver` (`required=True`, "driver code, for example ALO (any case)"), `--lap`.

**Command body pattern** (l.260-285): resolve slug, validate `--lap`, build `AsOf`, catch `OutOfSampleLockedError`, print to stderr and return 1:
```python
db = paths.db_path(data_dir)
race_id = asof.resolve_slug(db, slug)
if lap is not None and lap < 0:
    print(f"--lap must be 0 or more, got {lap}. Try: uv run f1si wear {slug} --lap 20", file=sys.stderr)
    return 1
at = asof.AsOf(race_id, asof.RACE_END if lap is None else lap)
try:
    snapshot = asof.AsOfAccessor(db).snapshot(at)
except OutOfSampleLockedError as err:
    print(f"{err} 2026 races are out-of-sample, so they cannot be analysed in Phase 2.", file=sys.stderr)
    return 1
```
`_cmd_wear_filter` must hold the accessor only inside cli.py, pass `RaceSnapshot` to the filter adapter, and report "the filter at lap N sees only laps up to N" (D-15: replay as-of every lap up to N by building one snapshot per cutoff or, cheaper, one end snapshot is NOT allowed because the fit priors must be as-of; planner must take a snapshot per reported cutoff at least for the prior-reporting laps 14, 20, 30).

**Table printing** (l.311-313; `_print_table` l.368):
```python
widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(header)]
for line in (header, *rows):
    print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip())
```
Prefer calling `_print_table(header, rows)`.

**Driver lookup:** `_pick_driver` (l.412) and `_DRIVER_CODE` (l.55); reuse.

**Prior-only labelling** (l.579-582):
```python
def _sc_source(est: ScRateEstimate) -> str:
    if est.is_prior_only:
        return "prior only: no earlier races"
    return f"{est.n_deployments} earlier SC deployments ..."
```
Write analogous `_prior_source` strings for rate, fuel and noise per stint.

**Hindsight label constant** (l.348-350, `_HINDSIGHT_LABEL`): copy the style for a "hindsight" reference note.

**Output file** (l.342-344): `out = reports_dir / wear_file_name(race.slug)`; `render_wear_plot(...)`; `print(f"Wrote {out}. Open it to see ...")`.

**Dispatch + friendly errors** (l.54, 737-741, 768-772): add `"wear-filter"` to `_FRIENDLY_VALUE_ERRORS`; add an `if args.command == "wear-filter":` branch resolving `reports_dir` exactly like the `wear` branch. Note the sub-command name contains a hyphen; `args.command` equals `"wear-filter"`.

---

### `src/f1si/state.py` (model, serialization)

**Analog:** same file; mirror how `laps_done` / `pace_offset_sd` / `sc_laps_elapsed` were added as backward-compatible optional keys.

**Key tuples** (l.68-86): add `"wear_source"` to `_CAR_KEYS` AND `_OPTIONAL_CAR_KEYS` (`_check_keys` rejects unknown keys):
```python
_OPTIONAL_CAR_KEYS: Final = ("laps_done", "pace_offset_sd")   # + "wear_source"
```

**Dataclass field** (l.143-150): new trailing defaulted field `wear_source: str = "fit"` after `pace_offset_sd`; validate in `__post_init__` (l.151-173) in the same style:
```python
if self.laps_done is not None and _check_int("laps_done", self.laps_done) < 0:
    raise ValueError(f"laps_done must be >= 0 or None, got {self.laps_done!r}")
```
-> `if self.wear_source not in ("fit", "filter"): raise ValueError(...)`.

**JSON write only when non-default, to keep old JSON byte-stable** (l.334-335, the `sc_laps_elapsed` precedent):
```python
if self.sc_laps_elapsed:
    out["sc_laps_elapsed"] = self.sc_laps_elapsed
```
The car dict at l.307-333 is built in a comprehension; add the key conditionally (build dict then `if c.wear_source != "fit": d["wear_source"] = ...`). Read with `raw.get("wear_source", "fit")` as `laps_done=raw.get("laps_done")` does at l.377.

**Builder** (l.476-600): signature gets `wear_filter: Mapping[int, FilterSnapshot] | None = None` (keyword-only, after `pit_loss_s`). At l.583-584 the fit values are set:
```python
wear_rate_s_per_lap=None if name is None else fit.wear_rate(name),
wear_sd=None if name is None else fit.wear_se(name),
```
Replace per car with the filter's current-stint posterior (keyed by `r["number"]`) plus `wear_source="filter"`; otherwise unchanged. Keep `state.py` free of an import cycle: define the small `FilterSnapshot` type in `f1si.pace.kalman` (state already imports `f1si.pace.linear`), or accept a plain Mapping of (rate, sd) tuples.

---

### `src/f1si/sim/numpy_backend.py` and `src/f1si/sim/draws.py` (service, draws)

**Analog:** itself. Integration design is fixed in RESEARCH.md Pattern 4 (virtual compound columns; `kernel.py` untouched).

**Insertion points in `simulate`:**
- Compound index and `start_comp` (l.173-196): `comp_names = sorted(names)`; `start_comp[i] = index[car.compound.upper()]`. The virtual index `K + j` is appended AFTER these; keep a `real_name_of` mapping because `_start` (l.456+) calls `_mean_lap(pace, car, comp_names[int(start_comp[lead])], ...)` and `comp_names[int(comp[i])]` (l.486, 507).
- Tables (l.213-216): `mean_tab, sd_tab = self._tables(pace, numbers, comp_names, laps, max_age)`; `wear_sd = self._wear_sd_array(comp_names, diagnostics)` (shape `(n_comp,)`); extend these arrays by the virtual columns. `mean_tab` shape is `(len(laps), n_cars, n_comp, max_age)`.
- Draws (l.234-252):
```python
sc_params, passing, noise = make_streams(rng, d_sc)
n_draw = len(DRAW_COMPOUNDS)
block = uniform_block(self._mode, n_sim + n_cars + n_draw, n, sc_params)
...
z_wear = np.zeros((n, n_comp), dtype=np.float64)
for i, name in enumerate(comp_names):
    if name in DRAW_COMPOUNDS:
        z_wear[:, i] = z_slots[:, DRAW_COMPOUNDS.index(name)]
```
The new per-car stream: call `rng.spawn(1)[0]` AFTER `make_streams` and only if a filter car exists; `z_car = normal_block(self._mode, n_cars, n, car_stream)` (plain antithetic normals, never Sobol); copy `z_car[:, i]` into `z_wear[:, K+j]`. Put the spawn in a helper in `draws.py` next to `make_streams` (draws.py l.84-95):
```python
def make_streams(rng, n_laps):
    """Spawn (sc_params, one passing stream per lap, noise); a fourth child is kept spare."""
    sc_params, passing, noise, _spare = rng.spawn(4)
    return sc_params, passing.spawn(n_laps), noise
```
Do not edit `make_streams`. `normal_block` (draws.py l.76-82) is the draw primitive.
- Kernel call (l.277-289) passes `z_wear`, `wear_sd`; extended arrays flow through unchanged, so `kernel.py` and `tests/sim/test_kernel.py` stay untouched. `_check_kernel_inputs` (l.355) validates table shapes; run it on the extended arrays.
- Guard on `start.stops_done[i] == 0` so a car that pitted on the cutoff lap is not a filter car (l.261-263 shows how `stops_done` seeds `stop_taken`).

**Byte-identity guard (Wave 0, A5):** capture a hash of `finish_positions` and `total_time_s` for a fixed seed and state BEFORE editing `numpy_backend.py`; assert equal for fit-only runs afterwards. Tests: `tests/sim/test_reproducibility.py` and `tests/sim/conftest.py` (`hand_state`, `ZeroNoisePace`, `PIT`, `CODES`) show how to build deterministic states; use `dataclasses.replace(car, wear_rate_s_per_lap=..., wear_sd=..., wear_source="filter")` as `tests/sim/conftest.py` already imports `replace`.

---

### `src/f1si/synthetic/generator.py` (service, transform)

**Analog:** itself (Phase 3 added `sc_laps`, `sc_duration_laps`, `sc_slowdown_factor` as defaulted spec fields, `sc_laps` as defaulted truth field).

**Spec field** (l.62-88): add after the last field, defaulted:
```python
wear_rate_deviation_s_per_lap: Mapping[int, float] = field(default_factory=dict)  # keyed by driver index
```
(`field` and `Mapping` are already imported; `_default_wear` at l.57 shows the default-factory idiom.)

**Use in the lap-time model** (l.349): replace `wear[compound] * tyre_life` with `(wear[compound] + dev.get(i, 0.0)) * tyre_life` where `dev = spec.wear_rate_deviation_s_per_lap`. No new random draws: the noise block at l.300 (`rng.normal(0.0, spec.noise_sd_s, size=(spec.n_drivers, spec.n_laps))`) must stay first and unchanged so existing fixtures remain byte-identical.

**Truth field** (l.133-145): `SyntheticTruth` fields after `vsc_laps` are defaulted (`sc_laps: tuple[int, ...] = ()`); add `driver_wear_rate_s_per_lap: Mapping[int, Mapping[str, float]] = field(default_factory=dict)` last, filled at the constructor call (l.400-411) keyed by driver NUMBER (`10 + i`) to match `driver_pace_offset_s`, which is keyed by number.

**Stint geometry for tests needing stint lap 8+:** `pit_lap = spec.n_laps // 2 + (i % 2)` (l.~324), `tyre_life = lap - stops[0]` after the stop, `spec.start_tyre_age + lap` before. Use `n_laps >= 24`. The 1,000-stint recovery test should not build a DuckDB: simulate directly from the model equation or from `generate_race(...).race.tables["laps"]`.

---

### `tests/guards/consumers.py` (test-support, request-response)

**Analog:** same file, `wear_plot_data` (l.92-95) and `sc_rate` (l.98-100).

**Consumer pattern:**
```python
def wear_plot_data(db_path: Path, at: AsOf) -> object:
    """The wear plot's prepared data (points, lines, panels)."""
    snapshot = AsOfAccessor(db_path).snapshot(at)
    return prepare_wear_plot_data(snapshot, fit_linear_pace(snapshot))
```
Add `wear_filter(db_path, at)` that builds the snapshot, runs `fit_linear_pace`, calls the kalman snapshot adapter and `prepare_wear_filter_data`, and returns plain comparable data (dataclasses / lists). Then:
- add to `CONSUMERS` dict (l.103-115);
- add `"f1si.pace.kalman"` and `"f1si.plots.wear_filter"` to `DESIGNATED_MODULES` (l.124-131);
- add `CONSUMED` entries (l.134-148) for each public function the consumer calls, for example `"f1si.pace.kalman.<adapter>": "wear_filter"`, `"f1si.plots.wear_filter.prepare_wear_filter_data": "wear_filter"`, and `"f1si.state.build_race_state"` stays on `race_state` (consider extending `race_state` to also build with `wear_filter=` so the new argument is scrambled too);
- add `EXEMPT` entries (l.151-167) with a written reason for every pure-array public function / method (`WearFilter.update`, `reset`, closed-form helpers, `build_wear_filter_figure`, `render_wear_filter_plot`, `wear_filter_file_name`), phrased like `"f1si.plots.wear.build_wear_figure": "pure drawing of already-prepared WearPlotData"`.

`tests/guards/test_consumer_registry.py` fails if any public function/method in a DESIGNATED module is neither CONSUMED nor EXEMPT, so list every one.

---

### `tests/pace/test_kalman_*.py` (test, unit / statistical)

**Analog:** `tests/pace/test_linear_recovery.py` (coverage across seeds, fixture use) and `tests/conftest.py` (`LONG_RACE_ID`, `build_long_db`, `long_synthetic_db`, `long_synthetic_truth`).

**Header/imports idiom** (test_linear_recovery.py l.1-16): one-line docstring citing requirement and decision IDs; `import numpy as np`, `import pytest`; `from f1si.data.asof import RACE_END, AsOf, AsOfAccessor`; `from tests.conftest import LONG_RACE_ID, build_long_db`.

**Coverage-over-seeds idiom** (l.42-56): loop over seeds, count hits, assert on the count. The new recovery test replaces the loose `>= 8` with a binomial band: `lo, hi = binom.interval(0.999, n_stints, 0.95)`; assert `lo <= covered <= hi` (scipy.stats; RESEARCH Code Examples). Closed-form oracle `posterior_rate_sd(tau, sigma, fuel_sd, n_measured)` is in RESEARCH.md; compare filter SD to it exactly (deterministic, not statistical) and the Monte Carlo error to `sqrt(2/pi) * sd` within MC error. Use explicit `np.random.Generator` via `make_rng(seed)` (`f1si.rng`), never global state.

**Determinism test** (l.124-125): `assert _fit(...).report == _fit(...).report`; copy for incremental == batch equality.

**Never-raises-on-empty test** (l.128-132): copy idea for a snapshot with no usable laps (lap 0 cutoff) returning a "prior only" result.

Property tests with hypothesis: dependency already pinned; see `tests/data/test_asof.py` / `tests/guards/test_future_scramble.py` for the existing hypothesis style.

---

### `tests/test_cli_wear_filter.py` (test, CLI)

**Analog:** `tests/test_cli_simulate.py` (l.1-60).

```python
def _run(data_dir: Path, tmp_path: Path, *args: str) -> int:
    return main(["--data-dir", str(data_dir), "--reports-dir", str(tmp_path), *args])

assert _run(long_synthetic_data_dir, tmp_path, "simulate", LONG_SLUG, "--driver", code, "--n", "400") == 0
out = capsys.readouterr().out
for needle in ("hindsight simulation", "prior only: no earlier races", ..., "Wrote"):
    assert needle in out, needle
```
Use fixtures `long_synthetic_data_dir`, `long_synthetic_db`, `LONG_SLUG`, `LONG_RACE_ID`; helper `_code(db, race_id, index)` to pick a driver code. Assert needles "prior only", the PNG exists, friendly error exit code 1 for bad `--lap`/unknown driver, and 2026 out-of-sample message.

### `tests/plots/test_wear_filter_plot.py`

**Analog:** `tests/plots/test_wear_plot.py` (l.1-50): `_data(db)` helper building `snap`, `fit`, prepared data; asserts on prepared data columns, PNG written, `wear_file_name` rejects unsafe slugs, and a subprocess check that `pyplot` is not imported.

### `tests/real/test_wear_filter_bahrain.py`

**Analog:** `tests/real/test_wear_bahrain.py` (l.1-60): `pytestmark = pytest.mark.network`; module-scoped `db`, `race_id`, `end` fixtures that `pytest.skip(...)` when the cache or race is missing; `SLUG = "bahrain-2023"`, `LAPS_TOTAL = 57`. Assert ALO's band narrows over the first measured laps of each stint, first stint is "prior only", and report (print, not gate) the Bahrain prior at laps 14, 20, 30 (D-19) and the ALO 90% interval width with and without the filter at a mid-race lap (OQ3).

### `tests/test_state.py` / `tests/test_state_builder.py` / `tests/test_synthetic.py`

Extend in place: old JSON without `wear_source` loads and re-dumps byte-identical; `wear_source="filter"` round-trips; `build_race_state(..., wear_filter=None)` equals today's; synthetic default spec output unchanged (compare table hashes) and truth exposes deviations when set.

---

### Docs: `docs/explained/phase-04.md`, `DECISIONS.md`, `README.md`, `tests/test_docs.py`, `tests/test_decisions_log.py`

**Analogs:** `docs/explained/phase-03.md` (must contain the five headings in `HEADINGS`, test_docs.py l.16-22: "What was built and why", "How the pieces connect", "File-by-file tour", "Interview questions" with 3 to 5 `### QN.` answers of 40+ characters, "Good to know"). `test_tour_covers_every_module` (test_docs.py l.55-60) requires every `src/f1si/**/*.py` (except `__init__.py`) to be mentioned in some tour, so `src/f1si/pace/kalman.py` and `src/f1si/plots/wear_filter.py` must appear in phase-04.md's File-by-file tour in the same task that creates them. Add `PHASE4` constant if tests mirror `PHASE3` (l.9-11).

**DEC entry format** (DECISIONS.md DEC-087):
```
## DEC-087 — Fixed compound slots for the wear draws, so forced plans cannot move common random numbers

**Date:** 2026-11-12
**Status:** Accepted
**Context:** ...
**Decision:** ...
**Why:** ...
**Alternatives rejected:** ...
**Consequences:** ...
**Refs:** DEC-080, D-14, SIM-03
```
Suggested entries from DEC-088 (RESEARCH "Suggested DEC entries"): 088 3-state model, 089 zero process noise, 090 priors and [ASSUMED] values, 091 clean-lap and gate rule, 092 feasibility + PAC-04 restatement (owner D-17, "test optimal accuracy"), 093 simulator integration, 094 `wear_source`. Bump `MIN_ENTRIES = 87` (tests/test_decisions_log.py l.44) to 87 + number added; extend `REQUIRED_REFS` there per its docstring (l.4).

**README needles:** add `"uv run f1si wear-filter bahrain-2023 --driver ALO"` to the needle tuple in test_docs.py (l.80-97), alongside `"uv run f1si simulate bahrain-2023"`.

---

## Shared Patterns

### No look-ahead (as-of discipline)
**Source:** `src/f1si/pace/linear.py` docstring l.54 and `tests/guards/consumers.py`
**Apply to:** `pace/kalman.py` snapshot adapter, `plots/wear_filter.py`, `cli.py`
Functions take a `RaceSnapshot` (or plain arrays), never `AsOfAccessor`. Every noise/fuel/prior value comes from `fit_linear_pace(snapshot)` of the SAME snapshot. Each new public snapshot-reading function is registered (see consumers.py section). Do not import `AsOfAccessor` or `RACE_END` outside the CLI/replay drivers (import scan, consumers.py l.119-123).

### Clean-lap rule
**Source:** `src/f1si/laps.py` l.30-42
```python
def fade_reason(lap_number: int, pit_in: bool, pit_out: bool, track_status: object) -> str | None:
    if lap_number == 1: return "lap 1"
    if pit_in: return "pit in"
    if pit_out: return "pit out"
    if slow_status(track_status): return "safety car/VSC/red"
    return None
```
**Apply to:** the filter's per-lap "used or skipped (reason)" column and the CLI table. Reuse the exact reason strings; add "outlier gate" as the one extra reason.

### 95% interval constant
**Source:** `src/f1si/pace/linear.py` l.79 `CI_Z: Final = 1.96`
**Apply to:** filter intervals, plot band, tests.

### Validation and error style
**Source:** `src/f1si/state.py` l.99-117 (`_check_int`, `_check_float`) and `ValueError` with the offending value in the message (`f"... got {x!r}"`).
**Apply to:** `WearFilter` constructor (q, sigma, SDs finite and positive), `CarState.wear_source`, file-name helper. CLI friendly errors rely on `ValueError` being printed without a traceback for commands in `_FRIENDLY_VALUE_ERRORS` (cli.py l.54, 768-772).

### Reproducibility
**Source:** `src/f1si/sim/draws.py` (module docstring: "Streams come only from `rng.spawn`") and `f1si.rng.make_rng`
**Apply to:** simulator per-car stream and all tests. No global NumPy RNG; explicit `np.random.Generator`.

### Plot rendering
**Source:** `src/f1si/plots/wear.py` (Figure API, no pyplot, slug regex, prepare/build/render split)
**Apply to:** `plots/wear_filter.py`.

### Backward-compatible state additions
**Source:** `src/f1si/state.py` l.68-86, 334-335, 377 (`_OPTIONAL_CAR_KEYS`, write-only-when-nonzero, `raw.get(...)`)
**Apply to:** `wear_source`.

### Docstring states the math; DEC for every method choice
**Source:** linear.py module docstring; DECISIONS.md.
**Apply to:** kalman.py, every new constant marked `[ASSUMED]` with its DEC number.

## No Analog Found

| File / Piece | Role | Data Flow | Reason |
|--------------|------|-----------|--------|
| Joseph-form 3-state Kalman recursion in `pace/kalman.py` | math | transform | No recursive estimator exists in the repo. Use RESEARCH.md Pattern 1 (`update`) and Pattern 2 (gate), and the closed-form oracle in Code Examples. |
| Binomial coverage band test | test | statistical | Existing coverage test (`test_interval_covers_truth_in_most_seeds`) uses a loose `>= 8 of 10`; use `scipy.stats.binom.interval(0.999, n, 0.95)` per RESEARCH. |
| Virtual-compound table extension in the simulator | service | batch | Described in RESEARCH Pattern 4 only; no existing code builds per-car virtual compounds. Follow the insertion points listed above. |

## Open points the planner must handle (from the files read)

1. D-17 restated the accuracy gate: gate coverage, narrowing, closed-form SD match and `error(lap 8) < error(lap 0)`; print (do not gate) the 10% figure. RESEARCH `test_accuracy_report` already matches this.
2. `_classify` in linear.py is private; decide import versus copy of the column extraction, but keep `fade_reason` as the one rule.
3. `build_race_state` currently cannot import from `f1si.pace.kalman` without checking for cycles (kalman imports `f1si.pace.linear`; state imports `f1si.pace.linear`); define the snapshot type in kalman.py and import it in state.py.
4. The CLI must snapshot per cutoff for as-of priors; do not reuse one end-of-race fit across laps (that would be look-ahead for D-05/D-07).
5. Capture the Phase 3 byte-identity reference before touching `numpy_backend.py`.

## Metadata

**Analog search scope:** `src/f1si/{pace,plots,sim,synthetic}`, `src/f1si/{cli,state,laps}.py`, `tests/{pace,plots,sim,real,guards}`, `tests/conftest.py`, `tests/test_*.py`, `DECISIONS.md`, `docs/explained/`
**Files scanned:** about 30 (read in full or targeted ranges)
**Pattern extraction date:** 2026-11-12
