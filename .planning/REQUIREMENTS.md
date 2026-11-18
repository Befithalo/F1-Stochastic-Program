# Requirements: F1 Stochastic Intelligence Platform

**Milestone:** v2.0 — M2 Physics  
**Defined:** 2026-11-17  
**Core Value:** For any driver at any lap of a replayed race, give a pit-strategy recommendation whose uncertainty is honest: cutoff-safe, checked against synthetic ground truth, and evaluated against real race data with limitations disclosed.

## v1 Requirements

Requirements committed for M2. Every physics model must include a synthetic known-parameter recovery test. Synthetic data is test-only; real race data is required for model fitting and comparative evaluation. Every phase must pass required CI on Ubuntu and Windows and report the fixed M1 strategy baseline from `.planning/M1-BASELINE.md`.

### Data and Geometry

- [x] **DAT-01**: A user can build a provenance-checked, cutoff-safe physics input from the existing cached race data and optional historical OpenF1 car telemetry, location, and weather, with unavailable coverage reported explicitly.
- [x] **GEO-01**: A user can run the pace model on a versioned, unit-checked track profile with source, coordinate transform, quality checks, and redistribution terms recorded; Bahrain 2023 is the reference track.
- [x] **PAR-01**: A user can inspect which vehicle, fuel, and tire quantities are fitted effective parameters versus assumed hidden values, including evidence, era-specific bounds, uncertainty, and sensitivity results.

### Point-Mass Pace

- [x] **PHY-01**: A user can obtain a deterministic lap-time mean and uncertainty from track distance/curvature, effective drive power, drag, downforce, grip, and declared mass/fuel inputs through the existing `PaceModel` contract.
- [x] **PHY-02**: A user can verify the point-mass model's recovered identifiable parameters and physical invariants using synthetic known-parameter trajectories and independent parameter/track sensitivity checks.

### Tire Thermal and Wear State

- [ ] **TIR-01**: A user can obtain compound-aware tire pace and uncertainty from a hidden thermal/wear state driven by temperature and a documented energy/stress proxy, with weather boundaries and stint/compound resets represented explicitly.
- [ ] **TIR-02**: A user can verify tire-model parameter recovery on synthetic known-parameter stints and see how latent temperature and wear uncertainty affects predictions on real, cutoff-safe stints.

### Hybrid and Evaluation Gate

- [ ] **HYB-01**: A user can select a hybrid `PaceModel` whose physical prediction is the base and whose existing Bayesian model learns residual pace, with the current protocol and simulator, strategy, and backtest consumers unchanged.
- [ ] **EVAL-01**: A user can audit a pre-registered real-data held-out-stint comparison of the hybrid and data-only Bayesian models on identical next-lap targets, with no look-ahead and no reuse of the M1 PAC-06 or 2026 holdout locks.
- [ ] **GATE-01**: M2 passes the pre-M3 gate only if the locked hybrid evaluation has at least 500 paired targets from at least 10 races, at least 15% lower point-estimate MAE than the data-only Bayesian model, a race/stint-clustered 95% interval whose lower bound shows positive improvement, and 90% predictive-interval coverage no more than 5 percentage points below the Bayesian control. If it fails, report the failure without tuning or rescoring the lock.
- [ ] **OPS-01**: A user can reproduce the model and phase reports from versioned inputs and fixed seeds, retain the existing 50,000-race runtime budget, and see a passing Ubuntu and Windows CI result at each phase closeout.
- [ ] **BASE-01**: A user can compare every M2 phase-end summary against the unmodified M1 baseline: podium Brier 0.055456 (grid 0.073693), top-10 Brier 0.144645 (grid 0.169086), inclusive P05–P95 coverage 82.26% (16,508/20,001), signed stop-timing error +1.174 laps (695 stops), and team-call agreement 17.22% (695 stops).

## Data, Identifiability, and Validation Decisions

