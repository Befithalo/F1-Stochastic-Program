---
phase: "09"
plan: "02"
subsystem: data
tags: [openf1, as-of, telemetry, coverage, physics-input]
status: complete
dependency_graph:
  requires: [09-01 acceptance contracts, existing RaceSnapshot visibility boundary]
  provides: [cutoff-safe optional telemetry inputs, immutable PhysicsInput, local coverage audit, bounded Bahrain probe]
  affects: [09-03 geometry, 09-04 parameter sensitivity, Phase 10 point-mass model]
tech_stack:
  added: []
  patterns: [optional normalized channels, source UTC plus race clock, coverage-driven cached-lap fallback]
key_files:
  created:
    - src/f1si/data/physics_input.py
    - src/f1si/data/coverage_audit.py
    - .planning/phases/09-data-and-geometry-readiness/09-OPENF1-COVERAGE.json
  modified:
    - src/f1si/data/schema.py
    - src/f1si/data/sources/openf1.py
    - src/f1si/data/_snapshot.py
    - src/f1si/data/_db.py
    - src/f1si/data/loader.py
    - tests/data/test_physics_input.py
    - tests/data/test_openf1.py
    - DECISIONS.md
decisions: [DEC-137]
requirements-completed: [DAT-01]
metrics:
  completed_date: 2026-11-17
  complete_catalog_races: 87
  expected_catalog_races: 87
  cached_weather_rows: 13928
  cached_car_data_rows: 0
  cached_location_rows: 0
  bahrain_2023_session_key: 7953
  probe_window_minutes: 10
  probe_car_data_rows: 45160
  probe_location_rows: 45580
  probe_weather_rows: 10
  probe_timestamp_fraction_all_channels: 1.0
  focused_data_tests_passed: 127
  probe_requests: 3
actuals:
  tasks: 3
  implementation_commits: 2
---

# Phase 09 Plan 02: Cutoff-Safe Data and Coverage Audit

The optional car-data, location, and weather channels now reach a race-scoped `PhysicsInput` through the existing normalized cache and inclusive as-of cutoff. The input owns defensive frame copies, versioned artifact references, and per-channel coverage and fallback status; it has no cache accessor or database path.

## Accomplishments

- Added normalized OpenF1 car-data and location schemas while preserving source UTC and race-clock seconds. Weather now preserves source UTC when present; old cache rows retain unknown UTC rather than reconstructing it from race-clock time.
- Added additive DuckDB compatibility for optional telemetry tables and missing legacy tables. Existing reads return correctly shaped empty frames until those tables are populated.
- Kept the existing `visible_at_s IS NOT NULL AND visible_at_s <= cutoff_s` snapshot gate. The prepared input retains visibility metadata when supplied, copies every public frame on access, and rejects non-snapshot and out-of-sample inputs.
- Recorded DEC-137: a channel requires at least three rows, at least 95% valid source timestamps and race-clock mappings, and a p95 sampling gap of at most 5 seconds for car data/location or 180 seconds for weather. Otherwise the input reports sparse/unavailable coverage and selects cached lap timing as fallback. No interpolation is performed.
- Added a read-only audit for every complete catalog race and a single ten-minute Bahrain 2023 probe using the existing rate-limited OpenF1 cache.

## Coverage Results

The saved audit records 87 complete races, matching the expected catalog size. The local cache contains 13,928 weather rows, no car-data rows, and no location rows. Bahrain session 7953 was queried from 15:03:38.500Z through 15:13:38.500Z, anchored to the earliest lap-one start. All returned rows had valid UTC timestamps and mapped inside the requested race-clock window:

| Endpoint | Rows | Valid timestamps | Race-clock alignment |
|---|---:|---:|---|
| `/car_data` | 45,160 | 100% | aligned |
| `/location` | 45,580 | 100% | aligned |
| `/weather` | 10 | 100% | aligned |

## Verification

- Tracer: `uv run pytest tests/data/test_physics_input.py -k "car_data_cutoff or physics_input_is_immutable" -q` — **2 passed**.
- Final focused integration set covering PhysicsInput, as-of, audit, OpenF1, schema, and DuckDB round-trip behavior — **127 passed**.
- `uv run pytest tests/data/test_coverage_audit.py -q` — **4 passed**.
- `uv run ruff check` on changed production and test files — **passed**; commit hooks also passed Ruff check and formatting.
- The one bounded coverage command generated `09-OPENF1-COVERAGE.json`; it made three channel requests plus cached/rate-limited session and lap metadata requests. No other race received a high-rate request.

## Deviations and Limitations

- The implementation also updates the normalized loader, DuckDB compatibility helpers, mini-race fixtures, and future-scramble guard so existing databases and tests can tolerate optional tables. This was required to make the new time-indexed channels usable without breaking legacy cache reads.
- The audit verifies raw endpoint timestamp validity and ten-minute alignment. The car-data/location gap threshold is applied per driver later when constructing a race `PhysicsInput`, where driver identity and race-clock samples are available together.
- The separate pre-fix repository-wide pytest run was still in progress and is not counted as post-change validation. The phase-end gate will use a fresh full suite and the Ubuntu/Windows CI matrix.

## Task Commits

1. `a133c8f` — prepare cutoff-safe telemetry inputs.
2. `dc387f2` — audit telemetry coverage and fallback quality.

## Next Plan Readiness

Plan 09-03 can now pin and validate the Bahrain geometry artifact independently of approximate OpenF1 location. `PhysicsInput` already carries its versioned geometry reference, and no simulator or strategy consumer changes were needed.
