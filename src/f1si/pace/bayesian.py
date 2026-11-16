"""Seeded Bayesian pace fit used behind the shared ``PaceModel`` contract.

The model separates fitted team, driver, race, era, compound and wear effects from residual lap
noise. Shared team/driver and tire uncertainty is exposed through the corresponding ``RaceState``
fields; it is not repeated as per-lap noise.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import pymc as pm  # type: ignore[import-untyped]
import pytensor.tensor as pt
from numpy.typing import NDArray

from f1si.pace.training import BayesianTrainingPanel

_MIN_DRIVER_LAPS = 5
_MIN_TEAM_LAPS = 20
_MIN_GROUP_ROWS = 30
_EFFECT_NAMES = (
    "team/car",
    "driver",
    "fresh compound",
    "compound wear",
    "fuel proxy",
    "regulation era",
    "race/event",
)


class PaceFitError(ValueError):
    """Raised when a Bayesian pace model cannot be fit from the supplied rows."""


@dataclass(frozen=True)
class BayesianFitReport:
    """Compact posterior summaries and auditable fit diagnostics."""

    driver_offsets: Mapping[int, float]
    driver_offset_se: Mapping[int, float]
    fuel_s_per_lap: float
    sigma_s: float
    n_rows: int
    seed: int
    iterations: int
    final_loss: float
    effect_names: tuple[str, ...]
    team_offsets: Mapping[str, float]
    driver_identity_offsets: Mapping[str, float]
    fresh_offsets_s: Mapping[str, float]
    wear_s_per_lap: Mapping[str, float]
    wear_sd: Mapping[str, float]
    era_offsets: Mapping[str, float]
    race_offsets: Mapping[str, float]
    category_indexes: Mapping[str, Mapping[str, int]]
    prior_driven_driver_ids: tuple[str, ...]
    prior_driven_driver_numbers: tuple[int, ...]
    prior_driven_team_names: tuple[str, ...]
    prior_driven_compounds: tuple[str, ...]
    prior_driven_era_names: tuple[str, ...]
    prior_driven_event_ids: tuple[str, ...]
    identifiability_notes: tuple[str, ...]


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
        """Compounds represented by training rows."""
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
        """Centered posterior mean team plus driver effect for this race entry."""
        return self._driver_offsets.get(int(driver_number))

    def pace_offset_se(self, driver_number: int) -> float | None:
        """Posterior SD of the shared team plus driver pace effect."""
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
    """Fit a seeded single-event panel for the model tracer and compact synthetic fixtures."""
    driver_ids = np.char.add("driver-", driver.astype(str))
    current_driver_ids = {
        int(number): str(identity) for number, identity in zip(driver, driver_ids, strict=True)
    }
    current_teams = {int(number): "TEAM_UNKNOWN" for number in np.unique(driver)}
    count = len(driver)
    return _fit_arrays(
        driver_number=driver,
        driver_id=driver_ids,
        team_name=np.full(count, "TEAM_UNKNOWN", dtype=np.str_),
        event_id=np.full(count, "CURRENT_EVENT", dtype=np.str_),
        era=np.full(count, "CURRENT_ERA", dtype=np.str_),
        compound=compound,
        tire_age=tire_age,
        lap=lap,
        lap_time_s=lap_time_s,
        current_driver_id_by_number=current_driver_ids,
        current_team_by_number=current_teams,
        current_event_id="CURRENT_EVENT",
        current_era="CURRENT_ERA",
        seed=seed,
        iterations=iterations,
        draws=draws,
    )


def fit_bayesian_panel(
    panel: BayesianTrainingPanel,
    *,
    seed: int,
    iterations: int = 3_000,
    draws: int = 256,
) -> BayesianPaceFit:
    """Fit the partially pooled model from a cutoff-safe panel and its active grid lookup."""
    rows = panel.rows
    if rows.empty:
        raise PaceFitError("the cutoff-safe pace panel has no clean training rows")
    return _fit_arrays(
        driver_number=rows["driver_number"].to_numpy(dtype=np.int64),
        driver_id=rows["driver_id"].astype(str).to_numpy(dtype=np.str_),
        team_name=rows["team_name"].astype(str).to_numpy(dtype=np.str_),
        event_id=rows["race_id"].astype(str).to_numpy(dtype=np.str_),
        era=rows["era"].astype(str).to_numpy(dtype=np.str_),
        compound=rows["compound"].astype(str).to_numpy(dtype=np.str_),
        tire_age=rows["tire_age"].to_numpy(dtype=np.int64),
        lap=rows["lap_number"].to_numpy(dtype=np.int64),
        lap_time_s=rows["lap_time_s"].to_numpy(dtype=np.float64),
        current_driver_id_by_number=panel.current_driver_id_by_number,
        current_team_by_number=panel.current_team_by_number,
        current_event_id=panel.current_event_id,
        current_era=panel.current_era,
        seed=seed,
        iterations=iterations,
        draws=draws,
    )


def _fit_arrays(
    *,
    driver_number: NDArray[np.int64],
    driver_id: NDArray[np.str_],
    team_name: NDArray[np.str_],
    event_id: NDArray[np.str_],
    era: NDArray[np.str_],
    compound: NDArray[np.str_],
    tire_age: NDArray[np.int64],
    lap: NDArray[np.int64],
    lap_time_s: NDArray[np.float64],
    current_driver_id_by_number: Mapping[int, str],
    current_team_by_number: Mapping[int, str],
    current_event_id: str,
    current_era: str,
    seed: int,
    iterations: int,
    draws: int,
) -> BayesianPaceFit:
    arrays = (
        driver_number,
        driver_id,
        team_name,
        event_id,
        era,
        compound,
        tire_age,
        lap,
        lap_time_s,
    )
    if any(array.ndim != 1 for array in arrays) or len({array.shape for array in arrays}) != 1:
        raise PaceFitError("training arrays must be one dimensional and have matching shapes")
    if len(lap_time_s) < 20 or not np.isfinite(lap_time_s).all():
        raise PaceFitError("training needs at least 20 finite lap-time rows")
    if (driver_number < 1).any() or (lap < 1).any() or (tire_age < 0).any():
        raise PaceFitError(
            "driver numbers and lap numbers must be positive; tire age cannot be negative"
        )
    if iterations < 1 or draws < 2 or seed < 0:
        raise PaceFitError("iterations must be positive, draws at least 2, and seed non-negative")
    if np.unique(lap).size < 2 or np.unique(tire_age).size < 2:
        raise PaceFitError("lap and tire-age effects are not identifiable from constant predictors")
    if any(
        not str(value).strip()
        for array in (driver_id, team_name, event_id, era, compound)
        for value in array
    ):
        raise PaceFitError("driver, team, event, era and compound labels must not be empty")
    if set(current_driver_id_by_number) != set(current_team_by_number):
        raise PaceFitError("current driver and team lookups must have identical driver-number keys")
    if not current_event_id or not current_era:
        raise PaceFitError("the current event and regulation era must be named")

    driver_id = driver_id.astype(np.str_)
    team_name = team_name.astype(np.str_)
    event_id = event_id.astype(np.str_)
    era = era.astype(np.str_)
    compound = np.char.upper(compound.astype(np.str_))
    driver_levels = tuple(
        sorted(set(str(x) for x in driver_id) | set(current_driver_id_by_number.values()))
    )
    team_levels = tuple(
        sorted(set(str(x) for x in team_name) | set(current_team_by_number.values()))
    )
    event_levels = tuple(sorted(set(str(x) for x in event_id) | {current_event_id}))
    era_levels = tuple(sorted(set(str(x) for x in era) | {current_era}))
    compound_levels = tuple(sorted(set(str(x) for x in compound)))
    categories = {
        "driver_id": driver_levels,
        "team_name": team_levels,
        "race_id": event_levels,
        "era": era_levels,
        "compound": compound_levels,
    }
    category_indexes = MappingProxyType(
        {
            name: MappingProxyType({value: index for index, value in enumerate(values)})
            for name, values in categories.items()
        }
    )

    def codes(values: NDArray[np.str_], levels: tuple[str, ...]) -> NDArray[np.int64]:
        return np.searchsorted(np.array(levels, dtype=np.str_), values).astype(np.int64)

    driver_idx = codes(driver_id, driver_levels)
    team_idx = codes(team_name, team_levels)
    event_idx = codes(event_id, event_levels)
    era_idx = codes(era, era_levels)
    compound_idx = codes(compound, compound_levels)
    lap_value = lap.astype(np.float64) - 1.0
    lap_scale = float(np.std(lap_value)) or 1.0
    age_scale = float(np.std(tire_age.astype(np.float64))) or 1.0
    lap_x = lap_value / lap_scale
    age_x = tire_age.astype(np.float64) / age_scale

    try:
        with pm.Model():
            intercept = pm.Normal("intercept", mu=float(np.mean(lap_time_s)), sigma=5.0)

            def pooled_effect(name: str, size: int, scale_prior: float) -> Any:
                scale = pm.HalfNormal(f"{name}_scale", sigma=scale_prior)
                raw = pm.Normal(f"{name}_raw", mu=0.0, sigma=1.0, shape=size)
                return pm.Deterministic(
                    name,
                    scale * (raw - pt.mean(raw)),  # type: ignore[no-untyped-call]
                )

            team_effect = pooled_effect("team_effect", len(team_levels), 0.75)
            driver_effect = pooled_effect("driver_effect", len(driver_levels), 0.75)
            event_effect = pooled_effect("event_effect", len(event_levels), 1.0)
            era_effect = pooled_effect("era_effect", len(era_levels), 2.0)
            fresh_effect = pooled_effect("fresh_effect", len(compound_levels), 0.75)
            fuel_scaled = pm.Normal("fuel_scaled", mu=0.0, sigma=1.0)
            wear_mean = pm.Normal("wear_mean", mu=0.08, sigma=0.10)
            wear_scale = pm.HalfNormal("wear_scale", sigma=0.08)
            wear_raw = pm.Normal("wear_raw", mu=0.0, sigma=1.0, shape=len(compound_levels))
            wear_scaled = pm.Deterministic(
                "wear_scaled",
                wear_mean + wear_scale * (wear_raw - pt.mean(wear_raw)),  # type: ignore[no-untyped-call]
            )
            residual_sd = pm.HalfNormal("residual_sd", sigma=1.0)
            mu = (
                intercept
                + team_effect[team_idx]
                + driver_effect[driver_idx]
                + event_effect[event_idx]
                + era_effect[era_idx]
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
    except Exception as err:
        raise PaceFitError(f"Bayesian pace inference failed: {err}") from err

    def posterior_values(name: str) -> NDArray[np.float64]:
        values = np.asarray(posterior.posterior[name].values, dtype=np.float64)
        return values.reshape((-1, *values.shape[2:]))

    intercept_draws = posterior_values("intercept").reshape(-1)
    team_draws = posterior_values("team_effect")
    driver_draws = posterior_values("driver_effect")
    event_draws = posterior_values("event_effect")
    era_draws = posterior_values("era_effect")
    fresh_draws = posterior_values("fresh_effect")
    fuel_draws = posterior_values("fuel_scaled").reshape(-1) / lap_scale
    wear_draws = posterior_values("wear_scaled") / age_scale
    residual_draws = posterior_values("residual_sd").reshape(-1)
    team_scale_draws = posterior_values("team_effect_scale").reshape(-1)
    driver_scale_draws = posterior_values("driver_effect_scale").reshape(-1)

    if not np.isfinite(np.asarray(approximation.hist, dtype=np.float64)).all():
        raise PaceFitError("Bayesian pace inference returned a non-finite optimization loss")
    if not np.isfinite(residual_draws).all() or (residual_draws <= 0.0).any():
        raise PaceFitError("Bayesian pace inference returned invalid residual-noise summaries")

    team_means = np.mean(team_draws, axis=0)
    driver_means = np.mean(driver_draws, axis=0)
    event_means = np.mean(event_draws, axis=0)
    era_means = np.mean(era_draws, axis=0)
    fresh_means = np.mean(fresh_draws, axis=0)
    wear_means = np.mean(wear_draws, axis=0)
    team_map = {name: float(value) for name, value in zip(team_levels, team_means, strict=True)}
    driver_map = {
        name: float(value) for name, value in zip(driver_levels, driver_means, strict=True)
    }
    event_map = {name: float(value) for name, value in zip(event_levels, event_means, strict=True)}
    era_map = {name: float(value) for name, value in zip(era_levels, era_means, strict=True)}
    fresh_map = {
        name: float(value) for name, value in zip(compound_levels, fresh_means, strict=True)
    }
    wear_map = {name: float(value) for name, value in zip(compound_levels, wear_means, strict=True)}
    wear_sd_map = {
        name: float(value)
        for name, value in zip(compound_levels, np.std(wear_draws, axis=0, ddof=1), strict=True)
    }

    event_position = event_levels.index(current_event_id)
    era_position = era_levels.index(current_era)
    common_intercept_draws = (
        intercept_draws + event_draws[:, event_position] + era_draws[:, era_position]
    )
    intercept_mean = float(np.mean(common_intercept_draws))
    fuel_mean = float(np.mean(fuel_draws))
    current_driver_offsets: dict[int, float] = {}
    current_driver_sd: dict[int, float] = {}
    driver_counts = {name: int(np.count_nonzero(driver_id == name)) for name in driver_levels}
    team_counts = {name: int(np.count_nonzero(team_name == name)) for name in team_levels}
    prior_driven_numbers: list[int] = []
    for number, identity in sorted(current_driver_id_by_number.items()):
        identity = str(identity)
        team = str(current_team_by_number[number])
        driver_position = driver_levels.index(identity)
        team_position = team_levels.index(team)
        draws_for_car = driver_draws[:, driver_position] + team_draws[:, team_position]
        unknown_variance = np.zeros(draws_for_car.shape, dtype=np.float64)
        if driver_counts[identity] == 0:
            unknown_variance += driver_scale_draws**2
        if team_counts[team] == 0:
            unknown_variance += team_scale_draws**2
        current_driver_offsets[int(number)] = float(np.mean(draws_for_car))
        current_driver_sd[int(number)] = float(
            np.sqrt(np.var(draws_for_car, ddof=1) + np.mean(unknown_variance))
        )
        if driver_counts[identity] < _MIN_DRIVER_LAPS:
            prior_driven_numbers.append(int(number))

    driver_id_counts = {name: int(np.count_nonzero(driver_id == name)) for name in driver_levels}
    prior_driver_ids = tuple(
        name for name in driver_levels if driver_id_counts[name] < _MIN_DRIVER_LAPS
    )
    current_teams = set(str(value) for value in current_team_by_number.values())
    prior_teams = tuple(
        name for name in team_levels if name in current_teams and team_counts[name] < _MIN_TEAM_LAPS
    )
    compound_counts = {name: int(np.count_nonzero(compound == name)) for name in compound_levels}
    prior_compounds = tuple(
        name for name in compound_levels if compound_counts[name] < _MIN_GROUP_ROWS
    )
    era_counts = {name: int(np.count_nonzero(era == name)) for name in era_levels}
    prior_eras = tuple(name for name in era_levels if era_counts[name] < _MIN_GROUP_ROWS)
    event_counts = {name: int(np.count_nonzero(event_id == name)) for name in event_levels}
    prior_events = tuple(name for name in event_levels if event_counts[name] < _MIN_GROUP_ROWS)
    notes: list[str] = []
    if len(set(str(value) for value in era)) < 2:
        notes.append(
            "real training rows contain one regulation era; no between-era contrast is identified"
        )
    if prior_driver_ids or prior_teams or prior_compounds or prior_eras or prior_events:
        notes.append(
            "one or more group predictions are prior-driven because their clean-row count is sparse"
        )
    final_loss = float(np.asarray(approximation.hist, dtype=np.float64)[-1])
    report = BayesianFitReport(
        driver_offsets=MappingProxyType(dict(current_driver_offsets)),
        driver_offset_se=MappingProxyType(dict(current_driver_sd)),
        fuel_s_per_lap=fuel_mean,
        sigma_s=float(np.mean(residual_draws)),
        n_rows=len(lap_time_s),
        seed=int(seed),
        iterations=iterations,
        final_loss=final_loss,
        effect_names=_EFFECT_NAMES,
        team_offsets=MappingProxyType(team_map),
        driver_identity_offsets=MappingProxyType(driver_map),
        fresh_offsets_s=MappingProxyType(fresh_map),
        wear_s_per_lap=MappingProxyType(wear_map),
        wear_sd=MappingProxyType(wear_sd_map),
        era_offsets=MappingProxyType(era_map),
        race_offsets=MappingProxyType(event_map),
        category_indexes=category_indexes,
        prior_driven_driver_ids=prior_driver_ids,
        prior_driven_driver_numbers=tuple(prior_driven_numbers),
        prior_driven_team_names=prior_teams,
        prior_driven_compounds=prior_compounds,
        prior_driven_era_names=prior_eras,
        prior_driven_event_ids=prior_events,
        identifiability_notes=tuple(notes),
    )
    return BayesianPaceFit(
        report=report,
        _intercept_s=intercept_mean,
        _fuel_s_per_lap=fuel_mean,
        _driver_offsets=report.driver_offsets,
        _driver_offset_sd=report.driver_offset_se,
        _fresh_offsets_s=report.fresh_offsets_s,
        _wear_s_per_lap=report.wear_s_per_lap,
        _wear_sd=report.wear_sd,
    )
