# Phase 9: Data and Geometry Readiness - Pattern Map

**Mapped:** 2026-11-17  
**Files analyzed:** 11 likely new or modified files  
**Analogs found:** 9 / 11 (no existing geometry or parameter-register module)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/f1si/data/schema.py` (modify) | model/schema | transform | `src/f1si/data/schema.py` existing time-table specs | exact |
| `src/f1si/data/sources/openf1.py` (modify) | source/adapter | request-response, transform | `src/f1si/data/sources/openf1.py` weather/lap normalization | exact |
| `src/f1si/data/_snapshot.py` (modify) | service/access layer | CRUD/read, transform | existing `_visible_rows` / `build_snapshot` | exact |
| `src/f1si/data/asof.py` (modify) | accessor | request-response | existing `AsOfAccessor` | exact |
| `src/f1si/data/physics_input.py` (new) | service/builder, immutable model | transform | `src/f1si/pace/training.py` panel builder | role-match |
| `src/f1si/geometry/profile.py` (new; recommended location) | model/validator | file-I/O, transform | `src/f1si/data/schema.py` normalization and validation; no geometry analog | partial |
| `src/f1si/parameters/register.py` (new; recommended location) | model/registry | transform | `src/f1si/pace/linear.py` fit report and identifiability | partial |
| `tests/data/test_physics_input.py` (new) | test | transform | `tests/data/test_asof.py` and `tests/guards/test_future_scramble.py` | role-match |
| `tests/geometry/test_profile.py` (new) | test | file-I/O | `tests/data/test_schema.py` | partial |
| `tests/parameters/test_register.py` (new) | test | transform | `tests/pace/test_identification.py` | role-match |
| `src/f1si/data/parameter_report.py` or report artifact (undecided) | utility/report | transform | `src/f1si/pace/linear.py` FitReport | role-match |

The first nine new/modified paths are directly named or strongly implied by CONTEXT.md/RESEARCH.md and the validation strategy. The final parameter report path is only a possible implementation seam: no report output location is specified. Planner should avoid committing to a separate file unless needed; the register may itself provide serialization.

## Pattern Assignments

### `src/f1si/data/schema.py` (model/schema, transform)

**Analog:** same file, tracked. New time-indexed channels should follow `TableSpec` and `_col`.

**Time-table declaration pattern** (lines 190-208):
```python
_WEATHER = TableSpec(
    name="weather",
    columns=(
        _col("race_id", "VARCHAR", required=True),
        _col("seq", "INTEGER", required=True),
        _col("t_s", "DOUBLE", required=True),
        _col("air_temp_c", "DOUBLE"),
        _col("track_temp_c", "DOUBLE"),
        _col("humidity_pct", "DOUBLE"),
        _col("pressure_mbar", "DOUBLE"),
        _col("rainfall", "BOOLEAN"),
        _col("wind_speed_ms", "DOUBLE"),
        _col("wind_direction_deg", "DOUBLE"),
        _col(VISIBILITY_COLUMN, "DOUBLE"),
    ),
    key=("race_id", "seq"),
    visibility="time",
    time_column="t_s",
)
```

Rows need explicit units and a unique key, plus race-clock time, source UTC timestamp, and visibility time if those fields are added. The canonical schema currently has only INTEGER/DOUBLE/BOOLEAN/VARCHAR/TIMESTAMP types and coerces TIMESTAMP input to UTC. New tables must be included in `TABLES` and thus `PER_RACE_TABLES`; validate source completeness and keys using `validate_race`.

---

### `src/f1si/data/sources/openf1.py` (source/adapter, request-response + transform)

**Analog:** same file, tracked; `_build_weather` and existing rate-limited client seam.

**Cache request + session clock** (lines 283-308):
```python
weather_raw = self._rows("/weather", params, freshness=fresh)
...
lap_one = [lap.start for lap in laps_in if lap.lap == 1 and lap.start is not None]
t0 = min(lap_one) if lap_one else pd.to_datetime(ref.race_start_utc, utc=True)
...
weather = _build_weather(ref, weather_raw, t0)
```

**Validation and source errors** (`_stamp`, lines 68-80):
```python
def _stamp(value: object, path: str, what: str) -> pd.Timestamp | None:
    """A UTC timestamp from ISO 8601 text; None for null."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise _unexpected(path, f"{what} is not a timestamp ({value!r})")
    try:
        parsed = pd.to_datetime(value, utc=True, format="ISO8601")
    except (ValueError, TypeError):
        raise _unexpected(path, f"{what} is not a timestamp ({value!r})") from None
    return None if pd.isna(parsed) else parsed
```

**Normalized channel conversion** (lines 694-735):
```python
for seq, (when, _, row) in enumerate(parsed):
    rain = _number(row.get("rainfall"), path, "rainfall")
    out.append(
        {
            "race_id": ref.race_id,
            "seq": seq,
            "t_s": _seconds(when, t0),
            "air_temp_c": _number(row.get("air_temperature"), path, "air_temperature"),
            "track_temp_c": _number(row.get("track_temperature"), path, "track_temperature"),
            "humidity_pct": _number(row.get("humidity"), path, "humidity"),
            "pressure_mbar": _number(row.get("pressure"), path, "pressure"),
            "rainfall": None if rain is None else rain > 0,
            "wind_speed_ms": _number(row.get("wind_speed"), path, "wind_speed"),
            "wind_direction_deg": _number(row.get("wind_direction"), path, "wind_direction"),
        }
    )
```

For telemetry/location, keep original parsed UTC timestamps alongside `_seconds(when, t0)`; preserve input ordering deterministically when timestamps tie. Reuse `self._rows(path, params, freshness=fresh)` (it calls the shared `RateLimitedClient`) so optional data remain cached/rate-limited. Handle absent endpoints as empty optional coverage, not fabricated values. The source currently requests five OpenF1 endpoints in `_RACE_PATHS`; updating cache discard paths must include added endpoints.

---

### `src/f1si/data/_snapshot.py` + `src/f1si/data/asof.py` (access layer, request-response)

**Analog:** tracked `_visible_rows`, `build_snapshot`, and `AsOfAccessor`.

**Cutoff predicate** (`_visible_rows`, lines 218-230):
```python
sql = (
    f"SELECT * FROM {table} WHERE race_id = ? "
    f"AND visible_at_s IS NOT NULL AND visible_at_s <= ? ORDER BY {order}"
)
params = [race_id, cutoff_s]
```

**Snapshot receives normalized plain frames** (`build_snapshot`, lines 427-444):
```python
frames = {t: _visible_rows(db_path, t, info.race_id, cutoff_s, con) for t in _TIME_TABLES}
laps = frames["laps"]
...
return RaceSnapshot(
    race=info,
    at=at,
    cutoff_s=cutoff_s,
    entries=entries,
    laps=laps,
    track_status=frames["track_status"],
    race_control=frames["race_control"],
    weather=frames["weather"],
    stints=rebuild_stints(derived_laps, cutoff_s=cutoff_s),
    pit_events=rebuild_pit_events(derived_laps),
    cars=rebuild_cars(derived_laps, entries),
)
```

**Public door** (`asof.py`, lines 86-105):
```python
def snapshot(self, at: AsOf) -> RaceSnapshot:
    ...
    from f1si.data import _snapshot  # local import: not a module attribute (CR-01)
    return _snapshot.guarded_snapshot(self._db_path, at, self._check)

def history(self, at: AsOf) -> History:
    ...
    from f1si.data import _snapshot  # local import: not a module attribute (CR-01)
    return _snapshot.guarded_history(self._db_path, at, self._check)
```

Append new time tables to `_TIME_TABLES`, snapshot fields, and `History` only if appropriate. Preserve the same single read connection and exact `visible_at_s IS NOT NULL AND visible_at_s <= cutoff` rule. Keep access behind `AsOfAccessor` so physics input assembly cannot fetch from the cache itself.

---

### `src/f1si/data/physics_input.py` (service/builder, transform)

**Analog:** tracked `src/f1si/pace/training.py`, a cutoff-safe data panel builder; related immutable values in `src/f1si/data/_snapshot.py`.

**Imports, immutability, and error type** (`training.py`, lines 3-38):
```python
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
import pandas as pd

from f1si.data.asof import History, RaceSnapshot
...
class PaceTrainingError(ValueError):
    """Raised when as-of laps cannot be joined into a trustworthy pace panel."""

@dataclass(frozen=True, eq=False)
class BayesianTrainingPanel:
    rows: pd.DataFrame
    category_indexes: Mapping[str, Mapping[str, int]]
...
```

**Input-only builder and out-of-sample guard** (`training.py`, lines 104-121):
```python
def build_bayesian_training_panel(
    snapshot: RaceSnapshot,
    history: History | None = None,
) -> BayesianTrainingPanel:
    current_race = snapshot.race.race_id
    current_era = era_for_season(snapshot.race.season)
    if current_era.out_of_sample:
        raise PaceTrainingError(f"out-of-sample era {current_era.name!r} cannot train pace")
    if history is not None and history.as_of.race_id != current_race:
        raise PaceTrainingError("History and RaceSnapshot must refer to the same current race")
```

Builder should receive snapshot and validated geometry/parameter objects, return immutable prepared values, and be called before constructing the model. Treat any frames/arrays inside frozen dataclasses carefully: pandas frames remain mutable; copy them or expose immutable tuple/array representations if the contract requires deep immutability. Do not include an accessor, DB path, or cache capability. Preserve `PaceModel.predict` in `src/f1si/interfaces.py` unchanged.

---

### `src/f1si/geometry/profile.py` (model/validator, file-I/O + transform)

**Analog:** none for track geometry. Closest tracked analog: `src/f1si/data/schema.py` `normalize` / `validate_race`, which validates typed values, required fields, keys, and ranges.

**Schema validation pattern** (`schema.py`, lines 340-350):
```python
def normalize(table: str, df: pd.DataFrame) -> pd.DataFrame:
    """Return df with exactly the table's columns, in order, in the canonical dtypes."""
    spec = _spec(table)
    if spec.visibility == "time" and VISIBILITY_COLUMN not in df.columns:
        df = add_visibility(table, df)
    missing = [c.name for c in spec.columns if c.name not in df.columns]
    if missing:
        raise KeyError(f"table {table!r} is missing column(s): {', '.join(missing)}")
    out = pd.DataFrame({c.name: _cast(df[c.name], c.sql_type) for c in spec.columns})
    return out.reset_index(drop=True)
