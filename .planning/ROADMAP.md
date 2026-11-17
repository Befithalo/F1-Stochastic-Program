# Roadmap: F1 Stochastic Intelligence Platform

## Milestones

- **v1.0 M1 Core Stochastic Engine** — shipped 2026-11-17; eight phases and 55 plans. PAC-06 was not met and carries into M2 under DEC-130.
- **v2.0 M2 Physics** — active; Phases 9–12 add a point-mass pace foundation, uncertain tire state, and a separately locked hybrid evaluation gate before M3.

## Overview

M2 establishes provenance-checked, cutoff-safe physics inputs; builds a geometry-driven point-mass pace model and latent tire thermal/wear state; then composes the physics prediction with the existing Bayesian pace model as a residual learner. Its real-data held-out-stint result determines whether the pre-M3 gate passes. The work preserves the M1 PaceModel boundary, strategy and simulator consumers, fixed M1 strategy baseline, reproducibility, and the 50,000-race runtime budget.

## M1 Shipped Summary

M1 delivered the data foundation, typed model protocols, linear tire wear and free-track optimizer, Monte Carlo simulator, Kalman tire filter, Longstaff-Schwartz strategy and replay, ten-race evidence view, Bayesian pace model, and Markov regime model with a 20-race evaluation. Phase 7's locked Bayesian PAC-06 result missed its gate and remains open for M2. Detailed plans, verification, reports, and closeout evidence are archived under .planning/milestones/v1.0-*.

## M2 Guardrails

- Enforce no-lookahead at every input, fit, replay, and held-out target boundary.
- Use cached inputs and historical OpenF1 only through the existing rate-limited cache and as-of boundary. Keep OpenF1 telemetry and location optional when coverage or coordinate matching is poor; report missing coverage. Do not make new FastF1 downloads a dependency.
- Treat tire temperature, fuel, and absolute car parameters as hidden unless independently identified. Report effective fitted composites separately from assumptions.
- Keep M2 free of UI/UX work and do not change simulator, strategy, or backtest pace consumers to support the models.
- Record method, source, geometry-rights, and evaluation decisions in DECISIONS.md.
- Preserve the existing 50,000-race runtime budget.

## Phases

- [ ] **Phase 9: Data and Geometry Readiness** - Establish cutoff-safe inputs, optional telemetry coverage, provenance-reviewed geometry, and effective-parameter records.
- [ ] **Phase 10: Point-Mass PaceModel** - Deliver a geometry-driven pace prediction through the existing PaceModel contract, with physical checks and synthetic recovery.
- [ ] **Phase 11: Tire Thermal and Energy/Wear State** - Add compound-aware latent thermal/wear state, weather boundaries, resets, and uncertainty.
- [ ] **Phase 12: Hybrid Pace and Locked Held-Out-Stint Gate** - Compose a Bayesian residual learner behind physics and score it once against the preregistered real-data holdout.

## Phase Details

### Phase 9: Data and Geometry Readiness

**Goal**: Users can build an auditable, cutoff-safe physics context from existing cached race data, optional historical telemetry/weather, and a rights-reviewed Bahrain geometry profile.
**Depends on**: Phase 8
**Requirements**: DAT-01, GEO-01, PAR-01
**Success Criteria** (what must be TRUE):
  1. A user can audit cached inputs and build a reproducible physics input with optional OpenF1 telemetry, location, and weather, preserving original timestamps and race/session-clock mapping to each cutoff; unavailable coverage is reported and poor telemetry or location coverage leaves a documented fallback.
  2. A user can select a versioned, unit-checked Bahrain 2023 track profile whose source, coordinate transform, quality checks, attribution, and redistribution terms are recorded; if rights are unclear, the profile remains external/local and is referenced by digest and provenance.
  3. A user can inspect which vehicle, fuel, and tire quantities are effective fitted composites versus hidden assumptions, including supporting evidence, era-specific bounds, uncertainty, and sensitivity results.

**Plans:** 4 plans
Plans:
**Wave 1**
- [ ] 09-01-PLAN.md — Create Wave 0 validation contracts for Phase 9.
- [ ] 09-02-PLAN.md — Build cutoff-safe optional channels and the PhysicsInput envelope.

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 09-03-PLAN.md — Validate and pin the Bahrain 2023 geometry profile.

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 09-04-PLAN.md — Publish the parameter register, numeric sensitivity result, and closeout report.

**Required closeout for every phase**: Report the unchanged M1 baseline from .planning/M1-BASELINE.md: podium Brier 0.055456 (grid baseline 0.073693); top-10 Brier 0.144645 (grid baseline 0.169086); inclusive P05–P95 coverage 82.26% (16,508/20,001); signed planned-stop timing error +1.174 laps (695 matched stops); and top-action agreement with observed team calls 17.22% (695 matched stops). Preserve the original definitions and denominators; do not recompute this baseline or include the separate 2026 report. Require passing Ubuntu and Windows CI before phase close. Record method/source/evaluation decisions in DECISIONS.md and keep the 50,000-race runtime budget.

### Phase 10: Point-Mass PaceModel

