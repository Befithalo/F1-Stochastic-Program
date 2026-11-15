"""Acceptance contracts for the approved read-only Streamlit replay page."""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "f1si" / "app.py"
THEME_PATH = APP_PATH.parents[2] / ".streamlit" / "config.toml"


def app_source() -> str:
    assert APP_PATH.is_file()
    return APP_PATH.read_text(encoding="utf-8")


def test_page_has_catalog_controls_and_locked_defaults() -> None:
    source = app_source()
    for control in ("race", "driver", "cutoff", "risk"):
        assert control in source.lower()
    assert "2023-01" in source or "Bahrain 2023" in source
    assert "ALO" in source
    assert "0.5" in source
    assert "Update replay" in source


def test_page_calls_shared_cutoff_safe_builder_and_has_no_results_door() -> None:
    tree = ast.parse(app_source(), filename=str(APP_PATH))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    assert any("walk_forward" in name or "replay" in name for name in imports)
    assert all("data.results" not in name for name in imports)
    assert "ResultsAccessor" not in app_source()


@pytest.mark.parametrize(
    "required_text",
    [
        "Brier",
        "coverage",
        "denominator",
        "strategy",
        "Safety-car probability (current proxy)",
        "Uncalibrated",
        "risk",
    ],
)
def test_page_exposes_measured_summary_and_required_outputs(
    required_text: str,
) -> None:
    assert required_text.lower() in app_source().lower()


def test_page_shows_fixed_sample_scores_and_denominators() -> None:
    app = import_module("f1si.app")
    display = app._report_display_values(app._report_summary())
    assert display["podium"] == "0.04996 / 0.08174"
    assert display["top10"] == "0.14533 / 0.19090"
    assert display["coverage"] == "Equal-race average: 83.0%; pooled: 83.4% (8,004 / 9,602)"
    assert "Equal-race average" in display["coverage"]
    assert "pooled" in display["coverage"]
    assert "388 observed stops" in display["team"]
    assert "79.0%" in display["team"]
    assert "1.40 laps" in display["team"]


def test_scorecard_renders_complete_fixed_report_values_together() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    result = app_test.from_file(APP_PATH).run()
    assert not result.exception
    metric_items = {item.label: item for item in result.metric}
    metrics = {label: item.value for label, item in metric_items.items()}
    assert metrics["Podium Brier · model / grid baseline"] == "0.04996 / 0.08174"
    assert metrics["Top-10 Brier · model / grid baseline"] == "0.14533 / 0.19090"
    assert (
        metrics["90% finish coverage · classified denominator"]
        == "Equal-race average: 83.0%; pooled: 83.4% (8,004 / 9,602)"
    )
    assert metrics["Team top-action agreement"] == "79.0%"
    assert metrics["Absolute stop-timing error"] == "1.40 laps"
    visible_copy = " ".join(item.value for item in result.caption)
    assert "95% CI 70.4%-87.0%" in visible_copy
    assert "95% CI 0.96-1.84 laps" in visible_copy
    assert "10 registered races" in visible_copy
    assert "10,942 driver/cutoff observations" in visible_copy
    assert "388 observed stops" in visible_copy


def test_page_uses_full_immutable_replay_cache_identity() -> None:
    source = app_source().lower()
    for cache_input in (
        "race_id",
        "driver",
        "cutoff_lap",
        "risk",
        "n_simulations",
        "seed",
        "data_path",
        "model_identity",
    ):
        assert cache_input in source
    assert "st.cache_data" in source
    assert "cache_resource" not in source


def test_replay_cache_identity_includes_walk_forward_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = import_module("f1si.app")
    monkeypatch.setattr(app, "PROJECT_ROOT", tmp_path)
    source = tmp_path / "src" / "f1si" / "backtest" / "walk_forward.py"
    source.parent.mkdir(parents=True)
    source.write_text("horizon = 1\n", encoding="utf-8")
    data_path = tmp_path / "cache.duckdb"
    data_path.write_bytes(b"immutable cache")

    first = app._model_identity(data_path)
    source.write_text("horizon = 2\n", encoding="utf-8")
    second = app._model_identity(data_path)

    assert first != second


