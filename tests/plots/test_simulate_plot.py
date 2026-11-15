"""The finishing-distribution picture: prepared data, PNG output, name safety, no pyplot (D-16)."""

import subprocess
import sys
from pathlib import Path
from typing import cast

import numpy as np
import pytest
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from matplotlib.image import imread
from numpy.typing import NDArray

from f1si.plots.simulate import (
    build_fan_chart,
    build_quantile_dotplot,
    build_sim_figure,
    prepare_fan_chart_data,
    prepare_quantile_dotplot_data,
    prepare_sim_plot_data,
    render_sim_plot,
    sim_file_name,
)


def _positions() -> NDArray[np.int64]:
    rng = np.random.default_rng(3)
    return rng.integers(1, 21, size=2000).astype(np.int64)


def _data(hindsight: bool = True):  # type: ignore[no-untyped-def]
    return prepare_sim_plot_data(
        _positions(),
        slug="bahrain-2023",
        driver="ALO",
        lap=0,
        n_races=2000,
        sc_share=0.44,
        sc_source="prior only: no earlier races",
        hindsight=hindsight,
        n_cars=20,
    )


def test_prepared_data() -> None:
    data = _data()
    pos = _positions()
    assert len(data.probabilities) == 20
    assert abs(float(data.probabilities.sum()) - 1.0) < 1e-12
    assert data.mean == pytest.approx(float(pos.mean()))
    assert data.median == float(np.median(pos))
    assert data.interval == tuple(float(q) for q in np.quantile(pos, [0.05, 0.95]))
    assert "ALO" in data.title
    assert "lap 0" in data.title
    assert "prior only: no earlier races" in data.caption
    assert "hindsight simulation" in data.caption
    assert "hindsight simulation" not in _data(hindsight=False).caption


def test_figure_has_one_bar_per_position() -> None:
    fig = build_sim_figure(_data())
    assert isinstance(fig, Figure)
    ax = fig.axes[0]
    assert len(ax.patches) == 20
    assert ax.get_ylabel() == "Share of simulated races"
    assert any(ln.get_linestyle() == "--" for ln in ax.get_lines())


def test_selected_finish_summary_uses_neutral_bars_accent_marker_and_readable_roles() -> None:
    data = prepare_sim_plot_data(
        np.array([2, 4, 4, 6], dtype=np.int64),
        slug="selected-replay",
        driver="ALO",
        lap=8,
        n_races=4,
        sc_share=0.1,
        sc_source="prior only",
        hindsight=False,
        n_cars=6,
    )

    fig = build_sim_figure(data)
    ax = fig.axes[0]

    assert ax.get_xlabel() == "Finishing position"
    assert [line.get_label() for line in ax.get_lines()] == ["Mean finish at selected cutoff"]
    x_data = cast(NDArray[np.float64], ax.get_lines()[0].get_xdata())
    assert x_data[0] == pytest.approx(float(np.mean([2, 4, 4, 6])))
    assert cast(str, ax.get_lines()[0].get_color()).lower() == "#d90429"
    accent = to_rgba("#D90429")
    neutral = to_rgba("#AAB5C0")
    assert all(patch.get_facecolor() == neutral for patch in ax.patches)
    assert all(
        cast(tuple[float, float, float, float], patch.get_facecolor()) != accent
        for patch in ax.patches
    )
    assert fig.get_facecolor() == to_rgba("#1A222C")
    assert ax.get_facecolor() == to_rgba("#242E39")
    assert ax.xaxis.label.get_fontsize() == 12
    assert ax.yaxis.label.get_fontsize() == 12
    assert ax.xaxis.label.get_color() == "#F2F5F8"
    assert ax.yaxis.label.get_color() == "#F2F5F8"
    assert ax.get_xticklabels()[0].get_fontsize() == 10.5
    assert ax.get_xticklabels()[0].get_color() == "#B7C2CE"
    assert all(spine.get_edgecolor() == to_rgba("#536171") for spine in ax.spines.values())
    assert ax.yaxis.get_gridlines()[0].get_color() == "#536171"
    assert fig.texts[0].get_color() == "#F2F5F8"
    legend = ax.get_legend()
    assert legend is not None
    assert legend.get_texts()[0].get_fontsize() == 10.5
    assert legend.get_texts()[0].get_color() == "#F2F5F8"
    assert legend.get_frame().get_facecolor() == to_rgba("#1A222C")
    assert any(data.caption in text.get_text() for text in fig.texts)


