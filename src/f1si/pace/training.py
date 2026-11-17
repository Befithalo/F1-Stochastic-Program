"""Cutoff-safe, clean-lap training rows for the hierarchical Bayesian pace fit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
import pandas as pd

from f1si.data.asof import History, RaceSnapshot
from f1si.eras import era_for_season
from f1si.pace.linear import _classify

_ENTRY_COLUMNS = ("race_id", "driver_number", "driver_id", "team_name")
_PANEL_COLUMNS = (
    "race_id",
    "season",
    "era",
    "driver_number",
    "driver_id",
    "team_name",
    "lap_number",
    "compound",
    "tire_age",
    "lap_time_s",
)
_CATEGORY_COLUMNS = ("driver_id", "team_name", "race_id", "era", "compound")


class PaceTrainingError(ValueError):
    """Raised when as-of laps cannot be joined into a trustworthy pace panel."""


@dataclass(frozen=True, eq=False)
class BayesianTrainingPanel:
    """Clean lap rows, stable categorical indexes, and the current event's driver lookup."""

    rows: pd.DataFrame
    category_indexes: Mapping[str, Mapping[str, int]]
    current_driver_id_by_number: Mapping[int, str]
    current_team_by_number: Mapping[int, str]
    current_event_id: str
    current_era: str


def _season_from_race_id(race_id: str) -> int:
    try:
        return int(race_id.split("-", maxsplit=1)[0])
    except (ValueError, IndexError) as err:
        raise PaceTrainingError(f"race id {race_id!r} does not begin with a calendar year") from err


def _joined_laps(laps: pd.DataFrame, entries: pd.DataFrame, *, source: str) -> pd.DataFrame:
    if laps.empty:
        return pd.DataFrame(columns=[*laps.columns, "driver_id", "team_name"])
    missing = set(_ENTRY_COLUMNS) - set(entries.columns)
    if missing:
        raise PaceTrainingError(f"{source} entries lack required columns: {sorted(missing)}")
    joined = laps.merge(
        entries.loc[:, list(_ENTRY_COLUMNS)],
        on=["race_id", "driver_number"],
        how="left",
        validate="many_to_one",
    )
    if joined["driver_id"].isna().any():
        raise PaceTrainingError(f"{source} laps contain a driver with no matching entry")
    joined["driver_id"] = joined["driver_id"].astype(str).str.strip()
    team = joined["team_name"].astype("string").str.strip()
    joined["team_name"] = team.mask(team.isna() | team.eq(""), "UNKNOWN_TEAM").astype(str)
    return joined


def _clean_panel_rows(
    laps: pd.DataFrame,
    entries: pd.DataFrame,
    *,
    source: str,
    cutoff_s: float | None = None,
) -> pd.DataFrame:
    joined = _joined_laps(laps, entries, source=source)
    if joined.empty:
        return pd.DataFrame(columns=_PANEL_COLUMNS)
    clean = _classify(joined)["reason"].isna().to_numpy(dtype=bool)
    if source == "current":
        ends = pd.to_numeric(joined["lap_end_s"], errors="coerce").to_numpy(dtype=np.float64)
        clean &= np.isfinite(ends)
        if cutoff_s is not None:
            clean &= ends <= cutoff_s
    rows = joined.loc[clean].copy()
    if rows.empty:
        return pd.DataFrame(columns=_PANEL_COLUMNS)
    seasons = rows["race_id"].astype(str).map(_season_from_race_id)
    rows["season"] = seasons.astype(np.int64)
    rows["era"] = rows["season"].map(lambda season: era_for_season(int(season)).name)
    rows["compound"] = rows["compound"].astype(str).str.upper()
    rows["lap_number"] = rows["lap_number"].astype(np.int64)
    rows["tire_age"] = pd.to_numeric(rows["tyre_life"], errors="raise").astype(np.int64)
    rows["lap_time_s"] = pd.to_numeric(rows["lap_time_s"], errors="raise").astype(np.float64)
    rows["driver_number"] = rows["driver_number"].astype(np.int64)
    return rows.loc[:, list(_PANEL_COLUMNS)]


