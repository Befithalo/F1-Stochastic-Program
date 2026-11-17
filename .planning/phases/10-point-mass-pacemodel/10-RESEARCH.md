# Phase 10: Point-Mass PaceModel - Research

**Researched:** 2026-11-17  
**Domain:** Reduced-order vehicle dynamics and deterministic lap-time prediction  
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

All gray areas were selected in one pass using `gsd-discuss-phase 10 --auto`. The user authorized the assistant's recommended defaults and no clarification is needed.

### Lap solver and track representation
- **D-01:** Use a quasi-static point-mass lap solver over the pinned, immutable centerline profile. Compute a closed-lap speed envelope from curvature-limited cornering speed, effective drive force, aerodynamic drag/downforce, grip, and declared mass/fuel; include longitudinal acceleration and braking limits, then integrate segment distance over speed to get lap time. Keep the solver deterministic and document the reduced-order assumptions. Research/planning may refine numerical integration and convergence tolerances without changing this scope.

### Effective parameters and hidden assumptions
- **D-02:** Fit only parameters that the available evidence can identify as effective composites (for example, power-to-mass or drag-to-mass terms). Keep absolute team car mass, power, drag area, downforce, and tire friction as versioned, season-bounded assumptions unless independent data identify them. Use the Phase 9 parameter register and its provenance; do not claim synthetic recovery of non-identifiable absolute values as real-world measurement.

### Prediction uncertainty
- **D-03:** Preserve deterministic `PaceModel.predict`: return reproducible mean and standard deviation without sampling or runtime cache access. Represent epistemic uncertainty through documented effective-parameter uncertainty propagation and include a separate, cutoff-safe training-data residual component where estimable. Do not fit uncertainty against Phase 12 holdout targets or include tire-state uncertainty before Phase 11.

### Recovery and physical validation
- **D-04:** Generate synthetic trajectories from known identifiable parameters with a test-side forward generator that is separately implemented from the production solver. Require recovery within declared tolerances, physical invariants (finite positive times, speed/force limits, closed-loop consistency), independent changes to track shape and each identifiable parameter, and convergence checks. Synthetic tests validate implementation only; real-data claims remain separate.

### Integration and failure behavior
- **D-05:** Bind a validated geometry profile, immutable `PhysicsInput`, and declared parameter context when constructing the model, outside the prediction hot path. Keep the exact `PaceModel.predict` signature and all existing consumers unchanged. Fail clearly on missing, digest-invalid, or physically invalid required inputs; do not silently substitute the Bayesian model or invent missing geometry.

### the agent's Discretion
- Choose the concrete state/parameter schema, equations and units after technical research, numerical tolerances, optimizer or direct solver details, deterministic uncertainty propagation method, fit diagnostics, and tests, provided D-01–D-05 and PHY-01/PHY-02 remain satisfied.
- Use only cutoff-safe 2023–2025 training evidence for any real-data fit in this phase. Preserve the separate 2026 report and all locked M1/M2 comparison data from tuning.
- Copy the fixed M1 baseline into phase closeout; do not recompute it. Maintain the 50,000-race budget and add no UI/UX work.

### Deferred Ideas (OUT OF SCOPE)
- Tire temperature, energy-driven wear, and compound resets belong to Phase 11.
- Bayesian residual learning and the real held-out-stint gate belong to Phase 12.
- Full-circuit geometry coverage, detailed transient/multibody vehicle dynamics, private team parameter recovery, and UI/UX are out of scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PHY-01 | A user can obtain a deterministic lap-time mean and uncertainty from track distance/curvature, effective drive power, drag, downforce, grip, and declared mass/fuel inputs through the existing `PaceModel` contract. | Use the prevalidated Sakhir profile and immutable race context; compute a deterministic quasi-static speed envelope and lap-time integral; derive uncertainty from effective-parameter covariance plus cutoff-safe residual noise. |
| PHY-02 | A user can verify the point-mass model's recovered identifiable parameters and physical invariants using synthetic known-parameter trajectories and independent parameter/track sensitivity checks. | Use an independently implemented test-side trajectory generator; recover only identifiable composites; test closed-loop convergence, positive finite times, force/speed bounds, grid/track sensitivity, and finite-difference parameter sensitivities. |
</phase_requirements>

