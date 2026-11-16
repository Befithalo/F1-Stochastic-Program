# Phase 7: Bayesian Pace Model - Discussion Log

> **Audit trail only.** Decisions are captured in 07-CONTEXT.md.

**Date:** 2026-11-16
**Phase:** 7-Bayesian Pace Model
**Areas discussed:** Training data and effect structure, inference and PaceModel behavior, evaluation and synthetic recovery

> The owner authorized the agent to choose the recommended option for all decisions and asked that the workflow continue without owner input. The selected options below are the agent's recommendations under that authorization.

## Training data and effect structure

| Question | Options considered | Selected |
|---|---|---|
| Which laps may train the fit? | Current-race snapshot only; earlier in-sample races plus the current cutoff-visible prefix; all cached races | Earlier races plus cutoff-visible prefix |
| How should car and driver identity be represented? | Driver-only effects; team proxy plus driver hierarchy; chassis-specific effects without data support | Team proxy plus driver hierarchy |
| How should race and era effects be identified? | Unpooled one-hot effects; centered partial pooling with event intercept; omit event and era terms | Centered partial pooling with event intercept |
| What should happen for sparse groups? | Refuse the prediction; use population shrinkage; borrow a future group estimate | Population shrinkage with provenance |

## Inference and PaceModel behavior

| Question | Options considered | Selected |
|---|---|---|
| Which PyMC inference route supports repeated cutoff fits? | NUTS for every fit; seeded ADVI for operational fits with NUTS reference validation; non-Bayesian approximation | ADVI with NUTS validation |
| What should the protocol's standard deviation represent? | Residual lap noise only; fold parameter uncertainty into every lap; parameter uncertainty only | Residual lap noise only, with shared uncertainty in RaceState |
| How should fitting failures surface? | Silent linear fallback; explicit fit failure; clamp unsupported parameters | Explicit fit failure, with caller-controlled linear fallback |
| How should the model integrate? | Replace PaceModel's public protocol; add a parallel strategy path; select at existing composition seams | Select at existing seams |

## Evaluation and synthetic recovery

| Question | Options considered | Selected |
|---|---|---|
| How should held-out laps be split? | Random laps; race-grouped chronological walk-forward; tune on the same races | Race-grouped chronological walk-forward |
| Which metric gates the 15% claim? | RMSE; MAE on shared finite rows; different rows for each model | MAE on identical rows |
| How should truth recovery be tested? | One real-data fit; seeded synthetic multi-era data; qualitative visual inspection | Seeded synthetic multi-era data |
| How should real held-out races be selected? | Select after seeing scores; freeze calendar/group split before scoring; choose easiest available races | Freeze split and mask before scoring |

## the agent's Discretion

- The user authorized the agent to select the recommended option for all decisions.
- The planner will define numerical effect tolerances, ADVI convergence checks, runtime budgets, and the pre-registered grouped split before code execution.

## Deferred Ideas

- Markov regimes, regime-based pit loss, 20-race per-era report, and one-time holdout — Phase 8.
- UI/UX changes — excluded by the user's instruction.
