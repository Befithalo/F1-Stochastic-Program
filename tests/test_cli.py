"""Command line, loader and catalog behavior (in-process, scratch data folders)."""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from f1si import paths
from f1si.cli import build_parser, main
from f1si.data import _db, asof, schema
from f1si.data.loader import load_races
from f1si.data.sources import NormalizedRace, RaceRef
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.rng import make_rng

NOW = datetime(2026, 10, 22, tzinfo=UTC)


def test_races_lists_era(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--data-dir", str(tmp_path), "load", "--source", "synthetic"]) == 0
    capsys.readouterr()
    assert main(["--data-dir", str(tmp_path), "races"]) == 0
    out = capsys.readouterr().out
    for slug in ("alpha-2023", "bravo-2023", "charlie-2024", "delta-2026"):
        assert slug in out
    assert "ground_effect_2022_2025" in out
    assert "reg_2026" in out
    delta_line = next(line for line in out.splitlines() if "delta-2026" in line)
    assert "reg_2026" in delta_line
    assert "yes (locked)" in delta_line
    assert "4 races cached (1 out-of-sample and locked)." in out


def test_races_without_cache_says_what_to_do(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--data-dir", str(tmp_path / "nothing"), "races"]) == 1
    assert "uv run f1si load" in capsys.readouterr().err


def test_load_default_source_is_openf1() -> None:
    assert build_parser().parse_args(["load"]).source == "openf1"
    assert build_parser().parse_args(["load", "--source", "synthetic"]).source == "synthetic"


def test_ctrl_c_during_load_exits_130_and_says_progress_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupted(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("f1si.cli.load_races", interrupted)
    assert main(["--data-dir", str(tmp_path), "load", "--source", "synthetic"]) == 130
    assert "Finished races are kept" in capsys.readouterr().out


def test_load_prints_one_progress_line_per_race(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--data-dir", str(tmp_path), "load", "--source", "synthetic"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if " ok " in line]
    assert len(lines) == 4
    pattern = re.compile(r"^\[\d/4\] \d{4}-\d{2} \S+\s+ok\s+[\d,]+ laps\s+\(era \w+\)$")
    for line in lines:
        assert pattern.match(line), line


class _BrokenSource(SyntheticSource):
    def fetch(self, ref: RaceRef) -> NormalizedRace:
        race = super().fetch(ref)
        tables = dict(race.tables)
        del tables["laps"]
        return NormalizedRace(ref=race.ref, tables=tables)


def test_invalid_source_data_is_reported_as_a_failed_race_and_writes_nothing(
    tmp_path: Path,
) -> None:
    db = paths.db_path(tmp_path)
    report = load_races(_BrokenSource(rng=make_rng(1)), db, (2023,), now=NOW, echo=lambda _l: None)
    assert report.loaded == []
    assert len(report.failed) == 2
    assert all("invalid data from synthetic" in f.reason for f in report.failed)
    assert not db.exists() or _db.completed_race_ids(db) == set()


def test_load_seasons_selects_seasons(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(["--data-dir", str(tmp_path), "load", "--source", "synthetic", "--seasons", "2023"])
        == 0
    )
    out = capsys.readouterr().out
    assert len([line for line in out.splitlines() if " ok " in line]) == 2
    assert "Done: 2 loaded, 0 skipped, 0 failed." in out
    assert _db.completed_race_ids(paths.db_path(tmp_path)) == {"2023-01", "2023-02"}


def test_second_load_skips_cached_races(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["--data-dir", str(tmp_path), "load", "--source", "synthetic"]
    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 0
    out = capsys.readouterr().out
    assert out.count("skipped (cached)") == 4
    assert "Done: 0 loaded, 4 skipped, 0 failed." in out


def test_load_only_one_race_by_slug(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(["--data-dir", str(tmp_path), "load", "--source", "synthetic", "--only", "alpha-2023"])
        == 0
    )
    assert "Done: 1 loaded, 0 skipped, 0 failed." in capsys.readouterr().out
    assert _db.completed_race_ids(paths.db_path(tmp_path)) == {"2023-01"}


def test_load_only_unknown_race_exits_2_with_failure_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["--data-dir", str(tmp_path), "load", "--source", "synthetic", "--only", "nope-2023"]
    )
    assert code == 2
    out = capsys.readouterr().out
    assert "Failed races:" in out
    assert "not found" in out


def test_load_unknown_season_explains_the_era_problem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--data-dir", str(tmp_path), "load", "--source", "synthetic", "--seasons", "2030"])
    assert code == 1
    err = capsys.readouterr().err
    assert "regulation era" in err
    assert "2030" in err
    assert "eras.py" in err


def test_catalog_columns_and_order(synthetic_db: Path) -> None:
    cat = asof.catalog(synthetic_db)
    assert list(cat.columns) == [
        "race_id",
        "season",
        "round",
        "slug",
        "event_name",
        "circuit",
        "era",
        "out_of_sample",
        "source",
        "load_status",
    ]
    assert cat["slug"].tolist() == ["alpha-2023", "bravo-2023", "charlie-2024", "delta-2026"]
    assert set(cat["load_status"]) == {"complete"}


def test_synthetic_db_holds_complete_races(
    synthetic_db: Path, synthetic_races: list[object]
) -> None:
    assert len(_db.completed_race_ids(synthetic_db)) == len(synthetic_races) == 4
    for name in schema.PER_RACE_TABLES:
        assert len(_db.read_table(synthetic_db, name)) > 0
