"""Cutoff-safe data and FastF1 colors for the replay context charts."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from types import SimpleNamespace
from typing import Any, cast

from f1si.data.asof import RaceSnapshot
from f1si.ui_theme import TIMING_COLORS, TIRE_LETTERS


def _as_int(value: object) -> int:
    return int(cast(Any, value))


def _as_float(value: object) -> float:
    return float(cast(Any, value))


def _driver_codes_by_number(snapshot: RaceSnapshot) -> dict[int, str]:
    return {
        _as_int(row.driver_number): str(row.driver_code).upper()
        for row in snapshot.entries.itertuples(index=False)
    }


def _driver_order(snapshot: RaceSnapshot) -> tuple[str, ...]:
    entries = snapshot.entries.sort_values(["grid_position", "driver_code"], na_position="last")
    return tuple(str(code).upper() for code in entries["driver_code"])


def prepare_race_trace_data(snapshot: RaceSnapshot) -> tuple[dict[str, object], ...]:
    """Calculate same-lap completion gaps from only the supplied as-of snapshot."""
    laps = snapshot.laps
    if laps.empty:
        return ()
    visible = laps.dropna(subset=["lap_number", "lap_end_s"]).copy()
    if visible.empty:
        return ()
    visible["lap_number"] = visible["lap_number"].astype(int)
    visible["lap_end_s"] = visible["lap_end_s"].astype(float)
    leader_times = visible.groupby("lap_number")["lap_end_s"].min().to_dict()
    entries = snapshot.entries[
        ["driver_number", "driver_code", "team_name", "grid_position"]
    ].copy()
    entries["driver_number"] = entries["driver_number"].astype(int)
    visible = visible.merge(entries, on="driver_number", how="inner", validate="many_to_one")
    teammate_order: dict[str, dict[str, int]] = {}
    for team, group in entries.groupby("team_name", sort=False):
        codes = group.sort_values(["grid_position", "driver_code"], na_position="last")[
            "driver_code"
        ].astype(str)
        teammate_order[str(team)] = {code.upper(): index for index, code in enumerate(codes)}

    latest = visible.sort_values("lap_number").groupby("driver_number", as_index=False).tail(1)
    latest = latest.copy()
    latest["gap_to_leader_s"] = latest.apply(
        lambda row: max(
            0.0,
            _as_float(row["lap_end_s"]) - _as_float(leader_times[_as_int(row["lap_number"])]),
        ),
        axis=1,
    )
    latest = latest.sort_values(["gap_to_leader_s", "driver_number"], kind="stable")
    gap_low = max(0.0, _as_float(latest["gap_to_leader_s"].min()))
    gap_high = _as_float(latest["gap_to_leader_s"].max())
    label_step = max(1.6, (gap_high - gap_low) / max(1, len(latest) - 1))
    label_positions = {
        _as_int(number): gap_low + index * label_step
        for index, number in enumerate(latest["driver_number"].tolist())
    }
    latest_laps = latest.set_index("driver_number")["lap_number"].to_dict()
    label_lap = _as_int(visible["lap_number"].max()) + 1.5
    valid_laps = visible.loc[
        ~visible["is_pit_in_lap"].astype(bool) & ~visible["is_pit_out_lap"].astype(bool)
    ].dropna(subset=["lap_time_s"])
    personal_bests = valid_laps.groupby("driver_number")["lap_time_s"].min().to_dict()
    overall_best = _as_float(valid_laps["lap_time_s"].min()) if not valid_laps.empty else None
    timing_status_by_number: dict[int, tuple[str, str]] = {}
    for lap in latest.itertuples(index=False):
        number = _as_int(lap.driver_number)
        lap_time = getattr(lap, "lap_time_s", None)
        is_pit = bool(lap.is_pit_in_lap) or bool(lap.is_pit_out_lap)
        status = "last lap"
        label = ""
        if is_pit:
            status, label = "pit lane", "Pit"
        elif (
            lap_time is not None
            and overall_best is not None
            and abs(_as_float(lap_time) - overall_best) < 0.001
        ):
            status, label = "overall best", "Best"
        elif lap_time is not None and number in personal_bests:
            personal_best = _as_float(personal_bests[number])
            if abs(_as_float(lap_time) - personal_best) < 0.001:
                status, label = "personal best", "PB"
            elif _as_float(lap_time) > personal_best:
                status, label = "slower", "Slow"
        timing_status_by_number[number] = (status, label)

    rows: list[dict[str, object]] = []
    for row in visible.itertuples(index=False):
        code = str(row.driver_code).upper()
        team = str(row.team_name)
        lap_number = _as_int(row.lap_number)
        status, timing_label = timing_status_by_number[_as_int(row.driver_number)]
        number = _as_int(row.driver_number)
        rows.append(
            {
                "driver_code": code,
                "team_name": team,
                "lap": lap_number,
                "gap_to_leader_s": max(
                    0.0, _as_float(row.lap_end_s) - _as_float(leader_times[lap_number])
                ),
                "teammate_dash": teammate_order.get(team, {}).get(code, 0) > 0,
                "timing_status": status,
                "timing_label": timing_label,
                "timing_color": TIMING_COLORS[status],
                "driver_label": f"{code} {timing_label}" if timing_label else code,
                "label_gap_s": label_positions.get(number, 0.0),
                "label_lap": label_lap,
                "is_latest": lap_number == _as_int(latest_laps[number]),
                "lap_time_s": getattr(row, "lap_time_s", None),
            }
        )
    return tuple(rows)


def prepare_stint_bar_data(snapshot: RaceSnapshot) -> tuple[dict[str, object], ...]:
    """Convert as-of visible stints to compound-labeled bar segments."""
    if snapshot.stints.empty:
        return ()
    codes = _driver_codes_by_number(snapshot)
    rows: list[dict[str, object]] = []
    for stint in snapshot.stints.itertuples(index=False):
        compound = str(stint.compound).upper()
        if compound not in TIRE_LETTERS:
            continue
        first_lap = _as_int(stint.first_lap)
        last_lap = _as_int(stint.last_visible_lap)
        if first_lap < 1 or last_lap < first_lap:
            continue
        rows.append(
            {
                "driver_code": codes[_as_int(stint.driver_number)],
                "compound": compound,
                "compound_letter": TIRE_LETTERS[compound],
                "first_lap": first_lap,
                "last_visible_lap": last_lap,
                "start_lap": first_lap - 0.5,
                "end_lap": last_lap + 0.5,
                "mid_lap": (first_lap + last_lap) / 2,
            }
        )
    return tuple(rows)


@lru_cache(maxsize=8)
def _offline_fastf1_color_session(year: int) -> Any:
    """Seed FastF1's color lookup from its bundled season palette, without fetching timing data."""
    import fastf1.plotting._backend as fastf1_backend  # type: ignore[import-untyped]
    import fastf1.plotting._interface as fastf1_interface  # type: ignore[import-untyped]
    from fastf1.plotting._base import DriverTeamMapping, Team  # type: ignore[import-untyped]

    season = fastf1_backend.Constants[str(year)]
    teams = [
        Team(
            name=team_constants.short_name,
            normalized_name=normalized_name,
            short_name=team_constants.short_name,
            colors=team_constants.colors.model_copy(),
        )
        for normalized_name, team_constants in season.teams.items()
    ]
    api_path = f"/f1si/offline-team-colors/{year}"
    fastf1_interface._DRIVER_TEAM_MAPPINGS[api_path] = DriverTeamMapping(
        year=str(year), teams=teams
    )
    return SimpleNamespace(api_path=api_path, event={"EventDate": datetime(year, 1, 1)})


def fastf1_team_color_map(year: int, team_names: tuple[str, ...]) -> dict[str, str]:
    """Return FastF1 official colors from its local season palette without archive downloads."""
    import fastf1.plotting

    session = _offline_fastf1_color_session(year)
    return {
        team_name: cast(
            str,
            fastf1.plotting.get_team_color(
                team_name,
                session,
                colormap="official",
            ),
        )
        for team_name in team_names
    }


def snapshot_driver_order(snapshot: RaceSnapshot) -> tuple[str, ...]:
    """Return the stable grid order for charts with one lane per driver."""
    return _driver_order(snapshot)
