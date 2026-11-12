"""The shared clean-lap rule (PAC-01, D-02, D-22)."""

from pathlib import Path

import pandas as pd
import pytest

from f1si.laps import FADE_TRACK_CODES, fade_reason, slow_status

SRC = Path(__file__).resolve().parents[2] / "src"


def test_lap_one_and_pit_reasons() -> None:
    assert fade_reason(1, False, False, "1") == "lap 1"
    assert fade_reason(5, True, False, "1") == "pit in"
    assert fade_reason(5, False, True, "1") == "pit out"


@pytest.mark.parametrize("status", ["4", "5", "6", "7", "2671"])
def test_slow_track_status_is_faded(status: str) -> None:
    assert fade_reason(5, False, False, status) == "safety car/VSC/red"


@pytest.mark.parametrize("status", ["1", "2", "12", pd.NA, None])
def test_green_and_yellow_are_clean(status: object) -> None:
    assert fade_reason(5, False, False, status) is None


def test_pit_reason_wins_over_slow_status() -> None:
    assert fade_reason(5, True, False, "4") == "pit in"
    assert fade_reason(5, False, True, "6") == "pit out"


def test_slow_status() -> None:
    assert slow_status("2671")
    assert not slow_status("21")
    assert not slow_status(pd.NA)
    assert not slow_status(None)
    assert frozenset({"4", "5", "6", "7"}) == FADE_TRACK_CODES


def test_stint_plot_imports_the_rule_instead_of_copying_it() -> None:
    text = (SRC / "f1si" / "plots" / "stints.py").read_text(encoding="utf-8")
    assert "def _fade_reason" not in text
    assert "FADE_TRACK_CODES: Final" not in text
    assert "from f1si.laps import" in text
