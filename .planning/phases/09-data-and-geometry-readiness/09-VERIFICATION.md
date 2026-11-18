---
phase: 09-data-and-geometry-readiness
verified: 2026-11-18T06:37:38Z
status: passed
score: 3/3 roadmap truths verified
covered_files:
  - .planning/phases/09-data-and-geometry-readiness/09-01-PLAN.md
  - .planning/phases/09-data-and-geometry-readiness/09-01-SUMMARY.md
  - .planning/phases/09-data-and-geometry-readiness/09-02-PLAN.md
  - .planning/phases/09-data-and-geometry-readiness/09-02-SUMMARY.md
  - .planning/phases/09-data-and-geometry-readiness/09-03-PLAN.md
  - .planning/phases/09-data-and-geometry-readiness/09-03-SUMMARY.md
  - .planning/phases/09-data-and-geometry-readiness/09-04-PLAN.md
  - .planning/phases/09-data-and-geometry-readiness/09-04-SUMMARY.md
  - data/geometry/Sakhir.csv
  - docs/geometry/bahrain-2023-profile.json
  - src/f1si/data/_snapshot.py
  - src/f1si/data/coverage_audit.py
  - src/f1si/data/physics_input.py
  - src/f1si/data/schema.py
  - src/f1si/data/sources/openf1.py
  - src/f1si/geometry/profile.py
  - src/f1si/parameters/register.py
  - src/f1si/parameters/report.py
  - src/f1si/parameters/sensitivity.py
  - tests/data/test_coverage_audit.py
  - tests/data/test_openf1.py
  - tests/data/test_physics_input.py
  - tests/geometry/test_profile.py
  - tests/parameters/test_register.py
covered_digest: "v3:sha256:b1926db13afa3f50788d6b4fce7ac5c75c8275b58a5031e9aad0e3ee80f6c32e"
behavior_unverified: 0
overrides_applied: 0
decision_coverage:
  honored: 9
  total: 9
  not_honored: []
human_verification: []
---

# Phase 9: Data and Geometry Readiness Verification Report

**Phase Goal:** Users can build an auditable, cutoff-safe physics context from existing cached race data, optional historical telemetry/weather, and a rights-reviewed Bahrain geometry profile.
**Verified:** 2026-11-18T06:37:38Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Cached race data and optional OpenF1 telemetry/location/weather produce reproducible cutoff-safe PhysicsInput with source UTC and race-clock mapping; missing or sparse availability is reported with a cached-lap fallback. | ✓ VERIFIED | `build_physics_input` accepts only cutoff-limited `RaceSnapshot`, prepares copied values, checks snapshot cutoff and out-of-sample status, and records optional-channel coverage/fallback. `test_car_data_cutoff_preserves_source_utc_and_race_clock`, `test_future_car_data_perturbation_does_not_change_physics_input`, and coverage/OpenF1 tests pass. Complete-catalog audit reports 87/87 races; cached weather 13,928 rows, car data 0, location 0. The one bounded Bahrain probe records car data 45,160, location 45,580, and weather 10 usable rows; all endpoints have 100% valid timestamps and aligned race clocks. |
| 2 | Bahrain 2023 geometry is versioned and unit-checked, with source, transform, quality, attribution, redistribution terms, and a digest; unclear rights retain the raw asset local. | ✓ VERIFIED | The loader validates manifest metadata, confines the asset path, checks raw-byte SHA-256 and geometry quality. Direct loader spot-check returned digest `bc3c23da42f9474dbf5700341037bb45521acaa2ad1389bd0a48540fe179ee7a`, 1,082 points, and 5,405.749m closed distance. `test_valid_profile_preserves_units_transform_rights_and_digest` passed. The report and DEC-138 keep the source CSV local pending rights clarity. |
| 3 | Effective fitted pace terms are distinguished from hidden vehicle/fuel/tire assumptions, with evidence, era bounds, uncertainty, and sensitivity; the report preserves the exact M1 baseline. | ✓ VERIFIED | Register and report code use only in-sample 2023–2025 `RACE_END` snapshots and `fit_linear_pace`; predictive lap-time sensitivity remains `not_estimable_pre_solver`. Numeric report gives 70 eligible races, 57,159 clean laps, and leave-one-race-out coefficient change −0.00105 to +0.02475 s/lap; it does not recover absolute team parameters. `test_closeout_contract_carries_coverage_and_exact_m1_baseline` passed and the published closeout matches `.planning/M1-BASELINE.md` verbatim in values and denominators. |

