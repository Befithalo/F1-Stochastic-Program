"""Altair chart contracts for the replay page."""

from __future__ import annotations

from itertools import pairwise
from typing import cast

import numpy as np

from f1si.plots.altair_charts import (
    build_fan_chart,
    build_race_trace_chart,
    build_stint_chart,
)
from f1si.plots.simulate import prepare_fan_chart_data
from f1si.ui_theme import ASPHALT, CHALK, FOG, contrast_ratio, fan_band_colors, readable_on


def _inline_values(spec: dict[str, object], layer: dict[str, object]) -> list[dict[str, object]]:
    data = layer.get("data", spec.get("data"))
    assert isinstance(data, dict)
    values = data.get("values")
    if values is None:
        datasets = spec["datasets"]
        assert isinstance(datasets, dict)
        values = datasets[data["name"]]
    assert isinstance(values, list)
    return values


def test_fan_chart_uses_one_team_hue_strongest_at_the_median_and_labels_at_the_flag() -> None:
    history = np.asarray(
        [[1, 2, 3, 3, 3], [2, 4, 5, 5, 5], [3, 5, 7, 7, 7], [5, 7, 9, 9, 9]],
        dtype=np.int64,
    )
    data = prepare_fan_chart_data(history, first_lap=53, n_cars=10)
    team_color = "#358C75"
    spec = build_fan_chart(data, team_color=team_color).to_dict()
    layers = spec["layer"]
    assert isinstance(layers, list)
    assert "title" not in spec
    x_axis = layers[0]["encoding"]["x"]
    assert x_axis["title"] == "Lap"
    # Decision 15: lap k spans [k - 0.5, k + 0.5], so laps 53 to 57 fill 52.5 to 57.5.
    assert x_axis["scale"]["domain"] == [52.5, 57.5]
    band_rows = _inline_values(spec, layers[0])
    assert [row["x"] for row in band_rows] == [52.5, 53.5, 54.5, 55.5, 56.5, 57.5]
    area_colors = [layer["mark"]["color"] for layer in layers if layer["mark"]["type"] == "area"]
    assert area_colors == list(fan_band_colors(team_color))
    assert min(contrast_ratio(color, ASPHALT) for color in area_colors) >= 3.0
    medians = [layer["mark"]["color"] for layer in layers if layer["mark"]["type"] == "line"]
    assert medians == [ASPHALT, CHALK]
    label_layer = next(layer for layer in layers if layer["mark"]["type"] == "text")
    assert label_layer["mark"]["color"] == FOG
    labels = _inline_values(spec, label_layer)
    assert [
        row["label"] for row in sorted(labels, key=lambda row: cast(float, row["position"]))
    ] == [
        "2 in 10",
        "5 in 10",
        "8 in 10 races",
    ]
    label_rows = sorted(cast(float, row["position"]) for row in labels)
    assert min(b - a for a, b in pairwise(label_rows)) >= 1.2
    assert {row["lap"] for row in labels} == {57.5}


def test_gap_trace_has_no_dashes_or_leader_lines_and_labels_line_ends_with_gaps() -> None:
    def row(code: str, lap: int, gap: float, latest: bool) -> dict[str, object]:
        return {"driver_code": code, "lap": lap, "gap_to_leader_s": gap, "is_latest": latest}

    rows = (
        row("VER", 13, 0.0, False),
        row("VER", 14, 0.0, True),
        row("STR", 14, 14.0, True),
        row("ALO", 13, 14.5, False),
        row("ALO", 14, 15.0, True),
        row("LEC", 14, 20.0, True),
        row("HAM", 14, 40.0, True),
    )
    chart = build_race_trace_chart(rows, selected_driver="ALO", selected_color="#358C75")
    assert chart is not None
    spec = chart.to_dict()
    layers = spec["layer"]
    assert isinstance(layers, list)
    assert layers[0]["encoding"]["x"]["scale"]["domain"] == [0.5, 14.5]
    assert all("strokeDash" not in layer.get("encoding", {}) for layer in layers)
    assert all(layer["mark"]["type"] in {"line", "text"} for layer in layers)
    colors = [layer["mark"]["color"] for layer in layers if layer["mark"]["type"] == "line"]
    assert FOG in colors
    assert readable_on("#358C75") in colors
    texts = {
        value["text"]
        for layer in layers
        if layer["mark"]["type"] == "text"
        for value in _inline_values(spec, layer)
    }
    assert texts == {"ALO 15.0 s", "STR 14.0 s", "LEC 20.0 s"}


def test_stint_chart_draws_plan_dashed_now_line_and_team_colored_driver() -> None:
    rows = (
        {
            "driver_code": "ALO",
            "compound": "SOFT",
            "compound_letter": "S",
            "first_lap": 1,
            "last_visible_lap": 14,
            "laps_completed": 14,
            "start_lap": 0.5,
            "end_lap": 14.5,
            "mid_lap": 7.5,
        },
        {
            "driver_code": "ALO",
            "compound": "HARD",
            "compound_letter": "H",
            "first_lap": 15,
            "last_visible_lap": None,
            "laps_completed": 0,
            "start_lap": 14.5,
            "end_lap": 15.5,
            "mid_lap": 15.0,
        },
        {
            "driver_code": "VER",
            "compound": "MEDIUM",
            "compound_letter": "M",
            "first_lap": 1,
            "last_visible_lap": 15,
            "laps_completed": 15,
            "start_lap": 0.5,
            "end_lap": 15.5,
            "mid_lap": 8,
        },
    )
    team_color = "#358C75"
    chart = build_stint_chart(
        rows,
        cutoff_lap=15,
        laps_total=57,
        driver_order=("VER", "ALO"),
        selected_driver="ALO",
        plan_segments=((15.5, 57.5, "HARD"),),
        selected_color=team_color,
    )
    assert chart is not None
    spec = chart.to_dict()
    layers = spec["layer"]
    assert isinstance(layers, list)
    planned = next(
        layer
        for layer in layers
        if layer["mark"]["type"] == "bar" and "strokeDash" in layer["mark"]
    )
    assert planned["mark"]["stroke"] == readable_on(team_color)
    plan_rows = _inline_values(spec, planned)
    assert plan_rows[0]["driver_code"] == "ALO"
    assert (plan_rows[0]["start_lap"], plan_rows[0]["end_lap"]) == (15.5, 57.5)
    rule = next(layer for layer in layers if layer["mark"]["type"] == "rule")
    assert _inline_values(spec, rule)[0]["lap"] == 15.5
    bars = next(layer for layer in layers if layer["mark"]["type"] == "bar")
    assert bars["encoding"]["x"]["axis"]["title"] == "Lap"
    driver_labels = [
        layer
        for layer in layers
        if layer["mark"]["type"] == "text" and layer["encoding"]["text"]["field"] == "driver_code"
    ]
    selected = next(layer for layer in driver_labels if layer["mark"]["fontWeight"] == 700)
    assert selected["mark"]["color"] == readable_on(team_color)
    assert {value["driver_code"] for value in _inline_values(spec, selected)} == {"ALO"}