## Summary

The most suitable Phase 10 design is a small deterministic solver that works along the existing Sakhir centerline and models one fixed driving line. A quasi-steady point-mass speed envelope is consistent with the phase contract and the published TUMFTM reference family; a full transient vehicle simulator, race-line optimizer, and new runtime package would expand scope without improving the required PaceModel seam. The TUMFTM repository explicitly warns that curvature smoothing affects lap-time results, so the solver should consume the quality-checked, digest-pinned profile and include resolution/smoothing sensitivity checks. [CITED: https://github.com/TUMFTM/laptime-simulation]

Use NumPy/SciPy already in the project for geometry arrays, the envelope passes, integration, and local sensitivity calculations. Keep the model object immutable after construction: it holds validated geometry, cutoff-visible `PhysicsInput`, and a versioned parameter context. Its vectorized `predict` method should do no I/O, draw no randomness, and preserve the exact protocol. The existing data cache contains no car-data or location rows; Phase 9 also recorded a one-time historical Bahrain probe. This leaves cached lap times and explicit assumptions as the default calibration basis; optional, already-available OpenF1 evidence can add diagnostics, but no new FastF1 download or repeated probe should be a dependency. [VERIFIED: `.planning/phases/09-data-and-geometry-readiness/09-PHASE-REPORT.md:13-20` — “Car: 0 races / 0 rows.” / “GPS: 0 races / 0 rows.” / “Single bounded Bahrain 2023 probe.”]

Parameter recovery from synthetic paths demonstrates that the implementation can recover the model's identifiable combinations. It does not establish that public data identify absolute team mass, power, drag area, downforce, or grip. Those values remain assumptions unless independent evidence resolves their confounding. For `sd_s`, propagate the fitted/declared parameter covariance through the deterministic solver and add a separately estimated, cutoff-safe residual term where supported. NIST's uncertainty guidance supports first-order sensitivity/covariance propagation when linearization is adequate and documented numerical propagation where it is not. [CITED: https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-law-propagation-uncertainty]

**Primary recommendation:** implement one tested NumPy reference path first; keep solver construction outside simulator loops; validate on analytic/simple synthetic geometry and independent generated speed/lap-time data; add optional Numba only if end-to-end profiling shows the 50,000-race budget is threatened. Do not add dependencies.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Track-profile validation and curvature input | Geometry/data layer | Pace model construction | Phase 9 already owns immutable, versioned geometry; the solver should not parse assets. |
| Vehicle force envelope and lap-time integration | `src/f1si/pace/` | NumPy/SciPy numerical routines | This is the Phase 10 pace algorithm and belongs behind the existing model protocol. |
| Effective-parameter fit and assumptions | Parameter/model-construction layer | As-of data boundary | Fits use only permitted historical training evidence; hidden values remain declared assumptions. |
| Deterministic pace mean/SD | `PaceModel.predict` | Simulator sampling | The model returns means and standard deviations; the simulator remains the stochastic consumer. |
| Synthetic recovery and physical behavior | `tests/pace/` | `tests/conformance/` | Phase-specific tests establish equations/recovery; shared conformance verifies the unchanged protocol. |

## Standard Stack

### Core

| Library | Version constraint in project | Purpose | Why Standard |
|---------|--------------------------------|---------|--------------|
| Python | `>=3.12,<3.13` | Immutable model/value types and solver | Existing project runtime. |
| NumPy | `>=2.3,<3` | Vectorized geometry, speed profiles, and covariance propagation | Already a runtime dependency; enough for the reference implementation. |
| SciPy | `>=1.15,<2` | Optional established numerical routines for local optimization or diagnostics | Already a runtime dependency; use only if direct fitting needs it. |
| pytest + Hypothesis | `pytest>=9.1,<10`, `hypothesis>=6.170` | Deterministic unit/property and synthetic recovery tests | Existing test stack. |

The exact dependency declarations are in `pyproject.toml`: `requires-python = ">=3.12,<3.13"`, `"numpy>=2.3,<3"`, `"scipy>=1.15,<2"`, `"pytest>=9.1,<10"`, and `"hypothesis>=6.170"`. [VERIFIED: `pyproject.toml:6-8,17,34-35`]

### Supporting

| Library | Version constraint | Purpose | When to Use |
|---------|--------------------|---------|-------------|
| Numba | `>=0.68,<1` | Optional compiled envelope/integration kernel | Only after profiling proves the plain NumPy implementation cannot meet the existing budget. |
| DuckDB/as-of accessor | Existing project dependency | Load permitted race snapshots and lap training data outside `predict` | Model fitting/report preparation only, never inside the solver prediction path. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Deterministic quasi-static point-mass envelope | Full transient multibody or optimal-control solver | Higher fidelity requires substantially more states/data/compute and is explicitly out of scope. |
| Existing NumPy/SciPy | CasADi/IPOPT or a new vehicle-simulation package | Adds an unneeded runtime dependency and makes the 50,000-race integration harder to audit. |
| Effective composite fit plus disclosed assumptions | Per-team absolute physical parameter fit | Lap-time and sparse telemetry evidence are insufficient to identify all hidden quantities independently. |

**Installation:** none. Keep the existing lockfile unchanged unless a separately justified need emerges.

## Architecture Patterns

### Recommended model path

```text
AsOfAccessor snapshot + pinned GeometryProfile + ParameterRegister
                 │ model construction (outside predict / simulation loops)
                 ▼
     immutable PointMassPaceModel context
                 │
                 ├─ curvature and distance profile
                 ├─ effective/assumed parameters with provenance
                 ├─ quasi-static cornering and longitudinal force envelope
                 └─ deterministic lap-time mean + uncertainty components
                              │
                              ▼
                 PaceModel.predict(driver, compound, tire_age, lap)
```

`PaceModel.predict` is the only consumer-facing integration point. The repository defines its exact method as:

```python
def predict(
    self,
    *,
    driver: NDArray[np.int64],
    compound: NDArray[np.str_],
    tire_age: NDArray[np.int64],
    lap: NDArray[np.int64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
```

The protocol docstring says it returns same-shape float64 arrays and that the model “never samples and never reads the data accessor.” [VERIFIED: `src/f1si/interfaces.py:150-165`]

### Recommended solver procedure (planning-level)

1. Consume the Sakhir profile's precomputed distances and smoothed curvature; do not recompute geometry from approximate OpenF1 location.
2. Convert declared parameters to force/acceleration quantities with unit-checked, finite inputs. For each spatial segment, compute a lateral-grip speed cap and longitudinal drive/braking limits that account for power limits, drag, and downforce.
3. Enforce acceleration and braking reachability in both directions around the closed lap until the start/finish speed profile is self-consistent. Explicitly define convergence tolerance, maximum iterations, low-speed handling, and the zero-curvature/top-speed case.
4. Integrate segment time over the converged speed profile, with a documented endpoint rule and a hard error for invalid/nonpositive speed intervals.
5. Build a deterministic uncertainty result from effective parameter covariance and residual variation; expose component diagnostics at construction/report time, not through mutable prediction side effects.

This specific forward/backward implementation is a recommendation, not a verbatim claim about a required solver algorithm. It is consistent with the TUMFTM quasi-steady lap-simulation scope; its public README also separates track/raceline preparation from lap simulation and calls out sensitivity analysis and curvature smoothness. [CITED: https://github.com/TUMFTM/laptime-simulation] The 3D racing-planning paper describes a quasi-steady point-mass model constrained by acceleration envelopes; it also discusses vertical and track-frame effects, which Phase 10's planar Sakhir model must explicitly exclude. [CITED: https://arxiv.org/abs/2304.10954]

### Parameter identifiability

**Inference from the selected force model:** observed acceleration constrains force-to-mass combinations; cornering constrains a combined grip/load response. Multiple absolute mass, power, drag, and downforce values can produce similar trajectories. Use a rank/condition-number or profile-likelihood check for every fitted composite. If the real observations do not distinguish a term, keep it in the parameter register as an assumption. A synthetic test can prove recovery only for a deliberately identifiable parameterization.

Phase 9 confirms this is consequential: its lap-number pace effect is an observational coefficient and the report explicitly says predictive lap-time sensitivity was `not_estimable_pre_solver`. The report's numerical screen is not a physical calibration result. [VERIFIED: `.planning/phases/09-data-and-geometry-readiness/09-PHASE-REPORT.md:3-11` — “The screen measures coefficient stability; it does not recover physical parameters.”]

### Uncertainty propagation

For a solver `t = f(θ, g, x)` with effective parameters `θ`, geometry terms `g`, and fixed as-of inputs `x`, use deterministic covariance propagation `Var(t) ≈ J Σ Jᵀ` as a baseline when the local linear approximation is sound. Include parameter covariance, geometry resolution/curvature uncertainty when quantified, and a distinct residual variance from eligible training data. If active constraints change or curvature/parameter uncertainty makes the approximation unreliable, compare against a deterministic bootstrap or fixed quadrature offline and document the chosen method. NIST explains that the first-order propagation uses sensitivity derivatives plus input variances/covariances and only corresponds to standard uncertainty under its stated assumptions. [CITED: https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-law-propagation-uncertainty] Do not count the same residual spread both in parameter covariance and residual noise.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|------------|-------------|-----|
| Geometry validation, digest, transform, immutable arrays | Another loader or unverified track parser in the pace model | `GeometryProfile` from `src/f1si/geometry/profile.py` | Existing artifact already owns provenance, quality, and immutable geometry. |
| Cutoff-safe race context and optional channel status | DB/cache reads inside `predict` | `AsOfAccessor`/`PhysicsInput` built before model construction | Preserves visibility and prevents hot-path I/O/lookahead. |
| Hidden/effective distinction | A one-off set of undocumented car constants | Phase 9 `ParameterRegister` | Register carries classification, provenance, ranges, uncertainty, and sensitivity status. |
| Uncertainty propagation | A hand-coded ad hoc sum of standard deviations | Covariance-aware law of propagation or a documented numeric equivalent | Correlated inputs require covariance terms; verify linearization where active constraints are present. |
| External solver internals | Copying TUMFTM source or model files | Reimplement the scoped equations and cite the method | TUMFTM repository identifies itself as LGPL-3.0; copying invokes separate license obligations. [CITED: https://github.com/TUMFTM/laptime-simulation] |

## Common Pitfalls

### Curvature noise and seam errors
**What goes wrong:** Small geometry oscillations create excessive corner-speed caps and inflate lap time; a discontinuity at the start/finish seam breaks the supposedly closed speed profile.  
**Why:** Curvature is a second-derivative quantity and amplifies coordinate noise. The TUMFTM README explicitly cautions that curvature smoothness strongly affects simulation results. [CITED: https://github.com/TUMFTM/laptime-simulation]  
**How to avoid:** Use the validated, already smoothed profile; preserve the digest; test curvature resolution and seam continuity. Don't silently smooth new geometry inside the solver.  
**Warning signs:** Lap time changes substantially with resampling, a spike appears at the seam, or a short isolated geometry kink causes a large speed drop.

### Inconsistent force/energy units and low speed
**What goes wrong:** Power divided by speed explodes near standstill; wrong km/h/m/s or kW/W conversion gives plausible but incorrect lap times.  
**How to avoid:** Validate units at model construction, use a low-speed traction-limited branch, reject nonfinite or nonpositive parameters, and include unit-equivalence tests.

### Open track boundary treated as a closed lap
**What goes wrong:** A first-point-only acceleration pass leaves an impossible start/finish speed, changing times at the seam.  
**How to avoid:** Iterate the two reachability passes around the cyclic seam to a documented tolerance and test start/finish speeds agree.

### Confounding reported as recovery
**What goes wrong:** Synthetic recovery returns absolute vehicle values even though only combinations can be identified from the chosen observations.  
**How to avoid:** Declare the fitted parameter basis first; test the generator/model pair on independent excitation; evaluate rank/conditioning on real fit data; preserve unidentifiable values as assumptions.

### Uncertainty double-counting or nonlinearity
**What goes wrong:** Parameter and residual uncertainties are summed as if independent, or first-order propagation is trusted across a force-envelope regime switch.  
**How to avoid:** Record covariance and components, inspect solver regime changes, and compare linear propagation with deterministic bootstrap/quadrature for a fixed validation set.

### Cutoff and holdout leakage
**What goes wrong:** The fit uses results, future laps, the M1 PAC-06 lock, 2026, or Phase 12 holdout outcomes.  
**How to avoid:** Source all real fit rows through the as-of boundary, retain row provenance, restrict to approved 2023–2025 training evidence, and add future-row perturbation tests. Do not rerun or open locked outcome files during tuning.

### Hot-path physics work
**What goes wrong:** Geometry/parameter loading and repeated solver calls land inside per-simulation predictions and breach the existing simulation budget.  
**How to avoid:** Construct once, precompute speed/time maps by relevant immutable parameter context, and benchmark full integration; only optimize after a correct reference path exists.

## Code Examples

### Spatial reachability sketch

The following is a planning-level kinematic identity, not copied source code. Derive the exact force terms from the documented parameterization and verify units before implementation:

```text
corner_speed_i^2 <= lateral_acceleration_limit_i / abs(curvature_i)
v_next^2 <= v_i^2 + 2 * drive_acceleration_i * ds
v_i^2 <= v_next^2 + 2 * braking_deceleration_i * ds
lap_time = sum(2 * ds / (v_i + v_next))
```

Use a finite top-speed / power-limited condition where curvature is effectively zero; define the zero-speed integration case instead of dividing by zero. Include downforce in normal load and reserve combined longitudinal/lateral tire force where the chosen grip envelope requires it. The high-level QSS and point-mass basis is documented in the TUMFTM repository and Rowold et al.; the exact equations are the planner's implementation choice under D-01. [CITED: https://github.com/TUMFTM/laptime-simulation; https://arxiv.org/abs/2304.10954]

### Existing construction pattern

The Phase 9 model-facing types are frozen and copy-owning: `GeometryProfile` is `@dataclass(frozen=True, eq=False, init=False)` and `PhysicsInput` has the same declaration and documents that it “contains no accessor, database path, or results door.” [VERIFIED: `src/f1si/geometry/profile.py:119-126`; `src/f1si/data/physics_input.py:143-150`] The new model should follow this pattern, not hold a mutable database handle.

## State of the Art

| Established approach | Phase 10 recommendation | Impact |
|----------------------|-------------------------|--------|
| Quasi-steady lap-time simulation with a force-limited speed profile | Use the same reduced-order family for one fixed, validated planar line | Matches Phase 10 while keeping runtime bounded and equations inspectable. |
| Detailed 3D racing trajectory planning with g-g constraints | Keep elevation, banking, race-line optimization, and transient states out of this phase | The published 3D method documents these effects; adding them requires geometry/data absent from the Phase 9 contract. [CITED: https://arxiv.org/abs/2304.10954] |
| First-order covariance propagation | Use only where local linearization is adequate; compare a deterministic numeric alternative near active-bound switches | Prevents a precise-looking SD from masking nonlinear force-limit changes. [CITED: NIST TN 1297 Appendix A] |

**Deprecated/outdated:** no package replacement is indicated. The project already pins the NumPy/SciPy-compatible Python 3.12 stack; adopting an external transient solver or new optimizer is unnecessary for this goal.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The first solver will model one flat, planar, fixed Sakhir driving line and ignore banking/elevation/racing-line optimization. | Summary / Architecture | The predicted mean may omit material track-frame effects; do not present it as a team-grade or full-fidelity F1 lap simulator. |
| A2 | Existing lap-time observations may support only a very low-dimensional physical calibration; insufficiently identified terms will stay assumptions. | Parameter identifiability | Real-data parameter fit may be smaller or absent; that is preferable to claiming false identification. |
| A3 | The local OpenF1 probe artifacts are optional diagnostics and don't imply the telemetry rows are part of the DuckDB cache. | Summary | Do not build a training pipeline that assumes cached car/location tables exist. |

## Open Questions for Planning

1. **Which effective composite is recoverable from the chosen training evidence?**
   - What we know: Phase 9 found lap-number and wear observational effects, not physical parameter recovery; the local cache has no car-data or location rows.
   - What's unclear: whether a small physical composite can be fit robustly from available 2023–2025 lap rows and any already-cached optional telemetry.
   - Recommendation: predeclare the candidate parameter basis; run a rank/conditioning and sensitivity screen on training-only inputs; keep nonidentified parameters as assumptions. Do not redownload data just to force a fit.

2. **What convergence and approximation thresholds are appropriate?**
   - What we know: geometry smoothing affects the reference solver; finite spatial resolution can affect the speed envelope and integrated lap time.
   - What's unclear: tolerances specific to the project and the chosen Sakhir sample grid.
   - Recommendation: define a grid-refinement study and cyclic speed convergence test using synthetic profiles, then lock tolerances in the implementation decision before fitting real rows.

3. **Is first-order uncertainty adequate for the selected parameterization?**
   - What we know: covariance propagation is first-order; force envelopes contain active constraints.
   - What's unclear: whether parameter ranges cross drive/brake/cornering regime boundaries enough to invalidate linearization.
   - Recommendation: use the deterministic Jacobian/covariance path for the hot path; compare its SD to deterministic bootstrap/quadrature offline across representative training contexts and disclose its domain.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Solver/tests | ✓ | 3.12.10 | None needed. |
| uv | Reproducible environment | ✓ | 0.13.5 | None needed. |
| NumPy | Vectorized solver | ✓ via project dependency | Constraint `>=2.3,<3` | Pure Python scalar path only for debugging, not preferred runtime. |
| SciPy | Optional fit/diagnostics | ✓ via project dependency | Constraint `>=1.15,<2` | NumPy least squares/finite differences if a SciPy routine is unnecessary. |
| OpenF1 / FastF1 network access | Not required for core solver | Optional | — | Use existing local laps and declared assumptions; no fresh FastF1 archive download. |

No external binary or package installation is required for Phase 10.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + Hypothesis (existing project dependencies) |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/pace/test_point_mass.py tests/pace/test_point_mass_recovery.py -q` |
| Full suite command | `uv run pytest --cov=f1si --cov-report=term` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PHY-01 | Same-shape, finite deterministic mean/SD; respects interface and doesn't mutate inputs; required geometry/parameter failures are explicit. | Unit + conformance | `uv run pytest tests/pace/test_point_mass.py tests/conformance/test_protocols.py -q` | New model test: no; conformance test exists. |
| PHY-01 | Physical mean responds to power, drag, downforce, grip, mass/fuel and track curvature on controlled cases; result converges with grid refinement. | Unit/property | `uv run pytest tests/pace/test_point_mass.py -q` | No; add. |
| PHY-02 | Independently generated synthetic known-composite trajectories recover identifiable parameters; nonidentifiable absolute values remain labeled. | Synthetic recovery | `uv run pytest tests/pace/test_point_mass_recovery.py -q` | No; add. |
| PHY-02 | Closed-loop speed/force bounds and sensitivity on independent parameter and track perturbations. | Property/integration | `uv run pytest tests/pace/test_point_mass.py tests/pace/test_point_mass_recovery.py -q` | No; add. |
| PHY-01/PHY-02 | No look-ahead, no results-door access, and complete regression compatibility. | Guard + full suite | `uv run pytest tests/data/test_asof.py tests/data/test_doors.py tests/pace tests/conformance -q`; final CI full suite | Guard files exist. |

### Wave 0 Gaps

- Add `tests/pace/test_point_mass.py` and `tests/pace/test_point_mass_recovery.py`; there is no Phase 10 solver yet.
- Reuse geometry fixtures and shared protocol suites; no framework or fixture overhaul is needed.
- Keep new solver/reference and synthetic generator as separate implementations so one cannot call the other's force-envelope or integration helper.
- At phase closeout, run complete Ubuntu and Windows CI, copy the exact M1 baseline, and report the fixed PAC-06 miss and `not_estimable`/assumption limits without retuning any lock.

## Security Domain

No authentication, sessions, access-control, or cryptography features apply. Input validation does apply: accept only finite, unit-checked, physically bounded parameters and a previously digest-validated geometry profile; reject malformed arrays and impossible state values before numerical operations. Do not load executable model/config files or resolve arbitrary paths from race data.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user accounts. |
| V3 Session Management | No | No sessions. |
| V4 Access Control | No | Local model construction only. |
| V5 Input Validation | Yes | Strict typed dataclasses, finite/range/unit checks, fail-closed artifact validation. |
| V6 Cryptography | No | Reuse SHA-256 artifact validation already implemented; do not create a cryptographic protocol. |

## Sources

### Primary / official technical sources (MEDIUM confidence via verified web retrieval)

- [TUMFTM `laptime-simulation` repository](https://github.com/TUMFTM/laptime-simulation) — project describes a quasi-steady Python lap simulator; README separates raceline prep from lap simulation, highlights curvature smoothing and sensitivity analysis, and links the 2019 paper. The repository lists LGPL-3.0; cite/reimplement method, do not copy code.
- [Rowold et al., “Online Time-Optimal Trajectory Planning on Three-Dimensional Race Tracks”](https://arxiv.org/abs/2304.10954) — primary paper describing quasi-steady point-mass planning constrained by g-g diagrams and 3D track-frame effects.
- [NIST TN 1297 Appendix A: Law of Propagation of Uncertainty](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-law-propagation-uncertainty) — first-order Taylor sensitivity coefficients and input covariance propagation.
- [NIST TN 1297: Combined Standard Uncertainty](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-5-combined-standard-uncertainty) — covariance-aware combination, assumptions, and when a standard uncertainty is approximately Gaussian.
- [TUMFTM README’s solver-paper reference](https://github.com/TUMFTM/laptime-simulation#detailed-description-of-the-lap-time-simulation) — Heilmeier, Geisslinger, Betz (2019), “A Quasi-Steady-State Lap Time Simulation for Electrified Race Cars,” DOI: 10.1109/EVER.2019.8813646. Full IEEE paper was not accessible in this research environment; no specific equation is attributed to it here.

### Local sources (HIGH confidence, read this session)

- `pyproject.toml:6-8,17,34-35` — Python, NumPy, SciPy, pytest, and Hypothesis dependency constraints.
- `src/f1si/interfaces.py:150-165` — `PaceModel` signature and no-sampling/no-accessor contract.
- `src/f1si/geometry/profile.py:119-126` — immutable validated geometry profile.
- `src/f1si/data/physics_input.py:143-165` — copy-owning race input and no-accessor/results-door boundary.
- `src/f1si/parameters/register.py:38-61,109-116` — effective vs hidden-assumption classification and immutable register.
- `.planning/phases/09-data-and-geometry-readiness/09-PHASE-REPORT.md:3-35` — cache availability, parameter identifiability limits, geometry status, and fixed baseline.
- `.planning/phases/09-data-and-geometry-readiness/09-PARAMETER-SENSITIVITY.json` — 2023–2025 evidence selection, identifiability-only scope, and `not_estimable_pre_solver` marker.
- `.planning/M1-BASELINE.md` — fixed metrics and denominator definitions.
- `DECISIONS.md` DEC-134–139 — effective-only parameter fitting, unchanged PaceModel seam, as-of input boundary, and Phase 9 register method.
- `F1 Docs/BUILD_PLAN.md` — project architecture and approved quasi-steady reference.

### Assumed / not used as authoritative

- No third-party community simulator is used to set equations, F1 values, license terms, or acceptance thresholds.
- Absolute team-specific physical values, real-data recovery tolerances, and solver convergence tolerances are not inferred from search snippets; planning must define numerical thresholds and label physical priors as assumptions.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing Python 3.12/NumPy/SciPy and test dependencies are declared locally; no new dependency is needed.
- Architecture: HIGH — local PaceModel, immutable geometry, PhysicsInput, and parameter register were read directly; the phase context locks integration.
- Solver method: MEDIUM — QSS/point-mass sources are primary, but the legacy IEEE paper itself was inaccessible; exact force-envelope implementation remains a phase planning choice.
- Identifiability: MEDIUM — project decisions and Phase 9 screen explicitly caution against physical recovery; actual fit identifiability must be evaluated on training evidence.
- Uncertainty: MEDIUM — NIST method is primary, but linearization adequacy is solver/data-specific and must be tested.
- Pitfalls: MEDIUM — curvature smoothness and uncertainty assumptions have primary-source support; project-specific numerical thresholds remain to be established.

**Research date:** 2026-11-17  
**Valid until:** 2027-11-17 (stable mechanics; revisit only if project stack or phase constraints change)