```

Geometry validation is a new domain. Use explicit typed metadata (source/revision, attribution/rights decision, units, frame/transform, digest, validation version/results). Compute SHA-256 against raw bytes and fail with a project-specific ValueError when the path is missing, digest differs, or checks fail. A digest verifies identity only; it does not establish redistribution rights. No bundled Bahrain asset is currently tracked or available in the project.

---

### `src/f1si/parameters/register.py` (model/registry, transform)

**Analog:** none for an assumptions register. Closest tracked analogs: `src/f1si/pace/linear.py` `FitReport` / `CompoundFit`; tests in `tests/pace/test_identification.py`.

**Plain report records** (`linear.py`, lines 65-111):
```python
@dataclass(frozen=True)
class CompoundFit:
    compound: str
    wear_s_per_lap: float
    se: float
    ci_low: float
    ci_high: float
    n_laps: int
    n_stints: int

@dataclass(frozen=True)
class FitReport:
    fuel_s_per_lap: float | None
    fuel_se: float | None
    fuel_ci_low: float | None
    fuel_ci_high: float | None
    compounds: tuple[CompoundFit, ...]
    not_enough_data: tuple[str, ...]
    unidentified: tuple[str, ...]
    ...
```

**Fail closed when rank/data cannot identify terms** (`linear.py`, lines 448-474):
```python
if rank < p or cond > COND_LIMIT:
    ...
    return _unidentified(
        n,
        _dropped(final_reason, design),
        tuple(design.not_enough),
        tuple(bad),
        "these parameters cannot be separated with the laps visible so far: " + ", ".join(bad),
        df_resid=n - p,
        n_trimmed=n_trimmed,
    )
