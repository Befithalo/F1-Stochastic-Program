"""Selected-cutoff replay output and refusal behavior."""

import argparse
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from f1si import cli
from f1si.cli import build_parser, main
from f1si.data import asof
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.pace.kalman import GENERIC_SIGMA_S
from f1si.pace.linear import _classify
from f1si.pace.sparse_fallback import SparsePaceFallback
from f1si.sim.constants import MAX_RACES
from f1si.sim.numpy_backend import NumpySimulator
from tests.conftest import LONG_RACE_ID, LONG_SLUG


def _run(data_dir: Path, *args: str) -> int:
    return main(["--data-dir", str(data_dir), *args])


def _code(db: Path) -> str:
    cars = AsOfAccessor(db).snapshot(AsOf(LONG_RACE_ID, RACE_END)).cars
    return str(sorted(cars["driver_code"])[0])


def test_selected_cutoff_replay_prints_ranked_options(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db)
    assert (
        _run(
            long_synthetic_data_dir,
            "replay",
            LONG_SLUG,
            "--driver",
            code,
            "--lap",
            "35",
            "--n",
            "12",
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "after lap 35" in out
    assert all(heading in out for heading in ("MEAN", "SPREAD", "CVAR10", "SCORE"))
    assert "CVaR10" in out
    assert "Recommendation:" in out
    assert "Reason:" in out


def test_sparse_fallback_replay_returns_ranked_options_at_lap_zero_and_fallback_lap(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db)
    for lap in (0, 5):
        assert (
            _run(
                long_synthetic_data_dir,
                "replay",
                LONG_SLUG,
                "--driver",
                code,
                "--lap",
                str(lap),
                "--n",
                "12",
            )
            == 0
        )
        output = capsys.readouterr().out
        assert "Status: fallback" in output
        assert all(key in output for key in ("MEAN", "SPREAD", "CVAR10", "SCORE"))
        assert "Recommendation:" in output
        assert "cutoff-visible clean laps" in output
        assert "generic DEC-091" in output
        assert "[ASSUMED] 1.0 s" in output
        assert "uncalibrated" in output
        assert "unavailable" not in output


def test_sparse_fallback_noise_floor_is_generic_at_lap_zero(
    long_synthetic_db: Path,
) -> None:
    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf(LONG_RACE_ID, 0))
    fallback = SparsePaceFallback(snapshot)
    assert fallback.sigma_sparse == GENERIC_SIGMA_S
    assert fallback.visible_clean_laps == 0
    assert set(fallback.driver_offsets.values()) == {0.0}
    assert fallback.pace_offset_sd_s == 1.0


def test_sparse_fallback_uses_cutoff_clean_residuals_and_robust_noise(
    long_synthetic_db: Path,
) -> None:
    snapshot = AsOfAccessor(long_synthetic_db).snapshot(AsOf(LONG_RACE_ID, 5))
    fallback = SparsePaceFallback(snapshot)
    clean = _classify(snapshot.laps)
    clean = clean.loc[clean["reason"].isna()].copy()
    fuel = -0.05
    wear = {"SOFT": 0.10, "MEDIUM": 0.08, "HARD": 0.06}
    residuals = (
        clean["time"].to_numpy()
        - fuel * (clean["lap"].to_numpy() - 1.0)
        - clean["compound"].map(wear).to_numpy() * clean["age"].to_numpy()
    )
    clean["residual"] = residuals
    centers = clean.groupby("driver")["residual"].median()
    field_center = float(centers.median())
    for driver_number, center in centers.items():
        number = cast(int, driver_number)
        assert fallback.driver_offsets[number] == pytest.approx(center - field_center)
    within_driver = np.array(
        [
            value - centers.loc[number]
            for number, value in zip(clean["driver"], residuals, strict=True)
        ]
    )
    expected_sigma = max(
        GENERIC_SIGMA_S,
        1.4826 * float(np.median(np.abs(within_driver - np.median(within_driver)))),
    )
    assert fallback.sigma_sparse == pytest.approx(expected_sigma)


@pytest.mark.parametrize(
    "args",
    [
        ("not-a-race-2023", "--driver", "AAA", "--lap", "10"),
        (LONG_SLUG, "--driver", "ZZZ", "--lap", "10"),
        (LONG_SLUG, "--driver", "AAA", "--lap", "-1"),
        (LONG_SLUG, "--driver", "AAA", "--lap", "999"),
        (LONG_SLUG, "--driver", "AAA", "--lap", "10", "--n", "0"),
        (LONG_SLUG, "--driver", "AAA", "--lap", "10", "--n", "-1"),
        (LONG_SLUG, "--driver", "AAA", "--lap", "10", "--risk", "nan"),
        (LONG_SLUG, "--driver", "AAA", "--lap", "10", "--risk", "inf"),
        (LONG_SLUG, "--driver", "AAA", "--lap", "10", "--risk", "1.1"),
    ],
)
def test_bad_replay_inputs_refuse_before_running(
    long_synthetic_data_dir: Path, capsys: pytest.CaptureFixture[str], args: tuple[str, ...]
) -> None:
    assert _run(long_synthetic_data_dir, "replay", *args) == 1
    err = capsys.readouterr().err
    assert err.strip()
    assert "Traceback" not in err


def test_replay_parser_defaults() -> None:
    args = build_parser().parse_args(["replay", "bahrain-2023", "--driver", "ALO", "--lap", "20"])
    assert (args.lap, args.n, args.risk) == (20, 50000, 0.5)
    parser = build_parser()
    subparsers = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    help_text = " ".join(subparsers.choices["replay"].format_help().split())
    assert "[0, 1]" in help_text
    assert "default 0.5" in help_text
    assert "--risk-aversion" in help_text
    assert "default 50000" in help_text
    assert "0 to one less than the race lap count" in help_text
    assert "catalog (for example bahrain-2023)" in help_text
    assert "known driver code for that race" in help_text


def test_replay_parser_accepts_risk_aversion_alias() -> None:
    args = build_parser().parse_args(
        ["replay", "bahrain-2023", "--driver", "ALO", "--risk-aversion", "0.25"]
    )
    assert args.risk == 0.25


def test_replay_parser_allows_full_series() -> None:
    args = build_parser().parse_args(["replay", "bahrain-2023", "--driver", "ALO"])
    assert args.lap is None


class ReplayParserTest(unittest.TestCase):
    def test_full_series_does_not_require_a_selected_lap(self) -> None:
        with redirect_stderr(StringIO()):
            try:
                args = build_parser().parse_args(["replay", "bahrain-2023", "--driver", "ALO"])
            except SystemExit:
                self.fail("full replay parser requires --lap")
        assert args.lap is None


def test_full_replay_emits_every_cutoff_and_marks_fallback_cutoffs(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db)
    assert _run(long_synthetic_data_dir, "replay", LONG_SLUG, "--driver", code, "--n", "12") == 0
    out = capsys.readouterr().out
    laps = [
        int(line.split()[2].rstrip(":"))
        for line in out.splitlines()
        if line.startswith("Cutoff lap ")
    ]
    assert laps == list(range(max(laps) + 1))
    assert "Status: unavailable" not in out
    assert "Status: fallback" in out
    assert out.count("Recommendation:") == len(laps)
    reasons = [
        line.removeprefix("Reason: ") for line in out.splitlines() if line.startswith("Reason: ")
    ]
    assert reasons
    assert all(reason.endswith(".") for reason in reasons)


def test_selected_replay_matches_full_replay_cutoff_block(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db)
    args = ("replay", LONG_SLUG, "--driver", code, "--n", "12")
    assert _run(long_synthetic_data_dir, *args) == 0
    full = capsys.readouterr().out
    full_lines = full.splitlines()
    for lap in (0, 5, 35):
        assert _run(long_synthetic_data_dir, *args, "--lap", str(lap)) == 0
        selected = capsys.readouterr().out
        start = next(
            i for i, line in enumerate(full_lines) if line.startswith(f"Cutoff lap {lap}:")
        )
        end = next(
            (
                i
                for i in range(start + 1, len(full_lines))
                if full_lines[i].startswith("Cutoff lap ")
            ),
            len(full_lines),
        )
        full_block = "\n".join(full_lines[start:end])
        assert selected.strip() == full_block.strip()


def test_invalid_replay_values_are_refused_before_state_or_simulation(
    long_synthetic_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append("started")
        raise AssertionError("replay computation started for invalid input")

    monkeypatch.setattr(cli, "build_race_state", forbidden)
    monkeypatch.setattr(NumpySimulator, "_simulate", forbidden)
    assert (
        _run(
            long_synthetic_data_dir,
            "replay",
            "not-a-race-2023",
            "--driver",
            "AAA",
            "--lap",
            "10",
        )
        == 1
    )
    assert (
        _run(
            long_synthetic_data_dir,
            "replay",
            LONG_SLUG,
            "--driver",
            "ZZZ",
            "--lap",
            "10",
        )
        == 1
    )
    assert _run(long_synthetic_data_dir, "replay", LONG_SLUG, "--driver", "AAA", "--lap", "-1") == 1
    assert (
        _run(
            long_synthetic_data_dir,
            "replay",
            LONG_SLUG,
            "--driver",
            "AAA",
            "--lap",
            "999",
        )
        == 1
    )
    assert (
        _run(
            long_synthetic_data_dir,
            "replay",
            LONG_SLUG,
            "--driver",
            "AAA",
            "--lap",
            "10",
            "--n",
            "0",
        )
        == 1
    )
    assert (
        _run(
            long_synthetic_data_dir,
            "replay",
            LONG_SLUG,
            "--driver",
            "AAA",
            "--lap",
            "10",
            "--risk",
            "nan",
        )
        == 1
    )
    assert calls == []
    assert "Traceback" not in capsys.readouterr().err


def test_replay_rejects_simulation_count_above_limit_before_loading_race(
    long_synthetic_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("race data or state was accessed for an invalid simulation count")

    monkeypatch.setattr(asof, "resolve_slug", forbidden)
    monkeypatch.setattr(cli, "build_race_state", forbidden)

    assert (
        _run(
            long_synthetic_data_dir,
            "replay",
            "not-a-race-2023",
            "--driver",
            "AAA",
            "--n",
            str(MAX_RACES + 1),
        )
        == 1
    )
    err = capsys.readouterr().err
    assert f"--n must be at most {MAX_RACES}" in err
    assert "Traceback" not in err


def test_replay_help_documents_simulation_count_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as result:
        build_parser().parse_args(["replay", "--help"])

    assert result.value.code == 0
    assert f"up to {MAX_RACES}" in capsys.readouterr().out
