"""Acceptance checks for the replay page and its chart data path."""

from __future__ import annotations

import ast
import tomllib
from contextlib import nullcontext
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

from f1si.data.asof import AsOf
from f1si.ui_theme import (
    ASPHALT,
    CHALK,
    FOG,
    RECOMMENDATION,
    TIMING_COLORS,
    TIRE_COLORS,
    contrast_ratio,
)

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "f1si" / "app.py"
THEME_PATH = APP_PATH.parents[2] / ".streamlit" / "config.toml"
CSS_PATH = APP_PATH.with_name("dashboard.css")


def app_source() -> str:
    return APP_PATH.read_text(encoding="utf-8")


def test_page_defaults_to_bahrain_2023_alo_after_lap_15() -> None:
    source = app_source()
    assert 'default_race = "2023-01"' in source
    assert '"ALO" if "ALO" in driver_options' in source
    assert "15 if 15 in cutoff_options" in source
    assert 'st.selectbox(\n                "Race"' in source
    assert 'st.selectbox(\n                "Driver"' in source
    assert 'st.selectbox(\n                "After lap"' in source
    assert 'st.slider(\n                "Risk setting"' in source
    assert "st.form(" not in source
    assert "st.form_submit_button" not in source


def test_race_picker_uses_full_event_name() -> None:
    app = import_module("f1si.app")
    assert app._race_label(SimpleNamespace(event_name="Bahrain Grand Prix", season=2023)) == (
        "Bahrain Grand Prix 2023"
    )


def test_page_copy_uses_plain_language_and_has_no_middle_dot() -> None:
    source = (app_source() + CSS_PATH.read_text(encoding="utf-8")).lower()
    assert "·" not in source
    for phrase in ("cutoff-safe", "classified denominator", "schedule horizon"):
        assert phrase not in source
    assert "shading shows the share of simulated finishes" in source
    assert "no strategy is available at this lap." in source


def test_page_uses_shared_asof_replay_builder_without_results_imports() -> None:
    tree = ast.parse(app_source(), filename=str(APP_PATH))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    assert any("walk_forward" in name or "replay" in name for name in modules)
    assert all("data.results" not in name for name in modules)
    assert "ResultsAccessor" not in app_source()


def test_report_copy_formats_brier_scores_and_keeps_coverage_target_visible() -> None:
    app = import_module("f1si.app")
    report = app._report_summary()
    metrics = report["metrics"]
    podium, top10 = metrics["podium_brier"], metrics["top10_brier"]
    coverage = metrics["finish_interval_90"]
    pooled = coverage["covered"] / coverage["classified_finishers"]
    display = app._report_display_values(report)
    assert display["podium"] == (
        f"Model {podium['model']['mean']:.3f} vs grid baseline "
        f"{podium['baseline']['mean']:.3f} (lower is better)"
    )
    assert display["top10"] == (
        f"Model {top10['model']['mean']:.3f} vs grid baseline "
        f"{top10['baseline']['mean']:.3f} (lower is better)"
    )
    assert display["coverage"].startswith(
        f"{coverage['coverage']['mean']:.0%} race average; {pooled:.1%} across all finishes"
    )
    assert "Target: 85% to 95%" in display["coverage"]


def test_recommended_reason_explains_tire_pace_and_pit_loss() -> None:
    app = import_module("f1si.app")
    reason = app._strategist_reason(
        "pit now (MEDIUM)",
        current_compound="SOFT",
        tire_age=15,
        laps_done=15,
        laps_total=57,
        pit_loss_s=24.0,
        next_stop_lap=16,
        target_compound="MEDIUM",
        wear_rates={"SOFT": 0.20, "MEDIUM": 0.10},
    )
    assert reason == (
        "Box this lap: fresh Medium should make back the stop loss as the Soft loses pace."
    )


