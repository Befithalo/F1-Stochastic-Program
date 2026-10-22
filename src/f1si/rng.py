"""Seeded random number generation: the single place a NumPy generator is built (FND-03).

NumPy's `default_rng(seed)` returns a PCG64 bit generator whose state is derived from the seed
through `SeedSequence`, so the same seed always yields the same stream on every machine.

Library code never creates generators. It receives a keyword-only `rng: np.random.Generator`
argument and, when it needs independent streams (for example one per worker or per simulated
race), calls `rng.spawn(n)`, which uses `SeedSequence.spawn` so the child streams are
statistically independent of each other and of the parent.

This module is the only place allowed to call `default_rng`; an import-ban guard added in
plan 01-05 enforces it.
"""

from typing import Final

import numpy as np

DEFAULT_SEED: Final[int] = 20230305  # Bahrain 2023 race date, the project's reference race


def make_rng(seed: int) -> np.random.Generator:
    """Return a PCG64 generator seeded with `seed`.

    Raises:
        ValueError: if `seed` is a bool or negative (both are almost certainly a mistake).
    """
    if isinstance(seed, bool) or seed < 0:
        raise ValueError(f"seed must be a non-negative integer, got {seed!r}")
    return np.random.default_rng(seed)
