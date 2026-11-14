"""Command line, loader and catalog behavior (in-process, scratch data folders)."""

import contextlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from f1si import cli, paths
from f1si.cli import build_parser, main
from f1si.data import _db, asof, schema
from f1si.data.loader import load_races
from f1si.data.sources import NormalizedRace, RaceRef
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.rng import make_rng

NOW = datetime(2026, 10, 22, tzinfo=UTC)


def test_backtest_report_parser_accepts_report_mode_and_default_output() -> None:
    parsed = None
    with contextlib.suppress(SystemExit):
        parsed = build_parser().parse_args(["backtest", "--report"])
    assert parsed is not None, "backtest --report must not require single-cutoff arguments"
    assert parsed.report is True
    assert parsed.output == Path("reports/backtest/phase-06.json")
    assert parsed.workers == 4


def test_backtest_report_writes_completed_json_to_output_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from f1si.backtest import scoring

    report: dict[str, object] = {
        "race_ids": ["2023-01"],
        "metrics": {"podium_brier": {"model": {"mean": 0.2}}},
    }
    calls: list[tuple[Path, dict[str, object], dict[str, object]]] = []

    def score(db_path: Path, **options: object) -> dict[str, object]:
        calls.append((db_path, report, options))
        return report

    monkeypatch.setattr(scoring, "score_registered_sample", score)
    output = tmp_path / "phase-06.json"
    assert (
        main(
            [
                "--data-dir",
                str(tmp_path),
                "backtest",
                "--report",
                "--output",
                str(output),
                "--workers",
                "2",
            ]
        )
        == 0
    )
    assert calls == [
        (
            paths.db_path(tmp_path),
            report,
            {"n_simulations": 1000, "risk": 0.5, "seed": 0, "workers": 2},
        )
    ]
    assert json.loads(output.read_text(encoding="utf-8")) == report


