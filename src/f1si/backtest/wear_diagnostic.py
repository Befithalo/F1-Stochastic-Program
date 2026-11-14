"""Read-only retrospective proxy checks for cutoff wear bands."""

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from f1si.backtest.walk_forward import REGISTERED_RACE_IDS, PredictionRow, _race_laps_total
from f1si.data import asof
from f1si.pace.kalman import filter_stints
from f1si.pace.linear import fit_linear_pace


def build_leave_stint_out_reference(laps: pd.DataFrame, *, driver: str, stint: int) -> pd.DataFrame:
    """Return retrospective laps excluding the current driver's current stint."""
    driver_column = "driver" if "driver" in laps else "driver_number"
    if driver_column not in laps or "stint" not in laps:
        raise ValueError("reference laps require driver/driver_number and stint columns")
    reference = laps.loc[
        ~(
            (laps[driver_column].astype(str) == str(driver))
            & (pd.to_numeric(laps["stint"], errors="coerce") == stint)
        )
    ].copy()
    reference.attrs["label"] = "retrospective proxy"
    return reference


def summarize_wear_proxy(rows: pd.DataFrame) -> dict[str, object]:
    """Summarize wear-band evidence against a retrospective proxy."""
    required = {
        "race_id",
        "inside_proxy_band",
        "early_fit_error_s_per_lap",
        "current_stint_own_lap_share",
    }
    if not required.issubset(rows.columns):
        raise ValueError("wear-proxy rows are missing required evidence columns")
    frame = rows.copy()
    frame["inside_proxy_band"] = frame["inside_proxy_band"].astype("boolean")
    coverage_rows = frame.dropna(subset=["inside_proxy_band"])
    coverage_by_race: dict[str, dict[str, int | float]] = {}
    for race_id, group in coverage_rows.groupby("race_id", sort=True):
        covered = int(group["inside_proxy_band"].sum())
        denominator = len(group)
        coverage_by_race[str(race_id)] = {
            "covered": covered,
            "denominator": denominator,
            "coverage": covered / denominator,
        }

    bias = pd.to_numeric(frame["early_fit_error_s_per_lap"], errors="coerce")
    bias_by_race = frame.assign(_bias=bias).groupby("race_id", sort=True)["_bias"].mean()
    own_share = pd.to_numeric(frame["current_stint_own_lap_share"], errors="coerce")
    own_by_race = frame.assign(_share=own_share).groupby("race_id", sort=True)["_share"].mean()
    per_race_bias = {str(key): float(value) for key, value in bias_by_race.dropna().items()}
    per_race_share = {str(key): float(value) for key, value in own_by_race.dropna().items()}
    return {
        "label": "retrospective proxy, not latent ground truth",
        "coverage": {
            "covered": int(coverage_rows["inside_proxy_band"].sum()),
            "denominator": len(coverage_rows),
            "rate": (
                float(coverage_rows["inside_proxy_band"].mean())
                if not coverage_rows.empty
                else None
            ),
        },
        "coverage_denominator": len(coverage_rows),
        "coverage_by_race": coverage_by_race,
        "early_fit_bias_s_per_lap": (
            float(pd.Series(per_race_bias, dtype=float).mean()) if per_race_bias else None
        ),
        "early_fit_bias_by_race": per_race_bias,
        "own_lap_evidence": {
            "mean_share": float(pd.Series(per_race_share, dtype=float).mean())
            if per_race_share
            else None,
            "share_by_race": per_race_share,
            "measurement_count": int(own_share.notna().sum()),
            "interpretation": (
                "share of same-cutoff, same-compound clean laps from the current stint"
            ),
        },
    }


