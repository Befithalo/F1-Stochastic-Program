# Phase 6 UI Follow-up: Pattern Map

**Mapped:** 2026-11-14
**Files analyzed:** 4
**Analogs found:** 4 / 4 (each target is an existing implementation or its acceptance test)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/f1si/app.py` | component (Streamlit page) | request-response | `src/f1si/app.py` | exact |
| `src/f1si/plots/simulate.py` | utility (plot preparation/renderer) | transform | `src/f1si/plots/simulate.py` | exact |
| `tests/app/test_app.py` | test | request-response | `tests/app/test_app.py` | exact |
| `tests/plots/test_simulate_plot.py` | test | transform | `tests/plots/test_simulate_plot.py` | exact |

All four analog paths are git-tracked (`git ls-files` returned each path). Scope is limited to these UI follow-up files; README, backtest, and other modules are out of scope.

## Pattern Assignments

### `src/f1si/app.py` (Streamlit page, request-response)

**Analog:** `src/f1si/app.py` (same page; the UI review calls out refinements to its existing integration points).

**Imports and page boundaries** (lines 11–20):

```python
import numpy as np
import pandas as pd
import streamlit as st

import f1si.backtest.walk_forward as walk_forward
from f1si import cli, paths
from f1si.data import asof
from f1si.plots.simulate import build_sim_figure, prepare_sim_plot_data
```

The page should continue to consume the shared cutoff-safe replay path. Preserve the no-results-door boundary: do not import `f1si.data.results` or display final results in this view.

**Failure handling** (lines 28–31, 86–92, 445–466):

```python
ERROR_COPY = (
    "Replay could not be built for this selection. Check the local cache and eligible cutoffs, "
    "then retry or choose another race."
)

