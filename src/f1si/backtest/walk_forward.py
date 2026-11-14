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


def _predict_from_accessor(
    accessor: asof.AsOfAccessor,
    race_id: str,
    driver: str,
    lap: int,
    *,
    n_simulations: int,
    risk: float,
    seed: int,
) -> PredictionRow:
    """Build one row from the shared replay cutoff builder; never reads final outcomes."""
    if race_id not in REGISTERED_RACE_IDS:
        raise ValueError(f"Race {race_id} is outside the registered 2023-2025 backtest sample.")
    end = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
    if end.laps.empty:
        raise ValueError(f"No lap data available for {race_id}.")
    laps_total = int(end.laps["lap_number"].max())
    code = driver.upper()
    known = set(str(value) for value in end.entries["driver_code"])
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
            asof.AsOfAccessor(db_path),
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
    if not isinstance(at.lap, int):
        raise ValueError("The walk-forward consumer requires an integer cutoff lap.")
    return _predict_from_accessor(
        asof.AsOfAccessor(db_path),
        at.race_id,
        "ALO",
        at.lap,
        n_simulations=1,
        risk=0.5,
        seed=0,
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
    accessor = asof.AsOfAccessor(db_path)
    rows: list[PredictionRow] = []
    for race_id in REGISTERED_RACE_IDS:
        end = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
        if end.laps.empty:
            raise ValueError(f"No lap data available for registered race {race_id}.")
        laps_total = int(end.laps["lap_number"].max())
        drivers = sorted(str(value) for value in end.entries["driver_code"])
        for lap in range(laps_total):
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
                    )
                )
    return WalkForwardTrace(tuple(rows))
