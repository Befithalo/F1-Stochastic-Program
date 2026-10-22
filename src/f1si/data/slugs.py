"""Stable, readable race slugs such as `bahrain-2023`."""

import re
import unicodedata

_SUFFIX = re.compile(r"(^|\s)grand prix$")


def event_slug(event_name: str, season: int) -> str:
    """Return the slug for an event: ASCII, lowercase, no "Grand Prix", dash-separated.

    >>> event_slug("São Paulo Grand Prix", 2024)
    'sao-paulo-2024'

    Raises:
        ValueError: if nothing is left of the name once it is cleaned.
    """
    ascii_name = (
        unicodedata.normalize("NFKD", event_name).encode("ascii", "ignore").decode("ascii").lower()
    )
    ascii_name = _SUFFIX.sub("", ascii_name.strip())
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    if not base:
        raise ValueError(f"cannot build a slug from event name {event_name!r}")
    return f"{base}-{season}"
