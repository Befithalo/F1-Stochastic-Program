---
phase: "06"
slug: "mvp-backtest-streamlit-view-readme"
status: draft
shadcn_initialized: false
preset: none
created: "2026-11-13"
reviewed_at: "2026-11-15"
---

# Phase 06 — UI Design Contract

> Visual and interaction contract for the Phase 6 read-only Streamlit page. D-12 through D-15 supersede the rejected D-11 visual direction. Owner browser acceptance remains pending in Plan 06-10.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none — no installed UI design system or component package detected |
| Preset | not applicable |
| Component library | Streamlit native widgets and Matplotlib; Streamlit is the roadmap-required UI runtime (06-CONTEXT.md D-08) |
| Icon library | none — use text labels and native control labels |
| Font | system UI stack: system-ui, Segoe UI, Arial, sans-serif |

Design basis: the codebase has no existing app, CSS/SCSS tokens, component configuration, or UI design system. Use Streamlit's native theme for a warm, light editorial canvas, clear ink text, restrained red action accent, and system UI typography. Keep the existing chart and replay data as the visual focus; do not add decorative imagery, brand-implying marks, packages, or component libraries. Use scoped CSS only for layout details that native theme settings cannot express, and avoid broad selectors against unstable internal DOM. This contract follows D-12 through D-15; D-07/D-08 continue to lock page content, controls, defaults, read-only behavior, and safety-car proxy meaning.

### Visual Hierarchy

Use a warm, light editorial page with a clear masthead and concise scope note, then put replay controls and their results first: controls, finishing-position distribution, safety-car and tire companions, ranked strategy table and reason. Place the fixed evaluation scorecard below the replay/results so it supports rather than delays the main task; finish with source and limitation notes. Use open spacing and a few quiet surface divisions instead of nested bordered cards. The existing replay chart is the principal graphic. On narrow screens, stack the chart and companion content, and make every scorecard metric, control, table value, and reason wrap or scroll without clipping.

The scorecard keeps all fixed measured quantities: podium and top-10 model/grid-baseline Brier pairings, 90% interval coverage with equal-race and pooled values plus its classified denominator, top-action agreement and stop-timing error with their race-cluster 95% intervals, observed stop count, ten-race count, and observation count. Use short headings and a quiet metadata line for race/observation counts; compactness must not hide, round away, or change the meaning of a value. This presentation is read-only and introduces no new metric.

---

## Spacing Scale

