"""Read-only single-page race replay view."""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

import pandas as pd
import streamlit as st

import f1si.backtest.walk_forward as walk_forward
from f1si import cli, paths
from f1si.data import asof
from f1si.plots.altair_charts import (
    build_fan_chart,
    build_finish_probability_strip,
    build_race_trace_chart,
    build_stint_chart,
)
from f1si.plots.replay_charts import (
    fastf1_team_color_map,
    prepare_race_trace_data,
    prepare_stint_bar_data,
    snapshot_driver_order,
)
from f1si.plots.simulate import FanChartData, prepare_fan_chart_data, prepare_quantile_dotplot_data
from f1si.ui_theme import (
    ASPHALT,
    CHALK,
    FOG,
    PITWALL,
    RECOMMENDATION,
    TIRE_COLORS,
    TIRE_LETTERS,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "reports" / "backtest" / "phase-06.json"
SIMULATIONS = 10_000
SEED = 0
EMPTY_BODY = (
    "No eligible races are available because their scheduled lap counts are missing. "
    "Refresh the race cache, then choose a supported event."
)
UNAVAILABLE_SCHEDULE_COPY = (
    "This race cannot be replayed because its scheduled lap count is missing. "
    "Refresh the race cache or choose another race."
)
ERROR_COPY = (
    "Replay could not be built for this selection. Check the local cache and eligible cutoffs, "
    "then retry or choose another race."
)
LOADING_COPY = "Building replay..."
TIRE_NAMES = {
    "SOFT": "Soft",
    "MEDIUM": "Medium",
    "HARD": "Hard",
    "INTERMEDIATE": "Intermediate",
    "WET": "Full wet",
}


def _data_file() -> Path:
    """Resolve the configured local cache without creating or modifying it."""
    configured = paths.db_path(paths.data_dir())
    return configured if configured.is_absolute() else PROJECT_ROOT / configured


def _model_identity(data_path: Path) -> str:
    """Use immutable cache metadata plus all package source in the replay cache identity."""
    stat = data_path.stat()
    digest = hashlib.sha256()
    package_root = PROJECT_ROOT / "src" / "f1si"
    for source in sorted(package_root.rglob("*.py")):
        relative = source.relative_to(PROJECT_ROOT).as_posix()
        digest.update(relative.encode())
        digest.update(source.read_bytes())
    return f"{stat.st_size}:{stat.st_mtime_ns}:{digest.hexdigest()}"


@st.cache_data(show_spinner=False, max_entries=4)
def _eligible_catalog(data_path: Path) -> pd.DataFrame:
    """List only complete in-sample races with a verified race-start horizon."""
    catalog = asof.catalog(data_path)
    catalog = catalog.loc[
        catalog["season"].between(2023, 2025)
        & catalog["load_status"].eq("complete")
        & ~catalog["out_of_sample"].astype(bool)
    ].copy()
    if catalog.empty:
        return catalog

    race_ids = catalog["race_id"].astype(str).tolist()
    accessor = cli._make_asof_accessor(data_path)

    def has_verified_horizon(race_id: str) -> bool:
        try:
            first_snapshot = accessor.snapshot(asof.AsOf(race_id, 0))
            walk_forward._race_laps_total(accessor, race_id, first_snapshot)
        except ValueError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=min(4, len(race_ids))) as workers:
        scheduled = {
            race_id
            for race_id, has_horizon in zip(
                race_ids, workers.map(has_verified_horizon, race_ids), strict=True
            )
            if has_horizon
        }
    return catalog.loc[catalog["race_id"].astype(str).isin(scheduled)].copy()


def _race_label(row: Any) -> str:
    event = str(row.event_name).replace("Grand Prix", "GP")
    return f"{event} {int(row.season)}"


def _action_copy(action: str, *, include_compound: bool = True) -> str:
    """Turn optimizer labels into short strategist language."""
    if action == "stay out":
        return "Stay out"
    if action == "wait and decide next lap":
        return "Wait and decide next lap"
    compound_match = re.search(r"\(([A-Z]+)\)$", action)
    compound = compound_match.group(1) if compound_match is not None else ""
    suffix = (
        f" ({TIRE_NAMES.get(compound, compound.title())})" if include_compound and compound else ""
    )
    if action.startswith("pit now"):
        return f"Box this lap{suffix}"
    delayed = re.match(r"pit in (\d+) lap(?:\(s\)|s?)", action)
    if delayed is not None:
        laps = int(delayed.group(1))
        unit = "lap" if laps == 1 else "laps"
        return f"Box in {laps} {unit}{suffix}"
    return action.capitalize()


