"""Load races from a `RaceSource` into the DuckDB cache.

Behavior (D-05, D-14):

* Resumable. Races already complete in the cache are skipped, so running the same command again
  only fetches what is missing.
* Rate limits are waited out. A `RateLimitedError` makes the loader sleep (at least 60 s, longer
  if the service asked) and try the same race again, up to `max_attempts` attempts in total.
* One bad race never aborts the run. Failures are collected and listed at the end with a hint to
  run the same command again. Only problems that would fail every race (a busy cache, a cache
  holding another source) stop the run, and Ctrl+C stops it at once; `_db.write_race` rolls the
  current race back so a half-written race never exists.
* One source per cache folder. Mixing synthetic and real races would put fake races into real
  history, so the loader refuses before any network call.
* Each race is validated before anything is written; `laps.track_status` and `lap_cutoffs` are
  derived here (see `f1si.data.derive`) so every source gets them for free.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from f1si.data import derive, schema
from f1si.data.errors import CacheBusyError, MixedSourceError
from f1si.data.sources import (
    CacheDiscarding,
    NormalizedRace,
    RaceRef,
    RaceSource,
    RateLimitedError,
    SourceError,
)
from f1si.eras import era_for_season

MIN_RATE_LIMIT_WAIT_S = 60.0


@dataclass(frozen=True)
class LoadFailure:
    """A race (or schedule, or `--only` value) that could not be loaded and why."""

    race_id: str
    slug: str
    reason: str


@dataclass
class LoadReport:
    """Outcome of one `load_races` call."""

    loaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[LoadFailure] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """0 if no race failed, else 2."""
        return 0 if not self.failed else 2


def _race_row(source: RaceSource, ref: RaceRef, now: datetime) -> pd.DataFrame:
    era = era_for_season(ref.season)
    return pd.DataFrame(
        [
            {
                "race_id": ref.race_id,
                "season": ref.season,
                "round": ref.round,
                "slug": ref.slug,
                "event_name": ref.event_name,
                "circuit": ref.circuit,
                "country": ref.country,
                "race_start_utc": ref.race_start_utc,
                "scheduled_laps": ref.scheduled_laps,
                "era": era.name,
                "out_of_sample": era.out_of_sample,
                "source": source.name,
                "source_version": source.version,
                "loaded_at_utc": now,
                "load_status": "complete",
            }
        ]
    )


def _build_tables(ref: RaceRef, race: NormalizedRace) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Normalize the source tables, clean the lap clock, fill `laps.track_status`, derive cutoffs.

    Returns the tables to write and human-readable notes about anything that was repaired.

    Raises:
        SourceError: if too many lap end times had to be dropped for the race to be trusted.
    """
    tables = {
        name: schema.normalize(name, race.tables[name])
        for name in schema.PER_RACE_TABLES
        if not schema.TABLES[name].derived
    }
    laps, dropped = derive.sanitize_lap_ends(tables["laps"])
    notes: list[str] = []
    if dropped:
        before = int(tables["laps"]["lap_end_s"].notna().sum())
        n_bad = before - int(laps["lap_end_s"].notna().sum())
        if n_bad > derive.MAX_BAD_END_FRACTION * max(before, 1):
            raise SourceError(
                f"{n_bad} of {before} lap end times break the race clock "
                f"(e.g. {dropped[0]}); the feed looks corrupt"
            )
        notes.append(
            f"dropped {n_bad} lap end time(s) that break the race clock "
            f"({', '.join(dropped)}); those laps are visible only at the race end"
        )
    repaired = derive.cutoff_repairs(laps)
    if repaired:
        notes.append(
            f"lowered the cutoff of lap(s) {', '.join(str(n) for n in repaired[:5])} because "
            "the leader's own lap end is missing"
        )
    laps["track_status"] = derive.annotate_lap_track_status(laps, tables["track_status"])
    tables["laps"] = schema.normalize("laps", laps)
    tables["lap_cutoffs"] = derive.derive_lap_cutoffs(ref.race_id, tables["laps"])
    built = {
        name: schema.normalize(name, schema.add_visibility(name, tables[name]))
        for name in schema.PER_RACE_TABLES
    }
    return built, notes


def _select(
    refs: list[RaceRef], only: Collection[str] | None, seasons: Sequence[int]
) -> tuple[list[RaceRef], list[LoadFailure]]:
    """Keep refs whose race_id or slug is in `only`; report `only` values that matched nothing."""
    if only is None:
        return refs, []
    wanted = list(dict.fromkeys(only))
    kept = [r for r in refs if r.race_id in wanted or r.slug in wanted]
    matched = {r.race_id for r in kept} | {r.slug for r in kept}
    shown = ", ".join(str(s) for s in seasons)
    missing = [
        LoadFailure(value, "-", f"not found in the schedule for seasons {shown}")
        for value in wanted
        if value not in matched
    ]
    return kept, missing


