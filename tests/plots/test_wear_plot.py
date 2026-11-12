"""The wear picture: prepared data, PNG output, slug safety, no pyplot (PAC-01, D-15)."""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.pace.linear import fit_linear_pace
from f1si.plots.wear import (
    prepare_wear_plot_data,
    render_wear_plot,
    wear_file_name,
)
from tests.conftest import LONG_RACE_ID


def _data(db: Path):  # type: ignore[no-untyped-def]
    snap = AsOfAccessor(db).snapshot(AsOf(LONG_RACE_ID, RACE_END))
    fit = fit_linear_pace(snap)
    return snap, fit, prepare_wear_plot_data(snap, fit)


def test_panels_points_and_lines(long_synthetic_db: Path) -> None:
    _, fit, data = _data(long_synthetic_db)
    assert set(data.panels) == {"MEDIUM", "HARD"}
    assert list(data.points.columns) == ["driver", "compound", "tire_age", "y_corrected"]
    assert len(data.points) > 100
    assert np.isfinite(data.points["y_corrected"].astype(float)).all()
    offsets = list(fit.report.driver_offsets.values())
    for c in fit.report.compounds:
        intercept, slope, half = data.lines[c.compound]
        assert intercept == pytest.approx(float(np.mean(offsets)))
        assert slope == c.wear_s_per_lap
        assert half == pytest.approx(1.96 * c.se)


def test_not_enough_data_panel_has_no_line(long_synthetic_db: Path) -> None:
    _, fit, data = _data(long_synthetic_db)
    assert "SOFT" not in data.panels or "SOFT" not in data.lines
    for name in fit.report.not_enough_data:
        assert name in data.panels
        assert name not in data.lines
        assert "not enough data" in data.panel_titles[name]


def test_corrected_value_is_hand_checkable(long_synthetic_db: Path) -> None:
    snap, fit, data = _data(long_synthetic_db)
    assert fit.fuel_effect is not None
    row = data.points.iloc[0]
    code_to_number = dict(
        zip(snap.entries["driver_code"], snap.entries["driver_number"], strict=True)
    )
    number = int(code_to_number[row["driver"]])
    laps = snap.laps
    cand = laps[
        (laps["driver_number"] == number)
        & (laps["compound"].astype(str).str.upper() == row["compound"])
        & (laps["tyre_life"] == row["tire_age"])
    ]
    offset = fit.pace_offset(number)
    assert offset is not None
    expected = {
        float(t) - fit.fuel_effect * (int(n) - 1) - offset
        for t, n in zip(cand["lap_time_s"], cand["lap_number"], strict=True)
        if t == t
    }
    assert any(abs(float(row["y_corrected"]) - e) < 1e-9 for e in expected)


def test_unidentified_fit_gives_an_empty_picture(long_synthetic_db: Path) -> None:
    snap = AsOfAccessor(long_synthetic_db).snapshot(AsOf(LONG_RACE_ID, 20))
    data = prepare_wear_plot_data(snap, fit_linear_pace(snap))
    assert data.panels == ()
    assert data.points.empty
    assert "not identified" in data.caption


def test_render_writes_a_png(long_synthetic_db: Path, tmp_path: Path) -> None:
    _, _, data = _data(long_synthetic_db)
    out = render_wear_plot(data, tmp_path / "nested" / "wear.png")
    raw = out.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(raw) > 5_000


def test_render_unidentified_still_writes(long_synthetic_db: Path, tmp_path: Path) -> None:
    snap = AsOfAccessor(long_synthetic_db).snapshot(AsOf(LONG_RACE_ID, 20))
    data = prepare_wear_plot_data(snap, fit_linear_pace(snap))
    assert render_wear_plot(data, tmp_path / "w.png").exists()


def test_wear_file_name() -> None:
    assert wear_file_name("long-2023") == "wear-long-2023.png"
    for bad in ("../evil", "A B"):
        with pytest.raises(ValueError, match="Unsafe"):
            wear_file_name(bad)


def test_module_imports_without_pyplot() -> None:
    code = "import sys, f1si.plots.wear; sys.exit(1 if 'matplotlib.pyplot' in sys.modules else 0)"
    assert subprocess.run([sys.executable, "-I", "-c", code], check=False).returncode == 0
