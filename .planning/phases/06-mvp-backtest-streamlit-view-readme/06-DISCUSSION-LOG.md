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

## Follow-up: whole-page redesign after owner rejection (2026-11-15)

**Observed state:** The 1440×900 capture showed a dark page dominated by nested bordered scorecard panels. The coverage denominator is cut off, then the replay controls show only the race selector and a generic error. The screen has no populated replay/chart, so the primary job of the page is missing.

**Research comparison:**

| Reference | Finding relevant to this page |
|---|---|
| Apple Human Interface Guidelines | Establish hierarchy, keep the interface simple and familiar, prioritize accessibility and craft, and avoid decoration that competes with the task. |
| Linear's 2026 interface refresh | In a dense product, quiet secondary elements; remove unnecessary icons and borders so the working content carries attention. |
| GOV.UK Design System | Use a tested, responsive type scale and coherent spacing rhythm for readability and scanability. |
| USWDS data-visualization guidance | Use familiar charts, one main idea per visualization, careful color, and accessible explanatory context. |
| Streamlit best-practice/API docs | Forms have a border by default; border grouping should be intentional, which explains how the current outer and inner forms create visual noise. |

**Schedule-data finding:** The current replay error is not a CSS issue. The default race's cached `scheduled_laps` is null, and `walk_forward._race_laps_total` correctly refuses to continue without a planned horizon. OpenF1 describes `number_of_laps` as the number completed during a session, while the FIA defines scheduled race distance as the original lap distance set for the event. The fix must source pre-race schedule facts and cannot substitute final results or observed laps.

| Decision area | Recommended option selected | Rationale |
|---|---|---|
| Visual language | Warm, light editorial race-strategy desk with ink text and restrained red. | It rejects the dark dashboard the owner just saw, while using hierarchy, alignment, and contrast to make the real replay content feel intentional. |
| Page order | Replay controls and populated selected-race result first; fixed ten-race benchmark second. | The page's main job is race strategy. Benchmark evidence remains complete but should not dominate the first screen. |
| Graphics | Lead with the existing finishing-distribution chart and real measured evidence; use only a small original, non-data-implying vector accent if needed. | It adds a visual identity without inventing telemetry, copying F1 branding, or distracting from chart meaning. |
| Whole-page scope | Refresh identity, states, controls, result panels, chart/table/reason, benchmark and explanatory notes as one coherent page. | Local spacing tweaks cannot fix the broken hierarchy and empty first impression visible in the capture. |
| Default first view | Populate the locked default replay on first usable load when its runtime is acceptable, cache the result, and retain explicit submit behavior for changes. | A strategy product should show its main artifact immediately; the first impression should not be an empty prompt. |
| Race horizon | Require an authoritative ex-ante schedule fact; clearly disable/error when missing. | The user-facing error must be resolved without leaking outcome information into the cutoff-safe path. |

**Selection:** The owner previously authorized choosing the agent's recommendation and asked for autonomous progress. These recommendations were selected under that standing instruction.
**Decisions captured:** D-12–D-15 in `06-CONTEXT.md`. D-11's visual choices are superseded; D-07/D-08's data contract and feature boundary remain in force.
**Sources:** Apple HIG, Linear's interface refresh, GOV.UK type/spacing, USWDS chart guidance, Streamlit forms/best practices, OpenF1 docs, and FIA 2026 General Provisions are linked in `06-CONTEXT.md`.

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
