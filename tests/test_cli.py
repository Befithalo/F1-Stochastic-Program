"""Command line, loader and catalog behavior (in-process, scratch data folders)."""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from f1si import paths
from f1si.cli import main
from f1si.data import _db, asof, schema
from f1si.data.loader import load_races
from f1si.data.sources import NormalizedRace, RaceRef, SourceError
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


def test_load_requires_source(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--data-dir", str(tmp_path), "load"])
    assert exc.value.code == 2


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


def test_invalid_source_data_writes_nothing(tmp_path: Path) -> None:
    db = paths.db_path(tmp_path)
    with pytest.raises(SourceError, match="invalid data from synthetic"):
        load_races(_BrokenSource(rng=make_rng(1)), db, (2023,), now=NOW, echo=lambda _l: None)
    assert not db.exists() or _db.completed_race_ids(db) == set()


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
