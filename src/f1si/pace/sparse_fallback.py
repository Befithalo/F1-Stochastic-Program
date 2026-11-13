"""Cutoff-local, explicitly prior-driven pace model for unsupported joint fits."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Final

import numpy as np
from numpy.typing import NDArray

from f1si.data.asof import RaceSnapshot
from f1si.interfaces import DRY_COMPOUNDS
from f1si.pace.kalman import (
    GENERIC_FUEL_MEAN,
    GENERIC_RATE_MEAN,
    GENERIC_RATE_SD,
    GENERIC_SIGMA_S,
)
from f1si.pace.linear import _classify

PACE_OFFSET_SD_S: Final = 1.0  # [ASSUMED] broad driver-level uncertainty for unsupported fits


@dataclass(frozen=True)
class SparseFallbackReport:
    """Small model metadata shape consumed by the simulator's fitted-driver boundary."""

    driver_offsets: dict[int, float]


class SparsePaceFallback:
    """Generic fuel/wear model with driver centers from clean laps in one as-of snapshot."""

    def __init__(self, snapshot: RaceSnapshot) -> None:
        table = _classify(snapshot.laps)
        clean = table.loc[table["reason"].isna()].copy()
        clean["residual"] = np.array(
            [
                float(row.time)
                - GENERIC_FUEL_MEAN * (float(row.lap) - 1.0)
                - GENERIC_RATE_MEAN[str(row.compound)] * float(row.age)
                for row in clean.itertuples(index=False)
            ],
            dtype=np.float64,
        )
        raw_centers = {
            int(number): float(group["residual"].median())
            for number, group in clean.groupby("driver", sort=True)
        }
        center = float(median(raw_centers.values())) if raw_centers else 0.0
        numbers = [int(number) for number in snapshot.cars["driver_number"].tolist()]
        self.driver_offsets = {
            number: raw_centers.get(number, center) - center for number in numbers
        }
        self.report = SparseFallbackReport(self.driver_offsets)
        self.pace_offset_sd_s = PACE_OFFSET_SD_S
        self.clean_laps_by_driver = {
            int(number): len(group) for number, group in clean.groupby("driver", sort=True)
        }
        self.visible_clean_laps = len(clean)
        within_driver = np.array(
            [
                float(row.residual) - raw_centers[int(row.driver)]
                for row in clean[["driver", "residual"]].itertuples(index=False)
            ],
            dtype=np.float64,
        )
        if within_driver.size:
            residual_mad = float(np.median(np.abs(within_driver - np.median(within_driver))))
            self.sigma_sparse = max(GENERIC_SIGMA_S, 1.4826 * residual_mad)
        else:
            self.sigma_sparse = GENERIC_SIGMA_S
        self.wear_sd_by_compound = {name: GENERIC_RATE_SD for name in DRY_COMPOUNDS}

    def clean_laps_for(self, driver_number: int) -> int:
        """Number of clean laps for a driver visible in the supplied snapshot."""
        return self.clean_laps_by_driver.get(driver_number, 0)

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Return generic-prior lap means and sparse residual-noise standard deviations."""
        alpha = np.empty(driver.shape, dtype=np.float64)
        for number in np.unique(driver):
            try:
                alpha[driver == number] = self.driver_offsets[int(number)]
            except KeyError as err:
                raise ValueError(
                    f"Driver number {int(number)} was not in the cutoff snapshot"
                ) from err
        wear = np.empty(driver.shape, dtype=np.float64)
        for name in np.unique(compound):
            compound_name = str(name)
            if compound_name not in self.wear_sd_by_compound:
                raise ValueError(f"Compound {compound_name!r} is not a supported dry compound")
            wear[compound == name] = GENERIC_RATE_MEAN[compound_name]
        mean = (
            alpha
            + GENERIC_FUEL_MEAN * (lap.astype(np.float64) - 1.0)
            + wear * tire_age.astype(np.float64)
        )
        return mean, np.full(driver.shape, self.sigma_sparse, dtype=np.float64)
