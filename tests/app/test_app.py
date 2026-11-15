"""Acceptance contracts for the approved read-only Streamlit replay page."""

from __future__ import annotations

import ast
from contextlib import contextmanager, nullcontext
from importlib import import_module
from pathlib import Path

import numpy as np
import pytest

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "f1si" / "app.py"


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
        "UNCALIBRATED",
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
        "No race data available",
        "Load the local race cache, then reload this page.",
        "Building cutoff-safe replay",
        "Replay could not be built for this selection.",
        "Unavailable at this cutoff",
    ],
)
def test_empty_loading_error_and_partial_states_are_explicit(
    state_text: str,
) -> None:
    assert state_text.lower() in app_source().lower()


def test_streamlit_harness_can_open_page_for_zero_one_many_and_layout_assertions() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    result = app_test.from_file(APP_PATH).run()
    assert not result.exception
    assert any("Complete ten-race evaluation" in item.value for item in result.subheader)


def test_empty_local_cache_shows_copy_without_empty_result_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("F1SI_DATA_DIR", str(tmp_path))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    result = app_test.from_file(APP_PATH).run()
    assert not result.exception
    assert any(item.value == "No race data available" for item in result.subheader)
    assert any(
        "Load the local race cache, then reload this page." in item.value
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


def test_fallback_rows_are_labeled_adjacent_to_each_strategy_action() -> None:
    app = import_module("f1si.app")
    assert hasattr(app, "_annotate_strategy_options")
    columns, rows = app._annotate_strategy_options(
        ("Action", "Score"), (("pit now", 2.1), ("stay out", 2.4)), True
    )
    assert columns[-1] == "Basis"
    assert [row[-1] for row in rows] == ["UNCALIBRATED", "UNCALIBRATED"]


def test_responsive_layout_stacks_panels_scrolls_table_and_wraps_long_text() -> None:
    source = app_source()
    assert "@media (max-width: 760px)" in source
    assert "overflow-x: auto" in source
    assert "overflow-wrap: anywhere" in source
    assert "white-space: normal" in source


def test_selected_replay_chart_uses_its_finish_draws_and_shows_full_explanation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = import_module("f1si.app")
    figures = []
    captions: list[tuple[str | None, str]] = []
    containers: list[dict[str, object]] = []
    active_container: list[str | None] = []

    @contextmanager
    def capture_container(**kwargs: object):
        containers.append(kwargs)
        active_container.append(kwargs.get("key") if isinstance(kwargs.get("key"), str) else None)
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

    finishes = (2, 4, 4, 6)
    app._render_selected(
        {
            "available": True,
            "strategy_available": True,
            "finishes": finishes,
            "driver": "ALO",
            "cutoff_lap": 8,
            "safety_car_share": 0.1,
            "safety_car_source": "prior only",
            "n_cars": 6,
            "safety_car_probability": 0.01,
            "fallback": False,
            "tire_rate": 0.1,
            "tire_sd": 0.01,
            "tire_source": "filter",
            "options": (("pit now", 1.2),),
            "option_columns": ("Action", "Mean finish"),
            "reason": "Controlled fixture",
            "risk": 0.5,
        }
    )

    assert len(figures) == 1
    mean_artist = figures[0].axes[0].get_lines()[0]
    assert mean_artist.get_xdata()[0] == pytest.approx(float(np.mean(finishes)))
    assert mean_artist.get_xdata()[0] != 8
    assert {"border": True, "key": "finish-chart"} in containers
    assert any(key == "finish-chart" and "90% interval" in caption for key, caption in captions)


def test_top_ranked_marker_stays_on_first_action_and_preserves_each_basis() -> None:
    app = import_module("f1si.app")
    assert hasattr(app, "_ranked_strategy_rows")
    columns, rows = app._ranked_strategy_rows(
        ("Action", "Mean finish", "Basis"),
        (("pit now", 2.1, "UNCALIBRATED"), ("stay out", 2.4, "Cutoff inputs")),
    )

    assert columns == ("Rank", "Action", "Mean finish", "Basis")
    assert rows == (
        ("TOP", "pit now", 2.1, "UNCALIBRATED"),
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
    monkeypatch.setattr(app.st, "info", messages.append)
    monkeypatch.setattr(app, "_render_selected", selected.append)

    app._render_replay_outcome({"status": "error", "value": None, "reason": reason})

    assert messages == [app.ERROR_COPY]
    assert reason not in messages[0]
    assert selected == []


def test_risk_control_has_visible_endpoints_value_spacing_and_44px_targets() -> None:
    app = import_module("f1si.app")
    source = app_source()
    assert "0.0 Mean-focused" in source
    assert "1.0 Tail-risk-focused" in source
    assert app._risk_value_label(0.5) == "Current risk aversion: 0.50"
    assert "_risk_value_label(risk)" in source
    for token in ("4px", "8px", "16px", "24px", "32px", "48px", "64px"):
        assert token in source
    assert "min-height: 44px" in source
    assert source.index("Current risk aversion") < source.index(
        'st.form_submit_button("Update replay"'
    )


def test_safety_car_probability_uses_neutral_track_and_one_positioned_accent_marker() -> None:
    app = import_module("f1si.app")
    assert hasattr(app, "_probability_track_markup")
    track = app._probability_track_markup(0.25)

    assert "#E9EEF3" in track
    assert track.count("#D90429") == 1
    assert "left: 25.0%" in track
    assert 'role="img"' in track
