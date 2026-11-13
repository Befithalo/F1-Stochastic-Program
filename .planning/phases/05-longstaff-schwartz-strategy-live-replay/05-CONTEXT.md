# Phase 5: Longstaff-Schwartz Strategy & Live Replay - Context

**Gathered:** 2026-11-13
**Status:** Ready for planning

> **How these decisions were made.** The owner has repeatedly asked Claude to choose the recommended option for GSD discussion questions and, in Phase 4, to continue through discussion, planning and execution in one go. Those recommendations are recorded here for review and can be revised before implementation.

<domain>
## Phase Boundary

Phase 5 adds a StrategyPolicy based on Longstaff-Schwartz valuation and a lap-by-lap replay for Bahrain 2023. At each cutoff, the policy prices pit now, pitting in 1-5 laps, and staying out; it ranks the options by mean finishing position and CVaR@10%, exposes a risk setting, and gives a one-sentence reason. The replay must use only the data visible at each lap and pass the shared StrategyPolicy conformance suite.

The phase is a CLI workflow that exercises the strategy end to end. The Streamlit view, walk-forward backtest, and measured comparison across multiple races belong to Phase 6. The Bayesian pace model and Markov regime model remain in Phases 7 and 8.

Requirements: STR-01, STR-02, STR-03, STR-04, RPL-01, RPL-02.
</domain>

<decisions>
## Implementation Decisions

### Strategy ranking and risk setting
- **D-01:** Use one user-facing risk-aversion value on a 0-1 scale. 0 is mean-focused / chase-the-win; 1 is tail-focused / protect-points. Rank options by a blend of expected finishing position and worst-decile CVaR, with lower values better. Keep the mean and CVaR visible as separate reported metrics so the blend remains inspectable.
- **D-02:** Define CVaR@10% as the average finishing position in the worst 10% of simulated outcomes (higher finishing-position numbers are worse). The CLI default risk setting and exact numeric output format are implementation details for planning.

### Replay workflow and output
- **D-03:** Add a f1si replay CLI command. With no lap argument it emits recommendations for successive race cutoffs; --lap N emits the single as-of recommendation at lap N. Use the existing CLI command and plain-text table patterns; reserve the interactive dashboard and fan chart for Phase 6.
- **D-04:** Rebuild the snapshot, fit, filter output, and RaceState from the same as-of cutoff for each recommendation. Keep replay on AsOfAccessor; do not read current-race results, future laps, or hindsight fits to produce a call.
- **D-05:** All stochastic strategy comparisons must use the project's injected, seeded numpy.random.Generator conventions. Preserve common random numbers between competing options where the simulator permits it, so option differences are not dominated by unrelated draws.

### Recommendation reasons
- **D-06:** Produce a concise, deterministic sentence from the current as-of state and the option scores. Mention an undercut, current safety-car stop value, or wear uncertainty only when the visible inputs and simulated outcomes support the claim. Do not claim a tire cliff or forecast an unobserved future regime.
- **D-07:** If the available state cannot support a specific explanation, report the score-based reason plainly instead of inventing a race narrative.

### Carried forward
- Keep the StrategyPolicy.decide(state, *, driver) contract and its shared conformance suite (DEC-061); the policy owns any RNG it needs rather than changing the protocol.
- Use the existing filter-to-RaceState integration for the current tyres (DEC-093/094). The Phase 4 wear-prior double-counting concern remains documented and is to be measured in Phase 6 before changing the method (DEC-091; 04-HUMAN-UAT.md).
- Use only the candidate actions already fixed in the Phase 5 success criteria. Do not add a dashboard, multi-race backtest, new regime model, or nonlinear tire-cliff model to this phase.

### the agent's Discretion
The Longstaff-Schwartz regression basis, numerical details of estimating CVaR, legal-plan handling at race boundaries, CLI formatting, exact reason-rule thresholds, and internal module boundaries may follow the simplest approach that meets the existing contracts and is documented. Any assumption-based threshold must be labeled and kept easy to revisit.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- .planning/ROADMAP.md - Phase 5 goal, success criteria, and Phase 6 boundary.
- .planning/REQUIREMENTS.md - STR-01 through STR-04 and RPL-01 through RPL-02.
- .planning/PROJECT.md - Core Value, reproducibility, no-look-ahead, and model-validation constraints.
- F1 Docs/BUILD_PLAN.md §§ Architecture, How a strategy call works, Data, validity and honesty - intended strategy outputs and no-look-ahead rules.
- F1 Docs/MASTER_PROMPT.md - M1 build order and definition of done.

