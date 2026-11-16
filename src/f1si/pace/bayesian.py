"""Seeded Bayesian pace fit used behind the shared ``PaceModel`` contract.

The model separates fitted car/driver and compound effects from the residual lap noise returned
by :meth:`BayesianPaceFit.predict`. The simulator samples shared driver and tire uncertainty from
the corresponding ``RaceState`` fields, so those terms are not repeated as per-lap noise.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pymc as pm  # type: ignore[import-untyped]
import pytensor.tensor as pt
from numpy.typing import NDArray


class PaceFitError(ValueError):
    """Raised when a Bayesian pace model cannot be fit from the supplied rows."""


@dataclass(frozen=True)
class BayesianFitReport:
    """Compact, serializable diagnostics and driver offsets from a Bayesian fit."""

    driver_offsets: Mapping[int, float]
    driver_offset_se: Mapping[int, float]
    fuel_s_per_lap: float
    sigma_s: float
    n_rows: int
    seed: int
    iterations: int
    final_loss: float


@dataclass(frozen=True)
class BayesianPaceFit:
    """Posterior summaries implementing ``PaceModel`` and the state-builder fit contract."""

    report: BayesianFitReport
    _intercept_s: float
    _fuel_s_per_lap: float
    _driver_offsets: Mapping[int, float]
    _driver_offset_sd: Mapping[int, float]
    _fresh_offsets_s: Mapping[str, float]
    _wear_s_per_lap: Mapping[str, float]
    _wear_sd: Mapping[str, float]

    @property
    def fitted_compounds(self) -> tuple[str, ...]:
        """Compounds represented by the training rows."""
        return tuple(self._wear_s_per_lap)

    @property
    def fuel_effect(self) -> float:
        """Shared lap-number effect, in seconds per lap."""
        return self._fuel_s_per_lap

    def wear_rate(self, compound: str) -> float | None:
        """Posterior mean compound wear slope, or ``None`` when the compound is unseen."""
        return self._wear_s_per_lap.get(str(compound).upper())

    def wear_se(self, compound: str) -> float | None:
        """Posterior SD of the shared compound wear slope."""
        return self._wear_sd.get(str(compound).upper())

    def pace_offset(self, driver_number: int) -> float | None:
        """Centered posterior mean driver pace effect, or ``None`` for an unseen driver."""
        return self._driver_offsets.get(int(driver_number))

    def pace_offset_se(self, driver_number: int) -> float | None:
        """Posterior SD of the shared driver pace effect."""
        return self._driver_offset_sd.get(int(driver_number))

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Return posterior mean lap time and residual SD; shared effects are not re-sampled."""
        if not (driver.shape == compound.shape == tire_age.shape == lap.shape):
            raise ValueError("driver, compound, tire_age and lap arrays must have equal shapes")
        driver_effect = np.empty(driver.shape, dtype=np.float64)
        for number in np.unique(driver):
            effect = self.pace_offset(int(number))
            if effect is None:
                raise ValueError(f"Driver number {int(number)} was not in the pace fit")
            driver_effect[driver == number] = effect
        compound_offset = np.empty(driver.shape, dtype=np.float64)
        wear_rate = np.empty(driver.shape, dtype=np.float64)
        for value in np.unique(compound):
            name = str(value).upper()
            if name not in self._fresh_offsets_s:
                raise ValueError(f"Compound {name!r} was not in the pace fit")
            mask = compound == value
            compound_offset[mask] = self._fresh_offsets_s[name]
            wear_rate[mask] = self._wear_s_per_lap[name]
        mean = (
            self._intercept_s
            + driver_effect
            + compound_offset
            + self._fuel_s_per_lap * (lap.astype(np.float64) - 1.0)
            + wear_rate * tire_age.astype(np.float64)
        )
        return mean, np.full(driver.shape, self.report.sigma_s, dtype=np.float64)