**Goal**: Users can obtain a deterministic geometry-driven lap-time mean and uncertainty through the existing PaceModel contract, with identifiable effective inputs and physical behavior independently checked.
**Depends on**: Phase 9
**Requirements**: PHY-01, PHY-02
**Success Criteria** (what must be TRUE):
  1. A user can request lap-time mean and uncertainty from track distance and curvature, effective drive power, drag, downforce, grip, and declared mass/fuel inputs through the current PaceModel contract.
  2. Synthetic known-parameter trajectories recover the model's identifiable parameters within declared tolerances, while physical invariants and independent parameter/track sensitivity checks behave as documented.

**Plans**: TBD
**Required closeout for every phase**: Report the unchanged M1 baseline from .planning/M1-BASELINE.md: podium Brier 0.055456 (grid baseline 0.073693); top-10 Brier 0.144645 (grid baseline 0.169086); inclusive P05–P95 coverage 82.26% (16,508/20,001); signed planned-stop timing error +1.174 laps (695 matched stops); and top-action agreement with observed team calls 17.22% (695 matched stops). Preserve the original definitions and denominators; do not recompute this baseline or include the separate 2026 report. Require passing Ubuntu and Windows CI before phase close. Record method/source/evaluation decisions in DECISIONS.md and keep the 50,000-race runtime budget.

### Phase 11: Tire Thermal and Energy/Wear State

**Goal**: Users can account for compound-aware pace changes from uncertain hidden tire thermal and wear state without presenting weather or proxy measurements as direct tire observations.
**Depends on**: Phase 10
**Requirements**: TIR-01, TIR-02
**Success Criteria** (what must be TRUE):
  1. A user can obtain compound-aware pace and uncertainty from a documented energy/stress proxy and hidden thermal/wear state, with cutoff-visible weather boundaries and explicit stint and compound resets.
  2. Synthetic known-parameter stints recover identifiable tire-model parameters, and a real cutoff-safe stint report shows how latent temperature and wear uncertainty affects predictions while labeling what public data cannot identify.

**Plans**: TBD
**Required closeout for every phase**: Report the unchanged M1 baseline from .planning/M1-BASELINE.md: podium Brier 0.055456 (grid baseline 0.073693); top-10 Brier 0.144645 (grid baseline 0.169086); inclusive P05–P95 coverage 82.26% (16,508/20,001); signed planned-stop timing error +1.174 laps (695 matched stops); and top-action agreement with observed team calls 17.22% (695 matched stops). Preserve the original definitions and denominators; do not recompute this baseline or include the separate 2026 report. Require passing Ubuntu and Windows CI before phase close. Record method/source/evaluation decisions in DECISIONS.md and keep the 50,000-race runtime budget.

### Phase 12: Hybrid Pace and Locked Held-Out-Stint Gate

**Goal**: Users can choose a physics-based pace model with a Bayesian residual correction and audit a one-time, preregistered real-data comparison that controls whether M3's gate is met.
**Depends on**: Phase 11
**Requirements**: HYB-01, EVAL-01, GATE-01, OPS-01, BASE-01
**Success Criteria** (what must be TRUE):
  1. A user can select a hybrid PaceModel whose physical prediction is the base and whose existing Bayesian pace model learns observed-minus-physics residuals; the protocol, simulator, strategy, backtest, and other pace consumers remain unchanged.
  2. A user can audit a new preregistered comparison on identical next-lap targets from complete held-out stints, with cutoff-safe training rows, race/stint-clustered uncertainty, and locks separate from M1 PAC-06 and the 2026 report.
  3. The report declares the gate passed only with at least 500 paired targets across at least 10 races, at least 15% lower hybrid point-estimate MAE, a race/stint-clustered 95% improvement interval with a positive lower bound, and 90% predictive-interval coverage no more than 5 percentage points below the Bayesian control; if any condition fails, the failure is reported without tuning or rescoring the lock.
  4. A user can reproduce model and phase reports from versioned inputs and fixed seeds, see that the 50,000-race runtime budget and the fixed M1 baseline are preserved, and confirm passing Ubuntu and Windows CI at phase closeout.

**Plans**: TBD
**Required closeout for every phase**: Report the unchanged M1 baseline from .planning/M1-BASELINE.md: podium Brier 0.055456 (grid baseline 0.073693); top-10 Brier 0.144645 (grid baseline 0.169086); inclusive P05–P95 coverage 82.26% (16,508/20,001); signed planned-stop timing error +1.174 laps (695 matched stops); and top-action agreement with observed team calls 17.22% (695 matched stops). Preserve the original definitions and denominators; do not recompute this baseline or include the separate 2026 report. Require passing Ubuntu and Windows CI before phase close. Record method/source/evaluation decisions in DECISIONS.md and keep the 50,000-race runtime budget.

## Progress

**Execution Order:** Phases execute in numeric order: 9 → 10 → 11 → 12.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 9. Data and Geometry Readiness | v2.0 | 0/TBD | Not started | - |
| 10. Point-Mass PaceModel | v2.0 | 0/TBD | Not started | - |
| 11. Tire Thermal and Energy/Wear State | v2.0 | 0/TBD | Not started | - |
| 12. Hybrid Pace and Locked Held-Out-Stint Gate | v2.0 | 0/TBD | Not started | - |
