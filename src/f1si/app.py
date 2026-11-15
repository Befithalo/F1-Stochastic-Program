"""Read-only, cutoff-safe single-page replay view."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import streamlit as st

import f1si.backtest.walk_forward as walk_forward
from f1si import cli, paths
from f1si.data import asof
from f1si.plots.simulate import build_sim_figure, prepare_sim_plot_data
from f1si.rng import make_rng
from f1si.sim.numpy_backend import NumpySimulator, SafetyCarModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "reports" / "backtest" / "phase-06.json"
SIMULATIONS = 1_000
SEED = 0
EMPTY_TITLE = "No race data available"
EMPTY_BODY = "Load the local race cache, then reload this page."
ERROR_COPY = (
    "Replay could not be built for this selection. Check the local cache and eligible cutoffs, "
    "then retry or choose another race."
)
LOADING_COPY = "Building cutoff-safe replay…"


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


def _eligible_catalog(data_path: Path) -> Any:
    catalog = asof.catalog(data_path)
    return catalog.loc[
        catalog["season"].between(2023, 2025)
        & catalog["load_status"].eq("complete")
        & ~catalog["out_of_sample"].astype(bool)
    ].copy()


def _race_label(row: Any) -> str:
    return f"{row.event_name} {int(row.season)}"


def _count_label(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural or singular + 's'}"


def _action_heading(count: int) -> str:
    if count == 0:
        return "No ranked strategy actions available"
    return "Ranked strategy actions · " + _count_label(count, "action", "actions")


def _annotate_strategy_options(
    columns: tuple[str, ...], rows: tuple[tuple[Any, ...], ...], fallback: bool
) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]]:
    """Keep fallback status adjacent to each affected ranked action."""
    label = "UNCALIBRATED" if fallback else "Cutoff inputs"
    return (*columns, "Basis"), tuple((*row, label) for row in rows)


def _ranked_strategy_rows(
    columns: tuple[str, ...], rows: tuple[tuple[Any, ...], ...]
) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]]:
    """Attach the top marker to the first ranked action without changing its metrics."""
    return ("Rank", *columns), tuple(
        ("TOP" if index == 0 else "", *row) for index, row in enumerate(rows)
    )


def _safe_replay_result(builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Return a fresh error state without carrying any previous selection's output."""
    try:
        return {"status": "ready", "value": builder()}
    except Exception as err:
        return {"status": "error", "value": None, "reason": str(err)}


def _render_replay_failure() -> None:
    """Show fixed recovery copy without exposing a caught exception or old output."""
    st.info(ERROR_COPY)


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
        'background: #10151C; border: 1px solid #536171; border-radius: 6px;">'
        f'<span style="position: absolute; left: {value * 100:.1f}%; top: -4px; '
        "width: 4px; height: 20px; background: #D90429; border-radius: 2px; "
        'transform: translateX(-50%);"></span></div>'
    )


def _risk_value_label(risk: float) -> str:
    return f"Current risk aversion: {risk:.2f}"


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
            "finishes": (),
            "n_cars": len(context.state.cars),
            "safety_car_probability": context.estimate.rate_per_lap,
            "safety_car_share": None,
            "safety_car_source": cli._sc_source(context.estimate),
            "tire_rate": car.wear_rate_s_per_lap,
            "tire_sd": car.wear_sd,
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
    )
    column = next(index for index, car in enumerate(context.state.cars) if car.driver == code)
    finishes = np.asarray(simulation.finish_positions[:, column], dtype=np.int64)
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
            "CVaR10",
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
        "reason": analysis.reason,
        "finishes": tuple(int(value) for value in finishes),
        "n_cars": len(context.state.cars),
        "safety_car_probability": context.estimate.rate_per_lap,
        "safety_car_share": sc_share,
        "safety_car_source": cli._sc_source(context.estimate),
        "tire_rate": rate,
        "tire_sd": wear_sd,
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
    return {
        "podium": f"{podium['model']['mean']:.5f} / {podium['baseline']['mean']:.5f}",
        "top10": f"{top10['model']['mean']:.5f} / {top10['baseline']['mean']:.5f}",
        "coverage": (
            f"Equal-race average: {coverage['coverage']['mean']:.1%}; "
            f"pooled: {coverage['covered'] / coverage['classified_finishers']:.1%} "
            f"({coverage['covered']:,} / {coverage['classified_finishers']:,})"
        ),
        "team": (
            f"{agreement['mean']:.1%} top-action agreement "
            f"(race-cluster 95% interval {agreement['race_cluster_95']['low']:.1%}-"
            f"{agreement['race_cluster_95']['high']:.1%}); absolute stop-timing error "
            f"{timing['mean']:.2f} laps (95% interval {timing['race_cluster_95']['low']:.2f}-"
            f"{timing['race_cluster_95']['high']:.2f}); {team['event_count']} observed stops."
        ),
        "team_agreement": f"{agreement['mean']:.1%}",
        "team_agreement_interval": (
            f"95% CI {agreement_interval['low']:.1%}-{agreement_interval['high']:.1%}"
        ),
        "team_timing": f"{timing['mean']:.2f} laps",
        "team_timing_interval": (
            f"95% CI {timing_interval['low']:.2f}-{timing_interval['high']:.2f} laps"
        ),
    }


