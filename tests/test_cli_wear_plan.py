"""The `wear` command on the long synthetic race (PAC-01, D-15, D-17, D-19)."""

from pathlib import Path

import pytest

from f1si.cli import main
from tests.conftest import LONG_SLUG


def _run(data_dir: Path, tmp_path: Path, *args: str) -> int:
    return main(["--data-dir", str(data_dir), "--reports-dir", str(tmp_path), *args])


def test_wear_prints_the_table(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "wear", LONG_SLUG) == 0
    out = capsys.readouterr().out
    for needle in (
        "HARD",
        "MEDIUM",
        "Fuel effect",
        "Pit loss",
        "Laps dropped",
        "compound pace offsets are not modeled",
        "95% INTERVAL",
    ):
        assert needle in out, needle
    assert "Outside the literature range" not in out  # synthetic fuel is -0.03


def test_wear_before_first_stop_says_what_to_do(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "wear", LONG_SLUG, "--lap", "20") == 1
    err = capsys.readouterr().err
    assert "Try: uv run f1si wear long-2023 --lap" in err
    assert "fuel effect" in err


def test_wear_after_first_stop_works(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "wear", LONG_SLUG, "--lap", "45") == 0
    assert "after lap 45" in capsys.readouterr().out


def test_wear_rejects_a_negative_lap(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "wear", LONG_SLUG, "--lap", "-3") == 1
    assert "Try: uv run f1si wear" in capsys.readouterr().err


def test_wear_unknown_slug(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "wear", "nowhere-2023") == 1
    assert capsys.readouterr().err.strip()
