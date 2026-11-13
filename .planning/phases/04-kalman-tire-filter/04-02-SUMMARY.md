---
phase: 04-kalman-tire-filter
plan: 02
subsystem: pace
tags: [kalman, tyre-wear, as-of-adapter, priors, synthetic-recovery, coverage]
requires: ["04-01"]
provides:
  - "f1si.pace.kalman: filter_stints, resolve_priors, current_stint_snapshots, ResolvedPriors, LapRow, StintFilterResult, generic prior constants"
  - "SyntheticRaceSpec.wear_rate_deviation_s_per_lap and SyntheticTruth.driver_wear_rate_s_per_lap"
affects: [04-03, 04-04, 04-05]
tech-stack:
  added: []
  patterns: ["per-quantity prior fallback with source labels", "stint-count binomial band for correlated coverage"]
key-files:
  created:
    - tests/pace/test_kalman_adapter.py
    - tests/pace/test_kalman_recovery.py
  modified:
    - src/f1si/synthetic/generator.py
    - src/f1si/pace/kalman.py
    - tests/test_synthetic.py
    - tests/guards/consumers.py
    - docs/explained/phase-04.md
    - DECISIONS.md
    - tests/test_decisions_log.py
key-decisions:
  - "DEC-091: priors from the same-snapshot fit when identified, generic [ASSUMED] otherwise, labelled per quantity"
  - "DEC-092: PAC-04 accuracy restated (D-17): gate coverage and Bayes-optimal accuracy, report the 10% figure"
requirements-completed: []
duration: ~1h30m
completed: 2026-11-13
---

# Phase 4 Plan 02: Snapshot adapter, priors and PAC-04 recovery Summary

**`filter_stints` turns an as-of `RaceSnapshot` plus its own fit into per-stint, per-lap wear-rate rows with labelled prior sources; synthetic recovery proves 95% coverage inside the 99.9% binomial band and Bayes-optimal accuracy, and prints the 10% figure without gating it.**

## Tasks

| Task | Commit | Result |
|------|--------|--------|
| 1 Generator deviations | 04550a9 | optional per-driver wear deviation, truth exposes per-driver rates; laps-table sha256 of all 4 default races and the long fixture captured BEFORE the edit and reproduced after |
| 2 Adapter, priors, guard, DEC-091 | 402a024 | `filter_stints`, `resolve_priors`, `current_stint_snapshots`; `wear_filter` consumer + 3 CONSUMED entries; 10 adapter tests |
| 3 Recovery tests, DEC-092 | 9ab9147 | 13 recovery tests (coverage, closed form, oracle, optimal accuracy, report) |

## Printed accuracy report (verbatim, real numbers)

```
Wear-rate accuracy at stint lap 8 (7 measured laps), sigma 0.15 s, 2,000 stints each
relative error = mean |estimate - truth| / truth over stints with truth > 0.25 * mu
compound mode        prior only    lap 8  closed form  verdict
SOFT     fuel known       44.5%    19.4%        17.0%  target 10%: not met at honest noise (reported, not gated, D-17)
SOFT     fuel prior       45.9%    22.9%        20.0%  target 10%: not met at honest noise (reported, not gated, D-17)
MEDIUM   fuel known       44.1%    28.3%        25.1%  target 10%: not met at honest noise (reported, not gated, D-17)
MEDIUM   fuel prior       43.6%    31.9%        28.1%  target 10%: not met at honest noise (reported, not gated, D-17)
HARD     fuel known       42.7%    35.0%        32.6%  target 10%: not met at honest noise (reported, not gated, D-17)
HARD     fuel prior       44.9%    38.2%        34.6%  target 10%: not met at honest noise (reported, not gated, D-17)
closed form = sqrt(2/pi) * posterior SD / mu, the best any estimator can reach
```

The measured lap-8 error sits just above the closed-form optimum, as it should. The plan's feasibility figures for the fuel-prior mode (22/31/37%) were 22.9/31.9/38.2% here; DEC-092 records the measured values.

## Verification

- ruff check, ruff format --check, mypy: clean.
- Full suite: 880 passed, 8 failed, 1 error, 19 deselected. The failures and error are exactly the known environment-only set (5 in tests/test_import_order.py, 3 `test_module_imports_without_pyplot`, the db lock error).
- Guards (190 tests) pass including the future-scramble run over `wear_filter`.
- `grep AsOfAccessor|RACE_END src/f1si/pace/kalman.py`: nothing.

## Deviations from Plan

None in behaviour. Notes:

- The pooled coverage band uses n = number of stints (6,000), not number of intervals, because laps of one stint are correlated (a stint's covered fraction has variance at most 0.95 x 0.05, so this band is valid, not loosened). Per-lap and per-compound checks use their own n. Documented in the test docstring and DEC-092.
- The production outlier gate stays on. Exact comparisons (closed-form SD, oracle 1e-9) use stints without a gate rejection; a test asserts fewer than 2% of stints have a rejection. The oracle test uses fuel SD 1e-3 for the "fuel known" case because 1e-6 makes the oracle's 3x3 inversion ill-conditioned; coverage and accuracy tests use 1e-6.
- Test report file keeps `REPORT_TARGET = 0.10` for the printed verdict text only; no assertion compares an error with 10%, so the grep acceptance shows a constant and a print-side comparison, not an assert.
- Requirements not marked complete (orchestrator marks after verification).

## Known Stubs

None.

## Threat surface

No new surface beyond the plan's threat model. T-04-05 to T-04-08 mitigated as planned (single-snapshot fit, scramble consumer, `_classify` skips, spec validation, fixed seeds, no 10% assertion).

## Self-Check: PASSED

Commits 04550a9, 402a024, 9ab9147 exist; created files present.
