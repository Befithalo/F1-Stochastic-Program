# Phase 10: Point-Mass PaceModel - Pattern Map

**Mapped:** 2026-11-17  
**Files analyzed:** 6 proposed implementation/test files plus existing conformance and decision artifacts  
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/f1si/pace/point_mass.py` | model / numerical utility | request-response | `src/f1si/pace/bayesian.py`, `src/f1si/geometry/profile.py` | role-match |
| `src/f1si/pace/point_mass_fit.py` (if kept separate) | model fitting / value types | batch transform | `src/f1si/pace/linear.py`, `src/f1si/pace/training.py` | role-match |
| `tests/pace/test_point_mass.py` | test | request-response | `tests/pace/test_bayesian_model.py` | strong |
| `tests/pace/point_mass_truth.py` (if split out) | test fixture / independent synthetic generator | transform | `tests/pace/test_linear_recovery.py`, `tests/pace/test_bayesian_recovery.py` | partial; independence is new |
| `tests/pace/test_point_mass_recovery.py` | synthetic recovery test | batch transform | `tests/pace/test_linear_recovery.py` | strong |
| `tests/conformance/test_point_mass_conformance.py` (or tests in the model test module) | contract test | request-response | `tests/conformance/suites.py`, `tests/pace/test_bayesian_model.py` | strong |
| `.planning/phases/10-point-mass-pacemodel/10-PHASE-REPORT.md` | report | batch/reporting | `.planning/phases/09-data-and-geometry-readiness/09-PHASE-REPORT.md` | strong |
| `DECISIONS.md` | method record | configuration/documentation | DEC-139 pattern / existing physics entries | strong |

All named analog source and test paths above are tracked by Git (`git ls-files` was checked during mapping); no generated runtime mirror is cited.

## Pattern Assignments

### `src/f1si/pace/point_mass.py` (model and solver, request-response)

**Analogs:** `src/f1si/pace/bayesian.py` (model contract), `src/f1si/geometry/profile.py` (immutable numeric input).

`BayesianPaceFit` is a frozen model object with a small prediction surface. Its method checks equal input shapes, rejects unseen categories, constructs float64 outputs, and returns a constant SD array:

```python
@dataclass(frozen=True)
class BayesianPaceFit:
    report: BayesianFitReport
    # immutable fitted values follow

def predict(self, *, driver, compound, tire_age, lap):
    if not (driver.shape == compound.shape == tire_age.shape == lap.shape):
        raise ValueError("driver, compound, tire_age and lap arrays must have equal shapes")
    # reject unknown values before indexing
    return mean, np.full(driver.shape, self.report.sigma_s, dtype=np.float64)
```

Source: `src/f1si/pace/bayesian.py:78-90,117-150`. Keep `point_mass.py`'s prediction signature identical to `PaceModel`; validate shapes and identifiers explicitly, keep all values finite/float64, and make repeated and scalar-batch calls deterministic. `PaceModel.predict` is already the seam; do not edit `src/f1si/interfaces.py` or consumer call sites.

The geometry value object provides the constructor pattern for ownership of numerical arrays:

```python
@dataclass(frozen=True, eq=False, init=False)
class GeometryProfile:
    # immutable metadata and arrays
    def __init__(self, manifest, validation, x_m, y_m, width_right_m, width_left_m):
        object.__setattr__(self, "manifest", manifest)
        object.__setattr__(self, "validation", validation)
        object.__setattr__(self, "_x_m", _read_only_array(x_m))
```

Source: `src/f1si/geometry/profile.py:119-144`. Consume the validated profile rather than loading/parsing the CSV in the pace model. Follow `profile.py:181-184` for immutable array ownership. Keep solver helpers pure and explicit about SI units; avoid hidden mutation or implicit re-smoothing of geometry.

### `src/f1si/pace/point_mass_fit.py` (optional separated fit code, batch transform)

**Analogs:** `src/f1si/pace/linear.py:133-221`, `src/f1si/pace/training.py:32-105`.

The linear model separates fitted value/report types from the routine that builds and fits design data. It records missing/identified terms rather than inventing coefficients; `LinearPaceFit.predict` refuses unidentified models and unknown drivers/compounds before returning predictions. The point-mass fit should similarly return an immutable parameter/report value with explicit identified composite terms, covariance/uncertainty diagnostics, units, and explicit unidentified terms. Do not give the fit a result/classification path or promote hidden absolute values into recovered values.

For real rows, build from a cutoff-safe `RaceSnapshot`/`PhysicsInput` before model construction. `fit_linear_pace(snapshot)` is the local entry pattern; `build_physics_input` makes the input boundary explicit:

```python
if snapshot.race.out_of_sample:
    raise ValueError("out-of-sample races cannot build PhysicsInput")
