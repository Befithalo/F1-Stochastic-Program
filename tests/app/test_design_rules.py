"""The 2026-11-16 design decisions (DESIGN_SYSTEM_V2.md section 10) as executable checks."""

from __future__ import annotations

from importlib import import_module
from typing import Any

import pytest

from f1si.ui_theme import (
    ASPHALT,
    FOG,
    TIRE_COLORS,
    band_background,
    contrast_ratio,
    fan_band_colors,
    readable_on,
    relative_luminance,
    team_fill,
)

app: Any = import_module("f1si.app")

TEAM_NAMES = {
    2023: (
        "Alfa Romeo",
        "AlphaTauri",
        "Alpine",
        "Aston Martin",
        "Ferrari",
        "Haas F1 Team",
        "McLaren",
        "Mercedes",
        "Red Bull",
        "Williams",
    ),
    2024: (
        "Red Bull Racing",
        "Williams",
        "RB F1 Team",
        "McLaren",
        "Alpine F1 Team",
        "Aston Martin",
        "Ferrari",
        "Haas F1 Team",
        "Sauber",
        "Mercedes",
    ),
}


def _team_colors() -> set[str]:
    palette = import_module("f1si.plots.replay_charts").fastf1_team_color_map
    colors: set[str] = set()
    for season, names in TEAM_NAMES.items():
        colors.update(color.upper() for color in palette(season, names).values())
    colors.update(c.upper() for c in palette(2025, TEAM_NAMES[2024]).values())
    return colors


def _option(action: str, mean: float, **overrides: Any) -> Any:
    values: dict[str, Any] = {
        "action": action,
        "mean": mean,
        "bad_day": 17.0,
        "podium": 0.19,
        "points": 0.76,
        "interval": "P2-P17",
        "quantiles": tuple([4] * 50 + [9] * 50),
        "stop_laps": (),
        "compounds": (),
    }
    values.update(overrides)
    return app.Option(**values)


def _context(*, current: str = "HARD", stops_done: int = 0) -> Any:
    return app.PageContext(
        code="ALO",
        surname="Alonso",
        team="#358C75",
        current=current,
        stops_done=stops_done,
        pit_loss_s=24.0,
        n_cars=20,
        never_stop_allowed=True,
        simulations=10_000,
    )


def test_identical_wait_and_stay_out_merge_into_one_stay_out_row() -> None:
    wait = _option("wait and decide next lap", 7.5447)
    stay = _option("stay out", 7.5447)
    pit = _option("pit now (HARD)", 8.6053, bad_day=17.6, podium=0.12, points=0.69)
    merged = app._merge_options([wait, stay, pit])
    assert [item.action for item in merged] == ["stay out", "pit now (HARD)"]
    assert merged[0].merged == ("wait and decide next lap",)
    assert app._option_title(merged[0].action, "HARD") == "Stay out on Hards"
    context = _context(current="HARD", stops_done=1)
    assert app._option_why(merged[0], context=context) == (
        "No more stops. Waiting a lap and deciding then gives the same result."
    )
    assert app._option_why(merged[1], context=context) == (
        "Another stop costs about 24 seconds in the pits."
    )


def test_options_with_different_shown_numbers_stay_separate() -> None:
    merged = app._merge_options(
        [_option("stay out", 7.54), _option("wait and decide next lap", 7.61)]
    )
    assert len(merged) == 2


@pytest.mark.parametrize(
    ("action", "stops", "close", "allowed", "expected"),
    [
        ("pit now (HARD)", (16,), True, True, "Too close to call"),
        ("pit now (HARD)", (16,), False, True, "Box this lap"),
        ("pit in 1 lap (MEDIUM)", (17,), False, True, "Box next lap"),
        ("pit in 3 laps (MEDIUM)", (19,), False, True, "Stay out for now"),
        ("wait and decide next lap", (), False, False, "Stay out for now"),
        ("stay out", (), False, True, "Stay out to the flag"),
    ],
)
def test_headline_order_follows_decision_6(
    action: str, stops: tuple[int, ...], close: bool, allowed: bool, expected: str
) -> None:
    option = _option(action, 7.5, stop_laps=stops)
    assert app._headline(option, close_call=close, never_stop_allowed=allowed) == expected