def test_evaluation_uses_five_explained_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    app = import_module("f1si.app")
    fragments: list[str] = []
    monkeypatch.setattr(app.st, "html", fragments.append)
    monkeypatch.setattr(app.st, "metric", lambda *_args, **_kwargs: pytest.fail("stat card"))

    app._render_report_summary(app._report_summary())

    assert len(fragments) == 1
    assert "How good is this model?" in fragments[0]
    assert "Better than starting order" in fragments[0]
    podium = app._report_summary()["metrics"]["podium_brier"]
    assert (
        f"model {podium['model']['mean']:.3f} versus grid baseline {podium['baseline']['mean']:.3f}"
    ) in fragments[0]
    assert "Target: 85% to 95%" in fragments[0]
    assert fragments[0].count('class="metric"') == 5


def test_theme_is_dark_borderless_and_uses_v2_fonts_and_palette() -> None:
    config = tomllib.loads(THEME_PATH.read_text(encoding="utf-8"))
    theme = config["theme"]
    assert theme["base"] == "dark"
    assert theme["font"].startswith("Titillium Web:https://fonts.googleapis.com/")
    assert theme["headingFont"].startswith("Saira Condensed:https://fonts.googleapis.com/")
    assert theme["backgroundColor"] == "#1B1D23"
    assert theme["secondaryBackgroundColor"] == "#23262E"
    assert theme["borderColor"] == theme["backgroundColor"]
    assert theme["dataframeBorderColor"] == theme["backgroundColor"]
    assert theme["showWidgetBorder"] is False
    assert len(theme["chartCategoricalColors"]) == 10
    assert config["client"]["toolbarMode"] == "minimal"


def test_ui_text_and_data_colors_meet_contrast_thresholds() -> None:
    team_names = (
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
    )
    team_names_2024_25 = (
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
    )
    palette = import_module("f1si.plots.replay_charts").fastf1_team_color_map
    colors = {
        **palette(2023, team_names),
        **palette(2024, team_names_2024_25),
        **palette(2025, team_names_2024_25),
    }
    text_colors = (CHALK, FOG, RECOMMENDATION)
    assert all(contrast_ratio(color, ASPHALT) >= 4.5 for color in text_colors)
    data_colors = (*colors.values(), *TIRE_COLORS.values(), *TIMING_COLORS.values())
    assert min(contrast_ratio(color, ASPHALT) for color in data_colors) >= 3.0


def test_page_uses_tabular_numbers_and_has_no_metric_cards() -> None:
    source = app_source() + CSS_PATH.read_text(encoding="utf-8")
    assert "font-variant-numeric: tabular-nums" in source
    assert 'font-feature-settings: "tnum"' in source
    assert "st.metric(" not in source
    assert "border: 1px solid" not in source
    assert 'st.container(key="replay-controls")' in source
    assert "@media (max-width: 760px)" in source
    assert ".vega-embed .vega-actions" in source
    assert '[data-testid="stHeaderActionElements"]' in source
    assert "white-space: nowrap" in source
    assert "min_value=0.0" in source
    assert "max_value=1.0" in source
    assert "min-height: 44px" in source
    assert "Safety car" in source
    assert "st.progress(" not in source


def test_format_strategy_table_hides_basis_and_formats_values() -> None:
    app = import_module("f1si.app")
    table = app._format_strategy_table(
        (
            "Action",
            "Mean finish",
            "Spread",
            "Worst 10% average finish",
            "Podium chance",
            "Top-10 chance",
            "90% finish interval",
        ),
        (("stay out", 7.286, 3.141, 15.264, 0.071, 0.864, "P2-P17"),),
    )
    assert "Recommended" not in table.columns
    assert "Score" not in table.columns
    assert table.iloc[0]["Mean finish"] == "7.3"
    assert table.iloc[0]["Podium chance"] == "7%"
    assert table.iloc[0]["Top-10 chance"] == "86%"
    assert table.iloc[0]["Action"] == "Stay out"


