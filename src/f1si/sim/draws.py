"""Variance-reduced random draws for the race simulator (SIM-03 groundwork, DEC-080).

Layout. For `n` races and `d` dimensions let `h = ceil(n / 2)` and `m = max(1, ceil(log2(h)))`.
The base block is the first `h` rows of a scrambled Sobol sequence of `2**m` points,
`Sobol(d, scramble=True, rng=child).random_base2(m)[:h]`, called with `random_base2` so SciPy
never warns about a non power of two. Antithetic pairing stacks `[u; 1 - u]` and trims to `n`
rows, so odd `n` is padded and trimmed internally and `n_races` need not be even. Row `i` and
row `i + h` always sum to one. Normals use `z = Phi^-1(clip(u, 1e-12, 1 - 1e-12))`.

Which block is Sobol. Sobol is used only for low-dimensional blocks (safety-car start, per car
and per compound parameter draws, and one `Sobol(d=n_cars)` engine per lap for pass uniforms),
far below SciPy's 21,201 dimension limit. High-dimensional per-lap noise uses plain
antithetic normals `[e; -e]` (D-13).

Common random numbers. Every draw is indexed by (race, car, lap), generated unconditionally and
in lap order, never conditioned on a plan, the running order or the safety-car state, so forcing
one driver's plan cannot shift anyone else's draws. The per-compound wear columns follow a
fixed slot layout (`f1si.sim.constants.DRAW_COMPOUNDS`), not the compounds a plan happens to use,
so even a forced plan that adds a compound leaves the block unchanged (DEC-087). Streams come
only from `rng.spawn`.
"""

import math
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray
from scipy.stats import norm
from scipy.stats.qmc import Sobol

VarianceReduction = Literal["none", "antithetic", "sobol_antithetic"]
MODES: Final[tuple[str, ...]] = ("none", "antithetic", "sobol_antithetic")
SOBOL_MAX_DIM: Final[int] = 21201
_CLIP: Final[float] = 1e-12


def _check(mode: str, d: int, n: int) -> None:
    if mode not in MODES:
        raise ValueError(f"variance-reduction mode must be one of {MODES}, got {mode!r}")
    if n < 1:
        raise ValueError(f"n must be at least 1, got {n!r}")
    if d < 1:
        raise ValueError(f"d must be at least 1, got {d!r}")


def _pair(base: NDArray[np.float64], n: int, *, normal: bool) -> NDArray[np.float64]:
    mirror = -base if normal else 1.0 - base
    return np.concatenate([base, mirror], axis=0)[:n]


def sobol_pairs(d: int, n: int, child: np.random.Generator) -> NDArray[np.float64]:
    """Scrambled Sobol points in (0, 1), shape (n, d), with antithetic partners 1 - u."""
    _check("sobol_antithetic", d, n)
    if d > SOBOL_MAX_DIM:
        raise ValueError(f"Sobol supports at most {SOBOL_MAX_DIM} dimensions, got d={d!r}")
    h = math.ceil(n / 2)
    m = max(1, math.ceil(math.log2(h)))
    engine = Sobol(d=d, scramble=True, rng=child)
    base = np.asarray(engine.random_base2(m)[:h], dtype=np.float64)
    return _pair(base, n, normal=False)


def uniform_block(mode: str, d: int, n: int, child: np.random.Generator) -> NDArray[np.float64]:
    """Uniform draws, shape (n, d), under the chosen variance-reduction mode."""
    _check(mode, d, n)
    if mode == "none":
        return np.asarray(child.random((n, d)), dtype=np.float64)
    if mode == "antithetic":
        base = np.asarray(child.random((math.ceil(n / 2), d)), dtype=np.float64)
        return _pair(base, n, normal=False)
    return sobol_pairs(d, n, child)


def normal_block(mode: str, d: int, n: int, child: np.random.Generator) -> NDArray[np.float64]:
    """Standard normal draws, shape (n, d); plain (never Sobol) antithetic normals (D-13)."""
    _check(mode, d, n)
    if mode == "none":
        return np.asarray(child.standard_normal((n, d)), dtype=np.float64)
    base = np.asarray(child.standard_normal((math.ceil(n / 2), d)), dtype=np.float64)
    return _pair(base, n, normal=True)


def normal_from_uniform(u: NDArray[np.float64]) -> NDArray[np.float64]:
    """Inverse normal CDF with the uniforms clipped to [1e-12, 1 - 1e-12] (never inf)."""
    return np.asarray(norm.ppf(np.clip(u, _CLIP, 1.0 - _CLIP)), dtype=np.float64)


def make_streams(
    rng: np.random.Generator, n_laps: int
) -> tuple[np.random.Generator, list[np.random.Generator], np.random.Generator]:
    """Spawn (sc_params, one passing stream per lap, noise); a fourth child is kept spare."""
    if n_laps < 1:
        raise ValueError(f"n_laps must be at least 1, got {n_laps!r}")
    sc_params, passing, noise, _spare = rng.spawn(4)
    return sc_params, passing.spawn(n_laps), noise
