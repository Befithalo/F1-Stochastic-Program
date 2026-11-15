# Phase 06 — UI Review

**Audited:** 2026-11-14
**Baseline:** Approved `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-UI-SPEC.md`
**Screenshots:** Not captured (no dev server on localhost:3000, 5173, or 8080); code-only audit
**Interaction captures:** off (workflow.ui_interaction_capture is false)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | Required replay error copy is defined but never rendered; exception details replace it. |
| 2. Visuals | 2/4 | The 13-row strategy table marks a separate generic banner, not the actual top-ranked row. |
| 3. Color | 2/4 | UI styles specify the contract neutrals, but the fan chart introduces undeclared blue and does not use the selected-point/accent encoding. |
| 4. Typography | 3/4 | Main UI CSS uses the four contract sizes and two weights; chart labels and caption instead use 6–9px. |
| 5. Spacing | 3/4 | No arbitrary spacing is found in `app.py`, but padding and control-height rules are not established against the contract. |
| 6. Experience Design | 2/4 | Replay failures expose raw exception text instead of the required recoverable error state; interaction and responsive behavior lack visual verification. |

**Overall: 14/24**

---

## Top 3 Priority Fixes

1. **Render the contract error copy and retry path** — users receive internal exception details, with no consistent next step — map failed replay states to `ERROR_COPY` and provide a retry or selection action.
2. **Mark the actual top-ranked action and selected cutoff in the data visuals** — users cannot visually distinguish the best row or selected fan-chart point as specified — style the first ranked row and add the accent marker for the selected cutoff where applicable.
3. **Complete live layout and interaction review** — narrow-screen clipping or awkward wrapping is not ruled out by CSS string checks — run the required human check at desktop and narrow widths, submitting a changed race/driver/cutoff/risk and inspecting loading, populated, and failure states.

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)

- **BLOCKER — required error copy is unused.** The contract copy is stored in `ERROR_COPY` (`src/f1si/app.py:28-31`), but both exception paths render `Replay unavailable: {reason}` (`src/f1si/app.py:461-466`). Cache, cutoff, and data errors can therefore expose implementation-specific text and omit the approved next steps. Render `ERROR_COPY` as the primary state and keep diagnostic details secondary if needed.
- The title and scope note communicate the page's one-page read-only scope (`src/f1si/app.py:369-370`), and the empty-state strings match the contract (`src/f1si/app.py:26-27`, `381-382`). The primary action label is exactly `Update replay` (`src/f1si/app.py:440`).
- Risk endpoints `Mean-focused` and `Tail-risk-focused` appear in the slider label/help (`src/f1si/app.py:432-438`), but they are not rendered as distinct endpoint labels. The selected value appears after replay rendering (`src/f1si/app.py:353`, `363`), not while choosing the value.

### Pillar 2: Visuals (2/4)

- **WARNING — top-ranked action is not marked in the table.** The view adds a standalone `TOP RANKED ACTION` banner before the full table (`src/f1si/app.py:358-361`), while all option rows are rendered uniformly. The actual top-ranked row is not visually identified, weakening comparison across 13 actions (AppTest evidence recorded in `06-06-SUMMARY.md`). Highlight the first row or give its action cell a specific marker.
- The layout creates a 2:1 fan-chart and side-panel grouping, then puts the table below (`src/f1si/app.py:312-363`), matching the intended hierarchy structurally. The CSS defines mobile wrapping (`src/f1si/app.py:295-299`) but no screenshot or browser inspection was available to establish the rendered result.
- Controls are grouped in one form at the top (`src/f1si/app.py:391-440`). Human verification is still required to confirm that the chart remains dominant, content isn't clipped, and the control widths remain readable.

### Pillar 3: Color (2/4)

- **WARNING — chart color does not follow the visual contract.** The contract reserves `#D90429` for the top-ranked strategy marker, selected fan-chart cutoff, and active safety-car marker. The chart renderer uses `_BAR_COLOR = "#4c78a8"` for every bar and `EDGE_COLOR` for the mean line (`src/f1si/plots/simulate.py:30,108-110`); the chart has no selected-cutoff accent marker. Preserve a neutral distribution and add only the specified accent markers.
- Inline page CSS defines the approved canvas `#F5F7FA`, secondary panel `#E9EEF3`, and text `#17212B` (`src/f1si/app.py:278-283`), plus the accent in progress and a banner (`src/f1si/app.py:293-294`). However, the accent banner is generic rather than attached to the ranked row, and progress styling colors the whole progress fill rather than a single active marker.
- Source search finds these hardcoded colors in CSS and the plot helper; there are no design tokens or runtime visual captures to validate the effective 60/30/10 distribution.

### Pillar 4: Typography (3/4)

