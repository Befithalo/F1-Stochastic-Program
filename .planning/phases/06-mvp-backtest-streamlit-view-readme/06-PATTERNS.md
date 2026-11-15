# Phase 6: MVP Backtest, Streamlit View & README - Pattern Map

**Mapped:** 2026-11-14 (D-11 visual refresh)
**Files analyzed:** 4 UI files in the D-10/D-11 follow-up scope
**Analogs found:** 4 / 4 (all targets already exist and are tracked)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/f1si/app.py` | component (Streamlit page) | request-response | `src/f1si/app.py` | exact |
| `src/f1si/plots/simulate.py` | utility (plot preparation/renderer) | transform | `src/f1si/plots/simulate.py` | exact |
| `tests/app/test_app.py` | test | request-response | `tests/app/test_app.py` | exact |
| `tests/plots/test_simulate_plot.py` | test | transform | `tests/plots/test_simulate_plot.py` | exact |

These are the visual-refresh targets. The scorecard and replay panels are both rendered in `app.py`; there is no separate card component or CSS file. Backtest scoring, README evidence, and other phase files are outside this UI mapping. `git ls-files --error-unmatch` verified all four analog paths are tracked.

## Pattern Assignments

### `src/f1si/app.py` (Streamlit page, request-response)

**Analog:** `src/f1si/app.py` (the existing replay page and scorecard).

**Imports and page/data boundary** (lines 11-20):

```python
import numpy as np
import pandas as pd
import streamlit as st

import f1si.backtest.walk_forward as walk_forward
from f1si import cli, paths
from f1si.data import asof
from f1si.plots.simulate import build_sim_figure, prepare_sim_plot_data
```

Keep the existing cutoff-safe replay path and do not import `f1si.data.results` into the view. Presentation work should not move data construction into CSS/card helpers or change replay inputs.

**Report metrics and compact scorecard** (lines 263-310):

```python
def _report_display_values(report: dict[str, Any]) -> dict[str, str]:
    metrics = report["metrics"]
    podium = metrics["podium_brier"]
    top10 = metrics["top10_brier"]
    coverage = metrics["finish_interval_90"]
    team = metrics["team_strategy_comparison"]
    ...

def _render_report_summary(report: dict[str, Any]) -> None:
    display = _report_display_values(report)
    metrics = report["metrics"]
    st.subheader("Complete ten-race evaluation · fixed report")
    st.caption(f"{len(report['race_ids'])} registered races · ...")
    columns = st.columns(3)
    columns[0].metric("Podium Brier · model / grid baseline", display["podium"])
    columns[1].metric("Top-10 Brier · model / grid baseline", display["top10"])
    columns[2].metric("90% finish interval coverage · ...", display["coverage"])
    st.caption("Team comparison: " + display["team"])
```

Reuse the prepared display strings and metric values. D-11 calls for a compact ten-race scorecard; group it in a bordered `st.container` and use a tight multi-column metric row, retaining model/baseline pairing, equal-race and pooled coverage denominator, team comparison/interval, registered race count, and observation count. Do not omit required numbers to gain compactness. Use graphite canvas and layered slate surfaces, high contrast text, and deliberate spacing; D-11 supersedes the former light values in the current CSS. The updated context leaves exact hex tokens to implementation discretion.

**Containers and page hierarchy** (lines 358-416, 419-425):

```python
left, right = st.columns((2, 1), gap="large")
with left:
    st.pyplot(build_sim_figure(chart, include_caption=False), clear_figure=True)
    st.caption(chart.caption)
with right:
    st.subheader("Safety-car probability (current proxy)")
    ...
    st.subheader("Tire estimate and uncertainty")
    ...
