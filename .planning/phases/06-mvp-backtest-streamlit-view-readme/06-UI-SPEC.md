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

> Visual and interaction contract for the Phase 6 read-only Streamlit page. The owner's 2026-11-15 rework decisions below supersede earlier conflicting Phase 6 decisions and copy. Final browser approval remains pending in Plan 06-10.

> The owner's selected Streamlit subset of `DESIGN_BRIEF.md` adds the color, numeric, sentence-case, copy, and uncertainty-chart rules below. It supersedes earlier conflicting color tokens in this UI spec while preserving Phase 6 layout, data semantics, and scope.

## Owner Rework Addendum — 2026-11-15

This addendum is the current acceptance contract for the rejected running page. It overrides conflicting hierarchy, copy, default-cutoff, and replay-horizon instructions elsewhere in this historical UI spec. It keeps the approved Streamlit color tokens, sentence case, tabular numerals, tire and timing meanings, and uncertainty-chart design.

- Lead with the recommended strategy, its one-sentence reason, then the uncertainty charts. Put the ten-race evaluation after the selected replay. Keep the summary compact and use a simple results table instead of repeated bordered stat cards.
- Open on the working 2023 Bahrain Grand Prix replay. Keep visible race and driver pickers; select Alonso by default when present. Use after lap 15 as the initial cutoff so the default view and requested screenshots show a populated chart.
- Render the quantile dotplot and position fan chart from the selected replay's simulation outputs. Verify Bahrain 2023 after laps 15 and 40. Each dotplot row has 100 dots at the option's 100 midpoint quantiles; keep the known-distribution unit test from Plan 06-08 as a required regression.
- Use purple `#B69BFF` only for the recommended strategy. Keep the selected-cutoff marker and alternatives neutral. If an overall-best lap is already shown, label it `Best` in fog; do not color it purple. Pair tire colors with S/M/H/I/W, apply timing colors only to timing data already present, and keep all changing or comparable figures tabular.
- Remove visible middle-dot separators. Use sentence case and plain strategist language. Do not show the phrases `cutoff-safe`, `classified denominator`, or `schedule horizon` in the app. Each Brier result follows `Model 0.050 vs grid baseline 0.082 (lower is better)`, with each score rounded to three decimals. Keep the measured coverage visible as `83%` and add `Target: 85–95%`.
- Use plain result labels such as `Worst 10% average finish` and explain the recommendation without exposing formula names. Show coverage as a race average and across all finishes in everyday language; keep `83%` and `Target: 85–95%` visible. Use `95% confidence range` for comparison intervals. The safety-car panel describes its historical per-lap estimate in one clear sentence. Keep all numeric chart ticks, table values, and changing figures tabular.
- Replace the old empty-state copy with exactly two sentences: `No eligible races are available because their scheduled lap counts are missing. Refresh the race cache, then choose a supported event.` The first sentence states the problem; the second states the action.
- After corrections, run the app with Bahrain 2023 after lap 15 loaded, inspect the actual render at 1440px and 390px, and capture screenshots as `06-11-bahrain-lap15-1440.png` and `06-11-bahrain-lap15-390.png` in this phase directory. Record and fix any color, tabular-number, or copy violations before requesting approval.

The owner explicitly requires FastF1 `Session.total_laps` as the first scheduled-lap source and the winner's `Session.results["Laps"]` as fallback. Apply the backfill only to the 70 eligible cached races from 2023–2025. Keep the 2026 rows and their out-of-sample lock unchanged. Retain provenance for values supplied by the winner-result fallback. This latest owner correction supersedes D-14's ban on adding a dependency and D-15's rejection of result-lap fallback for this repair only; the existing as-of/results data-door boundary and Phase 6 scope still apply.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none — no installed UI design system or component package detected |
| Preset | not applicable |
| Component library | Streamlit native widgets and Matplotlib; Streamlit is the roadmap-required UI runtime (06-CONTEXT.md D-08) |
| Icon library | none — use text labels and native control labels |
| Font | system UI stack: system-ui, Segoe UI, Arial, sans-serif |

Design basis: the codebase has no existing app, CSS/SCSS tokens, component configuration, or UI design system. Use Streamlit's native theme for an asphalt canvas, pitwall panels, chalk primary text, fog supporting text, and system UI typography. Use color only for the tire and timing meanings defined below; keep the primary action and selected-cutoff summary neutral. Keep the existing replay data as the visual focus; do not add decorative imagery, brand-implying marks, packages, component libraries, timing-tower content, or other data surfaces. Use scoped CSS only for layout details that native theme settings cannot express, and avoid broad selectors against unstable internal DOM. This contract follows D-12 through D-15 for page flow and responsiveness; D-07/D-08 continue to lock page content, controls, defaults, read-only behavior, and safety-car proxy meaning.

