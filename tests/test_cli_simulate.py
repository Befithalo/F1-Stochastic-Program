"""The `simulate` command on synthetic data (SIM-01, REG-01, D-16, D-17)."""

from pathlib import Path

import pytest

from f1si.cli import build_parser, main
from f1si.data import asof
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from tests.conftest import (
    LONG_RACE_ID,
    LONG_SLUG,
    SC_HISTORY_CURRENT_RACE_ID,
    SC_HISTORY_CURRENT_SLUG,
)


def _run(data_dir: Path, tmp_path: Path, *args: str) -> int:
    return main(["--data-dir", str(data_dir), "--reports-dir", str(tmp_path), *args])


def _code(db: Path, race_id: str, index: int = 0) -> str:
    cars = AsOfAccessor(db).snapshot(AsOf(race_id, RACE_END)).cars
    return str(sorted(cars["driver_code"])[index])


def _rows(out: str) -> str:
    """The distribution rows, the summary line and the safety-car share (no runtime)."""
    start = out.index("P1 ")
    return out[start : out.index("runtime", start)]


def test_hindsight_success(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db, LONG_RACE_ID)
    assert (
        _run(
            long_synthetic_data_dir, tmp_path, "simulate", LONG_SLUG, "--driver", code, "--n", "400"
        )
        == 0
    )
    out = capsys.readouterr().out
    for needle in (
        "hindsight simulation",
        "prior only: no earlier races",
        "mean",
        "median",
        "90%",
        "Safety car in",
        "runtime",
        f"P{20} ",
        "Wrote",
    ):
        assert needle in out, needle
    assert "from the free-track optimizer" in out
    assert "fallback" in out
    for k in range(1, 21):
        assert f"P{k} " in out
    assert (tmp_path / f"sim-{LONG_SLUG}-{code}-lap0.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_lap_mode_uses_only_known_data(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db, LONG_RACE_ID)
    args = ("simulate", LONG_SLUG, "--driver", code, "--n", "300")
    assert _run(long_synthetic_data_dir, tmp_path, *args, "--lap", "45") == 0
    out = capsys.readouterr().out
    assert "hindsight simulation" not in out.lower()
    assert "after lap 45" in out
    assert (tmp_path / f"sim-{LONG_SLUG}-{code}-lap45.png").exists()


def test_lap_mode_refuses_an_unidentified_fit(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db, LONG_RACE_ID)
    args = ("simulate", LONG_SLUG, "--driver", code, "--n", "300", "--lap", "20")
    assert _run(long_synthetic_data_dir, tmp_path, *args) == 1
    err = capsys.readouterr().err
    assert "try --lap" in err
    assert "uv run f1si simulate long-2023" in err
    assert "Traceback" not in err


@pytest.mark.parametrize(
    "extra",
    [
        ["--n", "1"],
        ["--n", "1000001"],
        ["--lap", "-1"],
        ["--seed", "-1"],
    ],
)
def test_bounds_are_refused_with_a_try_line(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    extra: list[str],
) -> None:
    code = _code(long_synthetic_db, LONG_RACE_ID)
    assert (
        _run(long_synthetic_data_dir, tmp_path, "simulate", LONG_SLUG, "--driver", code, *extra)
        == 1
    )
    err = capsys.readouterr().err.strip()
    assert "Traceback" not in err
    assert len(err.splitlines()) == 1
    assert "Try: uv run f1si simulate" in err
    assert list(tmp_path.glob("sim-*")) == []


@pytest.mark.parametrize("driver", ["alo", "ALON", "ZZZ", "A1B"])
def test_bad_driver_codes_are_refused(
    long_synthetic_data_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    driver: str,
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "simulate", LONG_SLUG, "--driver", driver) == 1
    err = capsys.readouterr().err.strip()
    assert "Traceback" not in err
    assert "Try: uv run f1si simulate" in err


def test_non_numeric_n_exits_nonzero(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        _run(
            long_synthetic_data_dir,
            tmp_path,
            "simulate",
            LONG_SLUG,
            "--driver",
            "AAA",
            "--n",
            "abc",
        )
    assert exc.value.code != 0
    assert "Traceback" not in capsys.readouterr().err


def test_unknown_slug(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        _run(long_synthetic_data_dir, tmp_path, "simulate", "nowhere-2023", "--driver", "AAA") == 1
    )
    assert capsys.readouterr().err.strip()


def test_2026_race_is_refused(
    synthetic_db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cat = asof.catalog(synthetic_db)
    slug = str(cat[cat["out_of_sample"].astype(bool)]["slug"].iloc[0])
    assert _run(synthetic_db.parent, tmp_path, "simulate", slug, "--driver", "AAA") == 1
    assert "out-of-sample" in capsys.readouterr().err


def test_same_seed_same_rows_and_different_seed_differs(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db, LONG_RACE_ID, 12)
    base = ("simulate", LONG_SLUG, "--driver", code, "--n", "2000")
    texts = []
    for seed in ("5", "5", "6"):
        assert _run(long_synthetic_data_dir, tmp_path, *base, "--seed", seed) == 0
        texts.append(_rows(capsys.readouterr().out))
    assert texts[0] == texts[1]
    # The synthetic grid never reshuffles, so the finishing rows can be the same for every seed;
    # the simulated safety-car share is the quantity that must move with the seed.
    assert texts[0] != texts[2]


def test_sc_rate_comes_from_earlier_races(
    sc_history_db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _code(sc_history_db, SC_HISTORY_CURRENT_RACE_ID)
    args = ("simulate", SC_HISTORY_CURRENT_SLUG, "--driver", code, "--n", "300")
    assert _run(sc_history_db.parent, tmp_path, *args) == 0
    out = capsys.readouterr().out
    assert "prior only" not in out
    assert "earlier SC deployments over" in out
    assert "4 earlier SC deployments over 200 laps" in out


def test_parser_lists_simulate() -> None:
    parser = build_parser()
    assert "simulate" in parser.format_help()
    ns = parser.parse_args(["simulate", "x-2023", "--driver", "ALO"])
    assert (ns.n, ns.seed, ns.lap) == (50000, 0, None)
