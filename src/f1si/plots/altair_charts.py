"""Altair renderers for replay uncertainty and race context."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

import altair as alt
import pandas as pd

from f1si.plots.simulate import FanChartData, QuantileDotplotData
from f1si.ui_theme import ASPHALT, CHALK, FOG, RULE, TIRE_COLORS


def _base_chart(chart: Any) -> Any:
    return (
        chart.configure(background=ASPHALT)
        .configure_axis(
            labelColor=FOG,
            titleColor=CHALK,
            labelFont="Titillium Web",
            titleFont="Titillium Web",
            labelFontSize=12,
            titleFontSize=13,
            titleFontWeight=500,
            gridColor=RULE,
            gridOpacity=0.7,
            tickColor=FOG,
            domain=False,
        )
        .configure_view(strokeOpacity=0)
    )


def build_finish_probability_strip(
    data: QuantileDotplotData, *, recommended_color: str = "#4ADE80"
) -> alt.LayerChart:
    """Show each action's share of simulated finishes at every finishing position."""
    labels = data.labels[:5]
    quantiles = data.quantiles[:5]
    rows: list[dict[str, object]] = []
    for index, (label, sample) in enumerate(zip(labels, quantiles, strict=True)):
        for position in range(1, data.n_cars + 1):
            rows.append(
                {
                    "action": label,
                    "position": position,
                    "probability": sample.count(position) / 100.0,
                    "recommended": index == 0,
                }
            )
    frame = pd.DataFrame(rows)
    max_probability = max(float(frame["probability"].max()), 0.01)
    labels_order = list(labels)
    positions_order = list(range(1, data.n_cars + 1))

    def layer(recommended: bool, low: str, high: str) -> Any:
        subset = frame.loc[frame["recommended"].eq(recommended)]
        return (
            alt.Chart(subset)
            .mark_rect(stroke=ASPHALT, strokeWidth=0.6)
            .encode(
                x=alt.X(
                    "position:O",
                    title="Finishing position",
                    sort=positions_order,
                    axis=alt.Axis(grid=False, labelAngle=0, labelOverlap=False),
                ),
                y=alt.Y(
                    "action:N",
                    title=None,
                    sort=labels_order,
                    axis=alt.Axis(grid=False, labelLimit=140, labelPadding=8, tickSize=0),
                ),
                color=alt.Color(
                    "probability:Q",
                    scale=alt.Scale(
                        domain=[0, max_probability],
                        range=[low, high],
                        clamp=True,
                    ),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("action:N", title="Action"),
                    alt.Tooltip("position:O", title="Finishing position"),
                    alt.Tooltip("probability:Q", title="Chance", format=".0%"),
                ],
            )
        )

    chart = (
        alt.layer(
            layer(True, "#8A8F99", recommended_color),
            layer(False, "#8A8F99", "#D3D5D9"),
        )
        .resolve_scale(color="independent")
        .properties(height=max(230, len(labels) * 46))
    )
    return cast(alt.LayerChart, _base_chart(chart))


def _tint(color: str, amount: float) -> str:
    """Mix an opaque color toward white for lower-confidence fan bands."""
    channels = [int(color[index : index + 2], 16) for index in (1, 3, 5)]
    tinted = [round(channel + (255 - channel) * amount) for channel in channels]
    return "#" + "".join(f"{channel:02X}" for channel in tinted)


def _spaced_labels(centers: Mapping[str, float], n_cars: int) -> dict[str, float]:
    """Place nested percentile labels on separate rows without changing their order."""
    gap = min(2.0, max(1.2, (n_cars - 1) / 4))
    ordered = sorted(centers.items(), key=lambda pair: pair[1])
    slots = [min(float(n_cars), max(1.0, value)) for _, value in ordered]
    for index in range(1, len(slots)):
        slots[index] = max(slots[index], slots[index - 1] + gap)
    if slots and slots[-1] > n_cars:
        slots[-1] = float(n_cars)
        for index in range(len(slots) - 2, -1, -1):
            slots[index] = min(slots[index], slots[index + 1] - gap)
    if slots and slots[0] < 1:
        shift = 1.0 - slots[0]
        slots = [value + shift for value in slots]
    return {label: value for (label, _), value in zip(ordered, slots, strict=True)}


