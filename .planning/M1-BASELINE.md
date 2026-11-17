# M1 Final Backtest Baseline

The canonical M1 baseline for M2 phase-end reporting is the locked 20-race, 2023-2025 in-sample evaluation in `reports/backtest/phase-08.json`. It uses the linear pace model, 1,000 simulations per prediction, equal race weighting after within-race averaging, and whole-race bootstrap intervals. All 20 races belong to the `ground_effect_2022_2025` era.

| Metric | M1 baseline | Denominator / interpretation |
|---|---:|---|
| Podium Brier | 0.055456 (grid baseline 0.073693) | 20 race-weighted means; 22,213 Brier observations |
| Top-10 Brier | 0.144645 (grid baseline 0.169086) | 20 race-weighted means; 22,213 Brier observations |
| Inclusive P05-P95 finish-interval coverage | 82.26% | 16,508 / 20,001 classified finishers |
| Signed planned-stop timing error | +1.174 laps | 695 matched stops across 20 races |
| Top-action agreement with observed team calls | 17.22% | 695 matched stops across 20 races |

The metrics and denominators come from the committed report and are not recomputed here. Agreement and stop timing are retrospective comparisons with team behavior, not claims of competitive superiority. The 95% paired Brier-difference intervals include zero. Keep the separate 2026 report out of this baseline: it is another era, has no grid-baseline comparison, and was pre-registered but retrospectively unblinded.

The Phase 7 PAC-06 real-data gate remains unmet. Its locked result is Bayesian MAE 0.538745 s versus 0.364033 s for linear pace (-47.99% improvement); do not fold it into the M1 strategy baseline or rescore it. M2 must use a separately registered held-out-stint comparison.
