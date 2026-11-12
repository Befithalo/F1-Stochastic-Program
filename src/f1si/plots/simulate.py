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
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
from matplotlib.figure import Figure
from numpy.typing import NDArray

from f1si.plots.stints import EDGE_COLOR

_SLUG = re.compile(r"^[a-z0-9-]+$")
_DRIVER = re.compile(r"^[A-Z]{3}$")
_BAR_COLOR: Final = "#4c78a8"


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


def build_sim_figure(data: SimPlotData) -> Figure:
    """Draw one bar per finishing position (Figure API, no pyplot)."""
    fig = Figure(figsize=(9, 5), layout="constrained")
    ax = fig.subplots()
    places = np.arange(1, len(data.probabilities) + 1)
    ax.bar(places, data.probabilities, edgecolor=EDGE_COLOR, color=_BAR_COLOR)
    ax.axvline(data.mean, color=EDGE_COLOR, linestyle="--", linewidth=1.2, label="mean")
    ax.set_xticks(places)
    ax.set_xlabel("Finishing position", fontsize=9)
    ax.set_ylabel("Share of simulated races", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=8)
    fig.suptitle(data.title)
    fig.supxlabel(data.caption, fontsize=6, wrap=True)
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
    if not isinstance(slug, str) or not _SLUG.match(slug):
        raise ValueError(f"Unsafe race slug for a file name: {slug!r}")
    if not isinstance(driver, str) or not _DRIVER.match(driver):
        raise ValueError(f"Unsafe driver code for a file name: {driver!r}")
    if isinstance(lap, bool) or not isinstance(lap, int) or lap < 0:
        raise ValueError(f"Unsafe lap for a file name: {lap!r}")
    return f"sim-{slug}-{driver}-lap{lap}.png"