def _action_heading(count: int) -> str:
    if count == 0:
        return "No strategy options available"
    return "Strategy options"


def _safe_replay_result(builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Return a fresh error state without carrying a previous selection's output."""
    try:
        return {"status": "ready", "value": builder()}
    except Exception:
        return {"status": "error", "value": None}


def _render_replay_failure() -> None:
    st.error(ERROR_COPY)


def _schedule_failure_copy(error: ValueError) -> str:
    if str(error).startswith("Scheduled race distance is unavailable"):
        return UNAVAILABLE_SCHEDULE_COPY
    return ERROR_COPY


def _render_replay_outcome(outcome: dict[str, Any]) -> None:
    if outcome.get("status") != "ready" or outcome.get("value") is None:
        _render_replay_failure()
        return
    _render_selected(cast(dict[str, Any], outcome["value"]))


def _risk_value_label(risk: float) -> str:
    return f"Risk aversion {risk:.2f}"


def _strategist_reason(
    action: str,
    *,
    current_compound: str | None,
    tire_age: int,
    laps_done: int,
    laps_total: int,
    pit_loss_s: float,
    next_stop_lap: int | None,
    target_compound: str | None,
    wear_rates: dict[str, float | None],
) -> str:
    """Explain the recommendation using tire pace and the cost of a stop."""
    old = (current_compound or "").upper()
    new = (target_compound or "").upper()
    shown_action = _action_copy(action, include_compound=False)
    if next_stop_lap is None or not old or not new:
        if old:
            return (
                f"{shown_action}: the current {old.title()} set remains the better call "
                "for the laps left."
            )
        return f"{shown_action}: keep the current tires for the laps left."

    old_rate, new_rate = wear_rates.get(old), wear_rates.get(new)
    if old_rate is not None and new_rate is not None:
        remaining = max(0, laps_total - laps_done)
        before_stop = max(0, min(remaining, next_stop_lap - laps_done))
        after_stop = max(0, laps_total - next_stop_lap)
        no_stop_wear = float(old_rate) * (remaining * (2 * tire_age + remaining + 1) / 2)
        planned_wear = float(old_rate) * (before_stop * (2 * tire_age + before_stop + 1) / 2)
        planned_wear += float(new_rate) * after_stop * (after_stop + 1) / 2
        pace_gain = no_stop_wear - planned_wear
        if pace_gain > pit_loss_s:
            return (
                f"{shown_action}: fresh {new.title()} should make back the stop loss as the "
                f"{old.title()} loses pace."
            )

    return (
        f"{shown_action}: the {old.title()} still has useful pace, so use it through the "
        f"in-lap before switching to fresh {new.title()} for the final stint."
    )


@st.cache_data(show_spinner=False, max_entries=64)
def _build_selected_replay(
    race_id: str,
    driver: str,
    cutoff_lap: int,
    risk: float,
    n_simulations: int,
    seed: int,
    data_path: str,
    model_identity: str,
) -> dict[str, Any]:
    """Build chart and strategy data through the shared cutoff-only replay path."""
    del model_identity
    db = Path(data_path)
    accessor = cli._make_asof_accessor(db)
    first = accessor.snapshot(asof.AsOf(race_id, 0))
    laps_total = walk_forward._race_laps_total(accessor, race_id, first)
    if not 0 <= cutoff_lap < laps_total - 1:
        raise ValueError("Choose a cutoff before the final lap.")
    snapshot = first if cutoff_lap == 0 else accessor.snapshot(asof.AsOf(race_id, cutoff_lap))
    available_drivers = {str(code).upper() for code in snapshot.entries["driver_code"]}
    code = driver.upper()
    if code not in available_drivers:
        raise ValueError(f"Unknown driver {code!r} at cutoff {cutoff_lap}.")

    trace_rows = prepare_race_trace_data(snapshot)
    stint_rows = prepare_stint_bar_data(snapshot)
    team_names = tuple(dict.fromkeys(snapshot.entries["team_name"].astype(str)))
    team_colors = fastf1_team_color_map(int(snapshot.race.season), team_names)
    driver_entry = snapshot.entries.loc[
        snapshot.entries["driver_code"].astype(str).str.upper().eq(code)
    ]
    team_name = str(driver_entry.iloc[0]["team_name"])
    selected_color = team_colors.get(team_name, CHALK)
    driver_order = snapshot_driver_order(snapshot)

    context = cli._prepare_replay_context(
        accessor, race_id, laps_total, cutoff_lap, snapshot=snapshot
    )
    cutoff = cli._replay_at_cutoff(
        accessor,
        race_id,
        laps_total,
        code,
        cutoff_lap,
        n_simulations,
        risk,
        seed,
        prepared_context=context,
        retain_position_history=True,
    )
    if cutoff.analysis is None:
        car = context.state.car(code)
        return {
            "available": True,
            "strategy_available": False,
            "reason": cutoff.unavailable_reason,
            "race_name": snapshot.race.event_name,
            "race_season": int(snapshot.race.season),
            "laps_total": laps_total,
            "driver": code,
            "cutoff_lap": cutoff_lap,
            "risk": risk,
            "options": (),
            "option_columns": (),
            "option_quantiles": (),
            "selected_cutoff_mean": None,
            "simulation_count": n_simulations,
            "fan_chart_data": None,
            "n_cars": len(context.state.cars),
            "safety_car_probability": context.estimate.rate_per_lap,
            "tire_rate": car.wear_rate_s_per_lap,
            "tire_sd": car.wear_sd,
            "tire_compound": car.compound,
            "tire_source": car.wear_source,
            "fallback": context.is_fallback,
            "race_trace_rows": trace_rows,
            "stint_rows": stint_rows,
            "team_colors": team_colors,
            "selected_color": selected_color,
            "driver_order": driver_order,
        }

    analysis = cutoff.analysis
    selected = analysis.best
    policy_history = cutoff.analysis.recommended_position_history
    fan_chart_data = (
        None
        if policy_history is None
        else prepare_fan_chart_data(
            policy_history,
            first_lap=cutoff_lap + 1,
            n_cars=len(context.state.cars),
        )
    )
    car = context.state.car(code)
    option_columns = (
        "Action",
        "Mean finish",
        "Spread",
        "Worst 10% average finish",
        "Podium chance",
        "Top-10 chance",
        "90% finish interval",
    )
    options = tuple(
        (
            item.action,
            item.mean_finish,
            item.spread,
            item.cvar10,
            item.podium_probability,
            item.top10_probability,
            f"P{item.finish_p05}-P{item.finish_p95}",
        )
        for item in analysis.options
    )
    wear_rate_method = getattr(context.model, "wear_rate", None)
    wear_rates = {
        compound: (
            cast(Callable[[str], float | None], wear_rate_method)(compound)
            if callable(wear_rate_method)
            else None
        )
        for compound in context.compounds
    }
    return {
        "available": True,
        "strategy_available": True,
        "race_name": snapshot.race.event_name,
        "race_season": int(snapshot.race.season),
        "laps_total": laps_total,
        "driver": code,
        "cutoff_lap": cutoff_lap,
        "risk": risk,
        "option_columns": option_columns,
        "options": options,
        "option_quantiles": tuple(item.finish_quantiles for item in analysis.options),
        "selected_cutoff_mean": selected.mean_finish,
        "simulation_count": n_simulations,
        "close_call_places": analysis.close_call_places,
        "close_call_two_se": analysis.close_call_two_se,
        "waiting_tie_window_laps": analysis.waiting_tie_window_laps,
        "never_stop_allowed": analysis.never_stop_allowed,
        "fan_chart_data": fan_chart_data,
        "reason": _strategist_reason(
            selected.action,
            current_compound=car.compound,
            tire_age=car.tire_age,
            laps_done=context.state.laps_done_of(car),
            laps_total=laps_total,
            pit_loss_s=float(context.state.pit_loss_s["green"]),
            next_stop_lap=(selected.plan.stop_laps[0] if selected.plan.stop_laps else None),
            target_compound=(selected.plan.compounds[0] if selected.plan.compounds else None),
            wear_rates=wear_rates,
        ),
        "n_cars": len(context.state.cars),
        "safety_car_probability": context.estimate.rate_per_lap,
        "tire_rate": car.wear_rate_s_per_lap,
        "tire_sd": car.wear_sd,
        "tire_compound": car.compound,
        "tire_source": car.wear_source,
        "fallback": cutoff.is_fallback,
        "race_trace_rows": trace_rows,
        "stint_rows": stint_rows,
        "team_colors": team_colors,
        "selected_color": selected_color,
        "recommended_stop_lap": (selected.plan.stop_laps[0] if selected.plan.stop_laps else None),
        "recommended_compound": (selected.plan.compounds[0] if selected.plan.compounds else None),
        "driver_order": driver_order,
    }


def _report_summary() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(REPORT_PATH.read_text(encoding="utf-8")))


