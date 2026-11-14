# Phase 6: MVP Backtest, Streamlit View & README - Context

**Gathered:** 2026-11-13
**Status:** Ready for planning

> **How these decisions were made.** The user had already selected all four discussion areas and authorized the agent to choose the recommended option. The choices below use those recommended defaults; the discussion log records the alternatives.

<domain>
## Phase Boundary

Phase 6 evaluates the existing strategy and probability outputs on ten real races from 2023–2025, compares them with observed team pit stops and a grid-position baseline, provides a one-page Streamlit view, and records measured results and data limitations in the README.

The phase keeps all predictions cutoff-local through `AsOfAccessor`, uses final results only in `f1si.backtest.scoring`, and leaves 2026 locked out of training and evaluation. The 20-race per-era backtest and one-time holdout remain in Phase 8; Bayesian pace modeling remains in Phase 7.

Requirements: BKT-01, BKT-02, BKT-04, UI-01, UI-02.
</domain>

<decisions>
## Implementation Decisions

### Race selection and aggregation
- **D-01:** Before scoring, pre-register ten complete races from 2023–2025, spread across years (4/3/3 when the catalog supports it) and selected using calendar order, season, round, and data completeness only. Include Bahrain 2023 as the fixed reference race. Do not select or replace races based on their outcomes or model metrics.
- **D-02:** Evaluate eligible as-of cutoffs in chronological order, using only earlier completed in-sample history. Average observations within each race, weight the ten races equally, and form uncertainty intervals by resampling whole races so repeated laps and drivers do not act like independent races.

### Probability scores and uncertainty coverage
- **D-03:** Report Brier scores for podium and top-10 outcomes beside a probabilistic grid-position baseline learned only from earlier races. Use a conservative neutral prior when the first evaluation race has no usable earlier results. Report the model and baseline on the same drivers and cutoffs.
- **D-04:** Build each driver's 90% finishing-position interval from the central empirical interval of simulated outcomes at that cutoff. Report observed coverage with race-clustered uncertainty; do not tune the interval on the ten evaluation races.
- **D-05:** Measure Phase 4's real-data wear-band follow-up as a retrospective diagnostic against a leave-current-stint-out reference. Label this as a proxy rather than latent ground truth, report early-fit bias and own-laps double-counting evidence, and do not change the filter merely to make this diagnostic look better.

### Platform recommendations and observed team stops
- **D-06:** Pair each recommendation with the next observed pit event using the decision available before that event. Report top-action agreement and stop-timing error per race with 95% race-cluster bootstrap intervals. Describe this as comparison with observed team behavior, not proof that the platform beats teams.

### Streamlit page and defaults
- **D-07:** Build one read-only page with the required strategy table, finishing-position fan chart, regime gauge, tire estimate and uncertainty panel, reason line, and risk dial. Provide race, driver, cutoff-lap, and risk controls. Default to Bahrain 2023, ALO, a middle eligible cutoff, and risk aversion 0.5.
- **D-08:** Reuse cutoff-safe replay inputs and show the existing safety-car probability as the regime view; do not imply that Phase 8's Markov regime model exists. Clearly label prior-driven or sparse-fallback output as uncalibrated. Add Streamlit as a project dependency as required by the roadmap, without adding deployment or live streaming.

### the agent's Discretion
- The exact ten race IDs within the pre-registered season/round rule, with Bahrain 2023 fixed and the full list recorded before scoring.
- The smoothing details for the past-only grid baseline, the bootstrap implementation, app module layout, caching, and chart styling, provided the decisions above and existing data-access boundaries remain intact.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.** The Phase 6 roadmap entry has no separate canonical-reference list, so the following project, requirement, decision, and code contracts are authoritative.

### Project scope and evaluation
- `.planning/ROADMAP.md` § Phase 6 — goal, success criteria, 10-race scope, and carried-forward evaluation questions.
- `.planning/REQUIREMENTS.md` — BKT-01, BKT-02, BKT-04, UI-01, UI-02; also FND-02, FND-03, DAT-03, DAT-04, and DAT-05.
- `.planning/PROJECT.md` — core value, no-look-ahead rule, reproducibility, and quality gate.
- `CLAUDE.md` — stack, testing, documentation, and CI constraints.
- `F1 Docs/BUILD_PLAN.md` — week-six MVP, evaluation metrics, hidden-variable limitations, and source-credit/licensing expectations.

