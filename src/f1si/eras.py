"""Regulation eras (DAT-05).

Race data is tagged with the regulation era it belongs to so models can be fitted per era and
the structural break of 2026 is never mixed into the in-sample data.

2026 is a structural break: narrower tyres, about 10% less grip and more one-stop races
(BUILD_PLAN, "The 2026 break"). It is therefore a separate, out-of-sample era whose data stays
locked behind the out-of-sample door until the final holdout evaluation.
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Era:
    """A block of seasons run under one set of technical regulations."""

    name: str
    first_season: int
    last_season: int
    out_of_sample: bool

    def contains(self, season: int) -> bool:
        """Return True if `season` falls inside this era."""
        return self.first_season <= season <= self.last_season


GROUND_EFFECT: Final[Era] = Era("ground_effect_2022_2025", 2022, 2025, False)
REG_2026: Final[Era] = Era("reg_2026", 2026, 2026, True)
ERAS: Final[tuple[Era, ...]] = (GROUND_EFFECT, REG_2026)


class UnknownEraError(ValueError):
    """Raised when a season does not belong to any defined era."""

    def __init__(self, season: int) -> None:
        super().__init__(
            f"No regulation era is defined for season {season}; "
            "add one to f1si/eras.py and log it in DECISIONS.md"
        )
        self.season = season


def era_for_season(season: int) -> Era:
    """Return the era a season belongs to.

    Raises:
        UnknownEraError: if no era covers `season`.
    """
    for era in ERAS:
        if era.contains(season):
            return era
    raise UnknownEraError(season)
