# Phase 2: Interfaces, Linear Tire Wear & Free-Track Optimizer - Pattern Map

**Mapped:** 2026-11-11
**Files analyzed:** 27 new or modified files
**Analogs found:** 24 / 27 (3 have only partial analogs; see "No Analog Found")

All excerpts are from the working tree at commit 5f2583b. Line numbers refer to the files as read in this session.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/f1si/interfaces.py` (new) | model (Protocol definitions) | request-response | `tests/fixtures/leaky_consumer.py` (the `_HasRaceId` Protocol) + `_snapshot.py` frozen types | partial |
| `src/f1si/laps.py` (new, shared clean-lap rule) | utility | transform | `src/f1si/plots/stints.py` lines 51, 92-102 (source of the code being moved) | exact (move) |
| `src/f1si/plots/stints.py` (modify: import from `f1si.laps`) | utility | transform | itself | exact |
| `src/f1si/pace/__init__.py`, `src/f1si/strategy/__init__.py` (new) | config | n/a | `src/f1si/plots/__init__.py` (one-line docstring) | exact |
| `src/f1si/pace/linear.py` (new: `fit_linear_pace`, `LinearPaceFit`, `FitReport`, `measure_pit_loss`) | service | transform (snapshot -> fitted model) | `prepare_stint_plot_data` in `plots/stints.py` + `rebuild_*` in `_snapshot.py` | role-match |
| `src/f1si/state.py` (new: `CarState`, `RaceState`, `build_race_state`, JSON) | model + builder | transform | `RaceSnapshot`/`RaceInfo`/`AsOf` in `_snapshot.py`; `StintPlotData` in `plots/stints.py` | role-match |
| `src/f1si/strategy/free_track.py` (new: `FreeTrackOptimizer`, `Plan`, enumeration) | service (StrategyPolicy) | batch (enumerate and price) | `prepare_stint_plot_data` (pure function returning frozen result) | partial |
| `src/f1si/plots/wear.py` (new) | component (plot) | file-I/O | `src/f1si/plots/stints.py` | exact |
| `src/f1si/cli.py` (modify: `wear`, `plan` subcommands) | controller | request-response | `_cmd_plot` / `_cmd_races` / `main` in `cli.py` | exact |
| `tests/conformance/` (suites, registry, planted stubs, meta-test, simulator double) | test | n/a | `tests/guards/test_meta_guard.py` + `tests/fixtures/leaky_consumer.py` + `tests/guards/consumers.py` | role-match |
| `tests/conformance/test_protocols.py` (mypy rejection proof) | test | n/a | no runtime analog; pattern in RESEARCH Pattern 2 | no analog |
| `tests/pace/test_linear_recovery.py`, `test_identification.py`, `test_clean_laps.py` (new) | test | transform | `tests/test_synthetic.py`, `tests/plots/test_stint_plot.py` | role-match |
| `tests/strategy/test_free_track.py` (new) | test | batch | `tests/plots/test_stint_plot.py` (+ hypothesis usage in `tests/guards/test_future_scramble.py`) | role-match |
| `tests/test_state.py` (new) | test | transform | `tests/plots/test_stint_plot.py` | role-match |
| `tests/test_cli_wear_plan.py` (new) | test | request-response | `tests/test_cli.py` | exact |
| `tests/real/test_wear_bahrain.py` (new, opt-in) | test | request-response | `tests/real/test_bahrain_2023.py` | exact |
| `tests/guards/consumers.py` (modify: CONSUMERS, DESIGNATED_MODULES, CONSUMED, EXEMPT) | config (registry) | n/a | itself | exact |
| `tests/guards/import_scan.py` (modify only if a new rule is needed) | config (policy) | n/a | itself | exact |
| `tests/test_docs.py` (modify: generalize to all explainers) | test | n/a | itself | exact |
| `tests/test_decisions_log.py` (modify: `MIN_ENTRIES`, optional title test) | test | n/a | itself | exact |
| `DECISIONS.md` (append DEC-061..) | config (docs) | n/a | DEC-050, DEC-051, DEC-060 | exact |
| `docs/explained/phase-02.md` (new) | docs | n/a | `docs/explained/phase-01.md` | exact |
| `README.md` (modify: `wear`/`plan` commands, phase-02 link) | docs | n/a | existing README lines 11-27 | exact |
| `tests/conftest.py` (modify: long synthetic spec fixture, 57 laps / 20 drivers) | test fixture | file-I/O | `synthetic_db` fixture in `tests/conftest.py` | exact |
| analytic 2-stop case in `tests/strategy/` (hand-built, D-24) | test | batch | none (new) | no analog |
| `src/f1si/synthetic/generator.py` | (NOT modified, D-24) | | read-only truth source | n/a |

## Pattern Assignments

### `src/f1si/laps.py` (utility, transform) - the shared clean-lap rule

**Analog:** `src/f1si/plots/stints.py` (move, do not rewrite)

**Constant and function to move** (lines 51 and 92-102):
```python
FADE_TRACK_CODES: Final = frozenset({"4", "5", "6", "7"})

def _fade_reason(lap_number: int, pit_in: bool, pit_out: bool, track_status: object) -> str | None:
    """First matching reason a lap is faded, or None for a clean lap."""
    if lap_number == 1:
        return "lap 1"
    if pit_in:
        return "pit in"
    if pit_out:
        return "pit out"
    if isinstance(track_status, str) and any(c in FADE_TRACK_CODES for c in track_status):
        return "safety car/VSC/red"
    return None
```

**Call site in the plot** (lines 187-196), which the clean-lap mask for the fit should mirror (same zip over `lap_number`, `is_pit_in_lap`, `is_pit_out_lap`, `track_status`, with `.fillna(False)`):
```python
    reasons = [
        _fade_reason(int(lap), bool(pin), bool(pout), ts)
        for lap, pin, pout, ts in zip(
            laps["lap_number"],
            laps["is_pit_in_lap"].fillna(False),
            laps["is_pit_out_lap"].fillna(False),
            laps["track_status"],
            strict=True,
        )
    ]