```

Represent fitted effective composites separately from assumptions. Store evidence/reference, season/era bounds, uncertainty, sensitivity status/result version, and a clear identifiability class. Avoid naming absolute mass/power/aero/grip/fuel/tire values as recovered when only a composite is fitted. No parameter register exists in tracked source.

---

### Tests

#### `tests/data/test_physics_input.py` (test, transform)

**Analog:** tracked `tests/data/test_asof.py` and `tests/guards/test_future_scramble.py`.

**Exact cutoff assertions** (`test_asof.py`, lines 38-45):
```python
snap = accessor.snapshot(AsOf("2023-01", lap))
expected = float(cutoffs.loc[cutoffs["lap"] == lap, "cutoff_s"].iloc[0])
assert snap.cutoff_s == expected
assert bool((snap.laps["lap_end_s"] <= expected).all())
done = snap.cars["laps_done"].astype(int)
assert sorted(done.tolist()) == [lap - 1] * 5 + [lap]
```

Add exact-boundary inclusion, future-row exclusion/perturbation, original UTC timestamp round-trip, channel coverage/status, optional-channel emptiness and cached-lap fallback. Include separate assertions that current-race results and 2026 holdout cannot enter M2 fitting.

#### `tests/geometry/test_profile.py` (test, file-I/O)

**Analog:** tracked `tests/data/test_schema.py`; no geometry test analog exists. Follow its fixture-driven invalid-shape/type/error checks. Cover digest mismatch, missing asset, malformed/nonfinite coordinates, degenerate segments, closure/distance/width/curvature checks, units and transform provenance. Test bundle metadata as data; manual review is required for actual redistribution terms.

#### `tests/parameters/test_register.py` (test, transform)

**Analog:** tracked `tests/pace/test_identification.py`.

**No-number behavior when not identifiable** (lines 19-31):
```python
fit = _fit(long_synthetic_db, 20)
r = fit.report
assert not fit.is_identified
assert r.fuel_s_per_lap is None
assert r.fuel_se is None
assert "fuel effect" in r.unidentified
...
with pytest.raises(ValueError, match="not identified"):
    fit.predict(...)
