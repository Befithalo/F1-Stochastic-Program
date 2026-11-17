# Phase 9: Data and Geometry Readiness - Context

**Gathered:** 2026-11-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Prepare an auditable, cutoff-safe physics input for the later pace models from the existing race cache, optional historical OpenF1 channels, a provenance-reviewed Bahrain 2023 geometry profile, and a parameter register. This phase does not build the point-mass solver, tire state model, hybrid model, or a user interface.

</domain>

<decisions>
## Implementation Decisions

### Input cutoff and telemetry coverage
- **D-01:** Read optional OpenF1 telemetry, location, and weather only through the rate-limited cache and the as-of boundary. Preserve source timestamps and the mapping to the lights-out race clock; include a row only when it was visible at the requested cutoff.
- **D-02:** Keep optional channels optional. Report per-race and per-channel coverage and quality. If data are sparse, use the documented cached-lap fallback; never silently fabricate telemetry, interpolate across a cutoff, or treat approximate location as survey-grade geometry.

### Geometry provenance and rights
- **D-03:** Evaluate a versioned Sakhir/Bahrain 2023 profile as the reference candidate. Record its source, version or retrieval reference, coordinate frame and transform, units, quality checks, attribution, and SHA-256 digest.
- **D-04:** Bundle a geometry asset only after the specific file's redistribution terms are verified. If terms are unclear, keep it external/local and refer to it by digest and provenance; downstream model execution must fail clearly when the required asset is unavailable or fails quality checks.

### Parameter identifiability and assumptions
- **D-05:** Fit and publish only effective parameter composites whose identifiability is supported by available evidence. Label absolute mass, power, aero, grip, fuel, and tire quantities as hidden assumptions unless independently identified.
- **D-06:** For assumed quantities, record cited evidence, season-specific bounds, uncertainty, and sensitivity. Treat regulatory minima as constraints, not measured team values; do not report team-specific hidden values as recovered parameters.
- **D-09:** Phase 9 must provide a numeric sensitivity/identifiability result for the parameter register without expanding into the Phase 10 lap solver. Report evidence-supported identifiability sensitivity now; label any predictive lap-time sensitivity that cannot be computed before the solver as `not_estimable_pre_solver` and carry it into Phase 10. Do not describe the latter as completed.

### Physics input integration
- **D-07:** Construct an immutable, race-scoped physics input before the simulation hot path. Model code receives prepared values and no cache accessor. Preserve the existing `PaceModel` signature and leave simulator, strategy, and backtest consumers unchanged.
- **D-08:** Extend the existing normalized source/cache and as-of design where required. Tests must prove cutoff safety and preserve original source time provenance; current-race results and the separate 2026 holdout remain inaccessible to M2 fitting.

### the agent's Discretion
- Choose concrete schemas, coverage summaries, geometry quality thresholds, candidate asset pinning mechanics, and fit diagnostics that satisfy the locked requirements and fail closed on missing or invalid inputs.
- Use OpenF1 only where observed coverage and timestamp alignment pass those documented quality checks. No new FastF1 downloads are required.

</decisions>

<canonical_refs>
## Canonical References

### Milestone and acceptance criteria
- `.planning/PROJECT.md` — active milestone scope, guardrails, and retained M1 disclosures.
- `.planning/REQUIREMENTS.md` — DAT-01, GEO-01, and PAR-01 requirements plus M2 data and identifiability decisions.
- `.planning/ROADMAP.md` — Phase 9 boundary, success criteria, phase order, and required M1 baseline closeout.
- `.planning/M1-BASELINE.md` — fixed M1 baseline values and denominators to copy into the phase report.
- `.planning/research/SUMMARY.md` — M2 data, geometry, identifiability, and validation research.
- `F1 Docs/BUILD_PLAN.md` — original architecture, available model seams, data constraints, and milestone gates.
- `DECISIONS.md` — project method decisions, including DEC-130 and DEC-132 through DEC-136.

### Existing data and model contracts
- `src/f1si/data/asof.py` — public cutoff-safe accessor boundary.
- `src/f1si/data/_snapshot.py` — snapshot construction and visibility semantics.
- `src/f1si/data/schema.py` — normalized cache schema, units, and row visibility fields.
- `src/f1si/data/sources/openf1.py` — existing OpenF1 cache/source pattern, race clock, pacing, and currently supported endpoints.
- `src/f1si/interfaces.py` — unchanged `PaceModel` protocol and consumer contracts.

### External provenance references
- [OpenF1 API documentation](https://openf1.org/docs/) — documented historical telemetry and weather fields.
- [TUMFTM racetrack database](https://github.com/TUMFTM/racetrack-database) — candidate circuit geometry; verify the individual asset's source and terms before use.
- [FIA Formula One Technical Regulations](https://www.fia.com/regulation/fia-formula-1-world-championship-technical-regulations) — era-specific constraints, not observed car parameters.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AsOfAccessor` and `RaceSnapshot` — public boundary for cutoff-safe race facts and visible weather.
- `f1si.data.schema` and the `RaceSource` cache pipeline — typed normalized records, race-clock seconds, and rate-limited source caching.
- `PaceModel` in `f1si.interfaces` — stable model seam consumed by the existing simulation and strategy stack.

### Established Patterns
- Time-indexed rows carry `visible_at_s` and are filtered at the race-clock cutoff.
- A model receives plain immutable snapshot data; only a replay/backtest driver holds the accessor.
- OpenF1 data is cached and rate limited; raw data under `data/` is ignored by Git.

### Integration Points
- A new physics-input builder belongs beside the data/as-of layer and produces inputs for race-scoped model construction.
- Optional telemetry/location need normalized schema and ingestion support; no such high-rate tables currently exist.
- Track geometry needs an explicit artifact/provenance boundary and must remain outside the per-lap simulation hot path.

</code_context>

<specifics>
## Specific Ideas

- Bahrain 2023/Sakhir is the first reference geometry.
- Keep the existing pace-model consumers unchanged; no UI/UX work is in scope.
- Report the fixed M1 baseline exactly as recorded in `.planning/M1-BASELINE.md` at phase closeout.
</specifics>

<deferred>
## Deferred Ideas

- Geometry coverage for every circuit belongs to a later requirement (PHY-03).
- Full vehicle dynamics, private telemetry reconstruction, and user-facing product work remain outside M2.

</deferred>

---

*Phase: 9-data-and-geometry-readiness*
*Context gathered: 2026-11-17*
