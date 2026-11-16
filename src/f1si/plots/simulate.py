"""Finishing-position picture: how often one driver finishes P1, P2, ... in the simulation (D-16).

What the picture shows, in plain words. Each bar is the share of simulated races in which the
driver finished in that position: with `n` simulated races and `c_k` of them ending in position
`k`, the bar height is `c_k / n`, so the bars sum to 1. The dashed line marks the mean finishing
position. The 90% interval is the 5% and 95% empirical quantiles of the simulated finishes. The
caption states where the safety-car rate came from and, for a whole-race fit, that this is a
hindsight simulation. The bars are Monte Carlo estimates, so they carry sampling noise of about
`sqrt(p (1 - p) / n)` each.

The data preparation (`prepare_sim_plot_data`) is a pure function of plain arrays and scalars; it
takes no snapshot. The renderer uses the matplotlib `Figure` API directly and never `pyplot`
(DEC-050).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from numpy.typing import NDArray

_SLUG = re.compile(r"[a-z0-9-]+")
_DRIVER = re.compile(r"[A-Z]{3}")
_FIGURE_COLOR: Final = "#1A222C"
_AXES_COLOR: Final = "#242E39"
_TEXT_COLOR: Final = "#F2F5F8"
_SUPPORTING_COLOR: Final = "#B7C2CE"
_GRID_COLOR: Final = "#536171"
_BAR_COLOR: Final = "#AAB5C0"
_SUMMARY_COLOR: Final = "#D90429"

_UI_ASPHALT: Final = "#1C1F23"
_UI_PITWALL: Final = "#24282D"
_UI_RULE: Final = "#3A4047"
_UI_CHALK: Final = "#ECEAE4"
_UI_FOG: Final = "#9BA1A8"
_UI_RECOMMENDATION: Final = "#B69BFF"


@dataclass(frozen=True, eq=False)
class SimPlotData:
    """Everything the renderer needs, as plain data."""

    title: str
    slug: str
    driver: str
    lap: int
    probabilities: NDArray[np.float64]
    mean: float
    median: float
    interval: tuple[float, float]
    caption: str


@dataclass(frozen=True)
class QuantileDotplotData:
    """Compact per-option quantiles and display metadata for the selected-cutoff dotplot."""

    labels: tuple[str, ...]
    quantiles: tuple[tuple[int, ...], ...]
    y_positions: tuple[tuple[float, ...], ...]
    row_centers: tuple[float, ...]
    mean_finish: float
    n_cars: int
    simulation_count: int
    caption: str


@dataclass(frozen=True)
class FanChartData:
    """Compact percentile bands from forward simulated ranks, with no raw simulation matrix."""

    laps: tuple[int, ...]
    p10: tuple[float, ...]
    p25: tuple[float, ...]
    p40: tuple[float, ...]
    p50: tuple[float, ...]
    p60: tuple[float, ...]
    p75: tuple[float, ...]
    p90: tuple[float, ...]
    n_cars: int
    simulation_count: int
    caption: str


def prepare_quantile_dotplot_data(
    labels: tuple[str, ...],
    quantiles: tuple[tuple[int, ...], ...],
    *,
    mean_finish: float,
    n_cars: int,
    simulation_count: int,
) -> QuantileDotplotData:
    """Validate 100 fixed midpoint-quantile positions per strategy and add deterministic stacks."""
    labels = tuple(labels)
    quantiles = tuple(tuple(values) for values in quantiles)
    if not labels or len(labels) != len(quantiles):
        raise ValueError("labels and quantile rows must be non-empty and have matching lengths")
    if isinstance(n_cars, bool) or not isinstance(n_cars, int) or n_cars < 1:
        raise ValueError("n_cars must be a positive integer")
    if (
        isinstance(simulation_count, bool)
        or not isinstance(simulation_count, int)
        or simulation_count < 1
    ):
        raise ValueError("simulation_count must be a positive integer")
    if not np.isfinite(mean_finish) or not 1 <= float(mean_finish) <= n_cars:
        raise ValueError("mean_finish must be finite and lie within the finishing positions")
    for label, row in zip(labels, quantiles, strict=True):
        if not isinstance(label, str) or not label:
            raise ValueError("strategy labels must be non-empty strings")
        if len(row) != 100:
            raise ValueError("each strategy option must provide exactly 100 quantile positions")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, np.integer)) for value in row
        ):
            raise ValueError("quantile positions must be integers")
        if any(value < 1 or value > n_cars for value in row):
            raise ValueError(f"quantile positions must lie in 1..{n_cars}")
        if tuple(sorted(row)) != row:
            raise ValueError("quantile positions must be ordered from low to high")

    stack_step = 0.035
    max_stack = max(Counter(row).most_common(1)[0][1] for row in quantiles)
    row_gap = max(1.0, (max_stack - 1) * stack_step + 0.32)
    row_centers = tuple(float(index) * row_gap for index in range(len(labels)))
    y_positions: list[tuple[float, ...]] = []
    for center, row in zip(row_centers, quantiles, strict=True):
        counts = Counter(row)
        seen: Counter[int] = Counter()
        positions: list[float] = []
        for value in row:
            count = counts[value]
            offset = seen[value]
            seen[value] += 1
            positions.append(center + (offset - (count - 1) / 2) * stack_step)
        y_positions.append(tuple(positions))

    caption = (
        f"Each dot shows one of the {simulation_count:,} simulated finishes, spaced by percentile."
    )
    return QuantileDotplotData(
        labels=labels,
        quantiles=quantiles,
        y_positions=tuple(y_positions),
        row_centers=row_centers,
        mean_finish=float(mean_finish),
        n_cars=n_cars,
        simulation_count=simulation_count,
        caption=caption,
    )


def build_quantile_dotplot(
    data: QuantileDotplotData, *, include_caption: bool = True, compact: bool = False
) -> Figure:
    """Render a deterministic 100-dot row per ranked option and a neutral mean marker."""
    row_count = len(data.labels)
    row_gap = 1.0 if row_count < 2 else data.row_centers[1] - data.row_centers[0]
    height = max(4.0, 1.15 + row_gap * row_count * 0.56)
    fig = Figure(figsize=(4 if compact else 9, height), layout="constrained")
    fig.set_facecolor(_UI_ASPHALT)
    ax = fig.subplots()
    ax.set_facecolor(_UI_PITWALL)

    shown_labels = tuple(
        f"Top: {label}" if index == 0 else label for index, label in enumerate(data.labels)
    )
    for index, (x_values, y_values) in enumerate(
        zip(data.quantiles, data.y_positions, strict=True)
    ):
        ax.scatter(
            x_values,
            y_values,
            s=21,
            color=_UI_RECOMMENDATION if index == 0 else _UI_FOG,
            edgecolors=_UI_ASPHALT,
            linewidths=0.35,
            label="Recommended strategy" if index == 0 else None,
            zorder=3,
        )
    ax.axvline(
        data.mean_finish,
        color=_UI_FOG,
        linestyle="--",
        linewidth=1.6,
        label="Mean finish at selected cutoff",
        zorder=2,
    )
    ax.set_xlim(0.5, data.n_cars + 0.5)
    if compact:
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    else:
        ax.set_xticks(np.arange(1, data.n_cars + 1))
    ax.set_yticks(data.row_centers, shown_labels)
    ax.invert_yaxis()
    ax.set_title("Finish quantiles by strategy", color=_UI_CHALK, fontsize=16, pad=14)
    ax.set_xlabel("Finishing position", color=_UI_CHALK, fontsize=12)
    ax.set_ylabel("Ranked strategy", color=_UI_CHALK, fontsize=12)
    ax.tick_params(labelsize=10.5, colors=_UI_FOG, color=_UI_RULE)
    for tick in ax.get_xticklabels():
        tick.set_fontfamily("DejaVu Sans Mono")
    for index, tick in enumerate(ax.get_yticklabels()):
        tick.set_color(_UI_RECOMMENDATION if index == 0 else _UI_CHALK)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=_UI_RULE, linewidth=0.7, alpha=0.8)
    ax.grid(axis="y", visible=False)
    for spine in ax.spines.values():
        spine.set_color(_UI_RULE)
        spine.set_linewidth(0.8)
    legend = ax.legend(fontsize=8 if compact else 10, frameon=False, loc="best")
    if legend is not None:
        for label in legend.get_texts():
            label.set_color(_UI_CHALK)
    if include_caption:
        fig.text(
            0.01,
            0.005,
            data.caption,
            fontsize=10.5,
            color=_UI_FOG,
            wrap=True,
            va="bottom",
            fontfamily="DejaVu Sans",
        )
    return fig


def prepare_fan_chart_data(
    position_history: NDArray[np.int64], *, first_lap: int, n_cars: int
) -> FanChartData:
    """Reduce selected-driver future-rank history to compact nested percentile bands."""
    history = np.asarray(position_history)
    if history.ndim != 2 or history.shape[0] < 1 or history.shape[1] < 1:
        raise ValueError("position_history must be a non-empty race-by-lap matrix")
    if not np.issubdtype(history.dtype, np.integer):
        raise ValueError("position_history values must be integer finishing ranks")
    if isinstance(first_lap, bool) or not isinstance(first_lap, int) or first_lap < 1:
        raise ValueError("first_lap must be a positive integer")
    if isinstance(n_cars, bool) or not isinstance(n_cars, int) or n_cars < 1:
        raise ValueError("n_cars must be a positive integer")
    if int(history.min()) < 1 or int(history.max()) > n_cars:
        raise ValueError(f"position_history values must lie in 1..{n_cars}")
    levels = np.quantile(history, [0.10, 0.25, 0.40, 0.50, 0.60, 0.75, 0.90], axis=0)
    arrays = [tuple(float(value) for value in level) for level in levels]
    laps = tuple(range(first_lap, first_lap + history.shape[1]))
    count = int(history.shape[0])
    caption = (
        f"Projected ranks from {count:,} simulated races; bands show the 10th to 90th, "
        "25th to 75th, and 40th to 60th percentile ranges."
    )
    return FanChartData(
        laps=laps,
        p10=arrays[0],
        p25=arrays[1],
        p40=arrays[2],
        p50=arrays[3],
        p60=arrays[4],
        p75=arrays[5],
        p90=arrays[6],
        n_cars=n_cars,
        simulation_count=count,
        caption=caption,
    )


def build_fan_chart(
    data: FanChartData, *, include_caption: bool = True, compact: bool = False
) -> Figure:
    """Render nested uncertainty bands for the recommended plan's simulated future ranks."""
    fig = Figure(figsize=(4, 4.8) if compact else (9, 4.4), layout="constrained")
    fig.set_facecolor(_UI_ASPHALT)
    ax = fig.subplots()
    ax.set_facecolor(_UI_PITWALL)
    laps = np.asarray(data.laps)
    ax.fill_between(
        laps,
        data.p10,
        data.p90,
        color=_UI_RECOMMENDATION,
        alpha=0.13,
        linewidth=0,
        label="10th to 90th percentile band",
    )
    ax.fill_between(
        laps,
        data.p25,
        data.p75,
        color=_UI_RECOMMENDATION,
        alpha=0.24,
        linewidth=0,
        label="25th to 75th percentile band",
    )
    ax.fill_between(
        laps,
        data.p40,
        data.p60,
        color=_UI_RECOMMENDATION,
        alpha=0.36,
        linewidth=0,
        label="40th to 60th percentile band",
    )
    ax.plot(
        laps,
        data.p50,
        color=_UI_RECOMMENDATION,
        linewidth=1.7,
        label="Median position",
    )
    ax.set_title("Projected finishing position by lap", color=_UI_CHALK, fontsize=16, pad=14)
    ax.set_xlabel("Lap", color=_UI_CHALK, fontsize=12)
    ax.set_ylabel("Finishing position", color=_UI_CHALK, fontsize=12)
    ax.set_ylim(data.n_cars + 0.5, 0.5)
    tick_count = 5 if compact else 8
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=tick_count))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=tick_count))
    ax.tick_params(labelsize=10.5, colors=_UI_FOG, color=_UI_RULE)
    for axis in (ax.xaxis, ax.yaxis):
        for tick in axis.get_ticklabels():
            tick.set_fontfamily("DejaVu Sans Mono")
    ax.set_axisbelow(True)
    ax.grid(color=_UI_RULE, linewidth=0.7, alpha=0.8)
    for spine in ax.spines.values():
        spine.set_color(_UI_RULE)
        spine.set_linewidth(0.8)
    legend = ax.legend(fontsize=9.5, frameon=False, loc="best")
    if legend is not None:
        for label in legend.get_texts():
            label.set_color(_UI_CHALK)
    if include_caption:
        fig.text(
            0.01,
            0.005,
            data.caption,
            fontsize=10.5,
            color=_UI_FOG,
            wrap=True,
            va="bottom",
            fontfamily="DejaVu Sans",
        )
    return fig


