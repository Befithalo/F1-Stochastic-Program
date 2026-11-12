"""The fit refuses to report numbers it cannot identify (D-01, D-03)."""

from pathlib import Path

import numpy as np
import pytest

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor
from f1si.pace import linear
from f1si.pace.linear import LinearPaceFit, fit_linear_pace
from tests.conftest import LONG_RACE_ID


def _fit(db: Path, lap: int | None = None) -> LinearPaceFit:
    at = AsOf(LONG_RACE_ID, RACE_END if lap is None else lap)
    return fit_linear_pace(AsOfAccessor(db).snapshot(at))


def test_before_first_stop_fuel_is_unidentified(long_synthetic_db: Path) -> None:
    fit = _fit(long_synthetic_db, 20)
    r = fit.report
    assert not fit.is_identified
    assert r.fuel_s_per_lap is None
    assert r.fuel_se is None
    assert "fuel effect" in r.unidentified
    assert "wear MEDIUM" in r.unidentified
    assert r.compounds == ()
    assert "fuel effect" in r.message
    one = np.array([1], dtype=np.int64)
    with pytest.raises(ValueError, match="not identified"):
        fit.predict(
            driver=np.array([10], dtype=np.int64),
            compound=np.array(["MEDIUM"], dtype=np.str_),
            tire_age=one,
            lap=one,
        )


def test_after_first_stop_the_fit_is_identified(long_synthetic_db: Path) -> None:
    fit = _fit(long_synthetic_db, 40)
    assert fit.is_identified
    assert fit.report.unidentified == ()


def test_compound_with_too_few_laps_gets_no_number(
    long_synthetic_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    full = _fit(long_synthetic_db).report
    counts = {c.compound: c.n_laps for c in full.compounds}
    assert counts["MEDIUM"] < counts["HARD"]
    monkeypatch.setattr(linear, "MIN_CLEAN_LAPS_PER_COMPOUND", counts["MEDIUM"] + 1)
    fit = _fit(long_synthetic_db)
    assert "MEDIUM" in fit.report.not_enough_data
    assert fit.wear_rate("MEDIUM") is None
    assert fit.report.dropped.get("compound with too few laps", 0) > 0
    assert not fit.is_identified