### Visual Hierarchy

Use an editorial page with the asphalt canvas, pitwall panels, and a clear masthead and concise scope note. After the replay controls, lead with the recommended strategy and its one-sentence reason, followed by the finishing-position dotplot and fan chart. Put safety-car and tire companions and the ranked strategy table after the charts. Place the fixed evaluation scorecard below the replay/results; finish with source and limitation notes. Use open spacing and a few quiet surface divisions instead of nested bordered cards. The uncertainty charts are the principal graphics. On narrow screens, stack the charts and companion content, and make every scorecard metric, control, table value, and reason wrap or scroll without clipping.

The scorecard keeps all fixed measured quantities: podium and top-10 Brier scores beside the grid baseline, 90% interval coverage as equal-race and pooled values with covered and classified finish counts, top-action agreement and stop-timing error with their race-cluster 95% intervals, observed stop count, ten-race count, and observation count. Use short headings and a quiet metadata line for race/observation counts; compactness must not hide, round away, or change the meaning of a value. This presentation is read-only and introduces no new metric.

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

Use only these four sizes and two weights. (Researcher default; no upstream typography decision.) Keep the system UI font stack. Apply `font-variant-numeric: tabular-nums` to every number that is compared or updates, including table values, metric values, chart ticks, and annotations. Matplotlib labels must use a font with tabular figures or an equivalent numeric alignment method; do not use a monospace font for ordinary labels. Use sentence case for UI headings, labels, and prose; retain uppercase only for driver codes, tire letters, and established acronyms. Keep numeric values in tables and metric panels aligned consistently; use the body style for explanatory text.

---

## Color

Use only meaning-bearing color. The neutral tokens are the brief's starting palette; tire and timing values below are custom swatches tuned for contrast rather than copied from broadcast graphics.

| Token | Hex | Usage |
|-------|-----|-------|
| `asphalt` | `#1C1F23` | Page background |
| `pitwall` | `#24282D` | Panels, controls, and quiet scorecard surfaces |
| `rule` | `#3A4047` | Dividers and table rules; not the only visible control boundary |
| `chalk` | `#ECEAE4` | Primary text and neutral button text |
| `fog` | `#9BA1A8` | Supporting text, neutral chart marks, and selected-cutoff summary marker |
| Recommendation purple | `#B69BFF` | Recommended strategy only; label with `Top` |
| Destructive | none | The page has no destructive actions. Use Streamlit's semantic error treatment for failures. |

**Tire compounds**

| Compound | Letter | Hex | Contrast on asphalt / pitwall |
|----------|--------|-----|------------------------------|
| Soft | S | `#FF6B6B` | 5.96:1 / 5.34:1 |
| Medium | M | `#FFD166` | 11.47:1 / 10.28:1 |
| Hard | H | `#ECEAE4` | 13.75:1 / 12.32:1 |
| Intermediate | I | `#5FD38D` | 8.81:1 / 7.90:1 |
| Full wet | W | `#65BDFF` | 8.09:1 / 7.26:1 |

Show the compound letter beside its color anywhere compound data already appears; color is never the only compound signal.

**Timing**

| Meaning | Hex | Contrast on asphalt / pitwall |
|---------|-----|------------------------------|
| Last lap | `#ECEAE4` | 13.75:1 / 12.32:1 |
| Slower than personal best | `#FFD166` | 11.47:1 / 10.28:1 |
| Personal best | `#5FD38D` | 8.81:1 / 7.90:1 |
| Overall best | `#9BA1A8` | >4.5:1 / >4.5:1 |
| In the pit lane | `#65BDFF` | 8.09:1 / 7.26:1 |

Use the timing mappings only for timing data already present in the Phase 6 view; do not add a timing tower or infer timing states. Purple is reserved exclusively for the recommended strategy and uses a readable `Top` label. An overall-best lap uses neutral fog with a readable `Best` label. The **Update replay** action uses a neutral pitwall surface with chalk text; the selected-cutoff mean marker remains neutral fog. Safety-car probability and calibration states remain explicitly labeled and use neutral styling, not the former red signal.

