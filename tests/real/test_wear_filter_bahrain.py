"""Real-data checks for the Kalman tyre-wear filter at Bahrain 2023 (ALO).

These tests read the owner's local cache (`data/f1si.duckdb`) and never write to it. They carry the
`network` marker, so the normal `pytest` run and the push CI skip them; run them with
`uv run python -m pytest -m network -v tests/real/test_wear_filter_bahrain.py -s`. If the cache,
the race or ALO is missing, they skip and tell you to run `uv run f1si load --only bahrain-2023`.

The bands are deliberately loose. Observations (the fit prior at laps 14, 20 and 30, the 90%
finishing interval with and without the filter) are printed and never gated.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pytest

from f1si import paths
from f1si.data import asof
from f1si.data.asof import AsOf, AsOfAccessor, RaceEnd, RaceSnapshot
from f1si.pace.kalman import (
    CutoffRow,
    StintFilterResult,
    current_stint_snapshots,
    cutoff_row,
    filter_stints,
    resolve_priors,
)
from f1si.pace.linear import fit_linear_pace, measure_pit_loss
from f1si.regime.sc_rate import estimate_sc_rate
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel
from f1si.state import build_race_state

pytestmark = pytest.mark.network

SLUG = "bahrain-2023"
LAPS_TOTAL = 57
DRIVER = "ALO"
HINT = "run `uv run f1si load --only bahrain-2023` first"
TOL = 1e-12


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
def number(db: Path, race_id: str) -> int:
    entries = AsOfAccessor(db).snapshot(AsOf(race_id, asof.RACE_END)).entries
    mine = entries[entries["driver_code"] == DRIVER]
    if mine.empty:
        pytest.skip(f"{DRIVER} is not in the cached entries")
    return int(mine["driver_number"].iloc[0])


def _results(
    db: Path, race_id: str, cutoff: int | RaceEnd, number: int
) -> tuple[tuple[StintFilterResult, ...], RaceSnapshot]:
    snapshot = AsOfAccessor(db).snapshot(AsOf(race_id, cutoff))
    fit = fit_linear_pace(snapshot)
    return filter_stints(snapshot, fit, driver_numbers=[number]), snapshot


def test_first_stint_is_prior_only_early_and_ages_match(
    db: Path, race_id: str, number: int
) -> None:
    end_results, _ = _results(db, race_id, asof.RACE_END, number)
    assert end_results, "every ALO stint should have a result at the race end"
    early, snapshot = _results(db, race_id, 13, number)
    first = min(early, key=lambda r: r.stint)
    assert first.priors.rate_source.startswith("prior only")
    assert first.priors.fuel_source.startswith("prior only")
    laps = snapshot.laps
    mine = laps[(laps["driver_number"] == number) & (laps["stint"] == first.stint)]
    first_lap = mine.sort_values("lap_number").iloc[0]
    assert first.rows[0].race_lap == int(first_lap["lap_number"])
    assert first.rows[0].tyre_age == int(first_lap["tyre_life"])


def test_band_narrows_within_each_stint(db: Path, race_id: str, number: int) -> None:
    results, _ = _results(db, race_id, asof.RACE_END, number)
    for r in results:
        used = [row for row in r.rows if row.used]
        sds = [row.rate_sd for row in used]
        for a, b in itertools.pairwise(sds):
            assert b <= a + 1e-9, f"stint {r.stint}: SD rose from {a} to {b}"
        if len(used) >= 7:
            ratio = sds[6] / r.priors.prior.rate_sd
            print(
                f"\nstint {r.stint} {r.compound}: prior SD {r.priors.prior.rate_sd:.4f} "
                f"({r.priors.rate_source}), SD after 7 used laps {sds[6]:.4f}, ratio {ratio:.2f}"
            )
            assert sds[6] < r.priors.prior.rate_sd
            # The ratio is reported, not gated (owner, Phase 4 UAT): a tight fit prior (SD
            # about 0.03 s/lap) with noisy real laps narrows by only 5-7% in 7 laps, which is
            # the honest Bayes answer. Gated: SD never rises on a used lap and ends below the
            # prior SD.


def test_lap_20_row_is_reproducible_and_uses_own_fit(db: Path, race_id: str, number: int) -> None:
    accessor = AsOfAccessor(db)
    first_snap = accessor.snapshot(AsOf(race_id, 20))
    first = filter_stints(first_snap, fit_linear_pace(first_snap), driver_numbers=[number])
    fresh = accessor.snapshot(AsOf(race_id, 20))
    fresh_fit = fit_linear_pace(fresh)
    again = filter_stints(fresh, fresh_fit, driver_numbers=[number])
    row_a, row_b = cutoff_row(first, number, 20), cutoff_row(again, number, 20)
    assert row_a is not None
    assert row_a == row_b
    assert row_a.priors == resolve_priors(fresh_fit, row_a.compound)


def _comparable(a: CutoffRow, b: CutoffRow) -> bool:
    pa, pb = a.priors, b.priors
    return (
        a.stint == b.stint
        and pa.rate_source == pb.rate_source
        and pa.fuel_source == pb.fuel_source
        and pa.noise_source == pb.noise_source
        and abs(pa.prior.rate_mean - pb.prior.rate_mean) <= TOL
        and abs(pa.prior.rate_sd - pb.prior.rate_sd) <= TOL
        and abs(pa.prior.fuel_sd - pb.prior.fuel_sd) <= TOL
        and abs(pa.prior.sigma - pb.prior.sigma) <= TOL
    )


def test_replay_series_narrows_where_inputs_are_unchanged(
    db: Path, race_id: str, number: int
) -> None:
    accessor = AsOfAccessor(db)
    end_results, _ = _results(db, race_id, asof.RACE_END, number)
    stints = sorted(r.stint for r in end_results)[:2]
    laps = [row.race_lap for r in end_results if r.stint in stints for row in r.rows]
    cutoffs = range(min(laps), max(laps) + 2)
    picked: list[CutoffRow] = []
    for cutoff in cutoffs:
        snapshot = accessor.snapshot(AsOf(race_id, cutoff))
        results = filter_stints(snapshot, fit_linear_pace(snapshot), driver_numbers=[number])
        row = cutoff_row(results, number, cutoff)
        if row is not None and row.stint in stints:
            picked.append(row)
    checked = 0
    changed: list[int] = []
    for prev, cur in itertools.pairwise(picked):
        if prev.stint != cur.stint:
            continue
        if not _comparable(prev, cur):
            changed.append(cur.cutoff_lap)
            continue
        if prev.row.used and cur.row.used and cur.row.race_lap != prev.row.race_lap:
            checked += 1
            assert cur.row.rate_sd <= prev.row.rate_sd + 1e-9, (
                f"cutoff {cur.cutoff_lap}: SD rose {prev.row.rate_sd:.5f} -> "
                f"{cur.row.rate_sd:.5f} with unchanged inputs"
            )
    print(f"\nreplay narrowing: {checked} comparable pairs checked; inputs changed at {changed}")
    assert checked >= 3, f"only {checked} comparable consecutive pairs; the check would be vacuous"


def test_observation_fit_prior_at_laps_14_20_30(db: Path, race_id: str, number: int) -> None:
    accessor = AsOfAccessor(db)
    end = accessor.snapshot(AsOf(race_id, asof.RACE_END))
    end_fit = fit_linear_pace(end)
    print("\nPhase 2 fit prior for ALO's current compound (observation, not gated):")
    for cutoff in (14, 20, 30):
        snapshot = accessor.snapshot(AsOf(race_id, cutoff))
        fit = fit_linear_pace(snapshot)
        results = filter_stints(snapshot, fit, driver_numbers=[number])
        row = cutoff_row(results, number, cutoff)
        if row is None:
            print(f"  lap {cutoff}: no visible row")
            continue
        hindsight = end_fit.wear_rate(row.compound)
        shown = "n/a" if hindsight is None else f"{hindsight:+.3f}"
        print(
            f"  lap {cutoff}: {row.compound} rate prior {row.priors.prior.rate_mean:+.3f} "
            f"+/- {row.priors.prior.rate_sd:.3f} s/lap ({row.priors.rate_source}); "
            f"Phase 2 end-of-race value {shown}"
        )


def test_observation_interval_with_and_without_filter(db: Path, race_id: str, number: int) -> None:
    accessor = AsOfAccessor(db)
    cutoff = 20
    snapshot = accessor.snapshot(AsOf(race_id, cutoff))
    fit = fit_linear_pace(snapshot)
    pit = measure_pit_loss(snapshot, fit)
    results = filter_stints(snapshot, fit)
    filt = current_stint_snapshots(results)
    estimate = estimate_sc_rate(accessor.history(AsOf(race_id, cutoff)))
    widths: dict[str, float] = {}
    for label, wear_filter in (("without filter", None), ("with filter", filt)):
        state = build_race_state(
            snapshot, fit, laps_total=LAPS_TOTAL, pit_loss_s=pit.median_s, wear_filter=wear_filter
        )
        codes = [c.driver for c in state.cars]
        if DRIVER not in codes:
            pytest.skip(f"{DRIVER} is not in the race state")
        simulator = NumpySimulator(
            fit,
            sc=SafetyCarModel(estimate.rate_per_lap, estimate.duration_laps),
            compounds=fit.fitted_compounds,
            wear_sd_by_compound={c.compound: c.se for c in fit.report.compounds},
        )
        result = simulator.simulate(state, n_races=5000, rng=np.random.default_rng(20260101))
        mine = result.finish_positions[:, codes.index(DRIVER)]
        n_cars = len(codes)
        shares = np.bincount(mine, minlength=n_cars + 1)[1 : n_cars + 1] / float(len(mine))
        assert shares.sum() == pytest.approx(1.0)
        low, high = (float(q) for q in np.quantile(mine, [0.05, 0.95]))
        widths[label] = high - low
        assert np.isfinite(widths[label])
        assert widths[label] > 0
        print(
            f"\nALO lap {cutoff} {label}: mean {float(mine.mean()):.2f}, "
            f"90% interval {low:.0f} to {high:.0f} (width {widths[label]:.0f})"
        )
