# M2 Technology Stack

**Project:** F1 Stochastic Intelligence Platform (f1si)  
**Researched:** 2026-11-17  
**Scope:** M2 point-mass lap simulation, thermal/wear tyre state, and a hybrid `PaceModel` that retains M1 consumer compatibility.

## Recommendation

Keep the M1 Python stack and add no runtime dependency for M2. Implement the point-mass lap model and thermal/wear state with the existing NumPy/SciPy/Numba stack; use DuckDB for versioned track/config/derived calibration inputs; keep PyMC for the hierarchical Bayesian residual fit. Package a `HybridPaceModel` that still implements the existing `PaceModel.predict(driver, compound, tire_age, lap) -> (mean_s, sd_s)` contract. Supply race, circuit, weather, fuel, and vehicle-parameter context when constructing/fitting the model, because those variables are not part of the protocol arguments.

The recommendation is deliberately an **effective physics model**, not a claim to reconstruct a current F1 car. Public timing sources do not provide team power, drag, downforce, tyre grip curves, fuel mass, or tyre temperatures. Use a named, versioned representative parameter set with explicit uncertainty, calibrate only identifiable aggregate/era/team residual effects from historical lap times, and report physics terms as modeled assumptions. If track data license terms cannot be accepted, start with the Bahrain TUM track file only after a provenance check; do not quietly copy a multi-circuit dataset into a public release.

## Existing stack and cache (verified locally)

Python 3.12, `uv`, NumPy, pandas, SciPy, Numba, PyMC, DuckDB, FastF1, pytest/Hypothesis, Ruff, mypy strict are already pinned in `pyproject.toml`. The existing DuckDB contains 87 races (2023: 22, 2024: 24, 2025: 24, 2026: 17).

The normalized cache currently contains:

| Table | Exact relevant stored fields | M2 use / limitation |
|---|---|---|
| `laps` | `race_id`, `driver_number`, `lap_number`, `lap_start_s`, `lap_end_s`, `lap_time_s`, `s1_s`, `s2_s`, `s3_s`, `is_pit_in_lap`, `is_pit_out_lap`, `pit_duration_s`, `stint`, `compound`, `tyre_life`, `track_status`, `visible_at_s` | Lap/sector timing, tyre compound/age and cutoff-safe timing targets. No speed trace, distance trace, tyre temperature, fuel mass, or vehicle parameters. |
| `weather` | `race_id`, `seq`, `t_s`, `air_temp_c`, `track_temp_c`, `humidity_pct`, `pressure_mbar`, `rainfall`, `wind_speed_ms`, `wind_direction_deg`, `visible_at_s` | Ambient/track boundary conditions; official API describes weather as updated every minute. Local cache has 13,928 rows and all rows have air and track temperature. It is not tyre surface/carcass temperature. |
| `entries` / `races` | driver/team identity, starting compound and tyre age; circuit id/name, calendar and era metadata | Conditioning labels and circuit mapping. No effective power, aero, mass, grip, or fuel-load measurements. |
| All current tables | No telemetry or location table | OpenF1 exposes `car_data` and `location`, but current `OpenF1Source` only requests drivers, laps, stints, race control, and weather. These feeds are absent from the local cache until deliberately ingested and normalized. |

OpenF1's official historical API documentation says historical data from 2023 onward is free/no-auth and live access is paid. `car_data` fields are `date`, `driver_number`, `meeting_key`, `session_key`, `brake`, `drs`, `n_gear`, `rpm`, `speed` (km/h), and `throttle`, sampled about 3.7 Hz. `location` provides `date`, driver/meeting/session keys and approximate `x`, `y`, `z`, also about 3.7 Hz; the origin is arbitrary and it lacks lateral track position. These can support speed-trace diagnostics and progress alignment, but not a trustworthy wheel-load or tyre-energy observation. Adding either feed means a new time-indexed table, caching/rate-limit work, and an as-of visibility contract; do not make it a prerequisite for the first M2 slice. [OpenF1 API docs](https://openf1.org/docs/)

### Data and access terms

