# Phase 10 Report - Point-Mass PaceModel

## Scope and method

Phase 10 adds a deterministic, geometry-driven lap-time model behind the existing `PaceModel` contract. The solver uses the validated Sakhir centerline, a closed cyclic speed envelope, reciprocal-speed trapezoid integration, and explicit per-driver scenario assumptions. Prediction performs no I/O and draws no random values.

The geometry is pinned by `.planning/phases/09-data-and-geometry-readiness` at SHA-256 `bc3c23da42f9474dbf5700341037bb45521acaa2ad1389bd0a48540fe179ee7a`. Its raw asset remains local because the underlying source and redistribution terms are not fully established.

The only candidate eligible for fitting is the dimensionless effective tractive-power-to-mass scale. Mass, fuel, fuel burn, total power, drag area, downforce area, grip, and tire effects remain explicit scenario assumptions. The real-data diagnostic used 850 kg mass, 50 kg fuel, 1.7 kg/lap burn, 650,000 W power, 1.4 m² drag area, 18.5 m² downforce area, 1.7 combined grip, and 0.15 s scenario SD. These are analyst scenario inputs, not recovered car values.

## Numerical contract

The implementation follows DEC-140 and DEC-141:

- Close the cyclic speed envelope at a maximum update of `1e-5 m/s`; raise after `1,000 forward/backward passes`.
- Compare the base grid with one interval bisection; relative lap-time change must remain at or below `0.1%`.
- Fit the one effective scalar with SciPy bounded minimization using `xatol=1e-8` and `maxiter=500`.
- Require a full-rank sensitivity design and condition number no greater than `1e6`. A candidate on an inclusive bound is `boundary_limited` and retains its declared assumption.
- Report residual variance only with at least `30 clean laps` across `three distinct races` in the 2023-2025 in-sample range.
- Use first-order covariance propagation only if symmetric perturbations preserve the force active set and agree with the bounded sigma-point variance within `10%`. Otherwise use symmetric spherical-radial points `plus/minus sqrt(p)` times covariance-factor columns, shrinking their common radius while preserving symmetry and registered bounds.

The fit consumes prepared `PhysicsInput` snapshots. It filters rows by `visible_at_s` or the source snapshot's `lap_end_s` at the supplied cutoff, includes exact-cutoff rows, and rejects out-of-sample and non-training seasons. Model construction binds every vehicle scenario to the prepared race's season, and the fit retains a defensive per-driver season check. It does not access classification, results, or scoring artifacts.

## Fit and uncertainty evidence

The real-data fit-path diagnostic used one in-sample `RACE_END` snapshot per training season (`2023-01`, `2024-01`, and `2025-01`), selecting the driver with the most lap records in each race. After clean-lap filtering, the panel contained 104 laps from three races. The fit diagnostics were rank 4/4 and condition number 164.61.

The result was `boundary_limited` at the lower effective scale bound `0.76923077` (the 500,000 W registered lower power bound divided by the 650,000 W scenario power). The declared scale assumption 1.0 was retained; no candidate estimate or covariance was emitted. Rank-deficient or unexcited designs are reported as unidentifiable and retain the declared assumption. This small diagnostic panel is not a full-data calibration and does not show that the scenario assumptions are real car values. Residual variance unavailable because the fit did not produce an interior identified estimate.

For that real-data scenario, the uncertainty branch was `scenario_only`: scenario variance is 0.0225 s², parameter variance is unavailable, and residual variance unavailable. Synthetic uncertainty tests separately exercise the `first_order` and `sigma_points` branches and verify the support threshold.

## Independent synthetic recovery and physical checks

The test-side truth generator reimplements the constant-curvature closed-lap force balance and imports no production pace solver or fitting helper. With fixed seed 10142 and noise SD 0.0005 s, it generated 120 SI lap targets over three synthetic race panels. The known effective scale was 1.08 with predeclared fit bounds `[1.0, 1.15]`. The fit returned 1.079989 (relative error below 0.01%), rank 4/4, and condition number 2.18. The acceptance boundary is inclusive at `5% relative tolerance`; the tests accept exactly 5% and reject a larger error. Absolute vehicle terms remain assumptions in the truth record.

Directional checks change one input at a time: higher effective power does not increase drive-limited lap time; higher drag or mass does not improve it; higher grip or downforce does not lower the corner-speed cap. An independent curvature-shape change alters the corner constraint and closed-lap speed solution without mutating the source profile. Closed-loop segment accounting counts the seam once, and profile validation rejects a zero-length segment.

## Fixed M1 baseline

Copied unchanged from `.planning/M1-BASELINE.md`; not recomputed.

| Metric | M1 value | Denominator / interpretation |
|---|---:|---|
| Podium Brier | 0.055456 (grid baseline 0.073693) | 20 race-weighted means; 22,213 Brier observations |
| Top-10 Brier | 0.144645 (grid baseline 0.169086) | 20 race-weighted means; 22,213 Brier observations |
| Inclusive P05-P95 finish-interval coverage | 82.26% | 16,508/20,001 classified finishers |
| Signed planned-stop timing error | +1.174 laps | 695 matched stops across 20 races |
| Top-action agreement with observed team calls | 17.22% | 695 matched stops across 20 races |

PAC-06 remains unmet: Bayesian MAE was 0.538745 s versus linear MAE 0.364033 s (-47.99%). This phase does not retune or rescore that result.

## Runtime and CI

The configured 50,000-race budget and existing pace consumers are unchanged. The repository CI workflow runs the complete lint, type, and test suite on Ubuntu and Windows.

Final code commit: `f53183e`.

- Ubuntu (`ubuntu-latest`): run #44275275671 for code commit `f53183e`; status success. [CI run](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/44275275671)
- Windows (`windows-latest`): run #44275275671 for code commit `f53183e`; status success. [CI run](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/44275275671)

---
*Phase: 10-point-mass-pacemodel*
*Report date: 2026-11-18*