```

**Planner notes:**
- `plots/stints.py` must then `from f1si.laps import FADE_TRACK_CODES, fade_reason` (or keep the private alias `_fade_reason = fade_reason` for one release). Grep found `_fade_reason` / `FADE_TRACK_CODES` only inside `src/f1si/plots/stints.py`; `tests/plots/test_stint_plot.py` tests fade classes through `prepare_stint_plot_data` and imports only `COMPOUND_COLORS, StintPlotData, UnknownDriverError, build_figure, plot_file_name, prepare_stint_plot_data, render_stint_plot`, so the move does not break that file. Keep `COMPOUND_COLORS` in `plots/stints.py`.
- Pitfall 3: `_fade_reason` returns "pit in"/"pit out" BEFORE the track-status check. Add a separate public predicate in `f1si/laps.py` (e.g. `slow_status(track_status: object) -> bool`) using the same `isinstance(track_status, str) and any(c in FADE_TRACK_CODES ...)` expression; pit-loss measurement uses it.
- Module docstring style: lead with one sentence naming the requirement IDs, then a prose section header with underlines (see `plots/stints.py` lines 1-23, `_snapshot.py` lines 1-30).
- Registry consequence: if `f1si.laps` has a public function taking a `RaceSnapshot` (clean-lap mask), it belongs in `DESIGNATED_MODULES`. If its public functions are scalar (like `fade_reason(lap, pit_in, pit_out, status)`), simplest is to keep them out of `DESIGNATED_MODULES` (the registry test only enumerates designated modules) and have the snapshot-level wrapper live in `pace/linear.py`.

---

### `src/f1si/state.py` (model + builder, transform)

**Analog 1 (frozen value objects):** `src/f1si/data/_snapshot.py` lines 46-112

**Frozen dataclass conventions** (lines 46-65, 94-112):
```python
@dataclass(frozen=True)
class AsOf:
    """A point on the race clock: after the leader completed `lap` laps, or `RACE_END`.

    Raises:
        ValueError: if `lap` is negative, a bool, or neither an int nor `RACE_END`.
    """

    race_id: str
    lap: int | RaceEnd

    def __post_init__(self) -> None:
        if isinstance(self.lap, RaceEnd):
            return
        if isinstance(self.lap, bool) or not isinstance(self.lap, int):
            raise ValueError(f"lap must be an int >= 0 or RACE_END, got {self.lap!r}")
        if self.lap < 0:
            raise ValueError(f"lap must be >= 0 (0 means before the start), got {self.lap}")

@dataclass(frozen=True, eq=False)
class RaceSnapshot:
    """What was knowable at `at`. Plain data: it grants no further access to the cache. ..."""
    race: RaceInfo
    at: AsOf
    cutoff_s: float | None
    entries: pd.DataFrame
    ...
```
- Use `@dataclass(frozen=True)` WITH default `eq` for `CarState`/`RaceState` (tuple-of-records, no DataFrame fields), so `from_json(to_json(s)) == s` works. `eq=False` in `_snapshot.py` is only because fields are DataFrames; do not copy it.
- Validation in `__post_init__` raising `ValueError` with a message that states the bad value (`{x!r}`) is the house style. Do the same for `RaceState.lap >= 0`, `laps_total >= lap`.
- `from __future__ import annotations` at top of modules that use forward refs (as in `_snapshot.py`, `stints.py`, `generator.py`).

**Analog 2 (frozen result with `Mapping` and tuple fields):** `src/f1si/plots/stints.py` lines 78-89
```python
@dataclass(frozen=True, eq=False)
class StintPlotData:
    """Everything the renderer needs, as plain data (no snapshot, no accessor)."""

    title: str
    slug: str
    drivers: tuple[str, ...]
    panel_titles: Mapping[str, str]
    points: pd.DataFrame
    y_limits: tuple[float, float]
    skipped_laps: int
    stint_starts: Mapping[str, tuple[int, ...]]
```
Type fields as `tuple[...]` and `Mapping[...]` (from `collections.abc`); for `RaceState.regime` / `pit_loss_s` wrap in `types.MappingProxyType` in `__post_init__` via `object.__setattr__` (RESEARCH Pattern 4).

**Builder pattern (pure function of snapshot):** `rebuild_cars` in `_snapshot.py` lines 296-319 is the closest analog for position/gap derivation and for `Int64`/NA handling:
```python
    done = laps[laps["lap_end_s"].notna()]
    per_driver = done.groupby("driver_number", sort=True).agg(
        laps_done=("lap_end_s", "count"), last_lap_end_s=("lap_end_s", "max")
    )
    ...
    cars["position"] = ranks.reindex(cars.index).astype("Int64")
```
So `snapshot.cars` columns are `driver_number, driver_code, laps_done, last_lap_end_s, stops_done, position`, all nullable pandas dtypes. When reading them in `build_race_state`, convert with `pd.isna(x)` -> `None` (D-23) and `int(x)` for values; this is the same idiom as `race_info` (`None if pd.isna(scheduled) else int(scheduled)`, `_snapshot.py` line 182).

**Import rule for this module:** import only `from f1si.data.asof import RaceSnapshot` (type-only is fine). It must NOT mention `AsOfAccessor`, `RACE_END`, `RaceEnd` (checked by `test_only_the_drivers_name_the_accessor_in_src`, `tests/guards/test_consumer_registry.py` lines 59-75, which allows only `f1si.cli`, `f1si.data.asof`, `f1si.data._snapshot`). `RaceSnapshot.at.lap` may be read as `int | RaceEnd` using `isinstance(snapshot.at.lap, int)` (that is what `stints.py` line 175 does) without naming `RaceEnd`.

**JSON:** no existing JSON-round-trip analog in src. Closest: `jolpica.calls.json` handling in `src/f1si/data/sources/_http.py` (not read here). Use RESEARCH Pattern 4: `json.dumps(..., allow_nan=False)`, `None` for unknown.

---

### `src/f1si/interfaces.py` (Protocol definitions)

**Analog:** `tests/fixtures/leaky_consumer.py` lines 14-17 (the only Protocol in the repo):
```python
from typing import Protocol

