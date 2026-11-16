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
from f1si.ui_theme import CHALK, FOG, RECOMMENDATION, TIRE_COLORS, TIRE_LETTERS

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
DRIVER_NAMES = {
    "VER": "Max Verstappen",
    "PER": "Sergio Perez",
    "HAM": "Lewis Hamilton",
    "RUS": "George Russell",
    "LEC": "Charles Leclerc",
    "SAI": "Carlos Sainz",
    "NOR": "Lando Norris",
    "PIA": "Oscar Piastri",
    "ALO": "Fernando Alonso",
    "STR": "Lance Stroll",
    "GAS": "Pierre Gasly",
    "OCO": "Esteban Ocon",
    "TSU": "Yuki Tsunoda",
    "RIC": "Daniel Ricciardo",
    "LAW": "Liam Lawson",
    "ALB": "Alex Albon",
    "SAR": "Logan Sargeant",
    "BOT": "Valtteri Bottas",
    "ZHO": "Zhou Guanyu",
    "HUL": "Nico Hulkenberg",
    "MAG": "Kevin Magnussen",
    "BEA": "Oliver Bearman",
    "COL": "Franco Colapinto",
    "ANT": "Kimi Antonelli",
    "DOO": "Jack Doohan",
    "HAD": "Isack Hadjar",
    "BOR": "Gabriel Bortoleto",
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
    event = str(row.event_name)
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
    driver_name = DRIVER_NAMES.get(code, str(driver_entry.iloc[0].get("full_name") or code).title())
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
            "driver_name": driver_name,
            "team_name": team_name,
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
        "driver_name": driver_name,
        "team_name": team_name,
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


def _metric_html(number: str, verdict: str, meaning: str, *, caution: bool = False) -> str:
    tone = "caution" if caution else "better"
    return (
        '<div class="metric"><div class="metric-number">'
        f'{html.escape(number)}</div><div class="verdict {tone}">{html.escape(verdict)}</div>'
        f'<p class="metric-copy">{html.escape(meaning)}</p></div>'
    )


def _model_report_html(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    podium = metrics["podium_brier"]
    top10 = metrics["top10_brier"]
    coverage = metrics["finish_interval_90"]
    team = metrics["team_strategy_comparison"]
    agreement = team["top_action_agreement"]
    timing = team["stop_timing_error_laps"]["absolute"]
    pooled = coverage["covered"] / coverage["classified_finishers"]
    metric_rows = [
        _metric_html(
            f"{podium['model']['mean']:.3f}",
            "Better than starting order",
            f"Podium Brier: model {podium['model']['mean']:.3f} versus grid baseline "
            f"{podium['baseline']['mean']:.3f}; lower is better.",
        ),
        _metric_html(
            f"{top10['model']['mean']:.3f}",
            "Better than starting order",
            f"Points Brier: model {top10['model']['mean']:.3f} versus grid baseline "
            f"{top10['baseline']['mean']:.3f}; lower is better.",
        ),
        _metric_html(
            f"{coverage['coverage']['mean']:.0%}",
            "Below target",
            f"The 90% finish range covered {pooled:.1%} of classified results "
            f"({coverage['covered']:,} of {coverage['classified_finishers']:,}). "
            "Target: 85% to 95%.",
            caution=True,
        ),
        _metric_html(
            f"{agreement['mean']:.0%}",
            "Needs work",
            f"Top strategy matched observed team calls in {agreement['mean']:.1%} of "
            f"{team['event_count']} stop events.",
            caution=True,
        ),
        _metric_html(
            f"{timing['mean']:.1f} laps",
            "Often several laps apart",
            f"The recommended stop differed from the observed stop by {timing['mean']:.2f} "
            "laps on average.",
            caution=True,
        ),
    ]
    sample = (
        f"Ten races, {metrics['brier_observation_count']:,} driver and cutoff predictions, "
        f"and {team['event_count']} observed stops."
    )
    return (
        '<section class="page-section" id="model-report"><h2>How good is this model?</h2>'
        f'<p class="section-sub">{html.escape(sample)}</p><div class="metrics">'
        f"{''.join(metric_rows)}</div></section>"
    )


def _render_report_summary(report: dict[str, Any]) -> None:
    st.html(_model_report_html(report))


def _apply_styles() -> None:
    css_path = Path(__file__).with_name("dashboard.css")
    st.html(f"<style>{css_path.read_text(encoding='utf-8')}</style>")


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


def _position_interval(value: str, quantiles: tuple[int, ...], field_size: int) -> tuple[int, int]:
    match = re.fullmatch(r"P?(\d+(?:\.\d+)?)(?:-|\u2013)P?(\d+(?:\.\d+)?)", value)
    if match is not None:
        low, high = (round(float(part)) for part in match.groups())
        return max(1, low), min(field_size, high)
    return quantiles[4], quantiles[94]


def _compound_for_action(action: str, fallback: str) -> str:
    match = re.search(r"\(([A-Z]+)\)$", action)
    compound = match.group(1) if match is not None else fallback.upper()
    return compound if compound in TIRE_COLORS else fallback.upper()


def _tie_window(value: object) -> tuple[int, int] | None:
    if isinstance(value, tuple | list) and len(value) == 2:
        return int(value[0]), int(value[1])
    return None


def _option_title(action: str) -> str:
    if action == "wait and decide next lap":
        return "Wait and decide next lap"
    if action == "stay out":
        return "Never stop"
    return _action_copy(action)


def _option_explanation(
    index: int, difference: float, action: str, tied: tuple[int, int] | None
) -> str:
    if action == "wait and decide next lap" and tied is not None:
        return (
            f"Stopping between laps {tied[0]} and {tied[1]} gives a similar result, "
            "so keep the current tires and reassess next lap."
        )
    if index == 0:
        return "This choice gives the strongest balance of expected result and bad-day risk."
    return f"It finishes about {difference:.1f} places behind the recommended choice on average."


def _option_row_html(
    row: tuple[Any, ...],
    quantiles: tuple[int, ...],
    *,
    index: int,
    recommended_mean: float,
    current_compound: str,
    field_size: int,
    tie_window: tuple[int, int] | None,
    team_color: str,
) -> str:
    action = str(row[0])
    mean, spread, bad_day, podium, points = (float(value) for value in row[1:6])
    interval_text = str(row[6])
    low, high = _position_interval(interval_text, quantiles, field_size)
    difference = max(0.0, mean - recommended_mean)
    is_recommended = index == 0
    compound = _compound_for_action(action, current_compound)
    tire_color = TIRE_COLORS.get(compound, FOG)
    tire_letter = TIRE_LETTERS.get(compound, "?")
    title = _option_title(action)
    if is_recommended:
        tag = '<span class="tag tag-rec">Recommended</span>'
    else:
        tag = f'<span class="tag tag-worse">{difference:.1f} places worse</span>'

    def position(rank: float) -> float:
        return (rank - 1) / max(1, field_size - 1) * 100

    row_class = "option-row recommended" if is_recommended else "option-row"
    explanation = _option_explanation(index, difference, action, tie_window)
    table_row = (
        "<tr>"
        f"<td>{html.escape(title)}</td><td>P{mean:.1f}</td><td>{spread:.1f}</td>"
        f"<td>P{bad_day:.1f}</td>"
        f"<td>{podium:.0%}</td><td>{points:.0%}</td><td>P{low} to P{high}</td>"
        "</tr>"
    )
    help_blurbs = (
        "Average across simulated races",
        "Average of the worst 1 in 10 races",
        "Finishes in P1 to P3",
        "Finishes in the top 10",
    )
    labels = ("Expected finish", "Bad-day finish", "Podium chance", "Points chance")
    values = (f"P{mean:.1f}", f"P{bad_day:.1f}", f"{podium:.0%}", f"{points:.0%}")
    stats = "".join(
        f'<div class="stat"><div class="big">{value}</div>'
        f'<div class="stat-label">{label}</div><div class="stat-help">{help_text}</div></div>'
        for value, label, help_text in zip(values, labels, help_blurbs, strict=True)
    )
    return (
        f'<article class="{row_class}" style="--team:{html.escape(team_color)}">'
        f'<div class="tire-chips"><span class="tire-chip" style="--tire:{tire_color}" '
        f'aria-label="{html.escape(TIRE_NAMES.get(compound, compound.title()))} tire">'
        f'{tire_letter}</span></div><div class="option-body">'
        f'<div class="option-title"><h3>{html.escape(title)}</h3>{tag}</div>'
        f'<p class="option-copy">{html.escape(explanation)}</p>'
        f'<div class="stats">{stats}</div>'
        f'<div class="range" role="img" aria-label="Expected P{mean:.1f}; nine in ten results '
        f'between P{low} and P{high}; bad-day average P{bad_day:.1f}">'
        '<div class="range-track"></div>'
        f'<div class="range-zone" style="left:0;width:{position(3):.3f}%"></div>'
        f'<div class="range-band" style="left:{position(low):.3f}%;'
        f'width:{max(0, position(high) - position(low)):.3f}%"></div>'
        f'<div class="range-dot" style="left:{position(mean):.3f}%"></div>'
        f'<div class="range-bad" style="left:{position(bad_day):.3f}%"></div>'
        f'<span class="range-tick" style="left:{position(3):.3f}%">P3</span>'
        f'<span class="range-tick" style="left:{position(10):.3f}%">P10</span>'
        '<span class="range-end">P1</span><span class="range-end right">P20</span></div>'
        f'<p class="range-text">9 in 10 simulated races finish between P{low} and P{high}.</p>'
        '<details><summary>Show all numbers</summary><div class="table-wrap">'
        '<table class="detail-table">'
        "<thead><tr><th>Option</th><th>Expected finish</th><th>Spread</th><th>Bad-day finish</th>"
        "<th>Podium chance</th><th>Points chance</th><th>9-in-10 range</th></tr></thead>"
        f"<tbody>{table_row}</tbody></table></div></details></div></article>"
    )


def _decision_band_html(result: dict[str, Any], options: tuple[tuple[Any, ...], ...]) -> str:
    selected = str(options[0][0])
    color = html.escape(str(result.get("selected_color") or CHALK))
    driver = html.escape(str(result["driver"]))
    driver_name = html.escape(str(result.get("driver_name") or driver))
    team = html.escape(str(result.get("team_name") or "the team"))
    cutoff, total = int(result["cutoff_lap"]), int(result["laps_total"])
    risk = float(result["risk"])
    risk_name = "Aggressive" if risk < 0.34 else "Cautious" if risk > 0.66 else "Balanced"
    tie_window = _tie_window(result.get("waiting_tie_window_laps"))
    if bool(result.get("close_call_two_se")):
        headline = "Too close to call"
    elif selected.startswith("pit now"):
        headline = "Box this lap"
    elif selected.startswith("pit in 1 lap"):
        headline = "Box next lap"
    else:
        headline = "Stay out for now"
    reason = str(result.get("reason") or "Keep running and reassess at the next lap.")
    if selected == "wait and decide next lap" and tie_window is not None:
        reason = (
            f"Stopping between laps {tie_window[0]} and {tie_window[1]} gives a similar result, "
            "so keep the current tires and reassess next lap."
        )
    close = ""
    if result.get("close_call_places") is not None and len(options) > 1:
        close = (
            f'<p class="close-call">Close call: {_action_copy(str(options[1][0]))} is only '
            f"{float(result['close_call_places']):.1f} places worse on average.</p>"
        )
    compound = str(result.get("tire_compound") or "unknown").title()
    tire_rate = result.get("tire_rate")
    tire_sd = result.get("tire_sd")
    tire_value = "Not available" if tire_rate is None else f"{float(tire_rate):.2f} s/lap"
    tire_copy = (
        f"The current {compound} tire is losing about {float(tire_rate):.2f} seconds per lap; "
        f"wear uncertainty is {float(tire_sd):.2f} seconds per lap."
        if tire_rate is not None and tire_sd is not None
        else "There is not enough tire data to estimate pace loss at this lap."
    )
    if tie_window is None:
        window_number, window_copy = (
            "No tied laps",
            "The model finds different results for each available stop choice.",
        )
    else:
        window_number = f"Laps {tie_window[0]} to {tie_window[1]}"
        window_copy = "Stops in this window give a similar expected finish."
    sc = float(result.get("safety_car_probability") or 0.0)
    remaining = max(0, total - cutoff)
    event_chance = 1.0 - (1.0 - sc) ** remaining
    reasons = (
        ("Tyres", tire_value, tire_copy),
        ("Pit window", window_number, window_copy),
        (
            "Safety car",
            f"{sc:.1%} per lap",
            f"Historical rate implies about a {event_chance:.0%} chance of one before the flag.",
        ),
    )
    reason_html = "".join(
        f'<div class="reason"><div class="reason-label">{html.escape(label)}</div>'
        f'<div class="reason-number">{html.escape(number)}</div>'
        f'<p class="reason-copy">{html.escape(copy)}</p></div>'
        for label, number, copy in reasons
    )
    fallback = (
        '<p class="close-call">The tire estimate uses limited data at this lap.</p>'
        if bool(result.get("fallback"))
        else ""
    )
    return (
        f'<div class="decision-band" style="--team:{color}"><div class="decision-inner">'
        f'<p class="context">{html.escape(str(result["race_name"]))} {int(result["race_season"])}, '
        f"after lap {cutoff} of {total}, {risk_name.lower()} risk setting</p>"
        f'<div class="driver-line"><span class="driver-code">{driver}</span>'
        f"{driver_name}, {team}</div><h1>{headline}</h1>"
        f'<p class="lede">{html.escape(reason)}</p>{close}{fallback}'
        f'<div class="reasons">{reason_html}</div></div></div>'
    )


def _glossary_html() -> str:
    glossary = (
        ("Expected finish", "Average finishing position across all simulated races."),
        ("Bad-day finish", "Average finishing position in the worst 1 in 10 simulated races."),
        ("Podium chance", "Share of simulated races ending in P1, P2, or P3."),
        ("Points chance", "Share of simulated races ending in the top 10."),
        ("9-in-10 range", "Nine of every ten simulated races finish inside this interval."),
        ("Pit window", "Laps where a stop gives about the same expected result."),
        ("Close call", "The top two options are within two standard errors in the simulation."),
        ("Risk setting", "Aggressive favors the average; cautious protects the bad-day result."),
    )
    rows = "".join(
        f'<div class="glossary-row"><dt>{html.escape(term)}</dt>'
        f"<dd>{html.escape(definition)}</dd></div>"
        for term, definition in glossary
    )
    return (
        '<section class="page-section" id="glossary"><h2>How to read this page</h2>'
        f'<dl class="glossary">{rows}</dl>'
        '<footer class="site-footer">Unofficial project, not affiliated with Formula 1. '
        "Data: FastF1, OpenF1, and Jolpica.</footer></section>"
    )


def _render_selected(result: dict[str, Any]) -> None:
    if not result.get("available"):
        st.html(
            '<p class="section-sub">This cutoff is unavailable. Choose another lap or race.</p>'
        )
        return
    options = tuple(result.get("options") or ())
    if not result.get("strategy_available") or not options:
        st.html(
            '<p class="section-sub">No strategy is available at this lap. '
            "Choose another cutoff or race.</p>"
        )
        return
    st.html(_decision_band_html(result, options))
    team_color = str(result.get("selected_color") or CHALK)
    current_compound = str(result.get("tire_compound") or "SOFT").upper()
    quantiles = tuple(result.get("option_quantiles") or ())
    option_rows = "".join(
        _option_row_html(
            row,
            tuple(int(value) for value in quantile_row),
            index=index,
            recommended_mean=float(options[0][1]),
            current_compound=current_compound,
            field_size=int(result["n_cars"]),
            tie_window=(
                None
                if _tie_window(result.get("waiting_tie_window_laps")) is None
                else cast(tuple[int, int], _tie_window(result.get("waiting_tie_window_laps")))
            ),
            team_color=team_color,
        )
        for index, (row, quantile_row) in enumerate(zip(options[:4], quantiles[:4], strict=False))
    )
    never_stop = ""
    if not bool(result.get("never_stop_allowed")):
        never_stop = (
            '<article class="option-row"><div></div><div class="option-body">'
            '<div class="option-title"><h3>Never stop</h3>'
            '<span class="tag tag-worse">Not allowed</span></div>'
            '<p class="option-copy">A driver must use two different tire compounds '
            "in a dry race.</p>"
            "</div></article>"
        )
    options_intro = (
        f"Best first. Each option uses {int(result['simulation_count']):,} simulated races."
    )
    st.html(
        '<section class="page-section" id="options"><h2>Your options</h2>'
        f'<p class="section-sub">{options_intro}</p>{option_rows}{never_stop}</section>'
    )

    trace_rows = cast(tuple[dict[str, object], ...], result.get("race_trace_rows") or ())
    trace = build_race_trace_chart(
        trace_rows,
        selected_driver=str(result["driver"]),
        selected_color=team_color,
        cutoff_lap=int(result["cutoff_lap"]),
    )
    driver_name = str(result.get("driver_name") or result["driver"])
    selected_trace = [
        row
        for row in trace_rows
        if str(row.get("driver_code", "")).upper() == str(result["driver"]).upper()
        and bool(row.get("is_latest"))
    ]
    if selected_trace:
        gap = float(cast(Any, selected_trace[-1].get("gap_to_leader_s", 0.0)))
        trace_takeaway = (
            f"{driver_name} is {gap:.1f} seconds from the lead after "
            f"lap {int(result['cutoff_lap'])}."
        )
    else:
        trace_takeaway = "No completed lap times are available for this cutoff."
    stint_rows = cast(tuple[dict[str, object], ...], result.get("stint_rows") or ())
    selected_stints = [
        str(row.get("compound", "")).title()
        for row in stint_rows
        if str(row.get("driver_code", "")).upper() == str(result["driver"]).upper()
    ]
    compounds = ", then ".join(selected_stints) if selected_stints else "no classified tire stints"
    next_compound = str(result.get("recommended_compound") or "").title()
    stint_takeaway = f"{driver_name} has run {compounds}."
    if next_compound:
        stint_takeaway += f" The recommended next set is {next_compound}."
    st.html(
        '<section class="page-section" id="race-so-far"><h2>The race so far</h2>'
        '<div class="charts"><div><h3 class="chart-title">Gap to leader</h3>'
        f'<p class="chart-takeaway">{html.escape(trace_takeaway)}</p></div>'
        '<div><h3 class="chart-title">Stints so far</h3>'
        f'<p class="chart-takeaway">{html.escape(stint_takeaway)}</p></div></div></section>'
    )
    trace_col, stint_col = st.columns(2, gap="large")
    with trace_col:
        if trace is None:
            st.caption("No completed lap times are available for this cutoff.")
        else:
            st.altair_chart(trace, theme="streamlit", width="stretch")
    with stint_col:
        stint_chart = build_stint_chart(
            stint_rows,
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
            selected_color=team_color,
        )
        if stint_chart is None:
            st.caption("No tire stint data is available at this cutoff.")
        else:
            st.altair_chart(stint_chart, theme="streamlit", width="stretch")

    fan_data = result.get("fan_chart_data")
    if isinstance(fan_data, dict):
        fan_data = FanChartData(**fan_data)
    option_quantiles = tuple(result.get("option_quantiles") or ())
    finish_chart = None
    if len(options) == len(option_quantiles):
        dotplot = prepare_quantile_dotplot_data(
            tuple(_dotplot_action_copy(str(row[0])) for row in options[:4]),
            tuple(tuple(row) for row in option_quantiles[:4]),
            mean_finish=float(result["selected_cutoff_mean"]),
            n_cars=int(result["n_cars"]),
            simulation_count=int(result["simulation_count"]),
        )
        finish_chart = build_finish_probability_strip(dotplot, recommended_color=team_color)
    fan_takeaway = "Projected finishing position at the chequered flag."
    if isinstance(fan_data, FanChartData) and fan_data.p50:
        fan_takeaway = (
            f"{driver_name} has a median projected finish of P{fan_data.p50[-1]:.1f} "
            f"at lap {fan_data.laps[-1]}."
        )
    st.html(
        '<section class="page-section" id="certainty"><h2>How sure are we?</h2>'
        '<div class="charts"><div><h3 class="chart-title">Projected finish by lap</h3>'
        f'<p class="chart-takeaway">{html.escape(fan_takeaway)}</p></div>'
        '<div><h3 class="chart-title">Finish chances</h3>'
        '<p class="chart-takeaway">Chance at each finishing position for the ranked options.</p>'
        "</div></div></section>"
    )
    fan_col, finish_col = st.columns(2, gap="large")
    with fan_col:
        if isinstance(fan_data, FanChartData):
            st.altair_chart(
                build_fan_chart(fan_data, team_color=team_color),
                theme="streamlit",
                width="stretch",
            )
        else:
            st.caption("Projected finish is unavailable for this lap.")
    with finish_col:
        if finish_chart is not None:
            st.altair_chart(finish_chart, theme="streamlit", width="stretch")
            st.caption("Shading shows the share of simulated finishes at each position.")
        else:
            st.caption("Finish chances are unavailable for this lap.")


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
        driver_names = {code: DRIVER_NAMES.get(code, code) for code in driver_options}
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
                format_func=lambda code: f"{driver_names[code]} ({code})",
                key="phase6_driver",
            )
        with lap_col:
            cutoff_lap = st.selectbox(
                "After lap",
                cutoff_options,
                key="phase6_cutoff",
                format_func=lambda lap: f"{lap} of {laps_total}",
            )
        if not isinstance(st.session_state.get("phase6_risk"), int | float):
            st.session_state["phase6_risk"] = 0.5
        with risk_col:
            risk = st.slider(
                "Risk setting",
                min_value=0.0,
                max_value=1.0,
                step=0.05,
                key="phase6_risk",
            )
            current_risk = (
                "aggressive" if risk < 0.34 else "cautious" if risk > 0.66 else "balanced"
            )
            risk_labels = "".join(
                f'<span class="{"current" if label.lower() == current_risk else ""}">{label}</span>'
                for label in ("Aggressive", "Balanced", "Cautious")
            )
            st.html(f'<div class="risk-labels">{risk_labels}</div>')
    return str(race_id), str(driver), int(cutoff_lap), float(risk)


def main() -> None:
    st.set_page_config(page_title="F1 strategy replay", layout="wide")
    _apply_styles()

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
        st.html(_model_report_html(_report_summary()))
        st.html(_glossary_html())
    except Exception:
        st.caption("The ten-race model report is unavailable.")


if __name__ == "__main__":
    main()
