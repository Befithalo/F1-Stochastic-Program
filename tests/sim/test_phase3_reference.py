"""Phase 3 simulator reference (PAC-03 guard, assumption A5): fit cars stay byte-identical.

The arrays in tests/fixtures/phase3_reference.npz were captured once from the unmodified
Phase 3 simulator for a fixed seed and a hand-built state (safety cars on, wear draws on).
Plan 04-03 changes how per-car wear is fed to the simulator; these tests prove "fit" cars
are untouched by that change. They must never be regenerated to make a failing run pass.

Regenerate only on purpose, from unmodified simulator code:
    python -m tests.sim.test_phase3_reference
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel

from .conftest import ZeroNoisePace, hand_state

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
NPZ = FIXTURES / "phase3_reference.npz"
META = FIXTURES / "phase3_reference.json"
SEED = 20260101
N_RACES = 256


def _run() -> tuple[np.ndarray, np.ndarray]:
    """Finish positions and total times of the fixed reference scenario."""
    state = hand_state(6, lap=3, laps_total=12, spacing_s=2.0, tire_age=3)
    sim = NumpySimulator(
        ZeroNoisePace(),
        sc=SafetyCarModel(0.05, 3),
        compounds=("HARD", "MEDIUM"),
        wear_sd_by_compound={"HARD": 0.01, "MEDIUM": 0.01},
    )
    result = sim.simulate(state, n_races=N_RACES, rng=make_rng(SEED))
    return result.finish_positions, result.total_time_s


def _sha(arr: np.ndarray) -> str:
    return hashlib.sha256(arr.tobytes()).hexdigest()


def generate_reference() -> None:
    """One-off writer of the fixture files (run once on unmodified simulator code)."""
    finish, total = _run()
    np.savez(NPZ, finish_positions=finish, total_time_s=total)
    META.write_text(
        json.dumps(
            {
                "sha256_finish_positions": _sha(finish),
                "sha256_total_time_s": _sha(total),
                "platform": sys.platform,
                "n_races": N_RACES,
                "seed": SEED,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_fit_cars_match_phase3_arrays() -> None:
    """Cross-platform gate: exact finish order, total times within one-ulp-scale tolerance."""
    ref = np.load(NPZ)
    finish, total = _run()
    assert np.array_equal(finish, ref["finish_positions"])
    assert np.allclose(total, ref["total_time_s"], rtol=0, atol=1e-9)


def test_fit_cars_match_phase3_hash() -> None:
    """Same-machine gate: sha256 of both arrays; skipped on CI and on other platforms.

    The hash was recorded on the owner's machine and float bit patterns can differ across
    operating systems and CPUs, so this only runs where the bits are comparable.
    """
    import os

    meta = json.loads(META.read_text(encoding="utf-8"))
    if os.environ.get("CI"):
        pytest.skip("reference hash recorded on the owner's machine; CI uses the array test")
    if sys.platform != meta["platform"]:
        pytest.skip(f"reference hash recorded on {meta['platform']}")
    finish, total = _run()
    assert _sha(finish) == meta["sha256_finish_positions"]
    assert _sha(total) == meta["sha256_total_time_s"]


def test_reference_run_is_deterministic() -> None:
    a_finish, a_total = _run()
    b_finish, b_total = _run()
    assert np.array_equal(a_finish, b_finish)
    assert np.array_equal(a_total, b_total)


if __name__ == "__main__":
    generate_reference()
