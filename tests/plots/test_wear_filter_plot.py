"""The wear-filter picture: prepared data, PNG output, name safety, no pyplot (PAC-03)."""

import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from matplotlib.collections import LineCollection

from f1si.pace.kalman import (
    CutoffRow,
    LapRow,
    ResolvedPriors,
    StintFilterResult,
    WearPrior,
    cutoff_row,
)
from f1si.plots.wear_filter import (
    build_wear_filter_figure,
    prepare_wear_filter_data,
    render_wear_filter_plot,
    wear_filter_file_name,
)

_PRIORS = ResolvedPriors(
    prior=WearPrior(rate_mean=0.08, rate_sd=0.05, fuel_sd=0.025, sigma=0.3),
    fuel_mean=-0.05,
    rate_source="prior only: fit not identified yet",
    fuel_source="prior only: fuel effect not identified yet",
    noise_source="prior only: noise not estimated yet",
)


def _row(lap: int, stint: int, compound: str, used: bool = True) -> CutoffRow:
    sd = 0.05 / math.sqrt(lap)
    mean = 0.07 + 0.001 * lap
    lap_row = LapRow(
        lap, lap, used, None if used else "pit", mean, sd, mean - 2 * sd, mean + 2 * sd
    )
    return CutoffRow(lap, stint, compound, _PRIORS, lap_row)


def _rows() -> list[CutoffRow]:
    return [_row(k, 1, "MEDIUM", used=k != 3) for k in range(1, 9)] + [
        _row(k, 2, "HARD") for k in range(9, 16)
    ]


def _data(full: bool = True):  # type: ignore[no-untyped-def]
    return prepare_wear_filter_data(
        list(reversed(_rows())),
        slug="long-2023",
        driver="ALO",
        hindsight={"MEDIUM": 0.08, "HARD": 0.06},
        is_full_race=full,
        last_lap=15,
    )


def test_prepare_sorted_parallel_tuples() -> None:
    d = _data()
    assert d.laps == tuple(range(1, 16))
    assert len(d.rate) == len(d.lo) == len(d.hi) == len(d.used) == len(d.compounds) == 15
    assert d.stint_starts == (1, 9)
    assert all(math.isfinite(v) for v in (*d.rate, *d.lo, *d.hi))
    assert "full race" in d.title
    assert "as of lap 15" in _data(full=False).title


def test_file_name_and_unsafe_values() -> None:
    assert wear_filter_file_name("bahrain-2023", "ALO") == "wear-filter-bahrain-2023-ALO.png"
    for slug in ("Bahrain", "a/b", "..", ""):
        with pytest.raises(ValueError, match="Unsafe race slug"):
            wear_filter_file_name(slug, "ALO")
    for code in ("alo", "AL", "../x", "ALOS", ""):
        with pytest.raises(ValueError, match="Unsafe driver code"):
            wear_filter_file_name("bahrain-2023", code)


def test_figure_has_band_line_boundaries_and_hindsight() -> None:
    fig = build_wear_filter_figure(_data())
    ax = fig.axes[0]
    assert len(ax.collections) >= 2  # one band per stint (plus scatter points)
    vlines = [ln for ln in ax.get_lines() if np.asarray(ln.get_xdata()).tolist() == [9.0, 9.0]]
    assert len(vlines) == 1
    legend = ax.get_legend()
    assert legend is not None
    labels = [t.get_text() for t in legend.get_texts()]
    assert any("hindsight" in t for t in labels)
    hlines = [c for c in ax.collections if isinstance(c, LineCollection)]
    assert len(hlines) == 2  # one dashed hindsight line per compound


def test_render_writes_png_and_parent_dirs(tmp_path: Path) -> None:
    out = render_wear_filter_plot(_data(), tmp_path / "deep" / "w.png")
    raw = out.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(raw) > 5_000


def test_empty_rows_still_render(tmp_path: Path) -> None:
    d = prepare_wear_filter_data(
        [], slug="long-2023", driver="ALO", hindsight={}, is_full_race=False, last_lap=0
    )
    assert render_wear_filter_plot(d, tmp_path / "e.png").exists()


def test_cutoff_row_lookup() -> None:
    rows = tuple(_row(k, 1, "MEDIUM").row for k in range(1, 5))
    res = StintFilterResult(14, 1, "MEDIUM", _PRIORS, rows, 4, 0, True, 4)
    found = cutoff_row([res], 14, 3)
    assert found is not None
    assert found.row.race_lap == 3
    assert found.stint == 1
    assert found.compound == "MEDIUM"
    behind = cutoff_row([res], 14, 9)  # newest visible lap at or before the cutoff
    assert behind is not None
    assert behind.row.race_lap == 4
    assert behind.cutoff_lap == 9
    assert cutoff_row([res], 14, 0) is None
    assert cutoff_row([res], 99, 3) is None


def test_module_imports_without_pyplot() -> None:
    code = (
        "import sys, f1si.plots.wear_filter; "
        "sys.exit(1 if 'matplotlib.pyplot' in sys.modules else 0)"
    )
    assert subprocess.run([sys.executable, "-I", "-c", code], check=False).returncode == 0