### Decisions and prior implementation
- DECISIONS.md - DEC-061 (interfaces), DEC-068 (plan rules), DEC-076/077 (race state and uncertainty), DEC-078 (overtaking), DEC-081/087 (forced plans and common random numbers), DEC-091 (wear priors), DEC-093/094 (filter integration).
- .planning/phases/02-interfaces-linear-tire-wear-free-track-optimizer/02-CONTEXT.md - contracts and the original strategy-policy boundary.
- .planning/phases/03-monte-carlo-simulator/03-CONTEXT.md - simulator and variance-reduction decisions.
- .planning/phases/04-kalman-tire-filter/04-CONTEXT.md and .planning/phases/04-kalman-tire-filter/04-HUMAN-UAT.md - filtered wear integration and the accepted Phase 6 coverage follow-up.

### Code integration points
- src/f1si/interfaces.py - StrategyPolicy, PitDecision, Plan, and SimulationResult contracts.
- src/f1si/data/asof.py - guarded snapshots for each race cutoff.
- src/f1si/state.py and src/f1si/pace/kalman.py - RaceState construction and per-cutoff wear filtering.
- src/f1si/strategy/free_track.py - current plan enumeration and deterministic policy pattern.
- src/f1si/sim/numpy_backend.py and src/f1si/sim/draws.py - continuation simulation, forced plans, and random-stream handling.
- src/f1si/cli.py - command registration, replaying cutoffs, tabular output, and friendly refusal patterns.
- tests/conformance/suites.py and tests/guards/consumers.py - strategy conformance and guarded data-consumer registration.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- AsOfAccessor.snapshot(AsOf(...)) provides the safe race snapshot for a replay cutoff.
- build_race_state(..., wear_filter=...) connects the per-stint Kalman result to the simulator without introducing a second state type.
- FreeTrackOptimizer already enumerates legal pit plans and implements StrategyPolicy; it is a baseline and source of plan-legality rules.
- NumpySimulator accepts forced per-driver plans and returns finishing-position samples and diagnostics for comparing candidate actions.

### Established Patterns
- Callers that replay cutoffs rebuild data and models from that cutoff; the as-of accessor is the sole door to current-race rows.
- Public contracts use typed protocols and frozen value objects; behavior is enforced by shared conformance tests.
- Randomness is injected through numpy.random.Generator, with fixed seeds and common random numbers used for fair plan comparisons.
- CLI commands validate inputs, print a direct table or explanation, and return a friendly refusal instead of exposing a traceback for expected data limitations.

### Integration Points
- Add the Longstaff-Schwartz policy under src/f1si/strategy/ and connect it to the existing protocol and simulator.
- Add f1si replay through src/f1si/cli.py; its replay driver owns the AsOfAccessor, while policy code receives only a RaceState.
- Keep the Phase 4 fit-prior coverage follow-up visible for the Phase 6 backtest.
</code_context>

<specifics>
## Specific Ideas

- Present each option's mean finishing position, spread, and CVaR@10% so the risk setting's effect can be seen, not just the winning action.
- A reason should describe what the model can substantiate at that cutoff. The build plan's “undercut threat” and “safety-car window” are examples, while “cliff risk” is deferred because the current tire model is linear.
</specifics>

<deferred>
## Deferred Ideas

- Streamlit dashboard and fan chart, plus walk-forward evaluation across real races - Phase 6.
- Hierarchical Bayesian pace model - Phase 7.
- Markov race regimes and measured regime-dependent pit loss - Phase 8.
- Nonlinear tire cliff or other tire-physics effects - future scope.
</deferred>

---

*Phase: 5-longstaff-schwartz-strategy-live-replay*
*Context gathered: 2026-11-13*