def test_mobile_strategy_table_keeps_results_and_labels_recommendation() -> None:
    app = import_module("f1si.app")
    table = app._format_strategy_table(
        (
            "Action",
            "Mean finish",
            "Spread",
            "Worst 10% average finish",
            "Podium chance",
            "Top-10 chance",
            "90% finish interval",
        ),
        (("stay out", 7.286, 3.141, 15.264, 0.16, 0.80, "P2-P15"),),
    )

    rendered = app._strategy_table_html(table)
    assert 'class="mobile-results"' in rendered
    assert "Recommended: Stay out" in rendered
    assert (
        "Mean P7.3. Spread 3.1. Worst 10% P15.3. Podium 16%. Top 10% 80%. Range P2-P15." in rendered
    )


def test_compact_dotplot_labels_keep_timing_and_compound() -> None:
    app = import_module("f1si.app")
    assert app._dotplot_action_copy("pit now (HARD)") == "Box now H"
    assert app._dotplot_action_copy("pit in 1 lap(s) (MEDIUM)") == "Box +1 lap M"
    assert app._dotplot_action_copy("wait and decide next lap") == "Wait and decide next lap"
    assert app._dotplot_action_copy("stay out") == "Stay out"


def test_replay_uses_ten_thousand_simulations() -> None:
    app = import_module("f1si.app")
    assert app.SIMULATIONS == 10_000


def test_replay_cache_identity_includes_model_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = import_module("f1si.app")
    monkeypatch.setattr(app, "PROJECT_ROOT", tmp_path)
    source = tmp_path / "src" / "f1si" / "module.py"
    source.parent.mkdir(parents=True)
    source.write_text("revision = 1\n", encoding="utf-8")
    data_path = tmp_path / "cache.duckdb"
    data_path.write_bytes(b"immutable cache")
    first = app._model_identity(data_path)
    source.write_text("revision = 2\n", encoding="utf-8")
    assert app._model_identity(data_path) != first


def test_empty_copy_is_two_sentences_with_a_next_step() -> None:
    app = import_module("f1si.app")
    assert app.EMPTY_BODY == (
        "No eligible races are available because their scheduled lap counts are missing. "
        "Refresh the race cache, then choose a supported event."
    )


def test_empty_cache_renders_the_two_sentence_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("F1SI_DATA_DIR", str(tmp_path))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    result = app_test.from_file(APP_PATH).run()
    assert not result.exception
    app = import_module("f1si.app")
    assert any(item.value == app.EMPTY_BODY for item in result.markdown)


def test_safe_replay_failure_discards_exception_details() -> None:
    app = import_module("f1si.app")
    failed = app._safe_replay_result(lambda: (_ for _ in ()).throw(ValueError("secret detail")))
    assert failed == {"status": "error", "value": None}
    assert "secret detail" not in app.ERROR_COPY


def test_replay_error_state_does_not_reuse_a_previous_selection() -> None:
    app = import_module("f1si.app")
    ready = app._safe_replay_result(lambda: {"driver": "ALO"})
    failed = app._safe_replay_result(
        lambda: (_ for _ in ()).throw(ValueError("new selection failed"))
    )
    assert ready == {"status": "ready", "value": {"driver": "ALO"}}
    assert failed == {"status": "error", "value": None}


def test_zero_one_and_many_action_states_have_matching_table_rows() -> None:
    app = import_module("f1si.app")
    columns = (
        "Action",
        "Mean finish",
        "Spread",
        "Worst 10% average finish",
        "Podium chance",
        "Top-10 chance",
        "90% finish interval",
    )
    one = app._format_strategy_table(columns, (("stay out", 7.2, 2.0, 15.0, 0.1, 0.8, "P2-P17"),))
    many = app._format_strategy_table(
        columns,
        (
            ("stay out", 7.2, 2.0, 15.0, 0.1, 0.8, "P2-P17"),
            ("pit now (MEDIUM)", 6.8, 2.0, 14.0, 0.2, 0.9, "P1-P16"),
            ("pit in 2 lap(s)", 7.0, 2.0, 13.0, 0.2, 0.9, "P1-P15"),
        ),
    )
    empty = app._format_strategy_table(columns, ())
    assert app._action_heading(0) == "No strategy options available"
    assert app._action_heading(1) == "Strategy options"
    assert app._action_heading(3) == "Strategy options"
    assert len(empty) == 0
    assert len(one) == 1
    assert len(many) == 3
    assert "Stay out" in app._strategy_table_html(one)
    assert "Box this lap (Medium)" in app._strategy_table_html(many)


