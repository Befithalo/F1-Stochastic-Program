"""Review fix WR-02: covariance from the SVD, no matrix inverse, tighter limit (DEC-071)."""

from pathlib import Path

import numpy as np
import pytest

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, RaceSnapshot
from f1si.pace import linear
from f1si.pace.linear import fit_linear_pace
from tests.conftest import LONG_RACE_ID


def _snap(db: Path) -> RaceSnapshot:
    return AsOfAccessor(db).snapshot(AsOf(LONG_RACE_ID, RACE_END))


def test_cond_limit_keeps_normal_equations_representable() -> None:
    assert linear.COND_LIMIT**2 <= 1e12


def test_standard_errors_do_not_use_a_matrix_inverse(
    long_synthetic_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snap = _snap(long_synthetic_db)
    expected = fit_linear_pace(snap).report

    def boom(*_args: object, **_kwargs: object) -> None:
        raise np.linalg.LinAlgError("inv must not be called")

    monkeypatch.setattr(np.linalg, "inv", boom)
    got = fit_linear_pace(snap).report
    assert got.fuel_se == pytest.approx(expected.fuel_se, rel=1e-12)
    assert [c.se for c in got.compounds] == pytest.approx([c.se for c in expected.compounds])


def test_standard_errors_match_the_textbook_formula(
    long_synthetic_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linear, "MAD_K", 1e9)  # no trimming: the plain OLS formula applies
    snap = _snap(long_synthetic_db)
    table = linear._classify(snap.laps)
    active = np.array([r is None for r in table["reason"].to_numpy()], dtype=bool)
    design = linear._build(table, active)
    x, y = design.x, design.y
    coef = np.linalg.lstsq(x, y, rcond=None)[0]
    s2 = float(np.sum((y - x @ coef) ** 2)) / (x.shape[0] - x.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.pinv(x.T @ x)))
    nd = len(design.drivers)
    report = fit_linear_pace(snap).report
    assert report.fuel_se == pytest.approx(se[nd], rel=1e-8)
    assert [c.se for c in report.compounds] == pytest.approx(list(se[nd + 1 :]), rel=1e-8)
