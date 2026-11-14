"""Fixed-sample, cutoff-local prediction generation. Final results are deliberately absent."""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from f1si.data import asof
from f1si.data.errors import OutOfSampleLockedError
from f1si.strategy.longstaff import StrategyAnalysis

REGISTERED_RACE_IDS: Final = (
    "2023-01",
    "2023-02",
    "2023-03",
    "2023-04",
    "2024-01",
    "2024-02",
    "2024-03",
    "2025-01",
    "2025-02",
    "2025-03",
)


def _new_accessor(db_path: Path) -> asof.AsOfAccessor:
    """Ask the CLI composition layer to create the sole cache-reading capability."""
    from f1si.cli import _make_asof_accessor

    return _make_asof_accessor(db_path)


@dataclass(frozen=True)
class PredictionRow:
    """One immutable prediction and its cutoff-local strategy distributions."""

    race_id: str
    driver: str
    cutoff_lap: int
    analysis: StrategyAnalysis | None
    unavailable_reason: str | None = None
    is_fallback: bool = False


@dataclass(frozen=True)
class WalkForwardTrace:
    """The immutable prediction set, fully generated before any scoring layer exists."""

    predictions: tuple[PredictionRow, ...]


def preflight_races(completion: dict[str, bool]) -> tuple[str, ...]:
    """Return every missing or incomplete registered race in locked calendar order."""
    return tuple(race_id for race_id in REGISTERED_RACE_IDS if not completion.get(race_id, False))


def _preflight_database(db_path: Path) -> None:
    catalog = asof.catalog(db_path)
    completion = {
        str(row.race_id): row.load_status == "complete" and not bool(row.out_of_sample)
        for row in catalog.itertuples(index=False)
    }
    missing = preflight_races(completion)
    if missing:
        raise ValueError(
            "Backtest cache is missing complete registered races: " + ", ".join(missing)
        )


def _seed(race_id: str, driver: str, lap: int, seed: int) -> int:
    return (seed + zlib.crc32(f"{race_id}:{driver}:{lap}".encode())) & 0x7FFFFFFF


def _race_laps_total(accessor: asof.AsOfAccessor, race_id: str, first_snapshot: object) -> int:
    """Return the race cutoff horizon, using completed lap rows when schedule metadata is absent.

    Some OpenF1 cache entries do not include the scheduled distance. In that case the completed
    lap table supplies only the finite evaluation horizon; every prediction still uses its own
    cutoff snapshot and strictly earlier history.
    """
    scheduled_laps = getattr(first_snapshot.race, "scheduled_laps", None)
    if scheduled_laps is not None and int(scheduled_laps) > 0:
        return int(scheduled_laps)

    end = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
    laps = getattr(end, "laps", None)
    if laps is None or laps.empty or "lap_number" not in laps:
        raise ValueError(f"No race distance or completed laps available for {race_id}.")
    observed_laps = laps["lap_number"].dropna()
    if observed_laps.empty:
        raise ValueError(f"No race distance or completed laps available for {race_id}.")
    laps_total = int(observed_laps.max())
    if laps_total < 1:
        raise ValueError(f"No race distance or completed laps available for {race_id}.")
    return laps_total


def _predict_from_accessor(
    accessor: asof.AsOfAccessor,
    race_id: str,
    driver: str,
    lap: int,
    *,
    n_simulations: int,
    risk: float,
    seed: int,
    laps_total: int | None = None,
) -> PredictionRow:
    """Build one row from the shared replay cutoff builder; never reads final outcomes."""
    if race_id not in REGISTERED_RACE_IDS:
        raise ValueError(f"Race {race_id} is outside the registered 2023-2025 backtest sample.")
    snapshot = accessor.snapshot(asof.AsOf(race_id, lap))
    if laps_total is None:
        laps_total = _race_laps_total(accessor, race_id, snapshot)
    code = driver.upper()
    known = set(str(value) for value in snapshot.entries["driver_code"])
    if code not in known:
        raise ValueError(f"Unknown driver {code!r} in {race_id}.")
    if lap < 0 or lap >= laps_total:
        raise ValueError(f"Cutoff lap must be in 0..{laps_total - 1}, got {lap}.")
    from f1si.cli import _replay_at_cutoff

    result = _replay_at_cutoff(
        accessor,
        race_id,
        laps_total,
        code,
        lap,
        n_simulations=n_simulations,
        risk=risk,
        seed=_seed(race_id, code, lap, seed),
    )
    return PredictionRow(
        race_id, code, lap, result.analysis, result.unavailable_reason, result.is_fallback
    )


