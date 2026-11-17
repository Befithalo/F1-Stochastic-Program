# Phase 10: Point-Mass PaceModel - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `10-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-11-17  
**Phase:** 10-Point-Mass PaceModel  
**Areas discussed:** lap solver, parameter identifiability, prediction uncertainty, synthetic recovery, integration boundary

---

All five gray areas were auto-selected and resolved in one pass under the user's explicit instruction to use the assistant's recommendation and not ask questions. For each area, the first option was the recommended default.

## Lap solver and track representation

| Option | Description | Selected |
|--------|-------------|----------|
| Quasi-static closed-lap speed envelope | Use curvature-limited corner speeds, effective longitudinal drive/brake limits, drag/downforce/grip, and integrate segment distance over speed. | ✓ |
| Time-stepped vehicle dynamics | Integrate transient position, velocity, and force states at small time steps throughout the lap. | |

**User's choice:** Recommended default selected automatically.  
**Notes:** The reduced-order solver fits M2's point-mass scope and 50,000-race budget; details and numerical limits remain a research/planning responsibility.

## Effective parameters and hidden assumptions

| Option | Description | Selected |
|--------|-------------|----------|
| Fit identifiable composites and disclose hidden absolute values | Estimate only supported effective terms and keep mass, power, aero, and grip assumptions versioned and bounded. | ✓ |
| Infer absolute team vehicle parameters from public lap times | Assign team-specific physical values from public race outcomes. | |

**User's choice:** Recommended default selected automatically.  
**Notes:** Carries forward DEC-134 and the Phase 9 parameter register; public data do not justify exact team-specific hidden values.

## Prediction uncertainty

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic propagation plus residual variance | Return repeatable mean/SD; propagate declared parameter uncertainty and add cutoff-safe training residual variance when estimable. | ✓ |
| Sample parameters on each predict call | Draw new physical parameters during `PaceModel.predict` and return sampled outcomes. | |

**User's choice:** Recommended default selected automatically.  
**Notes:** Keeps the PaceModel deterministic and leaves random draws to the simulator; excludes tire uncertainty until Phase 11 and the Phase 12 holdout from all fitting.

## Recovery and physical validation

| Option | Description | Selected |
|--------|-------------|----------|
| Independent synthetic generator and recovery checks | Generate known trajectories through a test-side forward implementation and check recovery, invariants, convergence, and independent sensitivities. | ✓ |
| Reuse production solver to generate and score its own synthetic data | Apply the same implementation in both directions for a round-trip test. | |

**User's choice:** Recommended default selected automatically.  
**Notes:** Avoids a tautological round trip and covers identifiable quantities only; synthetic validation is not real-data superiority evidence.

## Integration and failure behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Immutable race-scoped context, fail closed | Bind validated geometry and physics inputs at construction, preserve the PaceModel and consumers, and reject missing/invalid required assets. | ✓ |
| Resolve data or switch to another pace model inside predict | Read mutable cache state or silently fall back during each vectorized prediction. | |

**User's choice:** Recommended default selected automatically.  
**Notes:** Carries forward DEC-135 and Phase 9's immutable, as-of-safe input boundary.

## the agent's Discretion

Equation detail, exact schema, fitting routine, numeric tolerances, independent synthetic test construction, and diagnostic presentation are delegated to research/planning within the scope and guardrails in `10-CONTEXT.md`.

## Deferred Ideas

- Tire thermals/wear: Phase 11.
- Bayesian residual hybrid and locked held-out-stint gate: Phase 12.
- Multi-circuit library, transient multibody model, private data recovery, UI/UX: outside this phase or milestone.
