"""REG-01 simulation half: realised safety-car start frequency matches the input rate (D-06)."""

from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from f1si.data.asof import AsOf, AsOfAccessor
from f1si.regime.sc_rate import estimate_sc_rate
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel

from .conftest import ZeroNoisePace, hand_state


def _mask(rate: float, duration: int, laps: int, n: int, mode: str) -> NDArray[np.bool_]:
    sim = NumpySimulator(
        ZeroNoisePace(),
        sc=SafetyCarModel(rate, duration),
        compounds=("HARD", "MEDIUM"),
        variance_reduction=mode,  # type: ignore[arg-type]
    )
    state = hand_state(2, lap=0, laps_total=laps, spacing_s=60.0)
    mask = sim.simulate(state, n_races=n, rng=make_rng(17)).sc_lap_mask
    assert mask is not None
    return mask


@pytest.mark.parametrize("mode", ["none", "antithetic", "sobol_antithetic"])
def test_no_sc_share_in_first_ten_laps(mode: str) -> None:
    n, rate = 20000, 0.02
    mask = _mask(rate, 3, 10, n, mode)
    share = float((~mask.any(axis=1)).mean())
    want = (1 - rate) ** 10
    sigma = (want * (1 - want) / n) ** 0.5
    assert abs(share - want) < 4 * sigma


def _start_frequency(mask: NDArray[np.bool_], duration: int) -> tuple[float, int]:
    """(starts / at-risk laps, at-risk laps); a run of L SC laps holds ceil(L / duration) starts."""
    starts = 0
    for row in mask:
        run = 0
        for flag in (*row.tolist(), False):
            if flag:
                run += 1
            elif run:
                starts += -(-run // duration)
                run = 0
    at_risk = int((~mask).sum()) + starts
    return starts / at_risk, at_risk


def test_rate_from_the_estimator_is_reproduced(sc_history_db: Path) -> None:
    est = estimate_sc_rate(AsOfAccessor(sc_history_db).history(AsOf("2023-06", 11)))
    n, laps = 2000, 100
    mask = _mask(est.rate_per_lap, est.duration_laps, laps, n, "sobol_antithetic")
    freq, at_risk = _start_frequency(mask, est.duration_laps)
    sigma = (est.rate_per_lap * (1 - est.rate_per_lap) / at_risk) ** 0.5
    assert abs(freq - est.rate_per_lap) < 4 * sigma