def build_fan_chart(data: FanChartData, *, team_color: str = "#229971") -> alt.LayerChart:
    """Build nested team-colored uncertainty bands with direct labels at race distance."""
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
    tick_values = {first_lap, last_lap}
    tick_values.update(range(((first_lap + 9) // 10) * 10, last_lap, 10))
    axis_x = alt.Axis(
        title="Lap",
        grid=False,
        values=sorted(tick_values),
        tickMinStep=1,
    )
    axis_y = alt.Axis(
        title="Finishing position",
        grid=True,
        tickMinStep=1,
        labelExpr="'P' + datum.value",
    )
    x_scale = alt.Scale(domain=[first_lap, last_lap], nice=False)
    y_scale = alt.Scale(domain=[data.n_cars + 0.5, 0.5], nice=False)

    def band(lower: str, upper: str, color: str) -> Any:
        return (
            alt.Chart(frame)
            .mark_area(color=color, opacity=1)
            .encode(
                x=alt.X("lap:Q", title="Lap", scale=x_scale, axis=axis_x),
                y=alt.Y(f"{lower}:Q", title="Finishing position", scale=y_scale, axis=axis_y),
                y2=alt.Y2(f"{upper}:Q"),
            )
        )

    outer = band("p10", "p90", _tint(team_color, 0.35)).encode(opacity=alt.value(0.85))
    middle = band("p25", "p75", _tint(team_color, 0.20)).encode(opacity=alt.value(0.92))
    center = band("p40", "p60", _tint(team_color, 0.08)).encode(opacity=alt.value(1.0))
    median = (
        alt.Chart(frame)
        .mark_line(color=team_color, strokeWidth=2.5)
        .encode(
            x=alt.X("lap:Q", scale=x_scale, axis=axis_x),
            y=alt.Y("p50:Q", scale=y_scale, axis=axis_y),
        )
    )
    centers = {
        "10th\N{EN DASH}90th": (float(last["p10"]) + float(last["p90"])) / 2,
        "25th\N{EN DASH}75th": (float(last["p25"]) + float(last["p75"])) / 2,
        "40th\N{EN DASH}60th": (float(last["p40"]) + float(last["p60"])) / 2,
    }
    positions = _spaced_labels(centers, data.n_cars)
    labels = pd.DataFrame(
        [{"lap": last_lap, "position": positions[label], "label": label} for label in centers]
    )
    direct_labels = (
        alt.Chart(labels)
        .mark_text(
            align="right",
            dx=-4,
            font="Titillium Web",
            fontSize=10,
            color=FOG,
            stroke=ASPHALT,
            strokeWidth=2,
        )
        .encode(
            x=alt.X("lap:Q", scale=x_scale, axis=axis_x),
            y=alt.Y("position:Q", scale=y_scale, axis=axis_y),
            text=alt.Text("label:N"),
        )
    )
    chart = alt.layer(outer, middle, center, median, direct_labels).properties(height=330)
    return cast(alt.LayerChart, _base_chart(chart))


def build_race_trace_chart(
    rows: Sequence[Mapping[str, object]],
    *,
    selected_driver: str,
    selected_color: str,
    cutoff_lap: int,
) -> alt.LayerChart | None:
    """Highlight the selected driver's gap trace and mute every other car."""
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    selected_code = selected_driver.upper()
    frame["selected"] = frame["driver_code"].astype(str).str.upper().eq(selected_code)
    frame["driver_label"] = frame["driver_code"].astype(str).str.upper()
    x_scale = alt.Scale(domain=[0.5, max(1, cutoff_lap)], nice=False)
    tick_step = max(1, cutoff_lap // 5)
    trace_ticks = sorted({cutoff_lap, *range(tick_step, cutoff_lap, tick_step)})
    y_scale = alt.Scale(domain=[0, float(frame["label_gap_s"].max()) + 2], nice=False)
    common = {
        "x": alt.X(
            "lap:Q",
            title="Lap",
            scale=x_scale,
            axis=alt.Axis(grid=False, tickMinStep=1, values=trace_ticks),
        ),
        "y": alt.Y(
            "gap_to_leader_s:Q",
            title="Gap to leader (s)",
            scale=y_scale,
            axis=alt.Axis(grid=True),
        ),
        "detail": alt.Detail("driver_code:N"),
        "strokeDash": alt.StrokeDash(
            "teammate_dash:N",
            scale=alt.Scale(domain=[False, True], range=[[1, 0], [5, 3]]),
            legend=None,
        ),
    }
    layers: list[Any] = []

    def add_lines(source: pd.DataFrame, color: str, width: float, opacity: float) -> None:
        if source.empty:
            return
        layers.append(
            alt.Chart(source)
            .mark_line(color=color, strokeWidth=width, opacity=opacity)
            .encode(
                **common,
                tooltip=[
                    alt.Tooltip("driver_code:N", title="Driver"),
                    alt.Tooltip("lap:Q", title="Lap", format=".0f"),
                    alt.Tooltip("gap_to_leader_s:Q", title="Gap to leader", format=".1f"),
                ],
            )
        )

    selected_latest = frame.loc[frame["selected"] & frame["is_latest"].astype(bool)]
    nearest_codes: set[str] = set()
    if not selected_latest.empty:
        selected_gap = float(selected_latest.iloc[-1]["gap_to_leader_s"])
        latest_gaps = frame.loc[
            frame["is_latest"].astype(bool), ["driver_code", "gap_to_leader_s"]
        ].drop_duplicates("driver_code")
        ahead = latest_gaps.loc[latest_gaps["gap_to_leader_s"] < selected_gap].sort_values(
            "gap_to_leader_s", ascending=False
        )
        behind = latest_gaps.loc[latest_gaps["gap_to_leader_s"] > selected_gap].sort_values(
            "gap_to_leader_s"
        )
        nearest_codes = {
            str(code).upper()
            for code in [
                *ahead.head(1)["driver_code"].tolist(),
                *behind.head(1)["driver_code"].tolist(),
            ]
        }
    frame["nearest"] = frame["driver_code"].astype(str).str.upper().isin(nearest_codes)
    add_lines(frame.loc[~frame["selected"] & ~frame["nearest"]], "#7C828D", 0.9, 0.80)
    add_lines(frame.loc[frame["nearest"]], FOG, 1.25, 0.95)
    add_lines(frame.loc[frame["selected"]], selected_color, 2.8, 1.0)
    latest = frame.loc[frame["is_latest"].astype(bool)].copy()
    latest = latest.loc[latest["selected"] | latest["nearest"]]
    latest["label_lap"] = cutoff_lap
    latest["label_color"] = latest["selected"].map({True: selected_color, False: FOG})
    latest["point_color"] = latest["label_color"]

    def add_latest(source: pd.DataFrame, color: str, text_color: str) -> None:
        if source.empty:
            return
        layers.extend(
            [
                alt.Chart(source)
                .mark_point(filled=True, size=34, stroke=ASPHALT, strokeWidth=0.8, color=color)
                .encode(
                    x=alt.X("lap:Q", scale=x_scale),
                    y=alt.Y("gap_to_leader_s:Q", scale=y_scale),
                    tooltip=[
                        alt.Tooltip("driver_code:N", title="Driver"),
                        alt.Tooltip("lap:Q", title="Lap", format=".0f"),
                        alt.Tooltip("gap_to_leader_s:Q", title="Gap to leader", format=".1f"),
                    ],
                ),
                alt.Chart(source)
                .mark_rule(color=color, opacity=0.62, strokeWidth=0.7)
                .encode(
                    x=alt.X("lap:Q", scale=x_scale),
                    x2=alt.X2("label_lap:Q"),
                    y=alt.Y("gap_to_leader_s:Q", scale=y_scale),
                    y2=alt.Y2("label_gap_s:Q"),
                ),
                alt.Chart(source)
                .mark_text(
                    align="right", dx=-4, font="Titillium Web", fontSize=11, color=text_color
                )
                .encode(
                    x=alt.X("label_lap:Q", scale=x_scale),
                    y=alt.Y("label_gap_s:Q", scale=y_scale),
                    text=alt.Text("driver_label:N"),
                ),
            ]
        )

    add_latest(latest.loc[~latest["selected"]], FOG, FOG)
    add_latest(latest.loc[latest["selected"]], selected_color, CHALK)
    return cast(alt.LayerChart, _base_chart(alt.layer(*layers).properties(height=350)))


def build_stint_chart(
    rows: Sequence[Mapping[str, object]],
    *,
    cutoff_lap: int,
    laps_total: int,
    driver_order: Sequence[str],
    selected_driver: str,
    recommended_stop_lap: int | None,
    recommended_compound: str | None,
    selected_color: str = "#229971",
) -> alt.LayerChart | None:
    """Show completed stint bars and the selected driver's recommended next stint."""
    if not rows and recommended_stop_lap is None:
        return None
    segments = [dict(row, recommended=False) for row in rows]
    compound = (recommended_compound or "").upper()
    if (
        recommended_stop_lap is not None
        and recommended_stop_lap < laps_total
        and compound in TIRE_COLORS
    ):
        first_lap = recommended_stop_lap + 1
        segments.append(
            {
                "driver_code": selected_driver.upper(),
                "compound": compound,
                "compound_letter": compound[0],
                "first_lap": first_lap,
                "last_visible_lap": laps_total,
                "start_lap": first_lap - 0.5,
                "end_lap": laps_total + 0.5,
                "mid_lap": (first_lap + laps_total) / 2,
                "recommended": True,
            }
        )
    frame = pd.DataFrame(segments)
    if frame.empty:
        return None
    actual = frame.loc[~frame["recommended"]]
    next_stint = frame.loc[frame["recommended"]]
    compounds = list(TIRE_COLORS)
    colors = [TIRE_COLORS[name] for name in compounds]
    x_scale = alt.Scale(domain=[-5.5, laps_total + 0.5], nice=False)
    x_ticks = sorted({*range(5, laps_total + 1, 5), laps_total})

    def bar_layer(source: pd.DataFrame, *, recommended: bool) -> Any:
        return (
            alt.Chart(source)
            .mark_bar(
                size=13,
                stroke=selected_color if recommended else None,
                strokeWidth=2 if recommended else 0,
                fillOpacity=0.48 if recommended else 1,
            )
            .encode(
                x=alt.X(
                    "start_lap:Q",
                    title="Lap",
                    scale=x_scale,
                    axis=alt.Axis(grid=False, values=x_ticks, tickMinStep=1),
                ),
                x2=alt.X2("end_lap:Q"),
                y=alt.Y(
                    "driver_code:N",
                    title=None,
                    sort=list(driver_order),
                    axis=alt.Axis(
                        grid=True,
                        labels=False,
                        ticks=False,
                        domain=False,
                    ),
                ),
                color=alt.Color(
                    "compound:N",
                    scale=alt.Scale(domain=compounds, range=colors),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("driver_code:N", title="Driver"),
                    alt.Tooltip("compound:N", title="Compound"),
                    alt.Tooltip("first_lap:Q", title="Start lap", format=".0f"),
                    alt.Tooltip("last_visible_lap:Q", title="Last lap", format=".0f"),
                ],
            )
        )

    layers: list[Any] = []
    if not actual.empty:
        layers.append(bar_layer(actual, recommended=False))
    if not next_stint.empty:
        layers.append(bar_layer(next_stint, recommended=True))
    row_labels = pd.DataFrame(
        {"driver_code": list(driver_order), "label_x": [-0.4] * len(driver_order)}
    )
    direct_labels = (
        alt.Chart(row_labels)
        .mark_text(
            align="right",
            dx=-4,
            color=FOG,
            font="Titillium Web",
            fontSize=10,
        )
        .encode(
            x=alt.X("label_x:Q", scale=x_scale, axis=None),
            y=alt.Y("driver_code:N", sort=list(driver_order), axis=None),
            text=alt.Text("driver_code:N"),
        )
    )
    letter_backing = (
        alt.Chart(frame)
        .mark_point(
            shape="square",
            filled=True,
            size=100,
            color=ASPHALT,
            strokeWidth=1,
        )
        .encode(
            x=alt.X("mid_lap:Q", scale=x_scale),
            y=alt.Y("driver_code:N", sort=list(driver_order), axis=None),
            stroke=alt.Color(
                "compound:N", scale=alt.Scale(domain=compounds, range=colors), legend=None
            ),
        )
    )
    letters = (
        alt.Chart(frame)
        .mark_text(color=CHALK, font="Titillium Web", fontWeight=700, fontSize=9)
        .encode(
            x=alt.X("mid_lap:Q", scale=x_scale),
            y=alt.Y("driver_code:N", sort=list(driver_order), axis=None),
            text=alt.Text("compound_letter:N"),
        )
    )
    cutoff_rule = (
        alt.Chart(pd.DataFrame({"lap": [cutoff_lap]}))
        .mark_rule(color=FOG, opacity=0.75, strokeWidth=0.8)
        .encode(x=alt.X("lap:Q", scale=x_scale))
    )
    layers.append(cutoff_rule)
    layers.append(direct_labels)
    layers.append(letter_backing)
    layers.append(letters)
    return cast(
        alt.LayerChart,
        _base_chart(alt.layer(*layers).properties(height=max(260, len(driver_order) * 18))),
    )