def _render_report_summary(report: dict[str, Any]) -> None:
    display = _report_display_values(report)
    metrics = report["metrics"]
    st.subheader("Complete ten-race evaluation · fixed report")
    with st.container(border=True, key="evaluation-scorecard"):
        st.caption("Fixed, report-backed results · model / grid baseline")
        columns = st.columns(3)
        columns[0].metric("Podium Brier · model / grid baseline", display["podium"])
        columns[1].metric("Top-10 Brier · model / grid baseline", display["top10"])
        columns[2].metric("90% finish coverage · classified denominator", display["coverage"])
        team_columns = st.columns(2)
        team_columns[0].metric(
            "Team top-action agreement",
            display["team_agreement"],
            delta=display["team_agreement_interval"],
            delta_color="off",
        )
        team_columns[1].metric(
            "Absolute stop-timing error",
            display["team_timing"],
            delta=display["team_timing_interval"],
            delta_color="off",
        )
        st.caption(
            f"{len(report['race_ids'])} registered races · "
            f"{metrics['brier_observation_count']:,} driver/cutoff observations · "
            f"{report['metrics']['team_strategy_comparison']['event_count']} observed stops"
        )


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --space-xs: 4px; --space-sm: 8px; --space-md: 16px;
            --space-lg: 24px; --space-xl: 32px; --space-2xl: 48px; --space-3xl: 64px;
        }
        .stApp { background: #10151C; color: #F2F5F8; }
        .stApp p, .stApp li { font-size: 16px; line-height: 1.5; }
        .stApp h1 { font-size: 28px; font-weight: 600; line-height: 1.2; }
        .stApp h2, .stApp h3 { font-size: 20px; font-weight: 600; line-height: 1.2; }
        .stApp [data-testid="stVerticalBlock"] { gap: var(--space-md); }
        .stApp [data-testid="stMetricValue"] { color: #F2F5F8; font-size: 20px; }
        .stApp [data-testid="stMetricLabel"] { color: #B7C2CE; font-size: 14px; }
        .stApp [data-testid="stCaptionContainer"] { color: #B7C2CE; font-size: 14px; }
        .stApp [data-testid="stWidgetLabel"] p {
            font-size: 14px; font-weight: 600; line-height: 1.4;
        }
        .st-key-evaluation-scorecard [data-testid="stMetric"] {
            background-color: #242E39;
            border: 1px solid #35404C;
            border-radius: 8px;
            padding: var(--space-md);
        }
        .st-key-evaluation-scorecard,
        .st-key-replay-controls,
        .st-key-safety-car-card,
        .st-key-tire-card,
        .st-key-strategy-card {
            background-color: #1A222C;
            border: 1px solid #35404C;
            border-radius: 12px;
            padding: var(--space-lg);
        }
        .st-key-finish-chart {
            background-color: #1A222C;
            border: 1px solid #35404C;
            border-radius: 12px;
            padding: var(--space-md);
        }
        .st-key-replay-controls [data-testid="stForm"] { padding: var(--space-md) 0 0; }
        .st-key-evaluation-scorecard [data-testid="stHorizontalBlock"],
        .st-key-replay-controls [data-testid="stHorizontalBlock"] { gap: var(--space-md); }
        .st-key-replay-controls [data-testid="stSelectbox"] [data-baseweb="select"],
        .st-key-replay-controls [data-testid="stSlider"] [data-baseweb="slider"] {
            min-height: 44px;
        }
        .st-key-replay-controls [data-testid="stFormSubmitButton"] button {
            min-height: 44px;
            background: #D90429;
            border: 1px solid #D90429;
            border-radius: 8px;
            color: #F2F5F8;
            font-weight: 600;
        }
        .st-key-replay-controls [data-testid="stFormSubmitButton"] button:hover {
            filter: brightness(0.92);
        }
        .st-key-replay-controls [data-testid="stFormSubmitButton"] button:focus-visible {
            outline: 3px solid #F2F5F8;
            outline-offset: 2px;
        }
        .st-key-strategy-card [data-testid="stDataFrame"] { overflow-x: auto !important; }
        .st-key-strategy-card [data-testid="stMarkdownContainer"],
        .st-key-strategy-card [data-testid="stCaptionContainer"],
        .st-key-replay-controls [data-testid="stWidgetLabel"],
        .st-key-replay-controls [data-testid="stSelectbox"] *,
        .st-key-replay-controls [data-testid="stSlider"] *,
        .st-key-replay-controls [data-testid="stFormSubmitButton"] p {
            overflow-wrap: anywhere;
            white-space: normal;
        }
        @media (max-width: 760px) {
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
        st.info("Unavailable at this cutoff: " + str(result.get("reason") or "No eligible data."))
        return
    is_fallback = bool(result["fallback"])
    with st.container(key="replay-result-layout"):
        left, right = st.columns((2, 1), gap="large")
        with left:
            if result["strategy_available"]:
                finishes = np.asarray(result["finishes"], dtype=np.int64)
                chart = prepare_sim_plot_data(
                    finishes,
                    slug="selected-replay",
                    driver=result["driver"],
                    lap=result["cutoff_lap"],
                    n_races=len(finishes),
                    sc_share=float(result["safety_car_share"]),
                    sc_source=str(result["safety_car_source"]),
                    hindsight=False,
                    n_cars=int(result["n_cars"]),
                )
                with st.container(border=True, key="finish-chart"):
                    st.subheader("Finishing distribution")
                    st.pyplot(build_sim_figure(chart, include_caption=False), clear_figure=True)
                    st.caption(chart.caption)
            else:
                st.info(
                    "Unavailable at this cutoff: "
                    + str(result.get("reason") or "No strategy data.")
                )
        with right:
            with st.container(border=True, key="safety-car-card"):
                st.subheader("Safety-car probability (current proxy)")
                st.caption(
                    "Existing per-lap probability; this is not a Markov regime classification."
                )
                st.markdown(
                    _probability_track_markup(float(result["safety_car_probability"])),
                    unsafe_allow_html=True,
                )
                st.metric("Probability", f"{result['safety_car_probability']:.2%}")
                if is_fallback:
                    st.caption("UNCALIBRATED · sparse cutoff fallback")
            with st.container(border=True, key="tire-card"):
                st.subheader("Tire estimate and uncertainty")
                rate = result["tire_rate"]
                sd = result["tire_sd"]
                if rate is None or sd is None:
                    st.info("Unavailable at this cutoff")
                else:
                    st.metric("Wear rate", f"{rate:.3f} s/lap", delta=f"± {sd:.3f} s/lap")
                    if is_fallback or result["tire_source"] != "filter":
                        st.caption("UNCALIBRATED · prior or sparse fallback")
    options = tuple(result["options"])
    if not result["strategy_available"] or not options:
        with st.container(border=True, key="strategy-card"):
            st.info("Unavailable at this cutoff: no ranked strategy actions were produced.")
            st.markdown(f"**Reason:** {result.get('reason') or 'No strategy output is available.'}")
            st.caption(f"Selected risk aversion: {result['risk']:.2f}")
        return
    columns, rows = _annotate_strategy_options(
        tuple(result["option_columns"]), options, is_fallback
    )
    with st.container(border=True, key="strategy-card"):
        st.subheader(_action_heading(len(rows)))
        marked_columns, marked_rows = _ranked_strategy_rows(columns, rows)
        strategy_table = pd.DataFrame(marked_rows, columns=marked_columns)
        styled_table = strategy_table.style.map(
            lambda value: (
                (
                    "color: #F2F5F8; font-weight: 600; "
                    "border-left: 4px solid #D90429; padding-left: 8px;"
                )
                if value == "TOP"
                else ""
            ),
            subset=["Rank"],
        )
        st.dataframe(styled_table, hide_index=True, width="stretch", height="content")
        st.markdown(f"**Reason:** {result['reason']}")
        st.caption(f"Selected risk aversion: {result['risk']:.2f}")


def main() -> None:
    st.set_page_config(page_title="F1 strategy replay", page_icon="🏁", layout="wide")
    _apply_styles()
    st.title("F1 strategy replay")
    st.caption("A read-only, cutoff-safe strategy view · no live data or final race results")
    report = _report_summary()
    _render_report_summary(report)

    data_path = _data_file()
    try:
        catalog = _eligible_catalog(data_path) if data_path.is_file() else None
    except Exception:
        catalog = None
    if catalog is None or catalog.empty:
        with st.container(border=True, key="empty-cache-card"):
            st.subheader(EMPTY_TITLE)
            st.write(EMPTY_BODY)
        return

    rows = list(catalog.itertuples(index=False))
    race_ids = [str(row.race_id) for row in rows]
    default_race = next(
        (index for index, race_id in enumerate(race_ids) if race_id == "2023-01"), 0
    )
    labels = {_race_label(row): str(row.race_id) for row in rows}
    with st.container(border=True, key="replay-controls"):
        st.subheader("Replay controls")
        with st.form("replay-selection"):
            col_race, col_driver, col_cutoff, col_risk = st.columns(4, gap="medium")
            with col_race:
                race_label = st.selectbox(
                    f"Race · {_count_label(len(labels), 'eligible race', 'eligible races')}",
                    list(labels),
                    index=default_race,
                )
            race_id = labels[race_label]
            try:
                accessor = cli._make_asof_accessor(data_path)
                first = accessor.snapshot(asof.AsOf(race_id, 0))
                laps_total = walk_forward._race_laps_total(accessor, race_id, first)
            except Exception:
                _render_replay_failure()
                return
            cutoff_options = list(range(max(0, laps_total - 1)))
            driver_options = sorted({str(code).upper() for code in first.entries["driver_code"]})
            if not driver_options or not cutoff_options:
                with st.container(border=True, key="empty-cache-card"):
                    st.subheader(EMPTY_TITLE)
                    st.write(EMPTY_BODY)
                return
            selected_driver = (
                "ALO" if race_id == "2023-01" and "ALO" in driver_options else driver_options[0]
            )
            selected_cutoff = cutoff_options[len(cutoff_options) // 2]
            with col_driver:
                driver = st.selectbox(
                    f"Driver · {_count_label(len(driver_options), 'option')}",
                    driver_options,
                    index=driver_options.index(selected_driver),
                )
            with col_cutoff:
                cutoff_lap = st.selectbox(
                    f"Eligible cutoff · {_count_label(len(cutoff_options), 'lap')}",
                    cutoff_options,
                    index=cutoff_options.index(selected_cutoff),
                    format_func=lambda lap: f"After lap {lap}",
                )
            with col_risk:
                risk = st.slider(
                    "Risk aversion · Mean-focused to Tail-risk-focused",
                    0.0,
                    1.0,
                    0.5,
                    0.05,
                    help="0.0 = Mean-focused · 1.0 = Tail-risk-focused",
                )
                st.markdown(
                    '<div style="display:flex;justify-content:space-between;gap:8px;">'
                    "<span>0.0 Mean-focused</span><span>1.0 Tail-risk-focused</span></div>",
                    unsafe_allow_html=True,
                )
                st.caption(_risk_value_label(risk))
            submitted = st.form_submit_button(
                "Update replay", type="primary", use_container_width=True
            )

    if not submitted:
        st.info("Choose the race, driver, cutoff, and risk, then select Update replay.")
        return
    try:
        identity = _model_identity(data_path)
        with st.spinner(LOADING_COPY):
            outcome = _safe_replay_result(
                lambda: _build_selected_replay(
                    race_id,
                    driver,
                    int(cutoff_lap),
                    float(risk),
                    SIMULATIONS,
                    SEED,
                    str(data_path),
                    identity,
                )
            )
        _render_replay_outcome(outcome)
    except Exception:
        _render_replay_failure()


if __name__ == "__main__":
    main()