def _category_indexes(rows: pd.DataFrame) -> Mapping[str, Mapping[str, int]]:
    indexes: dict[str, Mapping[str, int]] = {}
    for column in _CATEGORY_COLUMNS:
        values = sorted(set(rows[column].astype(str)))
        indexes[column] = MappingProxyType({value: index for index, value in enumerate(values)})
    return MappingProxyType(indexes)


def build_bayesian_training_panel(
    snapshot: RaceSnapshot,
    history: History | None = None,
) -> BayesianTrainingPanel:
    """Join earlier full races and the completed clean prefix visible in ``snapshot``.

    The function consumes only the plain ``History`` and ``RaceSnapshot`` passed by the caller.
    It never reads ``History.results``. The current event's entries supply stable driver/team
    lookups for the PaceModel's driver-number interface.
    """
    current_race = snapshot.race.race_id
    current_era = era_for_season(snapshot.race.season)
    if current_era.out_of_sample:
        raise PaceTrainingError(f"out-of-sample era {current_era.name!r} cannot train pace")
    if history is not None and history.as_of.race_id != current_race:
        raise PaceTrainingError("History and RaceSnapshot must refer to the same current race")

    frames: list[pd.DataFrame] = []
    if history is not None:
        current_order = (snapshot.race.season, snapshot.race.round)
        for race_id in history.races:
            season = _season_from_race_id(str(race_id))
            if era_for_season(season).out_of_sample:
                raise PaceTrainingError(f"out-of-sample race {race_id!r} cannot train pace")
            try:
                round_no = int(str(race_id).split("-")[1])
            except (ValueError, IndexError) as err:
                raise PaceTrainingError(f"race id {race_id!r} has no calendar round") from err
            if (season, round_no) >= current_order:
                raise PaceTrainingError(
                    f"history race {race_id!r} is not earlier than {current_race!r}"
                )
        history_rows = _clean_panel_rows(
            history.laps,
            history.entries,
            source="history",
        )
        if not history_rows.empty:
            history_ids = set(str(value) for value in history.races)
            unexpected = set(history_rows["race_id"].astype(str)) - history_ids
            if unexpected:
                raise PaceTrainingError(
                    f"history laps include unlisted race ids: {sorted(unexpected)}"
                )
            frames.append(history_rows)

    current_rows = _clean_panel_rows(
        snapshot.laps,
        snapshot.entries,
        source="current",
        cutoff_s=snapshot.cutoff_s,
    )
    if not current_rows.empty:
        if set(current_rows["race_id"].astype(str)) != {current_race}:
            raise PaceTrainingError("current snapshot laps contain another race id")
        frames.append(current_rows)
    if frames:
        rows = pd.concat(frames, ignore_index=True)
        rows = rows.sort_values(
            ["season", "race_id", "driver_id", "lap_number", "driver_number"],
            kind="stable",
        ).reset_index(drop=True)
    else:
        rows = pd.DataFrame(columns=_PANEL_COLUMNS)

    entries = snapshot.entries.loc[:, list(_ENTRY_COLUMNS)]
    if entries["driver_id"].isna().any():
        raise PaceTrainingError("current entries contain a missing stable driver id")
    driver_id = dict(
        zip(
            entries["driver_number"].astype(int),
            entries["driver_id"].astype(str).str.strip(),
            strict=True,
        )
    )
    raw_team = entries["team_name"].astype("string").str.strip()
    team_values = raw_team.mask(raw_team.isna() | raw_team.eq(""), "UNKNOWN_TEAM").astype(str)
    team_by_number = dict(zip(entries["driver_number"].astype(int), team_values, strict=True))
    return BayesianTrainingPanel(
        rows=rows,
        category_indexes=_category_indexes(rows),
        current_driver_id_by_number=MappingProxyType(dict(sorted(driver_id.items()))),
        current_team_by_number=MappingProxyType(dict(sorted(team_by_number.items()))),
        current_event_id=current_race,
        current_era=current_era.name,
    )
