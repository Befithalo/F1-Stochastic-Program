"""Real-data checks for tyre wear, race state and the free-track plan at Bahrain 2023.

These tests read the owner's local cache (`data/f1si.duckdb`) and never write to it. They carry
the `network` marker, so the normal `pytest` run and the push CI skip them; run them with
`uv run pytest -m network -v tests/real/test_wear_bahrain.py`. If the race is not cached, they
skip and tell you to run `uv run f1si load --only bahrain-2023`.

The bands are deliberately loose: they check that the numbers are sensible, not exact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from f1si import paths
from f1si.cli import main
from f1si.data import asof
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, RaceEnd, RaceSnapshot
from f1si.pace.linear import LinearPaceFit, PitLossEstimate, fit_linear_pace, measure_pit_loss
from f1si.state import RaceState, build_race_state
from f1si.strategy.free_track import FreeTrackOptimizer

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


@pytest.fixture(scope="module")
def end(db: Path, race_id: str) -> RaceSnapshot:
    return AsOfAccessor(db).snapshot(AsOf(race_id, RACE_END))


@pytest.fixture(scope="module")
def fit(end: RaceSnapshot) -> LinearPaceFit:
    return fit_linear_pace(end)


@pytest.fixture(scope="module")
def pit(end: RaceSnapshot, fit: LinearPaceFit) -> PitLossEstimate:
    return measure_pit_loss(end, fit)


def test_wear_rates(fit: LinearPaceFit) -> None:
    assert fit.is_identified
    for compound in ("SOFT", "HARD"):
        rate = fit.wear_rate(compound)
        se = fit.wear_se(compound)
        assert rate is not None
        assert 0.08 <= rate <= 0.17, (compound, rate)
        assert se is not None
        assert se > 0
    assert "MEDIUM" in fit.report.not_enough_data
    assert fit.fuel_effect is not None
    assert fit.fuel_effect < 0


def test_pit_loss(pit: PitLossEstimate) -> None:
    assert not pit.is_default
    assert 22.0 <= pit.median_s <= 28.0


def _state(
    db: Path, race_id: str, fit: LinearPaceFit, pit: PitLossEstimate, lap: int | RaceEnd
) -> RaceState:
    snapshot = AsOfAccessor(db).snapshot(AsOf(race_id, lap))
    return build_race_state(snapshot, fit, laps_total=LAPS_TOTAL, pit_loss_s=pit.median_s)


def test_race_state_at_three_laps(
    db: Path, race_id: str, fit: LinearPaceFit, pit: PitLossEstimate
) -> None:
    states = {
        0: _state(db, race_id, fit, pit, 0),
        20: _state(db, race_id, fit, pit, 20),
        "end": _state(db, race_id, fit, pit, RACE_END),
    }
    for state in states.values():
        assert len(state.cars) == 20
        assert RaceState.from_json(state.to_json()) == state
    assert states[0].lap == 0
    assert states[20].lap == 20
    leader = next(c for c in states[20].cars if c.position == 1)
    assert leader.gap_ahead_s is None


@pytest.fixture(scope="module")
def optimizer(fit: LinearPaceFit) -> FreeTrackOptimizer:
    return FreeTrackOptimizer(fit, compounds=fit.fitted_compounds)


def test_ranked_plan_for_alonso(
    db: Path,
    race_id: str,
    fit: LinearPaceFit,
    pit: PitLossEstimate,
    optimizer: FreeTrackOptimizer,
) -> None:
    state = _state(db, race_id, fit, pit, 0)
    if "ALO" not in {c.driver for c in state.cars}:
        pytest.skip("ALO is not in the cached entries")
    plans = optimizer.rank_plans(state, driver="ALO")
    assert len(plans) > 1_000
    assert all(plan.n_stops in (1, 2) for plan in plans)
    assert any(plan.n_stops == 1 for plan in plans)
    assert any(plan.n_stops == 2 for plan in plans)
    decision = optimizer.decide(state, driver="ALO")
    assert decision.best_plan == plans[0]


def test_plan_command(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--data-dir", str(db.parent), "plan", SLUG, "--driver", "ALO"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Hindsight plan" in out
