# Phase 8: Markov Regimes & Full Backtest - Context

**Gathered:** 2026-11-16
**Status:** Ready for planning

> The owner authorized autonomous use of the agent's recommended choices. The decisions below are those recommended defaults, recorded for review.

<domain>
## Phase Boundary

Phase 8 replaces the constant safety-car probability with a cutoff-safe Markov model over green, VSC, SC, red and wet conditions; gives the simulator regime-dependent pit-loss inputs; and publishes a 20-race 2023–2025 walk-forward backtest with metrics by regulation era. It also locks and evaluates a separate 2026 holdout exactly once at the end of the milestone. Bahrain 2023 replay must continue to work, and CI must pass.

The in-sample 20-race targets are calendar-first complete races: 2023-01 through 2023-07, 2024-01 through 2024-07, and 2025-01 through 2025-06. The separate holdout is the second half of the complete 2026 calendar currently in the catalog, rounds 9 through 17. Calendar metadata and load status were inspected; no 2026 results were opened. The 20 in-sample races all belong to the 2022–2025 ground-effect era; 2026 is reported separately as reg_2026.

This phase does not change the replay page or other UI/UX, add a new pace model, use 2026 data for fitting, or tune the holdout after its score is seen. PAC-06 did not pass its locked Phase 7 test, so linear pace remains the Phase 8 backtest default and the Bayesian model is not described as superior.
</domain>

<decisions>
## Implementation Decisions

### Regime labels and cutoff visibility
- **D-01:** Use one mutually exclusive leader-lap regime derived from cutoff-visible track-control and weather observations. Priority is red, SC, VSC, wet, green. Rainfall marks wet only when red, SC and VSC are not active; yellow maps to green because yellow is not one of the five required states. Missing rainfall is not inferred from tyre choice or future laps.

### Markov training and holdout isolation
- **D-02:** Estimate one-lap transition counts from earlier completed in-sample races only and apply Dirichlet(1) smoothing to every destination in each source-state row. At each cutoff, derive the starting state from the current snapshot. For 2026 holdout predictions, fit transitions only from 2023–2025 data; do not use any race or cutoff from the locked 2026 group to fit or update the matrix. Use a synthetic sequence with known transitions to test matrix recovery.

### Pit-loss assumptions
- **D-03:** Retain the existing measured green-flag pit-loss baseline. Use 0.75 times green for VSC and 0.5 times green for SC, preserving the project's existing SC assumption. Keep red and wet at green cost unless the model has defensible measured evidence otherwise. Treat these regime adjustments as explicit assumptions, not measured regime-specific pit times; the existing pit-loss estimator excludes stops on slow-status laps.

### Backtest and holdout protocol
- **D-04:** Freeze the 20 in-sample race IDs, all predictions' seed derivation, model settings, eligible target mask, metric definitions, and report structure before scoring. Keep Phase 6's 1,000 simulations, base seed 0, risk setting 0.5, same clean-lap and paired-row rules, and race-weighted metric conventions for comparability.
- **D-05:** Freeze 2026-09 through 2026-17 as the single holdout group before any call to the out-of-sample results door. Score it once, only after the phase implementation and lock are committed. Use earlier 2023–2025 history for model fitting and the current race's cutoff-visible snapshot for its state; never use another 2026 holdout race as training history. Publish per-race and per-era denominators and keep the holdout results separate from the 20-race in-sample result.

### Carried forward from Phase 7
- The locked Phase 7 real-data score did not meet PAC-06: Bayesian next-lap MAE was 47.993% higher than the linear baseline. Preserve that result and keep linear pace as the default for Phase 8 scoring. Do not retune the Bayesian model against those races or imply that PAC-06 passed.
- Do not make any UI/UX changes in Phase 8.

### the agent's Discretion
- Choose the Markov model's internal representation, transition-count implementation, synthetic test size and recovery tolerance, and the smallest module/API changes that preserve existing contracts.
- Choose per-race report diagnostics and runtime optimizations that preserve the frozen sample, simulation count, seeds, cutoff rules and holdout protocol.

</decisions>

<canonical_refs>
## Canonical References