@pytest.mark.parametrize(
    "state_text",
    [
        "No verified race schedule available",
        "Building cutoff-safe replay",
        "Replay could not be built for this selection.",
        "Unavailable at this cutoff",
    ],
)
def test_empty_loading_error_and_partial_states_are_explicit(
    state_text: str,
) -> None:
    assert state_text.lower() in app_source().lower()


def test_empty_schedule_body_matches_approved_copy() -> None:
    app = import_module("f1si.app")
    assert app.EMPTY_BODY == (
        "Choose an event with verified pre-race schedule metadata "
        "or load the supported local race cache."
    )


def test_streamlit_harness_can_open_page_for_zero_one_many_and_layout_assertions() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    result = app_test.from_file(APP_PATH).run()
    assert not result.exception
    assert any("Ten-race evaluation" in item.value for item in result.subheader)


def test_empty_local_cache_shows_copy_without_empty_result_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("F1SI_DATA_DIR", str(tmp_path))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    result = app_test.from_file(APP_PATH).run()
    assert not result.exception
    assert any(item.value == "No verified race schedule available" for item in result.subheader)
    assert any(
        (
            "Choose an event with verified pre-race schedule metadata "
            "or load the supported local race cache."
        )
        in item.value
        for item in result.markdown
    )
    assert len(result.dataframe) == 0
    assert len(result.get("imgs")) == 0


def test_zero_one_many_actions_use_singular_labels_and_count_visible_rows() -> None:
    app = import_module("f1si.app")
    assert hasattr(app, "_action_heading")
    assert app._action_heading(0) == "No ranked strategy actions available"
    assert app._action_heading(1) == "Ranked strategy actions · 1 action"
    assert app._action_heading(13) == "Ranked strategy actions · 13 actions"


def test_replay_error_state_cannot_reuse_stale_selected_output() -> None:
    app = import_module("f1si.app")
    assert hasattr(app, "_safe_replay_result")
    failed = app._safe_replay_result(lambda: (_ for _ in ()).throw(ValueError("bad cutoff")))
    assert failed == {"status": "error", "value": None, "reason": "bad cutoff"}
    assert "Replay could not be built for this selection." in app.ERROR_COPY


def test_catalog_cutoff_failure_does_not_render_internal_exception_details() -> None:
    assert "Replay unavailable: {err}" not in app_source()


def test_schedule_horizon_failure_uses_unavailable_copy() -> None:
    app = import_module("f1si.app")
    failure = ValueError("Scheduled race distance is unavailable for 2023-01; cannot backtest it.")
    assert app._schedule_failure_copy(failure) == app.UNAVAILABLE_SCHEDULE_COPY
    assert app._schedule_failure_copy(ValueError("snapshot read failed")) == app.ERROR_COPY


