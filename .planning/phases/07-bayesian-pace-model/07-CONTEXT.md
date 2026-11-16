# Phase 7: Bayesian Pace Model - Context

**Gathered:** 2026-11-16
**Status:** Ready for planning

> The owner authorized the agent to choose its recommended option for each decision and asked to proceed without requiring owner input. The decisions below are the recommended defaults selected under that instruction.

<domain>
## Phase Boundary

Phase 7 adds a hierarchical PyMC pace model that implements the existing PaceModel contract, estimates pace from cutoff-safe real 2023-2025 data, recovers known synthetic effects within declared tolerances, and beats the current per-compound linear model by at least 15% on the pre-registered held-out next-lap metric. Replay and backtest must be able to use it through the existing model seam.

This phase does not add a new UI or change the strategy policy. Markov regimes, regime-dependent pit loss, the 20-race per-era report, and the one-time holdout evaluation remain Phase 8.
</domain>

<decisions>
## Implementation Decisions

### Training data and effect structure
- **D-01:** Fit from only completed clean laps in earlier in-sample races plus completed clean laps in the current RaceSnapshot. Use the as-of History and snapshot supplied by the caller; never read the current race's results, later laps, or 2026 data. Join team identity through that race's entries and derive each race's regulation era from its calendar metadata.
- **D-02:** Use an additive hierarchical model with partially pooled team/car and driver offsets, fresh-compound offsets, compound-specific tire-age wear, a shared fuel proxy by lap number, regulation-era offsets, and a race-level intercept for circuit and event conditions. Center group effects so the global intercept and nested effects are identifiable. Team name is the available car-performance proxy; do not describe it as a separately measured chassis effect.
- **D-03:** Use the same clean-lap eligibility rules as the linear baseline so the comparison differs by model, not by data curation. Keep the linear model available as baseline and fallback.
- **D-04:** Shrink unseen or sparse drivers, teams, compounds, and eras toward the learned population distribution. Do not silently borrow a realized future value; report when a prediction is population-prior-driven.

### Inference and PaceModel behavior
- **D-05:** Implement the model in PyMC with explicit seeded variational inference for repeated cutoff fits, and validate its posterior recovery and uncertainty against a higher-accuracy NUTS reference run on bounded synthetic fixtures. Use convergence/loss checks; a failed fit must be reported, never replaced silently with an apparently fitted model. This is the recommended balance for walk-forward runtime and posterior quality.
- **D-06:** PaceModel.predict returns posterior predictive mean and standard deviation: residual lap noise plus parameter uncertainty for the requested driver, compound, tire age, and lap. The caller continues to own simulation random draws.
- **D-07:** Keep all fitting and prediction behind the existing PaceModel seam. Replay and backtest select the model through their composition point and use the same cutoff-safe input path; policy, simulator, and scoring semantics do not change.

### Evaluation and synthetic recovery
- **D-08:** Measure next-lap accuracy with race-grouped chronological walk-forward predictions. At each scored lap, fit only earlier complete races and the current race's visible clean-lap prefix. Compare Bayesian and linear MAE on exactly the same finite rows. The gate is at least a 15% reduction in MAE; report race and era denominators and do not tune against scored races.
- **D-09:** Before evaluating real held-out predictions, freeze the race-grouped split, eligible-lap mask, seed derivation, metric, and minimum sample count in the plan and report. Do not replace or reselect evaluation races after seeing model results.
- **D-10:** Synthetic recovery must exercise multiple teams, drivers, compounds, races, and eras using known seeded effects. Declare absolute tolerances per effect in the plan; require the truth to be within the posterior 90% interval for the principal effects and separately report posterior predictive coverage. Keep synthetic fixture construction independent of real results.

### the agent's Discretion
- Choose model coordinates, weakly informative prior scales, the exact ADVI convergence callback and iteration cap, cached fit identity, and test fixture sizes. Validate these choices against identifiability, reproducibility, runtime, and the locked acceptance criteria.
- Resolve current PyMC API details against the installed/locked version and official documentation. Keep only reusable output needed by PaceModel; do not persist raw race data or full posterior paths.
- If the 15% gate is not met, diagnose the discrepancy and improve the model or eligibility design without using final results or tuning on the scored held-out races.