Keep all labels in sentence case, including `Top` and `Best`; driver codes, tire letters, and established acronyms may remain uppercase. Aim for at least 4.5:1 for normal text and 3:1 for large text and meaningful graphical marks against their adjacent surfaces. The listed tire and timing swatches exceed 4.5:1 as text on both `asphalt` and `pitwall`; `chalk` and `fog` also exceed 4.5:1 there. Check alpha-composited chart fills on their actual surface, and give meaningful band boundaries and control focus indicators at least 3:1 contrast. Do not rely on color alone for ranking, tire compound, timing status, selected cutoff, safety-car probability, calibration, or availability.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA | Update replay |
| Empty state heading | None; show only the two-sentence empty-state body |
| Empty state body | No eligible races are available because their scheduled lap counts are missing. Refresh the race cache, then choose a supported event. |
| Unavailable schedule | This race cannot be replayed because its scheduled lap count is missing. Refresh the race cache or choose another race. |
| Error state | Replay could not be built for this selection. Check the local cache and eligible cutoffs, then retry or choose another race. |
| Destructive confirmation | None — this read-only page has no destructive actions; confirmation is not applicable. |

Use strategist language where it fits the existing recommendation data: “Box this lap,” “Stay out,” “Box in N laps,” “Undercut threat,” and “Safety car window.” Keep the reason line to one plain sentence and retain the approved empty, unavailable-schedule, and error copy above so each state explains what happened and what to do next. Use sentence case for all UI copy, with uppercase reserved for driver codes, tire letters, and established acronyms. Each uncertainty chart has a one-line caption that explains how to read it and uses the actual number of simulations represented; never hard-code the brief's 50,000 example.

---

## Interaction Contract

