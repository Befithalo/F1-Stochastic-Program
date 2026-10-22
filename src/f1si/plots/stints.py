"""Lap time by stint: one small panel per driver, coloured by tyre compound (DAT-02, D-15, D-16).

The data preparation (`prepare_stint_plot_data`) is a pure function of a `RaceSnapshot`, so it can
only see what the as-of door shows at that cutoff. It is registered as a consumer in the
future-scramble test. The renderer (`build_figure`) uses the matplotlib `Figure` API directly and
never `pyplot`: pyplot keeps global figure state, and the Figure API needs no GUI backend on CI or
Windows.

Faded, not removed
------------------
Lap 1, pit in-laps, pit out-laps and laps under a safety car, virtual safety car or red flag are
drawn at alpha 0.25 instead of being dropped. The true race stays visible, while the clean laps
stand out so that the tyre-wear trend (lap time drifting up inside a stint) can be read.

The y-range comes from clean laps only:

    lower = min(clean lap time) - 0.5 s
    upper = 98th percentile(clean lap time) + 1.0 s

If it came from all laps, pit and safety-car laps (20 s or more slower) would flatten the trend.
A point outside the range is drawn on the edge of the panel with an arrow marker, so nothing is
hidden.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from f1si.data.asof import RaceSnapshot

COMPOUND_COLORS: Final[dict[str, str]] = {
    "SOFT": "#da291c",
    "MEDIUM": "#ffd12e",
    "HARD": "#f0f0ec",
    "INTERMEDIATE": "#43b02a",
    "WET": "#0067ad",
}
UNKNOWN_COLOR: Final = "#888888"
EDGE_COLOR: Final = "#333333"
FADED_ALPHA: Final = 0.25
FADE_TRACK_CODES: Final = frozenset({"4", "5", "6", "7"})
_STINT_LINE_COLOR: Final = "#999999"
_HEADROOM_S: Final = 0.3
_POINT_COLUMNS: Final = (
    "driver_code",
    "lap_number",
    "lap_time_s",
    "y_plot",
    "compound",
    "color",
    "faded",
    "fade_reason",
    "clipped",
)
_CODE = re.compile(r"^[A-Z]{3}$")
_SLUG = re.compile(r"^[a-z0-9-]+$")


class UnknownDriverError(ValueError):
    """A requested driver code is not in this race."""

    def __init__(self, unknown: Sequence[str], known: Sequence[str]) -> None:
        super().__init__(
            f"Unknown driver code(s) {', '.join(unknown)}. Codes in this race: {', '.join(known)}"
        )


@dataclass(frozen=True, eq=False)
class StintPlotData:
    """Everything the renderer needs, as plain data (no snapshot, no accessor)."""

    title: str
    slug: str
    drivers: tuple[str, ...]
    panel_titles: Mapping[str, str]
    points: pd.DataFrame
    y_limits: tuple[float, float]
    skipped_laps: int
    stint_starts: Mapping[str, tuple[int, ...]]


def _fade_reason(lap_number: int, pit_in: bool, pit_out: bool, track_status: object) -> str | None:
    """First matching reason a lap is faded, or None for a clean lap."""
    if lap_number == 1:
        return "lap 1"
    if pit_in:
        return "pit in"
    if pit_out:
        return "pit out"
    if isinstance(track_status, str) and any(c in FADE_TRACK_CODES for c in track_status):
        return "safety car/VSC/red"
    return None


def _grid_order(entries: pd.DataFrame) -> pd.DataFrame:
    """Entries sorted by grid position (missing last), then driver number."""
    ordered = entries.assign(_grid=entries["grid_position"].astype("Float64").fillna(math.inf))
    return ordered.sort_values(["_grid", "driver_number"], kind="stable").reset_index(drop=True)


def _select_drivers(order: pd.DataFrame, drivers: Sequence[str] | None) -> pd.DataFrame:
    if drivers is None:
        return order
    wanted = [str(d).upper() for d in drivers]
    bad_format = [d for d in wanted if not _CODE.match(d)]
    if bad_format:
        raise ValueError(f"Driver codes are three letters, like VER; got {', '.join(bad_format)}")
    known = [str(c) for c in order["driver_code"]]
    unknown = [d for d in wanted if d not in known]
    if unknown:
        raise UnknownDriverError(unknown, sorted(known))
    return order[order["driver_code"].isin(wanted)].reset_index(drop=True)


def _empty_points() -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series([], dtype="object") for name in _POINT_COLUMNS})


def _panel_title(row: pd.Series) -> str:
    code = str(row["driver_code"])
    if bool(row["pit_lane_start"]):
        return f"{code}  pit lane"
    if pd.isna(row["grid_position"]):
        return code
    return f"{code}  P{int(row['grid_position'])}"


def _stint_starts(
    snapshot: RaceSnapshot, number_to_code: Mapping[int, str]
) -> dict[str, tuple[int, ...]]:
    starts: dict[str, tuple[int, ...]] = {code: () for code in number_to_code.values()}
    stints = snapshot.stints
    if stints.empty:
        return starts
    ordered = stints.sort_values(["driver_number", "stint"])
    for number in ordered["driver_number"].unique():
        code = number_to_code.get(int(number))
        if code is not None:
            firsts = ordered.loc[ordered["driver_number"] == number, "first_lap"]
            starts[code] = tuple(int(v) for v in firsts.iloc[1:])
    return starts


def prepare_stint_plot_data(
    snapshot: RaceSnapshot, drivers: Sequence[str] | None = None
) -> StintPlotData:
    """Classify every visible lap and compute the shared y-range (pure; reads only `snapshot`).

    Raises:
        ValueError: if a driver code is not three letters.
        UnknownDriverError: if a driver code is not in this race.
    """
    chosen = _select_drivers(_grid_order(snapshot.entries), drivers)
    number_to_code = {
        int(n): str(c) for n, c in zip(chosen["driver_number"], chosen["driver_code"], strict=True)
    }
    codes = tuple(str(c) for c in chosen["driver_code"])
    laps = snapshot.laps[snapshot.laps["driver_number"].isin(list(number_to_code))]

    has_time = laps["lap_time_s"].notna()
    skipped = int((~has_time).sum())
    laps = laps[has_time]

    race = snapshot.race
    if isinstance(snapshot.at.lap, int):
        title = f"{race.event_name} {race.season}: lap time by stint (as of lap {snapshot.at.lap})"
    else:
        title = f"{race.event_name} {race.season}: lap time by stint (full race)"
    panel_titles = {str(r["driver_code"]): _panel_title(r) for _, r in chosen.iterrows()}
    starts = _stint_starts(snapshot, number_to_code)

    if laps.empty:
        return StintPlotData(
            title, race.slug, codes, panel_titles, _empty_points(), (0.0, 1.0), skipped, starts
        )

    reasons = [
        _fade_reason(int(lap), bool(pin), bool(pout), ts)
        for lap, pin, pout, ts in zip(
            laps["lap_number"],
            laps["is_pit_in_lap"].fillna(False),
            laps["is_pit_out_lap"].fillna(False),
            laps["track_status"],
            strict=True,
        )
    ]
    times = laps["lap_time_s"].astype(float).to_numpy()
    clean = np.array([r is None for r in reasons])
    basis = times[clean] if clean.any() else times
    lower = float(basis.min()) - 0.5
    upper = float(np.percentile(basis, 98)) + 1.0

    compound = (
        laps["compound"]
        .astype("object")
        .map(lambda v: str(v).upper() if isinstance(v, str) else None)
    )
    points = pd.DataFrame(
        {
            "driver_code": laps["driver_number"].map(lambda n: number_to_code[int(n)]).to_numpy(),
            "lap_number": laps["lap_number"].astype(int).to_numpy(),
            "lap_time_s": times,
            "y_plot": np.clip(times, lower, upper),
            "compound": compound.to_numpy(),
            "color": [COMPOUND_COLORS.get(c or "", UNKNOWN_COLOR) for c in compound],
            "faded": [r is not None for r in reasons],
            "fade_reason": reasons,
            "clipped": (times < lower) | (times > upper),
        }
    )
    return StintPlotData(
        title, race.slug, codes, panel_titles, points, (lower, upper), skipped, starts
    )


def build_figure(data: StintPlotData) -> Figure:
    """Draw the small multiples (Figure API, no pyplot)."""
    n = max(1, len(data.drivers))
    ncols = min(5, n)
    nrows = math.ceil(n / ncols)
    fig = Figure(figsize=(3.6 * ncols, 2.6 * nrows + 0.8), layout="constrained")
    axes = fig.subplots(nrows, ncols, sharex=True, sharey=True, squeeze=False)
    flat = list(axes.ravel())
    lower, upper = data.y_limits
    for ax in flat[len(data.drivers) :]:
        ax.set_visible(False)
    for code, ax in zip(data.drivers, flat, strict=False):
        ax.set_title(data.panel_titles[code], fontsize=9)
        ax.set_ylim(lower - _HEADROOM_S, upper + _HEADROOM_S)
        ax.tick_params(labelsize=7)
        mine = data.points[data.points["driver_code"] == code] if len(data.points) else data.points
        if mine.empty:
            ax.text(0.5, 0.5, "no laps yet", ha="center", va="center", transform=ax.transAxes)
        for faded in (False, True):
            for clipped, marker in ((False, "o"), (True, "^")):
                sel = mine[(mine["faded"] == faded) & (mine["clipped"] == clipped)]
                if sel.empty:
                    continue
                ax.scatter(
                    sel["lap_number"].astype(float),
                    sel["y_plot"].astype(float),
                    s=14,
                    marker=marker,
                    c=list(sel["color"]),
                    edgecolors=EDGE_COLOR,
                    linewidths=0.4,
                    alpha=FADED_ALPHA if faded else 1.0,
                )
        for lap in data.stint_starts.get(code, ()):
            ax.axvline(lap - 0.5, color=_STINT_LINE_COLOR, linewidth=0.6, linestyle=":", zorder=0)

    present = [
        c for c in COMPOUND_COLORS if len(data.points) and (data.points["compound"] == c).any()
    ]
    handles: list[Line2D] = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markerfacecolor=COMPOUND_COLORS[c],
            markeredgecolor=EDGE_COLOR,
            markersize=6,
            label=c.lower(),
        )
        for c in present
    ]
    handles += [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markerfacecolor="#888888",
            alpha=FADED_ALPHA,
            markeredgecolor=EDGE_COLOR,
            markersize=6,
            label="faded = lap 1, pit in/out, SC/VSC/red",
        ),
        Line2D(
            [],
            [],
            marker="^",
            linestyle="",
            markerfacecolor="#888888",
            markeredgecolor=EDGE_COLOR,
            markersize=6,
            label="^ = above the range",
        ),
        Line2D(
            [],
            [],
            color=_STINT_LINE_COLOR,
            linestyle=":",
            linewidth=0.8,
            label="dotted line = stint change",
        ),
    ]
    fig.legend(handles=handles, loc="outside lower center", ncols=min(len(handles), 4), fontsize=8)
    for index, ax in enumerate(flat[: len(data.drivers)]):
        if index + ncols >= len(data.drivers):  # lowest visible panel of its column
            ax.tick_params(labelbottom=True)
            ax.set_xlabel("Lap", fontsize=8)
    fig.supylabel("Lap time (s)")
    fig.suptitle(data.title)
    return fig


def render_stint_plot(data: StintPlotData, out_path: Path) -> Path:
    """Write the plot as a PNG (creating parent folders) and return the path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    build_figure(data).savefig(out_path, dpi=120)
    return out_path


def plot_file_name(slug: str, drivers: Sequence[str] | None) -> str:
    """File name from a catalog slug and validated driver codes (never a raw user path).

    Raises:
        ValueError: if the slug or a driver code has unexpected characters.
    """
    if not _SLUG.match(slug):
        raise ValueError(f"Unsafe race slug for a file name: {slug!r}")
    if drivers is None:
        return f"{slug}.png"
    codes = sorted({str(d).upper() for d in drivers})
    bad = [c for c in codes if not _CODE.match(c)]
    if bad:
        raise ValueError(f"Driver codes are three letters, like VER; got {', '.join(bad)}")
    return f"{slug}-{'-'.join(c.lower() for c in codes)}.png"
