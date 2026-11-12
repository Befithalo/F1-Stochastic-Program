"""SIM-03: Sobol plus antithetic sampling is less noisy than plain Monte Carlo (D-14).

D-14: "variance reduction is shown by running both arms at equal N over independent seeds and
comparing the variance of the estimators". The CONTEXT example uses 40 seeds; the sampling error
of a variance ratio at R = 40 is about 30%, so this test uses R = 120 (about 13%). N = 1024 races
(a power of two, so the Sobol blocks are balanced) of a 10-car, 30-lap trimmed copy of the long
synthetic race.

Asserted estimators: the chosen driver's mean finishing position, mean total time, and the
safety-car share. P(top 5) is report-only: it is a threshold indicator of a noise-dominated
integrand and Sobol is not expected to help it (RESEARCH Pitfall 8).
Both arms run through the same `NumpySimulator`; only `variance_reduction` changes.
"""

from dataclasses import replace

import numpy as np
import pytest

from f1si.pace.linear import LinearPaceFit
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import RaceState

R = 120
N = 1024
CHOSEN = 4
N_CARS = 10
GAP_S = 0.5
RATIO_MEAN_FINISH = 3.4  # measured 4.54
RATIO_TOTAL_TIME = 12.0  # measured 16.43
RATIO_SC_SHARE = 2.4  # measured 3.19

Ests = dict[str, np.ndarray]


def _arm(state: RaceState, fit: LinearPaceFit, mode: str) -> Ests:
    sim = NumpySimulator(
        fit,
        sc=SafetyCarModel(0.03, 3),
        compounds=fit.fitted_compounds,
        wear_sd_by_compound={c: fit.wear_se(c) for c in fit.fitted_compounds},
        variance_reduction=mode,  # type: ignore[arg-type]
    )
    out: dict[str, list[float]] = {"finish": [], "time": [], "sc": [], "top5": []}
    for s in range(R):
        res = sim.simulate(state, n_races=N, rng=make_rng(1000 + s))
        assert res.sc_lap_mask is not None
        pos = res.finish_positions[:, CHOSEN]
        out["finish"].append(float(pos.mean()))
        out["time"].append(float(res.total_time_s[:, CHOSEN].mean()))
        out["sc"].append(float(res.sc_lap_mask.any(axis=1).mean()))
        out["top5"].append(float((pos <= 5).mean()))
    return {k: np.array(v) for k, v in out.items()}


@pytest.fixture(scope="module")
def small(long_lap0: tuple[RaceState, LinearPaceFit]) -> tuple[RaceState, LinearPaceFit]:
    state, fit = long_lap0
    # a contested field: cars 0.5 s apart and mixed pace offsets, so positions actually change
    cars = tuple(
        replace(
            c,
            gap_ahead_s=None if i == 0 else GAP_S,
            gap_behind_s=None if i == N_CARS - 1 else GAP_S,
            pace_offset_s=0.1 * ((i * 7) % 10) - 0.45,
            pace_offset_sd=0.2,
        )
        for i, c in enumerate(state.cars[:N_CARS])
    )
    return replace(state, cars=cars, laps_total=30), fit


@pytest.fixture(scope="module")
def arms(small: tuple[RaceState, LinearPaceFit]) -> tuple[Ests, Ests]:
    state, fit = small
    return _arm(state, fit, "none"), _arm(state, fit, "sobol_antithetic")


def _ratios(arms: tuple[Ests, Ests]) -> dict[str, float]:
    plain, vr = arms
    return {k: float(plain[k].var(ddof=1) / vr[k].var(ddof=1)) for k in plain}


def test_variance_ratios(arms: tuple[Ests, Ests]) -> None:
    r = _ratios(arms)
    print(f"\nvariance ratios none/sobol_antithetic (R={R}, N={N}): {r}")
    assert r["finish"] >= RATIO_MEAN_FINISH, r
    assert r["time"] >= RATIO_TOTAL_TIME, r
    assert r["sc"] >= RATIO_SC_SHARE, r


def test_top5_report_only(arms: tuple[Ests, Ests]) -> None:
    ratio = _ratios(arms)["top5"]
    print(f"\nP(top 5) variance ratio (report only): {ratio:.3f}")
    assert np.isfinite(ratio), f"P(top 5) ratio {ratio}"
    assert ratio > 0, f"P(top 5) ratio {ratio}"


def test_no_bias(arms: tuple[Ests, Ests]) -> None:
    plain, vr = arms
    for key in ("finish", "time", "sc"):
        se = np.sqrt(plain[key].var(ddof=1) / R + vr[key].var(ddof=1) / R)
        diff = abs(plain[key].mean() - vr[key].mean())
        assert diff < 4 * se, (key, diff, se)


def test_deterministic(small: tuple[RaceState, LinearPaceFit], arms: tuple[Ests, Ests]) -> None:
    state, fit = small
    again = (_arm(state, fit, "none"), _arm(state, fit, "sobol_antithetic"))
    assert _ratios(again) == _ratios(arms)
