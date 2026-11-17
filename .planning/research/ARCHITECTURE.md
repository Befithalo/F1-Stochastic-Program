# Architecture Patterns: M2 Physics

**Domain:** Physics-grounded Formula 1 lap-time prediction and strategy simulation  
**Researched:** 2026-11-17  
**Confidence:** HIGH for the integration seams and data constraints; MEDIUM for the reduced-order physics and latent thermal choices because public F1 vehicle, tyre, and setup parameters are not available.

## Recommended Architecture

Keep M2 as a new implementation behind the existing `PaceModel` and preserve the current race/replay stack. Build an immutable, cutoff-specific physics context from track, weather, public telemetry, current race snapshot, and versioned vehicle priors. A spatial point-mass solver produces a clean baseline lap time and its parameter uncertainty; a compact latent tyre state adjusts grip and tyre pace; the existing hierarchical Bayesian model learns the remaining systematic error from historical residuals. The final hybrid fit implements the same `predict` method used by the linear and Bayesian pace fits.

```text
OpenF1 (laps/stints/weather + optional location/car data) ─┐
Track centerline / curvature / elevation ───────────────────┤
Vehicle parameter prior + era config ───────────────────────┤
RaceSnapshot + cutoff-visible history ──────────────────────┘
                              │
             feature preparation / cutoff-safe context
                              │
   geometry + environment + effective vehicle parameters
                              │
       point-mass speed envelope (forward/backward passes)
                              │
  clean physics pace ── latent tire temperature / wear state
                              │
         Bayesian residual fit over clean historical laps
                              │
               HybridPaceModel : PaceModel
                              │
   existing RaceState builder → Longstaff policy → simulator
```

