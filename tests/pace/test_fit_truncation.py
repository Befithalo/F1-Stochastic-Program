"""Review fix WR-04: sigma and SEs are corrected for the 3-MAD truncation (DEC-072)."""

from pathlib import Path

import numpy as np
import pytest

from f1si.data.asof import RACE_END, AsOf, AsOfAccessor, RaceSnapshot
from f1si.pace import linear
from f1si.pace.linear import fit_linear_pace, truncated_variance_factor, untruncated_sigma
from f1si.synthetic import SyntheticTruth
from tests.conftest import LONG_RACE_ID, build_long_db

N_SEEDS = 12


def _snap(db: Path) -> RaceSnapshot:
    return AsOfAccessor(db).snapshot(AsOf(LONG_RACE_ID, RACE_END))


def test_truncated_variance_factor_matches_known_values() -> None:
    assert truncated_variance_factor(3.0) == pytest.approx(0.97334, abs=2e-5)
    assert truncated_variance_factor(1.0) == pytest.approx(0.29112, abs=2e-5)
    assert truncated_variance_factor(8.0) == pytest.approx(1.0, abs=1e-9)


def test_untruncated_sigma_inverts_the_truncation() -> None:
    sigma, cutoff = 0.15, 0.45  # a 3-sigma cut
    kept_sd = sigma * float(np.sqrt(truncated_variance_factor(cutoff / sigma)))
    assert untruncated_sigma(kept_sd, cutoff) == pytest.approx(sigma, rel=1e-9)
    assert untruncated_sigma(0.1, 0.0) == 0.1


def test_sigma_recovers_truth_and_matches_the_untrimmed_fit(
    tmp_path: Path, long_synthetic_truth: SyntheticTruth, monkeypatch: pytest.MonkeyPatch
) -> None:
    snaps = [_snap(build_long_db(tmp_path / f"s{seed}", seed)) for seed in range(N_SEEDS)]
    trimmed = [fit_linear_pace(s).report for s in snaps]
    assert sum(r.n_trimmed for r in trimmed) > 0
    monkeypatch.setattr(linear, "MAD_K", 1e9)
    untrimmed = [fit_linear_pace(s).report for s in snaps]
    assert all(r.n_trimmed == 0 for r in untrimmed)
    sig_t = np.array([r.sigma_s for r in trimmed], dtype=float)
    sig_u = np.array([r.sigma_s for r in untrimmed], dtype=float)
    truth = long_synthetic_truth.noise_sd_s
    # Without the correction the trimmed sigma sits about 1.5% under the untrimmed one.
    assert abs(float(sig_t.mean() / sig_u.mean()) - 1.0) < 0.005
    assert abs(float(sig_t.mean()) / truth - 1.0) < 0.03


def test_wear_interval_coverage_is_sane(
    tmp_path: Path, long_synthetic_truth: SyntheticTruth
) -> None:
    inside = 0
    total = 0
    for seed in range(N_SEEDS):
        report = fit_linear_pace(_snap(build_long_db(tmp_path / f"s{seed}", seed))).report
        for c in report.compounds:
            truth = long_synthetic_truth.wear_rate_s_per_lap[c.compound]
            inside += int(abs(c.wear_s_per_lap - truth) <= 2.0 * c.se)
            total += 1
    assert total >= 2 * N_SEEDS
    assert inside / total >= 0.85, (inside, total)