class _HasRaceId(Protocol):
    @property
    def race_id(self) -> str: ...
```
**Other conventions to copy:**
- Keyword-only `rng: np.random.Generator` (from `generator.py` line 233): `def generate_race(spec: SyntheticRaceSpec, *, rng: np.random.Generator) -> SyntheticRace:`. For `SimulatorBackend.simulate` use the same signature shape (`*, rng: np.random.Generator`). `PaceModel.predict` and `StrategyPolicy.decide` take no rng (RESEARCH Pattern 1; log in DECISIONS).
- Never import `numpy.random.default_rng`; only `f1si.rng.make_rng` may (POLICY rows lines 93-100 of `import_scan.py`). Annotating with `np.random.Generator` is fine.
- Docstrings state the math/contract (project rule): see `generator.py` lines 1-28 for the format "Lap-time model ... t(d, L) = base + ...". The `PaceModel` docstring must restate the D-01 model and the "age at END of lap" convention.
- mypy strict applies to `src` and `tests` (`pyproject.toml` `[tool.mypy] strict = true, files = ["src", "tests"]`).
- Ruff `N806`: do not name a variable `L`; use `lap` (RESEARCH Pitfall 9).

---

### `src/f1si/pace/linear.py` (service, transform: snapshot -> fitted `PaceModel`)

**Analog:** `prepare_stint_plot_data` (`plots/stints.py` lines 154-223): a pure function of a `RaceSnapshot` that classifies laps, handles the empty case, and returns a frozen dataclass.

**Core shape to copy:**
```python
def prepare_stint_plot_data(
    snapshot: RaceSnapshot, drivers: Sequence[str] | None = None
) -> StintPlotData:
    """Classify every visible lap and compute the shared y-range (pure; reads only `snapshot`).

    Raises:
        ValueError: if a driver code is not three letters.
        UnknownDriverError: if a driver code is not in this race.
    """
    ...
    laps = snapshot.laps[snapshot.laps["driver_number"].isin(list(number_to_code))]
    has_time = laps["lap_time_s"].notna()
    skipped = int((~has_time).sum())
    laps = laps[has_time]
    ...
    if laps.empty:
        return StintPlotData(..., _empty_points(), (0.0, 1.0), skipped, starts)
```
Reuse: the `has_time` filter and "skipped" counting (feeds the `dropped` Counter reason `no lap time`), the early return for an empty snapshot (a lap-0 snapshot has no laps -> return a report with `unidentified` filled, do not raise, so the scramble consumer works at any cutoff; RESEARCH Pitfall 9).

**Compound normalization** (lines 203-207) - reuse to upper-case compounds and map non-str to None:
```python
    compound = (
        laps["compound"]
        .astype("object")
        .map(lambda v: str(v).upper() if isinstance(v, str) else None)
    )
```

**Custom error with a "what to do next" message** (lines 69-75) - copy for `NotIdentifiedError` / `NotEnoughDataError`:
```python
class UnknownDriverError(ValueError):
    """A requested driver code is not in this race."""

    def __init__(self, unknown: Sequence[str], known: Sequence[str]) -> None:
        super().__init__(
            f"Unknown driver code(s) {', '.join(unknown)}. Codes in this race: {', '.join(known)}"
        )
```
Reuse `UnknownDriverError` and `_select_drivers`-style code validation (lines 111-122) for `--driver`: `^[A-Z]{3}$` check first, then membership, listing sorted valid codes. If `pace`/`cli` need it, import from `f1si.plots.stints` (`UnknownDriverError` is public) rather than duplicating, or promote `_CODE`/the checker into `f1si.laps`.

**Numerical pieces with no codebase analog** (use RESEARCH "Code Examples": SVD rank check, classical SE, MAD trimming rebuilt each iteration). Use `numpy` only (SciPy is not installed). Data types: output dataclasses should contain Python floats/tuples/`Mapping`s, not ndarrays, so the scramble `_compare` (`tests/guards/scramble.py` lines 266-292) compares them exactly; if an ndarray is returned it is handled by `_same_scalar` with `np.array_equal(..., equal_nan=True)` (lines 256-263), but both sides must be the same type.

**Registry:** every public function in `f1si.pace.linear` that takes a `RaceSnapshot` (`fit_linear_pace`, `measure_pit_loss`) needs a consumer; see the `tests/guards/consumers.py` section below. Methods of `LinearPaceFit` (`predict`) are public methods of a class in a designated module: they too must be CONSUMED or EXEMPT (the registry test enumerates public functions AND public methods of classes; `test_consumer_registry.py` lines 19-33).

---

### `src/f1si/strategy/free_track.py` (service / StrategyPolicy, batch enumeration)

**Analog:** no enumeration code exists. Copy the structural conventions from `plots/stints.py`: pure functions, frozen result dataclasses, module docstring with the math (closed-form stint cost from RESEARCH Pattern 6), `Final` constants for tunables:
```python
_HEADROOM_S: Final = 0.3
FADED_ALPHA: Final = 0.25
```
Use `MIN_STINT_LAPS: Final = 5`, `MAX_STOPS: Final = 2`, default pit loss etc. as named `Final` constants with the DEC id in a comment.

**Import discipline:** receives a `RaceState` plus a `PaceModel` in `__init__`; must not import `f1si.data.asof` at all if possible (it takes no snapshot, so it need not be a designated module). It then needs no consumer entry.

**Error style:** raise `ValueError` with a message ending in a PowerShell-copy-pasteable next step (D-17), e.g. from `cli.py` line 136: `print("No races cached yet. Run: uv run f1si load")`.

---

### `src/f1si/plots/wear.py` (plot component, file-I/O)

**Analog:** `src/f1si/plots/stints.py` - copy the whole three-function split: `prepare_*` (pure data from the fit report), `build_figure(data) -> Figure`, `render_*_plot(data, out_path) -> Path`, `plot_file_name(slug)` for the file name.

**Imports** (lines 25-39):
```python
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from f1si.data.asof import RaceSnapshot
```
**Figure API without pyplot** (lines 231-233, 249-258, 319-323):
```python
    fig = Figure(figsize=(3.6 * ncols, 2.6 * nrows + 0.8), layout="constrained")
    axes = fig.subplots(nrows, ncols, sharex=True, sharey=True, squeeze=False)
    ...
    ax.scatter(sel["lap_number"].astype(float), sel["y_plot"].astype(float), s=14, marker=marker,
               c=list(sel["color"]), edgecolors=EDGE_COLOR, linewidths=0.4, alpha=...)
    ...
