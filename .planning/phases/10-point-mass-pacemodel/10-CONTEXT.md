# Phase 10: Point-Mass PaceModel - Context

**Gathered:** 2026-11-17  
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a deterministic, reduced-order, geometry-driven lap-time model behind the existing `PaceModel` contract. It covers the physical mean and uncertainty from effective power, drag, downforce, grip, and declared mass/fuel context; identifiable parameter recovery and physical validation use synthetic known-parameter trajectories plus independent sensitivities. Phase 10 does not implement tire thermal/wear state, the Bayesian residual hybrid, a multi-circuit geometry library, changes to simulator/strategy/backtest consumers, or UI/UX.

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

### Milestone scope, requirements, and fixed baselines
- `.planning/PROJECT.md` — M2 physics goal, audience constraints, data limits, and no-UI boundary.
- `.planning/REQUIREMENTS.md` — PHY-01 and PHY-02, identifiability, no-lookahead, synthetic recovery, and validation rules.
- `.planning/ROADMAP.md` — Phase 10 boundary, success criteria, dependencies, and required closeout disclosures.
- `.planning/M1-BASELINE.md` — immutable M1 metrics and denominators required in the phase report.
- `F1 Docs/BUILD_PLAN.md` — original architecture, data constraints, `PaceModel` seam, and physical-model motivation.
- `DECISIONS.md` — especially DEC-130, DEC-132–139: locked holdouts, fixed baseline, data, assumptions, seam, geometry, and Phase 9 evidence choices.
- `.planning/phases/09-data-and-geometry-readiness/09-CONTEXT.md` — upstream cutoffs, geometry, parameter provenance, and interface decisions.
- `.planning/phases/09-data-and-geometry-readiness/09-PHASE-REPORT.md` — measured data availability, pinned geometry facts, and numeric identifiability limits.

### Existing implementation contracts
- `src/f1si/interfaces.py` — exact `PaceModel.predict` protocol and deterministic output contract.
- `src/f1si/geometry/profile.py` — immutable digest-checked geometry, units, curvature, and profile validation.
- `src/f1si/data/physics_input.py` — immutable race-scoped, cutoff-safe inputs and optional-channel fallback semantics.
- `src/f1si/parameters/register.py` — versioned effective estimates versus hidden assumptions.
- `src/f1si/pace/bayesian.py` — existing data-only pace model; Phase 12 will use it for residual learning, while Phase 10 preserves the same consumer seam.
- `src/f1si/pace/linear.py` — established pace-fit and coefficient conventions.
- `.planning/research/SUMMARY.md` — M2 data, geometry, identifiability, and validation research.

### External references already approved for M2
- `https://github.com/TUMFTM/laptime-simulation` — quasi-static lap-time simulation reference; reimplement ideas, do not copy code, and verify terms before reuse.
- `https://github.com/TUMFTM/racetrack-database` — provenance source for the Phase 9 pinned Sakhir profile.
- `https://www.fia.com/regulation/fia-formula-1-world-championship-technical-regulations` — regulatory bounds are constraints, not observed team-specific parameters.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PaceModel` in `src/f1si/interfaces.py` is the stable vectorized prediction contract.
- `GeometryProfile` supplies immutable transformed coordinates, widths, total distance, validation results, and a digest-pinned reference.
- `PhysicsInput` owns copied snapshot data and source coverage without giving a model an accessor or results door.
- `ParameterRegister` distinguishes evidence-backed effective estimates from hidden assumptions and bounds.
- The existing Bayesian and linear pace fits establish driver, compound, age, and lap indexing patterns.

### Established Patterns
- Model predictions are deterministic vectorized arrays; random sampling belongs in the simulator.
- Race data is cutoff-safe through `AsOfAccessor`; models receive immutable prepared data and do not query the database.
- Geometry artifacts are versioned, content-digest checked, unit validated, and fail closed.
- M1 and M2 holdout data is locked; 2026 stays out of tuning.

### Integration Points
- Add the physics implementation in `src/f1si/pace/` and construct it using prepared geometry, `PhysicsInput`, and parameter values.
- Keep simulator, strategy, replay, backtest, and `PaceModel` call sites unchanged.
- Reuse Phase 9 geometry and parameter evidence but do not assume its effective lap-number slope is predictive physical sensitivity.

</code_context>

<specifics>
## Specific Ideas

- Bahrain 2023/Sakhir is the initial reference profile; the pinned source asset remains local because its specific redistribution rights were not established.
- Physical behavior should be inspectable through documented equations, units, limits, and sensitivity diagnostics.
- Phase 10 must report the unchanged M1 baseline and the known PAC-06 miss exactly as already locked, without retuning it.

</specifics>

<deferred>
## Deferred Ideas

- Tire temperature, energy-driven wear, and compound resets belong to Phase 11.
- Bayesian residual learning and the real held-out-stint gate belong to Phase 12.
- Full-circuit geometry coverage, detailed transient/multibody vehicle dynamics, private team parameter recovery, and UI/UX are out of scope.

</deferred>

---

*Phase: 10-point-mass-pacemodel*  
*Context gathered: 2026-11-17*