def predict_at_cutoff(
    db_path: Path,
    race_id: str,
    driver: str,
    lap: int,
    *,
    n_simulations: int = 1_000,
    risk: float = 0.5,
    seed: int = 0,
) -> PredictionRow:
    """Run the tracer request after verifying the complete frozen sample is cached."""
    if race_id not in REGISTERED_RACE_IDS:
        raise ValueError(f"Race {race_id} is outside the registered 2023-2025 backtest sample.")
    _preflight_database(db_path)
    try:
        return _predict_from_accessor(
            _new_accessor(db_path),
            race_id,
            driver,
            lap,
            n_simulations=n_simulations,
            risk=risk,
            seed=seed,
        )
    except OutOfSampleLockedError as err:
        raise ValueError(f"{err} 2026 races are out-of-sample and cannot be backtested.") from err


def cutoff_consumer(db_path: Path, at: asof.AsOf) -> PredictionRow:
    """Single-cutoff consumer registered with the future-row scramble guard."""
    if at.race_id not in REGISTERED_RACE_IDS:
        raise ValueError(f"Race {at.race_id} is outside the registered backtest sample.")
    # The scramble harness can supply RACE_END as a boundary marker. Resolve it to the last
    # scheduled strategy cutoff so the marker never grants access to future observations.
    accessor = _new_accessor(db_path)
    first = accessor.snapshot(asof.AsOf(at.race_id, 0))
    laps_total = _race_laps_total(accessor, at.race_id, first)
    lap = at.lap if isinstance(at.lap, int) else laps_total - 1
    lap = min(lap, laps_total - 1)
    snapshot = first if lap == 0 else accessor.snapshot(asof.AsOf(at.race_id, lap))
    drivers = sorted(str(value) for value in snapshot.entries["driver_code"])
    if not drivers:
        raise ValueError(f"No drivers available in {at.race_id} at lap {at.lap}.")
    return _predict_from_accessor(
        accessor,
        at.race_id,
        drivers[0],
        lap,
        n_simulations=1,
        risk=0.5,
        seed=0,
        laps_total=laps_total,
    )


def run_walk_forward(
    db_path: Path,
    *,
    n_simulations: int = 1_000,
    risk: float = 0.5,
    seed: int = 0,
) -> WalkForwardTrace:
    """Freeze all drivers' predictions at every eligible cutoff of the ten registered races."""
    _preflight_database(db_path)
    accessor = _new_accessor(db_path)
    rows: list[PredictionRow] = []
    for race_id in REGISTERED_RACE_IDS:
        first = accessor.snapshot(asof.AsOf(race_id, 0))
        laps_total = _race_laps_total(accessor, race_id, first)
        for lap in range(laps_total):
            snapshot = first if lap == 0 else accessor.snapshot(asof.AsOf(race_id, lap))
            drivers = sorted(str(value) for value in snapshot.entries["driver_code"])
            for driver in drivers:
                rows.append(
                    _predict_from_accessor(
                        accessor,
                        race_id,
                        driver,
                        lap,
                        n_simulations=n_simulations,
                        risk=risk,
                        seed=seed,
                        laps_total=laps_total,
                    )
                )
    return WalkForwardTrace(tuple(rows))
