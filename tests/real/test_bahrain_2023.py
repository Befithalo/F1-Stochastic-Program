"""Real-data checks for the 2023 Bahrain Grand Prix (D-10).

These tests call OpenF1 and Jolpica (through the shared HTTP cache in `data/http-cache`, so a
second run makes no calls). They carry the `network` marker, so the normal `pytest` run and the
push CI skip them; run them with `uv run pytest -m network -v tests/real`. The weekly
`real-data.yml` workflow does the same on GitHub and is not a required check.

The expectations are facts about the real race: 20 starters, 57 laps, a virtual safety car on
lap 41 (race-clock seconds 4,000 to 4,110), VER on pole and the winner.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from f1si import cli, paths
from f1si.backtest.walk_forward import _race_laps_total
from f1si.data import _db
from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.data.loader import backfill_scheduled_laps, load_races
from f1si.data.results import ResultsAccessor
from f1si.data.sources.openf1 import OpenF1Source
from f1si.plots.stints import build_figure, prepare_stint_plot_data, render_stint_plot
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel

pytestmark = pytest.mark.network

RACE_ID = "2023-01"
SLUG = "bahrain-2023"
LAST_LAP = 57


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Bahrain 2023 loaded into a temporary cache (the HTTP cache is shared and reused)."""
    db_path = tmp_path_factory.mktemp("real") / "f1si.duckdb"
    source = OpenF1Source(http_cache_dir=paths.http_cache_dir(paths.data_dir()), echo=print)
    report = load_races(
        source,
        db_path,
        [2023],
        now=datetime.now(UTC),
        echo=print,
        only=[SLUG],
    )
    assert report.failed == []
    lap_counts = backfill_scheduled_laps(
        db_path,
        fastf1_cache_dir=paths.http_cache_dir(paths.data_dir()) / "fastf1",
        provenance_path=db_path.parent / "lap-count-provenance.csv",
        echo=lambda _line: None,
    )
    assert lap_counts.failed == []
    assert lap_counts.eligible_count == 1
    return db_path


def _cutoffs(db_path: Path) -> dict[int, float]:
    frame = _db.read_df(
        db_path, "SELECT lap, cutoff_s FROM lap_cutoffs WHERE race_id = ? ORDER BY lap", [RACE_ID]
    )
    return {
        int(lap): float(cutoff) for lap, cutoff in zip(frame["lap"], frame["cutoff_s"], strict=True)
    }


def test_entries(db: Path) -> None:
    entries = _db.read_table(db, "entries", race_id=RACE_ID)
    assert len(entries) == 20
    ver = entries[entries["driver_code"] == "VER"]
    assert len(ver) == 1
    assert int(ver["grid_position"].iloc[0]) == 1


def test_laps(db: Path) -> None:
    laps = _db.read_table(db, "laps", race_id=RACE_ID)
    assert int(laps["lap_number"].max()) == LAST_LAP
    assert 1_050 <= len(laps) <= 1_100
    compounds = {str(c) for c in laps["compound"].dropna().unique()}
    assert compounds <= {"SOFT", "MEDIUM", "HARD"}


def test_virtual_safety_car_window(db: Path) -> None:
    cutoffs = _cutoffs(db)
    track = _db.read_table(db, "track_status", race_id=RACE_ID).sort_values("t_s")
    vsc = track[
        (track["status"] == "6") & (track["t_s"] > cutoffs[39]) & (track["t_s"] <= cutoffs[42])
    ]
    assert len(vsc) >= 1
    start = float(vsc["t_s"].iloc[0])
    clear = track[(track["status"] == "1") & (track["t_s"] > start) & (track["t_s"] <= cutoffs[45])]
    assert len(clear) >= 1


def test_pit_stops(db: Path) -> None:
    laps = _db.read_table(db, "laps", race_id=RACE_ID)
    assert 35 <= int(laps["is_pit_in_lap"].sum()) <= 60
    stops = _db.read_table(db, "pit_stops", race_id=RACE_ID)
    assert len(stops) > 0


def test_lap_cutoffs(db: Path) -> None:
    cutoffs = _cutoffs(db)
    assert sorted(cutoffs) == list(range(LAST_LAP + 1))
    values = [cutoffs[lap] for lap in range(LAST_LAP + 1)]
    assert all(a <= b for a, b in itertools.pairwise(values))
    assert 5_400 < cutoffs[LAST_LAP] < 6_000


