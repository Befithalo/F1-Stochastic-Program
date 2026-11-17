# Project Research Summary

**Project:** F1 Stochastic Intelligence Platform (f1si)  
**Domain:** Public-data, physics-informed Formula 1 race strategy and lap-pace modeling  
**Researched:** 2026-11-17  
**Confidence:** MEDIUM

## Executive Summary

f1si is a non-commercial replay platform that recommends pit strategy from lap-by-lap race state and uncertainty. M2 adds an interpretable pace foundation, not a reconstruction of proprietary F1 cars: public sources provide lap/stint/weather data and some sampled car telemetry, but not tire temperature, fuel mass, team-specific power/aero/grip, or tire forces. Historical OpenF1 from 2023 onward can supply car data, location, laps/stints, and weather; those optional telemetry endpoints are not in the current local cache/adapter. FastF1's software remains usable, but fresh timing archive access now requires F1 TV Access/Pro/Premium credentials for most data.

Keep the existing Python and DuckDB stack and `PaceModel` protocol. Establish provenance-checked track geometry and optional telemetry contracts; build a reduced-order point-mass pace model using named, versioned effective parameters with transparent assumed ranges; evolve tire temperature/wear as uncertain latent state; and let a regularized Bayesian model learn residuals. Do not claim direct observation or unique identification of hidden car/tire values. Validate each physical model with synthetic recovery, then require a pre-registered, race/stint-clustered real-data comparison before M3: the hybrid must beat the data-only Bayesian baseline on identical held-out next-lap targets. Preserve M1's failed PAC-06 result as historical context and do not retune or rescore its lock.

Key risks are confounding and leakage, uncertain geometry/data rights, and compute cost in the Monte Carlo path. Mitigate these with composite/effective identifiable fits and explicit assumed ranges, as-of-only data/fit construction, attribution and artifact-level licensing review, and cached/precomputed pace maps that preserve the existing runtime budget.

## Key Findings

### Recommended Stack

Retain the installed Python 3.12, NumPy, pandas, SciPy, Numba, PyMC, DuckDB, `uv`, and current quality tooling; no new runtime dependency is justified. Use NumPy/SciPy for geometry and the point-mass solver, with Numba only after a correct reference implementation; use PyMC for hierarchical residual uncertainty and DuckDB for versioned inputs and calibration metadata. Preserve deterministic, shape-stable `PaceModel.predict(driver, compound, tire_age, lap) -> (mean_s, sd_s)`; pass static race/circuit/weather/vehicle context through an immutable prebuilt model object, with no I/O or sampling inside `predict`.

The cache has 87 races and normalized laps, stints, and weather, but no high-rate car telemetry or track geometry. OpenF1 historical data from 2023 can provide `car_data` and approximate location at about 3.7 Hz, along with laps/stints/weather. Add these feeds only through explicit time-indexed, cutoff-visible ingestion; they are not prerequisites for the first solver. Fresh FastF1 archive downloads now require an active F1 TV Access/Pro/Premium account for most data, so use verified local history and OpenF1 historical access rather than making credentials an M2 dependency.

**Core technologies:**
- NumPy/SciPy: spatial geometry, forward/backward speed envelope, integration, and simple latent state — already installed and sufficient for a transparent reduced-order solver.
- DuckDB: versioned geometry, effective parameter/config provenance, and calibration artifacts — fits the existing store and as-of architecture.
- PyMC: partially pooled Bayesian fit over observed-minus-physics lap-time residuals — reuses the M1 stack while avoiding double counting absolute pace.
- Optional Numba: speed up established numerical kernels only after correctness — avoid introducing JAX/CasADi or M5's stack early.

### Expected Features

