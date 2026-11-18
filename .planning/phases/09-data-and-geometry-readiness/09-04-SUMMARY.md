---
phase: "09"
plan: "04"
subsystem: parameters
tags: [parameter-register, sensitivity, as-of, identifiability, closeout]
status: complete
dependency_graph:
  requires: [09-02 cutoff-safe PhysicsInput, 09-03 pinned geometry profile]
  provides: [versioned fitted-effective register, hidden-assumption register, numeric sensitivity report]
  affects: [Phase 10 point-mass model, Phase 12 held-out-stint comparison]
tech_stack:
  added: []
  patterns: [race-equal evidence pooling, RACE_END snapshots, leave-one-race-out sensitivity]
key_files:
  created:
    - src/f1si/parameters/register.py
    - src/f1si/parameters/sensitivity.py
    - src/f1si/parameters/report.py
    - .planning/phases/09-data-and-geometry-readiness/09-PARAMETER-SENSITIVITY.json
    - .planning/phases/09-data-and-geometry-readiness/09-PHASE-REPORT.md
  modified:
    - src/f1si/parameters/__init__.py
    - tests/parameters/test_register.py
    - DECISIONS.md
    - .planning/phases/09-data-and-geometry-readiness/09-VALIDATION.md
decisions: [DEC-139]
requirements-completed: [PAR-01]
coverage:
  - id: parameter_register
    description: Effective pace coefficients are distinct from cited hidden assumptions.
    verification:
      - kind: unit
        ref: tests/parameters/test_register.py#test_register_classifies_effective_terms_and_hidden_assumptions
        status: pass
      - kind: unit
        ref: tests/parameters/test_register.py#test_hidden_physical_parameter_requires_evidence_bounds_and_uncertainty
        status: pass
    human_judgment: false
  - id: parameter_sensitivity
    description: Numeric sensitivity uses cutoff-safe 2023-2025 snapshots only.
    verification:
      - kind: integration
        ref: uv run f1si parameter-evidence-report --coverage-report .planning/phases/09-data-and-geometry-readiness/09-OPENF1-COVERAGE.json --output .planning/phases/09-data-and-geometry-readiness/09-PARAMETER-SENSITIVITY.json --phase-report .planning/phases/09-data-and-geometry-readiness/09-PHASE-REPORT.md
        status: pass
      - kind: unit
        ref: tests/parameters/test_register.py#test_evidence_sensitivity_is_numeric_and_predictive_sensitivity_is_pre_solver
        status: pass
    human_judgment: false
  - id: phase_closeout_report
    description: Closeout records coverage, the Bahrain probe, and the fixed M1 baseline.
    verification:
      - kind: unit
        ref: tests/parameters/test_register.py#test_closeout_contract_carries_coverage_and_exact_m1_baseline
        status: pass
      - kind: integration
        ref: uv run f1si parameter-evidence-report --coverage-report .planning/phases/09-data-and-geometry-readiness/09-OPENF1-COVERAGE.json --output .planning/phases/09-data-and-geometry-readiness/09-PARAMETER-SENSITIVITY.json --phase-report .planning/phases/09-data-and-geometry-readiness/09-PHASE-REPORT.md
        status: pass
    human_judgment: false
  - id: parameter_method_decision
    description: Parameter assumptions and the solver-independent evidence method are recorded.
    verification:
      - kind: manual_procedural
        ref: DECISIONS.md#DEC-139
        status: pass
    human_judgment: true
    rationale: Assumption bounds and their cited regulatory or public-schema interpretation require technical review.
metrics:
  completed_date: 2026-11-17
  eligible_complete_in_sample_races: 70
  clean_lap_samples: 57159
  identified_fuel_effect_races: 66
  effective_lap_number_slope_s_per_lap: -0.0910406659000432
  effective_lap_number_slope_standard_error: 0.0256895879016079
  effective_lap_number_slope_ci_95: [-0.1413922581871947, -0.040689073612891716]
  leave_one_race_out_change_range_s_per_lap: [-0.0010535524676296287, 0.024748359033349474]
  local_complete_catalog_races: 87
  cached_weather_rows: 13928
  cached_car_data_rows: 0
  cached_location_rows: 0
  bahrain_probe_car_data_rows: 45160
  bahrain_probe_location_rows: 45580
  bahrain_probe_weather_rows: 10
  bahrain_probe_all_channels_aligned: true
  focused_parameter_tests_passed: 10
  pre_solver_predictive_sensitivity: not_estimable_pre_solver
