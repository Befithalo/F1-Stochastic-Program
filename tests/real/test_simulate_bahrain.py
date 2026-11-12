"""Real-data checks for the Monte Carlo simulator at Bahrain 2023.

These tests read the owner's local cache (`data/f1si.duckdb`) and never write to it (PNG files go
under pytest's `tmp_path`). They carry the `network` marker, so the normal `pytest` run and the
push CI skip them; run them with
`uv run python -m pytest -m network -v tests/real/test_simulate_bahrain.py`. If the race is not
cached, or ALO is not among the entries, they skip and tell you to run
`uv run f1si load --only bahrain-2023`.

The bands are deliberately loose: they check that the numbers are sensible, not exact.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from f1si import paths
from f1si.cli import main
from f1si.data import asof
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.pace.linear import fit_linear_pace, measure_pit_loss
from f1si.regime.sc_rate import estimate_sc_rate
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import RaceState, build_race_state

pytestmark = pytest.mark.network

SLUG = "bahrain-2023"
LAPS_TOTAL = 57
HINT = "run `uv run f1si load --only bahrain-2023` first"


@pytest.fixture(scope="module")
def db() -> Path:
    path = paths.db_path(paths.data_dir())
    if not path.is_file():
        pytest.skip(f"no local cache at {path}; {HINT}")
    try:
        asof.resolve_slug(path, SLUG)
    except Exception:
        pytest.skip(f"{SLUG} is not in the local cache; {HINT}")
    return path


@pytest.fixture(scope="module")
def race_id(db: Path) -> str:
    return asof.resolve_slug(db, SLUG)


def _simulator_and_state(
    db: Path, race_id: str, lap: int, *, hindsight: bool
) -> tuple[NumpySimulator, RaceState, bool, int]:
    accessor = AsOfAccessor(db)
    state_snapshot = accessor.snapshot(AsOf(race_id, lap))
    fit_snapshot = accessor.snapshot(AsOf(race_id, RACE_END)) if hindsight else state_snapshot
    fit = fit_linear_pace(fit_snapshot)
    pit = measure_pit_loss(fit_snapshot, fit)
    state = build_race_state(state_snapshot, fit, laps_total=LAPS_TOTAL, pit_loss_s=pit.median_s)
    if "ALO" not in {c.driver for c in state.cars}:
        pytest.skip("ALO is not in the cached entries")
    estimate = estimate_sc_rate(accessor.history(AsOf(race_id, lap)))
    simulator = NumpySimulator(
        fit,
        sc=SafetyCarModel(estimate.rate_per_lap, estimate.duration_laps),
        compounds=fit.fitted_compounds,
        wear_sd_by_compound={c.compound: c.se for c in fit.report.compounds},
    )
    return simulator, state, estimate.is_prior_only, estimate.duration_laps


def test_alonso_distribution_at_lap_zero(db: Path, race_id: str) -> None:
    simulator, state, _, _ = _simulator_and_state(db, race_id, 0, hindsight=True)
    result = simulator.simulate(state, n_races=5000, rng=np.random.default_rng(1))
    n_cars = len(state.cars)
    assert result.finish_positions.shape == (5000, n_cars)
    ordered = np.sort(result.finish_positions, axis=1)
    assert (ordered == np.arange(1, n_cars + 1)).all()  # every row is a permutation
    column = [c.driver for c in state.cars].index("ALO")
    mine = result.finish_positions[:, column]
    shares = np.bincount(mine, minlength=n_cars + 1)[1:] / 5000.0
    assert shares.sum() == pytest.approx(1.0)
    assert 1.0 <= float(mine.mean()) <= 20.0


def test_sc_rate_is_prior_only_at_bahrain(db: Path, race_id: str) -> None:
    estimate = estimate_sc_rate(AsOfAccessor(db).history(AsOf(race_id, 0)))
    assert estimate.is_prior_only
    assert estimate.rate_per_lap == pytest.approx(0.01)
    assert estimate.duration_laps == 4


def test_lap_30_borrowed_pace_and_retired_car(db: Path, race_id: str) -> None:
    simulator, state, _, _ = _simulator_and_state(db, race_id, 30, hindsight=False)
    result = simulator.simulate(state, n_races=2000, rng=np.random.default_rng(2))
    assert result.finish_positions.shape[0] == 2000
    notes = " ".join(result.diagnostics)
    unfitted = {str(c.compound).upper() for c in state.cars} - set(simulator_compounds(simulator))
    if unfitted:
        assert "borrowed" in notes
    # PIA retired on lap 13 and is absent from the fit: placed last or named in the notes.
    codes = [c.driver for c in state.cars]
    if "PIA" in codes:
        column = codes.index("PIA")
        last = len(codes)
        placed_last = bool((result.finish_positions[:, column] == last).all())
        assert placed_last or "PIA" in notes


def simulator_compounds(simulator: NumpySimulator) -> list[str]:
    """Compounds the simulator prices directly (private attribute read, test use only)."""
    return list(getattr(simulator, "_compounds", ()))


def test_fifty_thousand_races_under_ten_seconds(db: Path, race_id: str) -> None:
    simulator, state, _, _ = _simulator_and_state(db, race_id, 0, hindsight=True)
    simulator.simulate(state, n_races=64, rng=np.random.default_rng(3))  # warm-up
    started = time.perf_counter()
    simulator.simulate(state, n_races=50_000, rng=np.random.default_rng(3))
    assert time.perf_counter() - started < 10.0


def test_simulate_command(db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--data-dir",
            str(db.parent),
            "--reports-dir",
            str(tmp_path),
            "simulate",
            SLUG,
            "--driver",
            "ALO",
            "--n",
            "2000",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "hindsight simulation" in out
    assert "prior only" in out
    assert (tmp_path / "sim-bahrain-2023-ALO-lap0.png").is_file()


def test_leader_beats_last_car(db: Path, race_id: str) -> None:
    """The car running first after lap 5 finishes better on average than the car running last.

    Positions are unknown at lap 0 (no timing yet), so the check uses the state after lap 5.
    """
    simulator, state, _, _ = _simulator_and_state(db, race_id, 5, hindsight=True)
    result = simulator.simulate(state, n_races=3000, rng=np.random.default_rng(4))
    ranked = [(c.position, i) for i, c in enumerate(state.cars) if c.position is not None]
    leader = min(ranked)[1]
    last = max(ranked)[1]
    means = result.finish_positions.mean(axis=0)
    assert means[leader] < means[last]