def test_plan_segments_start_at_the_cutoff_and_switch_after_the_stop_lap() -> None:
    assert app._plan_segments(15, 57, "HARD", (), ()) == [(15.5, 57.5, "HARD")]
    assert app._plan_segments(10, 57, "SOFT", (13,), ("MEDIUM",)) == [
        (10.5, 13.5, "SOFT"),
        (13.5, 57.5, "MEDIUM"),
    ]


@pytest.mark.parametrize(
    ("probability", "phrase"),
    [
        (0.34, "1 in 3"),
        (0.76, "3 in 4"),
        (0.169, "1 in 6"),
        (0.5, "1 in 2"),
        (0.02, "fewer than 1 in 20"),
    ],
)
def test_share_phrases_use_small_denominators(probability: float, phrase: str) -> None:
    assert app._share_phrase(probability) == phrase


def test_gap_title_names_the_leader_of_the_lap_the_gap_is_measured_on() -> None:
    rows = (
        {"driver_code": "VER", "lap": 14, "gap_to_leader_s": 0.0, "is_latest": True},
        {"driver_code": "PER", "lap": 15, "gap_to_leader_s": 0.0, "is_latest": True},
        {"driver_code": "PER", "lap": 14, "gap_to_leader_s": 1.2, "is_latest": False},
        {"driver_code": "ALO", "lap": 14, "gap_to_leader_s": 27.5, "is_latest": True},
    )
    title, sub = app._gap_titles(
        {"driver": "ALO", "driver_name": "Fernando Alonso", "position": 4, "race_trace_rows": rows}
    )
    assert title == "Alonso is 4th, 27.5 s behind Verstappen"
    assert sub == "Gap to the leader, laps 1 to 15"


def test_stay_out_band_for_alonso_after_lap_15() -> None:
    result = {
        "driver": "ALO",
        "driver_name": "Fernando Alonso",
        "team_name": "Aston Martin",
        "race_name": "Bahrain Grand Prix",
        "race_season": 2023,
        "cutoff_lap": 15,
        "laps_total": 57,
        "risk": 0.5,
        "selected_color": "#358C75",
        "tire_compound": "HARD",
        "tire_age": 0,
        "stops_done": 1,
        "pit_loss_s": 24.05,
        "never_stop_allowed": True,
        "position": 4,
        "n_cars": 20,
        "simulation_count": 10_000,
        "safety_car_probability": 0.01,
        "fallback": True,
        "waiting_tie_window_laps": (17, 20),
        "race_trace_rows": (
            {"driver_code": "ALO", "lap": 14, "gap_to_leader_s": 27.5, "is_latest": True},
        ),
        "stint_rows": (
            {
                "driver_code": "ALO",
                "compound": "SOFT",
                "first_lap": 1,
                "last_visible_lap": 14,
                "start_lap": 0.5,
                "end_lap": 14.5,
            },
            {
                "driver_code": "ALO",
                "compound": "HARD",
                "first_lap": 15,
                "last_visible_lap": None,
                "start_lap": 14.5,
                "end_lap": 15.5,
            },
        ),
    }
    merged = app._merge_options(
        [
            _option("wait and decide next lap", 7.5447),
            _option("stay out", 7.5447),
            _option("pit now (HARD)", 8.6053, bad_day=17.6, podium=0.12, points=0.69),
        ]
    )
    band = app._decision_band_html(result, merged)
    assert "<h1>Stay out to the flag</h1>" in band
    assert "Alonso is on fresh Hards and has used both compounds" in band
    assert "Staying out on Hards, Alonso scores points in about 3 in 4 races" in band
    assert "Tyres: the Hards are too new to measure wear yet." in band
    assert "stop, about 24 s" in band
    assert "Another stop costs 1.1 places on average." in band
    assert "Alonso has made one stop and needs no more" in band
    assert "<b>4th</b><span>27.5 s behind the leader</span>" in band
    assert "about 1 in 3 races before the flag" in band
    assert "rough estimate" not in band  # no wear figure to qualify yet
    assert "rs-window" not in band  # decision 1: no window when no stop is planned
    assert "<svg" not in band