def load_races(
    source: RaceSource,
    db_path: Path,
    seasons: Sequence[int],
    *,
    now: datetime,
    echo: Callable[[str], None],
    only: Collection[str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_attempts: int = 3,
) -> LoadReport:
    """Fetch the races of `seasons` from `source` into the cache at `db_path`.

    Races are processed in season, round order. Complete races already in the cache are skipped;
    failures are collected in the report instead of stopping the run.

    Args:
        source: where races come from.
        db_path: the DuckDB cache file.
        seasons: seasons to load (each must belong to a regulation era).
        now: the current time, stored as `loaded_at_utc` and passed to the source's schedule.
        echo: receives one progress line per race and the final summary.
        only: if given, load only races whose id (`2023-01`) or slug (`bahrain-2023`) is listed.
        sleep: waits out rate limits; tests inject a recorder so nothing really sleeps.
        max_attempts: attempts per race when the service rate-limits us.

    Raises:
        UnknownEraError: if a season belongs to no regulation era.
        MixedSourceError: if the cache already holds data from another source.
        CacheBusyError: if another process holds the cache open.
    """
    from f1si.data import _db  # local import: not a module attribute (CR-01)

    for season in seasons:
        era_for_season(season)
    foreign = _db.sources_in_cache(db_path) - {source.name}
    if foreign:
        raise MixedSourceError(db_path, foreign, source.name)

    report = LoadReport()
    refs: list[RaceRef] = []
    for season in sorted(set(seasons)):
        try:
            refs.extend(sorted(source.list_races(season, now=now), key=lambda r: r.round))
        except SourceError as err:
            report.failed.append(LoadFailure(f"{season}-schedule", "-", str(err)))
    refs, unmatched = _select(refs, only, sorted(set(seasons)))
    report.failed.extend(unmatched)

    done = _db.completed_race_ids(db_path)
    width = len(str(len(refs)))
    for i, ref in enumerate(refs, start=1):
        prefix = f"[{i:>{width}}/{len(refs)}] {ref.race_id} {ref.slug:<20}"
        if ref.race_id in done:
            echo(f"{prefix} skipped (cached)")
            report.skipped.append(ref.race_id)
            continue
        failure = _load_one(source, db_path, ref, now, echo, prefix, sleep, max_attempts)
        if failure is None:
            report.loaded.append(ref.race_id)
        else:
            report.failed.append(failure)
            echo(f"{prefix} FAILED: {failure.reason}")

    echo(
        f"Done: {len(report.loaded)} loaded, {len(report.skipped)} skipped, "
        f"{len(report.failed)} failed. Cache: {db_path.parent}"
    )
    if report.failed:
        echo("Failed races:")
        for f in report.failed:
            echo(f"  {f.race_id} {f.slug}: {f.reason}")
        echo("Run the same command again to retry only the failed races (finished races are kept).")
    return report


def _load_one(
    source: RaceSource,
    db_path: Path,
    ref: RaceRef,
    now: datetime,
    echo: Callable[[str], None],
    prefix: str,
    sleep: Callable[[float], None],
    max_attempts: int,
) -> LoadFailure | None:
    """Fetch, validate, derive and write one race; return a failure instead of raising.

    Problems that would fail every race (`CacheBusyError`, `MixedSourceError`) and interrupts
    (`KeyboardInterrupt`, `SystemExit`) propagate.
    """
    from f1si.data import _db  # local import: not a module attribute (CR-01)

    for attempt in range(1, max_attempts + 1):
        try:
            race = source.fetch(ref)
            problems = schema.validate_race(race)
            if problems:
                raise SourceError(f"invalid data from {source.name}: " + "; ".join(problems))
            tables, notes = _build_tables(ref, race)
            _db.write_race(db_path, _race_row(source, ref, now), tables)
        except RateLimitedError as err:
            if attempt >= max_attempts:
                return LoadFailure(
                    ref.race_id,
                    ref.slug,
                    f"rate limited by {source.name}; run the same command again later "
                    "(finished races are kept)",
                )
            wait = max(err.retry_after_s or 0.0, MIN_RATE_LIMIT_WAIT_S)
            echo(
                f"{prefix} rate limited by {source.name}; waiting {wait:g} s before retry "
                f"{attempt + 1}/{max_attempts}"
            )
            sleep(wait)
        except (CacheBusyError, MixedSourceError):
            raise
        except Exception as err:
            if isinstance(err, SourceError) and isinstance(source, CacheDiscarding):
                source.discard_cached(ref)  # do not replay the same bad responses next time
            return LoadFailure(ref.race_id, ref.slug, f"{type(err).__name__}: {err}")
        else:
            era = era_for_season(ref.season)
            echo(f"{prefix} ok  {len(tables['laps']):,} laps  (era {era.name})")
            for note in notes:
                echo(f"{prefix} note: {note}")
            return None
    return LoadFailure(ref.race_id, ref.slug, "no attempts were made (max_attempts < 1)")