def wear_proxy_diagnostic(
    db_path: Path, predictions: tuple[PredictionRow, ...] | None
) -> dict[str, Any]:
    """Measure cutoff wear bands against later-fit references without modifying the filter."""
    accessor = asof.AsOfAccessor(db_path)
    if predictions is None:
        cutoffs: list[tuple[str, int]] = []
        for race_id in REGISTERED_RACE_IDS:
            first = accessor.snapshot(asof.AsOf(race_id, 0))
            laps_total = _race_laps_total(accessor, race_id, first)
            cutoffs.extend((race_id, lap) for lap in range(laps_total))
    else:
        cutoffs = sorted({(row.race_id, int(row.cutoff_lap)) for row in predictions})
    end_snapshots: dict[str, Any] = {}
    for race_id in REGISTERED_RACE_IDS:
        end = accessor.snapshot(asof.AsOf(race_id, asof.RACE_END))
        end_snapshots[race_id] = end

    reference_rates: dict[tuple[str, int, int], float | None] = {}
    measurements: list[dict[str, Any]] = []
    for race_id, cutoff in cutoffs:
        snapshot = accessor.snapshot(asof.AsOf(race_id, cutoff))
        fit = fit_linear_pace(snapshot)
        compound_counts = {item.compound: item.n_laps for item in fit.report.compounds}
        results = filter_stints(snapshot, fit)
        for result in results:
            if not result.is_current or not result.rows or result.n_used < 1:
                continue
            reference_key = (race_id, result.driver_number, result.stint)
            if reference_key not in reference_rates:
                end_snapshot = end_snapshots[race_id]
                reference = build_leave_stint_out_reference(
                    end_snapshot.laps,
                    driver=str(result.driver_number),
                    stint=result.stint,
                )
                reference_fit = fit_linear_pace(replace(end_snapshot, laps=reference))
                reference_rates[reference_key] = reference_fit.wear_rate(result.compound)
            proxy = reference_rates[reference_key]
            if proxy is None:
                continue
            last = result.rows[-1]
            band_low = last.rate_mean - 1.96 * last.rate_sd
            band_high = last.rate_mean + 1.96 * last.rate_sd
            own_count = result.n_used
            denominator = compound_counts.get(result.compound, 0)
            own_share = own_count / denominator if denominator else np.nan
            measurements.append(
                {
                    "race_id": race_id,
                    "driver": result.driver_number,
                    "stint": result.stint,
                    "cutoff_lap": cutoff,
                    "proxy_wear_s_per_lap": proxy,
                    "inside_proxy_band": band_low <= proxy <= band_high,
                    "early_fit_error_s_per_lap": (
                        last.rate_mean - proxy if result.n_used <= 8 else np.nan
                    ),
                    "current_stint_own_lap_share": own_share,
                }
            )
    summary = summarize_wear_proxy(
        pd.DataFrame(
            measurements,
            columns=[
                "race_id",
                "driver",
                "stint",
                "cutoff_lap",
                "proxy_wear_s_per_lap",
                "inside_proxy_band",
                "early_fit_error_s_per_lap",
                "current_stint_own_lap_share",
            ],
        )
    )
    summary["proxy_definition"] = (
        "existing fuel-plus-compound pace fit on race-end laps after excluding the evaluated "
        "driver stint; the remaining laps form retrospective proxy evidence"
    )
    summary["early_fit_definition"] = (
        "cutoff posterior mean minus retrospective proxy for estimates using at most eight "
        "clean laps"
    )
    summary["kalman_parameters_changed"] = False
    summary["tuned_on_evaluation_races"] = False
    summary["measurement_count"] = len(measurements)
    counts = (
        {
            str(race): int(count)
            for race, count in pd.DataFrame(measurements).groupby("race_id").size().items()
        }
        if measurements
        else {}
    )
    unavailable = [race for race in REGISTERED_RACE_IDS if counts.get(race, 0) == 0]
    coverage_by_race = cast(dict[str, Any], summary["coverage_by_race"])
    bias_by_race = cast(dict[str, Any], summary["early_fit_bias_by_race"])
    own_evidence = cast(dict[str, Any], summary["own_lap_evidence"])
    for race in REGISTERED_RACE_IDS:
        coverage_by_race.setdefault(race, {"covered": None, "denominator": 0, "coverage": None})
        bias_by_race.setdefault(race, None)
        cast(dict[str, Any], own_evidence["share_by_race"]).setdefault(race, None)
        counts.setdefault(race, 0)
    summary["per_race_measurements"] = counts
    summary["unavailable_races"] = {
        race: "no estimable leave-stint-out wear reference in the available clean laps"
        for race in unavailable
    }
    return summary
