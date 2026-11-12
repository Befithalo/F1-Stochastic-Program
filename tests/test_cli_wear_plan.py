"""The `wear` and `plan` commands on the long synthetic race (PAC-01, PAC-02, D-15 to D-20)."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from f1si import paths
from f1si.cli import main
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.data.loader import load_races
from f1si.data.sources import NormalizedRace, RaceRef
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.rng import DEFAULT_SEED, make_rng
from tests.conftest import LONG_RACE_ID, LONG_SLUG, long_specs


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


def test_wear_writes_the_png(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "wear", LONG_SLUG) == 0
    png = tmp_path / f"wear-{LONG_SLUG}.png"
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    wrote = [line for line in capsys.readouterr().out.splitlines() if line.startswith("Wrote ")]
    assert len(wrote) == 1
    assert wrote[0].endswith("Open it to see fuel-corrected lap time against tyre age.")


# ---------------------------------------------------------------------------------------------
# plan command (PAC-02, D-06, D-08, D-16, D-17, D-19, D-20)
# ---------------------------------------------------------------------------------------------


def _leader_code(data_dir: Path) -> str:
    accessor = AsOfAccessor(paths.db_path(data_dir))
    end = accessor.snapshot(AsOf(LONG_RACE_ID, RACE_END))
    return str(end.cars[end.cars["position"] == 1].iloc[0]["driver_code"])


def test_plan_hindsight_prints_every_section(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "plan", LONG_SLUG, "--driver", "BBB") == 0
    out = capsys.readouterr().out
    for needle in (
        "Hindsight plan: priced with a fit from the whole race",
        "Best 1-stop",
        "Best 2-stop",
        "Top 5 overall",
        "Compared against",
        "lower bound",
        "compound pace offsets are not modeled",
        "RACE TIME",
    ):
        assert needle in out, needle
    assert "beats" not in out


def test_plan_default_driver_is_the_leader_at_the_end(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "plan", LONG_SLUG) == 0
    first_line = capsys.readouterr().out.splitlines()[0]
    assert first_line.endswith(f": {_leader_code(long_synthetic_data_dir)}")


def test_plan_best_is_not_slower_than_the_actual_strategy(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "plan", LONG_SLUG, "--driver", "CCC") == 0
    line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("Compared"))
    gap = float(line.split("(")[-1].split(" s versus")[0])
    assert gap >= 0.0


def test_plan_mid_race(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ("plan", LONG_SLUG, "--driver", "BBB", "--lap", "40")
    assert _run(long_synthetic_data_dir, tmp_path, *args) == 0
    out = capsys.readouterr().out
    assert "after lap 40" in out
    assert "Current tyre" in out
    assert "stops done" in out
    assert "Actual strategy so far" in out
    assert "Hindsight" not in out
    assert "Compared against" not in out
    assert "TIME TO FINISH" in out


def test_plan_is_deterministic(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(long_synthetic_data_dir, tmp_path, "plan", LONG_SLUG, "--driver", "DDD")
    first = capsys.readouterr().out
    _run(long_synthetic_data_dir, tmp_path, "plan", LONG_SLUG, "--driver", "DDD")
    assert capsys.readouterr().out == first


@pytest.mark.parametrize("lap", ["0", "20"])
def test_plan_refuses_when_wear_cannot_be_fitted(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], lap: str
) -> None:
    args = ("plan", LONG_SLUG, "--driver", "BBB", "--lap", lap)
    assert _run(long_synthetic_data_dir, tmp_path, *args) == 1
    err = capsys.readouterr().err
    assert "not enough laps yet to fit wear" in err
    assert "try --lap" in err


def test_plan_refuses_the_end_of_the_race_and_negative_laps(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ("plan", LONG_SLUG, "--driver", "BBB", "--lap", "57")
    assert _run(long_synthetic_data_dir, tmp_path, *args) == 1
    assert "the race is over" in capsys.readouterr().err
    args = ("plan", LONG_SLUG, "--driver", "BBB", "--lap", "-1")
    assert _run(long_synthetic_data_dir, tmp_path, *args) == 1
    assert "Try: uv run f1si plan" in capsys.readouterr().err


def test_plan_driver_errors(
    long_synthetic_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "plan", LONG_SLUG, "--driver", "ZZZ") == 1
    err = capsys.readouterr().err
    assert "AAA" in err
    assert "BBB" in err
    assert _run(long_synthetic_data_dir, tmp_path, "plan", LONG_SLUG, "--driver", "zz") == 1
    assert "three letters" in capsys.readouterr().err


class _WetSource:
    """The long synthetic race with one driver's second stint turned into INTERMEDIATE."""

    def __init__(self, inner: SyntheticSource, number: int) -> None:
        self._inner = inner
        self._number = number
        self.name = inner.name
        self.version = inner.version
        self.default_seasons = inner.default_seasons

    def list_races(self, season: int, *, now: datetime) -> list[RaceRef]:
        return self._inner.list_races(season, now=now)

    def fetch(self, ref: RaceRef) -> NormalizedRace:
        race = self._inner.fetch(ref)
        laps = race.tables["laps"].copy()
        mask = (laps["driver_number"] == self._number) & (laps["stint"] == 2)
        assert mask.any()
        laps.loc[mask, "compound"] = "INTERMEDIATE"
        return replace(race, tables={**race.tables, "laps": laps})


def test_plan_hindsight_refuses_a_driver_who_ran_on_intermediates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "wet"
    folder.mkdir()
    source = _WetSource(SyntheticSource(long_specs(), rng=make_rng(DEFAULT_SEED)), 11)
    load_races(
        source,
        paths.db_path(folder),
        (2023,),
        now=datetime(2026, 10, 22, tzinfo=UTC),
        echo=lambda _line: None,
    )
    wet_code = (
        AsOfAccessor(paths.db_path(folder))
        .snapshot(AsOf(LONG_RACE_ID, RACE_END))
        .entries.set_index("driver_number")["driver_code"][11]
    )
    other = "AAA" if wet_code != "AAA" else "BBB"
    assert _run(folder, tmp_path, "plan", LONG_SLUG, "--driver", str(wet_code)) == 1
    err = capsys.readouterr().err
    assert "wet and intermediate strategy is out of scope" in err
    assert "Try: uv run f1si plan long-2023 --driver" in err
    assert _run(folder, tmp_path, "plan", LONG_SLUG, "--driver", other) == 0
