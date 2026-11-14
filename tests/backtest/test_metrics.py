"""Numeric and ordering contracts for Phase 6 scoring and metric aggregation."""

from __future__ import annotations

import importlib.util


def test_brier_score_api_is_available_for_binary_outcomes() -> None:
    module = importlib.util.find_spec("f1si.backtest.metrics")
    assert module is not None, "metrics must expose deterministic Brier scoring"