@pytest.mark.parametrize("existing", [False, True])
def test_backtest_report_incomplete_cache_writes_no_completed_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    existing: bool,
) -> None:
    from f1si.backtest import scoring

    output = tmp_path / "phase-06.json"
    before = '{"complete":true}\n'
    if existing:
        output.write_text(before, encoding="utf-8")

    def incomplete(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise ValueError("Backtest cache is missing complete registered races: 2024-02")

    monkeypatch.setattr(scoring, "score_registered_sample", incomplete)
    assert (
        main(
            [
                "--data-dir",
                str(tmp_path),
                "backtest",
                "--report",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert (output.read_text(encoding="utf-8") == before) if existing else not output.exists()
    assert "missing complete registered races" in capsys.readouterr().err


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


def test_replay_horizon_comes_from_ex_ante_schedule_not_race_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[asof.AsOf] = []
    replay_horizons: list[int] = []

    class Accessor:
        def __init__(self, _db: Path) -> None:
            pass

        def snapshot(self, at: asof.AsOf) -> SimpleNamespace:
            requests.append(at)
            if at.lap == asof.RACE_END:
                return SimpleNamespace(
                    laps=pd.DataFrame({"lap_number": [44]}),
                    entries=pd.DataFrame({"driver_code": ["VER"]}),
                )
            return SimpleNamespace(
                race=SimpleNamespace(scheduled_laps=57),
                entries=pd.DataFrame({"driver_code": ["VER"]}),
            )

    monkeypatch.setattr(paths, "db_path", lambda _data: tmp_path / "cache.duckdb")
    monkeypatch.setattr(asof, "resolve_slug", lambda _db, _slug: "2023-01")
    monkeypatch.setattr(asof, "AsOfAccessor", Accessor)

    def capture_replay_horizon(*args: object, **_kwargs: object) -> SimpleNamespace:
        horizon = args[2]
        assert isinstance(horizon, int)
        replay_horizons.append(horizon)
        return SimpleNamespace()

    monkeypatch.setattr(
        cli,
        "_replay_at_cutoff",
        capture_replay_horizon,
    )
    monkeypatch.setattr(cli, "_print_replay_cutoff", lambda *_args: None)

    assert cli._cmd_replay(tmp_path, "test-race", "VER", 10, 1, 0.5, 0) == 0
    assert replay_horizons == [57]
    assert [request.lap for request in requests] == [0, asof.RACE_END]


def test_replay_refuses_when_ex_ante_schedule_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    requests: list[asof.AsOf] = []

    class Accessor:
        def __init__(self, _db: Path) -> None:
            pass

        def snapshot(self, at: asof.AsOf) -> SimpleNamespace:
            requests.append(at)
            return SimpleNamespace(race=SimpleNamespace(scheduled_laps=None))

    monkeypatch.setattr(paths, "db_path", lambda _data: tmp_path / "cache.duckdb")
    monkeypatch.setattr(asof, "resolve_slug", lambda _db, _slug: "2023-01")
    monkeypatch.setattr(asof, "AsOfAccessor", Accessor)

    assert cli._cmd_replay(tmp_path, "test-race", "VER", 10, 1, 0.5, 0) == 1
    assert requests == [asof.AsOf("2023-01", 0)]
    assert "Scheduled race distance is unavailable for 2023-01" in capsys.readouterr().err


def test_races_with_an_empty_cache_says_what_to_do(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """WR-07: a cache file with the schema but no finished race used to raise TypeError."""
    db = paths.db_path(tmp_path)
    with _db.connect_writer(db) as con:
        _db.ensure_schema(con)
    assert main(["--data-dir", str(tmp_path), "races"]) == 0
    out = capsys.readouterr().out
    assert "No races cached yet" in out
    assert "uv run f1si load" in out


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


def _load_synthetic(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--data-dir", str(tmp_path), "load", "--source", "synthetic"]) == 0
    capsys.readouterr()


def test_plot_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _load_synthetic(tmp_path, capsys)
    base = ["--data-dir", str(tmp_path), "--reports-dir", str(tmp_path / "reports")]
    assert main([*base, "plot", "alpha-2023"]) == 0
    out = capsys.readouterr().out
    assert "alpha-2023.png" in out
    assert "6 drivers" in out
    png = tmp_path / "reports" / "alpha-2023.png"
    assert png.read_bytes().startswith(b"\x89PNG")

    assert main([*base, "plot", "alpha-2023", "--drivers", "AAA", "BBB"]) == 0
    assert (tmp_path / "reports" / "alpha-2023-aaa-bbb.png").is_file()


def test_plot_by_race_id_names_file_from_slug(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _load_synthetic(tmp_path, capsys)
    base = ["--data-dir", str(tmp_path), "--reports-dir", str(tmp_path / "reports")]
    assert main([*base, "plot", "2023-01"]) == 0
    assert (tmp_path / "reports" / "alpha-2023.png").is_file()


def test_plot_unknown_race_suggests_close_match(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _load_synthetic(tmp_path, capsys)
    assert main(["--data-dir", str(tmp_path), "plot", "alpah-2023"]) == 1
    assert "alpha-2023" in capsys.readouterr().err


def test_plot_refuses_2026(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _load_synthetic(tmp_path, capsys)
    assert main(["--data-dir", str(tmp_path), "plot", "delta-2026"]) == 1
    assert "out-of-sample" in capsys.readouterr().err


def test_plot_unknown_driver_lists_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _load_synthetic(tmp_path, capsys)
    base = ["--data-dir", str(tmp_path), "--reports-dir", str(tmp_path / "reports")]
    assert main([*base, "plot", "alpha-2023", "--drivers", "ZZZ"]) == 1
    assert "AAA" in capsys.readouterr().err
    assert main([*base, "plot", "alpha-2023", "--drivers", "../x"]) == 1
    assert "three letters" in capsys.readouterr().err
    assert not (tmp_path / "reports").exists()


def test_plot_without_cache_says_what_to_do(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--data-dir", str(tmp_path / "nothing"), "plot", "alpha-2023"]) == 1
    assert "uv run f1si load" in capsys.readouterr().err
