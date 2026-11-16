"""Stint bar data for the replay page, including a stint whose out-lap has not finished."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pandas as pd

from f1si.data.asof import RACE_END, AsOf
from f1si.plots.replay_charts import prepare_stint_bar_data

STINT_DTYPES = {
    "driver_number": "Int64",
    "stint": "Int64",
    "compound": "object",
    "first_lap": "Int64",
    "last_visible_lap": "Int64",
    "laps_so_far": "Int64",
    "tyre_life_now": "Int64",
}


def _snapshot(stints: list[dict[str, object]], *, lap: Any) -> Any:
    frame = pd.DataFrame(stints).astype(STINT_DTYPES)
    entries = pd.DataFrame({"driver_number": [1, 14], "driver_code": ["VER", "ALO"]})
    return SimpleNamespace(stints=frame, entries=entries, at=AsOf("2023-01", lap))


def _alo_after_lap_15(*, lap: Any = 15) -> Any:
    """ALO's in-lap 14 is complete; his Hard out-lap 15 has started but not finished.

    Lap k spans [k - 0.5, k + 0.5], so "after lap 15" is x = 15.5.
    """
    return _snapshot(
        [
            {
                "driver_number": 14,
                "stint": 1,
                "compound": "SOFT",
                "first_lap": 1,
                "last_visible_lap": 14,
                "laps_so_far": 14,
                "tyre_life_now": 17,
            },
            {
                "driver_number": 14,
                "stint": 2,
                "compound": "HARD",
                "first_lap": 15,
                "last_visible_lap": pd.NA,
                "laps_so_far": 0,
                "tyre_life_now": 0,
            },
        ],
        lap=lap,
    )


def test_started_stint_draws_from_the_stop_to_the_cutoff_on_the_new_compound() -> None:
    soft, hard = prepare_stint_bar_data(_alo_after_lap_15())

    assert soft["compound"] == "SOFT"
    assert (soft["start_lap"], soft["end_lap"]) == (0.5, 14.5)
    assert soft["laps_completed"] == 14
    assert soft["in_progress"] is False

    assert hard["driver_code"] == "ALO"
    assert hard["compound"] == "HARD"
    assert hard["compound_letter"] == "H"
    assert hard["start_lap"] == soft["end_lap"] == 14.5
    assert hard["end_lap"] == 15.5
    assert hard["mid_lap"] == 15.0
    assert hard["last_visible_lap"] is None
    assert hard["laps_completed"] == 0
    assert hard["in_progress"] is True


def test_started_stint_never_extends_past_the_cutoff() -> None:
    rows = prepare_stint_bar_data(_alo_after_lap_15())
    assert max(cast(float, row["end_lap"]) for row in rows) == 15.5


def test_started_stint_is_skipped_without_a_lap_cutoff() -> None:
    rows = prepare_stint_bar_data(_alo_after_lap_15(lap=RACE_END))
    assert [row["compound"] for row in rows] == ["SOFT"]
