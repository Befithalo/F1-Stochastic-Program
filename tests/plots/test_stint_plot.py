"""Stint plot: fade classes, ordering, filtering, clipping, stint markers, panels and the PNG."""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, RaceSnapshot
from f1si.plots.stints import (
    COMPOUND_COLORS,
    StintPlotData,
    UnknownDriverError,
    build_figure,
    plot_file_name,
    prepare_stint_plot_data,
    render_stint_plot,
)

SRC = Path(__file__).resolve().parents[2] / "src"


def _snap(db: Path, slug_id: str, lap: int | None = None) -> RaceSnapshot:
    at = AsOf(slug_id, RACE_END if lap is None else lap)
    return AsOfAccessor(db).snapshot(at)


@pytest.fixture(scope="module")
def alpha(synthetic_db: Path) -> StintPlotData:
    return prepare_stint_plot_data(_snap(synthetic_db, "2023-01"))


def test_alpha_order_and_point_count(alpha: StintPlotData) -> None:
    assert alpha.drivers == ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")
    assert len(alpha.points) == 72
    assert alpha.skipped_laps == 0
    assert "2023" in alpha.title
    assert "full race" in alpha.title
    assert alpha.title.isascii()


def test_fade_classes(alpha: StintPlotData) -> None:
    pts = alpha.points
    lap1 = pts[pts["lap_number"] == 1]
    assert (lap1["fade_reason"] == "lap 1").all()
    aaa = pts[pts["driver_code"] == "AAA"].set_index("lap_number")
    assert aaa.loc[6, "fade_reason"] == "pit in"
    assert aaa.loc[7, "fade_reason"] == "pit out"
    # Lap 8 is a VSC lap for everyone; cars that pit on lap 7 show "pit out" (higher priority).
    lap8 = pts[pts["lap_number"] == 8]
    assert lap8["faded"].all()
    assert set(lap8["fade_reason"]) <= {"safety car/VSC/red", "pit out"}
    assert (lap8["fade_reason"] == "safety car/VSC/red").sum() >= 3
    clean = pts[~pts["faded"]]
    assert len(clean) > 0
    assert clean["fade_reason"].isna().all()
    assert (pts["faded"] == pts["fade_reason"].notna()).all()


def test_clean_points_have_no_slow_track_status(synthetic_db: Path) -> None:
    snap = _snap(synthetic_db, "2023-01")
    data = prepare_stint_plot_data(snap)
    code_of = {
        int(n): str(c)
        for n, c in zip(snap.entries["driver_number"], snap.entries["driver_code"], strict=True)
    }
    status: dict[tuple[str, int], str] = {}
    for number, lap, ts in zip(
        snap.laps["driver_number"], snap.laps["lap_number"], snap.laps["track_status"], strict=True
    ):
        status[(code_of[int(number)], int(lap))] = str(ts)
    pts = data.points
    for code, lap, faded, reason in zip(
        pts["driver_code"], pts["lap_number"], pts["faded"], pts["fade_reason"], strict=True
    ):
        has_slow = any(c in status[(str(code), int(lap))] for c in "4567")
        if not faded:
            assert not has_slow
        if reason == "safety car/VSC/red":
            assert has_slow


def test_clipping_and_limits(alpha: StintPlotData) -> None:
    pts = alpha.points
    lo, hi = alpha.y_limits
    clean = pts[~pts["faded"]]["lap_time_s"].astype(float)
    assert lo == pytest.approx(clean.min() - 0.5)
    assert hi == pytest.approx(np.percentile(clean, 98) + 1.0)
    out = pts[pts["fade_reason"] == "pit out"]
    assert len(out) == 6
    assert bool(out["clipped"].all())
    assert (out["y_plot"].astype(float) == hi).all()
    free = pts[~pts["clipped"].astype(bool)]
    assert (free["y_plot"].astype(float) == free["lap_time_s"].astype(float)).all()