def render_stint_plot(data: StintPlotData, out_path: Path) -> Path:
    """Write the plot as a PNG (creating parent folders) and return the path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    build_figure(data).savefig(out_path, dpi=120)
    return out_path
```
**Colors:** import `COMPOUND_COLORS`, `UNKNOWN_COLOR`, `EDGE_COLOR` from `f1si.plots.stints` instead of redefining (keeps the compound palette in one place; DEC-050).
**File name safety** (lines 326-340): copy the `_SLUG = re.compile(r"^[a-z0-9-]+$")` check and `raise ValueError(f"Unsafe race slug for a file name: {slug!r}")`; the wear PNG is `wear-{slug}.png` (D-15 says `reports/wear-bahrain-2023.png`).
**No-pyplot enforcement:** `tests/plots/test_stint_plot.py::test_no_pyplot_in_src` (lines 177-186) scans ALL of `src` for pyplot imports, and `test_module_imports_without_pyplot` (lines 189-191) subprocess-checks `f1si.plots.stints`. Add the analogous subprocess check for `f1si.plots.wear` in the new wear test.
**Empty case:** stints plot returns an empty frame and writes "no laps yet" in panels (lines 182-185, 242-243); mirror with "not enough data" panels for compounds that were not fitted.
**Registry:** `plots/wear.py`'s prepare function takes the fit report (not a snapshot), so it does not need to be designated. If it takes a `RaceSnapshot`, it must be registered like `stint_plot_data`.

---

### `src/f1si/cli.py` (controller, request-response) - add `wear` and `plan`

**Analog:** `_cmd_plot` and `main` in the same file.

**Imports pattern** (lines 8-24): stdlib first, then `import f1si`, `from f1si import paths`, `from f1si.data import asof`, then specific modules; one import per module, alphabetical (ruff `I`). Only `f1si.cli` may import `AsOfAccessor`/`RACE_END` (POLICY `_REPLAY_DRIVERS`).

**Subparser pattern** (lines 77-85):
```python
    plot = sub.add_parser("plot", help="plot lap time by stint for one cached race")
    plot.add_argument("slug", metavar="SLUG", help="race slug (for example bahrain-2023)")
    plot.add_argument(
        "--drivers",
        nargs="+",
        default=None,
        metavar="CODE",
        help="only these driver codes, for example VER HAM (default: all drivers)",
    )
```
Add `wear` (slug, `--lap N` type int, default None) and `plan` (slug, `--driver CODE` default None, `--lap N`). Help strings use "for example ..." phrasing.

**Command function pattern** (lines 145-163) - the template for `_cmd_wear` / `_cmd_plan`:
```python
def _cmd_plot(data_dir: Path, reports_dir: Path, slug: str, drivers: Sequence[str] | None) -> int:
    db = paths.db_path(data_dir)
    race_id = asof.resolve_slug(db, slug)
    try:
        snapshot = asof.AsOfAccessor(db).snapshot(asof.AsOf(race_id, asof.RACE_END))
    except OutOfSampleLockedError as err:
        print(
            f"{err} 2026 races are out-of-sample, so they cannot be plotted in Phase 1.",
            file=sys.stderr,
        )
        return 1
    data = prepare_stint_plot_data(snapshot, drivers=drivers)
    out = reports_dir / plot_file_name(snapshot.race.slug, drivers)
    render_stint_plot(data, out)
    print(
        f"Wrote {out} ({len(data.drivers)} drivers; {data.skipped_laps} laps without a time "
        "were skipped). Open it to see lap times by stint."
    )
    return 0
```
Key points for the new commands: `race_id = asof.resolve_slug(db, slug)` (validates slug); `at = asof.AsOf(race_id, lap if lap is not None else asof.RACE_END)`; the CLI itself fetches `laps_total` from the `RACE_END` snapshot (max `lap_number`, D-21), default driver (D-08), and the "actual strategy" read (D-16). Error messages go to `sys.stderr` and return 1; the message ends with an actionable command.

**Table printing pattern** (lines 137-139) - reuse the width-aligned columns idiom:
```python
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(header)]
    for line in (header, *rows):
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip())
```

**Dispatch and error handling in `main`** (lines 166-202). Required edits:
```python
        if args.command == "plot":
            reports_dir: Path = (
                args.reports_dir if args.reports_dir is not None else paths.reports_dir()
            )
            return _cmd_plot(data_dir, reports_dir, args.slug, args.drivers)
        ...
    except ValueError as err:
        if args.debug or args.command != "plot":
            raise
        print(str(err), file=sys.stderr)
        return 1
```
Gotcha: the `ValueError` handler only converts to a friendly message for `args.command == "plot"`. Change the condition to `args.command not in {"plot", "wear", "plan"}` (or a module-level set) so unknown-driver / not-identified errors from the new commands print plainly and exit 1 (D-17). `--lap` out of range raises `LapOutOfRangeError`, which is an `F1siDataError` and already handled (lines 198-202). Also note that the `else` falls through to `_cmd_races`; add explicit branches for `wear`/`plan` before it. Update the module docstring (lines 1-6) to list the new subcommands.

**Tests:** copy `tests/test_cli.py` style: `main(["--data-dir", str(tmp_path), "load", "--source", "synthetic"]) == 0`, `capsys.readouterr()`, then assert on `out`/`err`. For wear/plan on synthetic data use a long-spec race (see conftest section) because default 12-lap races only identify from cutoff >= ~8-9.

---

### `tests/conformance/` (suites, registry, planted stubs, meta-test)

**Analog A (planted-leak + meta-test):** `tests/guards/test_meta_guard.py` and `tests/fixtures/leaky_consumer.py`.

Meta-test shape to copy (lines 33-47 and 71-73):
```python
def test_direct_duckdb_leak_is_caught_by_both_checks(tables: dict[str, pd.DataFrame]) -> None:
    violations = scan([FIXTURES / "leaky_consumer.py"], REPO_ROOT)
    assert violations
    ...
    with pytest.raises(LookaheadDetected):
        assert_no_lookahead(consumer, tables, AT, rng=np.random.default_rng(0))

@pytest.mark.parametrize("name", sorted(CONSUMERS))
def test_honest_consumers_pass(tables: dict[str, pd.DataFrame], name: str) -> None:
    assert_no_lookahead(CONSUMERS[name], tables, AT, rng=np.random.default_rng(0))
```
For Phase 2: `@pytest.mark.parametrize("name", sorted(PACE_MODELS))` runs `check_pace_model`; `@pytest.mark.parametrize("stub", BAD_PACE_STUBS, ids=lambda s: s.__name__)` + `pytest.raises(AssertionError)` proves each defect bites (RESEARCH Pattern 3 and "Meta-test" snippet).

**Analog B (registry as `Final` dict with documented entries):** `tests/guards/consumers.py` lines 47-54:
```python
CONSUMERS: Final[dict[str, Consumer]] = {
    "snapshot": snapshot,
    ...
}
```
Mirror as `PACE_MODELS: Final[dict[str, Callable[[], PaceModel]]]`, `POLICIES`, `BACKENDS`. Adding an implementation = one entry (D-11).

**Analog C (deliberately wrong fixture, header style):** `tests/fixtures/leaky_consumer.py` lines 1-6 - a docstring starting `"""DELIBERATELY ... test fixture ..."""` saying never import from `src/`. Put the planted stubs in `tests/fixtures/bad_pace_models.py` (or inside `tests/conformance/`) with the same header. Because `mypy` checks `tests`, stubs that intentionally violate the Protocol must not be passed to Protocol-typed params without `# type: ignore[arg-type]` (that is the point of Pattern 2).

**Use `make_rng`, not `np.random.default_rng`, in new tests?** Existing tests (`test_meta_guard.py` line 73) use `np.random.default_rng(0)` directly in `tests/`. The import-ban scan covers `src` only (`SRC_ROOT`, `scan_package`), so tests may do this, but prefer `from f1si.rng import make_rng` for consistency with `tests/conftest.py` lines 8, 29.

**Synthetic data for fixtures:** `tests/conftest.py` lines 14-35:
```python
@pytest.fixture(scope="session")
def synthetic_races() -> list[SyntheticRace]:
    return generate_dataset(default_specs(), rng=make_rng(DEFAULT_SEED))

@pytest.fixture(scope="session")
def synthetic_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("synthetic_db")
    db = paths.db_path(folder)
    load_races(SyntheticSource(rng=make_rng(DEFAULT_SEED)), db, (2023, 2024, 2026),
               now=datetime(2026, 10, 22, tzinfo=UTC), echo=lambda _line: None)
    return db
```
Default specs (`generator.py` lines 358-372) are 12 laps / 6 drivers with one stop at `n_laps // 2 + (i % 2)` -> lap 6 or 7; the fit is identifiable only from cutoff >= ~8-9. For recovery and optimizer tests add a session fixture `long_synthetic_db` built from `SyntheticRaceSpec(2023, 1, "Long Grand Prix", n_drivers=20, n_laps=57, start_tyre_age=3)` via `generate_race`/`generate_dataset` and the loader (a `SyntheticSource` takes default specs; check `synthetic_source.py` for how to pass custom specs before planning). Race ids come out as `f"{season}-{round:02d}"` and slugs via `event_slug` (`generator.py` lines 111-123): "Long Grand Prix" 2023 -> `long-2023` (verify with `event_slug`).

---

### `tests/pace/*`, `tests/strategy/*`, `tests/test_state.py` (unit tests)

**Analog:** `tests/plots/test_stint_plot.py` and `tests/test_synthetic.py`.

**Snapshot helper and module-scoped fixture** (test_stint_plot.py lines 22-31):
```python
def _snap(db: Path, slug_id: str, lap: int | None = None) -> RaceSnapshot:
    at = AsOf(slug_id, RACE_END if lap is None else lap)
    return AsOfAccessor(db).snapshot(at)

@pytest.fixture(scope="module")
def alpha(synthetic_db: Path) -> StintPlotData:
    return prepare_stint_plot_data(_snap(synthetic_db, "2023-01"))
```
Tests may hold the accessor (tests are not scanned by the import ban; `tests/guards/test_consumer_registry.py` scans `SRC_ROOT` only).

**Truth-recovery assertion style** (`tests/test_synthetic.py` lines 22-37): compare against `r.truth.*` using `pytest.approx`; for the fit use `abs(est - truth) < 3 * se` plus a seed-coverage loop (RESEARCH Pitfall 10). NOTE (RESEARCH Pitfall 10): the generator's `start_compound` is MEDIUM (truth 0.07) and `second_compound` HARD (truth 0.04); the wear dict has SOFT/MEDIUM/HARD but only MEDIUM and HARD appear in a race. Remember `track_status` is NA in synthetic laps (line 317), so do not use `vsc_laps` in recovery specs.

**Property tests:** hypothesis is a dev dependency; the existing usage is in `tests/guards/test_future_scramble.py` (not read in detail; open it before copying a `@given`/`settings` pattern).

**Frozen-instance tests:** `with pytest.raises(dataclasses.FrozenInstanceError):` (standard); `AsOf` validation tests are in `tests/data/test_asof.py` (error messages matched with `match=`).

---

### `tests/guards/consumers.py` (registry modification)

**Current pattern** (lines 12-14, 42-70):
```python
from f1si.data.asof import AsOf, AsOfAccessor
from f1si.plots.stints import prepare_stint_plot_data
from tests.guards.scramble import Consumer

def stint_plot_data(db_path: Path, at: AsOf) -> object:
    """The stint plot's prepared data (points, y-range, panel titles, stint starts)."""
    return prepare_stint_plot_data(AsOfAccessor(db_path).snapshot(at))