actuals:
  tasks: 3
  implementation_commits: 3
  duration: 17 min
  commits: [1d5d4cf, 6584b60, ec7d5a5]
  phase_level_full_suite_and_ci_matrix: pending
completed: 2026-11-17
---

# Phase 09 Plan 04: Evidence-backed parameter register

Phase 9 now exposes an immutable, versioned register for observable effective pace coefficients and a separate set of cited, season-bounded physical assumptions. Identified values remain in seconds per lap or seconds per tyre-age lap; none are translated into hidden car mass, engine output, fuel mass, or tire state.

## Numeric evidence screen

The reproducible screen used complete, in-sample `RACE_END` snapshots from 2023–2025 through `AsOfAccessor.snapshot`. It fit the existing linear pace model on each snapshot's lap frame only. The cache catalog contained 70 eligible races and 57,159 clean laps. The effective lap-number pace slope was -0.0910407 s/lap (standard error 0.0256896; 95% interval -0.1413923 to -0.0406891), identified in 66 of 70 races. Equal-race leave-one-race-out changes ranged from -0.0010536 to +0.0247484 s/lap. These are stability and identifiability diagnostics; the lap-number term can absorb track evolution. Predictive lap-time sensitivity remains `not_estimable_pre_solver` for Phase 10.

The report records per-race fuel and compound-age estimates, within-fit uncertainty, 95% intervals, sample counts, leave-one-race-out changes, a schema-contract digest, and a canonical evidence digest. Its selected race IDs are limited to 2023–2025. It does not read final classification fields or the 2026 out-of-sample door.

## Data and geometry closeout

- Local cache audit: 87/87 complete catalog races; weather 13,928 rows; car data 0; location 0.
- The one bounded Bahrain 2023 probe is available and aligned: car data 45,160 rows; location 45,580; weather 10; each endpoint has 100% valid source timestamps.
- The pinned Sakhir profile passed its recorded digest and geometry validation. The underlying raw asset remains local and ignored under DEC-138 while file-level redistribution terms remain unclear.
- DEC-139 records register classification, data selection, equal-race pooling, uncertainty, leave-one-race-out sensitivity, and the pre-solver predictive status.

## Fixed M1 baseline

Copied unchanged from `.planning/M1-BASELINE.md`; not recomputed here.

- Podium Brier: 0.055456 (grid baseline 0.073693); 20 race-weighted means, 22,213 Brier observations.
- Top-10 Brier: 0.144645 (grid baseline 0.169086); 20 race-weighted means, 22,213 Brier observations.
- Inclusive P05-P95 finish-interval coverage: 82.26%; 16,508 / 20,001 classified finishers.
- Signed planned-stop timing error: +1.174 laps; 695 matched stops across 20 races.
- Top-action agreement with observed team calls: 17.22%; 695 matched stops across 20 races.

PAC-06 remains unmet (Bayesian MAE 0.538745 s versus linear pace 0.364033 s); it was not retuned or rescored. The separate 2026 report remains outside M2 tuning. The 50,000-race budget and existing `PaceModel` consumer contract are unchanged.

## Verification

- `uv run pytest tests/parameters/test_register.py -q` — **10 passed**.
- `uv run ruff check src/f1si/parameters tests/parameters/test_register.py` — **passed**.
- `uv run ruff format --check src/f1si/parameters tests/parameters/test_register.py` — **passed**.
- Report command — **passed**; emitted the numeric JSON and Phase 9 closeout from the local cache and coverage audit.
- Phase-level full-suite and Ubuntu/Windows CI gates remain pending and must pass before routing Phase 10.

## Task Commits

1. `1d5d4cf` — add the versioned fitted-effective and hidden-assumption register.
2. `6584b60` — add cutoff-safe evidence sensitivity and reporting logic.
3. `ec7d5a5` — publish DEC-139, the actual numeric report, and Phase 9 closeout.

## Self-Check: PASSED

- Register and report artifacts exist and serialize successfully.
- Focused task tests, lint, formatting, and the real-cache report command pass.
- The numeric report includes only the 70 complete in-sample 2023–2025 races and marks predictive sensitivity as pre-solver.