**Must have (table stakes):**
- Point-mass quasi-steady pace from distance/curvature with lateral grip and longitudinal acceleration/braking limits, effective power, drag, downforce, and mass.
- Versioned circuit geometry and explicit fuel-mass assumptions; do not describe fuel correction as measured.
- Hidden tire thermal/wear state, compound/stint reset semantics, and uncertainty/provenance reporting.
- A physics-plus-residual hybrid that keeps the M1 protocol, with data-only linear/Bayesian controls and cutoff-safe replay.
- Synthetic known-truth recovery for every physical model and a separate locked real-data gate.

**Should have (competitive):**
- Optional OpenF1 location/car-data ingestion for progress alignment and broad speed/controls diagnostics, with original timestamps and missingness retained.
- An energy/stress-informed degradation proxy, explicitly labeled as a proxy rather than tire energy or force measurement.
- A minimum 500 paired target, at least 15% hybrid MAE improvement over data-only Bayesian, plus paired uncertainty intervals and calibration/coverage, as the proposed M3 gate.

**Defer (v2+):**
- Multi-circuit coverage beyond a well-validated starter track, full quasi-steady or multibody fidelity, precise racing-line/track-grip inference, and detailed tire parameter fitting.
- Live streaming, team-grade telemetry claims, and M3-M6 ML/RL, JAX/Rust, API/UI, and deployment work.

### Architecture Approach

Build an immutable, cutoff-specific model context at the replay/backtest composition seam. It combines versioned track profile, as-of weather/race snapshot, and declared effective vehicle/fuel priors; a spatial solver produces baseline pace; a compact latent thermal/wear state modifies grip and pace; and a Bayesian residual fit corrects systematic remaining error. Existing race-state construction, policy, simulator, and scoring continue to consume the unchanged `PaceModel` boundary. Keep results behind the existing locked scoring door, and never pass the accessor or future rows into model prediction or fit construction.

**Major components:**
1. Data and track profile: OpenF1 normalized history, optional timestamped telemetry, and pinned geometry with source/license/hash/coordinate transform.
2. Physics context and point-mass solver: effective vehicle/fuel ranges, environment snapshot, curvature speed caps, acceleration/braking passes, and uncertainty.
3. Latent tire state: temperature/energy proxy, wear accumulation, compound/stint resets, and uncertainty propagation.
4. Hybrid pace fit and evaluator: residual-only Bayesian correction, unchanged protocol, paired controls, immutable fit provenance, and locked grouped evaluation.

### Critical Pitfalls

1. **Unidentifiable team/car/tire parameters** — Fit only low-dimensional effective/composite parameters supported by lap times; publish season/era-specific assumed ranges and uncertainty; use partial pooling and sensitivity/identifiability checks. Never imply team-private values were recovered.
2. **Look-ahead in as-of features or fit rows** — Route all replay inputs through the one as-of accessor; reconstruct stints only from visible rows; group holdouts by stint/race and lock before fitting; test future-row perturbations for invariance.
3. **Telemetry and geometry overstated** — OpenF1 samples are sparse, approximate, and lack lateral position; temperature is ambient/track weather, not tire temperature. Preserve timestamps, nulls, coordinate/provenance metadata, and use telemetry as diagnostic support rather than ground truth.
4. **Data/software rights conflated** — OpenF1's free historical access is intended for non-commercial use and has rate limits; API openness does not license F1 data. FastF1's MIT license does not license timing data. TUMFTM track assets cite OSM/satellite-derived inputs and LGPL software; verify the individual asset, attribution, redistribution terms, and pinned provenance before shipping it.
5. **Physics harms validation or runtime** — Synthetic recovery does not establish real predictive gain; adjacent laps leak state; expensive physics inside every simulated path can break the 50,000-race budget. Use a separately locked grouped holdout, controls/ablations, precomputed maps, and benchmark full integration.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 9: Data and Geometry Readiness
**Rationale:** Geometry and time/provenance contracts underpin the solver; establish one circuit and cutoff-safe optional feed shape before physics work depends on them. Existing cache lacks both high-rate car telemetry and track geometry.  
**Delivers:** A provenance-reviewed starter circuit profile, geometry validation/coverage, effective parameter schema, and optional OpenF1 car_data/location normalization with race-clock visibility. If source terms or coverage are unsuitable, keep telemetry optional and expose a declared fallback.  
**Addresses:** Circuit geometry, telemetry auditability, assumption/provenance reporting.  
**Avoids:** Treating sparse arbitrary-origin location as surveyed geometry, license ambiguity, and look-ahead joins.

