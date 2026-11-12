"""Tyre wear picture: fuel-corrected clean lap time against tyre age, one panel per compound (D-15).

What the picture shows, in plain words. Each point is a clean lap with the fuel effect and the
driver's pace offset taken out, so what is left is tyre wear against tyre age. The line is the
field-average intercept plus wear * age. The shaded band is the 95% interval of the slope,
`+/- 1.96 * SE * age` around the line; it is not a prediction band for single laps, so most points
fall outside it. Points include laps that passed the clean-lap rule but that the fit later trimmed
as outliers (the caption states how many). Compound pace offsets are not modeled (D-19): each
compound line is anchored at the same field-average intercept.

The data preparation (`prepare_wear_plot_data`) is a pure function of a `RaceSnapshot` and a
fitted `LinearPaceFit`; it is registered as a consumer in the future-scramble test. The renderer
uses the matplotlib `Figure` API directly and never `pyplot` (DEC-050).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from f1si.data.asof import RaceSnapshot
from f1si.laps import fade_reason
from f1si.pace.linear import CI_Z, LinearPaceFit
from f1si.plots.stints import COMPOUND_COLORS, EDGE_COLOR, UNKNOWN_COLOR

_SLUG = re.compile(r"^[a-z0-9-]+$")
_POINT_COLUMNS: Final = ("driver", "compound", "tire_age", "y_corrected")
_NO_DATA: Final = "not enough data"


@dataclass(frozen=True, eq=False)
class WearPlotData:
    """Everything the renderer needs, as plain data (no snapshot, no fit)."""

    title: str
    slug: str
    panels: tuple[str, ...]
    panel_titles: Mapping[str, str]
    points: pd.DataFrame
    lines: Mapping[str, tuple[float, float, float]]
    caption: str


def _empty_points() -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series([], dtype="object") for name in _POINT_COLUMNS})


def prepare_wear_plot_data(snapshot: RaceSnapshot, fit: LinearPaceFit) -> WearPlotData:
    """Corrected clean laps, fitted lines and slope bands (pure; reads only its arguments)."""
    race = snapshot.race
    if isinstance(snapshot.at.lap, int):
        title = f"{race.event_name} {race.season}: tyre wear (as of lap {snapshot.at.lap})"
    else:
        title = f"{race.event_name} {race.season}: tyre wear (full race)"
    report = fit.report
    if not fit.is_identified or report.fuel_s_per_lap is None:
        caption = f"Tyre wear is not identified yet: {report.message}."
        return WearPlotData(title, race.slug, (), {}, _empty_points(), {}, caption)

    fuel = report.fuel_s_per_lap
    fitted = fit.fitted_compounds
    panels = (*fitted, *report.not_enough_data)
    panel_titles: dict[str, str] = {}
    lines: dict[str, tuple[float, float, float]] = {}
    mean_intercept = float(np.mean(list(report.driver_offsets.values())))
    for c in report.compounds:
        panel_titles[c.compound] = f"{c.compound}  {c.wear_s_per_lap:+.3f} s/lap"
        lines[c.compound] = (mean_intercept, c.wear_s_per_lap, CI_Z * c.se)
    for name in report.not_enough_data:
        panel_titles[name] = f"{name}  {_NO_DATA}"

    code_of = {
        int(n): str(c)
        for n, c in zip(
            snapshot.entries["driver_number"], snapshot.entries["driver_code"], strict=True
        )
    }
    laps = snapshot.laps
    records: list[dict[str, object]] = []
    for number, lap_no, time_s, age, comp, pit_in, pit_out, status in zip(
        laps["driver_number"].astype(int).to_numpy(),
        laps["lap_number"].astype(int).to_numpy(),
        laps["lap_time_s"].astype("Float64").to_numpy(dtype=np.float64, na_value=np.nan),
        laps["tyre_life"].astype("Float64").to_numpy(dtype=np.float64, na_value=np.nan),
        laps["compound"].astype("object"),
        laps["is_pit_in_lap"].fillna(False).astype(bool).to_numpy(),
        laps["is_pit_out_lap"].fillna(False).astype(bool).to_numpy(),
        laps["track_status"].astype("object"),
        strict=True,
    ):
        lap_comp = str(comp).upper() if isinstance(comp, str) else None
        offset = fit.pace_offset(int(number))
        if (
            np.isnan(time_s)
            or np.isnan(age)
            or lap_comp not in fitted
            or offset is None
            or fade_reason(int(lap_no), bool(pit_in), bool(pit_out), status) is not None
        ):
            continue
        records.append(
            {
                "driver": code_of.get(int(number), str(number)),
                "compound": lap_comp,
                "tire_age": int(age),
                "y_corrected": float(time_s) - fuel * (int(lap_no) - 1) - offset,
            }
        )
    points = pd.DataFrame(records, columns=list(_POINT_COLUMNS)) if records else _empty_points()
    caption = (
        f"Each point is a clean lap minus fuel and driver offset; line = field-average intercept "
        f"+ wear x age; band = 95% interval of the slope, not of single laps. "
        f"{report.n_trimmed} clean laps were trimmed as outliers by the fit but are still drawn. "
        "Compound pace offsets are not modeled."
    )
    return WearPlotData(title, race.slug, panels, panel_titles, points, lines, caption)


def build_wear_figure(data: WearPlotData) -> Figure:
    """Draw one panel per compound (Figure API, no pyplot)."""
    ncols = max(1, len(data.panels))
    fig = Figure(figsize=(4.2 * ncols, 3.4 + 0.4), layout="constrained")
    axes = fig.subplots(1, ncols, sharey=True, squeeze=False)
    flat = list(axes.ravel())
    cmap = matplotlib.colormaps["tab20"]
    drivers = sorted({str(d) for d in data.points["driver"]}) if len(data.points) else []
    colour_of = {d: cmap(i % 20) for i, d in enumerate(drivers)}
    marker_of = {d: "os^dv"[(i // 20) % 5] for i, d in enumerate(drivers)}
    if not data.panels:
        flat[0].text(0.5, 0.5, data.caption, ha="center", va="center", wrap=True)
        flat[0].set_axis_off()
    for name, ax in zip(data.panels, flat, strict=False):
        ax.set_title(data.panel_titles[name], fontsize=9)
        ax.tick_params(labelsize=7)
        ax.set_xlabel("Tyre age (laps)", fontsize=8)
        if name not in data.lines:
            ax.text(0.5, 0.5, _NO_DATA, ha="center", va="center", transform=ax.transAxes)
            continue
        mine = data.points[data.points["compound"] == name] if len(data.points) else data.points
        for code in drivers:
            sel = mine[mine["driver"] == code]
            if sel.empty:
                continue
            ax.scatter(
                sel["tire_age"].astype(float),
                sel["y_corrected"].astype(float),
                s=12,
                marker=marker_of[code],
                color=colour_of[code],
                edgecolors=EDGE_COLOR,
                linewidths=0.3,
                alpha=0.8,
            )
        intercept, slope, half = data.lines[name]
        top = float(mine["tire_age"].max()) if len(mine) else 1.0
        age = np.linspace(0.0, max(top, 1.0), 50)
        colour = COMPOUND_COLORS.get(name, UNKNOWN_COLOR)
        ax.fill_between(
            age,
            intercept + (slope - half) * age,
            intercept + (slope + half) * age,
            color=colour,
            alpha=0.35,
            zorder=2,
        )
        ax.plot(age, intercept + slope * age, color=EDGE_COLOR, linewidth=2.4, zorder=3)
        ax.plot(age, intercept + slope * age, color=colour, linewidth=1.4, zorder=4)
    flat[0].set_ylabel("Lap time minus fuel and driver offset (s)", fontsize=8)
    if drivers:
        handles = [
            Line2D(
                [],
                [],
                marker=marker_of[d],
                linestyle="",
                markerfacecolor=colour_of[d],
                markeredgecolor=EDGE_COLOR,
                markersize=5,
                label=d,
            )
            for d in drivers
        ]
        fig.legend(handles=handles, loc="outside right upper", fontsize=6, ncols=2)
    fig.suptitle(data.title)
    fig.supxlabel(data.caption, fontsize=6, wrap=True)
    return fig


def render_wear_plot(data: WearPlotData, out_path: Path) -> Path:
    """Write the plot as a PNG (creating parent folders) and return the path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    build_wear_figure(data).savefig(out_path, dpi=120)
    return out_path


def wear_file_name(slug: str) -> str:
    """File name from a catalog slug (never a raw user path).

    Raises:
        ValueError: if the slug has unexpected characters.
    """
    if not _SLUG.match(slug):
        raise ValueError(f"Unsafe race slug for a file name: {slug!r}")
    return f"wear-{slug}.png"
