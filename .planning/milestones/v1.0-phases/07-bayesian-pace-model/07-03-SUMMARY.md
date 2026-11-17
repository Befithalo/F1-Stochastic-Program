---
phase: 07-bayesian-pace-model
plan: "03"
subsystem: pace
tags: [pymc, advi, nuts, synthetic-recovery, convergence]
requires:
  - phase: 07-bayesian-pace-model
    provides: Cutoff-safe training panel and centered pace hierarchy
provides:
  - ADVI failure gate with a 50,000-iteration floor and trailing loss diagnostics
  - Compact 90% posterior intervals for major pace effects
  - Multi-era synthetic recovery and residual predictive-coverage evidence
  - Bounded four-chain NUTS reference with convergence and divergence diagnostics
affects: [07-04, 07-05, backtest, pace-model-selection]
actuals:
  tokens: 11200
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns: [fixed-seed ADVI with a loss gate, shared graph for ADVI and NUTS, synthetic known-truth recovery]
key-files:
  created:
    - tests/pace/test_bayesian_recovery.py
    - docs/explained/phase-07.md
  modified:
    - src/f1si/pace/bayesian.py
    - tests/pace/test_bayesian_model.py
    - tests/sim/test_bayesian_pace.py
key-decisions:
  - "Operational ADVI requires at least 50,000 iterations, finite loss, and no more than 6% relative median movement across a 1,000-value trailing window."
  - "An initial 10,000-step fit looked loss-stable but missed synthetic intercept by 0.81 seconds and fuel slope by 0.029 seconds per lap; the 50,000-step fit recovered the fixed effects within their declared bounds."
  - "The bounded NUTS reference uses 4 chains, 1,000 tuning steps, 400 retained draws per chain, target acceptance 0.99, and maximum tree depth 12; checks require R-hat <= 1.05, bulk ESS >= 100, and divergence fraction <= 1%."
requirements-completed: [PAC-06]
coverage:
  - id: D1
    description: Operational Bayesian fitting rejects non-finite or unstable ADVI trajectories before posterior sampling and records compact convergence summaries.
    requirement: PAC-06
    verification:
      - kind: unit
        ref: tests/pace/test_bayesian_model.py
        status: pass
      - kind: integration
        ref: tests/sim/test_bayesian_pace.py
        status: pass
    human_judgment: false
  - id: D2
    description: Known multi-era synthetic effects recover within fixed tolerances and predictive coverage is measured.
    requirement: PAC-06
    verification:
      - kind: other
        ref: tests/pace/test_bayesian_recovery.py::test_seeded_multiera_panel_recovers_pace_effects_and_predictive_coverage
        status: pass
    human_judgment: false
  - id: D3
    description: A bounded independent NUTS fit to the shared model graph passes the declared convergence checks and records comparison deltas.
    requirement: PAC-06
    verification:
      - kind: other
        ref: tests/pace/test_bayesian_recovery.py::test_four_chain_nuts_reference_is_converged_and_compared_with_advi
        status: pass
    human_judgment: false
duration: 25min
completed: 2026-11-16
status: complete
---

# Phase 7 Plan 03: ADVI Convergence and Synthetic Recovery Summary

**The Bayesian pace fit now gates posterior sampling on a measured ADVI trajectory and recovers declared synthetic effects against an independent NUTS reference.**

## Performance

- **Duration:** about 25 minutes
- **Started:** 2026-11-16 09:30 UTC
- **Completed:** 2026-11-16 09:55 UTC
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added an explicit 50,000-step ADVI floor, a finite-loss check, and a 6% maximum relative movement between medians across the trailing 1,000 loss values. Posterior sampling does not run when the gate fails.
- Added compact 90% intervals for intercept, fuel, team, driver, event, era, fresh compound, wear, and residual noise.
- The deterministic multi-era fixture recovered all declared group means within 0.10 seconds, fuel within 0.01 seconds per lap, and wear within 0.02 seconds per tire-age lap. The measured 90% residual interval covered **90.755%** of training rows.
- The four-chain NUTS reference passed with max R-hat **1.006**, minimum bulk ESS **928.4**, **1 divergence in 1,600 draws**, and one retained draw at the depth-12 cap. NUTS-minus-ADVI mean deltas were −0.0017 seconds for intercept, −0.000089 seconds per lap for fuel, and −0.0048 seconds for residual SD; fuel SD differed by −0.00025 seconds per lap.
- Existing simulator integration still builds and replays a RaceState with shared posterior uncertainty.
- Added the Phase 7 technical explainer required by the repository-wide module-tour completeness check; no UI changes were made.

## Task Commits

1. **Task 07-03-01: Add explicit ADVI convergence and failure handling** - `5185e89` (initial gate; final threshold and diagnostics are in the following commit)
2. **Tasks 07-03-01/02: Calibrate convergence and validate synthetic recovery** - `1981908`

## Decisions Made

- The 10,000-step gate was too permissive: on the full synthetic hierarchy it allowed a stable-looking loss while intercept error was 0.81 seconds and fuel-slope error was 0.029 seconds per lap. The floor is 50,000 steps.
- A 1,000-value window and 6% relative median-change limit accept the seeded operational fixtures while still rejecting deliberate drift and every fit below the iteration floor.
- The independent NUTS reference is considered acceptable at R-hat <= 1.05, bulk ESS >= 100, and divergence fraction <= 1%; the observed reference had one divergence and one max-depth hit. These checks do not assert exact posterior equivalence.

## Deviations from Plan

- The recovery evidence demonstrated that 10,000 iterations were insufficient, so the planned convergence thresholds were tightened and the ADVI floor raised to 50,000. This was based only on synthetic truth, not held-out race results.
- The first NUTS setup had 85 divergences and reached its default depth cap. It was rerun with target acceptance 0.99, 1,000 tuning steps, and maximum depth 12; the final bounded reference met the predeclared diagnostics.
- CI's documentation completeness test found that the new Bayesian modules were not included in any plain-language explainer. Added the Phase 7 technical overview and re-ran the documentation checks.

## Issues Encountered

- PyTensor emits a loop-fusion performance warning on this Windows CPU environment because the optional C++ compiler is unavailable. The fit and diagnostics complete on the CPU fallback.
- A single NUTS divergence and one depth-12 hit remain in the accepted reference. Both counts are recorded; R-hat and ESS pass the declared limits.

## User Setup Required

None - no external service configuration is required.

## Next Phase Readiness

- Phase 7 can now integrate the Bayesian fitter into replay and walk-forward backtests, then lock the holdout before scoring.
- The operational fitter can explicitly refuse a dataset whose ADVI loss remains unstable after its requested iteration budget.

---
*Phase: 07-bayesian-pace-model*
*Completed: 2026-11-16*
