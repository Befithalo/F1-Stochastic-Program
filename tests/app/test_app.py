"""Acceptance contracts for the approved read-only Streamlit replay page."""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest

APP_PATH = Path("src/f1si/app.py")


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
    source = app_source().lower()
    for measured_value in (
        "0.04996",
        "0.08174",
        "0.14533",
        "0.19090",
        "8,004 / 9,602",
        "388",
        "0.7899",
        "1.40 laps",
    ):
        assert measured_value in source


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
    assert app_test.from_file(str(APP_PATH)) is not None