</decisions>

<canonical_refs>
## Canonical References

**Downstream planners and implementers MUST read these before planning or coding.**

### Scope and requirements
- .planning/ROADMAP.md § Phase 7 — goal, dependency, requirements, and success criteria.
- .planning/REQUIREMENTS.md — PAC-05 and PAC-06; also FND-02, FND-03, DAT-03, DAT-04, and DAT-05.
- .planning/PROJECT.md — cutoff safety, reproducibility, plugin contracts, and M1 quality gates.
- CLAUDE.md — supported stack, testing and documentation requirements.
- F1 Docs/BUILD_PLAN.md — pace model rationale, evaluation and hidden-variable limits.

### Existing method and data contracts
- DECISIONS.md — DEC-003/004 (data doors), DEC-025 (fuel/track confounding), DEC-061 (PaceModel protocol), DEC-091 (wear-prior caveats), DEC-100/101 (cutoff rebuild and fallback), and Phase 6 decision entries.
- src/f1si/interfaces.py — PaceModel prediction signature and output meaning.
- src/f1si/data/asof.py and src/f1si/data/_snapshot.py — completed-lap visibility and earlier-race History.
- src/f1si/data/schema.py and src/f1si/eras.py — normalized lap/entry columns and regulation-era mapping.
- src/f1si/pace/linear.py — current clean-lap classification, per-compound linear baseline, and limitations.
- src/f1si/sim/borrow.py — existing population-mean behavior for unseen compounds and drivers.
- src/f1si/cli.py and src/f1si/backtest — replay/backtest composition points and existing comparison conventions.
- src/f1si/synthetic/generator.py and tests/conformance — seeded truth data and PaceModel contract checks.
- tests/guards — import and future-scramble rules for new data consumers.
- README.md and reports/backtest/phase-06.json — current measured results and reporting style.

### PyMC API reference
- https://www.pymc.io/projects/docs/en/stable/api/generated/pymc.fit.html — current variational fitting entry point.
- https://www.pymc.io/projects/docs/en/stable/api/generated/pymc.sample.html — NUTS reference sampling and reproducible seeds.
- https://www.pymc.io/projects/examples/en/latest/introductory/api_quickstart.html — PyMC inference choices and approximate-posterior sampling.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- RaceSnapshot and History are the only permitted inputs for current and earlier race data. History is ordered strictly before the current race.
- fit_linear_pace and its private clean-lap classifier provide the paired baseline and current data-quality convention.
- PaceModel is a narrow predict-only protocol consumed by the simulator, policy, replay, and backtest.
- BorrowedPace already defines sensible field-average behavior for unseen compounds and drivers.
- The seeded synthetic race generator, shared protocol checks, and guard fixtures provide test patterns for recovery and no-look-ahead.

### Established Patterns
- Results are readable only from f1si.backtest.scoring; the pace model must not import the results or out-of-sample doors.
- Randomness uses explicit NumPy generators or derived integer seeds. No module-global RNG.
- New data-consuming functions must be registered with the future-scramble guard and use only cutoff-safe snapshots/history.
- The project's strict mypy, ruff, and pytest checks are required; measured performance and assumptions belong in DECISIONS.md and the README explainer.

### Integration Points
- The replay builder and walk-forward backtest currently compose pace using fit_linear_pace; add a model-selection seam there without changing strategy or simulator APIs.
- Team identifiers come from the entry rows; driver identifiers must be stable across races, while prediction inputs still use the protocol's driver number.
- The current standard-deviation output feeds simulator lap noise. Preserve the interface and make its posterior predictive interpretation explicit.

</code_context>

<specifics>
## Specific Ideas

- Keep the linear estimator as a visible benchmark and honest fallback.
- For each held-out next-lap target, use the current race's visible prefix and only completed earlier races.
- Avoid any user-facing UI changes in this phase.
</specifics>

<deferred>
## Deferred Ideas

- Markov race regimes and regime-dependent pit loss — Phase 8.
- The 20-race per-era strategy backtest and one-time holdout evaluation — Phase 8.
- Broader model families, live data, deployment, and dashboard changes — later milestones.
</deferred>

---

*Phase: 07-bayesian-pace-model*
*Context gathered: 2026-11-16*
