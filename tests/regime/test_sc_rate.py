"""REG-01: the safety-car rate and duration estimator (D-01 to D-03, D-06)."""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from f1si import paths
from f1si.data.asof import AsOf, AsOfAccessor, History
from f1si.data.loader import load_races
from f1si.data.sources.synthetic_source import SyntheticSource
from f1si.regime.sc_rate import (
    FALLBACK_DURATION_LAPS,
    MIN_EVENTS_FOR_MEDIAN,
    PRIOR_ALPHA,
    PRIOR_BETA,
    ScRateEstimate,
    estimate_sc_rate,
)
from f1si.rng import make_rng
from f1si.synthetic import SyntheticRaceSpec
from tests.conftest import SC_HISTORY_CURRENT_RACE_ID, SC_HISTORY_EARLIER

N_LAPS_SC_HISTORY = 40


def _estimate(db: Path, race_id: str) -> ScRateEstimate:
    return estimate_sc_rate(AsOfAccessor(db).history(AsOf(race_id, 0)))


def test_constants() -> None:
    assert (PRIOR_ALPHA, PRIOR_BETA) == (3.0, 297.0)
    assert (MIN_EVENTS_FOR_MEDIAN, FALLBACK_DURATION_LAPS) == (5, 4)


def test_first_race_gets_the_prior_alone(sc_history_db: Path) -> None:
    est = _estimate(sc_history_db, "2023-01")
    assert est.is_prior_only
    assert (est.n_deployments, est.n_laps, est.n_durations) == (0, 0, 0)
    assert est.rate_per_lap == pytest.approx(3 / 300)
    assert est.duration_laps == 4
    assert est.ci_low < 0.01 < est.ci_high


def test_pooling_over_earlier_races(sc_history_db: Path) -> None:
    est = _estimate(sc_history_db, SC_HISTORY_CURRENT_RACE_ID)
    k = sum(len(laps) for laps, _ in SC_HISTORY_EARLIER)
    n = 5 * N_LAPS_SC_HISTORY
    assert not est.is_prior_only
    assert est.n_deployments == k
    assert est.n_laps == n
    assert est.rate_per_lap == pytest.approx((3 + k) / (300 + n))


def _durations_db(folder: Path, per_race: list[tuple[tuple[int, ...], int]]) -> Path:
    specs = [
        SyntheticRaceSpec(
            2023,
            rnd,
            f"Dur {rnd:02d}",
            n_drivers=4,
            n_laps=40,
            sc_laps=laps,
            sc_duration_laps=dur,
        )
        for rnd, (laps, dur) in enumerate([*per_race, ((), 4)], start=1)
    ]
    folder.mkdir(parents=True, exist_ok=True)
    load_races(
        SyntheticSource(specs, rng=make_rng(11)),
        paths.db_path(folder),
        (2023,),
        now=datetime(2026, 10, 22, tzinfo=UTC),
        echo=lambda _line: None,
    )
    return paths.db_path(folder)


def test_duration_is_the_median_when_enough_events(tmp_path: Path) -> None:
    db = _durations_db(tmp_path, [((5, 20), 3)] * 3)
    est = _estimate(db, "2023-04")
    assert est.n_deployments == 6
    assert est.n_durations >= 5
    assert est.duration_laps == 3


def test_duration_falls_back_with_few_events(tmp_path: Path) -> None:
    db = _durations_db(tmp_path, [((5, 20), 2)])
    est = _estimate(db, "2023-02")
    assert est.n_durations == 2
    assert est.duration_laps == 4


def _history(statuses: list[str | None]) -> History:
    """A one-race History whose track_status rows are `statuses` at t = 10, 20, ..."""
    rows = [
        {"race_id": "r1", "seq": i, "t_s": 10.0 * (i + 1), "status": s, "message": ""}
        for i, s in enumerate(statuses)
    ]
    cut = [0.0, 15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 1000.0]
    empty = pd.DataFrame()
    return History(
        as_of=AsOf("r2", 0),
        races=["r1"],
        entries=empty,
        laps=empty,
        track_status=pd.DataFrame(rows),
        race_control=empty,
        weather=empty,
        lap_cutoffs=pd.DataFrame({"race_id": "r1", "lap": range(len(cut)), "cutoff_s": cut}),
        results=empty,
    )


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["1", "5", "4"], 0),
        (["1", "2", "4"], 1),
        (["1", "6", "7", "4"], 1),
        (["1", "4", "4"], 1),
        (["4"], 1),
        (["1", "4", "1", "4", "1"], 2),
    ],
)
def test_edge_rule(statuses: list[str | None], expected: int) -> None:
    assert estimate_sc_rate(_history(statuses)).n_deployments == expected