def prepare_sim_plot_data(
    positions: NDArray[np.int64],
    *,
    slug: str,
    driver: str,
    lap: int,
    n_races: int,
    sc_share: float,
    sc_source: str,
    hindsight: bool,
    n_cars: int | None = None,
) -> SimPlotData:
    """Probabilities of each finishing position and summary numbers for one driver (pure).

    Args:
        positions: (n_races,) finishing positions of the driver, values in 1..n_cars.
        n_cars: number of positions to show (default: the largest position seen).
    """
    pos = np.asarray(positions, dtype=np.int64)
    if pos.ndim != 1 or pos.size == 0:
        raise ValueError(f"positions must be a non-empty 1-D array, got shape {pos.shape}")
    cars = int(pos.max()) if n_cars is None else int(n_cars)
    if int(pos.min()) < 1 or int(pos.max()) > cars:
        raise ValueError(f"positions must lie in 1..{cars}")
    counts = np.bincount(pos, minlength=cars + 1)[1 : cars + 1].astype(np.float64)
    probabilities = counts / float(pos.size)
    low, high = (float(q) for q in np.quantile(pos, [0.05, 0.95]))
    where = f"from lap {lap}" + (", hindsight simulation" if hindsight else "")
    title = f"{driver}: simulated finishing position ({slug}, {where})"
    caption = (
        f"Share of {n_races} simulated races ending in each position; dashed line = mean "
        f"{float(pos.mean()):.2f}, median {float(np.median(pos)):.1f}, 90% interval "
        f"{low:.0f} to {high:.0f}. Safety car in {sc_share * 100:.1f}% of simulated races "
        f"(rate source: {sc_source}). "
        + (
            "This is a hindsight simulation: the pace fit uses the whole race. "
            if hindsight
            else ""
        )
        + "Rivals follow the free-track best plan; no retirements are simulated."
    )
    return SimPlotData(
        title=title,
        slug=slug,
        driver=driver,
        lap=lap,
        probabilities=probabilities,
        mean=float(pos.mean()),
        median=float(np.median(pos)),
        interval=(low, high),
        caption=caption,
    )