def _safe_replay_result(builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return {"status": "ready", "value": builder()}
    except Exception as err:
        return {"status": "error", "value": None, "reason": str(err)}
```

Keep the helper's stale-output behavior (`value: None` on error), but render the exact approved `ERROR_COPY` on both replay error paths. Never put the captured `reason` or raw exception text into visible UI. In particular, replace the current raw interpolations at lines 461–466 with the shared safe copy.

**Ranked action rendering** (lines 78–84, 355–363):

```python
def _annotate_strategy_options(columns, rows, fallback):
    label = "UNCALIBRATED" if fallback else "Cutoff inputs"
    return (*columns, "Basis"), tuple((*row, label) for row in rows)

strategy_table = pd.DataFrame(rows, columns=columns)
st.dataframe(strategy_table, hide_index=True, width="stretch", height="content")
```

The current accent callout is a standalone heading and does not identify the first row. Attach the accent/marker to the actual row at index 0 while retaining the `Basis` field adjacent to each action; preserve the fallback annotation behavior and table data. The research contract specifies accent `#D90429` and allows removing/demoting the duplicate standalone banner.

**Existing layout/control integration points** (lines 274–304, 385–440):

```python
.stApp { background: #F5F7FA; color: #17212B; }
[data-testid="stVerticalBlockBorderWrapper"] { background: #E9EEF3; }
@media (max-width: 760px) {
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 16px; }
}
```

Use the UI-SPEC scale: body 16px, labels 14px, headings 20px, display 28px; spacing tokens are 4/8/16/24/32/48/64px. Set actionable controls to at least 44px where native Streamlit widgets permit. Render visible `Mean-focused` and `Tail-risk-focused` slider endpoint labels and keep its numeric value visible before submission. Retain mobile wrapping, table horizontal scrolling, and long-text wrapping; source-level CSS checks do not prove actual widget geometry or responsive behavior.

### `src/f1si/plots/simulate.py` (plot utility, transform)

**Analog:** `src/f1si/plots/simulate.py` (the existing pure-data preparation and Figure API renderer).

**Imports and plain-data boundary** (lines 18–27, 34–47):

```python
from dataclasses import dataclass
from typing import Final

import numpy as np
from matplotlib.figure import Figure
from numpy.typing import NDArray

@dataclass(frozen=True, eq=False)
class SimPlotData:
    probabilities: NDArray[np.float64]
    mean: float
    median: float
    interval: tuple[float, float]
```

Keep preparation a pure transform of the selected cutoff's finish draws and scalar metadata. Do not introduce `pyplot`; the module documents direct `Figure` API use.

**Renderer** (lines 103–117):

```python
def build_sim_figure(data: SimPlotData) -> Figure:
    fig = Figure(figsize=(9, 5), layout="constrained")
    ax = fig.subplots()
    places = np.arange(1, len(data.probabilities) + 1)
    ax.bar(places, data.probabilities, edgecolor=EDGE_COLOR, color=_BAR_COLOR)
    ax.axvline(data.mean, color=EDGE_COLOR, linestyle="--", linewidth=1.2, label="mean")
    ax.set_xlabel("Finishing position", fontsize=9)
    ax.set_ylabel("Share of simulated races", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=8)
    fig.supxlabel(data.caption, fontsize=6, wrap=True)
    return fig
```

For the follow-up, keep all bars light-neutral and use accent `#D90429` only for a labeled finishing-position summary statistic derived from these same selected-cutoff draws. A selected distribution mean or median is appropriate; label it as finishing position (never as lap coordinate). Raise typography to the contract scale and move long simulation caveats into normal-size Streamlit body copy if they cannot remain legible in the figure. Preserve useful caveats and selected-cutoff versus hindsight distinction.

### `tests/app/test_app.py` (test, request-response)

**Analog:** `tests/app/test_app.py` (the current Streamlit acceptance suite).

**Imports and AppTest pattern** (lines 5–16, 124–129):

```python
import ast
from importlib import import_module
from pathlib import Path

import pytest

app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
result = app_test.from_file(APP_PATH).run()
assert not result.exception
```

Use `AppTest.from_file(APP_PATH).run()` for UI-level error and row-marker coverage. Existing tests check empty state (131–145), helper stale-output behavior (155–161), fallback row labels (163–171), and source hooks for responsive CSS (173–178). Extend with failure injection that asserts the exact visible copy, excludes raw exception text, and confirms stale result components are absent. Assert that the marker is attached to the first table row/action, not merely present in page text; preserve fallback basis adjacency.

### `tests/plots/test_simulate_plot.py` (test, transform)

**Analog:** `tests/plots/test_simulate_plot.py` (the current plot data and renderer tests).

**Matplotlib Figure pattern** (lines 7–17, 54–60):

```python
from matplotlib.figure import Figure

def test_figure_has_one_bar_per_position() -> None:
    fig = build_sim_figure(_data())
    assert isinstance(fig, Figure)
    ax = fig.axes[0]
    assert len(ax.patches) == 20
    assert ax.get_ylabel() == "Share of simulated races"
    assert any(ln.get_linestyle() == "--" for ln in ax.get_lines())
```

Extend this inspection style to assert neutral bar face colors, accent summary artist/color and legend semantics, and that its plotted value equals the selected cutoff's supplied draws. Check axis/legend labels and configured typography. Existing pure-data test (39–51) validates mean, median, empirical interval, and hindsight/source caveats; preserve these data semantics. The no-pyplot import guard at lines 85–89 remains applicable.

## Shared Patterns

### Read-only replay and error UI

**Source:** `src/f1si/app.py:86–92, 445–466`
**Apply to:** replay submission and failure rendering.

Keep computation inside the safe replay wrapper, clear stale output on error, and show the approved generic recovery copy without exception details. Preserve cutoff-local replay construction and the import boundary established by `tests/app/test_app.py:29–40`.

### Figure and selected-cutoff data

**Source:** `src/f1si/plots/simulate.py:49–100, 103–117`
**Apply to:** chart data and rendering.

Derive chart data and highlighted summary from the same selected-cutoff finish-position array; the plot utility remains independent from snapshots and uses `matplotlib.figure.Figure` directly.

### Visual contract and manual inspection

**Source:** `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-UI-SPEC.md`; follow-up constraints summarized in `06-RESEARCH.md:455–477`
**Apply to:** app and embedded chart.

Accent: `#D90429`; page/panel/text: `#F5F7FA`, `#E9EEF3`, `#17212B`; all chart bars neutral. Verify desktop and narrow widths in a live browser, including default/populated, error, empty/partial, and long-text states, changed controls, table scrolling, wrapping, spacing, and actual control height. Record screenshots or concise observations as plan evidence; AppTest/source assertions alone cannot verify viewport layout.

## No Analog Found

None. The targets are existing files with direct patterns to extend.

## Metadata

**Analog search scope:** requested app, chart, and corresponding tests only.
**Files scanned:** 4 requested tracked files.
**Pattern extraction date:** 2026-11-14.
