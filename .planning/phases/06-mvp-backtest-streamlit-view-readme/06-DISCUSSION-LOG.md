# Phase 6: MVP Backtest, Streamlit View & README - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `06-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-11-13
**Phase:** 6-MVP Backtest, Streamlit View & README
**Areas discussed:** Race selection and aggregation, probability scores and interval coverage, platform recommendations and observed team stops, Streamlit controls and defaults

**Follow-up date:** 2026-11-14
**Follow-up area:** UI review remediation, using the user's standing instruction to select the agent-recommended option.

---

## Race selection and aggregation

| Option | Description | Selected |
|--------|-------------|----------|
| Balanced chronological sample | Pre-register 10 complete 2023–2025 races, balanced 4/3/3 by season where available; score all eligible cutoffs, give each race equal weight, and bootstrap by race. | ✓ Recommended |
| First ten complete races | Select the first ten by calendar order, likely concentrating the sample in 2023. | |
| Outcome-informed sample | Inspect results or model metrics before selecting the races. | |

**User's choice:** Agent-selected recommended option, authorized by the user's instruction: “Whatever you recommend choose that.” The user had already selected this discussion area.
**Notes:** Keep Bahrain 2023 as the fixed reference race. Select the remaining IDs using calendar and data completeness only, before scoring.

## Probability scores and interval coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Past-only probabilistic baseline | Score podium/top-10 Brier against a smoothed grid-position baseline trained only on earlier races; use central empirical 90% finish intervals and race-clustered uncertainty. | ✓ Recommended |
| Deterministic threshold baseline | Use 0/1 grid-position thresholds and pooled coverage without race-level uncertainty. | |
| Tune on evaluation races | Adjust interval width using the ten evaluation races until aggregate coverage approaches 90%. | |

**User's choice:** Agent-selected recommended option, authorized by the user's instruction: “Whatever you recommend choose that.” The user had already selected this discussion area.
**Notes:** Also measure the Phase 4 wear band as a labeled retrospective diagnostic against a leave-current-stint-out reference. This is not latent ground truth and does not authorize tuning the filter on these races.

## Platform recommendations and observed team stops

| Option | Description | Selected |
|--------|-------------|----------|
| Event-aligned comparison | Pair each recommendation with the next observed pit event; report per-race action agreement and stop-timing error with 95% race-cluster bootstrap intervals. | ✓ Recommended |
| End-of-race plan comparison | Compare only final plans after the race is complete. | |
| Claim team superiority | Treat position changes as proof that the platform beats actual teams. | |

**User's choice:** Agent-selected recommended option, authorized by the user's instruction: “Whatever you recommend choose that.” The user had already selected this discussion area.
**Notes:** Frame this as agreement with observed team behavior, not proof of superiority.

## Streamlit controls and defaults

| Option | Description | Selected |
|--------|-------------|----------|
| One cutoff-safe read-only page | Show the required strategy table, finish fan chart, regime gauge, tire panel, reason, and risk dial; controls for race, driver, lap, and risk; default to Bahrain 2023 / ALO / mid-race / 0.5 risk. | ✓ Recommended |
| Static report | Render a fixed race report without controls. | |
| Broader live dashboard | Add live streaming, deployment controls, and extra navigation. | |

**User's choice:** Agent-selected recommended option, authorized by the user's instruction: “Whatever you recommend choose that.” The user had already selected this discussion area.
**Notes:** The regime view reflects the existing safety-car probability model. Label prior-driven or sparse-fallback estimates as uncalibrated.

## the agent's Discretion

- Choose the exact ten race IDs within the committed selection rule and record them before scoring.
- Choose baseline smoothing and race-cluster bootstrap details, app module layout, caching, and chart styling while preserving the decisions in `06-CONTEXT.md`.

## Deferred Ideas

- 20-race per-era evaluation and the one-time 2026 holdout (Phase 8).
- Hierarchical Bayesian pace modeling (Phase 7).
- Markov regimes and regime-dependent pit loss (Phase 8).
- Live streaming, production deployment, market-odds benchmarking, and broader dashboard features.

---

## Follow-up: UI review remediation (2026-11-14)

| Area | Recommended option selected | Rationale |
|---|---|---|
| Error recovery | Render the exact approved error copy and keep raw exception text out of the user-facing state. | Matches the UI-SPEC recovery contract and avoids leaking implementation details. |
| Ranked strategy table | Mark the actual first-ranked row with the accent. | The generic banner alone does not identify the row among the ranked actions. |
| Finishing-position chart | Use neutral bars and an accent marker labeled as the selected-cutoff distribution summary. | Preserves the selected-cutoff signal while keeping the chart's finishing-position axis truthful. |
| Typography and layout | Use readable chart sizes, documented spacing/control sizing where Streamlit permits, visible risk endpoints, and inspect desktop plus narrow layouts. | Closes the remaining contract and live-layout gaps without expanding the page scope. |

**Selection:** Agent-selected recommended options, authorized by the user's standing instruction to choose the recommendation.
**Deferred ideas:** None; this follow-up stays within Phase 6's approved one-page view.

---

## Follow-up: visual redesign (2026-11-14)

| Option | Description | Selected |
|--------|-------------|----------|
| Dark motorsport dashboard | Graphite canvas, layered slate cards, high-contrast type, compact scorecard, clear controls/results hierarchy, chart-led visual, restrained red indicators. | ✓ Recommended |
| Refined light editorial dashboard | White canvas, subtle borders, compact scorecard and chart-led hierarchy while keeping light surfaces. | |
| Preserve the current appearance | Adjust only individual spacing or chart details in the existing light Streamlit layout. | |

**Owner's feedback:** The owner viewed the running site and said its graphics and appearance looked poor, asking for a visual fix.
**Selected approach:** The agent-selected recommended direction, authorized by the owner's standing instruction to choose recommendations. Preserve Phase 6's one-page read-only scope, data boundaries, chart semantics, and existing content.
**Decisions captured:** D-11 in `06-CONTEXT.md`; the prior light palette and flat component treatment are superseded for the visual redesign.

---

## Follow-up: visual redesign (2026-11-14)

| Option | Description | Selected |
|--------|-------------|----------|
| Dark motorsport dashboard | Graphite canvas, layered slate cards, high-contrast type, compact scorecard, clear controls/results hierarchy, chart-led visual, restrained red indicators. | ✓ Recommended |
| Refined light editorial dashboard | White canvas, subtle borders, compact scorecard and chart-led hierarchy while keeping light surfaces. | |
| Preserve the current appearance | Adjust only individual spacing or chart details in the existing light Streamlit layout. | |

**Owner's feedback:** The owner viewed the running site and said its graphics and appearance looked poor, asking for a visual fix.
**Selected approach:** The agent-selected recommended direction, authorized by the owner's standing instruction to choose recommendations. Preserve Phase 6's one-page read-only scope, data boundaries, chart semantics, and existing content.
**Decisions captured:** D-11 in `06-CONTEXT.md`; the prior light palette and flat component treatment are superseded for the visual redesign.
