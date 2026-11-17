# Phase 9: Data and Geometry Readiness - Discussion Log

> **Audit trail only.** Decisions are captured in `09-CONTEXT.md`; this log preserves the alternatives considered.

**Date:** 2026-11-17
**Phase:** 9-Data and Geometry Readiness
**Areas discussed:** Input cutoff and telemetry coverage; Geometry provenance and rights; Parameter identifiability and assumptions; Physics input integration

---

## Input cutoff and telemetry coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Use normalized cached inputs with timestamp and cutoff checks | Keep source timestamps, map them to race time, and expose only rows visible at the cutoff. | ✓ |
| Fetch directly inside the model | Couple model prediction to live source access. | |
| Treat lap timing as high-rate telemetry | Substitute lap summaries for vehicle telemetry. | |

**Choice:** Recommended cached/as-of path, following the user's standing instruction to use the recommended choice without prompting.
**Notes:** Keep telemetry optional; report missing coverage and use only a documented cached-lap fallback.

## Geometry provenance and rights

| Option | Description | Selected |
|--------|-------------|----------|
| Use a rights-reviewed, versioned candidate profile and keep it external if redistribution is unclear | Pin provenance and digest; bundle only when the individual asset's rights allow it. | ✓ |
| Bundle the candidate regardless of its source terms | Copy the geometry without verifying asset-specific redistribution terms. | |
| Reconstruct track geometry from approximate OpenF1 location | Treat telemetry location as survey-quality geometry. | |

**Choice:** Recommended rights-reviewed candidate profile.
**Notes:** Sakhir/Bahrain 2023 is the reference. A missing or invalid required asset must produce a clear failure.

## Parameter identifiability and assumptions

| Option | Description | Selected |
|--------|-------------|----------|
| Separate identifiable composites from hidden assumptions with evidence and sensitivity | Fit only supported effective composites; label absolute hidden quantities and provide sourced bounds. | ✓ |
| Fit absolute team-specific parameters from lap times | Attribute confounded values to individual teams. | |
| Use regulatory minima as measured car values | Treat regulatory constraints as observed vehicle specifications. | |

**Choice:** Recommended identifiable-composite approach.
**Notes:** Public-data limits and DEC-134 are carried forward. Phase 9 will include a numeric evidence/identifiability sensitivity result without implementing the Phase 10 solver; predictive sensitivity that genuinely needs the solver must be labeled not estimable yet and explicitly carried into Phase 10.

## Physics input integration

| Option | Description | Selected |
|--------|-------------|----------|
| Prebuild immutable race-scoped context behind the existing PaceModel seam | Construct inputs before simulation; keep model prediction deterministic and consumers unchanged. | ✓ |
| Let PaceModel query cache data directly per prediction | Put data access in the hot-path model call. | |
| Modify simulation and strategy consumers to pass new fields | Change existing consumer interfaces for M2 fields. | |

**Choice:** Recommended immutable race-scoped context.
**Notes:** Preserve the existing PaceModel signature and the 50,000-race runtime budget.

## the agent's Discretion

The agent will choose concrete schemas, quality thresholds, diagnostics, and pinning mechanics that meet the locked requirements and document method choices in `DECISIONS.md`.

## Deferred Ideas

- Multi-circuit geometry, complete vehicle dynamics, and UI/UX work remain outside Phase 9.