- OpenF1 describes its intended uses as educational, personal learning, research, and non-commercial fan engagement; it invites other use cases to contact it. Free historical access is limited to 3 requests/second and 30/minute. Keep this project non-commercial, credit/link the source, preserve the existing request pacing, and never publish raw dumps. Its API being open source does not convey ownership of underlying Formula 1 data. [OpenF1 usage/access](https://openf1.org/)
- FastF1 is MIT-licensed software, but fresh timing-archive access is a separate credential matter. FastF1's current docs say most available data requires an active F1 TV Access/Pro/Premium subscription and triggers account authentication. This matches DEC-107 and DEC-109: use verified local data first; do not make F1 TV credentials a required M2 dependency; use OpenF1 historical data for new sessions where available. FastF1 software license does not relicense F1 timing data. [FastF1 authentication docs](https://docs.fastf1.dev/api_reference/accounts_auth.html), [DEC-107/109](../../DECISIONS.md)
- TUMFTM's `racetrack-database` contains smoothed centerline coordinates and left/right track widths for 20+ circuits, including Sakhir; its repository is marked LGPL-3.0. The README says source centerlines were fetched from OpenStreetMap, widths were extracted from satellite imagery, and data quality varies. Treat the selected geometry file as third-party data with provenance: pin an upstream commit and filename, preserve attribution/license, record the OSM derivation and uncertainty, and review data redistribution separately from the repository's software license. Do not assume that LGPL alone settles rights in every underlying geometry/imagery-derived asset. [TUMFTM track database](https://github.com/TUMFTM/racetrack-database)
- TUMFTM's quasi-steady lap-time simulator is useful as a mathematical reference for force/energy balance and sensitivity structure; it is LGPL-3.0 and has a substantially larger workflow/dependency footprint than this project's MVP needs. Reimplement the equations with attribution and do not copy its source files. [TUMFTM lap-time simulation](https://github.com/TUMFTM/laptime-simulation)

## Recommended components

| Component | Technology | Purpose | Why |
|---|---|---|---|
| Track geometry and curvature | Vendored, pinned TUMFTM centerline/width CSV for one circuit initially; NumPy/SciPy for distance parameterization, smoothing/interpolation and curvature | Turn circuit coordinates into segment distance and curvature | Official repo already provides usable centerline and widths. Avoid an additional GIS dependency; preserve source file and attribution. |
| Point-mass lap solver | Existing NumPy arrays; SciPy only for geometry interpolation; optional existing Numba for the hot loop | Compute segment speed/time under effective power, drag, downforce, mass and grip bounds | Existing stack supports a transparent forward/backward speed envelope and force balance without introducing a full vehicle-dynamics framework. Numba is already installed; use it only after a pure-array implementation is correct. |
| Tyre thermal/wear state | Small pure-Python/NumPy state model; integrate per lap/segment | Evolve a hidden effective tyre-temperature state and energy/stress wear proxy; feed state into grip, pace and degradation | No public tyre-temperature telemetry exists in the existing cache or OpenF1's documented car/weather fields. A compact, explicitly latent model is supportable; adding a thermal library would not create missing observations. |
| Physics pace model | `PhysicsPaceModel` implementing existing `PaceModel` protocol | Provide baseline lap-time mean and uncertainty for a race/circuit context | Keeps downstream M1 state builder, simulator, and protocol consumers callable without signature edits. Construct a race-scoped predictor with static/context inputs. |
| Residual learner and hybrid | PyMC posterior trained on measured lap-time residuals after physics baseline; `HybridPaceModel` composes it with physics | Correct systematic model error while preserving uncertainty | PyMC is already present and Bayesian pace already established. A separately trained residual model is needed; adding the existing absolute-time Bayesian prediction to a physics time would double count its pace effects. |
| Data/config storage | Existing DuckDB plus versioned parameter/geometry metadata and as-of access | Store parameter provenance, model version, cutoff-safe weather and calibration fits | Consistent with current single cache and data-access design; do not put fitted/calibration-derived future information into the as-of view. |

### Numerical sketch

For distance segment `ds` and curvature `kappa`, cap cornering speed using `v_corner = sqrt(mu_eff * Fz / (m * abs(kappa)))`, where effective normal load includes mass and a calibrated downforce term. Limit longitudinal acceleration with an effective power/drag balance, e.g. `a_x = (min(P_eff / max(v, eps), F_drive) - 0.5 * rho * CdA * v**2 - F_roll) / m`; use a forward acceleration and backward braking pass to obtain a feasible segment speed envelope, then integrate `dt = ds / v`. Keep hybrid-electric deployment, DRS, and team-specific values folded into disclosed effective coefficients unless a defensible public measurement exists. This is a low-order baseline, not a lap simulator validated against proprietary vehicle data.

Model tyre state as latent: update effective carcass/surface temperature from an assumed heating term (slip/energy/stress proxy), cooling to an ambient/track-temperature-dependent equilibrium, and clamp or penalize grip/wear outside a configurable window. Public weather temperature is only an input proxy; do not label the output as measured tyre temperature. Compound and tyre age are available from stints; wear/pace degradation is inferred from lap times and already has an M1 linear/Bayesian model. Thermal parameters require synthetic recovery plus held-out-stint calibration; do not tune on the locked M1 PAC-06 holdout or reuse its result.

## Interface compatibility contract

Current protocol in `src/f1si/interfaces.py` accepts only integer `driver`, string `compound`, integer `tire_age`, and integer `lap` arrays, then returns same-shape float64 `mean_s` and `sd_s`. Preserve the signature and its no-I/O/no-sampling rule. Add a constructor/factory or fitted context object for circuit geometry, effective car parameters, race/era, fuel proxy, weather snapshot, and any latent thermal state. Context must be built by existing as-of accessors at the requested cutoff; `predict` must not query DuckDB or fetch network data. Have both physics and hybrid variants pass the shared `PaceModel` conformance suite.

Recommended composition:

```text
PaceModel consumer (unchanged)
       |
HybridPaceModel.predict(arrays)
       +-- PhysicsPaceModel.predict(arrays, prebuilt race/cutoff context)
       +-- BayesianResidualFit.predict(arrays)  # trained on y - physics_mean
       `-- mean = physics_mean + residual_mean; SD combines declared terms
```

The residual fit must model residuals, not reuse an absolute lap-time fit as an additive correction. Freeze the physics parameter/version and residual-training cutoff with every fit; report the physics-only, residual-only, and combined errors. If an additive-composition experiment fails PAC-06, the interface still permits reverting to the data-only M1 model without downstream consumer changes.

## Alternatives considered

| Category | Recommended | Alternative | Why not |
|---|---|---|---|
| Vehicle dynamics | Small NumPy/SciPy point-mass model | TUMFTM full quasi-steady simulator or a commercial-grade multibody model | Far more input parameters and dependencies than public data can identify; code reuse brings LGPL obligations. Use it as cited reference, not a required runtime. |
| Simulation dependencies | Existing NumPy/SciPy/Numba | JAX, CasADi, CVXPY, Torch | M5 explicitly owns JAX/Rust. Optimization/autodiff packages are unnecessary for the initial fixed-parameter lap solver and complicate Windows setup. |
| Track source | TUMFTM centerline/width data, pinned and attributed | Raw OpenF1 `location` traces as canonical geometry | OpenF1 coordinates have arbitrary origin and no lateral track position; race traces are sparse/noisy and do not supply the boundary widths needed for curvature/load constraints. |
| Track coverage | One circuit first, add files with provenance | Entire multi-circuit catalog immediately | Reduces licensing/provenance work and geometry QA while validating the numerical method. |
| Tyre temperature | Hidden, energy-driven state with uncertainty | Infer “measured” tyre temperature from weather/car telemetry | OpenF1 weather exposes ambient and track temperature; car telemetry exposes speed/controls/RPM, not tyre temperature. Such inference must stay explicitly latent. |
| Hybrid model | Physics baseline + posterior over pace residual | Physics + unchanged absolute Bayesian prediction | Both contain intercept, team/driver/compound/age effects; direct addition double counts overlapping terms and invalidates uncertainty. |
| FastF1 | Existing optional integration/cache only | Require authenticated FastF1 loads for M2 | Fresh timing access requires an F1 TV account for most data; this creates an avoidable account/access blocker. |

## Installation

No new dependencies recommended. Existing packages are sufficient:

```toml
# Existing project dependencies; no M2 addition
numpy
scipy
numba
pymc
duckdb
```

## Sources and confidence

**Overall confidence: MEDIUM.** Local stack/cache facts are high confidence because they were checked against the installed project and database. Official-source/API and license findings are medium confidence under the research confidence classifier (`websearch`, verified); model structure and geometry data-use interpretation are also medium. This is a recommendation and feasibility assessment, not a claim that public inputs identify real F1 vehicle parameters. No non-primary search result was used to assert API/auth/license facts.

- Local source of truth: `pyproject.toml`; `src/f1si/data/schema.py`; `src/f1si/data/sources/openf1.py`; `src/f1si/interfaces.py`; `DECISIONS.md` DEC-005, DEC-048, DEC-107, DEC-109, DEC-130.
- [OpenF1 API documentation](https://openf1.org/docs/) — official OpenF1 endpoint descriptions, sampled car data and location, historical availability, weather fields.
- [OpenF1 access and acceptable-use description](https://openf1.org/) — historical/live access split, personal/non-commercial intended use and request limits.
- [FastF1 authentication documentation](https://docs.fastf1.dev/api_reference/accounts_auth.html) — current F1 TV account requirement.
- [TUMFTM racetrack-database](https://github.com/TUMFTM/racetrack-database) — file format, track coverage, stated OpenStreetMap/satellite provenance, and LGPL-3.0 repository license.
- [TUMFTM laptime-simulation](https://github.com/TUMFTM/laptime-simulation) — quasi-steady simulation approach and LGPL-3.0 reference implementation.
