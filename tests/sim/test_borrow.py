"""BorrowedPace: exact for fitted inputs, averages for unfitted compounds and absent drivers."""

from typing import Any

import numpy as np
from numpy.typing import NDArray

from f1si.sim.borrow import BorrowedPace

from .conftest import ZeroNoisePace


def _args(drivers: list[int], compounds: list[str]) -> dict[str, Any]:
    n = len(drivers)
    return {
        "driver": np.array(drivers, dtype=np.int64),
        "compound": np.array(compounds, dtype=np.str_),
        "tire_age": np.arange(1, n + 1, dtype=np.int64),
        "lap": np.arange(5, 5 + n, dtype=np.int64),
    }


class _CompoundAware(ZeroNoisePace):
    """Pace that depends on the compound, so borrowing is visible."""

    def predict(
        self,
        *,
        driver: NDArray[np.int64],
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],
        lap: NDArray[np.int64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        mean, sd = super().predict(driver=driver, compound=compound, tire_age=tire_age, lap=lap)
        shift = np.where(compound == "SOFT", -1.0, 0.0) + np.where(compound == "HARD", 1.0, 0.0)
        return mean + shift, sd + np.where(compound == "SOFT", 0.5, 0.25)


def test_fitted_inputs_are_bit_identical() -> None:
    model = _CompoundAware()
    borrowed = BorrowedPace(model, ("HARD", "SOFT"), (1, 2, 3))
    a = _args([1, 2, 3, 1], ["HARD", "SOFT", "HARD", "SOFT"])
    want = model.predict(**a)
    got = borrowed.predict(**a)
    assert np.array_equal(want[0], got[0])
    assert np.array_equal(want[1], got[1])
    assert not borrowed.borrowed_compounds
    assert not borrowed.borrowed_drivers


def test_unfitted_compound_is_average_of_fitted() -> None:
    model = _CompoundAware()
    borrowed = BorrowedPace(model, ("HARD", "SOFT"), (1, 2))
    a = _args([1, 2], ["MEDIUM", "MEDIUM"])
    before = {k: v.copy() for k, v in a.items()}
    mean, sd = borrowed.predict(**a)
    hard = model.predict(**{**a, "compound": np.array(["HARD", "HARD"], dtype=np.str_)})
    soft = model.predict(**{**a, "compound": np.array(["SOFT", "SOFT"], dtype=np.str_)})
    assert np.allclose(mean, (hard[0] + soft[0]) / 2)
    assert np.allclose(sd, np.maximum(hard[1], soft[1]))
    assert "MEDIUM" in borrowed.borrowed_compounds
    for k in a:
        assert np.array_equal(a[k], before[k])


def test_absent_driver_is_field_mean_and_describe() -> None:
    model = _CompoundAware()
    borrowed = BorrowedPace(model, ("HARD", "SOFT"), (1, 2, 3))
    a = _args([81, 1], ["HARD", "HARD"])
    mean, _ = borrowed.predict(**a)
    expect = np.mean(
        [model.predict(**{**a, "driver": np.full(2, d, dtype=np.int64)})[0] for d in (1, 2, 3)],
        axis=0,
    )
    assert np.isclose(mean[0], expect[0])
    assert mean[1] == model.predict(**a)[0][1]
    assert borrowed.borrowed_drivers == {81}
    lines = borrowed.describe({"MEDIUM": 13, "HARD": 7}, [81])
    assert "MEDIUM pace borrowed from HARD, SOFT for 13 cars" in lines
    assert "driver 81 not in the fit: field-average pace" in lines
    assert not any(line.startswith("HARD") for line in lines)
