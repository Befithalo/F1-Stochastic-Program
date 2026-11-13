"""Selected-cutoff replay output and refusal behavior."""

import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

import pytest

from f1si import cli
from f1si.cli import build_parser, main
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
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
    subparsers = build_parser()._subparsers._group_actions[0].choices
    help_text = subparsers["replay"].format_help()
    assert "[0, 1]" in help_text
    assert "default 0.5" in help_text


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


def test_full_replay_emits_every_cutoff_and_marks_unsupported_cutoffs(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db)
    assert _run(long_synthetic_data_dir, "replay", LONG_SLUG, "--driver", code, "--n", "12") == 0
    out = capsys.readouterr().out
    laps = [int(line.split()[1]) for line in out.splitlines() if line.startswith("Cutoff lap ")]
    assert laps == list(range(max(laps) + 1))
    assert any("unavailable" in line.lower() for line in out.splitlines())
    assert any("Recommendation:" in line for line in out.splitlines())


def test_selected_replay_matches_full_replay_cutoff_block(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db)
    args = ("replay", LONG_SLUG, "--driver", code, "--n", "12")
    assert _run(long_synthetic_data_dir, *args) == 0
    full = capsys.readouterr().out
    assert _run(long_synthetic_data_dir, *args, "--lap", "35") == 0
    selected = capsys.readouterr().out
    full_block = full.split("Cutoff lap 35", maxsplit=1)[1].split("Cutoff lap 36", maxsplit=1)[0]
    selected_block = selected.split("Cutoff lap 35", maxsplit=1)[1]
    assert selected_block.strip() == full_block.strip()


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
