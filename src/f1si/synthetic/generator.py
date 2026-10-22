"""Seeded synthetic races whose true parameters are known (D-09, FND-03).

Lap-time model. For driver `d` on lap `L` (1-based) with tyre compound `c` and `a` laps on the
tyres at the end of the lap:

    t(d, L) = base + offset_d + fuel * (L - 1) + wear[c] * a + eps(d, L)
              + start(d) * [L = 1] + pit_loss * [L is an out-lap after a stop]

then multiplied by `vsc_slowdown_factor` on virtual-safety-car laps. Here `offset_d = i * gap`
for the driver at index `i`, `fuel` is negative (the car gets lighter), `wear[c]` is the
degradation in seconds per lap on compound `c`, `eps ~ Normal(0, noise_sd)` is i.i.d. noise and
`start(d) = 3.0 + 0.2 * i` on lap 1 (a standing start costs time), or `3.0 + 5.0` for a pit-lane
starter. A lap's end is its start plus its time; the next lap starts where this one ended and
lap 1 starts at the race clock's zero (lights out).

Every parameter is exposed in `SyntheticTruth`, so later phases can test that their estimators
recover known wear rates, pace offsets and the fuel effect. Randomness enters only through the
keyword-only `rng` argument; `generate_dataset` gives each race its own spawned stream, so
changing one spec never changes another race.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from f1si.data import schema
from f1si.data.slugs import event_slug
from f1si.data.sources import NormalizedRace, RaceRef

_FIRST_LAP_BASE_COST_S = 3.0
_FIRST_LAP_GRID_COST_S = 0.2
_PIT_LANE_START_COST_S = 5.0


def _default_wear() -> dict[str, float]:
    return {"SOFT": 0.12, "MEDIUM": 0.07, "HARD": 0.04}


@dataclass(frozen=True)
class SyntheticRaceSpec:
    """Inputs for one synthetic race."""

    season: int
    round: int
    event_name: str
    n_drivers: int = 6
    n_laps: int = 12
    base_lap_time_s: float = 90.0
    driver_gap_s_per_lap: float = 0.35
    fuel_effect_s_per_lap: float = -0.03
    wear_rate_s_per_lap: Mapping[str, float] = field(default_factory=_default_wear)
    noise_sd_s: float = 0.15
    pit_loss_s: float = 20.0
    pit_stationary_s: float = 2.5
    start_compound: str = "MEDIUM"
    second_compound: str = "HARD"
    start_tyre_age: int = 0
    vsc_laps: tuple[int, ...] = ()
    vsc_slowdown_factor: float = 1.4
    retired_driver_index: int | None = None
    retire_after_lap: int | None = None
    pit_lane_start_index: int | None = None
    race_start_utc: datetime | None = None

    @property
    def start_utc(self) -> datetime:
        """Race start (tz-naive UTC): the given value, else 15:00 on 5 March plus round-1 weeks."""
        if self.race_start_utc is not None:
            return self.race_start_utc
        return datetime(self.season, 3, 5, 15, 0, 0) + timedelta(weeks=self.round - 1)


@dataclass(frozen=True)
class SyntheticTruth:
    """The true parameters a generated race was drawn from."""

    base_lap_time_s: float
    driver_pace_offset_s: Mapping[int, float]
    fuel_effect_s_per_lap: float
    wear_rate_s_per_lap: Mapping[str, float]
    noise_sd_s: float
    pit_loss_s: float
    pit_laps: Mapping[int, tuple[int, ...]]
    vsc_laps: tuple[int, ...]


@dataclass(frozen=True)
class SyntheticRace:
    """A generated race: its spec, its truth and the normalized tables."""

    spec: SyntheticRaceSpec
    truth: SyntheticTruth
    race: NormalizedRace


def _ref(spec: SyntheticRaceSpec) -> RaceRef:
    slug = event_slug(spec.event_name, spec.season)
    return RaceRef(
        race_id=f"{spec.season}-{spec.round:02d}",
        season=spec.season,
        round=spec.round,
        slug=slug,
        event_name=spec.event_name,
        circuit=f"synthetic-{slug}",
        country="Nowhere",
        race_start_utc=spec.start_utc,
        scheduled_laps=spec.n_laps,
    )


def generate_race(spec: SyntheticRaceSpec, *, rng: np.random.Generator) -> SyntheticRace:
    """Generate one synthetic race with the lap-time model in the module docstring."""
    ref = _ref(spec)
    wear = dict(spec.wear_rate_s_per_lap)
    # All lap noise first, driver-major, so the stream layout does not depend on later branching.
    noise = rng.normal(0.0, spec.noise_sd_s, size=(spec.n_drivers, spec.n_laps))

    entry_rows: list[dict[str, Any]] = []
    lap_rows: list[dict[str, Any]] = []
    offsets: dict[int, float] = {}
    pit_laps: dict[int, tuple[int, ...]] = {}

    for i in range(spec.n_drivers):
        number = 10 + i
        offset = i * spec.driver_gap_s_per_lap
        offsets[number] = offset
        from_pit_lane = i == spec.pit_lane_start_index
        last_lap = spec.n_laps
        if spec.retired_driver_index == i and spec.retire_after_lap is not None:
            last_lap = min(last_lap, spec.retire_after_lap)
        pit_lap = spec.n_laps // 2 + (i % 2)
        stops: tuple[int, ...] = (pit_lap,) if pit_lap < last_lap else ()
        pit_laps[number] = stops

        entry_rows.append(
            {
                "race_id": ref.race_id,
                "driver_number": number,
                "driver_code": chr(ord("A") + i) * 3,
                "driver_id": f"synthetic_{i + 1:02d}",
                "full_name": f"Synthetic Driver {i + 1}",
                "team_name": f"Synthetic Team {i // 2 + 1}",
                "grid_position": pd.NA if from_pit_lane else i + 1,
                "pit_lane_start": from_pit_lane,
                "start_compound": spec.start_compound,
                "start_tyre_age": spec.start_tyre_age,
            }
        )

        clock = 0.0
        for lap in range(1, last_lap + 1):
            after_stop = bool(stops) and lap > stops[0]
            compound = spec.second_compound if after_stop else spec.start_compound
            tyre_life = lap - stops[0] if after_stop else spec.start_tyre_age + lap
            is_stop_out_lap = after_stop and lap == stops[0] + 1
            out_lap = is_stop_out_lap or (lap == 1 and from_pit_lane)

            time_s = (
                spec.base_lap_time_s
                + offset
                + spec.fuel_effect_s_per_lap * (lap - 1)
                + wear[compound] * tyre_life
                + float(noise[i, lap - 1])
            )
            if lap == 1:
                time_s += _FIRST_LAP_BASE_COST_S + (
                    _PIT_LANE_START_COST_S if from_pit_lane else _FIRST_LAP_GRID_COST_S * i
                )
            pit_duration: Any = pd.NA
            if is_stop_out_lap:
                time_s += spec.pit_loss_s
                pit_duration = spec.pit_stationary_s
            if lap in spec.vsc_laps:
                time_s *= spec.vsc_slowdown_factor

            lap_rows.append(
                {
                    "race_id": ref.race_id,
                    "driver_number": number,
                    "lap_number": lap,
                    "lap_start_s": clock,
                    "lap_end_s": clock + time_s,
                    "lap_time_s": time_s,
                    "s1_s": 0.3 * time_s,
                    "s2_s": 0.4 * time_s,
                    "s3_s": 0.3 * time_s,
                    "is_pit_in_lap": lap in stops,
                    "is_pit_out_lap": out_lap,
                    "pit_duration_s": pit_duration,
                    "stint": 2 if after_stop else 1,
                    "compound": compound,
                    "tyre_life": tyre_life,
                    "track_status": pd.NA,
                }
            )
            clock += time_s

    tables = {
        "entries": schema.normalize("entries", pd.DataFrame(entry_rows)),
        "laps": schema.normalize("laps", pd.DataFrame(lap_rows)),
    }
    truth = SyntheticTruth(
        base_lap_time_s=spec.base_lap_time_s,
        driver_pace_offset_s=offsets,
        fuel_effect_s_per_lap=spec.fuel_effect_s_per_lap,
        wear_rate_s_per_lap=wear,
        noise_sd_s=spec.noise_sd_s,
        pit_loss_s=spec.pit_loss_s,
        pit_laps=pit_laps,
        vsc_laps=spec.vsc_laps,
    )
    return SyntheticRace(spec=spec, truth=truth, race=NormalizedRace(ref=ref, tables=tables))


def generate_dataset(
    specs: Sequence[SyntheticRaceSpec], *, rng: np.random.Generator
) -> list[SyntheticRace]:
    """Generate one race per spec; each race draws from its own spawned stream."""
    streams = rng.spawn(len(specs))
    return [generate_race(spec, rng=stream) for spec, stream in zip(specs, streams, strict=True)]


def default_specs() -> tuple[SyntheticRaceSpec, ...]:
    """The four races of the walking skeleton: two in 2023, one in 2024, one in 2026."""
    return (
        SyntheticRaceSpec(2023, 1, "Alpha Grand Prix", vsc_laps=(8,)),
        SyntheticRaceSpec(
            2023,
            2,
            "Bravo Grand Prix",
            retired_driver_index=5,
            retire_after_lap=4,
            pit_lane_start_index=4,
        ),
        SyntheticRaceSpec(2024, 1, "Charlie Grand Prix"),
        SyntheticRaceSpec(2026, 1, "Delta Grand Prix", vsc_laps=(5,)),
    )