```

Test classification as fitted-effective vs hidden assumption, mandatory evidence and bounds, uncertainty, sensitivity status/version, and ensure assumptions are never serialized as team-specific measured values.

#### `src/f1si/data/parameter_report.py` (utility/report; optional)

No explicit path is locked. If planner chooses a separate report serializer, reuse the immutable plain-record style in `FitReport`; do not create parallel schemas for the same register.

## Shared Patterns

### Cutoff safety and source provenance

**Sources:** `src/f1si/data/schema.py`, `src/f1si/data/sources/openf1.py`, `src/f1si/data/_snapshot.py`  
**Apply to:** new telemetry/location/weather table records, as-of snapshot and physics-input builder.

- Store source UTC time unchanged and mapped race-clock seconds relative to lights out.
- The snapshot predicate is exactly `visible_at_s IS NOT NULL AND visible_at_s <= cutoff_s`; do not interpolate or silently include rows after cutoff.
- Reuse the existing source's `_rows` / rate-limited cache seam.
- Missing optional channels are reported as unavailable/sparse; cached laps remain the fallback.

### Immutable construction before model execution

**Sources:** `src/f1si/pace/training.py`, `src/f1si/interfaces.py`  
**Apply to:** physics-input builder and parameter/geometry values passed to it.

Pass plain records into construction before simulation. No model method should import or receive `AsOfAccessor`, DuckDB paths, or source clients. Keep the `PaceModel.predict` argument/return signature intact. Use defensive copies or immutable primitive collections for deep immutability.

### Fail-closed evidence and access controls

**Sources:** `src/f1si/data/asof.py`, `src/f1si/data/out_of_sample.py`, `src/f1si/pace/training.py`, `src/f1si/pace/linear.py`  
**Apply to:** physics input, geometry loader, and parameter register.

Reject 2026/out-of-sample fitting inputs and unavailable/invalid/mismatched geometry before model use. Identify an estimate as unavailable when evidence or rank is insufficient. A digest and regulatory constraint are not, respectively, redistribution permission and measured team parameters.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/f1si/geometry/profile.py` | model/validator | file-I/O | No geometry artifact or geometry loader exists in tracked source. |
| `src/f1si/parameters/register.py` | model/registry | transform | No parameter-assumption register exists; nearest fit-report analog covers only fitted pace effects. |
| `tests/geometry/test_profile.py` | test | file-I/O | No geometry-specific test suite exists. |

## Metadata

**Analog search scope:** `src/f1si/data/`, `src/f1si/pace/`, `src/f1si/interfaces.py`, `tests/data/`, `tests/pace/`, `tests/guards/`, phase 09 context/research/validation.  
**Files scanned:** 14 source/test candidates; tracked status checked with `git ls-files` for every named analog.  
**Pattern extraction date:** 2026-11-17

