"""Errors the data layer raises. Messages say what to do next."""

import difflib
from collections.abc import Collection
from pathlib import Path


class F1siDataError(Exception):
    """Base class for data-layer errors the command line reports as one friendly line."""


class CacheMissingError(F1siDataError):
    """The DuckDB cache file does not exist yet."""

    def __init__(self, path: Path | str) -> None:
        super().__init__(f"No cache found at {path}. Run: uv run f1si load")
        self.path = str(path)


class CacheBusyError(F1siDataError):
    """Another process holds the DuckDB file open."""

    def __init__(self) -> None:
        super().__init__(
            "The cache is busy (another f1si command is using it). "
            "Wait for it to finish, then run this again."
        )


class MixedSourceError(F1siDataError):
    """The cache already holds data from a different source (one source per folder)."""

    def __init__(self, path: Path | str, found: Collection[str], source_name: str) -> None:
        super().__init__(
            f"This cache ({path}) holds data from {', '.join(sorted(found))}. "
            f"Use a different --data-dir for source {source_name} (one source per folder)."
        )
        self.path = str(path)
        self.found = tuple(sorted(found))
        self.source_name = source_name


class UnknownRaceError(F1siDataError):
    """A race id or slug is not in the cache (or its load did not finish)."""

    def __init__(self, name: str, known: Collection[str] = ()) -> None:
        close = difflib.get_close_matches(name, sorted(known), n=3, cutoff=0.6)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        super().__init__(f"Unknown race {name!r}.{hint} Run: uv run f1si races")
        self.name = name
        self.close_matches = tuple(close)


class OutOfSampleLockedError(F1siDataError):
    """A 2026 (out-of-sample) race was requested through a door that keeps it locked (DAT-05)."""

    def __init__(self, race_id: str) -> None:
        super().__init__(
            f"{race_id} is in the out-of-sample 2026 era and is locked (DAT-05). "
            "Only the holdout evaluation (Phase 8) may open it, through f1si.data.out_of_sample."
        )
        self.race_id = race_id


class LapOutOfRangeError(F1siDataError):
    """A lap number beyond the last lap of the race was requested."""

    def __init__(self, lap: int, slug: str) -> None:
        super().__init__(
            f"Lap {lap} is beyond the last lap of {slug}; use RACE_END for the whole race"
        )
        self.lap = lap
        self.slug = slug