def test_render_writes_a_png(tmp_path: Path) -> None:
    out = render_sim_plot(_data(), tmp_path / "x" / "a.png")
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert out.stat().st_size > 0
    image = imread(out)
    assert image[0, 0, :3] == pytest.approx(np.array([26, 34, 44]) / 255, abs=1 / 255)


def test_sim_file_name() -> None:
    assert sim_file_name("bahrain-2023", "ALO", 0) == "sim-bahrain-2023-ALO-lap0.png"
    for slug, drv, lap in (
        ("../x", "ALO", 0),
        ("Bahrain", "ALO", 0),
        ("a b", "ALO", 0),
        ("bahrain-2023", "alo", 0),
        ("bahrain-2023", "ALON", 0),
        ("bahrain-2023", "ALO", -1),
        ("bahrain-2023", "ALO", 1.5),
        ("bahrain-2023", "ALO", True),
    ):
        with pytest.raises(ValueError, match="Unsafe"):
            sim_file_name(slug, drv, lap)  # type: ignore[arg-type]


def test_module_imports_without_pyplot() -> None:
    code = (
        "import sys, f1si.plots.simulate; sys.exit(1 if 'matplotlib.pyplot' in sys.modules else 0)"
    )
    assert subprocess.run([sys.executable, "-I", "-c", code], check=False).returncode == 0


def test_quantile_dotplot_places_100_dots_at_known_midpoint_quantiles() -> None:
    sample = np.repeat(np.arange(1, 11, dtype=np.int64), 10)
    probabilities = (np.arange(100, dtype=np.float64) + 0.5) / 100.0
    expected = np.quantile(sample, probabilities, method="inverted_cdf").astype(np.int64)
    data = prepare_quantile_dotplot_data(
        ("pit now",),
        (tuple(int(value) for value in expected),),
        mean_finish=float(sample.mean()),
        n_cars=10,
        simulation_count=len(sample),
    )

    fig = build_quantile_dotplot(data)
    offsets = np.asarray(fig.axes[0].collections[0].get_offsets())

    assert offsets.shape == (100, 2)
    np.testing.assert_array_equal(offsets[:, 0], expected)
    assert fig.axes[0].get_lines()[0].get_label() == "Mean finish at selected cutoff"
    assert fig.axes[0].get_lines()[0].get_color() == "#9BA1A8"
    assert "100 simulated finishes" in data.caption


def test_fan_chart_bands_match_each_lap_percentiles_and_report_real_count() -> None:
    history = np.asarray(
        [
            [1, 1, 2],
            [2, 3, 3],
            [4, 5, 6],
            [6, 7, 8],
            [8, 9, 10],
            [10, 10, 11],
        ],
        dtype=np.int64,
    )
    data = prepare_fan_chart_data(history, first_lap=8, n_cars=12)
    levels = np.quantile(history, [0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9], axis=0)

    assert data.laps == (8, 9, 10)
    np.testing.assert_allclose(data.p10, levels[0])
    np.testing.assert_allclose(data.p25, levels[1])
    np.testing.assert_allclose(data.p40, levels[2])
    np.testing.assert_allclose(data.p50, levels[3])
    np.testing.assert_allclose(data.p60, levels[4])
    np.testing.assert_allclose(data.p75, levels[5])
    np.testing.assert_allclose(data.p90, levels[6])
    assert data.simulation_count == 6
    assert "6 simulated races" in data.caption
    assert len(build_fan_chart(data).axes[0].collections) == 3
