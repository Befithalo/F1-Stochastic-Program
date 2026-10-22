"""A small hand-written race shared by the schema and storage tests."""

from datetime import datetime

import pandas as pd

from f1si.data.sources import NormalizedRace, RaceRef

RACE_ID = "2023-01"


def mini_ref() -> RaceRef:
    return RaceRef(
        race_id=RACE_ID,
        season=2023,
        round=1,
        slug="alpha-2023",
        event_name="Alpha Grand Prix",
        circuit="Alpha Ring",
        country="Alpha",
        race_start_utc=datetime(2023, 3, 5, 15, 0, 0),
        scheduled_laps=3,
    )


def mini_race_row(*, source: str = "synthetic", status: str = "complete") -> pd.DataFrame:
    """The `races` row (the loader writes it last as the completion marker)."""
    ref = mini_ref()
    return pd.DataFrame(
        [
            {
                "race_id": ref.race_id,
                "season": ref.season,
                "round": ref.round,
                "slug": ref.slug,
                "event_name": ref.event_name,
                "circuit": ref.circuit,
                "country": ref.country,
                "race_start_utc": ref.race_start_utc,
                "scheduled_laps": ref.scheduled_laps,
                "era": "ground_effect_2022_2025",
                "out_of_sample": False,
                "source": source,
                "source_version": "test-1",
                "loaded_at_utc": datetime(2026, 10, 22, 12, 0, 0),
                "load_status": status,
            }
        ]
    )


def mini_entries() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "race_id": [RACE_ID, RACE_ID],
            "driver_number": [10, 11],
            "driver_code": ["AAA", "BBB"],
            "driver_id": ["a_driver", "b_driver"],
            "full_name": ["A Driver", "B Driver"],
            "team_name": ["Team One", "Team Two"],
            "grid_position": [1, None],
            "pit_lane_start": [False, True],
            "start_compound": ["MEDIUM", "HARD"],
            "start_tyre_age": [0, 0],
        }
    )


def mini_laps() -> pd.DataFrame:
    """Driver 10 pits at the end of lap 2; driver 11 starts from the pit lane, lap 3 unfinished."""
    nan = float("nan")
    rows = [
        # driver, lap, start, end, time, in, out, pit_dur, stint, compound, tyre_life
        (10, 1, 0.0, 90.0, 90.0, False, False, nan, 1, "MEDIUM", 1),
        (10, 2, 90.0, 180.0, 90.0, True, False, nan, 1, "MEDIUM", 2),
        (10, 3, 180.0, 292.5, 112.5, False, True, 2.5, 2, "HARD", 1),
        (11, 1, 0.0, 95.0, 95.0, False, True, nan, 1, "HARD", 1),
        (11, 2, 95.0, 190.0, 95.0, False, False, nan, 1, "HARD", 2),
        (11, 3, 190.0, nan, nan, False, False, nan, 1, "HARD", 3),
    ]
    return pd.DataFrame(
        {
            "race_id": [RACE_ID] * len(rows),
            "driver_number": [r[0] for r in rows],
            "lap_number": [r[1] for r in rows],
            "lap_start_s": [r[2] for r in rows],
            "lap_end_s": [r[3] for r in rows],
            "lap_time_s": [r[4] for r in rows],
            "s1_s": [nan] * len(rows),
            "s2_s": [nan] * len(rows),
            "s3_s": [nan] * len(rows),
            "is_pit_in_lap": [r[5] for r in rows],
            "is_pit_out_lap": [r[6] for r in rows],
            "pit_duration_s": [r[7] for r in rows],
            "stint": [r[8] for r in rows],
            "compound": [r[9] for r in rows],
            "tyre_life": [r[10] for r in rows],
            "track_status": [None] * len(rows),
        }
    )


def mini_tables() -> dict[str, pd.DataFrame]:
    return {"entries": mini_entries(), "laps": mini_laps()}


def mini_race() -> NormalizedRace:
    return NormalizedRace(ref=mini_ref(), tables=mini_tables())