- Main page CSS declares body 16px/400, labels 14px/600, headings 20px/600, and display 28px/600 (`src/f1si/app.py:279-282`), matching the contract's roles and weights.
- **WARNING — plot annotations fall below the contract sizes.** Chart labels use 9px, ticks 8px, legend 8px, and the full explanatory caption 6px (`src/f1si/plots/simulate.py:111-116`). Those sizes are difficult to read and conflict with the four-size scale, especially when the chart is embedded in a Streamlit column. Increase them to readable contract sizes or shorten the content and provide it as normal-size text outside the plot.
- No runtime screenshots were available to assess Streamlit's native widget typography or whether long table values remain legible.

### Pillar 5: Spacing (3/4)

- The app uses native Streamlit gaps (`medium`, `large`) and responsive column gap 16px (`src/f1si/app.py:296,312,392`); no arbitrary pixel/rem spacing is present in its style block.
- **WARNING — the declared scale is not fully implemented.** No page CSS establishes the 4/8/16/24/32/48/64px rhythm for panel padding, major sections, or content margins, and no minimum 44px actionable-control height is set. Native Streamlit defaults are not evidenced as matching these measurements.
- Layout adequacy remains a human visual check because CSS and source alone cannot confirm the actual spacing after Streamlit renders.

### Pillar 6: Experience Design (2/4)

- **BLOCKER — failure state does not meet the recovery contract.** `_safe_replay_result` converts errors into a fresh state (`src/f1si/app.py:86-91`), but main displays the raw reason instead of the mandated copy (`src/f1si/app.py:457-466`). Stale outputs are not reused, which is good, but users lack the consistent recovery guidance.
- Loading uses `st.spinner(LOADING_COPY)` and outputs are rendered only after the call returns (`src/f1si/app.py:447-460`); the spinner string matches the contract. Empty cache, partial availability, and fallback states have explicit code paths and labels (`src/f1si/app.py:380-383`, `132-153`, `339-348`).
- The initial page shows the fixed report and controls but no selected replay result until `Update replay` is submitted (`src/f1si/app.py:442-444`). The contract describes a populated default view; human/app behavior confirmation is needed to decide whether submit-first is acceptable UX.
- No screenshots or interaction captures were taken. The Phase 06 summary reports AppTest and CSS-string assertions, while explicitly leaving narrow viewport inspection unknown (`06-06-SUMMARY.md`). Thus keyboard focus, native select/slider behavior, responsive stacking, horizontal table scrolling, and text wrapping remain unverified visually.
- No delete or other destructive action is present, so destructive confirmation is not applicable.

---

## Files Audited

- `src/f1si/app.py`
- `src/f1si/plots/simulate.py`
- `tests/app/test_app.py` (checked existing coverage claims)
- `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-UI-SPEC.md`
- `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-CONTEXT.md`
- `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-00-SUMMARY.md` through `06-07-SUMMARY.md`
- `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-00-PLAN.md` through `06-07-PLAN.md`

---

## Human Inspection Still Required

Run the Streamlit app at desktop and narrow widths. Submit a changed race, driver, cutoff, and risk; inspect loading, populated, empty/partial, and failed replay states. Verify that the selected values are reflected in the chart and all panels, the actual top-ranked table row is distinguishable, risk endpoints are apparent, the table scrolls without clipping, and long text wraps. These behaviors were not visually captured in this audit.

---

## Follow-up Implementation Closure — 2026-11-14

The D-10 implementation changes and automated contracts are in place:

- Both replay failure branches and the race/cutoff preflight exception now call the shared renderer for the exact approved recovery copy. The failed result has no value, and the error outcome returns before selected-result components render. App tests inject private/stack-trace details and guard against displaying internal exception text.
- The ranked table now carries a `Rank` column with a red `TOP` marker attached to its first action. Existing metrics and each row's `Basis` value remain in the same row.
- The selected replay's own `finishes` feed the chart data and its mean marker. Bars use a neutral fill; the accent line is labeled `Mean finish at selected cutoff`; the axis remains `Finishing position`. The app renders the complete explanatory caption below the Figure, while standalone Figure rendering includes it by default.
- Chart title, axes, ticks, and legend use the approved typography scale. The app declares the spacing tokens and 44px native-control targets; risk endpoints and the current formatted value render before submission.
- The safety-car probability now uses a neutral track with one positioned accent marker and retains its numeric metric.

Automated evidence: `uv run python -m pytest tests/app/test_app.py tests/plots/test_simulate_plot.py -q` passed (36 tests); the full suite passed (1,095 passed, 25 deselected); Ruff check, Ruff format check, and strict mypy passed.