### Phase 10: Point-Mass PaceModel
**Rationale:** The solver is the foundational physics baseline and can be validated independently before adding latent tire complexity.  
**Delivers:** A reduced-order distance/curvature solver with effective power, drag, downforce, grip, mass/fuel assumptions; deterministic context-bound `PhysicsPaceModel`; synthetic parameter recovery and sensitivity checks.  
**Uses:** NumPy/SciPy, optional Numba after correctness, versioned DuckDB inputs.  
**Implements:** Effective parameters and speed-envelope solver while leaving `PaceModel` signature unchanged.  
**Avoids:** High-dimensional fitting from lap times and simulation-path performance regressions.

### Phase 11: Tire Thermal and Energy/Wear State
**Rationale:** Tire state depends on solver/track context and adds latent dynamics and pit resets, so build it after the baseline is stable.  
**Delivers:** Compact temperature/wear state with energy/stress proxy, explicit uncertain reset prior, weather boundary inputs, and synthetic recovery including unidentifiable cases. Compare with the simpler M1 monotone-wear model.  
**Addresses:** Compound/stint semantics, thermal/wear evolution, uncertainty.  
**Avoids:** Calling modeled temperature measured, using public controls as direct tire-force/energy, or overstating recovery from sparse lap-time evidence.

### Phase 12: Hybrid Pace and Locked Held-Out-Stint Gate
**Rationale:** Only a composable, evaluated hybrid can resolve active PAC-06; integration and scoring must follow stable component models and a precommitted holdout.  
**Delivers:** Bayesian residual-only hybrid (physics mean plus regularized residual mean, uncertainty without double counting), unchanged protocol, physics-only/data-only controls, immutable fit and feature audit trail, and locked paired evaluation. Proposed gate: at least 500 identical paired next-lap targets, grouped by complete stint/race, with at least 15% lower MAE than data-only Bayesian; publish paired intervals and coverage.  
**Implements:** Existing pace factory/replay seam and evaluation architecture; no policy/simulator fork.  
**Avoids:** Retuning M1 PAC-06, lap-wise leakage, residual cancellation of physics, or treating synthetic/in-sample results as success. If gate fails, report failure and do not advance to M3 on the strength of synthetic results.

### Phase Ordering Rationale

- Geometry, visibility, provenance, and model context must be established before solver calibration; the current cache alone cannot support spatial physics.
- Point-mass pace precedes thermal state because it supplies a baseline force/energy proxy; the tire model then supplies a clearly bounded latent correction.
- Hybrid residual fitting and its locked real-data gate come last, after baseline/control models and feature contracts are stable.
- Preserve the existing `PaceModel` consumer seam and race strategy architecture throughout; cache/precompute numerical work to meet the existing simulator performance target.
- Keep every physical-model synthetic recovery suite separate from real-data held-out evaluation.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 9:** Specific geometry asset/variant suitability, license and underlying data redistribution terms; OpenF1 endpoint coverage, timestamp mapping, rate limits, and cutoff semantics.
- **Phase 11:** Which low-dimensional thermal/wear formulation is identifiable with available observations; define reset priors and energy proxy validity.
- **Phase 12:** Pre-register the grouped held-out sample, target cleaning rules, paired uncertainty method, and exact PAC-06 gate before opening outcomes.