def test_schedule_failure_has_actionable_copy() -> None:
    app = import_module("f1si.app")
    failure = ValueError("Scheduled race distance is unavailable for 2023-01")
    assert app._schedule_failure_copy(failure) == app.UNAVAILABLE_SCHEDULE_COPY
    assert app._schedule_failure_copy(ValueError("snapshot failed")) == app.ERROR_COPY


def test_eligible_catalog_excludes_races_without_a_verified_lap_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = import_module("f1si.app")
    rows = pd.DataFrame(
        [
            {
                "race_id": "2023-01",
                "season": 2023,
                "load_status": "complete",
                "out_of_sample": False,
            },
            {
                "race_id": "2023-02",
                "season": 2023,
                "load_status": "complete",
                "out_of_sample": False,
            },
        ]
    )

    class Accessor:
        @staticmethod
        def snapshot(request: AsOf) -> object:
            return SimpleNamespace(race_id=request.race_id)

    monkeypatch.setattr(app._eligible_catalog, "clear", lambda: None)
    monkeypatch.setattr(app.asof, "catalog", lambda _path: rows.copy())
    monkeypatch.setattr(app.cli, "_make_asof_accessor", lambda _path: Accessor())
    monkeypatch.setattr(
        app.walk_forward,
        "_race_laps_total",
        lambda _accessor, race_id, _snapshot: 58 if race_id == "2023-02" else _raise_missing_laps(),
    )

    eligible = app._eligible_catalog(Path("local-cache.duckdb"))
    assert eligible["race_id"].tolist() == ["2023-02"]


def _raise_missing_laps() -> int:
    raise ValueError("Scheduled race distance is unavailable")


def test_rendered_selected_replay_contains_all_four_altair_charts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = import_module("f1si.app")
    charts: list[Any] = []
    fragments: list[str] = []
    captions: list[str] = []
    monkeypatch.setattr(app.st, "columns", lambda *_args, **_kwargs: [nullcontext(), nullcontext()])
    monkeypatch.setattr(app.st, "write", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app.st, "caption", lambda value, **_kwargs: captions.append(str(value)))
    monkeypatch.setattr(app.st, "html", lambda value: fragments.append(str(value)))
    monkeypatch.setattr(app.st, "altair_chart", lambda chart, **_kwargs: charts.append(chart))
    monkeypatch.setattr(app.st, "dataframe", lambda *_args, **_kwargs: None)

    app._render_selected(
        {
            "available": True,
            "strategy_available": True,
            "race_name": "Bahrain Grand Prix",
            "race_season": 2023,
            "driver": "ALO",
            "driver_name": "Fernando Alonso",
            "team_name": "Aston Martin",
            "cutoff_lap": 15,
            "laps_total": 57,
            "risk": 0.5,
            "options": (("pit now (MEDIUM)", 7.3, 2.0, 15.3, 0.07, 0.86, "P2-P17"),),
            "option_columns": (
                "Action",
                "Mean finish",
                "Spread",
                "Worst 10% average finish",
                "Podium chance",
                "Top-10 chance",
                "90% finish interval",
            ),
            "option_quantiles": (tuple([3] * 50 + [8] * 50),),
            "selected_cutoff_mean": 7.3,
            "simulation_count": 100,
            "fan_chart_data": {
                "laps": (16, 17),
                "p10": (3.0, 3.0),
                "p25": (5.0, 5.0),
                "p40": (6.0, 6.0),
                "p50": (7.0, 7.0),
                "p60": (8.0, 8.0),
                "p75": (9.0, 9.0),
                "p90": (10.0, 10.0),
                "n_cars": 20,
                "simulation_count": 100,
                "caption": "Projected ranks from 100 simulated races.",
            },
            "reason": "Box this lap: fresh Medium should make back the stop loss.",
            "n_cars": 20,
            "safety_car_probability": 0.02,
            "tire_rate": 0.12,
            "tire_sd": 0.01,
            "tire_compound": "HARD",
            "tire_source": "filter",
            "fallback": False,
            "race_trace_rows": (
                {
                    "driver_code": "ALO",
                    "team_name": "Aston Martin",
                    "lap": 15,
                    "gap_to_leader_s": 4.2,
                    "teammate_dash": False,
                    "timing_status": "overall best",
                    "timing_label": "Best",
                    "timing_color": "#9BA1A8",
                    "driver_label": "ALO",
                    "label_gap_s": 4.2,
                    "label_lap": 16.5,
                    "is_latest": True,
                    "lap_time_s": 91.2,
                },
            ),
            "stint_rows": (
                {
                    "driver_code": "ALO",
                    "compound": "HARD",
                    "compound_letter": "H",
                    "first_lap": 1,
                    "last_visible_lap": 15,
                    "start_lap": 0.5,
                    "end_lap": 15.5,
                    "mid_lap": 8,
                },
            ),
            "selected_color": "#358c75",
            "recommended_stop_lap": 16,
            "recommended_compound": "MEDIUM",
            "driver_order": ("ALO",),
        }
    )

    assert len(charts) == 4
    assert all(hasattr(chart, "to_dict") for chart in charts)
    assert "#358c75" in str(charts[2].to_dict())
    option_html = next(value for value in fragments if 'id="options"' in value)
    assert 'class="option-row recommended"' in option_html
    assert "Show all numbers" in option_html
    assert "Never stop" in option_html
    assert any("Shading shows the share" in value for value in captions)
    assert "10th" in str(charts[2].to_dict())


