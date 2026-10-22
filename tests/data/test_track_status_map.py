"""Offline tests for the race-control to track-status mapping (D-07)."""

from collections.abc import Sequence

import pandas as pd

from f1si.data.sources.track_status_map import derive_track_status

Event = tuple[float, str, str | None, str | None, int | None, str]
"""(t_s, category, flag, scope, sector, message)"""


def sc(t: float, message: str) -> Event:
    return (t, "SafetyCar", None, None, None, message)


def flag(
    t: float, name: str, scope: str | None = "Track", sector: int | None = None, text: str = ""
) -> Event:
    return (t, "Flag", name, scope, sector, text or f"{name} FLAG")


def frame(events: Sequence[Event]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "seq": i,
                "t_s": t,
                "category": cat,
                "flag": fl,
                "scope": scope,
                "sector": sector,
                "driver_number": pd.NA,
                "lap_number": pd.NA,
                "message": msg,
            }
            for i, (t, cat, fl, scope, sector, msg) in enumerate(events)
        ]
    )


def rows(events: Sequence[Event], laps: Sequence[float] = ()) -> list[tuple[float, str]]:
    out = derive_track_status(frame(events), leader_lap_end_s=laps)
    return list(zip(out["t_s"], out["status"], strict=True))


VSC_ON = sc(100, "VIRTUAL SAFETY CAR DEPLOYED")
VSC_ENDING = sc(160, "VIRTUAL SAFETY CAR ENDING")


def test_empty_input_gives_empty_frame_with_columns() -> None:
    out = derive_track_status(frame([]), leader_lap_end_s=[])
    assert list(out.columns) == ["seq", "t_s", "status", "message"]
    assert out.empty


def test_vsc_ending_reverts_after_15_seconds() -> None:
    assert rows([VSC_ON, VSC_ENDING]) == [(100, "6"), (160, "7"), (175, "1")]


def test_vsc_ending_reverts_at_track_green_when_sooner() -> None:
    events = [VSC_ON, VSC_ENDING, flag(165, "GREEN")]
    assert rows(events) == [(100, "6"), (160, "7"), (165, "1")]


def test_vsc_message_gets_timed_transition_text() -> None:
    out = derive_track_status(frame([VSC_ON, VSC_ENDING]), leader_lap_end_s=[])
    assert out["message"].tolist() == [
        "VIRTUAL SAFETY CAR DEPLOYED",
        "VIRTUAL SAFETY CAR ENDING",
        "VSC ending complete (assumed +15 s)",
    ]
    assert out["seq"].tolist() == [0, 1, 2]


def test_safety_car_ends_at_first_leader_lap_end_after_in_this_lap() -> None:
    events = [sc(200, "SAFETY CAR DEPLOYED"), sc(400, "SAFETY CAR IN THIS LAP")]
    assert rows(events, [100, 200, 380, 470, 560]) == [(200, "4"), (470, "1")]


def test_safety_car_in_message_is_documented() -> None:
    events = [sc(200, "SAFETY CAR DEPLOYED"), sc(400, "SAFETY CAR IN THIS LAP")]
    out = derive_track_status(frame(events), leader_lap_end_s=[470])
    assert out["message"].iloc[-1] == "Safety car in at leader lap end (assumed)"


def test_safety_car_in_this_lap_ended_early_by_track_green() -> None:
    events = [
        sc(200, "SAFETY CAR DEPLOYED"),
        sc(400, "SAFETY CAR IN THIS LAP"),
        flag(420, "GREEN"),
    ]
    assert rows(events, [470]) == [(200, "4"), (420, "1")]


def test_safety_car_without_in_this_lap_ignores_track_green() -> None:
    events = [sc(200, "SAFETY CAR DEPLOYED"), flag(300, "GREEN")]
    assert rows(events) == [(200, "4")]


def test_pit_exit_green_changes_nothing_under_safety_car() -> None:
    events = [
        sc(200, "SAFETY CAR DEPLOYED"),
        flag(210, "GREEN", text="GREEN LIGHT - PIT EXIT OPEN"),
    ]
    assert rows(events) == [(200, "4")]