- Render one page with a title and a concise scope note. Do not add tabs, a navigation menu, live streaming, deployment controls, or editing actions. (06-CONTEXT.md D-07/D-08; Phase 6 boundary.)
- Keep the visual flow and emphasis defined in **Visual Hierarchy**: recommendation, reason, and uncertainty charts lead; the complete benchmark table follows the replay. Use the dark neutral tokens above, open spacing, and no nested bordered cards. Change presentation only; add no page, navigation, feature, data, or metric meaning. (06-CONTEXT.md D-12 through D-15, with the owner's later color-token update.)
- The fixed results table must retain podium and top-10 model/grid-baseline Brier pairings, interval coverage as equal-race average and pooled coverage with covered and classified finish counts, team top-action agreement and absolute stop-timing error with race-cluster 95% intervals, observed stop count, registered-race count, and Brier observation count. Compact headings and metadata may improve scanning; values and counts remain visible and unaltered. The page labels these as the fixed read-only measured results.
- Place the four controls together at the top in one form: race, driver, cutoff lap, and risk aversion. Submitting **Update replay** applies the selected values together.
- Defaults are Bahrain 2023, driver ALO, after lap 15, and risk aversion 0.5. (The owner's 2026-11-15 correction supersedes the earlier middle-cutoff default.)
- On first usable view, build the Bahrain 2023 / ALO / after-lap-15 / 0.5 replay automatically using the existing shared cache identity. Keep the selected controls visible while it loads. (D-13.)
- The race selector contains only eligible 2023–2025 catalog races; the driver selector is limited to the selected race; the cutoff control is limited to eligible cutoffs for that race. Changing race updates the driver and cutoff options.
- Events without a scheduled-lap count are excluded from selectable races and shown with the Copywriting Contract's unavailable-schedule guidance. Fill missing values from FastF1 session total laps or the winner's completed laps when the total is unavailable; do not infer counts from cached lap telemetry.
- Present risk aversion as a 0.0–1.0 slider with endpoints “Mean-focused” and “Tail-risk-focused”; show the selected value. The slider is the required risk dial and uses the locked 0.5 default. (06-CONTEXT.md D-07; existing replay bounds/default in 06-RESEARCH.md.)
- On first usable view, build the default replay automatically. Keep the submit action for later changes, show “Building replay…” while calculating, suppress stale outputs, and use the Error state copy on failure.
- Keep the page read-only and call shared cutoff-safe replay construction. The view must not access final results directly, bypass the as-of data door, or imply that 2026 is eligible. Only f1si.backtest.scoring may use final classifications. (06-CONTEXT.md D-08; 06-RESEARCH.md data-flow contract.)
- Use a wide page layout with the recommended strategy, reason, and finishing-position charts as the largest visual block, followed by safety-car/tire results and the strategy table. Keep the complete replay above the benchmark. Stack chart and companion content vertically on narrow screens; allow the strategy table to scroll horizontally if needed, and never clip metric values, labels, or reasons. Use Streamlit theme configuration for global colors/type and scoped CSS only for necessary layout details.
- Label the regime panel “Safety-car probability (current proxy)”; state that this is the existing per-lap safety-car probability, not a Markov regime classification. Mark prior-driven or sparse-fallback outputs as “Uncalibrated” adjacent to affected panels. Show unavailable data explicitly instead of implying a value.
- The strategy table shows the ranked actions and required comparison metrics; mark the actual top-ranked action with recommendation purple and a readable `Top` label. Purple is used nowhere else. If an overall-best lap is shown, use neutral fog and a readable `Best` label. The tire panel shows the existing estimate with its uncertainty and pairs any compound color with its S/M/H/I/W letter. Put the one-sentence recommendation reason above the charts beside the recommended action.
- Replace the finishing-position distribution bars with a quantile dotplot for the selected driver and cutoff, with one 100-dot row for each ranked strategy option. Each dot represents 1% of that option's simulated finishes and is placed at a quantile, not selected randomly. Use recommendation purple only for the recommended option and neutral fog for alternatives. Keep the selected-cutoff summary marker explicitly labeled `Mean finish at selected cutoff`; it summarizes the selected cutoff's simulated finishing positions and is not a lap-coordinate on the finishing-position axis. Style the figure, axes, labels, ticks, spines, grid, legend, dots, and marker for the dark neutral surfaces.
- Add a finishing-position fan chart over the remaining laps, using nested 10th–90th percentile intervals (for example, 10–90%, 25–75%, and 40–60%). Make the central band darkest and bands lighter toward the edges; use recommendation purple only for the recommended strategy and neutral grey for alternatives. Give each chart a one-line explanatory caption with the actual simulation count. Chart values and projections must come from real Phase 6 simulation outputs; if a projection is unavailable, say so instead of inventing data.
- Preserve high-contrast text and visible focus/control boundaries. Check normal text at 4.5:1, large text at 3:1, and meaningful non-text marks at 3:1 against their actual adjacent/composited colors. Use neutral focus treatment and do not use color as the only carrier of `Top`, `Best`, selected-cutoff, safety-car, fallback, tire, timing, or availability meaning.
- Keep the complete evaluation table below the replay/results, without hiding, clipping, or changing any fixed quantities: podium and top-10 model/grid Brier pairs; equal-race and pooled interval coverage with covered and classified finish counts; top-action agreement and stop-timing error with their race-cluster intervals; observed stop, registered race, and observation counts. Use concise labels and paired values; at narrow widths wrap table rows without omission.

---

## UI Considerations

Probe coverage: 29 applicable considerations across six UI elements; 0 unclassified. The --auto resolution floor resolved all 29 with backstop verification. Each behavior below has a concrete, observable acceptance condition, so the design resolutions are upgraded to explicit truths for planning and implementation verification.

| Category | Elements | Resolution | Explicit truth |
|----------|----------|------------|----------------|
| empty | E1 controls; E2 fan chart; E3 strategy table; E4 regime gauge; E5 tire panel | resolved (explicit) | With no verified eligible race, driver, or cutoff data, the page shows the Copywriting Contract's unavailable-schedule message and does not render empty charts or tables. |
| loading | E1 controls; E2 fan chart; E3 strategy table; E4 regime gauge; E5 tire panel | resolved (explicit) | Submitting "Update replay" shows the Copywriting Contract's loading message and suppresses the previous selection's outputs until the selected replay completes. |
| error | E1 controls; E2 fan chart; E3 strategy table; E4 regime gauge; E5 tire panel | resolved (explicit) | A replay failure replaces the result area with the Copywriting Contract's error and next step; stale outputs are not shown as current. |
| populated | E1 option collections; E2 fan chart; E3 strategy table; E4 regime gauge; E5 tire panel | resolved (explicit) | For an eligible selection, the page shows the ranked strategy table, finishing fan chart, safety-car proxy gauge, tire estimate with uncertainty, one-sentence reason, and selected risk value. |
| partial | E1 controls; E3 strategy table | resolved (explicit) | Incomplete selectors or strategy inputs show available values and explicit unavailable states. Prior-driven or sparse-fallback outputs in the regime gauge, tire panel, and strategy table carry "Uncalibrated" or "Unavailable at this cutoff"; unaffected panels remain visible. |
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
