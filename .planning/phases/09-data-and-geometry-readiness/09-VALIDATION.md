---
phase: "09"
slug: "data-and-geometry-readiness"
status: active
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-17"
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + Hypothesis |
| **Config file** | pyproject.toml |
| **Quick run command** | uv run pytest tests/data/test_physics_input.py tests/data/test_coverage_audit.py tests/data/test_asof.py -q |
| **Full suite command** | uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest --cov=f1si --cov-report=term |
| **Estimated runtime** | Under 60 minutes in CI; exact local runtime to be recorded by the executor |

No new test or runtime dependency is planned. The phase extends the existing normalized source/cache loader and validates DuckDB changes through that loader and tests; it creates no schema-push task.

---

## Sampling Rate

- **After every task commit:** Run the task's narrowest automated command below.
- **After every plan wave:** Run the full suite command.
- **Before phase closeout:** Require the repository CI matrix to pass on ubuntu-latest and windows-latest.
- **Max feedback latency:** CI job timeout is 60 minutes; local targeted tests should remain under 120 seconds.
- **Continuity:** Every task has an automated verification command paired with an observable failure condition.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-T01 | 09-01-PLAN.md | 0 | DAT-01 | T-09-01 | Specify exact-cutoff inclusion, future-row exclusion, UTC provenance, fallback, holdout boundary, all-catalog counts, and one bounded probe | Contract collection | uv run pytest tests/data/test_physics_input.py tests/data/test_coverage_audit.py --collect-only -q | Wave 0 creates both modules | green |
| 09-01-T02 | 09-01-PLAN.md | 0 | GEO-01 | T-09-03 | Specify provenance, geometry quality, path confinement, missing-asset, and digest rejection | Contract collection | uv run pytest tests/geometry/test_profile.py --collect-only -q | Wave 0 creates it | green |
| 09-01-T03 | 09-01-PLAN.md | 0 | PAR-01 | T-09-04 | Specify effective-versus-assumed classification, evidence, bounds, numeric sensitivity, pre-solver status, and closeout coverage/baseline fields | Contract collection | uv run pytest tests/parameters/test_register.py --collect-only -q | Wave 0 creates it | green |
| 09-02-T01 | 09-02-PLAN.md | 1 | DAT-01 | T-09-05 | Preserve source time and exclude post-cutoff telemetry through the as-of door | Integration | uv run pytest tests/data/test_physics_input.py -k "car_data_cutoff or physics_input_is_immutable" -q | Created by 09-01-T01 | green |
| 09-02-T02 | 09-02-PLAN.md | 1 | DAT-01 | T-09-06 | Validate timestamped optional payloads and report sparse-channel fallback | Unit + integration | uv run pytest tests/data/test_physics_input.py tests/data/test_asof.py -q | Created by 09-01-T01 | green |
| 09-02-T03 | 09-02-PLAN.md | 1 | DAT-01 | T-09-17 | Audit every complete local race and perform the single bounded Bahrain 2023 probe through the rate-limited cache | Integration + report generation | uv run f1si physics-coverage-audit --output .planning/phases/09-data-and-geometry-readiness/09-OPENF1-COVERAGE.json --probe-race 2023-01 | Created by 09-01-T01 | green |
| 09-03-T01 | 09-03-PLAN.md | 2 | GEO-01 | T-09-11 | Reject path escapes, missing/altered digest, malformed geometry, units, or quality failures | Unit + integration | uv run pytest tests/geometry/test_profile.py -q | Created by 09-01-T02 | green |
| 09-03-T02 | 09-03-PLAN.md | 2 | GEO-01 | T-09-11 | Pin source revision and record file-level rights, transform, attribution, and digest | Integration + provenance review | uv run pytest tests/geometry/test_profile.py tests/data/test_physics_input.py -q | Created by 09-01-T02 and 09-01-T01 | green |
| 09-04-T01 | 09-04-PLAN.md | 3 | PAR-01 | T-09-13 | Keep hidden physical values distinct and require citations, era bounds, and uncertainty | Unit + serialization | uv run pytest tests/parameters/test_register.py -k "register or assumption" -q | Created by 09-01-T03 | green |
| 09-04-T02 | 09-04-PLAN.md | 3 | PAR-01 | T-09-16 | Use only in-sample RaceSnapshot data, report numeric evidence sensitivity, and exclude results/2026 | Unit + report contract | uv run pytest tests/parameters/test_register.py -k "sensitivity or report" -q | Created by 09-01-T03 | green |
| 09-04-T03 | 09-04-PLAN.md | 3 | PAR-01 | T-09-16 | Produce numeric sensitivity, include OpenF1 coverage totals/probe outcome, and publish the required baseline and closeout disclosures | Report generation | uv run f1si parameter-evidence-report --coverage-report .planning/phases/09-data-and-geometry-readiness/09-OPENF1-COVERAGE.json --output .planning/phases/09-data-and-geometry-readiness/09-PARAMETER-SENSITIVITY.json --phase-report .planning/phases/09-data-and-geometry-readiness/09-PHASE-REPORT.md | Created by 09-04-T02 | green |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [x] **09-01-T01 / Plan 09-01 / Wave 0:** tests/data/test_physics_input.py and tests/data/test_coverage_audit.py — cutoff filtering, source UTC/race-clock preservation, per-channel coverage/fallback, immutability, results/holdout boundary, all-catalog counts, and one bounded Bahrain probe with explicit-unavailable behavior.
- [x] **09-01-T02 / Plan 09-01 / Wave 0:** tests/geometry/test_profile.py — manifest and digest, units/transform, quality validation, path confinement, and fail-closed behavior.
- [x] **09-01-T03 / Plan 09-01 / Wave 0:** tests/parameters/test_register.py — fitted-effective versus hidden-assumption classification, evidence, era bounds, uncertainty, and sensitivity fields.
- [x] Wave 0 tasks collect all acceptance tests before production implementation; later plans turn each suite green.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| File-level redistribution and attribution review for the chosen Sakhir geometry asset | GEO-01 | A digest test cannot establish rights for the individual file or its underlying OpenStreetMap/satellite-derived source material | Record the exact asset URL/revision, file-specific terms, attribution, and bundle-or-external decision in docs/geometry/bahrain-2023-profile.json and DECISIONS.md. If rights remain unclear, retain only the local/external asset and provenance reference. |

---

## Validation Sign-Off

- [x] All tasks have automated verification paired with observable failure conditions.
- [x] Sampling continuity has no three consecutive tasks without automated verification.
- [x] Wave 0 covers all three previously missing test suites.
- [x] No watch-mode flags.
- [ ] Feedback latency is within the limits above.
- [x] Set nyquist_compliant: true only after Wave 0 tests and the phase test map are complete.

**Approval:** autonomous execution authorized; Wave 0 collection complete.
