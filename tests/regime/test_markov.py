"""Mathematical and observation-contract tests for the five-state model."""

import numpy as np
import pandas as pd
import pytest

from f1si.data.asof import AsOf, History
from f1si.regime.markov import REGIMES, estimate_regime_model, label_regime
from f1si.rng import make_rng


def _empty() -> pd.DataFrame:
    return pd.DataFrame()


def _history(race_states: dict[str, list[str]]) -> History:
    """Build completed lap labels using one control/weather observation per lap."""
    lap_rows: list[dict[str, object]] = []
    status_rows: list[dict[str, object]] = []
    weather_rows: list[dict[str, object]] = []
    for race_id, states in race_states.items():
        for index, state in enumerate(states):
            time_s = float(index + 1)
            lap_rows.append({"race_id": race_id, "lap_number": index + 1, "lap_end_s": time_s})
            code = {"green": "1", "vsc": "6", "sc": "4", "red": "5", "wet": "1"}[state]
            status_rows.append({"race_id": race_id, "seq": index, "t_s": time_s, "status": code})
            weather_rows.append(
                {"race_id": race_id, "seq": index, "t_s": time_s, "rainfall": state == "wet"}
            )
    return History(
        as_of=AsOf("future", 0),
        races=list(race_states),
        entries=_empty(),
        laps=pd.DataFrame(lap_rows),
        track_status=pd.DataFrame(status_rows),
        race_control=_empty(),
        weather=pd.DataFrame(weather_rows),
        lap_cutoffs=_empty(),
        results=_empty(),
    )


@pytest.mark.parametrize(
    ("status", "rainfall", "expected"),
    [
        ("5", True, "red"),
        ("4", True, "sc"),
        ("6", True, "vsc"),
        ("7", True, "vsc"),
        ("2", True, "wet"),
        ("1", False, "green"),
        (None, None, "green"),
    ],
)
def test_cutoff_visible_regime_labels(
    status: str | None, rainfall: bool | None, expected: str
) -> None:
    control = pd.DataFrame([] if status is None else [{"t_s": 10.0, "seq": 0, "status": status}])
    weather = pd.DataFrame(
        [] if rainfall is None else [{"t_s": 10.0, "seq": 0, "rainfall": rainfall}]
    )
    assert label_regime(control, weather, cutoff_s=10.0) == expected


def test_simultaneous_control_events_keep_highest_priority() -> None:
    control = pd.DataFrame(
        [
            {"t_s": 10.0, "seq": 0, "status": "5"},
            {"t_s": 10.0, "seq": 1, "status": "4"},
        ]
    )
    assert label_regime(control, pd.DataFrame(), cutoff_s=10.0) == "red"


def test_cutoff_ignores_future_control_and_weather() -> None:
    control = pd.DataFrame([{"t_s": 11.0, "seq": 0, "status": "5"}])
    weather = pd.DataFrame([{"t_s": 11.0, "seq": 0, "rainfall": True}])
    assert label_regime(control, weather, cutoff_s=10.0) == "green"


def test_transition_counts_do_not_bridge_races_and_apply_dirichlet_one() -> None:
    estimate = estimate_regime_model(_history({"race-a": ["red"], "race-b": ["wet"]}))
    assert estimate.n_transitions == 0
    np.testing.assert_array_equal(estimate.counts, np.zeros((5, 5)))
    np.testing.assert_allclose(estimate.transition, np.full((5, 5), 0.2))


def test_seeded_synthetic_sequence_recovers_known_transition_rows() -> None:
    known = np.array(
        [
            [0.60, 0.10, 0.10, 0.10, 0.10],
            [0.10, 0.60, 0.10, 0.10, 0.10],
            [0.10, 0.10, 0.60, 0.10, 0.10],
            [0.10, 0.10, 0.10, 0.60, 0.10],
            [0.10, 0.10, 0.10, 0.10, 0.60],
        ]
    )
    rng = make_rng(20260802)
    sequence = [0]
    for _ in range(1, 2501):
        sequence.append(int(rng.choice(5, p=known[sequence[-1]])))
    states = [REGIMES[index] for index in sequence]
    estimate = estimate_regime_model(_history({"synthetic": states}))
    assert estimate.n_transitions == len(states) - 1
    # Finite sample of 2,500 transitions; Dirichlet(1) contributes <0.004 per cell.
    np.testing.assert_allclose(estimate.transition, known, atol=0.10)
