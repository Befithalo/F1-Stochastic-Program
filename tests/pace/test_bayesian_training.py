"""Cutoff-safe assembly for the Bayesian pace training panel."""

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest

from f1si.data.asof import AsOf, AsOfAccessor, History, RaceSnapshot
from f1si.eras import GROUND_EFFECT
from f1si.pace.linear import _classify
from f1si.pace.training import build_bayesian_training_panel

CURRENT_RACE = "2023-02"
CURRENT_LAP = 5
AsOfData = tuple[RaceSnapshot, History]


@pytest.fixture(scope="module")
def asof_data(synthetic_db: Path) -> AsOfData:
    accessor = AsOfAccessor(synthetic_db)
    at = AsOf(CURRENT_RACE, CURRENT_LAP)
    return accessor.snapshot(at), accessor.history(at)


def test_panel_joins_earlier_history_and_current_completed_clean_laps(asof_data: AsOfData) -> None:
    snapshot, history = asof_data
    panel = build_bayesian_training_panel(snapshot, history)
    rows = panel.rows

    assert set(rows["race_id"]) == {"2023-01", CURRENT_RACE}
    assert "2023-01" in history.races
    assert (rows.loc[rows["race_id"] == CURRENT_RACE, "lap_number"] <= CURRENT_LAP).all()
    assert rows["driver_id"].notna().all()
    assert rows["team_name"].notna().all()
    assert rows["lap_time_s"].notna().all()
    assert rows["compound"].isin(("SOFT", "MEDIUM", "HARD")).all()
    assert rows["era"].eq(GROUND_EFFECT.name).all()
    assert set(panel.category_indexes["driver_id"]) == set(rows["driver_id"])
    assert list(panel.category_indexes["driver_id"]) == sorted(panel.category_indexes["driver_id"])
    assert set(panel.current_driver_id_by_number) == set(
        snapshot.entries["driver_number"].astype(int)
    )


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("is_pit_in_lap", True),
        ("is_pit_out_lap", True),
        ("track_status", "4"),
        ("compound", "INTERMEDIATE"),
        ("lap_time_s", pd.NA),
        ("stint", pd.NA),
    ],
)
def test_panel_uses_linear_clean_lap_eligibility(
    asof_data: AsOfData, column: str, value: object
) -> None:
    snapshot, history = asof_data
    clean = _classify(snapshot.laps)
    index = int(clean.index[clean["reason"].isna()][0])
    lap = snapshot.laps.iloc[index]
    lap_key = (int(lap["driver_number"]), int(lap["lap_number"]))
    changed = snapshot.laps.copy()
    changed.loc[changed.index[index], column] = cast(Any, value)
    mutated_snapshot = replace(snapshot, laps=changed)

    panel = build_bayesian_training_panel(mutated_snapshot, history)
    current_keys = set(
        zip(
            panel.rows.loc[panel.rows["race_id"] == CURRENT_RACE, "driver_number"].astype(int),
            panel.rows.loc[panel.rows["race_id"] == CURRENT_RACE, "lap_number"].astype(int),
            strict=True,
        )
    )
    assert lap_key not in current_keys


def test_panel_rejects_a_snapshot_row_that_ends_after_its_cutoff(asof_data: AsOfData) -> None:
    snapshot, history = asof_data
    assert snapshot.cutoff_s is not None
    index = snapshot.laps.index[0]
    changed = snapshot.laps.copy()
    changed.loc[index, "lap_end_s"] = snapshot.cutoff_s + 1.0
    key = (int(changed.loc[index, "driver_number"]), int(changed.loc[index, "lap_number"]))
    panel = build_bayesian_training_panel(replace(snapshot, laps=changed), history)
    current = panel.rows[panel.rows["race_id"] == CURRENT_RACE]
    assert key not in set(
        zip(
            current["driver_number"].astype(int),
            current["lap_number"].astype(int),
            strict=True,
        )
    )


def test_category_indexes_are_stable_and_keep_event_identity(asof_data: AsOfData) -> None:
    snapshot, history = asof_data
    panel = build_bayesian_training_panel(snapshot, history)
    assert panel.current_event_id == CURRENT_RACE
    assert panel.current_era == GROUND_EFFECT.name
    for race_id, group in panel.rows.groupby("race_id", sort=False):
        assert group["era"].nunique() == 1
        assert group["season"].nunique() == 1
        assert group["season"].iloc[0] == int(str(race_id).split("-")[0])
    assert panel.category_indexes["team_name"] == {
        name: index
        for index, name in enumerate(sorted(panel.rows["team_name"].astype(str).unique()))
    }
