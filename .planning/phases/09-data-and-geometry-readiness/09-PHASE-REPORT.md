# Phase 9 Report — Data and Geometry Readiness

## Parameter evidence

- Eligible complete 2023-2025 in-sample races: 70.
- Clean lap samples used: 57159.
- Effective lap-number pace slope: -0.09104 s/lap (SE 0.02569; 95% CI -0.14139 to -0.04069; identified in 66/70 races).
- Leave-one-race-out estimate change: -0.00105 to +0.02475 s/lap.
- Predictive lap-time sensitivity: `not_estimable_pre_solver`.
- The register separates observable effective pace coefficients from hidden vehicle, fuel, and tire assumptions.
- The screen measures coefficient stability; it does not recover physical parameters.

## Data and geometry readiness

- DAT-01: complete catalog audit covers 87 races.
- Weather: 87 races / 13928 rows.
- Car: 0 races / 0 rows.
- GPS: 0 races / 0 rows.
- Single bounded Bahrain 2023 probe: Probe status: available. /car_data: 45160 rows, 45160 usable, alignment aligned, valid source timestamps 100.0%, status available. /location: 45580 rows, 45580 usable, alignment aligned, valid source timestamps 100.0%, status available. /weather: 10 rows, 10 usable, alignment aligned, valid source timestamps 100.0%, status available.
- GEO-01: pinned Sakhir profile passed its digest, unit, and geometry checks. The raw CSV remains local pending rights clarity.

## Fixed M1 baseline

Copied unchanged from `.planning/M1-BASELINE.md`; not recomputed for M2.

- Podium Brier: 0.055456 (grid baseline 0.073693); 20 race-weighted means, 22,213 observations.
- Top-10 Brier: 0.144645 (grid baseline 0.169086); 20 race-weighted means, 22,213 observations.
- Inclusive P05-P95 finish-interval coverage: 82.26%; 16,508/20,001 classified finishers.
- Signed planned-stop timing error: +1.174 laps; 695 matched stops across 20 races.
- Top-action agreement with observed team calls: 17.22%; 695 matched stops across 20 races.

## Locked boundaries

- PAC-06 remains unmet: Bayesian MAE 0.538745 s versus linear pace 0.364033 s.
  Do not retune or rescore this gate.
- Keep the separate 2026 report outside M2 tuning.
- Preserve the 50,000-race budget and existing `PaceModel` consumer contract.
- No geometry or parameter lookup occurs in the per-lap prediction path.
