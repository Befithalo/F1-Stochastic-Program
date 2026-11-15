# Phase 6: MVP Backtest, Streamlit View & README - Context

**Gathered:** 2026-11-13
**Status:** Ready for planning
**Follow-up decisions added:** 2026-11-14, based on the approved UI review and owner's visual feedback

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
- **D-09:** Before final-results access, freeze compact podium probability, top-10 probability, and inclusive empirical P05/P95 finish-position endpoints for each selected strategy option. Derive all four values from the same simulated finish-position draws already used to summarize that option, and discard the full draw arrays before retaining the prediction trace.
- **D-05:** Measure Phase 4's real-data wear-band follow-up as a retrospective diagnostic against a leave-current-stint-out reference. Label this as a proxy rather than latent ground truth, report early-fit bias and own-laps double-counting evidence, and do not change the filter merely to make this diagnostic look better.

### Platform recommendations and observed team stops
- **D-06:** Pair each recommendation with the next observed pit event using the decision available before that event. Report top-action agreement and stop-timing error per race with 95% race-cluster bootstrap intervals. Describe this as comparison with observed team behavior, not proof that the platform beats teams.

### Streamlit page and defaults
- **D-07:** Build one read-only page with the required strategy table, finishing-position fan chart, regime gauge, tire estimate and uncertainty panel, reason line, and risk dial. Provide race, driver, cutoff-lap, and risk controls. Default to Bahrain 2023, ALO, a middle eligible cutoff, and risk aversion 0.5.
- **D-08:** Reuse cutoff-safe replay inputs and show the existing safety-car probability as the regime view; do not imply that Phase 8's Markov regime model exists. Clearly label prior-driven or sparse-fallback output as uncalibrated. Add Streamlit as a project dependency as required by the roadmap, without adding deployment or live streaming.
- **D-10:** Resolve the Phase 6 UI review findings against the approved `06-UI-SPEC.md`: use its exact replay error copy without showing raw exception text; mark the actual first-ranked table action with the accent; keep fan-chart bars neutral and use the accent for a clearly labeled summary marker from the selected cutoff's simulation; bring chart text, spacing, and control sizing into the declared design scale where native widgets permit. Show the risk slider endpoints visibly. Validate the rendered page at desktop and narrow widths.
- **D-11:** Replace the current flat Streamlit presentation with a polished motorsport race-engineering dashboard. Use a dark graphite canvas, layered slate surfaces, crisp high-contrast type, and deliberate spacing; use racing red only for the primary action and the existing top-ranked, finishing-summary, and safety-car signals. Make the fixed ten-race scorecard compact, make the replay controls easy to scan, give the finishing-position chart visual priority, and present safety-car and tire estimates as tidy companion cards. Keep the page one-screen-flow, read-only, cutoff-safe, and free of new features or dependencies. This owner feedback supersedes the prior light visual palette and flat component treatment; it does not change D-07/D-08 data, copy, or scope requirements.

### the agent's Discretion
- The exact ten race IDs within the pre-registered season/round rule, with Bahrain 2023 fixed and the full list recorded before scoring.
- The smoothing details for the past-only grid baseline, the bootstrap implementation, app module layout, caching, and chart styling, provided the decisions above and existing data-access boundaries remain intact.
- The exact spacing, card shape, heading treatment, and chart grid/annotation details for D-11, provided contrast, accessibility, responsive behavior, and the locked data semantics remain intact.

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