def test_driver_filter(synthetic_db: Path) -> None:
    snap = _snap(synthetic_db, "2023-01")
    data = prepare_stint_plot_data(snap, drivers=["bbb", "AAA"])
    assert data.drivers == ("AAA", "BBB")
    assert set(data.points["driver_code"]) == {"AAA", "BBB"}
    with pytest.raises(UnknownDriverError, match="AAA"):
        prepare_stint_plot_data(snap, drivers=["ZZZ"])
    with pytest.raises(ValueError, match="three letters"):
        prepare_stint_plot_data(snap, drivers=["A1"])


def test_pit_lane_and_retired_driver(synthetic_db: Path) -> None:
    data = prepare_stint_plot_data(_snap(synthetic_db, "2023-02"))
    assert any("pit lane" in t for t in data.panel_titles.values())
    retired = [c for c in data.drivers if (data.points["driver_code"] == c).sum() == 4]
    assert len(retired) == 1


def test_mid_race_cutoff(synthetic_db: Path) -> None:
    snap = _snap(synthetic_db, "2023-01", 5)
    data = prepare_stint_plot_data(snap)
    assert snap.cutoff_s is not None
    ends = snap.laps.set_index(["driver_number", "lap_number"])["lap_end_s"]
    assert bool((ends <= snap.cutoff_s).all())
    assert len(data.points) == len(snap.laps)


def test_stint_starts(synthetic_db: Path, alpha: StintPlotData) -> None:
    assert alpha.stint_starts["AAA"] == (7,)
    assert alpha.stint_starts["BBB"] == (8,)
    early = prepare_stint_plot_data(_snap(synthetic_db, "2023-01", 3))
    assert all(v == () for v in early.stint_starts.values())


def test_stint_boundary_line_drawn(alpha: StintPlotData) -> None:
    fig = build_figure(alpha)
    ax = fig.axes[0]
    assert len(ax.lines) == 1
    assert ax.lines[0].get_linestyle() == ":"


def test_lap_zero_gives_empty_plot(synthetic_db: Path) -> None:
    data = prepare_stint_plot_data(_snap(synthetic_db, "2023-01", 0))
    assert len(data.points) == 0
    assert data.y_limits == (0.0, 1.0)
    assert data.skipped_laps == 0
    fig = build_figure(data)
    assert sum(ax.get_visible() for ax in fig.axes) == 6


def test_panel_counts(alpha: StintPlotData, synthetic_db: Path) -> None:
    assert sum(ax.get_visible() for ax in build_figure(alpha).axes) == 6
    two = prepare_stint_plot_data(_snap(synthetic_db, "2023-01"), drivers=["AAA", "BBB"])
    fig = build_figure(two)
    assert sum(ax.get_visible() for ax in fig.axes) == 2


def test_unknown_compound_gets_grey(synthetic_db: Path) -> None:
    data = prepare_stint_plot_data(_snap(synthetic_db, "2023-01"))
    assert set(data.points["color"]) <= set(COMPOUND_COLORS.values()) | {"#888888"}


def test_render_writes_png(alpha: StintPlotData, tmp_path: Path) -> None:
    out = render_stint_plot(alpha, tmp_path / "deep" / "folder" / "alpha-2023.png")
    raw = out.read_bytes()
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(raw) > 10_000


def test_plot_file_name() -> None:
    assert plot_file_name("bahrain-2023", None) == "bahrain-2023.png"
    assert plot_file_name("bahrain-2023", ["VER", "HAM"]) == "bahrain-2023-ham-ver.png"
    for bad in ("../x", "a/b", "..", "A b"):
        with pytest.raises(ValueError, match="Unsafe"):
            plot_file_name(bad, None)
    with pytest.raises(ValueError, match="three letters"):
        plot_file_name("bahrain-2023", ["../x"])


def test_no_pyplot_in_src() -> None:
    offenders = [
        str(p)
        for p in SRC.rglob("*.py")
        if any(
            line.strip().startswith(("import matplotlib.pyplot", "from matplotlib import pyplot"))
            for line in p.read_text(encoding="utf-8").splitlines()
        )
    ]
    assert offenders == []


def test_module_imports_without_pyplot() -> None:
    code = "import sys, f1si.plots.stints; sys.exit(1 if 'matplotlib.pyplot' in sys.modules else 0)"
    assert subprocess.run([sys.executable, "-I", "-c", code], check=False).returncode == 0
