"""Load races from a `RaceSource` into the DuckDB cache.

This is the happy path of the walking skeleton: fetch, validate, stamp the regulation era, write
one race per transaction. Plan 01-04 adds resumability, retries and the failure list; the report
types already carry the fields it needs.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from f1si.data import _db, schema
from f1si.data.sources import RaceRef, RaceSource, SourceError
from f1si.eras import era_for_season


@dataclass(frozen=True)
class LoadFailure:
    """A race that could not be loaded and why."""

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


def load_races(
    source: RaceSource,
    db_path: Path,
    seasons: Sequence[int],
    *,
    now: datetime,
    echo: Callable[[str], None],
) -> LoadReport:
    """Fetch every race of `seasons` from `source` and write it to the cache at `db_path`.

    Races are processed in season, round order. Each is validated before anything is written, so
    invalid source output never reaches the cache.

    Raises:
        SourceError: if a source returns data that fails `schema.validate_race`.
    """
    refs: list[RaceRef] = []
    for season in sorted(seasons):
        refs.extend(sorted(source.list_races(season, now=now), key=lambda r: r.round))

    report = LoadReport()
    width = len(str(len(refs)))
    for i, ref in enumerate(refs, start=1):
        race = source.fetch(ref)
        problems = schema.validate_race(race)
        if problems:
            raise SourceError(f"invalid data from {source.name}: " + "; ".join(problems))
        tables = {
            name: schema.normalize(name, schema.add_visibility(name, race.tables[name]))
            for name in schema.PER_RACE_TABLES
        }
        _db.write_race(db_path, _race_row(source, ref, now), tables)
        report.loaded.append(ref.race_id)
        era = era_for_season(ref.season)
        echo(
            f"[{i:>{width}}/{len(refs)}] {ref.race_id} {ref.slug:<20} ok  "
            f"{len(tables['laps']):,} laps  (era {era.name})"
        )
    return report
