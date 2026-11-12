"""Pace borrowing for tyres and drivers the fit cannot price (RESEARCH Pattern 7, DEC-082).

A whole-race fit can lack a compound (Bahrain 2023 has only HARD and SOFT fitted) or a driver (a
car that retired early). `BorrowedPace` wraps a `PaceModel` and fills the gaps:

* Unfitted compound: the mean of the fitted compounds' predicted means for the same driver, tyre
  age and lap, and the largest of their SDs. Wear differences between compounds are not identified
  by the data, so the borrowed pace is that of the average fitted compound.
* Driver not in the fit: the mean over all fitted drivers (the field-average offset) with the
  wrapped model, and the largest SD.
* Both at once: the mean over the product of fitted compounds and fitted drivers.

Elements with a fitted compound and a fitted driver return exactly what the wrapped model
returns. Inputs are never mutated. This module never touches the data accessor.
"""

from collections.abc import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from f1si.interfaces import PaceModel


class BorrowedPace:
    """A `PaceModel` that substitutes average pace for unfitted compounds and drivers."""

    def __init__(
        self, model: PaceModel, fitted_compounds: Sequence[str], fitted_drivers: Sequence[int]
    ) -> None:
        self._model = model
        self._compounds = tuple(sorted({str(c).upper() for c in fitted_compounds}))
        self._drivers = tuple(sorted({int(d) for d in fitted_drivers}))
        if not self._compounds or not self._drivers:
            raise ValueError("BorrowedPace needs at least one fitted compound and one driver")
        self.borrowed_compounds: dict[str, str] = {}
        self.borrowed_drivers: set[int] = set()

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Return (mean_s, sd_s) like the wrapped model, borrowing where it has no data."""
        comp_ok = np.isin(compound, np.array(self._compounds, dtype=np.str_))
        drv_ok = np.isin(driver, np.array(self._drivers, dtype=np.int64))
        good = comp_ok & drv_ok
        if bool(good.all()):
            return self._model.predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)
        mean = np.zeros(driver.shape, dtype=np.float64)
        sd = np.zeros(driver.shape, dtype=np.float64)
        if bool(good.any()):
            m, s = self._model.predict(
                driver=driver[good], compound=compound[good], tire_age=tire_age[good], lap=lap[good]
            )
            mean[good] = m
            sd[good] = s
        bad_idx = np.flatnonzero(~good.ravel())
        flat_drv, flat_comp = driver.ravel(), compound.ravel()
        pairs = {(int(flat_drv[i]), str(flat_comp[i])) for i in bad_idx}
        for number, name in sorted(pairs):
            sel = (driver == number) & (compound == name) & ~good
            comps = (name,) if name in self._compounds else self._compounds
            drvs = (number,) if number in self._drivers else self._drivers
            if name not in self._compounds:
                self.borrowed_compounds[name] = ", ".join(self._compounds)
            if number not in self._drivers:
                self.borrowed_drivers.add(number)
            age, lp = tire_age[sel], lap[sel]
            total = np.zeros(age.shape, dtype=np.float64)
            top = np.zeros(age.shape, dtype=np.float64)
            for c in comps:
                for d in drvs:
                    m, s = self._model.predict(
                        driver=np.full(age.shape, d, dtype=np.int64),
                        compound=np.repeat(np.array([c], dtype=np.str_), age.size).reshape(
                            age.shape
                        ),
                        tire_age=age,
                        lap=lp,
                    )
                    total += m
                    top = np.maximum(top, s)
            mean[sel] = total / (len(comps) * len(drvs))
            sd[sel] = top
        return mean, sd

    def describe(
        self, cars_by_compound: Mapping[str, int], cars_absent: Sequence[int]
    ) -> tuple[str, ...]:
        """Human-readable notes: which compounds and drivers were borrowed, for how many cars."""
        lines: list[str] = []
        for name in sorted(cars_by_compound):
            if name not in self._compounds and cars_by_compound[name] > 0:
                lines.append(
                    f"{name} pace borrowed from {', '.join(self._compounds)} for "
                    f"{cars_by_compound[name]} cars"
                )
        for number in sorted(int(n) for n in cars_absent):
            lines.append(f"driver {number} not in the fit: field-average pace")
        return tuple(lines)