| Question | M2 decision |
|----------|-------------|
| What data does each part need, and what is cached? | Existing DuckDB has race laps, stints, pit stops, control, results, and weather; it lacks high-rate car telemetry and track geometry. The point-mass model needs a track distance/curvature profile and declared vehicle/environment context. OpenF1 historical endpoints can add speed, RPM, gear, throttle, brake, DRS, approximate position, lap/stint and minute weather (including ambient and track temperature) from 2023. Telemetry/location remain optional when coverage or coordinate matching is poor. There is no documented tire-temperature channel. |
| Are new FastF1 downloads needed? | No. Use the verified local cache and add historical OpenF1 data through the existing rate-limited cache. Fresh FastF1 timing archive access is not an M2 dependency and generally requires F1 TV Access/Pro/Premium authentication. OpenF1 is an unofficial historical source, with its own rate/usage and underlying-data terms; keep the project non-commercial, cache responsibly, credit sources, and do not republish raw dumps. |
| Where does track geometry come from? | Phase 9 must validate a pinned geometry asset and its license before it is bundled. TUMFTM's racetrack database includes Sakhir and other circuits, but its centerlines/widths are derived from OpenStreetMap and satellite imagery and have variable quality; inspect the individual asset and attribution terms. If redistribution is unclear, keep the asset external/local and record its digest/provenance rather than copying it into the repository. |
| What can be fitted? | Fit only low-dimensional effective/composite quantities supported by telemetry and lap-time variation: for example power-to-mass or speed-dependent effective acceleration, effective drag-to-mass, and combined cornering/grip response under sufficiently varied conditions. Fit pace residual and compound effects from real stints using cutoff-visible rows. Check identifiability before reporting any coefficient. |
| What must be assumed? | Absolute car mass, engine power, drag area, downforce coefficient, tire friction curve, true tire temperature/heat capacity/cooling, initial fuel, and exact fuel burn are not uniquely observable from public data. Use broad, season-specific scenario ranges bounded where possible by the matching FIA regulations and cited public vehicle/thermal literature. FIA minima are constraints, not measured car values. Keep hidden states and assumptions labeled, with sensitivity analyses; do not claim team-specific values. |
| How will M2 distinguish physics from a good fit? | Check physical invariants and domain limits; recover declared parameters from independent synthetic trajectories; validate geometry, units, solver convergence, and sensitivity; fit only training races/stints; then score a separately locked set of whole held-out stints/races on identical targets. Compare physics-only, data-only Bayesian, and hybrid controls with paired race/stint-clustered uncertainty, interval coverage, and ablations. A synthetic recovery pass cannot satisfy the real-data gate. |

The proposed M2 gate is intentionally stricter than a positive point estimate: require at least 15% lower MAE, at least 500 paired rows across at least 10 races, positive lower 95% clustered improvement bound, and no more than a 5-point coverage loss. The final sample, cleaning rules, seed, and scoring command must be locked before model fitting and outcome scoring.

## Future Requirements

### Deferred Physics and Product Work

- **PHY-03**: Support validated geometry and full race-pace calibration for every F1 circuit.
- **TIR-03**: Identify true per-team tire temperatures, tire forces, and detailed compound-specific thermal constants from private telemetry.
- **SIM-01**: Add full transient or multibody vehicle dynamics.
- **ML-01**: Train an XGBoost baseline, neural surrogate, and reinforcement-learning strategy agent.
- **PERF-01**: Add JAX and Rust backends.
- **PROD-01**: Add FastAPI, Next.js, live mode, deployment, and commercial data integrations.

## Out of Scope

| Feature | Reason |
|---------|--------|
| New FastF1 archive downloads | F1 TV Access would be required for most fresh archive access; OpenF1 historical endpoints and the existing cache are sufficient for M2. |
| Claims of exact team-specific power, aero, grip, fuel, or tire temperature | These are not separately identified by public telemetry and must remain declared assumptions or effective composites. |
| Full multibody simulation or private tire-force reconstruction | M2 targets an interpretable reduced-order point-mass model with public data. |
| ML/RL strategy agents, JAX/Rust, live streaming, API/UI, and deployment | These belong to later milestones. No UI/UX changes are in M2. |
| Using or retuning the M1 2026 holdout to tune M2 | The report is a separate, retrospectively unblinded holdout and must remain untouched. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DAT-01 | Phase 9 | Complete |
| GEO-01 | Phase 9 | Complete |
| PAR-01 | Phase 9 | Complete |
| PHY-01 | Phase 10 | Complete |
| PHY-02 | Phase 10 | Complete |
| TIR-01 | Phase 11 | Pending |
| TIR-02 | Phase 11 | Pending |
| HYB-01 | Phase 12 | Pending |
| EVAL-01 | Phase 12 | Pending |
| GATE-01 | Phase 12 | Pending |
| OPS-01 | Phase 12 | Pending |
| BASE-01 | Phase 12 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Every requirement maps to exactly one phase; duplicate mappings: 0
- Unmapped: 0

---
*Requirements defined: 2026-11-17*
*Last updated: 2026-11-17 after M2 Physics roadmap creation*
