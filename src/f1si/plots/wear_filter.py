"""Wear-filter picture: the as-of wear-rate estimate and its 95% band against race lap (PAC-03).

What the picture shows, in plain words. Each point is the estimate the Kalman filter would have
shown at that race lap, using only laps up to it (the command re-runs the fit and the filter at
every cutoff). The line is the posterior mean of the wear rate (seconds per lap), the shaded band
is its 95% interval, which includes the fuel-effect uncertainty. Within a stint the band should
narrow as laps accumulate. Hollow markers are laps the filter skipped (pit laps, safety car, outlier
gate). The dashed horizontal line per compound is the Phase 2 whole-race fit, labelled hindsight
because it uses laps after the ones shown.

`prepare_wear_filter_data` takes already computed `CutoffRow` values and reads no race data. The
renderer uses the matplotlib `Figure` API directly and never `pyplot` (DEC-050).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from f1si.pace.kalman import CutoffRow
from f1si.plots.stints import COMPOUND_COLORS, EDGE_COLOR, UNKNOWN_COLOR

_SLUG = re.compile(r"^[a-z0-9-]+$")
_DRIVER = re.compile(r"^[A-Z]{3}$")
_HINDSIGHT: Final = "hindsight (Phase 2 fit, uses the whole race window)"
_CAPTION: Final = (
    "Each point uses only laps up to its own lap. The first stint uses documented priors "
    "(prior only), the band is the 95% interval and includes the fuel-effect uncertainty."
)


@dataclass(frozen=True, eq=False)
class WearFilterPlotData:
    """Everything the renderer needs, as plain data."""

    title: str
    slug: str
    driver: str
    laps: tuple[int, ...]
    stint_ids: tuple[int, ...]
    compounds: tuple[str, ...]
    rate: tuple[float, ...]
    lo: tuple[float, ...]
    hi: tuple[float, ...]
    used: tuple[bool, ...]
    stint_starts: tuple[int, ...]
    hindsight: Mapping[str, float]
    caption: str


def prepare_wear_filter_data(
    rows: Sequence[CutoffRow],
    *,
    slug: str,
    driver: str,
    hindsight: Mapping[str, float],
    is_full_race: bool,
    last_lap: int,
) -> WearFilterPlotData:
    """Parallel tuples sorted by race lap (pure; reads only its arguments)."""
    ordered = sorted(rows, key=lambda r: r.row.race_lap)
    starts: list[int] = []
    seen: set[int] = set()
    for r in ordered:
        if r.stint not in seen:
            seen.add(r.stint)
            starts.append(r.row.race_lap)
    where = "full race" if is_full_race else f"as of lap {last_lap}"
    return WearFilterPlotData(
        title=f"{slug} {driver}: tyre wear rate filter ({where})",
        slug=slug,
        driver=driver,
        laps=tuple(r.row.race_lap for r in ordered),
        stint_ids=tuple(r.stint for r in ordered),
        compounds=tuple(r.compound for r in ordered),
        rate=tuple(r.row.rate_mean for r in ordered),
        lo=tuple(r.row.rate_lo for r in ordered),
        hi=tuple(r.row.rate_hi for r in ordered),
        used=tuple(r.row.used for r in ordered),
        stint_starts=tuple(starts),
        hindsight=dict(hindsight),
        caption=_CAPTION,
    )


def build_wear_filter_figure(data: WearFilterPlotData) -> Figure:
    """Draw the estimate, its band, stint boundaries and the hindsight lines (no pyplot)."""
    fig = Figure(figsize=(10.0, 4.6), layout="constrained")
    ax = fig.subplots()
    ax.set_xlabel("Race lap", fontsize=8)
    ax.set_ylabel("Wear rate (s per lap of tyre age)", fontsize=8)
    ax.tick_params(labelsize=7)
    n = len(data.laps)
    handles: list[Artist] = []
    stints = list(dict.fromkeys(data.stint_ids))
    first_lap_of: dict[int, int] = {}
    span_of: dict[str, list[tuple[int, int]]] = {}
    for sid in stints:
        idx = [i for i in range(n) if data.stint_ids[i] == sid]
        comp = data.compounds[idx[0]]
        colour = COMPOUND_COLORS.get(comp, UNKNOWN_COLOR)
        x = [data.laps[i] for i in idx]
        first_lap_of[sid] = x[0]
        span_of.setdefault(comp, []).append((x[0], x[-1]))
        ax.fill_between(
            x,
            [data.lo[i] for i in idx],
            [data.hi[i] for i in idx],
            color=colour,
            alpha=0.35,
            zorder=2,
        )
        for edge in ("lo", "hi"):
            ax.plot(
                x,
                [getattr(data, edge)[i] for i in idx],
                color=EDGE_COLOR,
                linewidth=0.7,
                linestyle="--",
                zorder=2,
            )
        y = [data.rate[i] for i in idx]
        ax.plot(x, y, color=EDGE_COLOR, linewidth=2.4, zorder=3)
        ax.plot(x, y, color=colour, linewidth=1.4, zorder=4)
        handles.append(Patch(facecolor=colour, edgecolor=EDGE_COLOR, label=f"{comp} stint {sid}"))
        skipped = [i for i in idx if not data.used[i]]
        used = [i for i in idx if data.used[i]]
        ax.scatter(
            [data.laps[i] for i in used],
            [data.rate[i] for i in used],
            s=10,
            color=colour,
            edgecolors=EDGE_COLOR,
            linewidths=0.4,
            zorder=5,
        )
        ax.scatter(
            [data.laps[i] for i in skipped],
            [data.rate[i] for i in skipped],
            s=12,
            facecolors="none",
            edgecolors=EDGE_COLOR,
            linewidths=0.6,
            zorder=5,
        )
    for start in data.stint_starts[1:]:
        ax.axvline(start, color=EDGE_COLOR, linestyle=":", linewidth=0.8, zorder=1)
    labelled = False
    for comp, value in data.hindsight.items():
        if not math.isfinite(value) or comp not in span_of:
            continue
        lo_lap = min(a for a, _ in span_of[comp])
        hi_lap = max(b for _, b in span_of[comp])
        ax.hlines(
            value,
            lo_lap,
            hi_lap,
            colors=EDGE_COLOR,
            linestyles="--",
            linewidth=1.2,
            zorder=6,
        )
        if not labelled:
            handles.append(
                Line2D([], [], color=EDGE_COLOR, linestyle="--", linewidth=1.2, label=_HINDSIGHT)
            )
        labelled = True
    if n:
        ax.legend(handles=handles, fontsize=6, loc="upper right")
    fig.suptitle(data.title)
    fig.supxlabel(data.caption, fontsize=6, wrap=True)
    return fig


def render_wear_filter_plot(data: WearFilterPlotData, out_path: Path) -> Path:
    """Write the plot as a PNG (creating parent folders) and return the path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    build_wear_filter_figure(data).savefig(out_path, dpi=120)
    return out_path


def wear_filter_file_name(slug: str, driver: str) -> str:
    """File name from a catalog slug and a driver code (never a raw user path).

    Raises:
        ValueError: if the slug or the driver code has unexpected characters.
    """
    if not _SLUG.match(slug):
        raise ValueError(f"Unsafe race slug for a file name: {slug!r}")
    if not _DRIVER.match(driver):
        raise ValueError(f"Unsafe driver code for a file name: {driver!r}")
    return f"wear-filter-{slug}-{driver}.png"