def test_eligible_catalog_excludes_races_without_verified_schedule(
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
        def snapshot(self, request):
            scheduled_laps = 0 if request.race_id == "2023-01" else 50
            return SimpleNamespace(race=SimpleNamespace(scheduled_laps=scheduled_laps))

    monkeypatch.setattr(app.asof, "catalog", lambda _path: rows.copy())
    monkeypatch.setattr(app.cli, "_make_asof_accessor", lambda _path: Accessor())

    eligible = app._eligible_catalog(Path("local-cache.duckdb"))

    assert eligible["race_id"].tolist() == ["2023-02"]


def test_fallback_rows_are_labeled_adjacent_to_each_strategy_action() -> None:
    app = import_module("f1si.app")
    assert hasattr(app, "_annotate_strategy_options")
    columns, rows = app._annotate_strategy_options(
        ("Action", "Score"), (("pit now", 2.1), ("stay out", 2.4)), True
    )
    assert columns[-1] == "Basis"
    assert [row[-1] for row in rows] == ["Uncalibrated", "Uncalibrated"]


def test_responsive_layout_stacks_panels_scrolls_table_and_wraps_long_text() -> None:
    source = app_source()
    assert "@media (max-width: 760px)" in source
    assert "overflow-x: auto" in source
    assert "overflow-wrap: anywhere" in source
    assert "white-space: normal" in source
    assert '[data-testid="stMetricLabel"] [data-testid="stMarkdownContainer"]' in source
    assert '[data-testid="stMetricValue"] [data-testid="stMarkdownContainer"]' in source
    assert '.stApp [data-testid="stMetricLabel"] {' in source
    assert '.stApp [data-testid="stCaptionContainer"] {' in source
    assert "font-variant-numeric: tabular-nums" in source
    assert ".neutral-note" in source
    assert "st.info(" not in source


def test_dark_theme_and_keyed_dashboard_styles_follow_the_ui_contract() -> None:
    config = tomllib.loads(THEME_PATH.read_text(encoding="utf-8"))
    theme = config["theme"]
    assert theme["base"] == "dark"
    assert theme["backgroundColor"] == "#1C1F23"
    assert theme["secondaryBackgroundColor"] == "#24282D"
    assert theme["primaryColor"] == "#9BA1A8"
    assert theme["textColor"] == "#ECEAE4"
    assert theme["font"] == "sans serif"

    source = app_source()
    for token in (
        "#1C1F23",
        "#24282D",
        "#3A4047",
        "#ECEAE4",
        "#9BA1A8",
        "#B69BFF",
        ".st-key-evaluation-scorecard",
        ".st-key-replay-controls",
        ".st-key-finish-chart",
        ".st-key-safety-car-card",
        ".st-key-tire-card",
        ".st-key-strategy-card",
        "font-size: 16px",
        "font-size: 14px",
        "font-size: 20px",
        "font-size: 28px",
        "@media (max-width: 760px)",
    ):
        assert token in source
    assert "button:focus-visible" in source


def test_selected_replay_chart_uses_its_finish_draws_and_shows_full_explanation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = import_module("f1si.app")
    figures = []
    captions: list[tuple[str | None, str]] = []
    containers: list[dict[str, object]] = []
    active_container: list[str | None] = []

    @contextmanager
    def capture_container(**kwargs: object) -> Iterator[None]:
        containers.append(kwargs)
        key = kwargs.get("key")
        active_container.append(key if isinstance(key, str) else None)
        try:
            yield
        finally:
            active_container.pop()

    monkeypatch.setattr(app.st, "columns", lambda *_args, **_kwargs: (nullcontext(), nullcontext()))
    monkeypatch.setattr(app.st, "container", capture_container)
    monkeypatch.setattr(app.st, "pyplot", lambda figure, **_kwargs: figures.append(figure))
    monkeypatch.setattr(
        app.st,
        "caption",
        lambda text: captions.append((active_container[-1] if active_container else None, text)),
    )
    for name in ("subheader", "progress", "metric", "info", "dataframe", "markdown"):
        monkeypatch.setattr(app.st, name, lambda *_args, **_kwargs: None)

    quantiles = tuple([2] * 25 + [4] * 50 + [6] * 25)
    fan_chart = {
        "laps": (9, 10),
        "p10": (2.0, 2.0),
        "p25": (2.0, 2.0),
        "p40": (3.0, 3.0),
        "p50": (3.0, 3.0),
        "p60": (3.0, 3.0),
        "p75": (4.0, 4.0),
        "p90": (4.0, 4.0),
        "n_cars": 6,
        "simulation_count": 4,
        "caption": "Projected ranks from 4 simulated races.",
    }
    app._render_selected(
        {
            "available": True,
            "strategy_available": True,
            "driver": "ALO",
            "cutoff_lap": 8,
            "safety_car_share": 0.1,
            "safety_car_source": "prior only",
            "n_cars": 6,
            "safety_car_probability": 0.01,
            "fallback": False,
            "tire_rate": 0.1,
            "tire_sd": 0.01,
            "tire_compound": "HARD",
            "tire_source": "filter",
            "options": (("pit now", 1.2),),
            "option_columns": ("Action", "Mean finish"),
            "option_quantiles": (quantiles,),
            "selected_cutoff_mean": 4.0,
            "simulation_count": 4,
            "fan_chart_data": fan_chart,
            "reason": "Controlled fixture",
            "risk": 0.5,
        }
    )

    assert len(figures) == 2
    mean_artist = figures[0].axes[0].get_lines()[0]
    assert mean_artist.get_xdata()[0] == pytest.approx(4.0)
    assert mean_artist.get_xdata()[0] != 8
    assert mean_artist.get_label() == "Mean finish at selected cutoff"
    assert mean_artist.get_color() == "#9BA1A8"
    assert {"border": True, "key": "finish-chart"} in containers
    assert any(
        key == "finish-chart" and "4 simulated finishes" in caption for key, caption in captions
    )
    assert any(
        key == "finish-chart" and "4 simulated races" in caption for key, caption in captions
    )


def test_selected_replay_renders_both_quantile_and_forward_position_charts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = import_module("f1si.app")
    figures = []
    active_container: list[str | None] = []

    @contextmanager
    def capture_container(**kwargs: object) -> Iterator[None]:
        key = kwargs.get("key")
        active_container.append(key if isinstance(key, str) else None)
        try:
            yield
        finally:
            active_container.pop()

    monkeypatch.setattr(app.st, "columns", lambda *_args, **_kwargs: (nullcontext(), nullcontext()))
    monkeypatch.setattr(app.st, "container", capture_container)
    monkeypatch.setattr(app.st, "pyplot", lambda figure, **_kwargs: figures.append(figure))
    for name in ("subheader", "progress", "metric", "info", "dataframe", "markdown", "caption"):
        monkeypatch.setattr(app.st, name, lambda *_args, **_kwargs: None)

    app._render_selected(
        {
            "available": True,
            "strategy_available": True,
            "driver": "ALO",
            "cutoff_lap": 8,
            "safety_car_share": 0.1,
            "safety_car_source": "prior only",
            "n_cars": 6,
            "safety_car_probability": 0.01,
            "fallback": False,
            "tire_rate": 0.1,
            "tire_sd": 0.01,
            "tire_compound": "HARD",
            "tire_source": "filter",
            "options": (("pit now", 1.2),),
            "option_columns": ("Action", "Mean finish"),
            "option_quantiles": (tuple([2] * 100),),
            "selected_cutoff_mean": 3.0,
            "simulation_count": 4,
            "fan_chart_data": {
                "laps": (9, 10),
                "p10": (2.0, 2.0),
                "p25": (2.0, 2.0),
                "p40": (3.0, 3.0),
                "p50": (3.0, 3.0),
                "p60": (3.0, 3.0),
                "p75": (4.0, 4.0),
                "p90": (4.0, 4.0),
                "n_cars": 6,
                "simulation_count": 4,
                "caption": "Projected ranks from 4 simulated races.",
            },
            "reason": "Controlled fixture",
            "risk": 0.5,
        }
    )

    assert len(figures) == 2, "The selected cutoff should render both uncertainty charts."
    assert len(figures[1].axes[0].collections) >= 3


def test_selected_cutoff_simulates_recommended_plan_and_caches_only_compact_fan_bands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = import_module("f1si.app")
    recommended_plan = object()
    option = SimpleNamespace(
        action="pit now",
        plan=recommended_plan,
        mean_finish=4.0,
        spread=1.0,
        cvar10=6.0,
        score=5.0,
        podium_probability=0.25,
        top10_probability=1.0,
        finish_p05=1,
        finish_p95=8,
        finish_quantiles=tuple([1] * 12 + [2] * 13 + [4] * 50 + [6] * 25),
    )
    analysis = SimpleNamespace(best=option, options=(option,), reason="Pit now ranks first.")
    car = SimpleNamespace(
        driver="ALO",
        compound="HARD",
        wear_rate_s_per_lap=0.1,
        wear_sd=0.01,
        wear_source="filter",
    )

    class FakeState:
        def __init__(self) -> None:
            self.cars = (
                car,
                *(SimpleNamespace(driver=f"D{index:02d}") for index in range(2, 13)),
            )

        @staticmethod
        def car(code: str) -> object:
            assert code == "ALO"
            return car

    context = SimpleNamespace(
        state=FakeState(),
        model=object(),
        compounds=("HARD", "MEDIUM"),
        wear_sd_by_compound={"HARD": 0.01},
        estimate=SimpleNamespace(rate_per_lap=0.02, duration_laps=4),
        is_fallback=False,
    )
    snapshot = SimpleNamespace(
        entries={"driver_code": ("ALO", "VER")},
        race=SimpleNamespace(event_name="Bahrain"),
    )

    class FakeAccessor:
        @staticmethod
        def snapshot(_as_of: object) -> object:
            return snapshot

    calls: dict[str, object] = {}
    history = np.asarray(
        [
            np.arange(1, 11),
            np.arange(2, 12),
            np.arange(3, 13),
            np.arange(1, 11),
        ],
        dtype=np.int64,
    )

    class FakeSimulator:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def simulate(self, state: object, **kwargs: object) -> object:
            calls["state"] = state
            calls.update(kwargs)
            return SimpleNamespace(
                finish_positions=np.ones((4, 2), dtype=np.int64),
                sc_lap_mask=np.zeros((4, 10), dtype=np.bool_),
                position_history=history,
            )

    monkeypatch.setattr(app.cli, "_make_asof_accessor", lambda _path: FakeAccessor())
    monkeypatch.setattr(app.walk_forward, "_race_laps_total", lambda *_args: 20)
    monkeypatch.setattr(app.cli, "_prepare_replay_context", lambda *_args, **_kwargs: context)
    monkeypatch.setattr(
        app.cli,
        "_replay_at_cutoff",
        lambda *_args, **_kwargs: SimpleNamespace(analysis=analysis, is_fallback=False),
    )
    monkeypatch.setattr(app.cli, "_sc_source", lambda _estimate: "prior only")
    monkeypatch.setattr(app, "NumpySimulator", FakeSimulator)

    result = app._build_selected_replay(
        "2023-01", "ALO", 10, 0.5, 4, 3, str(tmp_path / "cache.duckdb"), "model-id"
    )

    assert calls["position_history_driver"] == "ALO"
    assert calls["plans"] == {"ALO": recommended_plan}
    fan = result["fan_chart_data"]
    assert fan.laps == tuple(range(11, 21))
    np.testing.assert_allclose(fan.p50, np.quantile(history, 0.5, axis=0))
    assert fan.simulation_count == 4
    assert "position_history" not in result
    assert "finishes" not in result


def test_top_ranked_marker_stays_on_first_action_and_preserves_each_basis() -> None:
    app = import_module("f1si.app")
    assert hasattr(app, "_ranked_strategy_rows")
    columns, rows = app._ranked_strategy_rows(
        ("Action", "Mean finish", "Basis"),
        (("pit now", 2.1, "Uncalibrated"), ("stay out", 2.4, "Cutoff inputs")),
    )

    assert columns == ("Rank", "Action", "Mean finish", "Basis")
    assert rows == (
        ("Top", "pit now", 2.1, "Uncalibrated"),
        ("", "stay out", 2.4, "Cutoff inputs"),
    )


@pytest.mark.parametrize("reason", ["private database path", "stack trace secret"])
def test_replay_error_renderer_uses_only_approved_copy_and_returns_before_outputs(
    monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    app = import_module("f1si.app")
    messages: list[str] = []
    selected: list[dict[str, object]] = []
    assert hasattr(app, "_render_replay_outcome")
    monkeypatch.setattr(app.st, "error", messages.append)
    monkeypatch.setattr(app, "_render_selected", selected.append)

    app._render_replay_outcome({"status": "error", "value": None, "reason": reason})

    assert messages == [app.ERROR_COPY]
    assert reason not in messages[0]
    assert selected == []


def test_risk_control_has_visible_endpoints_value_spacing_and_44px_targets() -> None:
    app = import_module("f1si.app")
    source = app_source()
    assert "0.0 Mean-focused" in source
    assert "1.0 tail-risk-focused" in source
    assert app._risk_value_label(0.5) == "Current risk aversion: 0.50"
    assert "_risk_value_label(risk)" in source
    for token in ("4px", "8px", "16px", "24px", "32px", "48px", "64px"):
        assert token in source
    assert "min-height: 44px" in source
    assert source.index("st.caption(_risk_value_label(risk))") < source.index(
        "st.form_submit_button"
    )
    submit_call = source.index("st.form_submit_button")
    assert '"Update replay"' in source[submit_call : submit_call + 120]


def test_safety_car_probability_uses_neutral_track_and_one_positioned_accent_marker() -> None:
    app = import_module("f1si.app")
    assert hasattr(app, "_probability_track_markup")
    track = app._probability_track_markup(0.25)

    assert "#24282D" in track
    assert track.count("#9BA1A8") == 1
    assert "left: 25.0%" in track
    assert 'role="img"' in track
    assert 'aria-label="Safety-car probability: 25.0%"' in track
