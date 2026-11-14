"""Comparison of frozen strategy recommendations with observed pit events."""

from typing import Any, cast

import numpy as np
import pandas as pd


def match_team_stops(
    recommendations: pd.DataFrame,
    stops: pd.DataFrame,
    *,
    visible_events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Pair each observed stop with the latest strictly earlier recommendation."""
    recommendation_columns = {
        "race_id",
        "driver",
        "cutoff_lap",
        "top_action",
        "planned_stop_lap",
    }
    stop_columns = {"race_id", "driver", "in_lap"}
    if not recommendation_columns.issubset(recommendations.columns):
        raise ValueError(
            "recommendations require race_id, driver, cutoff_lap, top_action, and planned_stop_lap"
        )
    if not stop_columns.issubset(stops.columns):
        raise ValueError("stops require race_id, driver, and in_lap")
    if visible_events is not None and not {
        "race_id",
        "driver",
        "in_lap",
        "cutoff_lap",
    }.issubset(visible_events.columns):
        raise ValueError("visible_events require race_id, driver, in_lap, and cutoff_lap")

    recs = recommendations.copy()
    events = stops.drop_duplicates(["race_id", "driver", "in_lap"], keep="first")
    recs["cutoff_lap"] = pd.to_numeric(recs["cutoff_lap"], errors="coerce")
    events["in_lap"] = pd.to_numeric(events["in_lap"], errors="coerce")
    recs = recs.dropna(subset=["race_id", "driver", "cutoff_lap"])
    events = events.dropna(subset=["race_id", "driver", "in_lap"])

    rows: list[dict[str, object]] = []
    for event in events.sort_values(["race_id", "driver", "in_lap"]).itertuples(index=False):
        visible_cutoffs: set[float] = set()
        if visible_events is not None:
            visible = visible_events.loc[
                (visible_events["race_id"] == event.race_id)
                & (visible_events["driver"] == event.driver)
                & (pd.to_numeric(visible_events["in_lap"], errors="coerce") == event.in_lap)
            ]
            visible_cutoffs = set(
                pd.to_numeric(visible["cutoff_lap"], errors="coerce").dropna().astype(float)
            )
        eligible = recs.loc[
            (recs["race_id"] == event.race_id)
            & (recs["driver"] == event.driver)
            & (recs["cutoff_lap"] < event.in_lap)
            & ~recs["cutoff_lap"].isin(visible_cutoffs)
        ]
        if eligible.empty:
            continue
        selected = eligible.sort_values("cutoff_lap", kind="stable").iloc[-1]
        planned = pd.to_numeric(pd.Series([selected["planned_stop_lap"]]), errors="coerce").iloc[0]
        in_lap = float(cast(Any, event.in_lap))
        timing_error = float(planned - in_lap) if pd.notna(planned) else np.nan
        rows.append(
            {
                "race_id": str(event.race_id),
                "driver": str(event.driver),
                "in_lap": int(in_lap),
                "cutoff_lap": int(float(cast(Any, selected["cutoff_lap"]))),
                "top_action": str(selected["top_action"]),
                "planned_stop_lap": int(float(planned)) if pd.notna(planned) else None,
                "action_agrees": str(selected["top_action"]).lower().startswith("pit"),
                "timing_error_laps": timing_error,
                "absolute_timing_error_laps": abs(timing_error),
                "event_visible_at_cutoff": False,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "race_id",
            "driver",
            "in_lap",
            "cutoff_lap",
            "top_action",
            "planned_stop_lap",
            "action_agrees",
            "timing_error_laps",
            "absolute_timing_error_laps",
            "event_visible_at_cutoff",
        ],
    )


def summarize_team_calls(rows: pd.DataFrame, *, rng: np.random.Generator) -> dict[str, object]:
    """Summarize observed team agreement and timing with race-cluster uncertainty."""
    from f1si.backtest.metrics import race_cluster_interval, summarize_by_race

    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be an injected numpy.random.Generator")
    required = {"race_id", "action_agrees", "timing_error_laps"}
    if not required.issubset(rows.columns):
        raise ValueError("team-call rows require race_id, action_agrees, and timing_error_laps")

    frame = rows.copy()
    frame["action_agrees"] = frame["action_agrees"].astype(float)
    frame["absolute_timing_error_laps"] = pd.to_numeric(
        frame["timing_error_laps"], errors="coerce"
    ).abs()

    def summarize(value: str) -> dict[str, object] | None:
        available = frame.loc[frame[value].notna(), ["race_id", value]]
        if available.empty:
            return None
        summary = summarize_by_race(available, value=value)
        interval = race_cluster_interval(available, value=value, rng=rng, n_resamples=2_000)
        return {**summary, "race_cluster_95": interval}

    agreement = summarize("action_agrees")
    signed = summarize("timing_error_laps")
    absolute = summarize("absolute_timing_error_laps")
    race_count = max(
        (
            int(cast(Any, item["race_count"]))
            for item in (agreement, signed, absolute)
            if item is not None
        ),
        default=0,
    )
    return {
        "event_count": len(frame),
        "race_count": race_count,
        "confidence_level": 0.95,
        "resampling_unit": "race",
        "top_action_agreement": agreement,
        "stop_timing_error_laps": {"signed": signed, "absolute": absolute},
        "description": (
            "Descriptive comparison with observed team behavior; no competitive performance "
            "claim is made."
        ),
    }