def fit_bayesian_pace(
    *,
    driver: NDArray[np.int64],
    compound: NDArray[np.str_],
    tire_age: NDArray[np.int64],
    lap: NDArray[np.int64],
    lap_time_s: NDArray[np.float64],
    seed: int,
    iterations: int = 3_000,
    draws: int = 256,
) -> BayesianPaceFit:
    """Fit a seeded partially pooled driver, compound, fuel and wear model.

    The inputs are plain arrays so callers decide which as-of visible rows are eligible. Group
    effects are centered; lap and tire-age predictors are scaled before inference and transformed
    back to seconds and seconds per lap in the returned fit.
    """
    arrays = (driver, compound, tire_age, lap, lap_time_s)
    if not arrays or any(array.ndim != 1 for array in arrays):
        raise PaceFitError("training arrays must be one dimensional")
    if len({array.shape for array in arrays}) != 1:
        raise PaceFitError("training arrays must have matching shapes")
    if len(lap_time_s) < 20 or not np.isfinite(lap_time_s).all():
        raise PaceFitError("training needs at least 20 finite lap-time rows")
    if (driver < 1).any() or (lap < 1).any() or (tire_age < 0).any():
        raise PaceFitError(
            "driver numbers and lap numbers must be positive; tire age cannot be negative"
        )
    if iterations < 1 or draws < 2 or seed < 0:
        raise PaceFitError("iterations and draws must be positive and seed must be non-negative")
    drivers = np.unique(driver)
    compounds = np.unique(np.char.upper(compound))
    if len(drivers) == 0 or len(compounds) == 0:
        raise PaceFitError("training must contain at least one driver and one compound")
    if np.unique(lap).size < 2 or np.unique(tire_age).size < 2:
        raise PaceFitError("lap and tire-age effects are not identifiable from constant predictors")

    driver_idx = np.searchsorted(drivers, driver).astype(np.int64)
    compound_upper = np.char.upper(compound)
    compound_idx = np.searchsorted(compounds, compound_upper).astype(np.int64)
    lap_value = lap.astype(np.float64) - 1.0
    age_value = tire_age.astype(np.float64)
    lap_center = float(np.mean(lap_value))
    age_center = float(np.mean(age_value))
    lap_scale = float(np.std(lap_value)) or 1.0
    age_scale = float(np.std(age_value)) or 1.0
    lap_x = (lap_value - lap_center) / lap_scale
    age_x = (age_value - age_center) / age_scale

    try:
        with pm.Model():
            intercept = pm.Normal("intercept", mu=float(np.mean(lap_time_s)), sigma=5.0)
            driver_scale = pm.HalfNormal("driver_scale", sigma=1.0)
            driver_raw = pm.Normal("driver_raw", mu=0.0, sigma=1.0, shape=len(drivers))
            driver_effect = pm.Deterministic(
                "driver_effect",
                driver_scale * (driver_raw - pt.mean(driver_raw)),  # type: ignore[no-untyped-call]
            )
            fresh_scale = pm.HalfNormal("fresh_scale", sigma=0.75)
            fresh_raw = pm.Normal("fresh_raw", mu=0.0, sigma=1.0, shape=len(compounds))
            fresh_effect = pm.Deterministic(
                "fresh_effect",
                fresh_scale * (fresh_raw - pt.mean(fresh_raw)),  # type: ignore[no-untyped-call]
            )
            fuel_scaled = pm.Normal("fuel_scaled", mu=0.0, sigma=1.0)
            wear_mean = pm.Normal("wear_mean", mu=0.08, sigma=0.10)
            wear_scale = pm.HalfNormal("wear_scale", sigma=0.08)
            wear_raw = pm.Normal("wear_raw", mu=0.0, sigma=1.0, shape=len(compounds))
            wear_scaled = pm.Deterministic(
                "wear_scaled",
                wear_mean + wear_scale * (wear_raw - pt.mean(wear_raw)),  # type: ignore[no-untyped-call]
            )
            residual_sd = pm.HalfNormal("residual_sd", sigma=1.0)
            mu = (
                intercept
                + driver_effect[driver_idx]
                + fresh_effect[compound_idx]
                + fuel_scaled * lap_x
                + wear_scaled[compound_idx] * age_x
            )
            pm.Normal("lap_time", mu=mu, sigma=residual_sd, observed=lap_time_s)
            approximation = pm.fit(
                n=iterations,
                method="fullrank_advi",
                random_seed=int(seed),
                progressbar=False,
            )
            posterior = approximation.sample(draws=draws, random_seed=int(seed))
    except (ArithmeticError, FloatingPointError, ValueError) as err:
        raise PaceFitError(f"Bayesian pace inference failed: {err}") from err

    def posterior_values(name: str) -> NDArray[np.float64]:
        values = np.asarray(posterior.posterior[name].values, dtype=np.float64)
        return values.reshape((-1, *values.shape[2:]))

    intercept_draws = posterior_values("intercept").reshape(-1)
    driver_draws = posterior_values("driver_effect")
    fresh_draws = posterior_values("fresh_effect")
    fuel_draws = posterior_values("fuel_scaled").reshape(-1) / lap_scale
    wear_draws = posterior_values("wear_scaled") / age_scale
    residual_draws = posterior_values("residual_sd").reshape(-1)
    fuel_mean = float(np.mean(fuel_draws))
    wear_means = np.mean(wear_draws, axis=0)
    fresh_means = np.mean(fresh_draws, axis=0) - wear_means * age_center
    driver_means = np.mean(driver_draws, axis=0)
    driver_sd = np.std(driver_draws, axis=0, ddof=1)
    final_loss = float(np.asarray(approximation.hist, dtype=np.float64)[-1])
    if not np.isfinite(final_loss) or not np.isfinite(residual_draws).all():
        raise PaceFitError("Bayesian pace inference returned non-finite posterior values")
    driver_map = {
        int(number): float(value) for number, value in zip(drivers, driver_means, strict=True)
    }
    driver_sd_map = {
        int(number): float(value) for number, value in zip(drivers, driver_sd, strict=True)
    }
    fresh_map = {
        str(name): float(value) for name, value in zip(compounds, fresh_means, strict=True)
    }
    wear_map = {str(name): float(value) for name, value in zip(compounds, wear_means, strict=True)}
    wear_sd_map = {
        str(name): float(value)
        for name, value in zip(compounds, np.std(wear_draws, axis=0, ddof=1), strict=True)
    }
    offset = float(np.mean(intercept_draws) - fuel_mean * lap_center)
    report = BayesianFitReport(
        driver_offsets=driver_map,
        driver_offset_se=driver_sd_map,
        fuel_s_per_lap=fuel_mean,
        sigma_s=float(np.mean(residual_draws)),
        n_rows=len(lap_time_s),
        seed=int(seed),
        iterations=iterations,
        final_loss=final_loss,
    )
    return BayesianPaceFit(
        report=report,
        _intercept_s=offset,
        _fuel_s_per_lap=fuel_mean,
        _driver_offsets=driver_map,
        _driver_offset_sd=driver_sd_map,
        _fresh_offsets_s=fresh_map,
        _wear_s_per_lap=wear_map,
        _wear_sd=wear_sd_map,
    )