def test_strategy_table_has_no_basis_column_and_uses_one_decimal_and_whole_percents() -> None:
    app = import_module("f1si.app")
    columns = (
        "Action",
        "Mean finish",
        "Spread",
        "Worst 10% average finish",
        "Podium chance",
        "Top-10 chance",
        "90% finish interval",
    )
    result = {
        "option_columns": columns,
        "options": (("pit now (MEDIUM)", 5.26, 2.0, 10.5, 0.334, 0.806, "P1-P12"),),
    }
    formatted = app._format_strategy_table(result["option_columns"], result["options"])
    assert "Basis" not in formatted.columns
    assert formatted.iloc[0]["Mean finish"] == "5.3"
    assert formatted.iloc[0]["Podium chance"] == "33%"
    assert formatted.iloc[0]["Action"] == "Box this lap (Medium)"
    html = app._strategy_table_html(formatted)
    assert 'style="color:#4ADE80;font-weight:600"' in html
    assert "Recommended</th>" not in html
    assert "Score</th>" not in html


def test_unavailable_cutoff_renders_one_actionable_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = import_module("f1si.app")
    fragments: list[str] = []
    monkeypatch.setattr(app.st, "html", lambda value: fragments.append(str(value)))
    monkeypatch.setattr(
        app.st,
        "altair_chart",
        lambda *_args, **_kwargs: pytest.fail("unavailable replay rendered a chart"),
    )
    monkeypatch.setattr(
        app.st,
        "table",
        lambda *_args, **_kwargs: pytest.fail("unavailable replay rendered a table"),
    )

    app._render_selected({"available": False})

    assert "This cutoff is unavailable. Choose another lap or race." in fragments[0]