def build_sim_figure(data: SimPlotData, *, include_caption: bool = True) -> Figure:
    """Draw a finishing-position distribution and its cutoff-local mean summary."""
    fig = Figure(figsize=(9, 5), layout="constrained")
    fig.set_facecolor(_FIGURE_COLOR)
    ax = fig.subplots()
    ax.set_facecolor(_AXES_COLOR)
    places = np.arange(1, len(data.probabilities) + 1)
    ax.bar(places, data.probabilities, edgecolor=_AXES_COLOR, color=_BAR_COLOR)
    ax.axvline(
        data.mean,
        color=_SUMMARY_COLOR,
        linestyle="--",
        linewidth=2.0,
        label="Mean finish at selected cutoff",
    )
    ax.set_xticks(places)
    ax.set_xlabel("Finishing position", fontsize=12, color=_TEXT_COLOR)
    ax.set_ylabel("Share of simulated races", fontsize=12, color=_TEXT_COLOR)
    ax.tick_params(labelsize=10.5, colors=_SUPPORTING_COLOR, color=_GRID_COLOR)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=_GRID_COLOR, linewidth=0.8, alpha=0.7)
    ax.grid(axis="x", visible=False)
    for spine in ax.spines.values():
        spine.set_color(_GRID_COLOR)
        spine.set_linewidth(0.8)
    legend = ax.legend(fontsize=10.5, frameon=True)
    legend.get_frame().set_facecolor(_FIGURE_COLOR)
    legend.get_frame().set_edgecolor(_GRID_COLOR)
    legend.get_frame().set_linewidth(0.8)
    legend.get_frame().set_alpha(1.0)
    for label in legend.get_texts():
        label.set_color(_TEXT_COLOR)
    fig.suptitle(data.title, fontsize=15, fontweight="semibold", color=_TEXT_COLOR)
    if include_caption:
        fig.text(
            0.01,
            0.01,
            data.caption,
            fontsize=12,
            color=_SUPPORTING_COLOR,
            wrap=True,
            va="bottom",
        )
    return fig


def render_sim_plot(data: SimPlotData, out_path: Path) -> Path:
    """Write the plot as a PNG (creating parent folders) and return the path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    build_sim_figure(data).savefig(out_path, dpi=120)
    return out_path


def sim_file_name(slug: str, driver: str, lap: int) -> str:
    """File name from a catalog slug, a driver code and a lap (never a raw user path).

    Raises:
        ValueError: if the slug, driver or lap has unexpected characters or values.
    """
    if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
        raise ValueError(f"Unsafe race slug for a file name: {slug!r}")
    if not isinstance(driver, str) or not _DRIVER.fullmatch(driver):
        raise ValueError(f"Unsafe driver code for a file name: {driver!r}")
    if isinstance(lap, bool) or not isinstance(lap, int) or lap < 0:
        raise ValueError(f"Unsafe lap for a file name: {lap!r}")
    return f"sim-{slug}-{driver}-lap{lap}.png"
