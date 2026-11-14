"""Acceptance contracts for the approved read-only Streamlit replay page."""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

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
    assert display["coverage"] == "8,004 / 9,602 (83.0%)"
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
    assert failed == {"status": "error", "value": None}
    assert "Replay could not be built for this selection." in app.ERROR_COPY


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