Phases with standard patterns (skip research-phase):
- **Phase 10:** A basic point-mass forward/backward speed envelope and numerical synthetic recovery are established methods, once Phase 9 fixes geometry and units. Research may still be needed for a particular circuit asset, not the solver pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | High confidence in local stack/cache facts; official API/auth and data-term findings are researched, but permissions apply to underlying data and individual assets. |
| Features | MEDIUM | Established solver and thermal concepts are documented; public observations cannot validate private parameter values or fully identify tire dynamics. |
| Architecture | HIGH | Existing protocol, data doors, and cache boundaries are locally verified; physics/latent-state details remain medium-confidence model choices. |
| Pitfalls | MEDIUM | Leakage, sparse sampling, licensing, and compute risks are well grounded; practical geometry coverage and real-data identifiability require implementation evidence. |

**Overall confidence:** MEDIUM

### Gaps to Address

- **Geometry asset decision:** Confirm chosen circuit file, variant, direction, units, coordinate transform, OSM/satellite provenance, and redistribution rights before vendoring or publishing derived geometry.
- **Telemetry availability and mapping:** Verify OpenF1 historical endpoint coverage and session-key/time conversion for candidate races; do not make telemetry a blocker for baseline pace if unavailable.
- **Identifiability:** Set transparent season-specific assumed ranges for effective car/fuel/tire parameters; establish which composite scales can be learned and report when data do not distinguish them.
- **Thermal state:** No tire temperature or direct tire energy is observed. Decide whether two-node state complexity is warranted by grouped validation, and preserve a simpler fallback.
- **Evaluation registration:** Lock the new held-out stint/race set, clean-lap policy, paired metric/interval procedure, and gate before fitting; do not expose outcomes during tuning.
- **M1 boundary:** Keep M1 PAC-06's locked miss and the separate 2026 report distinct. Use `.planning/M1-BASELINE.md` only for the fixed strategy baseline; do not recompute or pool it.

## Sources

### Primary (HIGH confidence)
- Local project sources: `pyproject.toml`, `src/f1si/data/schema.py`, `src/f1si/data/sources/openf1.py`, `src/f1si/interfaces.py`, `.planning/PROJECT.md`, `F1 Docs/BUILD_PLAN.md`, `DECISIONS.md`, `.planning/M1-BASELINE.md` — stack/cache/protocol, active requirements, M1 baseline and accepted decisions.
- [OpenF1 API documentation](https://openf1.org/docs/) — endpoints, historical availability, weather and sampled car/location fields.
- [OpenF1 access and acceptable-use description](https://openf1.org/) — access/rate limits, intended non-commercial use, data ownership disclaimer.
- [FastF1 authentication documentation](https://docs.fastf1.dev/api_reference/accounts_auth.html) — current F1 TV account requirement for most fresh archive data.
- [TUMFTM racetrack-database](https://github.com/TUMFTM/racetrack-database) and [lap-time simulation](https://github.com/TUMFTM/laptime-simulation) — geometry provenance and quasi-steady reference; inspect asset/software licensing separately.

### Secondary (MEDIUM confidence)
- [Online Time-Optimal Trajectory Planning on Three-Dimensional Race Tracks](https://arxiv.org/abs/2304.10954) — quasi-steady track/vehicle solver context.
- [Optimal Tyre Management of a Formula One Car](https://ifatwww.et.uni-magdeburg.de/ifac2020/media/pdfs/0335.pdf) — thermal/wear modeling concepts and hidden-parameter challenge.
- [A State-Space Approach to Modeling Tire Degradation in Formula 1 Racing](https://arxiv.org/abs/2512.00640) and [Explainable Time Series Prediction of Tyre Energy in Formula One Race Strategy](https://arxiv.org/abs/2501.04067) — public-data limits, degradation and energy-proxy context.
- `.planning/research/STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md` — synthesized technical research, sourced as listed in each artifact.

### Tertiary (LOW confidence)
- None used for a roadmap-critical claim. Effective parameter ranges and hidden thermal-state forms remain modeling assumptions to validate, not sourced facts.

---
*Research completed: 2026-11-17*  
*Ready for roadmap: yes*
