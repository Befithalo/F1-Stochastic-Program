"""Errors the data layer raises. Messages say what to do next."""

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