def test_white_text_on_team_fill_and_team_marks_meet_contrast_for_every_team() -> None:
    for color in _team_colors():
        assert contrast_ratio("#FFFFFF", team_fill(color)) >= 4.5, color
        band = band_background(color)
        assert contrast_ratio(readable_on(color, band), band) >= 3.0, color
        assert contrast_ratio(readable_on(FOG, band, 4.5), band) >= 4.5, color
        assert contrast_ratio(readable_on(color), ASPHALT) >= 3.0, color
        assert min(contrast_ratio(shade, ASPHALT) for shade in fan_band_colors(color)) >= 3.0
        for tyre in TIRE_COLORS.values():
            assert contrast_ratio(readable_on(tyre, band), band) >= 3.0, (color, tyre)


def test_fan_bands_get_stronger_toward_the_median() -> None:
    outer, middle, inner = fan_band_colors("#358C75")
    assert relative_luminance(outer) < relative_luminance(middle) < relative_luminance(inner)


def test_glossary_has_icons_only_for_terms_with_a_mark_on_the_page() -> None:
    rendered = app._glossary_html()
    assert rendered.count('class="glossary-row"') == 8
    assert rendered.count('class="gi ') == 6
    assert "<svg" not in rendered


def test_page_copy_says_tyres_not_tires() -> None:
    texts = [
        app._glossary_html(),
        app._model_report_html(app._report_summary()),
        app.THIN_TYRE_DATA_COPY,
        app._option_why(_option("stay out", 7.0), context=_context()),
        app._strategist_reason(
            current_compound="HARD",
            tire_age=3,
            laps_done=20,
            laps_total=57,
            pit_loss_s=24.0,
            next_stop_lap=None,
            target_compound=None,
            wear_rates={},
        ),
    ]
    assert all(" tire" not in text.lower() for text in texts)


def test_close_call_names_the_unmerged_runner_up() -> None:
    """The close-call gap is measured against the optimizer's second row, before merging."""
    best = _option("pit now (HARD)", 8.0, bad_day=16.0, podium=0.2, points=0.7, stop_laps=(16,))
    runner_up = _option("pit in 2 laps (MEDIUM)", 8.2, bad_day=16.4, podium=0.2, points=0.7)
    third = _option("stay out", 9.5, bad_day=18.0, podium=0.1, points=0.5)
    result = {
        "driver": "ALO",
        "driver_name": "Fernando Alonso",
        "team_name": "Aston Martin",
        "race_name": "Bahrain Grand Prix",
        "race_season": 2023,
        "cutoff_lap": 15,
        "laps_total": 57,
        "risk": 0.5,
        "selected_color": "#358C75",
        "tire_compound": "SOFT",
        "never_stop_allowed": False,
        "close_call_places": 0.2,
        "close_call_two_se": 0.3,
    }
    options = [best, runner_up, third]
    merged = [best, third]  # pretend the runner-up merged away
    band = app._decision_band_html(result, merged, options)
    assert "<h1>Too close to call</h1>" in band
    assert "Close call: boxing in 2 laps for Mediums is only 0.2 places worse" in band


@pytest.mark.parametrize(
    ("value", "verdict", "caution"),
    [
        (0.9, "On target", False),
        (0.83, "Slightly overconfident", True),
        (0.7, "Overconfident", True),
    ],
)
def test_coverage_verdict_follows_the_value(value: float, verdict: str, caution: bool) -> None:
    assert app._coverage_verdict(value) == (verdict, caution)


def test_brier_verdict_flags_a_model_no_better_than_the_grid() -> None:
    assert app._brier_verdict(0.047, 0.080) == ("Better than starting order", False)
    assert app._brier_verdict(0.090, 0.080) == ("No better than starting order", True)


def test_brackets_use_exact_chances_and_range_uses_exact_percentiles() -> None:
    option = _option("stay out", 7.5447, podium=0.1946, points=0.76, interval="P2-P17")
    strip = app._probability_strip_html(option, 20, full=True)
    assert "Podium 19%" in strip
    assert "Points (P1 to P10) 76%" in strip
    assert app._range_text(option) == "P2 to P17"