def _report_display_values(report: dict[str, Any]) -> dict[str, str]:
    metrics = report["metrics"]
    podium = metrics["podium_brier"]
    top10 = metrics["top10_brier"]
    coverage = metrics["finish_interval_90"]
    team = metrics["team_strategy_comparison"]
    agreement = team["top_action_agreement"]
    timing = team["stop_timing_error_laps"]["absolute"]
    agreement_interval = agreement["race_cluster_95"]
    timing_interval = timing["race_cluster_95"]
    pooled = coverage["covered"] / coverage["classified_finishers"]
    return {
        "podium": (
            f"Model {podium['model']['mean']:.3f} vs grid baseline "
            f"{podium['baseline']['mean']:.3f} (lower is better)"
        ),
        "top10": (
            f"Model {top10['model']['mean']:.3f} vs grid baseline "
            f"{top10['baseline']['mean']:.3f} (lower is better)"
        ),
        "coverage": (
            f"{coverage['coverage']['mean']:.0%} race average; "
            f"{pooled:.1%} across all finishes ({coverage['covered']:,} of "
            f"{coverage['classified_finishers']:,} finishes inside the range). "
            "Target: 85% to 95%."
        ),
        "team_agreement": (
            f"{agreement['mean']:.1%} (95% confidence range: "
            f"{agreement_interval['low']:.1%} to {agreement_interval['high']:.1%})"
        ),
        "team_timing": (
            f"{timing['mean']:.2f} laps (95% confidence range: "
            f"{timing_interval['low']:.2f} to {timing_interval['high']:.2f})"
        ),
        "sample": (
            f"{len(report['race_ids'])} races; "
            f"{metrics['brier_observation_count']:,} driver and cutoff predictions; "
            f"{team['event_count']} observed stops"
        ),
    }


