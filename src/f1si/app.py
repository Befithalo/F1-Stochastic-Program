"""Read-only single-page race replay view.

Layout and copy follow ``docs/design/DESIGN_SYSTEM_V2.md`` (section 10 holds the 2026-11-16
decisions) and ``docs/design/COPY_V2.md``. Every number on the page comes from the shared
cutoff-only replay path; nothing is read from after the selected lap.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd
import streamlit as st

import f1si.backtest.walk_forward as walk_forward
from f1si import cli, paths
from f1si.data import asof
from f1si.plots.altair_charts import (
    PlanSegment,
    build_fan_chart,
    build_race_trace_chart,
    build_stint_chart,
)
from f1si.plots.replay_charts import (
    fastf1_team_color_map,
    prepare_race_trace_data,
    prepare_stint_bar_data,
    snapshot_driver_order,
)
from f1si.plots.simulate import FanChartData, prepare_fan_chart_data
from f1si.ui_theme import (
    CHALK,
    DEFAULT_TEAM_COLOR,
    FOG,
    REST_GREY,
    TIRE_COLORS,
    TIRE_LETTERS,
    band_background,
    fan_band_colors,
    readable_on,
    team_fill,
)

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "reports" / "backtest" / "phase-06.json"
SIMULATIONS = 10_000
SEED = 0
MAX_OPTION_ROWS = 4
EMPTY_BODY = (
    "No race can be replayed: every cached race is missing its scheduled lap count. "
    "Refresh the race cache, then reload this page."
)
UNAVAILABLE_SCHEDULE_COPY = (
    "This race has no scheduled lap count, so it can't be replayed. "
    "Refresh the race cache or pick another race."
)
ERROR_COPY = (
    "This replay failed to build. Pick another lap or race; the full error is in the server log."
)
LOADING_COPY = "Simulating the rest of the race..."
CUTOFF_UNAVAILABLE_COPY = "There's no replay for this lap. Pick another lap or race."
NO_STRATEGY_COPY = "The model has no strategy for this lap. Pick another lap or race."
REPORT_MISSING_COPY = "The model report for the ten test races didn't load."
THIN_TYRE_DATA_COPY = (
    "There are only a few laps on this set, so the tyre wear figure is a rough estimate."
)
TIRE_NAMES = {
    "SOFT": "Soft",
    "MEDIUM": "Medium",
    "HARD": "Hard",
    "INTERMEDIATE": "Intermediate",
    "WET": "Wet",
}
TIRE_PLURALS = {
    "SOFT": "Softs",
    "MEDIUM": "Mediums",
    "HARD": "Hards",
    "INTERMEDIATE": "Intermediates",
    "WET": "Wets",
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
SURNAME_OVERRIDES = {"ZHO": "Zhou"}
NUMBER_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
}


# ---------------------------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------------------------


def _esc(value: object) -> str:
    return html.escape(str(value))


def _plural(compound: str | None) -> str:
    code = (compound or "").upper()
    return TIRE_PLURALS.get(code, code.title() + "s" if code else "tyres")


def _surname(code: str, full_name: str | None = None) -> str:
    code = code.upper()
    if code in SURNAME_OVERRIDES:
        return SURNAME_OVERRIDES[code]
    name = full_name or DRIVER_NAMES.get(code) or code
    return name.split()[-1]


def _sentence_case(text: str) -> str:
    """Capitalize the first letter only; ``str.capitalize`` would lowercase "Hards"."""
    return text[:1].upper() + text[1:]


def _ordinal(value: int) -> str:
    suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _share_phrase(probability: float) -> str:
    """Express a probability as "N in D" with a small denominator: 0.34 -> "1 in 3"."""
    if probability < 0.05:
        return "fewer than 1 in 20"
    if probability > 0.95:
        return "nearly all"
    best: tuple[float, int, int] | None = None
    for denominator in (2, 3, 4, 5, 6, 10):
        numerator = max(1, round(probability * denominator))
        if numerator >= denominator:
            continue
        error = abs(numerator / denominator - probability)
        if best is None or error < best[0] - 1e-9:
            best = (error, numerator, denominator)
    assert best is not None
    return f"{best[1]} in {best[2]}"


def _action_compound(action: str) -> str | None:
    match = re.search(r"\(([A-Z]+)\)$", action)
    return match.group(1) if match is not None else None


def _delay_laps(action: str) -> int | None:
    match = re.match(r"pit in (\d+) lap(?:\(s\)|s?)", action)
    return int(match.group(1)) if match is not None else None


def _race_label(row: Any) -> str:
    event = str(row.event_name)
    return f"{event} {int(row.season)}"


# ---------------------------------------------------------------------------------------------
# Data: catalog and the cutoff-only replay
# ---------------------------------------------------------------------------------------------


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


def _safe_replay_result(builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Return a fresh error state without carrying a previous selection's output.

    The page shows only the generic error copy; the full traceback goes to the server log.
    """
    try:
        return {"status": "ready", "value": builder()}
    except Exception:
        LOGGER.exception("Replay could not be built")
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