### Locked method and prior findings
- `DECISIONS.md` — DEC-003/004 (separate as-of, results, and out-of-sample doors), DEC-091 (wear-filter priors and measurement follow-up), DEC-095 (per-cutoff wear-filter replay), and DEC-096–101 (strategy valuation, replay, and sparse fallback assumptions).
- `.planning/phases/03-monte-carlo-simulator/03-VERIFICATION.md` — prior ALO finishing interval excluded the actual P3; carry this coverage question forward.
- `.planning/phases/04-kalman-tire-filter/04-CONTEXT.md` and `.planning/phases/04-kalman-tire-filter/04-HUMAN-UAT.md` — accepted Phase 4 method and the real-data wear-band follow-up.
- `.planning/phases/05-longstaff-schwartz-strategy-live-replay/05-CONTEXT.md`, `05-03-SUMMARY.md`, and `05-04-SUMMARY.md` — replay contract, current recommendation assumptions, and Phase 5 implementation evidence.

### Data and strategy contracts
- `src/f1si/data/asof.py` — cutoff semantics and earlier-race history.
- `src/f1si/data/results.py` — final-results door, reserved for backtest scoring.
- `src/f1si/strategy/longstaff.py` — seeded policy analysis and ranked stop options.
- `src/f1si/cli.py` — cutoff-local replay construction and formatting patterns.
- `src/f1si/pace/kalman.py` — wear estimates and uncertainty inputs.
- `tests/guards/import_scan.py` and `tests/guards/consumers.py` — import boundaries and future-scramble consumer registration.
- `README.md` — existing user-facing command, assumptions, and source-credit conventions.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AsOfAccessor.snapshot` and `.history` provide cutoff-local race inputs and strictly earlier completed race history.
- `ResultsAccessor.final_classification` exposes final outcomes through the module restricted to `f1si.backtest.scoring`.
- `LongstaffSchwartzPolicy.analyze` exposes ranked options and their simulated finish distributions; the Phase 5 cutoff builder already composes the pace fit, wear filter, race state, and safety-car estimate.
- `RaceState`, seeded `NumpySimulator`, existing plot helpers, the local race catalog, and the `reports/` output convention provide building blocks for the report and page.

### Established Patterns
- The current race's future rows and final results never enter a recommendation; register new as-of consumers and keep the future-scramble guard passing.
- Random simulations use injected, seeded NumPy generators. Documentation distinguishes measured evidence from assumed values and hidden-state limitations.
- `f1si.data.results` is reserved for `f1si.backtest.scoring`; 2026 outcomes remain behind the out-of-sample door.

### Integration Points
- There is no backtest package or Streamlit dependency yet. The roadmap calls for adding the Phase 6 scoring layer and the required Streamlit view.
- The Streamlit page should call shared cutoff-safe construction rather than duplicate data access or compute an end-of-race fit for earlier cutoffs.
- README and the Phase 6 explainer should report actual measured output, explain fuel and tire wear as hidden variables, disclose model assumptions, and credit FastF1/OpenF1 with licensing notes.
</code_context>

<specifics>
## Specific Ideas

- The four areas already selected for discussion are race selection/aggregation, platform versus team calls, probability scoring/interval coverage, and Streamlit controls/defaults.
- Carry forward the Phase 3 ALO interval miss and Phase 4 early-fit bias and own-laps double-counting measurements.
- Keep the dashboard's default on the known Bahrain 2023 ALO replay, with a neutral risk setting, while clearly showing fallback and calibration limits.
</specifics>

<deferred>
## Deferred Ideas

- 20-race per-era evaluation and the one-time 2026 holdout — Phase 8.
- Hierarchical Bayesian pace model — Phase 7.
- Markov regime model and regime-dependent pit loss — Phase 8.
- Live OpenF1 streaming, production deployment, market-odds benchmarking, and a broader dashboard — later milestones or out of scope.
</deferred>

---

*Phase: 06-mvp-backtest-streamlit-view-readme*
*Context gathered: 2026-11-13*
