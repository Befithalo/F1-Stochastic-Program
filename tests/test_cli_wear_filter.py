"""The `wear-filter` command on synthetic data: as-of replay, labels, PNG, errors (PAC-03)."""

from pathlib import Path

import pytest

from f1si.cli import _prior_switch_notes, main
from f1si.data import asof
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.pace.kalman import CutoffRow, LapRow, ResolvedPriors, WearPrior
from tests.conftest import LONG_RACE_ID, LONG_SLUG


def _run(data_dir: Path, tmp_path: Path, *args: str) -> int:
    return main(["--data-dir", str(data_dir), "--reports-dir", str(tmp_path), *args])


def _code(db: Path, index: int = 0) -> str:
    cars = AsOfAccessor(db).snapshot(AsOf(LONG_RACE_ID, RACE_END)).cars
    return str(sorted(cars["driver_code"])[index])


def test_full_replay_output_and_png(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db)
    assert _run(long_synthetic_data_dir, tmp_path, "wear-filter", LONG_SLUG, "--driver", code) == 0
    out = capsys.readouterr().out
    for needle in (
        "sees only laps up to N",
        "rate prior:",
        "fuel:",
        "noise:",
        "prior only",
        "LAP",
        "TYRE AGE",
        "USED",
        "95% LOW",
        "95% HIGH",
        "replayed",
        "Wrote",
        "lap 14: rate prior",
        "lap 20: rate prior",
        "lap 30: rate prior",
    ):
        assert needle in out, needle
    png = tmp_path / f"wear-filter-{LONG_SLUG}-{code}.png"
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_driver_code_is_case_insensitive(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db)

    def table(driver: str) -> str:
        args = ("wear-filter", LONG_SLUG, "--driver", driver, "--lap", "10")
        assert _run(long_synthetic_data_dir, tmp_path, *args) == 0
        text = capsys.readouterr().out
        return text[text.index("Stint 1") : text.index("replayed")]

    assert table(code.lower()) == table(code)


def test_lap_option_stops_the_replay(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _code(long_synthetic_db)
    args = ("wear-filter", LONG_SLUG, "--driver", code, "--lap", "12")
    assert _run(long_synthetic_data_dir, tmp_path, *args) == 0
    out = capsys.readouterr().out
    assert "replayed to lap 12" in out
    assert "lap 14: rate prior" not in out
    rows = [ln.split() for ln in out.splitlines() if ln.split()[:1] and ln.split()[0].isdigit()]
    assert rows
    assert max(int(r[0]) for r in rows) == 12


@pytest.mark.parametrize(
    ("args", "needle"),
    [
        (("--driver", "ZZZ"), "ZZZ"),
        (("--driver", "AB"), "three capital letters"),
        (("--driver", "ALO", "--lap", "-1"), "--lap must be 0 or more"),
    ],
)
def test_friendly_errors(
    long_synthetic_data_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    args: tuple[str, ...],
    needle: str,
) -> None:
    assert _run(long_synthetic_data_dir, tmp_path, "wear-filter", LONG_SLUG, *args) == 1
    captured = capsys.readouterr()
    assert needle in captured.err
    assert "Traceback" not in captured.err + captured.out
    assert not list(tmp_path.glob("*.png"))


def test_one_snapshot_per_cutoff_lap(
    long_synthetic_data_dir: Path,
    long_synthetic_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    code = _code(long_synthetic_db)
    original = AsOfAccessor.snapshot
    seen: list[object] = []

    def recording(self: AsOfAccessor, at: AsOf):  # type: ignore[no-untyped-def]
        seen.append(at.lap)
        return original(self, at)

    monkeypatch.setattr(AsOfAccessor, "snapshot", recording)
    args = ("wear-filter", LONG_SLUG, "--driver", code, "--lap", "8")
    assert _run(long_synthetic_data_dir, tmp_path, *args) == 0
    assert [k for k in seen if isinstance(k, int)] == list(range(1, 9))
    assert seen.count(RACE_END) == 1  # only the race-distance and entry lookup, never a fit


def _cut(lap: int, stint: int, source: str) -> CutoffRow:
    priors = ResolvedPriors(
        prior=WearPrior(rate_mean=0.08, rate_sd=0.05, fuel_sd=0.02, sigma=0.3),
        fuel_mean=-0.05,
        rate_source=source,
        fuel_source="fit",
        noise_source="fit",
    )
    return CutoffRow(lap, stint, "MEDIUM", priors, LapRow(lap, lap, True, None, 0.1, 0.02, 0, 0.2))


def test_prior_switch_notes() -> None:
    prior = "prior only: fit not identified yet"
    rows = [_cut(1, 1, prior), _cut(2, 1, prior), _cut(3, 1, "fit"), _cut(4, 1, "fit")]
    notes = _prior_switch_notes(rows)
    assert len(notes) == 1
    assert "lap 3" in notes[0]
    assert "prior only to fit" in notes[0]
    assert _prior_switch_notes([_cut(1, 1, "fit"), _cut(2, 1, "fit")]) == []
    assert _prior_switch_notes([_cut(1, 1, prior), _cut(1, 2, "fit")]) == []


def test_2026_race_is_refused(
    synthetic_db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cat = asof.catalog(synthetic_db)
    slug = str(cat[cat["out_of_sample"].astype(bool)]["slug"].iloc[0])
    assert _run(synthetic_db.parent, tmp_path, "wear-filter", slug, "--driver", "AAA") == 1
    assert "out-of-sample" in capsys.readouterr().err