### Scope, requirements, and prior decisions
- .planning/ROADMAP.md — Phase 8 goal, dependency, requirements and success criteria.
- .planning/REQUIREMENTS.md — REG-02, REG-03, BKT-03, BKT-05 and the 2026 out-of-sample constraints.
- .planning/PROJECT.md — core value, no-look-ahead, explicit randomness and CI requirements.
- F1 Docs/BUILD_PLAN.md — regime-state design, safety-car replay example, 20-race validation and holdout-overfitting policy.
- .planning/phases/06-mvp-backtest-streamlit-view-readme/06-CONTEXT.md — prior 10-race sample, scoring definitions and holdout boundary.
- .planning/phases/07-bayesian-pace-model/07-CONTEXT.md — cutoff-local pace and synthetic recovery decisions.
- .planning/phases/07-bayesian-pace-model/07-05-SUMMARY.md — Phase 7 measured result and PAC-06 limitation.
- reports/pace/phase-07.json — locked score and denominators; do not rescore.
- reports/backtest/phase-06.json — established 10-race metrics and conventions.
- DECISIONS.md — prior data-door, safety-car, race-state, and measured green pit-loss decisions.

### Regime, state and simulator contracts
- src/f1si/data/asof.py — in-sample snapshots, earlier-race History, and calendar-only catalog.
- src/f1si/data/_snapshot.py — snapshot cutoffs and visibility rules.
- src/f1si/data/out_of_sample.py — protected 2026 snapshots and final outcomes; only the holdout evaluator may import it.
- src/f1si/data/sources/track_status_map.py — OpenF1 race-control mapping to green, VSC, SC and red status codes.
- src/f1si/eras.py — ground-effect and out-of-sample era mapping.
- src/f1si/state.py — current binary regime state, pit-loss map and RaceState serialization.
- src/f1si/regime/sc_rate.py — prior-only/history-only pattern for the existing SC estimate.
- src/f1si/pace/linear.py — clean-lap and green-flag pit-loss baseline conventions.
- src/f1si/sim/kernel.py and src/f1si/sim/numpy_backend.py — per-lap simulator and current SC-only transition and pit-loss behavior.

### Backtest and guard patterns
- src/f1si/backtest/walk_forward.py — prediction generation separated from result scoring.
- src/f1si/backtest/scoring.py — paired metrics, race-cluster uncertainty and report validation.
- tests/guards/import_scan.py and tests/guards/test_future_scramble.py — restricted data-door and look-ahead protections.
- tests/test_state_builder.py and tests/sim/test_safety_car.py — state and simulator regression-test patterns.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- AsOfAccessor exposes calendar metadata, per-cutoff RaceSnapshot values and earlier completed History; final results are kept behind separate doors.
- Track-status rows already distinguish SC, VSC, red, yellow and green. Cutoff-visible weather includes rainfall observations that can distinguish wet laps.
- RaceState already carries regime probabilities and a per-regime pit-loss mapping. The simulator passes its current SC/green pit-loss values through a per-lap kernel.
- The existing SC estimator demonstrates a history-only fit with an explicit prior; the linear pace fit supplies the current green pit-loss estimate.
- The Phase 6 prediction runner and scorer already separate cutoff-safe prediction generation from outcomes and publish paired metrics.

### Established Patterns
- Train only on earlier in-sample History, use the current RaceSnapshot for the starting state, and keep result access in the scoring/evaluation layer.
- The out-of-sample accessor is protected by an import policy; only the dedicated holdout evaluator may reach 2026 outcomes.
- Stochastic code uses explicit seeded NumPy generators, and deterministic race/cutoff seed derivation is recorded in reports.
- Real pit-loss estimation excludes SC, VSC and red-flag stops, so discounted regime values must be labeled as assumptions unless a separate comparable measurement is proven.

### Integration Points
- Replace the SC-only fit and state construction at the replay and walk-forward composition points with a Markov regime estimate and cutoff-observed current state.
- Pass the transition matrix and full pit-loss mapping into RaceState so the simulator and strategy consume one shared state contract.
- Add the 2026 scoring path only inside the protected holdout evaluator, preserving current AsOfAccessor and results import boundaries.
- Expand the registered backtest sample and report while preserving the existing Phase 6 row pairing, metrics, and disclosure conventions.

</code_context>

<specifics>
## Specific Ideas

- A synthetic Markov sequence with a known 5 × 5 transition matrix should demonstrate parameter recovery.
- The Bahrain 2023 replay test should show that a visible safety-car condition changes the regime input and can change the top strategy recommendation under a controlled fixture.
- Use the current rainfall observation to label wet; do not infer a wet track from tyre choice or future weather.
- Keep all documentation plain-language, report measured results and explicit assumptions, and leave the UI untouched.
</specifics>

<deferred>
## Deferred Ideas

Broader physics or machine-learning models, live data, deployment, external odds, and dashboard changes remain outside Phase 8.
</deferred>

---

*Phase: 8-markov-regimes-full-backtest*
*Context gathered: 2026-11-16*