**Score:** 3/3 roadmap truths verified (0 present, behavior-unverified).

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/f1si/data/physics_input.py` | Immutable cutoff-safe prepared input | ✓ VERIFIED | Present, substantive; direct RaceSnapshot-only builder and named behavior tests. |
| `src/f1si/data/coverage_audit.py` and `09-OPENF1-COVERAGE.json` | Complete-catalog audit and one bounded historical probe | ✓ VERIFIED | GSD artifact check passed; JSON contains 87 complete races, exact local channel totals and per-endpoint probe quality. |
| `src/f1si/data/schema.py`, `src/f1si/data/sources/openf1.py`, `src/f1si/data/_snapshot.py` | Optional channel schemas, cached ingestion, cutoff-filtered snapshot values | ✓ VERIFIED | GSD artifact check passed; data flow traced through normalization and snapshot into PhysicsInput. |
| `src/f1si/geometry/profile.py`, `docs/geometry/bahrain-2023-profile.json`, `data/geometry/Sakhir.csv` | Validated Bahrain profile and digest-pinned local source | ✓ VERIFIED | GSD artifact check passed; production loader successfully validated actual asset and digest. |
| `src/f1si/parameters/register.py`, `sensitivity.py`, `report.py`; `09-PARAMETER-SENSITIVITY.json`, `09-PHASE-REPORT.md` | Evidence register, sensitivity output, and baseline-preserving closeout | ✓ VERIFIED | GSD artifact check passed; report path imports as-of snapshot and existing linear fitter; exact baseline contract has a passing named test. |
| Requirement-linked tests in `tests/data/`, `tests/geometry/`, `tests/parameters/` | Behavioral acceptance evidence | ✓ VERIFIED | All plan-declared test artifacts passed GSD artifact checks. Five focused named spot checks passed; no disabled tests or test-side expected-value writers were found by the quality scan. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| PhysicsInput tests | `physics_input.py` | Public builder contract | ✓ WIRED | Test imports and calls the builder inside test bodies; cutoff, provenance, fallback and immutability behaviors are asserted. |
| OpenF1 source | normalized schema | UTC and race-clock normalization | ✓ WIRED | Source constructs the schema-defined channel records; normalized optional records are retained in snapshots. |
| Snapshot | PhysicsInput builder | Cutoff-filtered channel values | ✓ WIRED | Builder receives `RaceSnapshot`; exact-cutoff inclusion and future-row perturbation are covered by passing tests. |
| Geometry manifest and profile loader | PhysicsInput | Digest-pinned geometry reference | ✓ WIRED | Actual manifest loads through `load_profile`; its validated reference is carried by PhysicsInput. |
| Parameter report | as-of snapshots and linear pace fitter | In-sample evidence computation | ✓ WIRED | `report.py` imports `RaceSnapshot` and `fit_linear_pace`, enumerates snapshots, and emits versioned evidence without results/holdout inputs. |

The generic `verify.key-links` checker returned “Target not referenced in source” for all 13 declared links because its path-token heuristic does not resolve Python module imports or manifest-to-loader relations. Each link was therefore checked manually against the actual imports/calls and tests; no broken link was found.

### Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces real data | Status |
|---|---|---|---|---|
| PhysicsInput | optional channel frames and coverage | cutoff-limited RaceSnapshot from `AsOfAccessor.snapshot` | Yes | ✓ FLOWING |
| Coverage audit | local channel counts | complete-race catalog and local cache tables | Yes | ✓ FLOWING |
| Coverage audit probe | endpoint records and time alignment | bounded Bahrain OpenF1 requests through the shared cache | Yes; committed probe records 45,160 / 45,580 / 10 usable rows | ✓ FLOWING |
| Geometry profile | coordinate arrays and quality summary | SHA-256-pinned local Sakhir CSV | Yes | ✓ FLOWING |
| Parameter evidence | fit diagnostics | 2023–2025 in-sample RaceSnapshot laps | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Preserve source UTC/race clock and cutoff | `uv run pytest tests/data/test_physics_input.py::test_car_data_cutoff_preserves_source_utc_and_race_clock -q` | 1 passed | ✓ PASS |
| Audit complete local catalog | `uv run pytest tests/data/test_coverage_audit.py::test_local_audit_counts_every_complete_race_and_channel -q` | 1 passed | ✓ PASS |
| Validate real profile provenance and units | `uv run pytest tests/geometry/test_profile.py::test_valid_profile_preserves_units_transform_rights_and_digest -q` | 1 passed | ✓ PASS |
| Preserve exact closeout baseline | `uv run pytest tests/parameters/test_register.py::test_closeout_contract_carries_coverage_and_exact_m1_baseline -q` | 1 passed | ✓ PASS |
| Missing weather retains race and cached timing fallback | `uv run pytest tests/data/test_openf1.py::test_missing_weather_keeps_the_race_and_uses_cached_lap_timing -q` | 1 passed | ✓ PASS |
| Load and validate actual Bahrain geometry asset | `uv run python -c "from pathlib import Path; from f1si.geometry.profile import load_profile; p=load_profile(Path('docs/geometry/bahrain-2023-profile.json'), asset_root=Path('data/geometry')); print(p.reference.sha256, len(p.x_m), p.total_distance_m)"` | digest `bc3c23…79ee7a`; 1,082 points; 5,405.749m | ✓ PASS |

The delegated execution record reports the full suite at 1,315 passed / 33 deselected, with 108 focused tests plus 10 latest coverage-audit tests. These broad suites were not rerun during verification; only the named spot-checks above were run here.

### CI

GitHub Actions run [44247505951](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/44247505951) was independently opened during verification. GitHub reports `Success` on commit `920150678f96b2d8ecb69904ab5e233800cca423` with 2 matrix jobs completed. The run usage page identifies `checks (windows-latest)` and `checks (ubuntu-latest)`; the Phase 09 closeout records both full suites, canary, lint, formatting, and mypy as passed. This checks the final implementation commit and the final summary's stated CI result.

### Fixed M1 Baseline and Phase Closeout

Compared the published closeout values and denominators with `.planning/M1-BASELINE.md`; all five metrics match exactly and remain unmodified:

| Metric | M1 value | Denominator |
|---|---:|---|
| Podium Brier (grid baseline) | 0.055456 (0.073693) | 20 race-weighted means; 22,213 observations |
| Top-10 Brier (grid baseline) | 0.144645 (0.169086) | 20 race-weighted means; 22,213 observations |
| Inclusive P05-P95 coverage | 82.26% | 16,508 / 20,001 classified finishers |
| Signed planned-stop timing error | +1.174 laps | 695 matched stops across 20 races |
| Team-call agreement | 17.22% | 695 matched stops across 20 races |

The report also preserves the 50,000-race budget, leaves PAC-06 unmet and untuned, and excludes the separate 2026 report from M2 tuning.

### Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
|---|---|---:|---:|---|---|---|
| `tests/data/test_physics_input.py`, `tests/data/test_coverage_audit.py`, `tests/data/test_openf1.py` | DAT-01 | Yes | 0 | No test-side expected-value writers found | Behavioral/value | PASS |
| `tests/geometry/test_profile.py` | GEO-01 | Yes | 0 | No test-side expected-value writers found | Behavioral/value | PASS |
| `tests/parameters/test_register.py` | PAR-01 | Yes | 0 | No test-side expected-value writers found | Behavioral/value | PASS |

**Disabled tests on requirements:** 0. **Circular patterns detected:** 0. **Insufficient assertions:** 0.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| DAT-01 | 09-01, 09-02 | Build an auditable cutoff-safe PhysicsInput from cached data and optional OpenF1 channels; report unavailable coverage. | ✓ SATISFIED | Input, catalog/probe audit, source timestamp mapping, fallback and cutoff tests; report includes complete-catalog and bounded probe output. |
| GEO-01 | 09-01, 09-03 | Provide versioned, unit-checked Bahrain 2023 geometry with source/transform/quality/rights metadata. | ✓ SATISFIED | Manifest, local raw CSV and loader pass provenance, digest, geometry-quality and path checks. |
| PAR-01 | 09-01, 09-04 | Separate fitted effective coefficients from hidden assumptions and report evidence, era bounds, uncertainty and sensitivity. | ✓ SATISFIED | Register, numerical evidence report, pre-solver predictive sensitivity status and unchanged baseline assertion. |

No additional Phase 9 requirement mappings were found orphaned from the plans.

### Decision Coverage

All trackable CONTEXT.md decisions are honored by shipped artifacts: **9/9**, none unhonored. The check was run with `check.decision-coverage-verify`.

### Security and Review

`09-SECURITY.md` is secured at ASVS L1: 17 high-severity threat instances mitigated, no open high-severity threats; the planned low-severity dependency risk remains accepted. `09-REVIEW.md` is clean with zero findings after re-review.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| None | — | No unresolved debt markers or production stubs found in the verified changed source scope. Test fixture helpers returning empty data are intentional fixtures. | — | — |

### Human Verification Required

N/A — infrastructure/data-foundation phase with no user-facing UI flow. Rights uncertainty is handled by the recorded decision to keep the raw geometry asset local; no unresolved human choice is required for this phase's acceptance criteria.

### Fixed M1 Baseline

Copied unchanged from `.planning/M1-BASELINE.md`; not recomputed:

| Metric | M1 baseline | Denominator / interpretation |
|---|---:|---|
| Podium Brier | 0.055456 (grid baseline 0.073693) | 20 race-weighted means; 22,213 Brier observations |
| Top-10 Brier | 0.144645 (grid baseline 0.169086) | 20 race-weighted means; 22,213 Brier observations |
| Inclusive P05-P95 finish-interval coverage | 82.26% | 16,508 / 20,001 classified finishers |
| Signed planned-stop timing error | +1.174 laps | 695 matched stops across 20 races |
| Top-action agreement with observed team calls | 17.22% | 695 matched stops across 20 races |

The closeout also preserves the Phase 7 PAC-06 result as unmet and keeps the separate 2026 report outside this baseline.

### Gaps Summary

No goal-level gaps remain. DAT-01, GEO-01 and PAR-01 are supported by implemented, wired artifacts and passing behavioral checks. The raw geometry asset remains local while rights are unclear, as explicitly documented in the accepted method decision.

---

_Verified: 2026-11-18T06:34:16.785Z_  
_Verifier: the agent (gsd-verifier)_