def test_red_then_green() -> None:
    assert rows([flag(50, "RED")]) == [(50, "5")]
    assert rows([flag(50, "RED"), flag(300, "GREEN")]) == [(50, "5"), (300, "1")]


def test_safety_car_deployed_ends_red() -> None:
    events = [flag(50, "RED"), sc(90, "SAFETY CAR DEPLOYED")]
    assert rows(events) == [(50, "5"), (90, "4")]


def test_vsc_deployed_ends_red() -> None:
    assert rows([flag(50, "RED"), VSC_ON]) == [(50, "5"), (100, "6")]


def test_sector_yellows_accumulate_and_clear_per_sector() -> None:
    events = [
        flag(10, "YELLOW", "Sector", 2),
        flag(12, "YELLOW", "Sector", 3),
        flag(20, "CLEAR", "Sector", 2),
        flag(25, "CLEAR", "Sector", 3),
    ]
    assert rows(events) == [(10, "2"), (25, "1")]


def test_track_wide_yellow_cleared_by_green() -> None:
    events = [flag(10, "DOUBLE YELLOW", "Track"), flag(30, "GREEN")]
    assert rows(events) == [(10, "2"), (30, "1")]


def test_yellow_during_safety_car_keeps_4_then_becomes_2() -> None:
    events = [
        sc(200, "SAFETY CAR DEPLOYED"),
        flag(210, "YELLOW", "Sector", 1),
        sc(400, "SAFETY CAR IN THIS LAP"),
    ]
    assert rows(events, [470]) == [(200, "4"), (470, "2")]


def test_irrelevant_messages_add_no_rows() -> None:
    events: list[Event] = [
        flag(5, "CHEQUERED"),
        flag(6, "BLUE", "Driver"),
        (7, "Drs", None, None, None, "DRS ENABLED"),
        (8, "CarEvent", None, None, None, "CAR 1 (VER) STOPPED"),
        (9, "Other", None, None, None, "RISK OF RAIN"),
    ]
    assert rows(events) == []


def test_matching_is_case_and_whitespace_tolerant() -> None:
    events: list[Event] = [
        (100, "safetycar", None, None, None, "  virtual   safety car   deployed "),
        (160, "SAFETYCAR", None, None, None, "Virtual Safety Car Ending"),
    ]
    assert rows(events) == [(100, "6"), (160, "7"), (175, "1")]


def test_lowercase_flag_and_scope_columns() -> None:
    events: list[Event] = [(10, "flag", "yellow", "sector", 2, "yellow in sector 2")]
    assert rows(events) == [(10, "2")]


def test_events_are_processed_in_time_then_seq_order() -> None:
    events = [flag(300, "GREEN"), flag(50, "RED")]
    assert rows(events) == [(50, "5"), (300, "1")]


def test_safety_car_deployed_replaces_vsc() -> None:
    events = [VSC_ON, sc(120, "SAFETY CAR DEPLOYED"), sc(300, "SAFETY CAR IN THIS LAP")]
    assert rows(events, [350]) == [(100, "6"), (120, "4"), (350, "1")]


def test_safety_car_in_this_lap_without_later_lap_end_waits_for_green() -> None:
    events = [sc(200, "SAFETY CAR DEPLOYED"), sc(400, "SAFETY CAR IN THIS LAP")]
    assert rows(events, [100, 380]) == [(200, "4")]
    assert rows([*events, flag(500, "GREEN")], [100, 380]) == [(200, "4"), (500, "1")]


def test_output_codes_are_in_the_closed_set() -> None:
    events = [
        flag(10, "YELLOW", "Sector", 2),
        flag(20, "RED"),
        flag(30, "GREEN"),
        VSC_ON,
        VSC_ENDING,
        sc(300, "SAFETY CAR DEPLOYED"),
    ]
    out = derive_track_status(frame(events), leader_lap_end_s=[])
    assert set(out["status"]) <= {"1", "2", "4", "5", "6", "7"}