def test_catalog_failure_does_not_show_internal_error_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = import_module("f1si.app")
    writes: list[str] = []
    monkeypatch.setattr(app, "_data_file", lambda: Path("cache.duckdb"))
    monkeypatch.setattr(
        app,
        "_eligible_catalog",
        lambda _path: (_ for _ in ()).throw(RuntimeError("C:\\private\\cache\\db error")),
    )
    monkeypatch.setattr(app, "_apply_styles", lambda: None)
    monkeypatch.setattr(app.st, "set_page_config", lambda **_kwargs: None)
    monkeypatch.setattr(app.st, "title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app.st, "write", lambda value: writes.append(str(value)))

    app.main()

    assert writes == [app.EMPTY_BODY]
    assert all("private" not in text and "db error" not in text for text in writes)


def test_fan_chart_uses_recommended_pathwise_policy_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = import_module("f1si.app")
    plan = SimpleNamespace(stop_laps=(11,), compounds=("MEDIUM",))
    option = SimpleNamespace(
        action="pit in 1 lap (MEDIUM)",
        plan=plan,
        mean_finish=4.0,
        spread=1.0,
        cvar10=6.0,
        score=5.0,
        podium_probability=0.25,
        top10_probability=1.0,
        finish_p05=1,
        finish_p95=8,
        finish_quantiles=tuple([1] * 100),
    )
    history = np.tile(np.arange(1, 11, dtype=np.int64), (4, 1))
    analysis = SimpleNamespace(
        best=option,
        options=(option,),
        recommended_position_history=history,
        close_call_places=None,
        close_call_two_se=None,
        waiting_tie_window_laps=(12, 16),
        never_stop_allowed=False,
    )
    car = SimpleNamespace(
        compound="HARD",
        tire_age=10,
        wear_rate_s_per_lap=0.1,
        wear_sd=0.01,
        wear_source="filter",
    )
    state = SimpleNamespace(
        cars=tuple(SimpleNamespace(driver=f"D{index:02d}") for index in range(20)),
        car=lambda _code: car,
        laps_done_of=lambda _car: 10,
        pit_loss_s={"green": 24.0},
    )
    context = SimpleNamespace(
        state=state,
        model=object(),
        compounds=("HARD", "MEDIUM"),
        wear_sd_by_compound={"HARD": 0.01},
        estimate=SimpleNamespace(rate_per_lap=0.02, duration_laps=4),
        is_fallback=False,
    )
    empty_laps = pd.DataFrame(
        columns=(
            "driver_number",
            "lap_number",
            "lap_end_s",
            "lap_time_s",
            "is_pit_in_lap",
            "is_pit_out_lap",
        )
    )
    snapshot = SimpleNamespace(
        entries=pd.DataFrame(
            [
                {
                    "driver_number": 14,
                    "driver_code": "ALO",
                    "team_name": "Aston Martin",
                    "grid_position": 7,
                }
            ]
        ),
        laps=empty_laps,
        stints=pd.DataFrame(),
        race=SimpleNamespace(event_name="Bahrain", season=2023),
    )

    class FakeAccessor:
        @staticmethod
        def snapshot(_as_of: object) -> object:
            return snapshot

    calls: dict[str, object] = {}

    monkeypatch.setattr(app._build_selected_replay, "clear", lambda: None)
    monkeypatch.setattr(app.cli, "_make_asof_accessor", lambda _path: FakeAccessor())
    monkeypatch.setattr(app.walk_forward, "_race_laps_total", lambda *_args: 20)
    monkeypatch.setattr(app.cli, "_prepare_replay_context", lambda *_args, **_kwargs: context)

    def replay(*_args: object, **kwargs: object) -> object:
        calls.update(kwargs)
        return SimpleNamespace(analysis=analysis, is_fallback=False)

    monkeypatch.setattr(app.cli, "_replay_at_cutoff", replay)
    monkeypatch.setattr(app, "fastf1_team_color_map", lambda *_args: {})

    result = app._build_selected_replay(
        "2023-01", "ALO", 10, 0.5, 4, 3, str(tmp_path / "cache.duckdb"), "model-id"
    )

    assert calls["retain_position_history"] is True
    fan = result["fan_chart_data"]
    assert fan.laps == tuple(range(11, 21))
    np.testing.assert_allclose(fan.p50, np.quantile(history, 0.5, axis=0))
    assert "position_history" not in result
    assert "finishes" not in result