**Live review status: pending.** This executor session had no connected browser surface, so no 1440×900 or 390×844 visual inspection, changed-selection interaction, forced-state review, screenshot, or rendered-geometry claim was made. Exact-head Ubuntu/Windows GitHub Actions is also pending on the final pushed head. Keep the Phase 06 UI review open until those checks are recorded in `06-VALIDATION.md`.

---

## Owner Rework Audit — 2026-11-15

This audit supersedes the earlier code-only review and the 2026-11-14 live-review-pending paragraph above. It covers the owner's latest Phase 06 changes only. The owner acceptance checkpoint is still open; screenshots and tests do not imply approval.

### Browser evidence

- The refreshed app opens on **Bahrain Grand Prix 2023**, driver **ALO**, **after lap 15**, risk aversion 0.50, with race and driver pickers visible.
- At lap 15, the live page rendered both charts from 1,000 simulation outputs. The recommendation's mean finish is 18.595 and its worst-10% average is 20.000. The dotplot row has 100 points at the stored midpoint quantiles, and the fan chart uses the same replay's forward position histories.
- At lap 40, a separate live replay rendered both charts from 1,000 simulation outputs. The recommendation's mean finish is 4.512 and its worst-10% average is 6.160. The browser updated the plotted images and the accompanying lap-40 tire state after the replay settled.
- Standard screenshots are `06-11-bahrain-lap15-1440.png` (1440×900) and `06-11-bahrain-lap15-390.png` (390×844). The standard captures show the recommendation, reason, and populated dotplot; the phone capture also shows the fan-chart heading. Supplemental `06-11-bahrain-lap15-1440-full-charts.png` (1440×1700) and `06-11-bahrain-lap15-390-full-charts.png` (390×1300) show both uncertainty charts in full.
- The document and main-content widths equal the viewport at both requested widths. At 390px there is no horizontal overflow; the compact chart images render at 324px wide with readable labels and reduced numeric ticks.

### Findings and fixes

| Rule | Finding during live audit | Resolution | Final status |
|---|---|---|---|
| Color | The recommendation used purple; the initial chart also applied purple to its median and dots. The fan chart represents that same recommended strategy. | Kept purple only on the recommended action, its 100-dot distribution, and its fan-chart projection. Alternatives and the selected-cutoff mean marker remain neutral. Tire colors retain the S/M/H/I/W labels. No overall-best lap appears in this view. | Pass |
| Tabular numbers | A broad control wrapping rule split the risk slider's `0.50` into a tall stack on desktop and phone widths. Initial desktop chart images also shrank their labels at phone width, and the mean legend ran out of room. | Removed the broad slider wrap rule, explicitly applied tabular figures to the slider and results table, and added compact phone chart figures with fewer integer ticks and a fitted legend. Final slider values are single-line, 24px labels with `tabular-nums`; table cells report `tabular-nums`/`tnum`; chart ticks use DejaVu Sans Mono. | Pass |
| Copy | The displayed explanation exposed the blended-score formula and `CVaR10`; the coverage row said “classified finishers”; the safety-car panel referred to a Markov regime; and the chart caption used “midpoint empirical quantile.” | Replaced those visible phrases with the recommendation's average and worst-10% outcomes, “finishes inside the range,” a one-sentence historical safety-car explanation, and a short percentile caption. Removed middle-dot separators. Each Brier row uses the required three-decimal model/grid wording. Coverage remains `83%` and shows `Target: 85–95%`. | Pass |
| Empty state | The previous empty-state treatment did not match the owner's two-sentence recovery rule. | The app now uses one sentence for the missing eligible lap counts and one sentence for the refresh/select action. The exact copy is covered by the app tests. | Pass |

### Final copy and responsive checks

- The live DOM contains no middle-dot, `cutoff-safe`, `classified denominator`, `schedule horizon`, `CVaR10`, “Markov regime,” or “race-cluster” text.
- The live result table shows `Model 0.050 vs grid baseline 0.082 (lower is better)` and `Model 0.145 vs grid baseline 0.191 (lower is better)`; coverage reads `83% race average; 83.4% across all finishes ... Target: 85–95%.`
- Both charts remain above safety-car/tire details and the ten-race evaluation table. The evaluation is one compact table rather than repeated stat cards.
- No color, tabular-number, or copy-rule violations remain in the final 1440px and 390px views. The actual running page and screenshot evidence are ready for owner review; acceptance remains pending.

### Verification state

- Focused Phase 06 checks: 83 passed.
- Full local suite after the loader-boundary fix: 1,117 passed, 25 deselected.
- Ruff check, Ruff format check, mypy, and lock validation passed.
- Exact-head Ubuntu/Windows CI remains pending until the final implementation commit is pushed and both jobs complete. See `06-11-SUMMARY.md` for the final head and CI record.