CONSUMERS: Final[dict[str, Consumer]] = { ..., "stint_plot_data": stint_plot_data }

DESIGNATED_MODULES: Final = ("f1si.data.asof", "f1si.plots.stints")

CONSUMED: Final[dict[str, str]] = {
    "f1si.data.asof.AsOfAccessor.snapshot": "snapshot",
    "f1si.data.asof.AsOfAccessor.history": "history",
    "f1si.plots.stints.prepare_stint_plot_data": "stint_plot_data",
}
EXEMPT: Final[dict[str, str]] = {
    "f1si.data.asof.catalog": "calendar facts (names, dates, eras) of every race are public",
    ...
    "f1si.plots.stints.plot_file_name": "string function of a slug and driver codes",
}
```
**Edits required (Pitfall 9):**
1. Add consumers `clean_lap_mask`, `linear_fit`, `pit_loss`, `race_state` of the form `def linear_fit(db_path: Path, at: AsOf) -> object: return fit_linear_pace(AsOfAccessor(db_path).snapshot(at))`. For `race_state` build the fit inside the consumer and pass an explicit `laps_total` (e.g. a constant per synthetic race or computed from a fixed snapshot; it must not read the future, so use a literal such as the 12-lap synthetic race length).
2. Add the new designated modules to `DESIGNATED_MODULES` (e.g. `"f1si.pace.linear"`, `"f1si.state"` if it exposes public functions taking snapshots, `"f1si.laps"` if applicable).
3. For each public function and each public method of each public class defined in those modules (e.g. `LinearPaceFit.predict`, `RaceState.to_json_dict`, `CarState`'s methods) add a `CONSUMED` entry (the named consumer's `__code__.co_names` must contain the function's last name component, `test_consumer_registry.py` lines 50-56; so a consumer that calls `fit.predict(...)` consumes `...LinearPaceFit.predict`) or an `EXEMPT` entry with >= 4 words of reason (line 46-47). Staleness is also an error (line 42), so remove entries if functions are renamed. Dataclass-generated methods are not `inspect.isfunction` in `vars(cls)`, but explicit `@staticmethod`/`@classmethod` are not plain functions either (`inspect.isfunction` is False for classmethod objects), so only plain instance methods and module-level functions are enumerated.
4. Consumers must not raise on early cutoffs: `_run` records raises as `("raised", (type, str))` and compares them (`scramble.py` lines 249-253), so a deterministic raise is tolerated, but prefer returning the report with `unidentified` filled.
5. Outputs are compared by `_compare` (lines 266-292): DataFrame, dataclass (field by field), Mapping, list/tuple, scalars (NaN-aware floats), ndarray. A `MappingProxyType` is a `Mapping` and works; a `Counter` works as a Mapping. Types must match exactly between the two runs (`type(a) is not type(b)` check, line 268).

**Import-ban policy (`import_scan.py`):** No new `Rule` is mandatory. New modules import only `f1si.data.asof.RaceSnapshot` (not protected: only `AsOfAccessor`, `RACE_END`, `RaceEnd` are, lines 127-141). `_REPLAY_DRIVERS` (line 74) already lists `f1si.cli`. Optional hardening: none required. Do NOT add a rule that bans `f1si.state`/`f1si.pace` from reaching `f1si.data.asof`, as that would break `RaceSnapshot` imports.

---

### `tests/test_docs.py` (generalize; Pitfall 8)

**Current hard-wiring** (lines 7, 19-20, 46-55, 71-80):
```python
EXPLAINER = ROOT / "docs" / "explained" / "phase-01.md"
...
def _text() -> str:
    return EXPLAINER.read_text(encoding="utf-8")
