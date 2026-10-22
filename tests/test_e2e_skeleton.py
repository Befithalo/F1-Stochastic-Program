"""End-to-end walking-skeleton test.

Loads the seeded synthetic races into a scratch data folder with the real command line, then lists
them. It is written first (MVP order) and stays red until the `load` and `races` commands exist.
"""

import os
import subprocess
import sys
from pathlib import Path


def _run_cli(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "f1si", "--data-dir", str(data_dir), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
        timeout=120,
        check=False,
    )


def test_load_synthetic_then_list_races(tmp_path: Path) -> None:
    loaded = _run_cli(tmp_path, "load", "--source", "synthetic")
    assert loaded.returncode == 0, loaded.stderr
    assert "alpha-2023" in loaded.stdout
    assert " ok " in loaded.stdout
    assert (tmp_path / "f1si.duckdb").exists()

    listed = _run_cli(tmp_path, "races")
    assert listed.returncode == 0, listed.stderr
    for expected in (
        "alpha-2023",
        "bravo-2023",
        "charlie-2024",
        "delta-2026",
        "ground_effect_2022_2025",
        "reg_2026",
        "yes (locked)",
    ):
        assert expected in listed.stdout
