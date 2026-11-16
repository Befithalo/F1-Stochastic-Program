"""Altair renderers for replay uncertainty and race context.

Lap coordinates: lap ``k`` occupies ``[k - 0.5, k + 0.5]`` on every lap axis, so the moment
"after lap N" sits at ``N + 0.5`` (DESIGN_SYSTEM_V2 §10, decision 15).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

import altair as alt
import pandas as pd

from f1si.plots.simulate import FanChartData
from f1si.ui_theme import (
    ASPHALT,
    CHALK,
    DEFAULT_TEAM_COLOR,
    FOG,
    GRID_GREY,
    RULE,
    TIRE_COLORS,
    fan_band_colors,
    readable_on,
)

DIM_LINE = GRID_GREY
"""Every car that is not the selected driver or a labelled neighbour."""

PlanSegment = tuple[float, float, str]
"""(start, end, compound) on the lap axis for the selected driver's planned running."""


def _base_chart(chart: Any) -> Any:
    return (
        chart.configure(background=ASPHALT)
        .configure_axis(
            labelColor=FOG,
            titleColor=FOG,
            labelFont="Titillium Web",
            titleFont="Titillium Web",
            labelFontSize=13,
            titleFontSize=13,
            titleFontWeight=400,
            gridColor=RULE,
            gridOpacity=1,
            tickColor=RULE,
            domain=False,
        )
        .configure_view(strokeOpacity=0)
    )


def _label_layers(
    frame: pd.DataFrame,
    *,
    selected_color: str,
    encode: dict[str, Any],
    align: str,
    dx: int,
    font_size: int,
) -> list[Any]:
    """Two text layers: other labels in fog at weight 400, the selected one bold in its color."""
    layers: list[Any] = []
    for selected, color, weight in ((False, FOG, 400), (True, selected_color, 700)):
        subset = frame.loc[frame["selected"].eq(selected)]
        if subset.empty:
            continue
        layers.append(
            alt.Chart(subset)
            .mark_text(
                align=cast(Any, align),
                dx=dx,
                font="Titillium Web",
                fontSize=font_size,
                fontWeight=cast(Any, weight),
                color=color,
            )
            .encode(**encode)
        )
    return layers


def _spread(values: Mapping[str, float], gap: float, low: float, high: float) -> dict[str, float]:
    """Place labels at their values, pushed apart to at least ``gap`` and kept in range."""
    ordered = sorted(values.items(), key=lambda pair: pair[1])
    slots = [min(high, max(low, value)) for _, value in ordered]
    for index in range(1, len(slots)):
        slots[index] = max(slots[index], slots[index - 1] + gap)
    if slots and slots[-1] > high:
        slots[-1] = high
        for index in range(len(slots) - 2, -1, -1):
            slots[index] = min(slots[index], slots[index + 1] - gap)
    return {label: slot for (label, _), slot in zip(ordered, slots, strict=True)}