def test_red_flag_ends_and_open_ends_are_not_durations() -> None:
    red = estimate_sc_rate(_history(["1", "4", "5"]))
    assert (red.n_deployments, red.n_durations) == (1, 0)
    open_ended = estimate_sc_rate(_history(["1", "4"]))
    assert (open_ended.n_deployments, open_ended.n_durations) == (1, 0)
    closed = estimate_sc_rate(_history(["1", "4", "1"]))
    assert (closed.n_deployments, closed.n_durations) == (1, 1)


def test_empty_history_returns_the_prior() -> None:
    empty = pd.DataFrame()
    history = History(
        as_of=AsOf("r1", 0),
        races=[],
        entries=empty,
        laps=empty,
        track_status=empty,
        race_control=empty,
        weather=empty,
        lap_cutoffs=empty,
        results=empty,
    )
    est = estimate_sc_rate(history)
    assert est.is_prior_only
    assert est.rate_per_lap == pytest.approx(0.01)


def test_estimate_validates_itself() -> None:
    good: dict[str, float | int | bool] = {
        "rate_per_lap": 0.01,
        "ci_low": 0.005,
        "ci_high": 0.02,
        "n_deployments": 1,
        "n_laps": 10,
        "duration_laps": 4,
        "n_durations": 0,
        "is_prior_only": False,
    }
    ScRateEstimate(**good)  # type: ignore[arg-type]
    for bad in ({"rate_per_lap": 1.5}, {"ci_low": 0.5}, {"duration_laps": 0}, {"n_laps": -1}):
        with pytest.raises(ValueError, match=r"-?\d"):
            ScRateEstimate(**{**good, **bad})  # type: ignore[arg-type]


TRUE_RATE = 0.025
N_RACES = 24
N_LAPS = 100


def _recovery_db(folder: Path, seed: int) -> Path:
    """24 races x 100 laps x 4 drivers; each lap is a deployment lap with probability 0.025.

    One-lap safety cars cannot overlap, so deployments per race lap are exactly i.i.d. Bernoulli.
    The generator is not asked to draw SC laps (its stream is unchanged).
    """
    rng = make_rng(seed)
    specs = []
    for rnd in range(1, N_RACES + 1):
        laps = tuple(int(i) + 1 for i in np.flatnonzero(rng.random(N_LAPS) < TRUE_RATE))
        specs.append(
            SyntheticRaceSpec(
                2023,
                rnd,
                f"Rec {rnd:02d}",
                n_drivers=4,
                n_laps=N_LAPS,
                sc_laps=laps,
                sc_duration_laps=1,
            )
        )
    folder.mkdir(parents=True, exist_ok=True)
    load_races(
        SyntheticSource(specs, rng=make_rng(seed + 1000)),
        paths.db_path(folder),
        (2023,),
        now=datetime(2026, 10, 22, tzinfo=UTC),
        echo=lambda _line: None,
    )
    return paths.db_path(folder)


def test_recovers_a_known_rate(tmp_path: Path) -> None:
    covered = 0
    for seed in range(5):
        db = _recovery_db(tmp_path / f"s{seed}", seed)
        est = _estimate(db, f"2023-{N_RACES:02d}")
        assert est.n_laps == (N_RACES - 1) * N_LAPS
        a = PRIOR_ALPHA + est.n_deployments
        b = PRIOR_BETA + est.n_laps - est.n_deployments
        sd = float(np.sqrt(a * b / ((a + b) ** 2 * (a + b + 1))))
        empirical = est.n_deployments / est.n_laps
        assert abs(est.rate_per_lap - empirical) < 3 * sd
        covered += int(est.ci_low <= TRUE_RATE <= est.ci_high)
    assert covered >= 4
