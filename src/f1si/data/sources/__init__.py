"""The contract every race data source implements (D-08).

Every source emits the normalized tables of `f1si.data.schema`, so adding a source changes nothing
downstream. This module imports nothing from the adapters; they import from here.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

import pandas as pd


@dataclass(frozen=True)
class RaceRef:
    """Identifies one race: stable id and slug plus the calendar facts."""

    race_id: str
    season: int
    round: int
    slug: str
    event_name: str
    circuit: str
    country: str
    race_start_utc: datetime
    scheduled_laps: int | None = None
    source_keys: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedRace:
    """A race as normalized tables keyed by table name (see `f1si.data.schema.TABLES`)."""

    ref: RaceRef
    tables: Mapping[str, pd.DataFrame]


class SourceError(Exception):
    """A source could not provide the requested data."""


class RateLimitedError(SourceError):
    """The remote service asked us to slow down."""

    def __init__(self, message: str, *, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


@runtime_checkable
class CacheDiscarding(Protocol):
    """An optional hook of sources that keep an HTTP cache.

    The loader calls it for a race that failed validation, so the next run fetches that race again
    instead of replaying the same bad responses (WR-05).
    """

    def discard_cached(self, ref: RaceRef) -> None:
        """Forget the saved responses of one race."""
        ...


class RaceSource(Protocol):
    """A provider of races: lists them for a season and fetches one as normalized tables."""

    @property
    def name(self) -> str:
        """Short source name stored with each race (for example `synthetic`, `openf1`)."""
        ...

    @property
    def version(self) -> str:
        """Source or generator version, stored with each race."""
        ...

    @property
    def default_seasons(self) -> tuple[int, ...]:
        """Seasons loaded when the user does not choose any."""
        ...

    def list_races(self, season: int, *, now: datetime) -> list[RaceRef]:
        """Races of `season` that have already been run at time `now`."""
        ...

    def fetch(self, ref: RaceRef) -> NormalizedRace:
        """Fetch one race as normalized tables."""
        ...
