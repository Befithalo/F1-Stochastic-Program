"""Selected-cutoff replay output and refusal behavior."""

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
    assert "CVaR10" in out
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