...
def test_tour_covers_every_module() -> None:
    tour = _section(_text(), "## File-by-file tour")
    modules = sorted(
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "src" / "f1si").rglob("*.py")
        if p.name != "__init__.py"
    )
    assert modules
    missing = [m for m in modules if m not in tour]
    assert not missing, missing
```
**Planned change:** `EXPLAINERS = sorted((ROOT/"docs"/"explained").glob("phase-*.md"))`; parametrize `test_headings_exist_in_order` and `test_interview_questions_have_answers` over `EXPLAINERS` (`ids=lambda p: p.name`); make `test_tour_covers_every_module` take the union of all explainers' `## File-by-file tour` sections (so phase-01 stays valid while phase-02 documents only new modules: `src/f1si/interfaces.py`, `state.py`, `laps.py`, `pace/linear.py`, `strategy/free_track.py`, `plots/wear.py`); keep `test_tour_mentions_guards_and_workflows` pointed at phase-01. In `test_readme_commands_and_links` add needles `"uv run f1si wear bahrain-2023"`, `"uv run f1si plan bahrain-2023"`, `"docs/explained/phase-02.md"`. Keep the helper `_section` unchanged (it matches `heading + "\n"`).

**Explainer format** (`docs/explained/phase-01.md`): headings, in order: `# Phase 2 explained: ...`, `## What was built and why`, `## How the pieces connect`, `## File-by-file tour` (with `Paths are relative to the repository folder. ...` line and bullets of the form ``- `src/f1si/cli.py` is the command line: ...``), `## Interview questions` (`### Q1. ...` through `### Q3-5`, each answer >= 40 characters; test: `3 <= len(answers) <= 5`), `## Good to know`. Subsections used in the tour: `### The package ...`, `### Guards, fixtures and shared test setup`, `### Automation and notes`. In phase-02 the tour should also list the new guard/test files (`tests/conformance/...`, `tests/guards/consumers.py` updates). Suggested Q topics (CONTEXT D-18): fuel vs wear separability, what a Protocol buys, why free-track is a lower bound.

