"""Read-only single-page race replay view."""

from __future__ import annotations

import hashlib
import html
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

import pandas as pd
import streamlit as st

import f1si.backtest.walk_forward as walk_forward
from f1si import cli, paths
from f1si.data import asof
from f1si.plots.simulate import (
    FanChartData,
    build_fan_chart,
    build_quantile_dotplot,
    prepare_fan_chart_data,
    prepare_quantile_dotplot_data,
)
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "reports" / "backtest" / "phase-06.json"
SIMULATIONS = 1_000
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
LOADING_COPY = "Building replay…"
TIRE_COMPOUNDS = {
    "SOFT": ("S", "Soft", "#FF6B6B"),
    "MEDIUM": ("M", "Medium", "#FFD166"),
    "HARD": ("H", "Hard", "#ECEAE4"),
    "INTERMEDIATE": ("I", "Intermediate", "#5FD38D"),
    "WET": ("W", "Full wet", "#65BDFF"),
}


def _data_file() -> Path:
    """Resolve the configured local cache without creating or modifying it."""
    configured = paths.db_path(paths.data_dir())
    return configured if configured.is_absolute() else PROJECT_ROOT / configured


def _model_identity(data_path: Path) -> str:
    """Use immutable cache metadata plus all package source in the cache identity."""
    stat = data_path.stat()
    digest = hashlib.sha256()
    package_root = PROJECT_ROOT / "src" / "f1si"
    for source in sorted(package_root.rglob("*.py")):
        relative = source.relative_to(PROJECT_ROOT).as_posix()
        digest.update(relative.encode())
        digest.update(source.read_bytes())
    return f"{stat.st_size}:{stat.st_mtime_ns}:{digest.hexdigest()}"


@st.cache_data(show_spinner=False, max_entries=4)
def _eligible_catalog(data_path: Path) -> Any:
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
    return f"{row.event_name} {int(row.season)}"


def _count_label(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural or singular + 's'}"


def _action_heading(count: int) -> str:
    if count == 0:
        return "No ranked strategy actions available"
    return "Ranked strategy actions: " + _count_label(count, "action", "actions")


def _annotate_strategy_options(
    columns: tuple[str, ...], rows: tuple[tuple[Any, ...], ...], fallback: bool
) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]]:
    """Keep fallback status adjacent to each affected ranked action."""
    label = "Uncalibrated" if fallback else "Cutoff inputs"
    return (*columns, "Basis"), tuple((*row, label) for row in rows)


def _ranked_strategy_rows(
    columns: tuple[str, ...], rows: tuple[tuple[Any, ...], ...]
) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]]:
    """Attach the top marker to the first ranked action without changing its metrics."""
    return ("Rank", *columns), tuple(
        ("Top" if index == 0 else "", *row) for index, row in enumerate(rows)
    )


