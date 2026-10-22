"""Errors the data layer raises. Messages say what to do next."""

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
