"""A `RaceSource` serving seeded synthetic races (D-09)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import numpy as np

import f1si
from f1si.data.sources import NormalizedRace, RaceRef, SourceError
from f1si.synthetic.generator import SyntheticRaceSpec, default_specs, generate_dataset


class SyntheticSource:
    """Generates the dataset once, from `rng`, and serves it through the `RaceSource` protocol."""

    def __init__(
        self, specs: Sequence[SyntheticRaceSpec] | None = None, *, rng: np.random.Generator
    ) -> None:
        chosen = tuple(default_specs() if specs is None else specs)
        self._races = {r.race.ref.race_id: r.race for r in generate_dataset(chosen, rng=rng)}
        self._seasons = tuple(sorted({spec.season for spec in chosen}))

    @property
    def name(self) -> str:
        """Source name stored with each race."""
        return "synthetic"

    @property
    def version(self) -> str:
        """Generator version stored with each race."""
        return f"f1si-{f1si.__version__}"

    @property
    def default_seasons(self) -> tuple[int, ...]:
        """Distinct seasons of the specs, ascending."""
        return self._seasons

    def list_races(self, season: int, *, now: datetime) -> list[RaceRef]:
        """Refs of `season` in round order (all synthetic races count as already run)."""
        refs = [r.ref for r in self._races.values() if r.ref.season == season]
        return sorted(refs, key=lambda ref: ref.round)

    def fetch(self, ref: RaceRef) -> NormalizedRace:
        """Return the stored race for `ref`."""
        try:
            return self._races[ref.race_id]
        except KeyError:
            raise SourceError(f"synthetic source has no race {ref.race_id!r}") from None