```

Use native `st.container(border=True, key=...)` as the pattern for layered slate scorecard, replay-control, chart, safety-car, and tire panels. Keep the one-page flow: compact scorecard, easy-to-scan controls, dominant finishing chart beside tidy safety-car/tire companion cards, then full-width strategy table and reason. Retain `st.columns((2, 1), gap="large")` as the desktop chart/sidebar proportion and stack at narrow width. Keep the safety-car proxy explanation, fallback/unavailable labels, and current metric content inside their associated cards. Do not nest columns more than once; the approved `06-UI-SPEC.md` requires controls together in a form, responsive stacking, and table/reason overflow handling.

**CSS and native-control sizing** (lines 313-350):

```css
:root {
    --space-xs: 4px; --space-sm: 8px; --space-md: 16px;
    --space-lg: 24px; --space-xl: 32px; --space-2xl: 48px; --space-3xl: 64px;
}
.stApp { background: #F5F7FA; color: #17212B; }
[data-testid="stVerticalBlockBorderWrapper"] { background: #E9EEF3; }
[data-testid="stDataFrame"] [role="grid"] { overflow-x: auto !important; }
[data-testid="stSelectbox"] [data-baseweb="select"] { min-height: 44px; }
@media (max-width: 760px) { ... }
```

Preserve spacing and type roles from the approved UI spec (4/8/16/24/32/48/64 px; body 16, label 14, heading 20, display 28; 44 px actionable targets where native widgets permit), plus wrapping, horizontal table scrolling, and narrow stacking. Replace the light palette with D-11's graphite canvas, slate layers, crisp high-contrast type; reserve racing red for the primary action and the existing top-ranked, finishing-summary, and safety-car signals. Scope any custom selectors narrowly (prefer keyed containers), since Streamlit's internal `data-testid` structure can change. Do not use CSS to recolor every widget red. Keep visible risk endpoints and selected value near the update action.

**Safety-car gauge and accent placement** (lines 116-126, 380-397, 410-415):

```python
def _probability_track_markup(probability: float) -> str:
    value = min(max(float(probability), 0.0), 1.0)
    return (
        '<div role="img" aria-label="Safety-car probability: '
        f'{value:.1%}" ... background: #E9EEF3; ...>'
        f'<span ... left: {value * 100:.1f}%; ... background: #D90429; ...></span></div>'
    )

styled_table = strategy_table.style.map(
    lambda value: "color: #D90429; font-weight: 600;" if value == "TOP" else "",
    subset=["Rank"],
)
```

Keep the track neutral with a single red, positioned marker and accessible probability label; pair with the numeric probability and proxy label. Keep red only on the actual first-ranked `TOP` row marker, the chart summary, and this safety-car marker (plus primary CTA); retain a textual marker so meaning does not depend on color. Avoid red-only small text on slate.

**Ranked table and safe replay state** (lines 78-113, 404-416, 445-466):

```python
def _ranked_strategy_rows(columns, rows):
    return ("Rank", *columns), tuple(
        ("TOP" if index == 0 else "", *row) for index, row in enumerate(rows)
    )

def _safe_replay_result(builder):
    try:
        return {"status": "ready", "value": builder()}
    except Exception as err:
        return {"status": "error", "value": None, "reason": str(err)}

def _render_replay_failure() -> None:
    st.info(ERROR_COPY)
```

Keep `Basis` adjacent to each action and accent the `TOP` value on row zero, not a detached banner. Preserve fresh-error semantics (`value: None`) and render only exact approved `ERROR_COPY`; never expose `reason`/exception text. The reason line stays under the table and wraps without clipping.

### `src/f1si/plots/simulate.py` (plot utility, transform)

**Analog:** `src/f1si/plots/simulate.py` (pure plot-data preparation and direct-Figure renderer).

**Plain-data and renderer pattern** (lines 23-47, 50-100, 104-131):

```python
import numpy as np
from matplotlib.figure import Figure

@dataclass(frozen=True, eq=False)
class SimPlotData:
    probabilities: NDArray[np.float64]
    mean: float
    median: float
    interval: tuple[float, float]

def build_sim_figure(data: SimPlotData, *, include_caption: bool = True) -> Figure:
    fig = Figure(figsize=(9, 5), layout="constrained")
    ax = fig.subplots()
    places = np.arange(1, len(data.probabilities) + 1)
    ax.bar(places, data.probabilities, edgecolor=EDGE_COLOR, color=_BAR_COLOR)
    ax.axvline(data.mean, color=_SUMMARY_COLOR, linestyle="--", linewidth=2.0,
               label="Mean finish at selected cutoff")
    ax.set_xlabel("Finishing position", fontsize=12)
    ax.set_ylabel("Share of simulated races", fontsize=12)
    ax.tick_params(labelsize=10.5)
    ax.legend(fontsize=10.5)
    fig.suptitle(data.title, fontsize=15, fontweight="semibold")
    if include_caption:
        fig.text(0.01, 0.01, data.caption, fontsize=12, wrap=True, va="bottom")
    return fig
```

Keep the pure array/scalar preparation boundary and direct `Figure` API; do not add `pyplot` or fetch data in the renderer. Give the chart visual priority. For the dark card, explicitly set figure/axes facecolors, title/axis/tick/legend text, spines, grid, and bar edge colors for readable graphite/slate contrast in both embedded Streamlit and saved PNG output. Keep bars neutral and use the accent only for the labeled selected-cutoff finishing summary; the marker is a finish-position value, not a lap coordinate. Keep caption/caveat text legible (move lengthy caveat to page body if necessary) and preserve selected-cutoff versus hindsight semantics. `SimPlotData` already computes probability bins, mean, median, and empirical interval from the same supplied draws.

### `tests/app/test_app.py` (test, request-response)

**Analog:** `tests/app/test_app.py` (AppTest and focused source/helper assertions).

**AppTest harness and state checks** (lines 126-146, 157-185, 229-285):

```python
app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
result = app_test.from_file(APP_PATH).run()
assert not result.exception

result = app_test.from_file(APP_PATH).run()
assert any(item.value == "No race data available" for item in result.subheader)
assert len(result.dataframe) == 0
assert len(result.get("imgs")) == 0
```

Extend existing error/empty, fallback-basis, top-row, selected-cutoff, CSS responsive-hook, risk-endpoint, and safety-car marker assertions as behavior changes. AppTest/source assertions cover state and semantic hooks; use rendered desktop and narrow-width inspection for hierarchy, actual dark contrast, card dimensions, wrapping, clipping, and compact scorecard readability. Do not treat AppTest as viewport/layout proof.

### `tests/plots/test_simulate_plot.py` (test, transform)

**Analog:** `tests/plots/test_simulate_plot.py` (Figure artist assertions and pure-data checks).

**Figure checks** (lines 56-98):

```python
fig = build_sim_figure(data)
assert isinstance(fig, Figure)
ax = fig.axes[0]
assert len(ax.patches) == 20
assert ax.get_xlabel() == "Finishing position"
assert [line.get_label() for line in ax.get_lines()] == [
    "Mean finish at selected cutoff"
]
assert cast(str, ax.get_lines()[0].get_color()).lower() == "#d90429"
assert all(to_rgba("#D90429") != patch.get_facecolor() for patch in ax.patches)
```

Retain plot data and direct-Figure assertions for bar neutrality, selected-cutoff marker value/label, readable typography and no-pyplot import. Add checks for dark facecolors and text/legend/grid contrast if implementing dark theming in the plot helper; maintain the PNG rendering check so export and embedded backgrounds agree.

## Shared Patterns

### D-11 visual hierarchy and surfaces

**Sources:** `src/f1si/app.py:289-350, 358-397`; `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-CONTEXT.md` D-11.
**Apply to:** scorecard, controls, chart, safety-car and tire panels.

Use native bordered containers for layered slate cards; keep the scorecard dense but complete, controls scannable, chart dominant, and safety-car/tire cards paired. Use a graphite background, high-contrast text, spacing from the approved scale, and a narrow responsive stack. D-11 role colors are locked; exact dark hex values are not. No separate project card/CSS system exists.

### Accent and accessible labels

**Sources:** `src/f1si/app.py:89-92, 116-126, 410-415`; `src/f1si/plots/simulate.py:31-32, 109-116`.
**Apply to:** primary CTA and existing top-ranked, finish-summary, and safety-car signals only.

Use racing red sparingly, with a `TOP` label, chart legend, or numeric probability as text context. Keep chart bars neutral. Do not infer D-11 red for other metrics, cards, or controls.

### Data correctness and error copy

**Sources:** `src/f1si/app.py:95-113, 353-416`; `tests/app/test_app.py:157-176, 229-259`.
**Apply to:** all replay outcomes and their presentation.

Keep safe cutoff replay construction, remove stale selected output on failure, use exact fixed error copy, and preserve fallback/unavailable labels with affected data. Style changes do not alter read-only behavior, scorecard values, or proxy semantics.

## No Analog Found

None for the four mapped files. There is no standalone card component or dashboard stylesheet; use the existing Streamlit page's native layout/CSS integration points.

## Metadata

**Analog search scope:** current app, plot helper, and their focused tests; phase UI contract/context.
**Files scanned:** 4 tracked source/test files.
**Tracked-source gate:** all four paths verified with `git ls-files --error-unmatch`.
**Pattern extraction date:** 2026-11-14.
