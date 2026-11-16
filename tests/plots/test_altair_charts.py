"""Altair chart contracts for the replay page."""

from __future__ import annotations

from itertools import pairwise
from typing import cast

import numpy as np

from f1si.plots.altair_charts import (
    build_fan_chart,
    build_finish_probability_strip,
    build_race_trace_chart,
    build_stint_chart,
)
from f1si.plots.simulate import prepare_fan_chart_data, prepare_quantile_dotplot_data
from f1si.ui_theme import ASPHALT, FOG, RECOMMENDATION, contrast_ratio


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


def test_probability_strip_aggregates_known_quantiles_into_one_cell_per_place() -> None:
    sample = np.repeat(np.arange(1, 11, dtype=np.int64), 10)
    probabilities = (np.arange(100, dtype=np.float64) + 0.5) / 100.0
    expected = np.quantile(sample, probabilities, method="inverted_cdf").astype(np.int64)
    labels = (
        "Stay out",
        "Box now M",
        "Box +1 lap M",
        "Box +2 laps H",
        "Box +3 laps H",
        "Box +4 laps H",
    )
    quantile_rows = tuple(tuple(int(value) for value in expected) for _ in labels)
    data = prepare_quantile_dotplot_data(
        labels,
        quantile_rows,
        mean_finish=float(sample.mean()),
        n_cars=10,
        simulation_count=len(sample),
    )

    spec = build_finish_probability_strip(data).to_dict()
    assert spec["height"] >= 230
    layers = spec["layer"]
    assert isinstance(layers, list)
    cells = [cell for layer in layers for cell in _inline_values(spec, layer)]

    assert len(cells) == 5 * 10
    assert {cell["action"] for cell in cells} == set(labels[:5])
    assert {(cell["action"], cell["position"]) for cell in cells} == {
        (label, position) for label in labels[:5] for position in range(1, 11)
    }
    for cell in cells:
        assert cell["probability"] == 0.1
    color_ranges = [layer["encoding"]["color"]["scale"]["range"] for layer in layers]
    assert color_ranges == [
        ["#382D50", RECOMMENDATION],
        ["#30353A", "#C5C9CD"],
    ]


def test_fan_chart_uses_purple_nested_bands_labeled_at_race_finish() -> None:
    history = np.asarray(
        [[1, 2, 3, 3, 3], [2, 4, 5, 5, 5], [3, 5, 7, 7, 7], [5, 7, 9, 9, 9]],
        dtype=np.int64,
    )
    data = prepare_fan_chart_data(history, first_lap=53, n_cars=10)
    spec = build_fan_chart(data).to_dict()
    layers = spec["layer"]
    assert isinstance(layers, list)
    assert "title" not in spec
    x_axis = layers[0]["encoding"]["x"]
    assert x_axis["title"] == "Lap"
    assert x_axis["scale"]["domain"] == [53, 57]
    y_axis = layers[0]["encoding"]["y"]["axis"]
    assert y_axis["grid"] is True
    area_colors = [layer["mark"]["color"] for layer in layers if layer["mark"]["type"] == "area"]
    assert area_colors[-1] == RECOMMENDATION
    assert len(set(area_colors)) == 3
    assert min(contrast_ratio(color, ASPHALT) for color in area_colors) >= 3.0
    label_layer = next(layer for layer in layers if layer["mark"]["type"] == "text")
    labels = _inline_values(spec, label_layer)
    dash = "\N{EN DASH}"
    assert {row["label"] for row in labels} == {
        f"10th{dash}90th",
        f"25th{dash}75th",
        f"40th{dash}60th",
    }
    label_rows = sorted(cast(float, row["position"]) for row in labels)
    assert len(set(label_rows)) == 3
    assert min(b - a for a, b in pairwise(label_rows)) >= 2.0
    assert {row["lap"] for row in labels} == {57}


def test_gap_trace_highlights_selected_driver_and_stops_at_cutoff() -> None:
    rows = (
        {
            "driver_code": "ALO",
            "team_name": "Aston Martin",
            "lap": 14,
            "gap_to_leader_s": 15.0,
            "teammate_dash": False,
            "driver_label": "ALO PB",
            "label_gap_s": 16.0,
            "label_lap": 16.0,
            "is_latest": True,
        },
        {
            "driver_code": "STR",
            "team_name": "Aston Martin",
            "lap": 14,
            "gap_to_leader_s": 20.0,
            "teammate_dash": True,
            "driver_label": "STR Pit",
            "label_gap_s": 22.0,
            "label_lap": 16.0,
            "is_latest": True,
        },
    )
    chart = build_race_trace_chart(
        rows, selected_driver="ALO", selected_color="#358C75", cutoff_lap=15
    )
    assert chart is not None
    spec = chart.to_dict()
    layers = spec["layer"]
    assert isinstance(layers, list)
    x_scale = layers[0]["encoding"]["x"]["scale"]
    assert x_scale["domain"] == [0.5, 15]
    colors = [layer["mark"].get("color") for layer in layers if layer["mark"]["type"] == "line"]
    assert FOG in colors
    assert "#358C75" in colors
    labels = [layer for layer in layers if layer["mark"]["type"] == "text"]
    assert len(labels) == 2
    assert all(layer["encoding"]["text"]["field"] == "driver_label" for layer in labels)
    assert {value["driver_label"] for layer in labels for value in _inline_values(spec, layer)} == {
        "ALO",
        "STR",
    }


def test_stint_chart_labels_rows_compounds_and_outlines_recommended_stint() -> None:
    rows = (
        {
            "driver_code": "ALO",
            "compound": "SOFT",
            "compound_letter": "S",
            "first_lap": 1,
            "last_visible_lap": 15,
            "start_lap": 0.5,
            "end_lap": 15.5,
            "mid_lap": 8,
        },
        {
            "driver_code": "VER",
            "compound": "MEDIUM",
            "compound_letter": "M",
            "first_lap": 1,
            "last_visible_lap": 15,
            "start_lap": 0.5,
            "end_lap": 15.5,
            "mid_lap": 8,
        },
    )
    chart = build_stint_chart(
        rows,
        cutoff_lap=15,
        laps_total=57,
        driver_order=("ALO", "VER"),
        selected_driver="ALO",
        recommended_stop_lap=16,
        recommended_compound="MEDIUM",
    )
    assert chart is not None
    spec = chart.to_dict()
    layers = spec["layer"]
    assert isinstance(layers, list)
    outlined = next(
        layer
        for layer in layers
        if layer["mark"]["type"] == "bar" and layer["mark"].get("stroke") == RECOMMENDATION
    )
    outlined_rows = _inline_values(spec, outlined)
    assert outlined_rows[0]["driver_code"] == "ALO"
    assert outlined_rows[0]["compound_letter"] == "M"
    assert outlined_rows[0]["first_lap"] == 17
    assert outlined_rows[0]["last_visible_lap"] == 57
    letters = next(
        layer
        for layer in layers
        if layer["mark"]["type"] == "text"
        and layer["encoding"]["text"]["field"] == "compound_letter"
    )
    assert letters["encoding"]["text"]["field"] == "compound_letter"
    row_labels = next(
        layer
        for layer in layers
        if layer["mark"]["type"] == "text" and layer["encoding"]["text"]["field"] == "driver_code"
    )
    assert {value["driver_code"] for value in _inline_values(spec, row_labels)} == {"ALO", "VER"}