def _safe_replay_result(builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Return a fresh error state without carrying any previous selection's output."""
    try:
        return {"status": "ready", "value": builder()}
    except Exception as err:
        return {"status": "error", "value": None, "reason": str(err)}


def _render_replay_failure() -> None:
    """Show fixed recovery copy without exposing a caught exception or old output."""
    st.error(ERROR_COPY)


def _render_neutral_note(copy: str) -> None:
    """Render a status note with only the page's neutral surface tokens."""
    st.markdown(
        f'<div class="neutral-note" role="status">{html.escape(copy)}</div>',
        unsafe_allow_html=True,
    )


def _schedule_failure_copy(error: ValueError) -> str:
    """Use schedule guidance when the selected event lacks a verified horizon."""
    if str(error).startswith("Scheduled race distance is unavailable"):
        return UNAVAILABLE_SCHEDULE_COPY
    return ERROR_COPY


def _render_replay_outcome(outcome: dict[str, Any]) -> None:
    """Render a fresh replay result or the same safe failure state for every error."""
    if outcome.get("status") != "ready" or outcome.get("value") is None:
        _render_replay_failure()
        return
    _render_selected(cast(dict[str, Any], outcome["value"]))


def _probability_track_markup(probability: float) -> str:
    """Return a neutral probability track with one accessible active-value marker."""
    value = min(max(float(probability), 0.0), 1.0)
    return (
        '<div role="img" aria-label="Safety-car probability: '
        f'{value:.1%}" style="height: 12px; position: relative; margin: 8px 0 16px; '
        'background: #24282D; border: 1px solid #3A4047; border-radius: 6px;">'
        f'<span style="position: absolute; left: {value * 100:.1f}%; top: -4px; '
        "width: 4px; height: 20px; background: #9BA1A8; border-radius: 2px; "
        'transform: translateX(-50%);"></span></div>'
    )


def _risk_value_label(risk: float) -> str:
    return f"Current risk aversion: {risk:.2f}"


def _strategist_reason(action: str, mean_finish: float, cvar10: float) -> str:
    return (
        f"{action.capitalize()} ranks first on the balanced score, averaging "
        f"{mean_finish:.2f} overall and {cvar10:.2f} among its worst 10% of simulated finishes."
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
    """Build immutable display values through the same cutoff builder as replay/backtest."""
    del model_identity  # It remains an explicit cache-key input; it is not a model override.
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
    )
    if cutoff.analysis is None:
        car = context.state.car(code)
        return {
            "available": True,
            "strategy_available": False,
            "reason": cutoff.unavailable_reason,
            "race_name": snapshot.race.event_name,
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
            "safety_car_share": None,
            "safety_car_source": cli._sc_source(context.estimate),
            "tire_rate": car.wear_rate_s_per_lap,
            "tire_sd": car.wear_sd,
            "tire_compound": car.compound,
            "tire_source": car.wear_source,
            "fallback": context.is_fallback,
        }

    analysis = cutoff.analysis
    selected = analysis.best
    simulator = NumpySimulator(
        context.model,
        sc=SafetyCarModel(context.estimate.rate_per_lap, context.estimate.duration_laps),
        compounds=context.compounds,
        wear_sd_by_compound=context.wear_sd_by_compound,
    )
    simulation = simulator.simulate(
        context.state,
        n_races=n_simulations,
        rng=make_rng(seed),
        plans={code: selected.plan},
        position_history_driver=code,
    )
    fan_chart_data = (
        None
        if simulation.position_history is None
        else prepare_fan_chart_data(
            simulation.position_history,
            first_lap=cutoff_lap + 1,
            n_cars=len(context.state.cars),
        )
    )
    sc_share = (
        0.0 if simulation.sc_lap_mask is None else float(simulation.sc_lap_mask.any(axis=1).mean())
    )
    car = context.state.car(code)
    rate = car.wear_rate_s_per_lap
    wear_sd = car.wear_sd
    return {
        "available": True,
        "strategy_available": True,
        "race_name": snapshot.race.event_name,
        "driver": code,
        "cutoff_lap": cutoff_lap,
        "risk": risk,
        "option_columns": (
            "Action",
            "Mean finish",
            "Spread",
            "Worst 10% average finish",
            "Score",
            "Podium chance",
            "Top-10 chance",
            "90% finish interval",
        ),
        "options": tuple(
            (
                item.action,
                item.mean_finish,
                item.spread,
                item.cvar10,
                item.score,
                item.podium_probability,
                item.top10_probability,
                f"P{item.finish_p05}-P{item.finish_p95}",
            )
            for item in analysis.options
        ),
        "option_quantiles": tuple(item.finish_quantiles for item in analysis.options),
        "selected_cutoff_mean": selected.mean_finish,
        "simulation_count": n_simulations,
        "fan_chart_data": fan_chart_data,
        "reason": _strategist_reason(selected.action, selected.mean_finish, selected.cvar10),
        "n_cars": len(context.state.cars),
        "safety_car_probability": context.estimate.rate_per_lap,
        "safety_car_share": sc_share,
        "safety_car_source": cli._sc_source(context.estimate),
        "tire_rate": rate,
        "tire_sd": wear_sd,
        "tire_compound": car.compound,
        "tire_source": car.wear_source,
        "fallback": cutoff.is_fallback,
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
            "Target: 85\u201395%."
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
    with st.container(key="evaluation-scorecard"):
        table = pd.DataFrame(
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
        st.table(table)


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --space-xs: 4px; --space-sm: 8px; --space-md: 16px;
            --space-lg: 24px; --space-xl: 32px; --space-2xl: 48px; --space-3xl: 64px;
        }
        .stApp { background: #1C1F23; color: #ECEAE4; }
        .stApp p, .stApp li { font-size: 16px; line-height: 1.5; }
        .stApp h1 { font-size: 28px; font-weight: 600; line-height: 1.2; }
        .stApp h2, .stApp h3 { font-size: 20px; font-weight: 600; line-height: 1.2; }
        .stApp [data-testid="stVerticalBlock"] { gap: var(--space-md); }
        .stApp [data-testid="stMetricValue"] {
            color: #ECEAE4; font-size: 20px;
            font-variant-numeric: tabular-nums; font-feature-settings: "tnum";
            white-space: normal; overflow-wrap: anywhere;
        }
        .stApp [data-testid="stMetricValue"] [data-testid="stMarkdownContainer"] {
            white-space: normal; overflow: visible; text-overflow: clip; height: auto;
        }
        .stApp [data-testid="stMetricValue"] p {
            white-space: normal; overflow-wrap: anywhere;
        }
        .stApp [data-testid="stMetricLabel"] {
            color: #9BA1A8; font-size: 14px; white-space: normal; overflow-wrap: anywhere;
            font-variant-numeric: tabular-nums; font-feature-settings: "tnum";
        }
        .stApp [data-testid="stMetricLabel"] [data-testid="stMarkdownContainer"] {
            white-space: normal; overflow: visible; text-overflow: clip; height: auto;
        }
        .stApp [data-testid="stMetricLabel"] p {
            white-space: normal; overflow-wrap: anywhere;
        }
        .stApp [data-testid="stCaptionContainer"] {
            color: #9BA1A8; font-size: 14px;
            font-variant-numeric: tabular-nums; font-feature-settings: "tnum";
        }
        .stApp .neutral-note {
            background: #24282D; border: 1px solid #3A4047; border-radius: 8px;
            color: #ECEAE4; font-size: 16px; line-height: 1.5; padding: 16px;
        }
        .stApp [data-testid="stDataFrame"],
        .stApp [data-testid="stTable"] {
            font-variant-numeric: tabular-nums; font-feature-settings: "tnum";
        }
        .stApp [data-testid="stWidgetLabel"] p {
            font-size: 14px; font-weight: 600; line-height: 1.4;
        }
        .st-key-evaluation-scorecard,
        .st-key-replay-controls,
        .st-key-safety-car-card,
        .st-key-tire-card,
        .st-key-strategy-card {
            background-color: #24282D;
            border: 1px solid #3A4047;
            border-radius: 12px;
            padding: var(--space-lg);
        }
        .st-key-finish-chart {
            background-color: #24282D;
            border: 1px solid #3A4047;
            border-radius: 12px;
            padding: var(--space-md);
        }
        .st-key-finish-chart-mobile,
        .st-key-fan-chart-mobile { display: none; }
        .st-key-replay-controls [data-testid="stForm"] { padding: var(--space-md) 0 0; }
        .st-key-evaluation-scorecard [data-testid="stHorizontalBlock"],
        .st-key-replay-controls [data-testid="stHorizontalBlock"] { gap: var(--space-md); }
        .st-key-replay-controls [data-testid="stSelectbox"] [data-baseweb="select"],
        .st-key-replay-controls [data-testid="stSlider"] [data-baseweb="slider"] {
            min-height: 44px;
        }
        .st-key-replay-controls [data-testid="stSlider"] {
            font-variant-numeric: tabular-nums; font-feature-settings: "tnum";
        }
        .st-key-replay-controls [data-testid="stFormSubmitButton"] button {
            min-height: 44px;
            background: #24282D;
            border: 1px solid #3A4047;
            border-radius: 8px;
            color: #ECEAE4;
            font-weight: 600;
        }
        .st-key-replay-controls [data-testid="stFormSubmitButton"] button:hover {
            filter: brightness(0.92);
        }
        .st-key-replay-controls [data-testid="stFormSubmitButton"] button:focus-visible {
            outline: 3px solid #ECEAE4;
            outline-offset: 2px;
        }
        .st-key-strategy-card [data-testid="stDataFrame"] { overflow-x: auto !important; }
        .st-key-evaluation-scorecard [data-testid="stTable"] th,
        .st-key-evaluation-scorecard [data-testid="stTable"] td {
            white-space: normal; overflow-wrap: anywhere;
            font-variant-numeric: tabular-nums; font-feature-settings: "tnum";
        }
        .st-key-strategy-card [data-testid="stMarkdownContainer"],
        .st-key-strategy-card [data-testid="stCaptionContainer"],
        .st-key-replay-controls [data-testid="stWidgetLabel"],
        .st-key-replay-controls [data-testid="stSelectbox"] *,
        .st-key-replay-controls [data-testid="stFormSubmitButton"] p {
            overflow-wrap: anywhere;
            white-space: normal;
        }
        @media (max-width: 760px) {
            .st-key-finish-chart-desktop,
            .st-key-fan-chart-desktop { display: none !important; }
            .st-key-finish-chart-mobile,
            .st-key-fan-chart-mobile { display: block !important; }
            .st-key-evaluation-scorecard [data-testid="stHorizontalBlock"],
            .st-key-replay-controls [data-testid="stHorizontalBlock"],
            .st-key-replay-result-layout [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
                gap: var(--space-md);
            }
            .st-key-evaluation-scorecard [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"],
            .st-key-replay-controls [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
            .st-key-replay-result-layout [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"] {
                flex: 1 1 100% !important; min-width: 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_selected(result: dict[str, Any]) -> None:
    if not result["available"]:
        _render_neutral_note(
            "Unavailable at this cutoff: " + str(result.get("reason") or "No eligible data.")
        )
        return
    is_fallback = bool(result["fallback"])
    options = tuple(result["options"])
    if not result["strategy_available"] or not options:
        st.subheader("Recommended strategy unavailable")
        _render_neutral_note("No ranked strategy actions were produced at this cutoff.")
        st.markdown(f"**Reason:** {result.get('reason') or 'No strategy output is available.'}")
        st.caption(f"Selected risk aversion: {result['risk']:.2f}")
        return

    with st.container(key="recommended-strategy"):
        st.subheader("Recommended strategy")
        st.markdown(
            '<p><span style="color:#B69BFF;font-weight:600;">Top</span>: '
            f"{html.escape(str(options[0][0]))}</p>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**Reason:** {html.escape(str(result['reason']))}")
        st.caption(
            f"{html.escape(str(result.get('race_name', 'Race')))}, {result['driver']}, "
            f"after lap {result['cutoff_lap']}"
        )

    with st.container(border=True, key="finish-chart"):
        option_quantiles = tuple(result.get("option_quantiles") or ())
        if len(options) == len(option_quantiles):
            dotplot = prepare_quantile_dotplot_data(
                tuple(str(row[0]) for row in options),
                option_quantiles,
                mean_finish=float(result["selected_cutoff_mean"]),
                n_cars=int(result["n_cars"]),
                simulation_count=int(result["simulation_count"]),
            )
            st.subheader("Finish distribution by strategy")
            with st.container(key="finish-chart-desktop"):
                st.pyplot(build_quantile_dotplot(dotplot, include_caption=False), clear_figure=True)
            with st.container(key="finish-chart-mobile"):
                st.pyplot(
                    build_quantile_dotplot(dotplot, include_caption=False, compact=True),
                    clear_figure=True,
                )
            st.caption(dotplot.caption)
        else:
            _render_neutral_note("Finishing distribution unavailable at this cutoff.")

        fan_chart = result.get("fan_chart_data")
        if isinstance(fan_chart, dict):
            fan_chart = FanChartData(**fan_chart)
        if isinstance(fan_chart, FanChartData):
            st.subheader("Projected finishing-position uncertainty")
            with st.container(key="fan-chart-desktop"):
                st.pyplot(build_fan_chart(fan_chart, include_caption=False), clear_figure=True)
            with st.container(key="fan-chart-mobile"):
                st.pyplot(
                    build_fan_chart(fan_chart, include_caption=False, compact=True),
                    clear_figure=True,
                )
            st.caption(fan_chart.caption)
        else:
            _render_neutral_note("Finishing projection unavailable at this cutoff.")

    with st.container(key="replay-result-layout"):
        left, right = st.columns((1, 1), gap="large")
        with left, st.container(border=True, key="safety-car-card"):
            st.subheader("Safety-car chance")
            st.caption("Historical per-lap estimate at this circuit, shown for context.")
            st.markdown(
                _probability_track_markup(float(result["safety_car_probability"])),
                unsafe_allow_html=True,
            )
            st.metric("Chance", f"{result['safety_car_probability']:.2%}")
            if is_fallback:
                st.caption("Uncalibrated. Based on limited data at this lap.")
        with right, st.container(border=True, key="tire-card"):
            st.subheader("Tire estimate and uncertainty")
            compound = str(result.get("tire_compound") or "").upper()
            if compound in TIRE_COMPOUNDS:
                letter, name, color = TIRE_COMPOUNDS[compound]
                st.markdown(
                    f'<span style="font-weight:600;color:{color};">{letter}</span> {name} compound',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Tire compound unavailable at this cutoff.")
            rate = result["tire_rate"]
            sd = result["tire_sd"]
            if rate is None or sd is None:
                _render_neutral_note("Tire wear estimate unavailable at this cutoff.")
            else:
                st.metric("Wear rate", f"{rate:.3f} s/lap", delta=f"± {sd:.3f} s/lap")
                if is_fallback or result["tire_source"] != "filter":
                    st.caption("Uncalibrated. Based on prior or limited data.")

    columns, rows = _annotate_strategy_options(
        tuple(result["option_columns"]), options, is_fallback
    )
    with st.container(key="strategy-card"):
        st.subheader(_action_heading(len(rows)))
        marked_columns, marked_rows = _ranked_strategy_rows(columns, rows)
        strategy_table = pd.DataFrame(marked_rows, columns=marked_columns)
        styled_table = strategy_table.style.set_table_styles(
            [
                {
                    "selector": "td",
                    "props": [
                        ("font-variant-numeric", "tabular-nums"),
                        ("font-feature-settings", '"tnum"'),
                    ],
                }
            ]
        ).map(
            lambda value: (
                (
                    "color: #B69BFF; font-weight: 600; "
                    "border-left: 4px solid #B69BFF; padding-left: 8px;"
                )
                if value == "Top"
                else ""
            ),
            subset=["Rank"],
        )
        st.dataframe(styled_table, hide_index=True, width="stretch", height="content")
        st.caption(f"Selected risk aversion: {result['risk']:.2f}")


def main() -> None:
    st.set_page_config(page_title="F1 strategy replay", page_icon="🏁", layout="wide")
    _apply_styles()
    st.title("F1 strategy replay")
    st.caption("Read-only race replay using information available at each lap.")
    report = _report_summary()

    data_path = _data_file()
    try:
        catalog = _eligible_catalog(data_path) if data_path.is_file() else None
    except Exception:
        catalog = None
    if catalog is None or catalog.empty:
        st.write(EMPTY_BODY)
        return

    rows = list(catalog.itertuples(index=False))
    race_ids = [str(row.race_id) for row in rows]
    raw_selection = st.session_state.get("phase6_replay_selection")
    saved_selection = (
        raw_selection if isinstance(raw_selection, tuple) and len(raw_selection) == 4 else None
    )
    saved_race = None if saved_selection is None else str(saved_selection[0])
    default_race = next(
        (index for index, race_id in enumerate(race_ids) if race_id == (saved_race or "2023-01")),
        0,
    )
    labels = {_race_label(row): str(row.race_id) for row in rows}
    with st.container(border=True, key="replay-controls"):
        st.subheader("Replay controls")
        with st.form("replay-selection"):
            col_race, col_driver, col_cutoff, col_risk = st.columns(4, gap="medium")
            with col_race:
                race_label = st.selectbox(
                    f"Race ({_count_label(len(labels), 'eligible race', 'eligible races')})",
                    list(labels),
                    index=default_race,
                )
            race_id = labels[race_label]
            try:
                accessor = cli._make_asof_accessor(data_path)
                first = accessor.snapshot(asof.AsOf(race_id, 0))
                laps_total = walk_forward._race_laps_total(accessor, race_id, first)
            except ValueError as err:
                _render_neutral_note(_schedule_failure_copy(err))
                return
            except Exception:
                _render_replay_failure()
                return
            cutoff_options = list(range(max(0, laps_total - 1)))
            driver_options = sorted({str(code).upper() for code in first.entries["driver_code"]})
            if not driver_options or not cutoff_options:
                st.write(EMPTY_BODY)
                return
            saved_driver = (
                str(saved_selection[1])
                if saved_selection is not None and str(saved_selection[0]) == race_id
                else ""
            )
            selected_driver = (
                saved_driver
                if saved_driver in driver_options
                else ("ALO" if "ALO" in driver_options else driver_options[0])
            )
            preferred_cutoff = (
                int(saved_selection[2])
                if saved_selection is not None
                and str(saved_selection[0]) == race_id
                and isinstance(saved_selection[2], int)
                else 15
            )
            selected_cutoff = (
                preferred_cutoff
                if preferred_cutoff in cutoff_options
                else cutoff_options[len(cutoff_options) // 2]
            )
            selected_risk = (
                float(saved_selection[3])
                if saved_selection is not None
                and str(saved_selection[0]) == race_id
                and isinstance(saved_selection[3], int | float)
                else 0.5
            )
            with col_driver:
                driver = st.selectbox(
                    f"Driver ({_count_label(len(driver_options), 'option')})",
                    driver_options,
                    index=driver_options.index(selected_driver),
                )
            with col_cutoff:
                cutoff_lap = st.selectbox(
                    f"Cutoff lap ({_count_label(len(cutoff_options), 'lap')})",
                    cutoff_options,
                    index=cutoff_options.index(selected_cutoff),
                    format_func=lambda lap: f"After lap {lap}",
                )
            with col_risk:
                risk = st.slider(
                    "Risk aversion",
                    0.0,
                    1.0,
                    selected_risk,
                    0.05,
                )
                st.markdown(
                    '<div style="display:flex;justify-content:space-between;gap:8px;'
                    "font-variant-numeric:tabular-nums;font-feature-settings:'tnum';\">"
                    "<span>0.0 Mean-focused</span><span>1.0 tail-risk-focused</span></div>",
                    unsafe_allow_html=True,
                )
                st.caption(_risk_value_label(risk))
            submitted = st.form_submit_button(
                "Update replay", type="secondary", use_container_width=True
            )

    if submitted:
        selected = (race_id, driver, int(cutoff_lap), float(risk))
        st.session_state["phase6_replay_selection"] = selected
    elif isinstance(saved_selection, tuple) and len(saved_selection) == 4:
        selected = (
            str(saved_selection[0]),
            str(saved_selection[1]),
            int(saved_selection[2]),
            float(saved_selection[3]),
        )
    else:
        selected = (race_id, driver, int(cutoff_lap), float(risk))
        st.session_state["phase6_replay_selection"] = selected
    try:
        identity = _model_identity(data_path)
        with st.spinner(LOADING_COPY):
            outcome = _safe_replay_result(
                lambda: _build_selected_replay(
                    selected[0],
                    selected[1],
                    selected[2],
                    selected[3],
                    SIMULATIONS,
                    SEED,
                    str(data_path),
                    identity,
                )
            )
        _render_replay_outcome(outcome)
    except Exception:
        _render_replay_failure()
    _render_report_summary(report)


if __name__ == "__main__":
    main()