---

### `DECISIONS.md` (append entries)

**Analog entries:** DEC-050 (conventions), DEC-051 (process), DEC-060 (latest, 2026-10-22). Next free number: **DEC-061**. The numbering must stay consecutive (`tests/test_decisions_log.py::test_ids_are_consecutive_and_enough`, lines 58-61).

**Exact entry format** (from DEC-060 and the test's `HEADING`/`LABELS`, lines 16-26; the heading uses an em dash):
```markdown
## DEC-061 — <title>

**Date:** 2026-11-11
**Status:** Accepted
**Context:** ...
**Decision:** ...
**Why:** ...
**Alternatives rejected:** ...
**Consequences:** ...
**Refs:** D-01, D-02, DEC-050
```
All eight bold labels are mandatory in every entry (line 64-67). `**Refs:**` line is parsed with `[A-Z]{1,3}-\d{2,3}`. Heading must be `## DEC-NNN — Title` (em dash U+2014, one space each side).

**Entries Phase 2 owes** (from CONTEXT/RESEARCH): regression method (OLS, classical SE, 1.96 normal CI, df >= 30); MAD outlier rule (k=3, iterate <= 5, rebuild design each pass); minimum clean laps per compound (suggest 30, >= 2 stints/drivers); identification rule (SVD rank, name unidentified parameters); fuel reported as measured (-0.078 at Bahrain, D-25); no compound pace offset (D-19, +0.26 s SE 0.13); clean lap = plot fade (D-22, overrides "yellow"); pit-loss definition and default 22.0 s flagged (D-05); minimum stint length 5 and plan conventions (stop at lap k = in-lap, out-lap age 1); tie-breaking order; `PaceModel` injected into optimizer (no schema change); `laps_total` argument (D-21); position/gap `None` (D-23); placeholder `regime`/`pit_loss_s` (D-13); plan cutoff policy and "hindsight plan" label (D-20); Protocol signatures (driver int key, `StrategyPolicy` without rng, `SimulatorBackend` result shape provisional); analytic ground truth for the optimizer (D-24).

**Test updates:** `tests/test_decisions_log.py` has `MIN_ENTRIES = 60` (line 44): raise it to the new count; add title-based tests following lines 98-121 (e.g. `test_...entry_exists_by_title` asserting a keyword in the body). `REQUIRED_REFS` (lines 27-43) only needs extension if new required refs are wanted.

---

### `tests/real/test_wear_bahrain.py` (opt-in real-data test)

**Analog:** `tests/real/test_bahrain_2023.py` (not re-read in detail; open it to copy the marker/skip pattern). pyproject markers: `network` (`addopts = ["-ra", "--strict-markers", "-m", "not network"]`). Per RESEARCH, tests must skip when the cache or race is absent and use loose bands (SOFT/HARD 0.08-0.17 s/lap, pit-loss median 22-28 s).

---

### `README.md` (modify)

Existing command list (lines 11-12, 23-27):
```
- `uv run f1si plot bahrain-2023` draws lap time by stint for a whole race, one panel per driver, coloured by tyre.
...
uv run f1si plot bahrain-2023                              # writes reports\bahrain-2023.png
```
Add bullets and example lines for `uv run f1si wear bahrain-2023` (writes `reports\wear-bahrain-2023.png`) and `uv run f1si plan bahrain-2023 --driver ALO`, plus a link to `docs/explained/phase-02.md`. Use PowerShell-friendly backslash path in comments as the existing line does.

---

## Shared Patterns

### Plain-data inputs only (look-ahead rule)
**Source:** `src/f1si/data/_snapshot.py` lines 94-112 (`RaceSnapshot`), `src/f1si/plots/stints.py` lines 3-7, `tests/guards/test_consumer_registry.py` lines 59-75
**Apply to:** `laps.py`, `pace/linear.py`, `state.py`, `strategy/free_track.py`, `plots/wear.py`
Model code receives a `RaceSnapshot` (or `RaceState`), never `AsOfAccessor`/`RACE_END`/`RaceEnd`. Only `f1si.cli` (and the doors) may name those; the test asserts `users <= {"f1si.cli", "f1si.data.asof", "f1si.data._snapshot"}`. Anything the CLI needs from `RACE_END` (laps_total, default driver, actual strategy) is read in `cli.py` and passed in as arguments.

### Explicit rng, never legacy or direct constructors
**Source:** `src/f1si/rng.py` lines 21-40, `src/f1si/synthetic/generator.py` line 233, `import_scan.py` lines 90-100
**Apply to:** `interfaces.py` (`SimulatorBackend.simulate`), any test double, tests
```python
def generate_race(spec: SyntheticRaceSpec, *, rng: np.random.Generator) -> SyntheticRace:
```
In `src`, only `f1si.rng` may call `default_rng`/`PCG64`/etc.; `np.random.seed`/`RandomState` are banned everywhere; ruff `NPY002` bans legacy calls.

### Error messages that say what to do next
**Source:** `src/f1si/cli.py` lines 134-136, 151-155, 193-202; `src/f1si/plots/stints.py` lines 69-75, 117
**Apply to:** `cli.py` new commands, `pace/linear.py` errors, `strategy/free_track.py` refusals
```python
        print("No races cached yet. Run: uv run f1si load")
...
        raise ValueError(f"Driver codes are three letters, like VER; got {', '.join(bad_format)}")
...
    except (F1siDataError, SourceError) as err:
        if args.debug:
            raise
        print(str(err), file=sys.stderr)
        return 1
```
Library code raises `ValueError` (or a subclass such as `UnknownDriverError`); the CLI prints `str(err)` to stderr and returns 1, with `--debug` re-raising.

### Input validation of CLI-derived strings
**Source:** `src/f1si/plots/stints.py` lines 65-66, 111-122, 326-340
**Apply to:** `plan --driver`, wear/plan file names
```python
_CODE = re.compile(r"^[A-Z]{3}$")
_SLUG = re.compile(r"^[a-z0-9-]+$")
```
Upper-case the code, check format, then membership against the race's codes (sorted list in the error); build output file names from the catalog slug only, never raw user text.

### Frozen dataclasses with plain data results
**Source:** `_snapshot.py` lines 46-112; `stints.py` lines 78-89; `generator.py` lines 54-108 (`SyntheticRaceSpec`, `SyntheticTruth`, `SyntheticRace`)
**Apply to:** `FitReport`, `LinearPaceFit`, `CarState`, `RaceState`, `Plan`, `PitDecision`
`@dataclass(frozen=True)` for value objects; `eq=False` only when a field is a DataFrame; `tuple[...]` and `Mapping[...]` field types; `dataclasses.field(default_factory=...)` for mutable defaults (`generator.py` line 66).

### Docstrings state the math; module docstring explains the convention
**Source:** `generator.py` lines 1-28, `stints.py` lines 1-23, `_snapshot.py` lines 1-30
**Apply to:** every new module. Include the D-01 model, the "age at end of lap" convention, why fuel and wear separate (age resets at a stop, lap number does not), which values are placeholders (D-13), and which fields are `None` when unknown (D-23). Each public function documents `Raises:`.

### Typing and lint constraints
**Source:** `pyproject.toml` lines 37-50
**Apply to:** all new files. `line-length = 100`, ruff rules `E,W,F,I,B,UP,NPY,RUF,SIM,PT,N`, mypy `strict = true` over `src` and `tests`. Gotchas seen in existing code: pandas typing needs `# type: ignore[call-overload]` in `_typed` (`_snapshot.py` line 230); avoid single-letter uppercase variables (N806); use `zip(..., strict=True)` (B905); `Final` for module constants.

### Registered consumers, enforced by tests
**Source:** `tests/guards/consumers.py` and `tests/guards/test_consumer_registry.py`
**Apply to:** every public function or public method in a designated module that takes snapshot-derived data. See the dedicated section above.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Joint OLS with SVD rank/identification check (inside `pace/linear.py`) | service | transform | No regression or linear algebra exists in the repo. Use RESEARCH "Code Examples" (rank check naming unidentified parameters), `np.linalg.lstsq`, classical SE; rebuild the design matrix every trimming pass. |
| Enumeration/pricing of plans (`strategy/free_track.py` core) | service | batch | No enumeration code exists. Use RESEARCH Pattern 6 (closed-form stint cost, a slow lap-by-lap reference for tests, deterministic tie-breaking). |
| `tests/conformance/test_protocols.py` mypy-rejection proof | test | static | No `# type: ignore[arg-type]` rejection tests exist; there is only one `# type: ignore[attr-defined]` usage in `test_consumer_registry.py` line 86. Note A2 in RESEARCH: confirm `strict` implies `warn_unused_ignores` by running `uv run mypy` once. |
| `RaceState.from_json_dict` / `to_json_dict` | model | transform | No JSON round-trip of domain objects in src. Follow RESEARCH Pattern 4 (`allow_nan=False`, `None` not NaN, validate keys and raise `ValueError`). |
| Analytic 2-stop ground-truth case (D-24) | test | batch | The generator makes exactly one stop per driver (`generator.py` line 255-256), so the optimizer's truth must be hand-built (equal known slopes, known pit loss, closed-form optimum). |

## Metadata

**Analog search scope:** `src/f1si/**`, `tests/**`, `docs/explained/`, `DECISIONS.md`, `README.md`, `pyproject.toml` (89 tracked non-planning files listed via `git ls-files`)
**Files read in full or in targeted ranges:** `_snapshot.py`, `cli.py`, `plots/stints.py`, `synthetic/generator.py`, `tests/guards/{consumers,import_scan,scramble (lines 249-295),test_consumer_registry,test_meta_guard (1-70)}.py`, `tests/{test_docs,test_decisions_log,conftest}.py`, `tests/test_cli.py (1-60)`, `tests/plots/test_stint_plot.py (1-50, 160-191)`, `tests/test_synthetic.py (1-45)`, `tests/fixtures/leaky_consumer.py`, `docs/explained/phase-01.md (headings and tour)`, `DECISIONS.md (DEC-001..003, DEC-050, 051, 057-060)`, `rng.py`, `paths.py`, `synthetic/__init__.py`
**Not read (open before copying from them):** `tests/real/test_bahrain_2023.py`, `tests/guards/test_future_scramble.py` (hypothesis usage), `src/f1si/data/sources/synthetic_source.py` (how to feed a custom long spec into the loader), `tests/guards/test_import_ban.py`
**Pattern extraction date:** 2026-11-11