The proposed point-mass calculation is an inference from standard quasi-steady lap simulation practice and the project's scope, not a claim that public F1 data supports a high-fidelity reconstruction. TUM FTM's open `laptime-simulation` explicitly uses a quasi-steady-state approach with track/raceline and vehicle parameters and evaluates vehicle-parameter effects; it is the best implementation-level reference to study, but its code is LGPL-3.0 and should inform a clean reimplementation rather than be copied. [TUMFTM laptime-simulation](https://github.com/TUMFTM/laptime-simulation)

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `track` profile (suggested `f1si/physics/track.py`) | Versioned distance grid with `ds`, curvature, elevation/grade, surface/track metadata, map provenance and quality flags. Build per-circuit profiles from centerline data; do not depend on plotting assets. | Data profile loader, solver |
| Environment snapshot (suggested `physics/environment.py`) | As-of weather and regime values plus explicitly configured ambient/track defaults and uncertainty. Interpolate only observations at or before the cutoff. | Context builder, thermal model |
| Effective vehicle parameters (suggested `physics/vehicle.py`) | Immutable parameter set for mass/fuel, power, drag, downforce, braking and grip scalars, with source, era and uncertainty metadata. Start with team/era or car-class priors; do not imply private setup values are identified from lap times. | Solver, residual training |
| Speed-envelope solver (suggested `physics/point_mass.py`) | Compute lateral speed caps and enforce longitudinal acceleration/braking limits with forward/backward propagation around the closed track. Integrate `dt = ds / v` with a stable low-speed floor and report energy/parameter sensitivities. | Baseline lap predictions |
| Tyre latent state (suggested `physics/tyres.py`) | Advance hidden tread/carcass temperature and degradation state from energy/load proxies, ambient and track temperature, compound, age and pit resets; map grip/pace effect and uncertainty. | Solver and HybridPaceModel |
| Physics training features (suggested `pace/physics_training.py`) | Build clean, cutoff-safe observed lap rows and corresponding physics baseline, joining only information known for each historical prediction cutoff. | Residual fit |
| Bayesian residual (extend/compose `pace/bayesian.py`) | Fit partial-pooled residuals `observed clean lap - physics mean`, conditioned on available team/driver, compound, stint age, era, track/environment and optionally pace-shape diagnostics. | HybridPaceModel |
| Hybrid predictor (suggested `pace/hybrid.py`) | Bind a fixed track/environment/vehicle/thermal context and residual fit; expose `predict` with the existing shape and uncertainty semantics. | Replay/backtest composition seam |
| Data adapter and storage | Add optional OpenF1 location/car-data ingestion and a static circuit-profile loader; preserve normalized race feed contracts and the one as-of data door. | Context and training builders |

### Data Flow

1. `OpenF1Source` and Jolpica continue producing the current normalized race tables. Extend the source additively for location data and, only if the endpoint's coverage is adequate, car data. The current OpenF1 adapter fetches `/drivers`, `/laps`, `/stints`, `/race_control`, and `/weather`; the cache/schema currently has no per-sample location table.
2. Store telemetry samples as immutable raw-ish observations keyed by race/session, driver, timestamp/sequence, with explicit race-clock `visible_at_s`; keep `x/y/z` and optional speed/RPM/gear/throttle/brake fields nullable. Never fold location samples into `laps` or treat a post-session enriched lap as though its data was visible at lap completion.
3. Map `race_id` to OpenF1 `session_key` in source metadata (the API needs a session key for location queries). Convert UTC sample timestamps to the existing lights-out race clock using the same event origin, validate ordering and duplicate behavior, and enforce the single `visible_at_s <= cutoff` predicate. Location data is about 3.7 Hz and approximate, with arbitrary origin and no lateral placement, as OpenF1 documents; use it to align progress to a known circuit path and estimate segment speed/curvature coverage, not as a surveyed track map or tire-force measurement. [OpenF1 location endpoint](https://openf1.org/docs/#位置) (English anchor may vary; canonical docs: [OpenF1 API](https://openf1.org/docs/))
4. Keep circuit centerline/curvature profiles as versioned static inputs keyed by stable circuit ID. TUMFTM's track database is a candidate source, but verify the particular profile's license, coordinate system, direction, pit lane, and geometry before adoption. Match the relative GPS path to the map with a documented coordinate transform; do not mix the API's arbitrary origin across sessions. Start with one well-covered circuit (Bahrain is the project benchmark) and make unsupported circuits fail clearly or use a disclosed simple fallback.
5. A cutoff-context builder receives only `RaceSnapshot`/`History`, static track/profile config, and explicit vehicle/physics config. It must not receive `AsOfAccessor`, result tables, future telemetry, or final classification. The current Bayesian training panel uses clean lap rows, stable identities and cutoff-visible current-event rows; build a parallel physics-feature panel rather than smuggling hidden access into `BayesianPaceFit`.
6. The solver calculates a baseline profile. A per-lap observable baseline can be generated from track distance and mapped telemetry progress; for the current optimizer's race-lap API, aggregate segment times into lap mean and uncertainty, then apply compound/age and fuel effects consistently. Avoid fitting arbitrary segment corrections on the same target lap being evaluated.
7. Update the latent tyre state from observed prior laps only. At a cutoff, keep a posterior summary (mean/covariance or particles compressed to moments) per current stint; prediction advances that hidden state forward under the configured expected energy/environment and widens uncertainty. Pit stops reset tyre temperature/age according to the explicit initialization model.
8. Fit the Bayesian model to `residual = observed_clean_lap - physics_baseline` using only rows that could be assembled at the corresponding training cutoff. Compose mean as physics + residual mean. Residual SD is kept distinct from shared uncertainty in vehicle/thermal parameters to avoid drawing the same uncertainty twice in `NumpySimulator`.
9. `_prepare_replay_context` and `predict_at_cutoff` select `physics`/`hybrid` at the existing model factory point. Pass the resulting `PaceModel` to the same `LongstaffSchwartzPolicy` and simulator. Do not fork strategy, scoring, race replay, or result semantics to add M2 physics.

### Interfaces That Must Remain Unchanged

- `f1si.interfaces.PaceModel.predict(*, driver, compound, tire_age, lap) -> (mean_s, sd_s)` remains keyword-only, vectorized, shape-preserving float64 and deterministic. It never samples and does not read an accessor. Add the hybrid as another implementation; do not add track, environment, RNG, state, or feature-array arguments.
- The caller retains random draw ownership. `sd_s` is conditional per-lap residual noise, not a second copy of shared team, car, fuel, weather, tyre-state or wear-parameter uncertainty.
- `RaceState`, `CarState`, `Plan`, `PitDecision`, `StrategyPolicy`, `SimulatorBackend`, and the first two `SimulationResult` fields stay stable. New context belongs in immutable model/config objects created at the replay/backtest composition seam. If M2 needs tire-temperature state serialized, make that a separately reviewed additive optional field with JSON compatibility; avoid widening the shared state before an end-to-end need is demonstrated.
- `build_race_state` currently consumes a narrow fit protocol for driver offsets, offset SEs, wear mean and wear SE. Keep this seam, or add only optional structural accessors with defaults. It should not become a physics solver or gain data-access responsibilities.
- Maintain the existing as-of accessor as the only temporal data door and preserve held-out result separation. New telemetry has to obey the same cutoff contract as laps/weather/race-control rows.
- Replay/backtest command defaults and M1 locks/reports remain historical. M2 gets a separately locked held-out-stint evaluation under DEC-130; no reinterpretation of Phase 7's failed PAC-06 score.

### Point-Mass and Tire Model Shape

Use a one-dimensional distance grid along an observed/known centerline, with curvature `kappa(s)`. A transparent first solver is sufficient: lateral cap `v_lat(s) = sqrt(mu_eff(s) * g / max(|kappa(s)|, epsilon))`; calculate acceleration from drive force minus aerodynamic drag and rolling resistance divided by mass; calculate braking deceleration from effective grip and aerodynamic load; enforce each segment's entry/exit speed compatibility in a forward acceleration pass and backward braking pass, iterating to a periodic lap boundary. Add downforce to the normal-load/grip relation and make power/drag/downforce/grip scale parameters explicit and unit-checked. Integrate segment time from distance and segment speeds.

These equations are deliberately a reduced-order envelope, not a full vehicle model: no tire slip-angle model, suspension, differential, DRS map, cornering line optimization, gear/ERS strategy, dirty-air loss, or full longitudinal transients in the MVP. TUM FTM's reference shows the usefulness of quasi-steady vehicle/track parameter separation; its published source and its inputs are a design reference, not proof that public F1 timing uniquely identifies effective parameters. [TUMFTM repository](https://github.com/TUMFTM/laptime-simulation)

For the tyre, use a low-dimensional hidden state (at minimum tread temperature and cumulative degradation; a two-node tread/carcass pair is preferable if the chosen energy proxy supports it). Advance heat and cooling from cornering/braking/traction energy proxies, track/ambient temperature, speed and elapsed time; let grip vary smoothly with temperature and wear. Keep all unidentified heat-flow coefficients and reset temperatures as declared priors, estimate only a small set with regularization, and propagate their uncertainty. Published F1 tyre thermal work models separate tread/carcass heat balances and fits heat parameters to telemetry; it also reports unavailable carcass measurements, illustrating why this project's public-data version must call these latent estimates, not observed tire temperatures. [Optimal Tyre Management of a Formula One Car (IFAC 2020)](https://ifatwww.et.uni-magdeburg.de/ifac2020/media/pdfs/0335.pdf)

The M1 Kalman wear filter is not a hidden-temperature sensor: use its observed-lap residual/wear information as an initialization or benchmark, then document any new latent thermal state separately. A recent public-data Bayesian state-space study likewise treats tire pace/degradation as latent and models pit stops as resets; it is an adjacent methodological reference, not ground truth or a validated F1 tire model. [Cappello & Hoegh, state-space tire degradation](https://arxiv.org/abs/2512.00640)

### Patterns to Follow

#### Pattern 1: immutable model context, narrow prediction protocol

**What:** Build a frozen physics context at the cutoff and bind it into a model instance. `predict` remains a pure array-to-arrays calculation. Model construction performs data retrieval/feature assembly outside the pace module; the pace implementation sees numeric arrays/config and compact posterior summaries.

**When:** Replay, held-out evaluation, repeated optimizer calls. This matches the existing M1 pattern: training panel receives plain snapshot/history inputs; fit result implements `PaceModel`; CLI composition chooses the model; strategy only consumes the protocol.

**Example:**

```python
mean_physics, physics_sd = solver.predict_laps(track, effective_vehicle, thermal_state, query)
residual_mean, residual_sd = residual_fit.predict(**query.pace_axes())
mean_s = mean_physics + residual_mean
sd_s = np.sqrt(physics_sd**2 + residual_sd**2)  # only if independent conditional errors
```

If shared parameter covariance couples physics and residual, carry that uncertainty as shared model metadata and have the simulator draw it once; do not assume independence just to make the formula convenient.

#### Pattern 2: separate measured inputs, priors, fitted corrections, and hidden states

**What:** Every effective vehicle/track/environment value carries source and confidence metadata (`measured`, `derived`, `prior`, `fit`, `assumption`). Keep a data class/config boundary between immutable public geometry, uncertain vehicle parameters, and posterior latent tire state.

**When:** All physics calculations. Lap-time data has strong confounding among power, drag, downforce, grip, driver behavior, fuel, track evolution and tire energy; posterior precision cannot be inferred from a good lap-time fit alone.

#### Pattern 3: analytic component tests before race-level composition

**What:** Recover solver behavior on straight/constant-radius/grade toy tracks; check speed limits and periodic boundary; recover synthetic vehicle parameters and tire state; then test hybrid conformance and full replay. Measure both physics baseline and hybrid separately.

**When:** Each M2 vertical slice. Existing project constraints call for synthetic recovery, fixed-seed reproducibility and shared `PaceModel` conformance.

### Anti-Patterns to Avoid

#### Anti-Pattern 1: expand `PaceModel` into a mutable simulation service

**What:** Add context or RNG arguments, allow predict to query DuckDB, or mutate thermal state on each call.

**Why bad:** Optimizer call order and batch shape then change results; strategy becomes coupled to physics internals; the existing protocol and test suite stop being a useful plug-in seam.

**Instead:** Construct an immutable cutoff-bound predictor with a pure vectorized `predict`; derive future thermal trajectories deterministically from the same bound context and query lap/age values.

#### Anti-Pattern 2: treat OpenF1 GPS as track geometry or tire telemetry

**What:** Infer curvature directly from noisy 3.7 Hz positions or treat `z`/coordinates as a common surveyed coordinate frame; use location-only samples as speed/forces.

**Why bad:** OpenF1 explicitly describes the origin as arbitrary, positions as approximate, and samples as lacking lateral placement. Differentiated position noise amplifies into false curvature and forces.

**Instead:** Use GPS to align a session's progress with an independently sourced map and check sample coverage; use map geometry for curvature; treat `car_data` and public weather as noisy observations and retain limits.

#### Anti-Pattern 3: overfit all vehicle coefficients from lap times

**What:** Fit per-team power, drag, downforce, grip, fuel, driver, tire wear, and thermal parameters freely against the same few race stints.

**Why bad:** The terms can compensate for one another and produce plausible lap time but nonphysical parameters; PAC-06 can appear to improve from leakage or unnecessary degrees of freedom.

**Instead:** Fix or strongly regularize a small set from public priors; use partial pooling by team/era; learn residual corrections; report identifiability and parameter sensitivity; lock an independent held-out-stint comparison before scoring.

#### Anti-Pattern 4: use one race's future telemetry to fit the earlier cutoff

**What:** Build current-race geometry or thermal history from complete session data before replaying earlier laps.

**Why bad:** High-frequency samples and completed-lap summaries reveal outcomes after the decision time.

**Instead:** Carry sample-level visibility times, assemble context only through the cutoff, and run future-scramble/as-of invariance checks for all new data paths.

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---|---|---|---|
| Current target is local replay, not service-scale | NumPy solver on one cached circuit profile per replay; cache immutable track grids and parameter sets in process | Batch pace queries by circuit/vehicle setup; avoid per-lap PyMC refits by caching immutable cutoff/data/config/seed identities | M2 should not design for this scale; later M5 vectorized/JAX/Rust backend and M6 service architecture need separate work |
| Telemetry volume | One event's location is a few hundred thousand samples total; persist compressed by event and fetch/cache only where needed | Preprocess location to progress/segment summaries while retaining provenance and raw cache locally | Partition or columnar object storage and derived features; outside M2 scope |
| Reproducibility | Version geometry, map transform, parameter config, model code/config, data digest and seed in fit/report | Same content-addressed cache key avoids duplicate fitting across replay requests | Distributed deterministic feature and model cache; only if product usage justifies it |

## Build Order and Configuration Seams

Recommended dependency order; each layer should end with a synthetic recovery or bounded physics check before downstream integration.

1. **Freeze M2 prediction/evaluation seam:** preserve `PaceModel`, reserve CLI/backtest selection (`linear`, `bayesian`, `hybrid`), create independent held-out-stint lock, specify conditional versus shared uncertainty. Keep M1 results/lock immutable.
2. **Versioned geometry and environment inputs:** circuit-keyed track profile asset plus parser/validator; `track_profile_version`, source/license, coordinate CRS/transform, distance step and track length. Expose weather fallback and uncertainty explicitly; no public data means uncertain/defaulted, not silently exact.
3. **Effective vehicle prior and point-mass solver:** `vehicle_config_version`, era, team/car class, nominal fuel mass schedule, engine-power curve simplification, `CdA`, downforce scale, mass, brake/grip scale, rolling resistance, efficiency assumptions, parameter covariance. Begin with one circuit and synthetic tracks; then compare against real clean laps without tuning on the locked holdout.
4. **Telemetry pipeline:** session-key provenance; location and optionally car-data endpoint schemas; raw timestamps, race-clock conversion, visibility, deduping, bounds/gap checks, source-version metadata; optional DuckDB table plus accessor methods. Test adapter validation and as-of filtering before trusting derived features.
5. **Latent thermal/wear dynamics:** compound priors and reset state; heat generation/cooling; grip-versus-temperature map; age/degradation dynamics; use OpenF1 weather, mapped speed and curvature proxies. State clearly which are hidden and which are observed. Integrate with current Kalman outputs only through a deliberate state initialization/measurement relationship.
6. **Residual feature panel and hybrid fit:** generate physics baseline for every qualifying training lap at its own historical cutoff; fit partially pooled Bayesian residual model. Keep physical fit context separate from residual fit so diagnostics can attribute error to base physics versus residual.
7. **CLI/replay/backtest integration:** one new hybrid factory selector routes to unchanged `LongstaffSchwartzPolicy` and `NumpySimulator`; keep fallback behavior explicit where circuit/compound support is missing. Preserve current model and score defaults.
8. **Evaluation and calibration:** synthetic parameter recovery; blocked held-out stints/races; next-lap errors and intervals by circuit/team/compound/age/era; compare against both linear and data-only Bayesian baselines. PAC-06's M2 requirement is specifically hybrid vs data-only Bayesian on a separately locked held-out-stint split. Report failures and unsupported coverage rather than retune after exposure.

**Configuration should be data, not constants buried in solver code.** Use versioned immutable objects for track profiles, vehicle priors, tire coefficients, weather fallback policy, numerical discretization, solver tolerances, residual formula, inference settings and random seed. Serialize identifiers/digests and assumption labels into a compact fit/evaluation report. Keep PyMC imports isolated to fit modules as in M1.

## Data Pipeline Changes Needed

| Change | Why | Contract |
|--------|-----|----------|
| Add session-key provenance to race/source metadata | Existing `race_id` is Jolpica season-round based; OpenF1 location/car-data endpoints require `session_key`. | Stable race/session mapping at load time, not guessed from event name at fit time. |
| Add optional `location` observations | Current adapter doesn't fetch location; track matching needs sample timestamps and coordinates. | `race_id`, `driver_number`, UTC `date` or race `t_s`, `x/y/z`, `seq`/source ordering, `visible_at_s`; nullable telemetry; composite dedupe key. |
| Add optional `car_data` only after endpoint audit | Needed for direct speed/throttle/brake proxies if historical coverage is reliable; location alone provides approximate progress, not controls or force. | Keep sample-level fields and missingness. Never backfill absent telemetry with lap-derived outcomes. |
| Extend `RaceSnapshot`/`History` and as-of accessor | Models must consume visible samples without bypassing the one data door. | Time-indexed sample filters reuse `visible_at_s <= cutoff`; history excludes current/future event outcomes. |
| Track map asset registry | The lap solver requires distance, curvature and direction independent of GPS origin. | Circuit ID, source, license, map version/hash, coordinate transform, direction, length, units, quality checks, fallback status. |
| Rebuild cached DuckDB schema safely | `CREATE TABLE IF NOT EXISTS` alone won't add the new tables/columns to existing local caches. | Explicit migration/version or a reproducible reload path; invalidate old source cache when adding endpoint coverage. |
| Update load budgeting and completeness criteria | Existing OpenF1 pacing allows one request every 2.1s; location can be large and possibly paginated/limited. | Don't make optional telemetry failure invalidate the M1 race feed; report missing/partial feature coverage. |

OpenF1's official documentation states location is sampled at about 3.7 Hz, approximate, has arbitrary origin, and doesn't include lateral placement. Its weather feed is minute-updated. This supports a separate static geometry asset plus visibility-aware sensor ingestion, not replacing track geometry with live GPS. [OpenF1 API documentation](https://openf1.org/docs/)

## Sources

- Local integration contracts: `src/f1si/interfaces.py` (`PaceModel`), `src/f1si/state.py` (`RaceState` and `build_race_state`), `src/f1si/cli.py` (`_prepare_replay_context`, `_replay_at_cutoff`), `src/f1si/pace/training.py`, `src/f1si/pace/bayesian.py`, `src/f1si/data/schema.py`, `src/f1si/data/sources/openf1.py`, `src/f1si/data/_snapshot.py`, `DECISIONS.md` DEC-005, DEC-061, DEC-063, DEC-065, DEC-130 through DEC-132, `.planning/PROJECT.md`, `F1 Docs/BUILD_PLAN.md`, `.planning/M1-BASELINE.md`.
- [TUMFTM/laptime-simulation](https://github.com/TUMFTM/laptime-simulation) — primary open implementation reference for quasi-steady lap simulation; repository identifies its LGPL-3.0 license.
- [OpenF1 official API documentation](https://openf1.org/docs/) — endpoint schema and limits for location, telemetry, laps, stints and weather.
- [Optimal Tyre Management of a Formula One Car](https://ifatwww.et.uni-magdeburg.de/ifac2020/media/pdfs/0335.pdf) — primary paper describing tread/carcass thermal balances and telemetry-fitted parameters; its proprietary/vehicle-specific parameters are not transferable without validation.
- [Cappello & Hoegh, A State-Space Approach to Modeling Tire Degradation in Formula 1 Racing](https://arxiv.org/abs/2512.00640) — public-data latent tire pace/degradation and pit-reset model; treat as an adjacent research reference, not an established benchmark.

## Research Gaps

- Audit OpenF1 historical `location` and `car_data` availability, retention, row counts, and quality on Bahrain 2023 before making telemetry mandatory. The docs establish fields, not the coverage of this project's stored sessions.
- Confirm track-map source licensing and circuit geometry provenance for the first target circuit; the build plan points to TUMFTM track data but does not yet select a specific release, map, license, transform, or direction convention.
- Determine which effective vehicle parameters can be fixed from primary public sources and which should remain weak priors. Lap-time-only identification is insufficient evidence for precise car parameters.
- Select and lock a thermal model's state dimension, energy proxy, reset rule, and uncertainty treatment during phase-specific planning. Public race timing does not directly reveal tire temperatures.
- Define calibration and the separate PAC-06 held-out-stint protocol before opening evaluation outcomes. M1's Bayesian PAC-06 miss means the residual model cannot be treated as a guaranteed improvement.