frames = {
    name: _cutoff_frame(getattr(snapshot, name), snapshot.cutoff_s)
    for name in _TIME_COLUMNS
}
```

Source: `src/f1si/data/physics_input.py:222-246`. Keep any fit/report preparation outside `predict`. If fitting can live cleanly in `point_mass.py`, the planner may omit the separate file; these are responsibilities, not a requirement to split modules.

### `tests/pace/test_point_mass.py` (unit, property, and contract tests)

**Analogs:** `tests/pace/test_bayesian_model.py:157-180`, `tests/conformance/suites.py:54-113`.

Use small deterministic geometry and typed NumPy input arrays. Existing model tests check same-shape finite predictions, strictly positive SD, protocol acceptance, deterministic repeat, and a shared `check_pace_model` call. The conformance helper additionally checks no input mutation and equal results between a batch call and per-element calls. Reuse the helper rather than inventing a second PaceModel contract suite.

The phase-specific test should separately check physical behavior: flat/constant-curvature analytic cases, increased drag/mass reducing speed, increased power/grip raising or preserving speed, lower curvature not increasing corner-speed restriction, closed-loop seam consistency, grid refinement, and validation errors. Assert directional/property outcomes instead of brittle exact lap times except for analytic fixtures.

### `tests/pace/point_mass_truth.py` and `tests/pace/test_point_mass_recovery.py` (test-only fixture and synthetic recovery)

**Analogs:** `tests/pace/test_linear_recovery.py:19-39,42-56`; `tests/pace/test_bayesian_recovery.py:15-28,73-140`.

The linear recovery test obtains known truth from `tests.conftest` and checks coefficient error against reported SE; the Bayesian recovery test creates a seeded synthetic panel and compares fitted values/coverage against a `SyntheticTruth` record. For the new model, put truth generation on the test side, preferably in a small `point_mass_truth.py`, and implement its forward equations independently from production solver functions. Store seed, truth, geometry excitation, noise scale, and units explicitly. Recovery tests must estimate only the preregistered identifiable composite basis and should include a rank/conditioning or deliberate non-identifiability case; a recovery test that generates targets by calling production solver code is not independent.

Reuse the existing pytest fixture conventions, NumPy `default_rng(seed)`, plain typed truth records, and tolerance checks. Keep the synthetic test out of the production `f1si` package.

### Conformance registry (only if the new model is added to the shared registry)

**Analog:** `tests/conformance/registry.py:124-139,202-205`.

`PACE_MODELS` maps a short name to a factory returning `(PaceModel, PaceProbe)`. A geometry-backed model factory would need a valid profile/parameter fixture; the existing registry uses the long synthetic cache for the linear implementation. Avoid adding Phase 10 fitting to the registry if a direct `check_pace_model` invocation from `test_point_mass.py` covers it. Do not alter the production conformance contract.

## Shared Patterns

### Immutable, prepared construction inputs

**Sources:** `src/f1si/geometry/profile.py:119-184`; `src/f1si/data/physics_input.py:143-167`. Geometry and race inputs are frozen/copy-owning, and public frame access returns defensive copies. Bind validated geometry and physics context once at model construction; prediction must not access DuckDB, source APIs, mutable race snapshots, or filesystem paths.

### Fail closed on invalid evidence and unknown categories

**Sources:** `src/f1si/geometry/profile.py:209-249`; `src/f1si/pace/linear.py:197-215`; `src/f1si/data/physics_input.py:227-246`. Reject bad digest/units, out-of-sample context, invalid parameter values, unidentified fits, and unknown driver/compound inputs with a named exception. Do not silently fall back to Bayesian pace or fill missing physics values with a guessed team value.

### Deterministic vectorized prediction

**Sources:** `src/f1si/interfaces.py:150-165`; `src/f1si/pace/bayesian.py:117-150`; `tests/conformance/suites.py:67-113`. Keep mean and SD arrays float64 and input-shaped, use no random generator inside `predict`, preserve inputs, and guarantee per-row results do not depend on batch size.

### Reproducible, honest synthetic recovery

**Sources:** `tests/pace/test_linear_recovery.py:24-56`; `tests/pace/test_bayesian_recovery.py:26-140`. Fix seeds and store synthetic truth. For Phase 10 additionally require an independent test-side generator, a declared effective parameter basis, identifiability checks, and no claim that synthetic recovery proves real-data validity.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/pace/point_mass_truth.py` | independent synthetic generator | transform | Existing fixtures generate pace targets but none generate a closed-loop vehicle speed envelope independently of production code. |

## Metadata

**Analog search scope:** `src/f1si/pace/`, `src/f1si/geometry/`, `src/f1si/data/`, `src/f1si/parameters/`, `tests/pace/`, `tests/conformance/`.  
**Files scanned:** 15 relevant source/test files.  
**Pattern extraction date:** 2026-11-17
