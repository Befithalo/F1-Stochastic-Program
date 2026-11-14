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