def _strategist_reason(
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
    """Explain the recommendation through tyre pace and the cost of a stop.

    Wear model: lap time grows linearly with tyre age at ``rate`` s per lap, so ``n`` more laps
    on a set aged ``a`` cost ``rate * n * (2a + n + 1) / 2`` seconds against a new set. A stop
    pays off when the wear it saves exceeds the green-flag pit loss.
    """
    old = (current_compound or "").upper()
    new = (target_compound or "").upper()
    if next_stop_lap is None or not old or not new:
        return "Keep the current tyres to the flag."

    old_rate, new_rate = wear_rates.get(old), wear_rates.get(new)
    if old_rate is not None and new_rate is not None:
        remaining = max(0, laps_total - laps_done)
        before_stop = max(0, min(remaining, next_stop_lap - laps_done))
        after_stop = max(0, laps_total - next_stop_lap)
        no_stop_wear = float(old_rate) * (remaining * (2 * tire_age + remaining + 1) / 2)
        planned_wear = float(old_rate) * (before_stop * (2 * tire_age + before_stop + 1) / 2)
        planned_wear += float(new_rate) * after_stop * (after_stop + 1) / 2
        if no_stop_wear - planned_wear > pit_loss_s:
            return (
                f"Fresh {_plural(new)} should win back the {pit_loss_s:.0f} seconds a stop "
                f"costs as the {_plural(old)} fade."
            )
    return (
        f"The {_plural(old)} still have pace. Run them to the stop, then fit {_plural(new)} "
        "for the last stint."
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
    selected_color = team_colors.get(team_name, CHALK).upper()
    driver_order = snapshot_driver_order(snapshot)

    context = cli._prepare_replay_context(
        accessor, race_id, laps_total, cutoff_lap, snapshot=snapshot
    )
    car = context.state.car(code)
    leader = next(
        (item for item in context.state.cars if getattr(item, "position", None) == 1), None
    )
    common: dict[str, Any] = {
        "available": True,
        "race_name": snapshot.race.event_name,
        "race_season": int(snapshot.race.season),
        "laps_total": laps_total,
        "driver": code,
        "driver_name": driver_name,
        "team_name": team_name,
        "cutoff_lap": cutoff_lap,
        "risk": risk,
        "simulation_count": n_simulations,
        "n_cars": len(context.state.cars),
        "position": getattr(car, "position", None),
        "leader_code": None if leader is None else str(getattr(leader, "driver", "")).upper(),
        "stops_done": int(getattr(car, "stops_done", 0) or 0),
        "tire_age": int(getattr(car, "tire_age", 0) or 0),
        "safety_car_probability": context.estimate.rate_per_lap,
        "pit_loss_s": float(context.state.pit_loss_s["green"]),
        "tire_rate": car.wear_rate_s_per_lap,
        "tire_sd": car.wear_sd,
        "tire_compound": car.compound,
        "tire_source": car.wear_source,
        "race_trace_rows": trace_rows,
        "stint_rows": stint_rows,
        "team_colors": team_colors,
        "selected_color": selected_color,
        "driver_order": driver_order,
    }
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
        return {
            **common,
            "strategy_available": False,
            "reason": cutoff.unavailable_reason,
            "options": (),
            "option_quantiles": (),
            "option_plans": (),
            "selected_cutoff_mean": None,
            "fan_chart_data": None,
            "fallback": context.is_fallback,
        }

    analysis = cutoff.analysis
    selected = analysis.best
    policy_history = analysis.recommended_position_history
    fan_chart_data = (
        None
        if policy_history is None
        else prepare_fan_chart_data(
            policy_history,
            first_lap=cutoff_lap + 1,
            n_cars=len(context.state.cars),
        )
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
        **common,
        "strategy_available": True,
        "options": options,
        "option_quantiles": tuple(item.finish_quantiles for item in analysis.options),
        "option_plans": tuple(
            (tuple(item.plan.stop_laps), tuple(item.plan.compounds)) for item in analysis.options
        ),
        "selected_cutoff_mean": selected.mean_finish,
        "close_call_places": analysis.close_call_places,
        "close_call_two_se": analysis.close_call_two_se,
        "waiting_tie_window_laps": analysis.waiting_tie_window_laps,
        "never_stop_allowed": analysis.never_stop_allowed,
        "fan_chart_data": fan_chart_data,
        "reason": _strategist_reason(
            current_compound=car.compound,
            tire_age=car.tire_age,
            laps_done=context.state.laps_done_of(car),
            laps_total=laps_total,
            pit_loss_s=float(context.state.pit_loss_s["green"]),
            next_stop_lap=(selected.plan.stop_laps[0] if selected.plan.stop_laps else None),
            target_compound=(selected.plan.compounds[0] if selected.plan.compounds else None),
            wear_rates=wear_rates,
        ),
        "fallback": cutoff.is_fallback,
        "recommended_stop_lap": (selected.plan.stop_laps[0] if selected.plan.stop_laps else None),
        "recommended_compound": (selected.plan.compounds[0] if selected.plan.compounds else None),
    }


# ---------------------------------------------------------------------------------------------
# Options: parsing, merging and copy
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedAction:
    """An optimizer action label split into what the page needs.

    ``kind`` is "stay" (never stop), "wait" (decide next lap), "pit" (stop after ``delay`` more
    laps; 0 means this lap) or "other". ``compound`` is the compound fitted at that stop.
    """

    kind: str
    delay: int | None = None
    compound: str | None = None


def _parse_action(action: str) -> ParsedAction:
    compound = _action_compound(action)
    if action == "stay out":
        return ParsedAction("stay")
    if action == "wait and decide next lap":
        return ParsedAction("wait")
    if action.startswith("pit now"):
        return ParsedAction("pit", 0, compound)
    delay = _delay_laps(action)
    if delay is not None:
        return ParsedAction("pit", delay, compound)
    return ParsedAction("other")


@dataclass(frozen=True)
class Option:
    """One strategy option as shown on the page; ``merged`` holds actions with equal results.

    ``quantiles`` are the option's 100 finish quantiles (1% resolution), used only for the shape
    of the histogram and probability strips; podium and points shares come from the exact
    ``podium`` and ``points`` fields over every simulated race.
    """

    action: str
    mean: float
    bad_day: float
    podium: float
    points: float
    interval: str
    quantiles: tuple[int, ...]
    stop_laps: tuple[int, ...]
    compounds: tuple[str, ...]
    merged: tuple[str, ...] = ()

    def display_key(self) -> tuple[str, str, str, str]:
        return (
            f"{self.mean:.1f}",
            f"{self.bad_day:.1f}",
            f"{self.podium:.0%}",
            f"{self.points:.0%}",
        )

    @property
    def actions(self) -> tuple[str, ...]:
        return (self.action, *self.merged)

    @property
    def parsed(self) -> ParsedAction:
        return _parse_action(self.action)


@dataclass(frozen=True)
class PageContext:
    """Values every section of the selected replay reads from the cached result."""

    code: str
    surname: str
    team: str
    current: str
    stops_done: int
    pit_loss_s: float
    n_cars: int
    never_stop_allowed: bool
    simulations: int

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> PageContext:
        code = str(result["driver"]).upper()
        return cls(
            code=code,
            surname=_surname(code, str(result.get("driver_name") or code)),
            team=str(result.get("selected_color") or DEFAULT_TEAM_COLOR).upper(),
            current=str(result.get("tire_compound") or "").upper(),
            stops_done=int(result.get("stops_done") or 0),
            pit_loss_s=float(result.get("pit_loss_s") or 0.0),
            n_cars=int(result.get("n_cars") or 20),
            never_stop_allowed=bool(result.get("never_stop_allowed")),
            simulations=int(result.get("simulation_count") or 0),
        )


def _options_from_result(result: dict[str, Any]) -> list[Option]:
    rows = tuple(result.get("options") or ())
    quantiles = tuple(result.get("option_quantiles") or ())
    plans = tuple(result.get("option_plans") or ())
    options: list[Option] = []
    for index, row in enumerate(rows):
        action, mean, _spread, bad_day, podium, points, interval = row
        stop_laps, compounds = plans[index] if index < len(plans) else ((), ())
        sample = tuple(int(value) for value in quantiles[index]) if index < len(quantiles) else ()
        options.append(
            Option(
                action=str(action),
                mean=float(mean),
                bad_day=float(bad_day),
                podium=float(podium),
                points=float(points),
                interval=str(interval),
                quantiles=sample,
                stop_laps=tuple(int(lap) for lap in stop_laps),
                compounds=tuple(str(compound).upper() for compound in compounds),
            )
        )
    return options


def _merge_options(options: Sequence[Option]) -> list[Option]:
    """Merge options whose four shown stats match at display precision (decision 2).

    The group keeps the best-ranked member's numbers. "stay out" names the group when present,
    since it is the more concrete action.
    """
    groups: dict[tuple[str, str, str, str], list[Option]] = {}
    for option in options:
        groups.setdefault(option.display_key(), []).append(option)
    merged: list[Option] = []
    for members in groups.values():
        lead = next((item for item in members if item.action == "stay out"), members[0])
        first = members[0]
        merged.append(
            Option(
                action=lead.action,
                mean=first.mean,
                bad_day=first.bad_day,
                podium=first.podium,
                points=first.points,
                interval=first.interval,
                quantiles=first.quantiles,
                stop_laps=lead.stop_laps,
                compounds=lead.compounds,
                merged=tuple(item.action for item in members if item is not lead),
            )
        )
    return merged


def _end_compounds(option: Option, current: str) -> tuple[str, ...]:
    """Compounds the option ends on: the planned last set, or the current set (decision 13)."""
    ends: list[str] = []
    for action in option.actions:
        parsed = _parse_action(action)
        if parsed.compound is not None:
            compound = parsed.compound
        elif parsed.kind != "stay" and option.compounds:
            compound = option.compounds[-1]
        else:
            compound = current
        if compound and compound not in ends:
            ends.append(compound)
    return tuple(ends) or (current,)


def _option_title(action: str, current: str) -> str:
    parsed = _parse_action(action)
    tyres = _plural(parsed.compound)
    if parsed.kind == "stay":
        return f"Stay out on {_plural(current)}"
    if parsed.kind == "wait":
        return "Stay out for now, decide next lap"
    if parsed.kind == "pit" and parsed.delay == 0:
        return f"Box this lap for {tyres}"
    if parsed.kind == "pit" and parsed.delay == 1:
        return f"Box next lap for {tyres}"
    if parsed.kind == "pit":
        return f"Box in {parsed.delay} laps for {tyres}"
    return action.capitalize()


def _option_gerund(action: str, current: str) -> str:
    """The option as a phrase inside a sentence: "boxing this lap for Hards"."""
    title = _option_title(action, current)
    if title.startswith("Stay out on"):
        return "staying out on" + title.removeprefix("Stay out on")
    if title.startswith("Stay out for now"):
        return "waiting a lap"
    if title.startswith("Box"):
        return "boxing" + title.removeprefix("Box")
    return action


def _option_why(option: Option, *, context: PageContext) -> str:
    parsed = option.parsed
    if parsed.kind == "stay":
        if "wait and decide next lap" in option.merged:
            return "No more stops. Waiting a lap and deciding then gives the same result."
        return f"No more stops. Run the {_plural(context.current)} to the flag."
    if parsed.kind == "wait":
        return "Keep going and look at this again next lap."
    if parsed.kind == "pit" and parsed.delay == 0:
        lead = "Another" if context.stops_done else "A"
        return f"{lead} stop costs about {context.pit_loss_s:.0f} seconds in the pits."
    if parsed.kind == "pit":
        lap_word = "lap" if parsed.delay == 1 else "laps"
        return (
            f"Run {parsed.delay} more {lap_word} on the {_plural(context.current)}, then fit "
            f"{_plural(parsed.compound)}."
        )
    return ""


def _distribution(quantiles: Sequence[int], n_cars: int) -> list[float]:
    """Share of simulated races at each position, from the option's 100 finish quantiles.

    Each quantile stands for 1% of races, so shares have 1% resolution and sum to 1.
    """
    if not quantiles:
        return [0.0] * n_cars
    total = len(quantiles)
    return [
        sum(1 for value in quantiles if value == position) / total
        for position in range(1, n_cars + 1)
    ]


def _headline(best: Option, *, close_call: bool, never_stop_allowed: bool) -> str:
    """Decision 6: close call, then box now or next lap, then stay out for now or to the flag."""
    parsed = best.parsed
    if close_call:
        return "Too close to call"
    if parsed.kind == "pit" and parsed.delay == 0:
        return "Box this lap"
    if parsed.kind == "pit" and parsed.delay == 1:
        return "Box next lap"
    if best.stop_laps or not never_stop_allowed:
        return "Stay out for now"
    return "Stay out to the flag"


def _plan_segments(
    cutoff_lap: int,
    laps_total: int,
    current: str,
    stop_laps: Sequence[int],
    compounds: Sequence[str],
) -> list[PlanSegment]:
    """The selected driver's planned running from the cutoff ``N + 0.5`` to the flag.

    A stop at the end of lap ``s`` switches compound at ``s + 0.5``.
    """
    segments: list[PlanSegment] = []
    start = cutoff_lap + 0.5
    compound = current
    for stop_lap, next_compound in zip(stop_laps, compounds, strict=False):
        end = min(stop_lap + 0.5, laps_total + 0.5)
        if end > start:
            segments.append((start, end, compound))
            start = end
        compound = next_compound.upper()
    if laps_total + 0.5 > start:
        segments.append((start, laps_total + 0.5, compound))
    return segments


def _latest_trace_row(result: dict[str, Any], code: str) -> dict[str, object] | None:
    """The selected driver's latest completed-lap row in the gap trace, if any."""
    rows = cast(Sequence[dict[str, object]], result.get("race_trace_rows") or ())
    own = [
        row
        for row in rows
        if str(row.get("driver_code", "")).upper() == code and row.get("is_latest")
    ]
    return own[-1] if own else None


def _risk_name(risk: float) -> str:
    """Slider value to its label: below 0.34 aggressive, above 0.66 cautious, else balanced."""
    return "aggressive" if risk < 0.34 else "cautious" if risk > 0.66 else "balanced"


# ---------------------------------------------------------------------------------------------
# Decision band (prototype B, the race strip)
# ---------------------------------------------------------------------------------------------


def _pct(value: float) -> str:
    return f"{value:.2f}%"


def _histogram_html(
    shares: Sequence[float],
    *,
    expected: float,
    podium: float,
    points: float,
    team_color: str,
    band: str,
) -> str:
    """Finish histogram as HTML boxes (Streamlit's sanitiser strips inline SVG).

    Bar height is the share of simulated races at each position, scaled to the tallest bar; the
    expected-finish marker sits at ``(expected - 0.5) / n`` of the width. Points positions (P1 to
    P10) use the team color, the rest grey; both are lightened to 3:1 on the band. The bracket
    labels use the exact podium and points shares, not the 1%-resolution bar heights.
    """
    n_cars = len(shares)
    peak = max(max(shares), 0.01)
    points_color = readable_on(team_color, band)
    rest_color = readable_on(REST_GREY, band)
    top_index = max(range(n_cars), key=lambda index: shares[index])
    bars = "".join(
        f'<div class="hbar" style="height:{_pct(share / peak * 100)};'
        f'background:{points_color if index < 10 else rest_color}" '
        f'title="P{index + 1}: {share:.0%} of races"></div>'
        for index, share in enumerate(shares)
    )
    peak_left = (top_index + 0.5) / n_cars * 100
    marker_left = (expected - 0.5) / n_cars * 100
    keys = (1, min(10, n_cars), n_cars)
    axis = "".join(
        f"<span>{'P' + str(position) if position in keys else ''}</span>"
        for position in range(1, n_cars + 1)
    )
    label = (
        f"Finish distribution: most likely P{top_index + 1}, podium {podium:.0%}, "
        f"points {points:.0%}, expected P{expected:.1f}"
    )
    return (
        f'<div class="hist" role="img" aria-label="{_esc(label)}">'
        f'<div class="hist-plot" style="--n:{n_cars}">{bars}'
        f'<span class="hpeak" style="left:{_pct(peak_left)}">{shares[top_index]:.0%}</span>'
        f'<div class="hexp" style="left:{_pct(marker_left)}"><span>expected P{expected:.1f}</span>'
        "</div></div>"
        f'<div class="hist-axis" style="--n:{n_cars}">{axis}</div>'
        f'<div class="hist-bracket pod" style="width:{_pct(3 / n_cars * 100)}">'
        f"Podium (P1 to P3): {podium:.0%}</div>"
        f'<div class="hist-bracket pts" style="width:{_pct(min(10, n_cars) / n_cars * 100)}">'
        f"Points (P1 to P10): {points:.0%}</div></div>"
    )


def _race_strip_html(
    *,
    own_stints: Sequence[dict[str, object]],
    plan: Sequence[PlanSegment],
    cutoff_lap: int,
    laps_total: int,
    team_color: str,
    band: str,
    pit_loss_s: float,
    tie_window: tuple[int, int] | None,
    safety_line: str,
) -> str:
    """Laps 1 to the flag as HTML boxes: stints run, stops, now, the plan, window bracket.

    Positions are percentages of the strip: lap boundary ``v`` sits at
    ``(v - 0.5) / laps_total``, so lap ``k`` spans ``[k - 0.5, k + 0.5]``. Tyre colors are
    lightened to 3:1 on the band.
    """

    def x(value: float) -> float:
        return max(0.0, min(100.0, (value - 0.5) / laps_total * 100))

    def tyre(compound: str) -> str:
        return readable_on(TIRE_COLORS.get(compound, FOG), band)

    track: list[str] = []
    above: list[str] = []
    below: list[str] = []
    for index, stint in enumerate(own_stints):
        start, end = float(cast(Any, stint["start_lap"])), float(cast(Any, stint["end_lap"]))
        compound = str(stint["compound"]).upper()
        track.append(
            f'<div class="rs-run" style="left:{_pct(x(start))};width:{_pct(x(end) - x(start))};'
            f'background:{tyre(compound)}"></div>'
        )
        if end - start >= 6:
            first = int(cast(Any, stint["first_lap"]))
            last = stint.get("last_visible_lap")
            span = f"laps {first} to {last}" if last is not None else f"from lap {first}"
            above.append(f'<span style="left:{_pct(x(start))}">{_plural(compound)}, {span}</span>')
        if index > 0:
            track.append(f'<div class="rs-stop" style="left:{_pct(x(start))}"></div>')
            below.append(
                f'<span class="end" style="left:{_pct(x(start))}">stop, about '
                f"{pit_loss_s:.0f} s</span>"
            )
    for index, (start, end, compound) in enumerate(plan):
        track.append(
            f'<div class="rs-plan" style="left:{_pct(x(start))};width:{_pct(x(end) - x(start))};'
            f'--c:{tyre(compound)}"></div>'
        )
        laps = round(end - start)
        if end - start >= 6:
            text = (
                f"{_plural(compound)} for the last {laps} laps"
                if index == len(plan) - 1
                else f"{_plural(compound)}, {laps} laps"
            )
            above.append(f'<span style="left:calc({_pct(x(start))} + 8px)">{text}</span>')
        if index > 0:
            track.append(f'<div class="rs-stop planned" style="left:{_pct(x(start))}"></div>')
            below.append(
                f'<span style="left:calc({_pct(x(start))} + 6px)">stop, about '
                f"{pit_loss_s:.0f} s</span>"
            )
    if tie_window is not None and len(plan) > 1:
        left, right = x(tie_window[0] - 0.5), x(tie_window[1] + 0.5)
        track.append(
            f'<div class="rs-window" style="left:{_pct(left)};width:{_pct(right - left)};'
            f'border-color:{readable_on(team_color, band)}"></div>'
        )
        below.append(
            f'<span class="window" style="left:{_pct(left)}">any stop here gives about the same '
            "finish</span>"
        )
    now = x(cutoff_lap + 0.5)
    track.append(f'<div class="rs-now" style="left:{_pct(now)}"></div>')
    below.append(f'<span style="left:calc({_pct(now)} + 6px)">now, after lap {cutoff_lap}</span>')
    return (
        f'<div class="rstrip" role="img" aria-label="Laps 1 to {laps_total}: stints run so far, '
        f'now after lap {cutoff_lap}, and the plan to the flag">'
        f'<div class="rs-above">{"".join(above)}</div>'
        f'<div class="rs-track">{"".join(track)}</div>'
        f'<div class="rs-below">{"".join(below)}</div>'
        f'<div class="rs-foot"><span>Lap 1</span><span>{_esc(safety_line)}</span>'
        f"<span>{laps_total}</span></div></div>"
    )


def _race_strip_sentence(
    own_stints: Sequence[dict[str, object]],
    plan: Sequence[PlanSegment],
    pit_loss_s: float,
) -> str:
    """Phone version of the race strip as one sentence (COPY_V2 "Phone text version")."""
    parts: list[str] = []
    for stint in own_stints:
        last = stint.get("last_visible_lap")
        first = int(cast(Any, stint["first_lap"]))
        tyres = _plural(str(stint["compound"]))
        parts.append(
            f"{tyres} for laps {first} to {last}"
            if last is not None
            else f"{tyres} from lap {first}"
        )
    stop = f"a stop of about {pit_loss_s:.0f} seconds"
    sentence = f", {stop}, then ".join(parts) if parts else "No laps run yet"
    if len(plan) <= 1:
        laps = round(plan[0][1] - plan[0][0]) if plan else 0
        tail = f" with no further stop: {laps} laps to go" if laps else ""
        return f"{sentence}{tail}."
    planned = [
        f"{stop} after lap {int(start - 0.5)}, then {_plural(compound)} for "
        f"{round(end - start)} laps"
        for start, end, compound in plan[1:]
    ]
    return f"{sentence}. Plan: {', then '.join(planned)}."


def _tyre_line(result: dict[str, Any], current: str) -> str:
    """Current tyre wear in plain words (COPY_V2 strip label on the current stint)."""
    rate, spread = result.get("tire_rate"), result.get("tire_sd")
    if rate is None or spread is None:
        return f"Tyres: the {_plural(current)} are too new to measure wear yet."
    return (
        f"Tyres: the {_plural(current)} are losing about {float(rate):.2f} s a lap, give or take "
        f"{float(spread):.2f} s."
    )


def _strip_title(best: Option, context: PageContext) -> str:
    parsed = best.parsed
    if best.stop_laps:
        tyres = _plural(best.compounds[0] if best.compounds else parsed.compound)
        if parsed.kind == "pit" and parsed.delay == 0:
            return f"{context.surname} stops this lap for {tyres}"
        if parsed.kind == "pit" and parsed.delay == 1:
            return f"{context.surname} stops next lap for {tyres}"
        if parsed.kind == "pit":
            return f"{context.surname} stops in {parsed.delay} laps for {tyres}"
        return f"{context.surname} stops after lap {best.stop_laps[0]} for {tyres}"
    if context.never_stop_allowed:
        count = NUMBER_WORDS.get(context.stops_done, str(context.stops_done))
        noun = "stop" if context.stops_done == 1 else "stops"
        if context.stops_done:
            return f"{context.surname} has made {count} {noun} and needs no more"
        return f"{context.surname} needs no stop"
    return f"{context.surname} still has to stop once"


def _decision_band_html(
    result: dict[str, Any], merged: Sequence[Option], options: Sequence[Option] = ()
) -> str:
    """The answer, its finish histogram and the race strip (prototype B).

    The safety-car line converts the per-lap rate ``p`` into the chance of at least one before
    the flag over the ``L`` laps left: ``1 - (1 - p) ** L``. The close-call note names the
    optimizer's unmerged runner-up, the option the close-call gap was measured against.
    """
    context = PageContext.from_result(result)
    best = merged[0]
    team, band = context.team, band_background(context.team)
    cutoff, total = int(result["cutoff_lap"]), int(result["laps_total"])
    close_call = bool(result.get("close_call_two_se"))
    headline = _headline(best, close_call=close_call, never_stop_allowed=context.never_stop_allowed)
    tie_window = _tie_window(result.get("waiting_tie_window_laps"))

    pit_now = [item for item in merged if item.parsed.kind == "pit" and item.parsed.delay == 0]
    if best.stop_laps and tie_window is not None:
        lede = (
            f"Any stop between laps {tie_window[0]} and {tie_window[1]} gives about the same "
            "result, so there's no rush. Look again next lap."
        )
    elif not best.stop_laps and context.never_stop_allowed and context.current:
        fresh = "fresh " if int(result.get("tire_age") or 0) <= 3 else ""
        lede = (
            f"{context.surname} is on {fresh}{_plural(context.current)} and has used both "
            "compounds, so there's no need to stop again."
        )
        if pit_now and pit_now[0] is not best:
            word = "Another" if context.stops_done else "A"
            lede += f" {word} stop costs {pit_now[0].mean - best.mean:.1f} places on average."
    else:
        lede = str(result.get("reason") or "Keep the current tyres to the flag.")
    close = ""
    places = result.get("close_call_places")
    runner_up = options[1] if len(options) > 1 else (merged[1] if len(merged) > 1 else None)
    if places is not None and runner_up is not None:
        close = (
            f'<p class="close-call">Close call: '
            f"{_esc(_option_gerund(runner_up.action, context.current))} "
            f"is only {float(places):.1f} places worse on average.</p>"
        )

    position = result.get("position")
    latest = _latest_trace_row(result, context.code)
    facts: list[str] = []
    if isinstance(position, int) and position >= 1:
        if position == 1:
            facts.append("<li><b>1st</b><span>leading the race</span></li>")
        elif latest is not None:
            gap = float(cast(Any, latest.get("gap_to_leader_s", 0.0)))
            facts.append(
                f"<li><b>{_ordinal(position)}</b><span>{gap:.1f} s behind the leader</span></li>"
            )
        else:
            facts.append(f"<li><b>{_ordinal(position)}</b><span>now</span></li>")
    facts.append(f"<li><b>P{best.mean:.1f}</b><span>expected finish</span></li>")
    facts.append(f"<li><b>{best.points:.0%}</b><span>points chance</span></li>")

    histogram = _histogram_html(
        _distribution(best.quantiles, context.n_cars),
        expected=best.mean,
        podium=best.podium,
        points=best.points,
        team_color=team,
        band=band,
    )
    own_stints = sorted(
        (
            dict(row)
            for row in cast(Sequence[dict[str, object]], result.get("stint_rows") or ())
            if str(row.get("driver_code", "")).upper() == context.code
        ),
        key=lambda row: float(cast(Any, row["start_lap"])),
    )
    plan = _plan_segments(cutoff, total, context.current, best.stop_laps, best.compounds)
    sc = float(result.get("safety_car_probability") or 0.0)
    event_chance = 1.0 - (1.0 - sc) ** max(0, total - cutoff)
    safety_line = (
        f"Safety car: {sc:.1%} per lap, about {_share_phrase(event_chance)} races before the flag"
        if sc > 0
        else "Safety car: none at this track's past rate"
    )
    strip = _race_strip_html(
        own_stints=own_stints,
        plan=plan,
        cutoff_lap=cutoff,
        laps_total=total,
        team_color=team,
        band=band,
        pit_loss_s=context.pit_loss_s,
        tie_window=tie_window if best.stop_laps else None,
        safety_line=safety_line,
    )
    notes = f'<p class="thin-note">{_esc(_tyre_line(result, context.current))}</p>'
    if bool(result.get("fallback")) and result.get("tire_rate") is not None:
        notes += f'<p class="thin-note">{_esc(THIN_TYRE_DATA_COPY)}</p>'
    hist_title = (
        f"{_sentence_case(_option_gerund(best.action, context.current))}, {context.surname} scores "
        f"points in about {_share_phrase(best.points)} races"
    )
    return (
        f'<div class="decision-band" style="--team:{team};--team-fill:{team_fill(team)};'
        f'--band:{band};--band-fog:{readable_on(FOG, band, 4.5)}">'
        '<div class="decision-inner">'
        '<div class="answer">'
        f'<p class="context">{_esc(result["race_name"])} {int(result["race_season"])}, '
        f"after lap {cutoff} of {total}, {_risk_name(float(result['risk']))} risk setting</p>"
        f'<div class="driver-line"><span class="driver-code">{_esc(context.code)}</span>'
        f"{_esc(result.get('driver_name') or context.code)}, "
        f"{_esc(result.get('team_name') or '')}</div>"
        f"<h1>{_esc(headline)}</h1>"
        f'<p class="lede">{_esc(lede)}</p>{close}'
        f'<ul class="facts">{"".join(facts)}</ul></div>'
        '<div class="dist">'
        f'<h2 class="band-title">{_esc(hist_title)}</h2>'
        f'<p class="band-sub">Share of {context.simulations:,} simulated races ending in each '
        "position</p>"
        f"{histogram}</div>"
        '<div class="strip">'
        f'<h2 class="band-title">{_esc(_strip_title(best, context))}</h2>'
        f'<p class="band-sub">Laps 1 to {total}. Solid bars are laps already run; the dashed bar '
        "is the plan.</p>"
        f"{strip}"
        '<p class="strip-sentence">'
        f"{_esc(_race_strip_sentence(own_stints, plan, context.pit_loss_s))} "
        f"{_esc(safety_line)}.</p>"
        f"{notes}</div></div></div>"
    )


def _tie_window(value: object) -> tuple[int, int] | None:
    if isinstance(value, tuple | list) and len(value) == 2:
        return int(value[0]), int(value[1])
    return None


# ---------------------------------------------------------------------------------------------
# Options section
# ---------------------------------------------------------------------------------------------


def _chip_html(compound: str) -> str:
    color = TIRE_COLORS.get(compound, FOG)
    letter = TIRE_LETTERS.get(compound, "?")
    name = TIRE_NAMES.get(compound, compound.title())
    return (
        f'<span class="tire-chip" style="--tire:{color}" aria-label="{_esc(name)} '
        f'tyres">{letter}</span>'
    )


def _probability_strip_html(option: Option, n_cars: int, *, full: bool) -> str:
    """One cell per finishing position, shaded by the share of races ending there.

    Shade runs from the weakest to the strongest fan-band color as ``share / peak``; the
    expected-finish marker sits at ``(mean - 0.5) / n`` of the width. Bracket labels use the
    exact podium and points chances.
    """
    shares = _distribution(option.quantiles, n_cars)
    peak = max(max(shares), 0.01)
    cells = "".join(
        f'<div style="--p:{round(100 * share / peak)}%" title="P{index + 1}: {share:.0%} of '
        'races"></div>'
        for index, share in enumerate(shares)
    )
    marker = (option.mean - 0.5) / n_cars * 100
    described = ", ".join(f"P{index + 1} {share:.0%}" for index, share in enumerate(shares))
    keys = {1, 3, min(10, n_cars), n_cars}
    axis = "".join(
        f'<span class="{"k" if position in keys else ""}">P{position}</span>'
        for position in range(1, n_cars + 1)
    )
    brackets = (
        '<div class="brackets">'
        f'<span class="pod">Podium {option.podium:.0%}</span>'
        f'<span class="pts">Points (P1 to P10) {option.points:.0%}</span></div>'
        if full
        else ""
    )
    return (
        f'<div class="cellwrap"><div class="exp" style="left:{marker:.2f}%" '
        f'title="Expected P{option.mean:.1f}"></div>'
        f'<div class="cells" role="img" aria-label="Chance of each finishing position: '
        f'{_esc(described)}">{cells}</div></div>{brackets}<div class="axis">{axis}</div>'
    )


def _option_row_html(
    option: Option, *, recommended: bool, best_mean: float, context: PageContext
) -> str:
    title = _option_title(option.action, context.current)
    chips = "".join(_chip_html(compound) for compound in _end_compounds(option, context.current))
    if recommended:
        tag = '<span class="tag tag-rec">Recommended</span>'
    else:
        tag = f'<span class="tag tag-worse">{option.mean - best_mean:.1f} places worse</span>'
    why = _option_why(option, context=context)
    labels = ("Expected finish", "Bad-day finish", "Podium chance", "Points chance")
    help_text = (
        "Average over all simulated races",
        "Average of the worst 1 in 10 races",
        "Races ending P1 to P3",
        "Races ending in the top 10",
    )
    values = (
        f"P{option.mean:.1f}",
        f"P{option.bad_day:.1f}",
        f"{option.podium:.0%}",
        f"{option.points:.0%}",
    )
    stats = "".join(
        f'<div class="stat"><div class="big">{value}</div><div class="stat-label">{label}</div>'
        + (f'<div class="stat-help">{help_line}</div>' if recommended else "")
        + "</div>"
        for value, label, help_line in zip(values, labels, help_text, strict=True)
    )
    row_class = "option-row recommended" if recommended else "option-row compact"
    return (
        f'<article class="{row_class}"><div class="tire-chips">{chips}</div><div '
        'class="option-body">'
        f'<div class="option-title"><h3>{_esc(title)}</h3>{tag}</div>'
        f'<p class="option-copy">{_esc(why)}</p><div class="stats">{stats}</div>'
        f"{_probability_strip_html(option, context.n_cars, full=recommended)}</div></article>"
    )


def _range_text(option: Option) -> str:
    """The 9-in-10 range from the exact 5th and 95th percentile finishes ("P2-P17")."""
    match = re.fullmatch(r"P(\d+)-P(\d+)", option.interval)
    return f"P{match.group(1)} to P{match.group(2)}" if match else ""


def _numbers_table_html(options: Sequence[Option], context: PageContext) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{_esc(_option_title(option.action, context.current))}</td>"
        f"<td>P{option.mean:.1f}</td><td>P{option.bad_day:.1f}</td>"
        f"<td>{option.podium:.0%}</td><td>{option.points:.0%}</td>"
        f"<td>{_range_text(option)}</td></tr>"
        for option in options
    )
    if not context.never_stop_allowed:
        rows += (
            "<tr><td>Never stop: not allowed (two-compound rule)</td>"
            "<td></td><td></td><td></td><td></td><td></td></tr>"
        )
    return (
        '<details class="all-numbers"><summary>Show all numbers</summary><div class="table-wrap">'
        '<table class="detail-table"><thead><tr><th scope="col">Option</th>'
        '<th scope="col">Expected finish</th><th scope="col">Bad-day finish</th>'
        '<th scope="col">Podium chance</th><th scope="col">Points chance</th>'
        '<th scope="col">9-in-10 range</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div></details>"
    )


def _options_section_html(
    result: dict[str, Any], options: Sequence[Option], merged: Sequence[Option]
) -> str:
    context = PageContext.from_result(result)
    rows = "".join(
        _option_row_html(option, recommended=index == 0, best_mean=merged[0].mean, context=context)
        for index, option in enumerate(merged[:MAX_OPTION_ROWS])
    )
    if not context.never_stop_allowed:
        rows += (
            '<article class="option-row compact"><div class="tire-chips"></div>'
            '<div class="option-body"><div class="option-title"><h3>Never stop</h3>'
            '<span class="tag tag-worse">Not allowed</span></div>'
            '<p class="option-copy">Dry races require two different tyre compounds.</p>'
            "</div></article>"
        )
    weakest, _middle, strongest = fan_band_colors(context.team)
    return (
        '<section class="page-section" id="options" '
        f'style="--team:{context.team};--team-fill:{team_fill(context.team)};'
        f'--team-line:{readable_on(context.team)};--cell-lo:{weakest};--cell-hi:{strongest}">'
        "<h2>Your options</h2>"
        f'<p class="section-sub">Best first. Each one is {context.simulations:,} simulated races '
        "from this lap to the flag.</p>"
        f"{rows}{_numbers_table_html(options, context)}</section>"
    )


# ---------------------------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------------------------


def _chart_heading(title: str, sub: str) -> str:
    return f'<h3 class="chart-title">{_esc(title)}</h3><p class="chart-sub">{_esc(sub)}</p>'


def _gap_titles(result: dict[str, Any]) -> tuple[str, str]:
    context = PageContext.from_result(result)
    surname = context.surname
    rows = cast(Sequence[dict[str, object]], result.get("race_trace_rows") or ())
    latest = _latest_trace_row(result, context.code)
    last_lap = max((int(cast(Any, row.get("lap", 0))) for row in rows), default=0)
    sub = f"Gap to the leader, laps 1 to {last_lap}"
    position = result.get("position")
    if latest is None:
        return f"{surname} has no completed laps yet", sub
    gap = float(cast(Any, latest.get("gap_to_leader_s", 0.0)))
    if position == 1 or gap <= 0.0:
        return f"{surname} leads the race", sub
    # The gap is measured on the driver's latest completed lap, so name that lap's leader (the
    # car with zero gap on it), not the current running order's P1.
    own_lap = int(cast(Any, latest.get("lap", 0)))
    lap_leaders = [
        str(row.get("driver_code", "")).upper()
        for row in rows
        if int(cast(Any, row.get("lap", 0))) == own_lap
        and float(cast(Any, row.get("gap_to_leader_s", 1.0))) == 0.0
    ]
    leader = lap_leaders[0] if lap_leaders else None
    leader_name = _surname(leader) if leader else "the leader"
    place = f"{_ordinal(position)}, " if isinstance(position, int) else ""
    return f"{surname} is {place}{gap:.1f} s behind {leader_name}", sub


def _stint_titles(result: dict[str, Any]) -> tuple[str, str]:
    surname = PageContext.from_result(result).surname
    rows = cast(Sequence[dict[str, object]], result.get("stint_rows") or ())
    counts: dict[str, int] = {}
    for row in rows:
        driver = str(row.get("driver_code", "")).upper()
        counts[driver] = counts.get(driver, 0) + 1
    stopped = sum(1 for value in counts.values() if value >= 2)
    current = _plural(str(result.get("tire_compound") or ""))
    lead = (
        f"{stopped} of {len(counts)} drivers have stopped" if stopped else "No one has stopped yet"
    )
    return f"{lead}; {surname} is on {current}", "Tyre stints so far, in running order"


def _fan_titles(result: dict[str, Any], fan: FanChartData) -> tuple[str, str]:
    surname = PageContext.from_result(result).surname
    final = round(fan.p50[-1]) if fan.p50 else None
    title = (
        f"{surname} most likely finishes around P{final}"
        if final
        else "Projected finishing position"
    )
    return title, "Projected position for each lap left. Shaded bands hold 8, 5 and 2 in 10 races."


def _render_charts(result: dict[str, Any], merged: Sequence[Option]) -> None:
    context = PageContext.from_result(result)
    team, code = context.team, context.code
    cutoff = int(result["cutoff_lap"])
    st.html(
        '<section class="page-section" id="race-so-far"><h2>The race so far</h2>'
        f'<p class="section-sub">Only laps finished by the end of lap {cutoff} are '
        "shown.</p></section>"
    )
    trace_col, stint_col = st.columns(2, gap="large")
    with trace_col:
        trace = build_race_trace_chart(
            cast(tuple[dict[str, object], ...], result.get("race_trace_rows") or ()),
            selected_driver=code,
            selected_color=team,
        )
        if trace is None:
            st.html(
                '<p class="chart-sub">No laps are complete yet, so there&#x27;s no gap chart.</p>'
            )
        else:
            st.html(_chart_heading(*_gap_titles(result)))
            st.altair_chart(trace, theme="streamlit", width="stretch")
    with stint_col:
        best = merged[0]
        plan = _plan_segments(
            cutoff,
            int(result["laps_total"]),
            context.current,
            best.stop_laps,
            best.compounds,
        )
        stint_chart = build_stint_chart(
            cast(tuple[dict[str, object], ...], result.get("stint_rows") or ()),
            cutoff_lap=cutoff,
            laps_total=int(result["laps_total"]),
            driver_order=cast(tuple[str, ...], result.get("driver_order") or ()),
            selected_driver=code,
            plan_segments=plan,
            selected_color=team,
        )
        if stint_chart is None:
            st.html('<p class="chart-sub">No tyre stints yet at this lap.</p>')
        else:
            st.html(_chart_heading(*_stint_titles(result)))
            st.altair_chart(stint_chart, theme="streamlit", width="stretch")

    fan_data = result.get("fan_chart_data")
    if isinstance(fan_data, dict):
        fan_data = FanChartData(**fan_data)
    st.html('<section class="page-section" id="certainty"><h2>How sure are we?</h2></section>')
    if isinstance(fan_data, FanChartData):
        st.html(_chart_heading(*_fan_titles(result, fan_data)))
        st.altair_chart(
            build_fan_chart(fan_data, team_color=team), theme="streamlit", width="stretch"
        )
    else:
        st.html('<p class="chart-sub">No projection for this lap.</p>')


def _render_selected(result: dict[str, Any]) -> None:
    if not result.get("available"):
        st.html(f'<p class="section-sub">{CUTOFF_UNAVAILABLE_COPY}</p>')
        return
    options = _options_from_result(result)
    if not result.get("strategy_available") or not options:
        st.html(f'<p class="section-sub">{NO_STRATEGY_COPY}</p>')
        return
    merged = _merge_options(options)
    st.html(_decision_band_html(result, merged, options))
    st.html(_options_section_html(result, options, merged))
    _render_charts(result, merged)


# ---------------------------------------------------------------------------------------------
# Model report and glossary
# ---------------------------------------------------------------------------------------------


def _bar_pair_html(model: float, grid: float, label: str) -> str:
    """Model and starting-grid Brier scores as two bars; shorter is better."""
    peak = max(model, grid) * 1.08
    return (
        f'<div class="pair" role="img" aria-label="{_esc(label)}">'
        f'<span class="pl">This model</span><div class="pt"><div class="pb team" '
        f'style="width:{_pct(model / peak * 100)}"></div><b>{model:.3f}</b></div>'
        f'<span class="pl">Starting grid</span><div class="pt"><div class="pb grey" '
        f'style="width:{_pct(grid / peak * 100)}"></div><b>{grid:.3f}</b></div></div>'
    )


def _coverage_html(value: float) -> str:
    """Interval coverage against its 85% to 95% target on a 70% to 100% scale."""

    def x(share: float) -> float:
        return (min(1.0, max(0.7, share)) - 0.7) / 0.3 * 100

    return (
        '<div class="cover" role="img" '
        f'aria-label="Range held the real finish {value:.0%} of the time; target 85 to 95%">'
        f'<span class="ct" style="left:{_pct(x(0.9))}">target 85 to 95%</span>'
        '<div class="ctrack"></div>'
        f'<div class="czone" style="left:{_pct(x(0.85))};width:{_pct(x(0.95) - x(0.85))}"></div>'
        f'<div class="cmark" style="left:{_pct(x(value))}"></div>'
        f'<span class="cv" style="left:{_pct(x(value))}">{value:.0%}</span>'
        '<span class="cl">70%</span><span class="cr">100%</span></div>'
    )


def _dots_html(fill: float, label: str) -> str:
    """Ten dots, ``fill`` of them filled in team color (partial fill on the last one)."""
    dots = "".join(
        f'<span style="--f:{_pct(max(0.0, min(1.0, fill - index)) * 100)}"></span>'
        for index in range(10)
    )
    return f'<div class="dots" role="img" aria-label="{_esc(label)}">{dots}</div>'


def _timing_html(laps: float) -> str:
    """Typical stop-timing error as a band around the team's stop, on a +/-8 lap scale."""
    half = min(8.0, laps) / 8 * 50
    return (
        '<div class="timing" role="img" '
        f'aria-label="Suggested lap typically within {laps:.1f} laps of the team stop">'
        '<span class="tt">team stopped</span><div class="ttrack"></div>'
        f'<div class="tband" style="left:{_pct(50 - half)};width:{_pct(2 * half)}"></div>'
        '<div class="tmid"></div>'
        f'<span class="tl" style="left:{_pct(50 - half)}">{laps:.1f} laps early</span>'
        f'<span class="tl" style="left:{_pct(50 + half)}">{laps:.1f} laps late</span></div>'
    )


def _brier_verdict(model: float, grid: float) -> tuple[str, bool]:
    """(verdict, caution) for a Brier score against the starting-grid baseline; lower is better."""
    if model < grid:
        return "Better than starting order", False
    return "No better than starting order", True


def _coverage_verdict(value: float) -> tuple[str, bool]:
    """(verdict, caution) for 9-in-10 range coverage against the 85% to 95% target."""
    if 0.85 <= value <= 0.95:
        return "On target", False
    if value < 0.85:
        return ("Slightly overconfident", True) if value >= 0.8 else ("Overconfident", True)
    return ("Slightly cautious", True) if value <= 0.97 else ("Too cautious", True)


def _agreement_verdict(value: float) -> tuple[str, bool]:
    """(verdict, caution) for how often the top call matched the team's actual call."""
    if value >= 0.6:
        return "Usually matches the pit wall", False
    if value >= 0.3:
        return "Sometimes matches the pit wall", True
    return "Rarely matches the pit wall", True


def _timing_verdict(laps: float) -> tuple[str, bool]:
    """(verdict, caution) for the mean absolute gap between suggested and actual stop laps."""
    if laps <= 1.5:
        return "Close on timing", False
    if laps <= 3.0:
        return "A few laps off", True
    return "Often several laps off", True


def _metric_html(
    number: str, verdict: str, meaning: str, graphic: str, *, caution: bool = False
) -> str:
    tone = "caution" if caution else "better"
    return (
        f'<div class="metric"><div class="metric-number">{_esc(number)}</div>'
        f'<div class="verdict {tone}">{_esc(verdict)}</div><div class="metric-vis">{graphic}</div>'
        f'<p class="metric-copy">{_esc(meaning)}</p></div>'
    )


def _model_report_html(report: dict[str, Any], team_color: str = DEFAULT_TEAM_COLOR) -> str:
    """Five back-test metrics, each with a verdict computed from its value (§6, decision 9)."""
    metrics = report["metrics"]
    podium = metrics["podium_brier"]
    top10 = metrics["top10_brier"]
    coverage = metrics["finish_interval_90"]
    team = metrics["team_strategy_comparison"]
    agreement = team["top_action_agreement"]["mean"]
    timing = team["stop_timing_error_laps"]["absolute"]["mean"]
    race_average = coverage["coverage"]["mean"]
    podium_model, podium_grid = podium["model"]["mean"], podium["baseline"]["mean"]
    points_model, points_grid = top10["model"]["mean"], top10["baseline"]["mean"]
    stops = team["event_count"]
    race_ids = list(report.get("race_ids", []))
    seasons = sorted({str(race_id)[:4] for race_id in race_ids})
    span = f"{seasons[0]} to {seasons[-1]}" if seasons else "recent"
    races = NUMBER_WORDS.get(len(race_ids), str(len(race_ids)))
    podium_verdict = _brier_verdict(podium_model, podium_grid)
    points_verdict = _brier_verdict(points_model, points_grid)
    coverage_verdict = _coverage_verdict(race_average)
    agreement_verdict = _agreement_verdict(agreement)
    timing_verdict = _timing_verdict(timing)
    metric_rows = [
        _metric_html(
            f"{podium_model:.3f}",
            podium_verdict[0],
            f"Podium calls score {podium_model:.3f} against {podium_grid:.3f} for just trusting "
            "the grid (Brier score; lower is better).",
            _bar_pair_html(
                podium_model,
                podium_grid,
                f"Podium Brier score: model {podium_model:.3f}, grid {podium_grid:.3f}; shorter is "
                "better",
            ),
            caution=podium_verdict[1],
        ),
        _metric_html(
            f"{points_model:.3f}",
            points_verdict[0],
            f"Points calls score {points_model:.3f} against {points_grid:.3f} for the grid.",
            _bar_pair_html(
                points_model,
                points_grid,
                f"Points Brier score: model {points_model:.3f}, grid {points_grid:.3f}; shorter is "
                "better",
            ),
            caution=points_verdict[1],
        ),
        _metric_html(
            f"{race_average:.0%}",
            coverage_verdict[0],
            f"Averaged over the {races} races, the 9-in-10 range held the real finish "
            f"{race_average:.0%} of the time ({coverage['covered']:,} of "
            f"{coverage['classified_finishers']:,} finishes overall). It should be 85% to 95%.",
            _coverage_html(race_average),
            caution=coverage_verdict[1],
        ),
        _metric_html(
            f"{agreement:.0%}",
            agreement_verdict[0],
            f"The model's top call matched what the team did at about "
            f"{_share_phrase(agreement)} of the {stops} real stops.",
            _dots_html(agreement * 10, f"About {_share_phrase(agreement)} calls matched the team"),
            caution=agreement_verdict[1],
        ),
        _metric_html(
            f"{timing:.1f} laps",
            timing_verdict[0],
            f"When a team stopped, the model's suggested lap was {timing:.1f} laps away on "
            "average.",
            _timing_html(timing),
            caution=timing_verdict[1],
        ),
    ]
    sample = (
        f"Tested on {races} {span} races using only what was known at each lap: "
        f"{metrics['brier_observation_count']:,} predictions and {stops} real pit stops."
    )
    return (
        '<section class="page-section" id="model-report" '
        f'style="--team-line:{readable_on(team_color)}">'
        f'<h2>How good is this model?</h2><p class="section-sub">{_esc(sample)}</p>'
        f'<div class="metrics">{"".join(metric_rows)}</div></section>'
    )


def _glossary_icon(kind: str) -> str:
    """Small HTML icons that repeat a mark used on the page (decision 10)."""
    cells = {"podium": 3, "points": 10}
    if kind in cells:
        filled = cells[kind]
        boxes = "".join(f'<i class="{"on" if index < filled else ""}"></i>' for index in range(20))
        return f'<div class="gi gi-cells gi-{kind}" aria-hidden="true">{boxes}</div>'
    if kind == "window":
        boxes = "".join(f'<i class="{"on" if 3 <= index <= 7 else ""}"></i>' for index in range(10))
        return f'<div class="gi gi-window" aria-hidden="true">{boxes}</div>'
    if kind in ("expected", "bad", "range"):
        return f'<div class="gi gi-track gi-{kind}" aria-hidden="true"><i></i><b></b></div>'
    return ""


def _glossary_html(team_color: str = DEFAULT_TEAM_COLOR) -> str:
    glossary = (
        ("expected", "Expected finish", "The average finishing position over all simulated races."),
        (
            "bad",
            "Bad-day finish",
            "The average finish in the worst 1 in 10 simulated races. It shows how far things can "
            "go wrong.",
        ),
        ("podium", "Podium chance", "The share of simulated races that end in P1, P2 or P3."),
        ("points", "Points chance", "The share that end in the top 10."),
        ("range", "9-in-10 range", "Nine in ten simulated races finish inside this range."),
        (
            "window",
            "Pit window",
            "The laps where stopping gives about the same expected finish, so the exact lap "
            "matters little.",
        ),
        (
            "",
            "Close call",
            "The top two options are so close that the simulation can't reliably separate them "
            "(less than two standard errors apart).",
        ),
        (
            "",
            "Risk setting",
            "Aggressive goes for the best average finish. Cautious protects against a bad day. "
            "Balanced weighs both.",
        ),
    )
    rows = "".join(
        f'<div class="glossary-row"><div class="glossary-icon">{_glossary_icon(kind)}</div>'
        f"<dt>{_esc(term)}</dt><dd>{_esc(definition)}</dd></div>"
        for kind, term, definition in glossary
    )
    return (
        '<section class="page-section" id="glossary" '
        f'style="--team-line:{readable_on(team_color)}">'
        "<h2>How to read this page</h2>"
        f'<dl class="glossary">{rows}</dl>'
        '<footer class="site-footer">Unofficial project, not affiliated with Formula 1. '
        "Data: FastF1, OpenF1, and Jolpica.</footer></section>"
    )


# ---------------------------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------------------------


def _report_summary() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(REPORT_PATH.read_text(encoding="utf-8")))


def _apply_styles() -> None:
    css_path = Path(__file__).with_name("dashboard.css")
    st.html(f"<style>{css_path.read_text(encoding='utf-8')}</style>")


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
            current_risk = _risk_name(risk)
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
        LOGGER.exception("Race catalog could not be read")
        catalog = None
    if catalog is None or catalog.empty:
        st.write(EMPTY_BODY)
        return

    team_color = DEFAULT_TEAM_COLOR
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
        if outcome.get("status") == "ready" and outcome.get("value"):
            team_color = str(outcome["value"].get("selected_color") or team_color).upper()
        _render_replay_outcome(outcome)
    except ValueError as err:
        LOGGER.exception("Replay controls could not be built")
        st.write(_schedule_failure_copy(err))
    except Exception:
        LOGGER.exception("Replay could not be built")
        _render_replay_failure()
    try:
        st.html(_model_report_html(_report_summary(), team_color))
        st.html(_glossary_html(team_color))
    except Exception:
        LOGGER.exception("Model report could not be built")
        st.caption(REPORT_MISSING_COPY)


if __name__ == "__main__":
    main()