### UI review follow-up
- `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-UI-SPEC.md` — approved copy, color, typography, spacing, responsive, and interaction contract.
- `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-UI-REVIEW.md` — audited gaps and required human inspection.
- `src/f1si/app.py` — existing replay page, state handling, table, and CSS integration points.
- `src/f1si/plots/simulate.py` — finishing-position chart data and renderer.
- `tests/app/test_app.py` and `tests/plots/test_simulate_plot.py` — current UI and chart acceptance coverage.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AsOfAccessor.snapshot` and `.history` provide cutoff-local race inputs and strictly earlier completed race history.
- `ResultsAccessor.final_classification` exposes final outcomes through the module restricted to `f1si.backtest.scoring`.
- `LongstaffSchwartzPolicy.analyze` currently exposes ranked option aggregates but discards its finish draws. Plan 06-02 must add the compact D-09 probabilities and endpoints from each selected option's existing draw array before the prediction trace freezes; it must not approximate them from mean, spread, or CVaR or retain full arrays. The Phase 5 cutoff builder already composes the pace fit, wear filter, race state, and safety-car estimate.
- `RaceState`, seeded `NumpySimulator`, existing plot helpers, the local race catalog, and the `reports/` output convention provide building blocks for the report and page.

### Established Patterns
- The current race's future rows and final results never enter a recommendation; register new as-of consumers and keep the future-scramble guard passing.
- Random simulations use injected, seeded NumPy generators. Documentation distinguishes measured evidence from assumed values and hidden-state limitations.
- `f1si.data.results` is reserved for `f1si.backtest.scoring`; 2026 outcomes remain behind the out-of-sample door.

### Integration Points
- There is no backtest package or Streamlit dependency yet. The roadmap calls for adding the Phase 6 scoring layer and the required Streamlit view.
- The Streamlit page should call shared cutoff-safe construction rather than duplicate data access or compute an end-of-race fit for earlier cutoffs.
- README and the Phase 6 explainer should report actual measured output, explain fuel and tire wear as hidden variables, disclose model assumptions, and credit FastF1/OpenF1 with licensing notes.
- The existing app defines the approved empty/loading/error copy, catches replay failures in `_safe_replay_result`, builds the strategy table in `_render_selected`, and injects its responsive styles in `_apply_styles`.
- `prepare_sim_plot_data` and `build_sim_figure` are shared by the app and CLI plot output; preserve their plain-data/Figure pattern while improving chart readability.
- Streamlit `AppTest` already checks page states and copy; add behavior-focused assertions for the error message, first-ranked marker, chart styling, and risk endpoints.
</code_context>

<specifics>
## Specific Ideas

- The four areas already selected for discussion are race selection/aggregation, platform versus team calls, probability scoring/interval coverage, and Streamlit controls/defaults.
- Carry forward the Phase 3 ALO interval miss and Phase 4 early-fit bias and own-laps double-counting measurements.
- Keep the dashboard's default on the known Bahrain 2023 ALO replay, with a neutral risk setting, while clearly showing fallback and calibration limits.
- Treat the selected-cutoff chart marker as a summary of that cutoff's simulated finishing distribution; label it accurately and do not imply it is a lap coordinate on the finishing-position axis.
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
*Context gathered: 2026-11-13; UI follow-up decisions added: 2026-11-14*

## Follow-up Decisions: D-12 Whole-page Visual Reset (2026-11-15)

The owner inspected the running page after D-11 and said the graphics and overall appearance still looked terrible. The D-11 dark graphite/dashboard treatment is therefore rejected and superseded by this follow-up. The prior D-11 implementation is not evidence of owner acceptance.

### D-12: Use a light editorial race-strategy workspace
- Rebuild the page as a light, warm editorial **race strategy desk** with ink-dark typography, generous alignment, a measured type/spacing scale, restrained racing red, and only the borders needed to clarify grouping.
- Remove the heavy graphite canvas, proliferated outlines, and nested card-in-card surfaces from D-11. Let spacing, typography, and alignment provide most of the hierarchy.
- Use the actual finishing-distribution chart and other existing report data as the principal graphics. A small original vector accent may support the racing identity, but it must not imply measured data, copy Formula 1 marks, or compete with the replay.

### D-13: Make the replay the first and clearest task
- Present the app identity and one-sentence purpose briefly, then lead with the race/driver/cutoff/risk controls and the selected replay result. The results chart is the main graphic; safety-car probability, tire estimate, and strategy table are organized around it.
- Move the fixed ten-race evidence below the selected replay as a concise, quieter section. Preserve every reported value, interval, denominator, count, and its existing meaning; ensure long values wrap instead of clipping.
- Populate the default Bahrain 2023 / ALO / middle-cutoff / 0.5 replay on the first usable view if the measured load time is acceptable and the result is cached by the existing inputs/cache identity. Keep the submit action for later selection changes and suppress stale results.

### D-14: Redesign the entire one-page experience
- Apply the redesign consistently to the masthead and scope note, first-load/empty/error states, replay controls, results panels, chart, strategy table/reason, fixed benchmark, and explanatory/source notes.
- Retain the one-page, read-only, cutoff-safe scope and current controls/defaults. No tabs, live mode, deployment, new metrics, copied F1 imagery/marks, or new dependencies.
- Ensure the desktop layout has a strong content grid and the narrow layout stacks naturally with no clipped labels/values; keep the full table reachable by scrolling when needed.

### D-15: Only use a pre-race race-distance horizon
- Repair the current default replay failure by supplying a race horizon from an authoritative schedule fact available independently of completed-race outcomes. Keep provenance beside any bundled or transformed schedule metadata.
- If an eligible event has no trustworthy pre-race horizon, make that event unavailable with clear recovery guidance; never infer scheduled laps from OpenF1 completed-lap counts, result laps, the last observed lap, or another post-race field.
- Preserve the existing cutoff accessor, outcome separation, and 2026 out-of-sample boundary.

### Research informing D-12 through D-15
- Apple's design principles recommend useful hierarchy, simplicity, familiarity, accessibility, and craft, while warning against decorative delight that competes with the task: https://developer.apple.com/design/human-interface-guidelines/design-principles/.
- Linear's March 2026 refresh describes lowering the visual weight of navigation, reducing unnecessary icons, and softening/removing borders so dense product content can stay in focus: https://linear.app/now/behind-the-latest-design-refresh.
- GOV.UK publishes tested responsive type and spacing scales to improve scanability and readability across devices: https://design-system.service.gov.uk/styles/type-scale/ and https://design-system.service.gov.uk/styles/spacing/.
- USWDS data-visualization guidance recommends familiar chart types, one central idea, careful color use, and accessible context: https://designsystem.digital.gov/components/data-visualizations/.
- The FIA defines scheduled race distance as the original lap distance specified on the event's Competition visa; OpenF1 documents `number_of_laps` as laps completed during the session. These are different facts, so the completed count is not an acceptable schedule fallback: https://api.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_a_general_provisions_-_iss_02_-_2026-02-27.pdf and https://openf1.org/docs/.
- Streamlit's forms have a border by default and its guidance recommends using borders only when they help group content: https://docs.streamlit.io/develop/api-reference/execution-flow/st.form and https://docs.streamlit.io/develop/concepts/design/best-practices.

*Follow-up discussion: 2026-11-15. D-12 through D-15 supersede D-11's visual choices while preserving D-07/D-08's scope and data semantics.*