def test_results_door(db: Path) -> None:
    final = ResultsAccessor(db).final_classification(RACE_ID)
    winner = final[final["driver_code"] == "VER"]
    assert len(winner) == 1
    assert int(winner["final_position"].iloc[0]) == 1


def test_as_of_rule_on_real_data(db: Path) -> None:
    snapshot = AsOfAccessor(db).snapshot(AsOf(RACE_ID, 15))
    laps_done = snapshot.cars["laps_done"].astype(int)
    assert int((laps_done == 15).sum()) == 1
    assert int(laps_done.max()) == 15
    assert int((laps_done <= 14).sum()) == len(laps_done) - 1


def test_lap_15_replay_ranks_stay_out_and_every_legal_box_timing(db: Path) -> None:
    accessor = AsOfAccessor(db)
    first = accessor.snapshot(AsOf(RACE_ID, 0))
    laps_total = _race_laps_total(accessor, RACE_ID, first)
    snapshot = accessor.snapshot(AsOf(RACE_ID, 15))
    context = cli._prepare_replay_context(accessor, RACE_ID, laps_total, 15, snapshot=snapshot)
    cutoff = cli._replay_at_cutoff(
        accessor, RACE_ID, laps_total, "ALO", 15, 1000, 0.5, 0, prepared_context=context
    )

    assert cutoff.analysis is not None
    timing_actions = {row.action.split(" (", maxsplit=1)[0] for row in cutoff.analysis.options}
    assert timing_actions == {
        "stay out",
        "pit now",
        "pit in 1 lap(s)",
        "pit in 2 lap(s)",
        "pit in 3 lap(s)",
        "pit in 4 lap(s)",
        "pit in 5 lap(s)",
    }
    assert cutoff.analysis.best.plan.stop_laps == (16,)

    simulator = NumpySimulator(
        context.model,
        sc=SafetyCarModel(context.estimate.rate_per_lap, context.estimate.duration_laps),
        compounds=context.compounds,
        wear_sd_by_compound=context.wear_sd_by_compound,
    )
    simulation = simulator.simulate(
        context.state,
        n_races=1000,
        rng=make_rng(0),
        plans={"ALO": cutoff.analysis.best.plan},
        position_history_driver="ALO",
    )
    driver_index = [car.driver for car in context.state.cars].index("ALO")
    assert simulation.stop_laps is not None
    assert (simulation.stop_laps[:, driver_index, 0] == 16).all()


def test_bahrain_lap_15_top_classified_forecasts_are_within_five_places(db: Path) -> None:
    """Check the five best classified forecasts after building every forecast cutoff-safely."""
    accessor = AsOfAccessor(db)
    first = accessor.snapshot(AsOf(RACE_ID, 0))
    laps_total = _race_laps_total(accessor, RACE_ID, first)
    snapshot = accessor.snapshot(AsOf(RACE_ID, 15))
    context = cli._prepare_replay_context(accessor, RACE_ID, laps_total, 15, snapshot=snapshot)

    # Build every model prediction before opening the actual classification. The model-ranked
    # sample is selected first; drivers who retired are excluded because retirements are not
    # simulated and therefore have no comparable predicted finishing place.
    predicted_mean: dict[str, float] = {}
    for car in context.state.cars:
        code = car.driver
        outcome = cli._replay_at_cutoff(
            accessor, RACE_ID, laps_total, code, 15, 1000, 0.5, 0, prepared_context=context
        )
        assert outcome.analysis is not None
        predicted_mean[code] = outcome.analysis.best.mean_finish

    actual = ResultsAccessor(db).final_classification(RACE_ID)
    classified = actual.loc[actual["final_position"].notna()].set_index("driver_code")
    forecast_order = sorted(predicted_mean, key=predicted_mean.__getitem__)
    top_five_codes = [code for code in forecast_order if code in classified.index][:5]
    assert len(top_five_codes) == 5
    errors = {
        code: abs(predicted_mean[code] - float(cast(Any, classified.loc[code, "final_position"])))
        for code in top_five_codes
    }
    assert all(error <= 5.0 for error in errors.values()), errors


def test_stint_plot(db: Path, tmp_path: Path) -> None:
    snapshot = AsOfAccessor(db).snapshot(AsOf(RACE_ID, RACE_END))
    data = prepare_stint_plot_data(snapshot)
    assert len(data.drivers) == 20
    figure = build_figure(data)
    assert sum(1 for ax in figure.axes if ax.get_visible()) == 20
    out = render_stint_plot(data, tmp_path / "bahrain-2023.png")
    assert out.is_file()
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