Declared values (must be multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon-free inline label gaps and compact chart annotations |
| sm | 8px | Compact control and table-cell spacing |
| md | 16px | Default element spacing |
| lg | 24px | Panel padding and section spacing |
| xl | 32px | Main layout gaps |
| 2xl | 48px | Major section breaks |
| 3xl | 64px | Page-level spacing |

Exceptions: use a 44px minimum height for actionable controls where the native widget permits; there are no icon-only controls. (Researcher default; no upstream spacing decision.)

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 16px | Regular (400) | 1.5 |
| Label | 14px | Semibold (600) | 1.4 |
| Heading | 20px | Semibold (600) | 1.2 |
| Display | 28px | Semibold (600) | 1.2 |

Use only these four sizes and two weights. (Researcher default; no upstream typography decision.) Keep numeric values in tables and metric panels aligned consistently; use the body style for explanatory text.

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | #F6F4EE | Warm paper page canvas |
| Secondary (30%) | #FFFFFF | Open, light surface for controls, charts, and result groups |
| Quiet surface | #F0EFE9 | Subtle separation for scorecard rows and control groupings; avoid nested cards |
| Primary text | #17212B | Titles, values, table content, and labels on light surfaces |
| Supporting text | #58646D | Captions, explanatory copy, chart ticks, and metadata |
| Neutral chart marks | #6F7C86 | Finishing-distribution bars and non-semantic chart marks |
| Accent (reserved) | #D90429 | Primary submit action and existing result signals only |
| Destructive | none | The page has no destructive actions. Use Streamlit's semantic error treatment for failures. |

Accent reserved for the **Update replay** primary action and the existing top-ranked, selected-cutoff finishing-summary, and safety-car probability signals. Do not use red for general links, slider tracks/focus states, all table rows, chart bars, headings, or decorative fills. Pair the row signal with readable `TOP` text and chart signals with labels; never rely on color alone. Use white text on the red primary action and keep generic widget highlights neutral. Recheck contrast for every adjacent surface pair. The light palette and restrained accent implement D-12; colors do not change data meaning.

Contrast checks: target at least 4.5:1 for normal text, 3:1 for large text, and 3:1 for meaningful control boundaries and graphical marks against adjacent surfaces. Verify actual palette pairings during implementation; do not carry forward contrast claims calculated for the rejected dark palette. Do not rely on color alone to convey ranking, selected cutoff, safety-car probability, calibration, or availability.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA | Update replay |
| Empty state heading | No verified race schedule available |
| Empty state body | Choose an event with verified pre-race schedule metadata or load the supported local race cache. |
| Unavailable schedule | This event has no verified pre-race schedule horizon and cannot be replayed. Choose an event with verified schedule metadata. |
| Error state | Replay could not be built for this selection. Check the local cache and eligible cutoffs, then retry or choose another race. |
| Destructive confirmation | None — this read-only page has no destructive actions; confirmation is not applicable. |

---

## Interaction Contract

- Render one page with a title and a concise scope note. Do not add tabs, a navigation menu, live streaming, deployment controls, or editing actions. (06-CONTEXT.md D-07/D-08; Phase 6 boundary.)
- Keep the visual flow and emphasis defined in **Visual Hierarchy**: replay and results first, complete benchmark scorecard below. Use a warm light canvas, restrained surfaces, open spacing, and no nested bordered cards. Change presentation only; add no page, navigation, feature, data, or metric meaning. (06-CONTEXT.md D-12 through D-15.)
- The fixed scorecard must retain the podium and top-10 model/grid-baseline Brier pairings, interval coverage as equal-race average and pooled coverage with its covered/classified denominator, team top-action agreement and absolute stop-timing error with race-cluster 95% intervals, observed stop count, registered-race count, and Brier observation count. Compact headings and metadata may improve scanning; values and denominators remain visible and unaltered. The page labels these as the fixed read-only measured results.
- Place the four controls together at the top in one form: race, driver, cutoff lap, and risk aversion. Submitting **Update replay** applies the selected values together.
- Defaults are Bahrain 2023, driver ALO, the middle eligible cutoff for that race, and risk aversion 0.5. (Locked by 06-CONTEXT.md D-07.)
- On first usable view, attempt the default Bahrain 2023 / ALO / middle-cutoff / 0.5 replay automatically using the existing shared cache identity. Target a populated first view within 5 seconds on a cold local cache and 1 second on a warm cache; if cold calculation cannot meet 5 seconds, show a branded, explicit one-click load state with visible defaults and progress rather than a generic empty/error page. (D-13.)
- The race selector contains only eligible 2023–2025 catalog races; the driver selector is limited to the selected race; the cutoff control is limited to eligible cutoffs for that race. Changing race updates the driver and cutoff options.
- Events without a verified pre-race schedule horizon are excluded from selectable races and shown with the Copywriting Contract's explicit unavailable-schedule guidance. Do not replace missing metadata with completed or observed lap counts.
- Present risk aversion as a 0.0–1.0 slider with endpoints “Mean-focused” and “Tail-risk-focused”; show the selected value. The slider is the required risk dial and uses the locked 0.5 default. (06-CONTEXT.md D-07; existing replay bounds/default in 06-RESEARCH.md.)
- On initial usable view, attempt the documented default replay through the existing cache identity. Target a populated default view within 5 seconds for a cold local cache and 1 second for a warm cache; if the cold path exceeds 5 seconds, use a branded one-click load state that retains the visible default selection and progress. Keep the submit action for later changes, show “Building cutoff-safe replay…” while calculating, suppress stale outputs, and use the Error state copy on failure.
- Keep the page read-only and call shared cutoff-safe replay construction. The view must not access final results directly, bypass the as-of data door, or imply that 2026 is eligible. Only f1si.backtest.scoring may use final classifications. (06-CONTEXT.md D-08; 06-RESEARCH.md data-flow contract.)
- Use a wide page layout with the finishing-position chart as the largest visual block and safety-car/tire results as readable companions on desktop. Keep the replay controls and full result flow above the benchmark. Stack chart and companion content vertically on narrow screens; allow the strategy table to scroll horizontally if needed, and never clip metric values, labels, or reasons. Include a repeatable first-view timing check for cold and warm cache paths. Use Streamlit theme configuration for global colors/type and scoped CSS only for necessary layout details.
- Label the regime panel “Safety-car probability (current proxy)”; state that this is the existing per-lap safety-car probability, not a Markov regime classification. Mark prior-driven or sparse-fallback outputs as “UNCALIBRATED” adjacent to affected panels. Show unavailable data explicitly instead of implying a value.
- The fan chart shows the finishing-position distribution for the selected driver and cutoff. The strategy table shows the ranked actions and the required comparison metrics; visually mark the top-ranked action. The tire panel shows the estimate with its uncertainty. Put the one-sentence recommendation reason directly under the table.
- Keep distribution bars neutral (#6F7C86) and the selected-cutoff summary marker racing red (#D90429), explicitly labeled `Mean finish at selected cutoff`; the marker summarizes the selected cutoff's simulated finishing positions and is not a lap-coordinate on the finishing-position axis. Style figure, axes, labels, ticks, spines, grid, legend, bars, and marker for the warm light surfaces. Keep the full explanatory caption in readable page text or a legible figure note. The safety-car probability remains explicitly labeled and readable without relying on red alone.
- Preserve high-contrast text and visible focus/control boundaries. Check normal text at 4.5:1, large text at 3:1, and meaningful non-text marks at 3:1 against their adjacent colors. Do not use color as the only carrier of `TOP`, selected-cutoff, safety-car, fallback, or availability meaning.
- Keep the complete evaluation scorecard below the replay/results, without hiding, clipping, or changing any fixed quantities: podium and top-10 model/grid Brier pairs; equal-race and pooled interval coverage and its classified denominator; top-action agreement and stop-timing error with their race-cluster intervals; observed stop, registered race, and observation counts. Use concise labels and paired values; at narrow widths wrap metrics into readable rows/cards without omission.

---

## UI Considerations

Probe coverage: 29 applicable considerations across six UI elements; 0 unclassified. The --auto resolution floor resolved all 29 with backstop verification. Each behavior below has a concrete, observable acceptance condition, so the design resolutions are upgraded to explicit truths for planning and implementation verification.

| Category | Elements | Resolution | Explicit truth |
|----------|----------|------------|----------------|
| empty | E1 controls; E2 fan chart; E3 strategy table; E4 regime gauge; E5 tire panel | resolved (explicit) | With no verified eligible race, driver, or cutoff data, the page shows the Copywriting Contract's unavailable-schedule message and does not render empty charts or tables. |
| loading | E1 controls; E2 fan chart; E3 strategy table; E4 regime gauge; E5 tire panel | resolved (explicit) | Submitting "Update replay" shows the Copywriting Contract's loading message and suppresses the previous selection's outputs until the selected replay completes. |
| error | E1 controls; E2 fan chart; E3 strategy table; E4 regime gauge; E5 tire panel | resolved (explicit) | A replay failure replaces the result area with the Copywriting Contract's error and next step; stale outputs are not shown as current. |
| populated | E1 option collections; E2 fan chart; E3 strategy table; E4 regime gauge; E5 tire panel | resolved (explicit) | For an eligible selection, the page shows the ranked strategy table, finishing fan chart, safety-car proxy gauge, tire estimate with uncertainty, one-sentence reason, and selected risk value. |
| partial | E1 controls; E3 strategy table | resolved (explicit) | Incomplete selectors or strategy inputs show available values and explicit unavailable states. Prior-driven or sparse-fallback outputs in the regime gauge, tire panel, and strategy table carry "UNCALIBRATED" or "Unavailable at this cutoff"; unaffected panels remain visible. |
| overflow | E1 option collections; E3 strategy table; E6 reason line | resolved (explicit) | Narrow layouts stack the panels, the strategy table can scroll horizontally, and the reason line wraps; values and labels are not clipped. |
| zero-one-many | E1 race/driver option collections; E3 strategy actions | resolved (explicit) | Zero eligible options use the Empty state; one option remains selectable with singular labels; many options remain catalog-filtered and every ranked action remains visible with a row count. |
| long-text | E1 control labels; E6 reason line and explanatory notes | resolved (explicit) | Long labels, explanations, and the one-sentence reason wrap and grow vertically without ellipses or truncation. |

There is no navigation element in the locked one-page scope.


## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| none | none | not applicable — no shadcn initialization or third-party registry use |

---

## Checker Sign-Off

D-11's earlier checker review is historical only; the owner rejected that rendered design. This D-12–D-15 contract is ready to guide implementation, but its actual hierarchy, contrast, responsive behavior, and first-load experience have not been checked against the running site. Plan 06-10 retains the blocking owner browser checkpoint at 1440×900 and 390×844. No prior human acceptance carries forward.