def build_fan_chart(data: FanChartData, *, team_color: str = DEFAULT_TEAM_COLOR) -> alt.LayerChart:
    """Nested team-colored bands (8, 5 and 2 in 10 races) with the median in chalk.

    The bands are the 10th to 90th, 25th to 75th and 40th to 60th percentiles of the selected
    driver's simulated position on each remaining lap. Labels sit to the right of the last lap.
    """
    frame = pd.DataFrame(
        {
            "lap": data.laps,
            "p10": data.p10,
            "p25": data.p25,
            "p40": data.p40,
            "p50": data.p50,
            "p60": data.p60,
            "p75": data.p75,
            "p90": data.p90,
        }
    )
    last = frame.iloc[-1]
    first_lap, last_lap = min(data.laps), max(data.laps)
    frame["x"] = frame["lap"] - 0.5
    closing = frame.iloc[[-1]].copy()
    closing["x"] = last_lap + 0.5
    frame = pd.concat([frame, closing], ignore_index=True)
    tick_values = {first_lap, last_lap}
    tick_values.update(range(((first_lap + 9) // 10) * 10, last_lap, 10))
    axis_x = alt.Axis(title="Lap", grid=False, values=sorted(tick_values), tickMinStep=1)
    axis_y = alt.Axis(title="Position", grid=True, tickMinStep=1, labelExpr="'P' + datum.value")
    x_scale = alt.Scale(domain=[first_lap - 0.5, last_lap + 0.5], nice=False)
    y_scale = alt.Scale(domain=[data.n_cars + 0.5, 0.5], nice=False)
    outer_color, middle_color, inner_color = fan_band_colors(team_color)

    def band(lower: str, upper: str, color: str) -> Any:
        return (
            alt.Chart(frame)
            .mark_area(color=color, opacity=1, interpolate="step-after")
            .encode(
                x=alt.X("x:Q", title="Lap", scale=x_scale, axis=axis_x),
                y=alt.Y(f"{lower}:Q", title="Position", scale=y_scale, axis=axis_y),
                y2=alt.Y2(f"{upper}:Q"),
                tooltip=[
                    alt.Tooltip("lap:Q", title="Lap", format=".0f"),
                    alt.Tooltip("p50:Q", title="Median position", format=".0f"),
                    alt.Tooltip("p10:Q", title="8 in 10 races from P", format=".0f"),
                    alt.Tooltip("p90:Q", title="to P", format=".0f"),
                ],
            )
        )

    def median(color: str, width: float) -> Any:
        return (
            alt.Chart(frame)
            .mark_line(color=color, strokeWidth=width, interpolate="step-after")
            .encode(
                x=alt.X("x:Q", scale=x_scale, axis=axis_x),
                y=alt.Y("p50:Q", scale=y_scale, axis=axis_y),
            )
        )

    # Nested bands share a center, so a tiny offset fixes the label order: narrowest band on top.
    centers = {
        "2 in 10": (float(last["p40"]) + float(last["p60"])) / 2,
        "5 in 10": (float(last["p25"]) + float(last["p75"])) / 2 + 0.001,
        "8 in 10 races": (float(last["p10"]) + float(last["p90"])) / 2 + 0.002,
    }
    gap = max(1.2, data.n_cars / 14)
    positions = _spread(centers, gap, 1.0, float(data.n_cars))
    labels = pd.DataFrame(
        [{"lap": last_lap + 0.5, "position": positions[label], "label": label} for label in centers]
    )
    direct_labels = (
        alt.Chart(labels)
        .mark_text(align="left", dx=8, font="Titillium Web", fontSize=13, color=FOG)
        .encode(
            x=alt.X("lap:Q", scale=x_scale, axis=axis_x),
            y=alt.Y("position:Q", scale=y_scale, axis=axis_y),
            text=alt.Text("label:N"),
        )
    )
    chart = alt.layer(
        band("p10", "p90", outer_color),
        band("p25", "p75", middle_color),
        band("p40", "p60", inner_color),
        median(ASPHALT, 5),
        median(CHALK, 2.5),
        direct_labels,
    ).properties(height=330, padding={"left": 4, "top": 8, "right": 96, "bottom": 4})
    return cast(alt.LayerChart, _base_chart(chart))


def build_race_trace_chart(
    rows: Sequence[Mapping[str, object]],
    *,
    selected_driver: str,
    selected_color: str,
) -> alt.LayerChart | None:
    """Gap to the leader by lap: selected driver in team color, nearest rivals in fog.

    Every other car is one thin dim line with no label. Labels sit at the line ends and carry
    the latest gap; they are nudged apart only as far as needed to stay readable.
    """
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    selected_code = selected_driver.upper()
    frame["driver_code"] = frame["driver_code"].astype(str).str.upper()
    frame["selected"] = frame["driver_code"].eq(selected_code)
    latest_rows = frame.loc[frame["is_latest"].astype(bool)].drop_duplicates("driver_code")
    nearest_codes: set[str] = set()
    selected_latest = latest_rows.loc[latest_rows["selected"]]
    if not selected_latest.empty:
        selected_gap = float(selected_latest.iloc[-1]["gap_to_leader_s"])
        others = latest_rows.loc[~latest_rows["selected"]]
        ahead = others.loc[others["gap_to_leader_s"] <= selected_gap].sort_values(
            "gap_to_leader_s", ascending=False
        )
        behind = others.loc[others["gap_to_leader_s"] > selected_gap].sort_values("gap_to_leader_s")
        nearest_codes = {
            str(code)
            for code in [
                *ahead.head(1)["driver_code"].tolist(),
                *behind.head(1)["driver_code"].tolist(),
            ]
        }
    frame["nearest"] = frame["driver_code"].isin(nearest_codes)
    max_lap = max(1, int(frame["lap"].max()))
    x_scale = alt.Scale(domain=[0.5, max(max_lap, 1) + 0.5], nice=False)
    tick_step = max(1, max_lap // 5)
    trace_ticks = sorted({1, max_lap, *range(tick_step, max_lap, tick_step)})
    y_max = float(frame["gap_to_leader_s"].max())
    y_scale = alt.Scale(domain=[0, y_max * 1.04 + 1], nice=False)
    x = alt.X(
        "lap:Q",
        title="Lap",
        scale=x_scale,
        axis=alt.Axis(grid=False, tickMinStep=1, values=trace_ticks),
    )
    y = alt.Y(
        "gap_to_leader_s:Q",
        title="Gap to leader (s)",
        scale=y_scale,
        axis=alt.Axis(grid=True, tickCount=6),
    )
    tooltip = [
        alt.Tooltip("driver_code:N", title="Driver"),
        alt.Tooltip("lap:Q", title="Lap", format=".0f"),
        alt.Tooltip("gap_to_leader_s:Q", title="Gap to leader (s)", format=".1f"),
    ]
    line_color = readable_on(selected_color)
    layers: list[Any] = []
    for subset, color, width in (
        (frame.loc[~frame["selected"] & ~frame["nearest"]], DIM_LINE, 1.0),
        (frame.loc[frame["nearest"]], FOG, 1.6),
        (frame.loc[frame["selected"]], line_color, 3.0),
    ):
        if subset.empty:
            continue
        layers.append(
            alt.Chart(subset)
            .mark_line(color=color, strokeWidth=width)
            .encode(x=x, y=y, detail=alt.Detail("driver_code:N"), tooltip=tooltip)
        )
    labelled = latest_rows.loc[
        latest_rows["selected"] | latest_rows["driver_code"].isin(nearest_codes)
    ]
    if not labelled.empty:
        gaps = {
            str(row.driver_code): float(cast(Any, row.gap_to_leader_s))
            for row in labelled.itertuples(index=False)
        }
        placed = _spread(gaps, max(1.0, y_max * 0.06), 0.0, y_max * 1.04 + 1)
        label_frame = pd.DataFrame(
            [
                {
                    "lap": int(cast(Any, row.lap)),
                    "label_y": placed[str(row.driver_code)],
                    "text": f"{row.driver_code} {float(cast(Any, row.gap_to_leader_s)):.1f} s",
                    "selected": bool(row.selected),
                }
                for row in labelled.itertuples(index=False)
            ]
        )
        layers.extend(
            _label_layers(
                label_frame,
                selected_color=CHALK,
                encode={
                    "x": alt.X("lap:Q", scale=x_scale),
                    "y": alt.Y("label_y:Q", scale=y_scale),
                    "text": alt.Text("text:N"),
                },
                align="left",
                dx=8,
                font_size=13,
            )
        )
    chart = alt.layer(*layers).properties(
        height=340, padding={"left": 4, "top": 8, "right": 92, "bottom": 4}
    )
    return cast(alt.LayerChart, _base_chart(chart))


def build_stint_chart(
    rows: Sequence[Mapping[str, object]],
    *,
    cutoff_lap: int,
    laps_total: int,
    driver_order: Sequence[str],
    selected_driver: str,
    plan_segments: Sequence[PlanSegment] = (),
    selected_color: str = DEFAULT_TEAM_COLOR,
) -> alt.LayerChart | None:
    """Completed stints for every driver, the selected driver's plan dashed in team color.

    ``rows`` come from ``prepare_stint_bar_data``. ``plan_segments`` are the selected driver's
    planned stints from the cutoff ``N + 0.5`` to the flag.
    """
    if not rows and not plan_segments:
        return None
    selected_code = selected_driver.upper()
    actual = pd.DataFrame([dict(row) for row in rows])
    plan = pd.DataFrame(
        [
            {
                "driver_code": selected_code,
                "compound": compound,
                "compound_letter": compound[0],
                "start_lap": start,
                "end_lap": end,
                "mid_lap": (start + end) / 2,
                "laps": round(end - start),
            }
            for start, end, compound in plan_segments
            if compound in TIRE_COLORS and end > start
        ]
    )
    compounds = list(TIRE_COLORS)
    colors = [TIRE_COLORS[name] for name in compounds]
    order = list(driver_order)
    x_scale = alt.Scale(domain=[-4.5, laps_total + 0.5], nice=False)
    x_ticks = sorted({1, *range(10, laps_total + 1, 10), laps_total})
    lap_axis = alt.Axis(grid=False, values=x_ticks, tickMinStep=1, title="Lap")

    def x(field: str) -> alt.X:
        return alt.X(f"{field}:Q", title="Lap", scale=x_scale, axis=lap_axis)

    y = alt.Y(
        "driver_code:N",
        title=None,
        sort=order,
        axis=alt.Axis(grid=False, labels=False, ticks=False, domain=False),
        scale=alt.Scale(paddingInner=0.3),
    )
    compound_color = alt.Color(
        "compound:N", scale=alt.Scale(domain=compounds, range=colors), legend=None
    )
    layers: list[Any] = []
    if not actual.empty:
        layers.append(
            alt.Chart(actual)
            .mark_bar(cornerRadius=2)
            .encode(
                x=x("start_lap"),
                x2=alt.X2("end_lap:Q"),
                y=y,
                color=compound_color,
                tooltip=[
                    alt.Tooltip("driver_code:N", title="Driver"),
                    alt.Tooltip("compound:N", title="Compound"),
                    alt.Tooltip("first_lap:Q", title="Start lap", format=".0f"),
                    alt.Tooltip("laps_completed:Q", title="Laps completed", format=".0f"),
                ],
            )
        )
    if not plan.empty:
        layers.append(
            alt.Chart(plan)
            .mark_bar(
                cornerRadius=2,
                fillOpacity=0.18,
                stroke=readable_on(selected_color),
                strokeWidth=2,
                strokeDash=[5, 3],
            )
            .encode(
                x=x("start_lap"),
                x2=alt.X2("end_lap:Q"),
                y=y,
                color=compound_color,
                tooltip=[
                    alt.Tooltip("compound:N", title="Planned compound"),
                    alt.Tooltip("laps:Q", title="Planned laps", format=".0f"),
                ],
            )
        )
    letters_source = pd.concat(
        [frame for frame in (actual, plan) if not frame.empty], ignore_index=True
    )
    if not letters_source.empty:
        wide = letters_source.loc[
            (letters_source["end_lap"].astype(float) - letters_source["start_lap"].astype(float))
            >= 2
        ]
        layers.append(
            alt.Chart(wide)
            .mark_text(color=ASPHALT, font="Saira Condensed", fontWeight=800, fontSize=11)
            .encode(
                x=x("mid_lap"),
                y=alt.Y("driver_code:N", sort=order),
                text=alt.Text("compound_letter:N"),
            )
        )
    cutoff_x = cutoff_lap + 0.5
    layers.append(
        alt.Chart(pd.DataFrame({"lap": [cutoff_x]}))
        .mark_rule(color=FOG, strokeDash=[2, 3], strokeWidth=1)
        .encode(x=x("lap"))
    )
    layers.append(
        alt.Chart(pd.DataFrame({"lap": [cutoff_x], "text": [f"now, after lap {cutoff_lap}"]}))
        .mark_text(align="left", dx=4, dy=-6, baseline="bottom", color=FOG, fontSize=12)
        .encode(x=x("lap"), y=alt.value(0), text=alt.Text("text:N"))
    )
    label_rows = pd.DataFrame(
        {
            "driver_code": order,
            "label_x": [-0.3] * len(order),
            "selected": [code.upper() == selected_code for code in order],
        }
    )
    layers.extend(
        _label_layers(
            label_rows,
            selected_color=readable_on(selected_color),
            encode={
                "x": x("label_x"),
                "y": alt.Y("driver_code:N", sort=order),
                "text": alt.Text("driver_code:N"),
            },
            align="right",
            dx=-2,
            font_size=12,
        )
    )
    height = max(260, len(order) * 19)
    chart = alt.layer(*layers).properties(
        height=height, padding={"left": 4, "top": 18, "right": 8, "bottom": 4}
    )
    return cast(alt.LayerChart, _base_chart(chart))
