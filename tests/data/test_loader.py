"""Loader resilience: resume, rate limits, failure list, source mixing, interrupts."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from f1si import paths
from f1si.data import _db
from f1si.data.errors import MixedSourceError
from f1si.data.loader import LoadReport, load_races
from f1si.data.sources import NormalizedRace, RaceRef, SourceError
from f1si.data.sources import RateLimitedError as RateLimited
from f1si.eras import UnknownEraError
from f1si.rng import DEFAULT_SEED, make_rng
from f1si.synthetic import default_specs, generate_dataset
from tests.data.mini_race import mini_race_row, mini_tables

NOW = datetime(2026, 10, 22, tzinfo=UTC)
SEASONS = (2023, 2024, 2026)

# A behavior is called on each fetch of a race (with the attempt number, from 1) and may raise.
Behavior = Callable[[int], None]


class FakeSource:
    """A RaceSource over the default synthetic dataset with injectable failures."""

    def __init__(
        self,
        behaviors: dict[str, Behavior] | None = None,
        *,
        schedule_error_for: int | None = None,
        name: str = "synthetic",
    ) -> None:
        dataset = generate_dataset(default_specs(), rng=make_rng(DEFAULT_SEED))
        self._races = {r.race.ref.race_id: r.race for r in dataset}
        self._behaviors = behaviors or {}
        self._schedule_error_for = schedule_error_for
        self._name = name
        self.fetch_calls: list[str] = []
        self.list_calls = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "fake-1"

    @property
    def default_seasons(self) -> tuple[int, ...]:
        return SEASONS

    def list_races(self, season: int, *, now: datetime) -> list[RaceRef]:
        self.list_calls += 1
        if season == self._schedule_error_for:
            raise SourceError("schedule service unavailable")
        return sorted(
            (r.ref for r in self._races.values() if r.ref.season == season),
            key=lambda ref: ref.round,
        )

    def fetch(self, ref: RaceRef) -> NormalizedRace:
        self.fetch_calls.append(ref.race_id)
        attempt = self.fetch_calls.count(ref.race_id)
        behavior = self._behaviors.get(ref.race_id)
        if behavior is not None:
            behavior(attempt)
        return self._races[ref.race_id]


def _run(
    source: FakeSource,
    tmp_path: Path,
    *,
    seasons: tuple[int, ...] = SEASONS,
    only: list[str] | None = None,
    max_attempts: int = 3,
) -> tuple[LoadReport, list[str], list[float]]:
    lines: list[str] = []
    sleeps: list[float] = []
    report = load_races(
        source,
        paths.db_path(tmp_path),
        seasons,
        now=NOW,
        echo=lines.append,
        only=only,
        sleep=sleeps.append,
        max_attempts=max_attempts,
    )
    return report, lines, sleeps


def _fail_first(attempt: int) -> None:
    if attempt == 1:
        raise SourceError("boom: connection reset")


def test_failed_race_is_listed_and_the_rerun_resumes(tmp_path: Path) -> None:
    source = FakeSource({"2023-02": _fail_first})
    report, lines, _ = _run(source, tmp_path)
    assert report.loaded == ["2023-01", "2024-01", "2026-01"]
    assert [(f.race_id, "boom" in f.reason) for f in report.failed] == [("2023-02", True)]
    assert report.exit_code == 2
    text = "\n".join(lines)
    assert "Failed races:" in text
    assert "SourceError: boom: connection reset" in text
    assert "Run the same command again" in text

    report2, lines2, _ = _run(source, tmp_path)
    assert report2.exit_code == 0
    assert report2.loaded == ["2023-02"]
    assert report2.skipped == ["2023-01", "2024-01", "2026-01"]
    assert sum("skipped (cached)" in line for line in lines2) == 3
    assert "Failed races:" not in "\n".join(lines2)
    # the cached races were not fetched again
    assert source.fetch_calls.count("2023-01") == 1


def test_rate_limit_waits_and_retries(tmp_path: Path) -> None:
    def limited_twice(attempt: int) -> None:
        if attempt <= 2:
            raise RateLimited("slow down", retry_after_s=5)

    source = FakeSource({"2023-01": limited_twice})
    report, lines, sleeps = _run(source, tmp_path)
    assert sleeps == [60.0, 60.0]
    assert report.failed == []
    assert "2023-01" in report.loaded
    assert any("rate limited by synthetic; waiting 60 s before retry 2/3" in x for x in lines)


def test_long_retry_after_is_honored(tmp_path: Path) -> None:
    def limited_once(attempt: int) -> None:
        if attempt == 1:
            raise RateLimited("slow down", retry_after_s=95)

    _, _, sleeps = _run(FakeSource({"2023-01": limited_once}), tmp_path)
    assert sleeps == [95.0]


def test_rate_limit_that_never_clears_fails_one_race_only(tmp_path: Path) -> None:
    def always(_attempt: int) -> None:
        raise RateLimited("slow down")

    report, _, sleeps = _run(FakeSource({"2023-02": always}), tmp_path, max_attempts=3)
    assert sleeps == [60.0, 60.0]
    assert len(report.failed) == 1
    assert report.failed[0].race_id == "2023-02"
    assert "rate limited" in report.failed[0].reason
    assert report.loaded == ["2023-01", "2024-01", "2026-01"]


@pytest.mark.parametrize("value", ["bravo-2023", "2023-02"])
def test_only_accepts_slug_or_race_id(tmp_path: Path, value: str) -> None:
    source = FakeSource()
    report, _, _ = _run(source, tmp_path, only=[value])
    assert report.loaded == ["2023-02"]
    assert source.fetch_calls == ["2023-02"]


def test_only_unknown_value_is_a_failure(tmp_path: Path) -> None:
    report, lines, _ = _run(FakeSource(), tmp_path, only=["nope-2023", "alpha-2023"])
    assert report.loaded == ["2023-01"]
    assert [f.race_id for f in report.failed] == ["nope-2023"]
    assert "not found" in report.failed[0].reason
    assert "Failed races:" in "\n".join(lines)


def test_cache_from_another_source_is_refused_before_any_fetch(tmp_path: Path) -> None:
    db = paths.db_path(tmp_path)
    _db.write_race(db, mini_race_row(source="openf1+jolpica"), mini_tables())
    source = FakeSource()
    with pytest.raises(MixedSourceError, match="openf1\\+jolpica"):
        _run(source, tmp_path)
    assert source.fetch_calls == []
    assert source.list_calls == 0


def test_keyboard_interrupt_propagates_and_leaves_no_rows(tmp_path: Path) -> None:
    def interrupt(_attempt: int) -> None:
        raise KeyboardInterrupt

    source = FakeSource({"2023-02": interrupt})
    with pytest.raises(KeyboardInterrupt):
        _run(source, tmp_path)
    db = paths.db_path(tmp_path)
    assert _db.completed_race_ids(db) == {"2023-01"}
    laps = _db.read_table(db, "laps", race_id="2023-02")
    assert len(laps) == 0


def test_schedule_failure_for_one_season_does_not_stop_the_others(tmp_path: Path) -> None:
    report, _, _ = _run(FakeSource(schedule_error_for=2024), tmp_path)
    assert [(f.race_id, f.slug) for f in report.failed] == [("2024-schedule", "-")]
    assert report.loaded == ["2023-01", "2023-02", "2026-01"]


def test_unknown_season_is_rejected_before_anything_happens(tmp_path: Path) -> None:
    source = FakeSource()
    with pytest.raises(UnknownEraError) as exc:
        _run(source, tmp_path, seasons=(2023, 2030))
    assert exc.value.season == 2030
    assert source.list_calls == 0


def test_invalid_source_data_becomes_a_failure_and_writes_nothing(tmp_path: Path) -> None:
    class Broken(FakeSource):
        def fetch(self, ref: RaceRef) -> NormalizedRace:
            race = super().fetch(ref)
            tables = dict(race.tables)
            del tables["weather"]
            return NormalizedRace(ref=race.ref, tables=tables)

    report, _, _ = _run(Broken(), tmp_path, seasons=(2023,))
    assert report.loaded == []
    assert len(report.failed) == 2
    assert all("invalid data from synthetic" in f.reason for f in report.failed)
    assert all("missing required table 'weather'" in f.reason for f in report.failed)
    db = paths.db_path(tmp_path)
    assert not db.exists() or _db.completed_race_ids(db) == set()


def test_summary_line_counts_and_cache_path(tmp_path: Path) -> None:
    _, lines, _ = _run(FakeSource(), tmp_path)
    assert lines[-1] == f"Done: 4 loaded, 0 skipped, 0 failed. Cache: {tmp_path}"


class _DiscardingSource(FakeSource):
    """A source with an HTTP cache: it is told which race to forget (WR-05)."""

    def __init__(self) -> None:
        super().__init__()
        self.discarded: list[str] = []

    def discard_cached(self, ref: RaceRef) -> None:
        self.discarded.append(ref.race_id)


def test_loader_discards_the_cached_responses_of_a_race_that_fails_validation(
    tmp_path: Path,
) -> None:
    def invalid(attempt: int) -> None:
        raise SourceError("invalid data from the service")

    source = _DiscardingSource()
    source._behaviors["2023-02"] = invalid
    report, _, _ = _run(source, tmp_path)
    assert [f.race_id for f in report.failed] == ["2023-02"]
    assert source.discarded == ["2023-02"]


def test_loader_does_not_discard_cached_responses_of_races_that_load(tmp_path: Path) -> None:
    source = _DiscardingSource()
    report, _, _ = _run(source, tmp_path)
    assert report.failed == []
    assert source.discarded == []