def _render_report_summary(report: dict[str, Any]) -> None:
    display = _report_display_values(report)
    st.subheader("Ten-race evaluation")
    st.table(
        pd.DataFrame(
            [
                ("Podium Brier score", display["podium"]),
                ("Top-10 Brier score", display["top10"]),
                ("90% finish coverage", display["coverage"]),
                ("Team top-action agreement", display["team_agreement"]),
                ("Observed stop-timing error", display["team_timing"]),
                ("Sample", display["sample"]),
            ],
            columns=("Measure", "Result"),
        )
    )


def _apply_styles() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{ background: {ASPHALT}; color: {CHALK}; }}
        .stApp .block-container {{ max-width: 1440px; padding-top: 28px; padding-bottom: 48px; }}
        .stApp p, .stApp li {{ color: {CHALK}; font-size: 16px; line-height: 1.5; }}
        .stApp h1 {{ color: {CHALK}; font-size: 28px; font-weight: 600; line-height: 1.2; }}
        .stApp h2, .stApp h3 {{
            color: {CHALK}; font-size: 20px; font-weight: 600; line-height: 1.2;
        }}
        .stApp [data-testid="stCaptionContainer"] {{
            color: {FOG}; font-size: 14px; line-height: 1.45;
            font-variant-numeric: tabular-nums; font-feature-settings: "tnum";
        }}
        .stApp, .stApp * {{ font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; }}
        .stApp .recommended-action {{
            color: {RECOMMENDATION}; font-size: 28px;
            font-weight: 600; line-height: 1.2;
        }}
        .stApp .compound-letter {{ font-weight: 600; }}
        .stApp [data-testid="stTable"] {{ border-color: {ASPHALT}; }}
        .stApp [data-testid="stTable"] th, .stApp [data-testid="stTable"] td {{
            border-color: {ASPHALT} !important; color: {CHALK};
            white-space: normal; overflow-wrap: anywhere;
        }}
        .stApp [data-testid="stTable"] td {{ font-variant-numeric: tabular-nums; }}
        .stApp [data-testid="stWidgetLabel"] p {{
            color: {CHALK}; font-size: 14px; font-weight: 500;
        }}
        .stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div {{
            min-height: 44px; background: {PITWALL}; border-color: {ASPHALT}; color: {CHALK};
        }}
        .stApp [data-testid="stSlider"] {{ min-height: 44px; }}
        .stApp [data-testid="stDataFrame"] {{ border-color: {ASPHALT}; }}
        .stApp [data-testid="stDataFrame"] * {{ font-variant-numeric: tabular-nums; }}
        .stApp table.strategy-options {{
            width: 100%; border-collapse: collapse; table-layout: fixed;
            font-size: 13px; font-variant-numeric: tabular-nums;
        }}
        .stApp table.strategy-options th, .stApp table.strategy-options td {{
            border: 0; padding: 7px 6px; text-align: left; vertical-align: top;
            color: {CHALK}; overflow-wrap: anywhere;
        }}
        .stApp table.strategy-options th {{ color: {FOG}; font-weight: 500; }}
        .stApp table.strategy-options .mobile-results,
        .stApp table.strategy-options .mobile-action {{ display: none; }}
        .stApp table.strategy-options th:nth-child(1),
        .stApp table.strategy-options td:nth-child(1) {{
            width: 24%; white-space: nowrap; overflow-wrap: normal;
        }}
        .stApp table.strategy-options th:nth-child(2),
        .stApp table.strategy-options td:nth-child(2) {{ width: 10%; }}
        .stApp table.strategy-options th:nth-child(3),
        .stApp table.strategy-options td:nth-child(3) {{ width: 9%; }}
        .stApp table.strategy-options th:nth-child(4),
        .stApp table.strategy-options td:nth-child(4) {{ width: 18%; }}
        .stApp table.strategy-options th:nth-child(5),
        .stApp table.strategy-options td:nth-child(5) {{ width: 12%; }}
        .stApp table.strategy-options th:nth-child(6),
        .stApp table.strategy-options td:nth-child(6) {{ width: 12%; }}
        .stApp table.strategy-options th:nth-child(7),
        .stApp table.strategy-options td:nth-child(7) {{ width: 15%; }}
        .stApp .vega-embed .vega-actions {{ display: none !important; }}
        .stApp [data-testid="stHeaderActionElements"] {{ display: none !important; }}
        .stApp [data-testid="stMarkdownContainer"]:focus-visible,
        .stApp button:focus-visible,
        .stApp input:focus-visible,
        .stApp [role="combobox"]:focus-visible {{
            outline: 2px solid {CHALK}; outline-offset: 2px;
        }}
        .stApp .vega-embed text {{
            font-family: "IBM Plex Sans", sans-serif;
            font-variant-numeric: tabular-nums; font-feature-settings: "tnum";
        }}
        .st-key-replay-controls [data-testid="stHorizontalBlock"] {{ gap: 16px; }}
        @media (max-width: 760px) {{
            .stApp .block-container {{ padding: 18px 14px 32px; }}
            .stApp table.strategy-options {{ table-layout: fixed; font-size: 13px; }}
            .stApp table.strategy-options th:nth-child(n+2):nth-child(-n+7),
            .stApp table.strategy-options td:nth-child(n+2):nth-child(-n+7) {{ display: none; }}
            .stApp table.strategy-options .mobile-results {{ display: table-cell; }}
            .stApp table.strategy-options .desktop-action {{ display: none; }}
            .stApp table.strategy-options .mobile-action {{ display: inline; }}
            .stApp table.strategy-options th:nth-child(1),
            .stApp table.strategy-options td:nth-child(1) {{ width: 42%; }}
            .stApp table.strategy-options th:nth-child(8),
            .stApp table.strategy-options td:nth-child(8) {{ width: 58%; }}
            .stApp table.strategy-options td:nth-child(1) {{
                white-space: normal; overflow-wrap: break-word;
            }}
            .st-key-replay-controls [data-testid="stHorizontalBlock"] {{
                flex-wrap: wrap; gap: 12px;
            }}
            .st-key-replay-controls [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
                flex: 1 1 calc(50% - 12px) !important; min-width: calc(50% - 12px) !important;
            }}
            .stApp .recommended-action {{ font-size: 24px; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _format_strategy_table(
    option_columns: tuple[str, ...],
    options: tuple[tuple[Any, ...], ...],
) -> pd.DataFrame:
    formatted: list[dict[str, str]] = []
    numeric_one_decimal = {"Mean finish", "Spread", "Worst 10% average finish"}
    percentages = {"Podium chance", "Top-10 chance"}
    for row in options:
        result: dict[str, str] = {}
        for column, value in zip(option_columns, row, strict=True):
            if column == "Action":
                result[column] = _action_copy(str(value))
            elif column in numeric_one_decimal:
                result[column] = f"{float(value):.1f}"
            elif column in percentages:
                result[column] = f"{float(value):.0%}"
            else:
                result[column] = str(value)
        formatted.append(result)
    return pd.DataFrame(formatted, columns=option_columns)


def _dotplot_action_copy(action: str) -> str:
    """Shorten direct chart labels while preserving the stop timing and tire compound."""
    if action == "stay out":
        return "Stay out"
    compound_match = re.search(r"\(([A-Z]+)\)$", action)
    compound = compound_match.group(1)[0] if compound_match is not None else ""
    compound_suffix = f" {compound}" if compound else ""
    if action.startswith("pit now"):
        return f"Box now{compound_suffix}"
    delayed = re.match(r"pit in (\d+) lap(?:\(s\)|s?)", action)
    if delayed is not None:
        return f"Box +{delayed.group(1)} lap{compound_suffix}"
    return _action_copy(action, include_compound=False)


def _strategy_table_html(table: pd.DataFrame) -> str:
    """Render a compact semantic table with a focused mobile column set."""
    headings = "".join(
        f'<th scope="col">{html.escape(str(column))}</th>' for column in table.columns
    )
    headings += '<th class="mobile-results" scope="col">Results</th>'
    body_rows: list[str] = []
    for index, row in enumerate(table.itertuples(index=False, name=None)):
        cells: list[str] = []
        for column, value in zip(table.columns, row, strict=True):
            recommended = index == 0 and column == "Action"
            style = f' style="color:{RECOMMENDATION};font-weight:600"' if recommended else ""
            if column == "Action":
                mobile_value = f"Recommended: {value}" if index == 0 else str(value)
                value_html = (
                    f'<span class="desktop-action">{html.escape(str(value))}</span>'
                    f'<span class="mobile-action">{html.escape(mobile_value)}</span>'
                )
            else:
                value_html = html.escape(str(value))
            cells.append(f"<td{style}>{value_html}</td>")
        values = dict(zip(table.columns, row, strict=True))
        mobile_result = (
            f"Mean P{values['Mean finish']}. Spread {values['Spread']}. "
            f"Worst 10% P{values['Worst 10% average finish']}. "
            f"Podium {values['Podium chance']}. Top 10% {values['Top-10 chance']}. "
            f"Range {values['90% finish interval']}."
        )
        cells.append(f'<td class="mobile-results">{html.escape(mobile_result)}</td>')
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<table class="strategy-options"><thead><tr>'
        f"{headings}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _render_selected(result: dict[str, Any]) -> None:
    if not result.get("available"):
        st.write("Unavailable at this cutoff. Choose another lap or race.")
        return

    st.subheader("Recommended strategy")
    options = tuple(result.get("options") or ())
    if not result.get("strategy_available") or not options:
        st.write(
            "No strategy options are available at this lap. Choose a later lap or another race."
        )
        return

    action = _action_copy(str(options[0][0]), include_compound=False)
    st.markdown(
        f'<p class="recommended-action">{html.escape(action)}</p>',
        unsafe_allow_html=True,
    )
    st.write(str(result["reason"]))
    if result.get("close_call_places") is not None:
        runner_up = _action_copy(str(options[1][0]))
        places = float(result["close_call_places"])
        st.caption(
            f"Close call: {runner_up} is only {places:.1f} places worse on average "
            "(less than two standard errors apart)."
        )
    tie_window = result.get("waiting_tie_window_laps")
    if tie_window is not None:
        start_lap, end_lap = tie_window
        st.caption(f"Waiting ties from lap {start_lap} through lap {end_lap}.")
    st.caption(
        f"{result['race_name']} {result['race_season']}. Driver {result['driver']}. "
        f"After lap {result['cutoff_lap']} of {result['laps_total']}. "
        f"Risk aversion {result['risk']:.2f}."
    )
    if bool(result.get("fallback")):
        st.caption("Uncalibrated. The model uses only the laps available at this point.")

    trace_col, stint_col = st.columns((1.1, 1.0), gap="large")
    with trace_col:
        st.subheader("Gap to leader")
        trace = build_race_trace_chart(
            cast(tuple[dict[str, object], ...], result.get("race_trace_rows") or ()),
            selected_driver=str(result["driver"]),
            selected_color=str(result.get("selected_color") or CHALK),
            cutoff_lap=int(result["cutoff_lap"]),
        )
        if trace is None:
            st.caption("No completed laps are visible at this cutoff.")
        else:
            st.altair_chart(trace, theme="streamlit", width="stretch")
        st.caption(
            "Selected driver is in team color. Other drivers are grey; teammates are dashed."
        )

    with stint_col:
        st.subheader("Stints so far")
        stint_chart = build_stint_chart(
            cast(tuple[dict[str, object], ...], result.get("stint_rows") or ()),
            cutoff_lap=int(result["cutoff_lap"]),
            laps_total=int(result["laps_total"]),
            driver_order=cast(tuple[str, ...], result.get("driver_order") or ()),
            selected_driver=str(result["driver"]),
            recommended_stop_lap=(
                None
                if result.get("recommended_stop_lap") is None
                else int(result["recommended_stop_lap"])
            ),
            recommended_compound=(
                None
                if result.get("recommended_compound") is None
                else str(result["recommended_compound"])
            ),
        )
        if stint_chart is None:
            st.caption("No tire stints are visible at this cutoff.")
        else:
            st.altair_chart(stint_chart, theme="streamlit", width="stretch")
        st.caption(
            "Letters show the tire compound. A purple outline marks the recommended next stint."
        )

    dotplot_col, fan_col = st.columns((1.1, 1.0), gap="large")
    with dotplot_col:
        st.subheader("Finish distribution by option")
        option_quantiles = tuple(result.get("option_quantiles") or ())
        if len(options) == len(option_quantiles):
            dotplot = prepare_quantile_dotplot_data(
                tuple(_dotplot_action_copy(str(row[0])) for row in options),
                option_quantiles,
                mean_finish=float(result["selected_cutoff_mean"]),
                n_cars=int(result["n_cars"]),
                simulation_count=int(result["simulation_count"]),
            )
            chart = build_finish_probability_strip(dotplot)
            st.altair_chart(chart, theme="streamlit", width="stretch")
            st.caption("Each cell shows the share of simulated finishes in that position.")
        else:
            st.caption("Finish distribution is unavailable for this lap.")

    with fan_col:
        st.subheader("Projected finish by lap")
        fan_data = result.get("fan_chart_data")
        if isinstance(fan_data, dict):
            fan_data = FanChartData(**fan_data)
        if isinstance(fan_data, FanChartData):
            st.altair_chart(
                build_fan_chart(fan_data),
                theme="streamlit",
                width="stretch",
            )
            st.caption(fan_data.caption)
        else:
            st.caption("Projected finish is unavailable for this lap.")

    st.subheader("Safety car and tire")
    safety_car = float(result["safety_car_probability"])
    st.write(
        f"Safety-car chance: {safety_car:.1%} per lap, based on historical data at this circuit."
    )
    compound = str(result.get("tire_compound") or "").upper()
    if compound in TIRE_COLORS:
        letter = TIRE_LETTERS[compound]
        name = TIRE_NAMES[compound]
        color = TIRE_COLORS[compound]
        st.markdown(
            f'<p><span class="compound-letter" style="color:{color}">{letter}</span> '
            f"{name} tire</p>",
            unsafe_allow_html=True,
        )
    tire_rate = result.get("tire_rate")
    tire_sd = result.get("tire_sd")
    if tire_rate is None or tire_sd is None:
        st.write("Tire wear uncertainty is unavailable at this lap.")
    else:
        st.write(
            f"Wear estimate {float(tire_rate):.3f} seconds per lap; "
            f"uncertainty plus or minus {float(tire_sd):.3f} seconds per lap."
        )
        if bool(result.get("fallback")) or result.get("tire_source") != "filter":
            st.caption("Uncalibrated tire estimate from limited data at this lap.")

    st.subheader(_action_heading(len(options)))
    table = _format_strategy_table(tuple(result["option_columns"]), options)
    st.markdown(_strategy_table_html(table), unsafe_allow_html=True)
    if not bool(result.get("never_stop_allowed")):
        st.caption("Never stop is not allowed under the two-compound rule.")
    st.caption(f"Each option uses {int(result['simulation_count']):,} simulated races.")


def _render_controls(catalog: pd.DataFrame, data_path: Path) -> tuple[str, str, int, float]:
    rows = list(catalog.itertuples(index=False))
    race_ids = [str(row.race_id) for row in rows]
    labels = {str(row.race_id): _race_label(row) for row in rows}
    default_race = "2023-01" if "2023-01" in race_ids else race_ids[0]
    if st.session_state.get("phase6_race") not in race_ids:
        st.session_state["phase6_race"] = default_race

    with st.container(key="replay-controls"):
        race_col, driver_col, lap_col, risk_col = st.columns(4, gap="medium")
        with race_col:
            race_id = st.selectbox(
                "Race",
                race_ids,
                format_func=labels.__getitem__,
                key="phase6_race",
            )

        accessor = cli._make_asof_accessor(data_path)
        first = accessor.snapshot(asof.AsOf(str(race_id), 0))
        laps_total = walk_forward._race_laps_total(accessor, str(race_id), first)
        cutoff_options = list(range(max(0, laps_total - 1)))
        driver_options = sorted({str(code).upper() for code in first.entries["driver_code"]})
        if not driver_options or not cutoff_options:
            raise ValueError("The selected race has no usable drivers or laps.")

        default_driver = "ALO" if "ALO" in driver_options else driver_options[0]
        if st.session_state.get("phase6_driver") not in driver_options:
            st.session_state["phase6_driver"] = default_driver
        if st.session_state.get("phase6_cutoff") not in cutoff_options:
            st.session_state["phase6_cutoff"] = 15 if 15 in cutoff_options else cutoff_options[0]

        with driver_col:
            driver = st.selectbox(
                "Driver",
                driver_options,
                key="phase6_driver",
            )
        with lap_col:
            cutoff_lap = st.selectbox(
                "After lap",
                cutoff_options,
                key="phase6_cutoff",
                format_func=lambda lap: str(lap),
            )
        if not isinstance(st.session_state.get("phase6_risk"), int | float):
            st.session_state["phase6_risk"] = 0.5
        with risk_col:
            risk = st.slider(
                "Risk aversion",
                min_value=0.0,
                max_value=1.0,
                step=0.05,
                key="phase6_risk",
            )
            st.caption("0.0 mean-focused. 1.0 tail-risk-focused.")
    return str(race_id), str(driver), int(cutoff_lap), float(risk)


def main() -> None:
    st.set_page_config(page_title="F1 strategy replay", layout="wide")
    _apply_styles()
    st.title("F1 strategy replay")
    st.caption("Read-only race strategy replay using information available at each lap.")

    data_path = _data_file()
    try:
        catalog = _eligible_catalog(data_path) if data_path.is_file() else None
    except Exception:
        catalog = None
    if catalog is None or catalog.empty:
        st.write(EMPTY_BODY)
        return

    try:
        race_id, driver, cutoff_lap, risk = _render_controls(catalog, data_path)
        identity = _model_identity(data_path)
        with st.spinner(LOADING_COPY):
            outcome = _safe_replay_result(
                lambda: _build_selected_replay(
                    race_id,
                    driver,
                    cutoff_lap,
                    risk,
                    SIMULATIONS,
                    SEED,
                    str(data_path),
                    identity,
                )
            )
        _render_replay_outcome(outcome)
    except ValueError as err:
        st.write(_schedule_failure_copy(err))
    except Exception:
        _render_replay_failure()

    try:
        _render_report_summary(_report_summary())
    except Exception:
        st.caption("The ten-race evaluation report is unavailable.")
    st.caption(
        "Unofficial project. Not affiliated with Formula 1. Data: FastF1, OpenF1, and Jolpica."
    )


if __name__ == "__main__":
    main()
