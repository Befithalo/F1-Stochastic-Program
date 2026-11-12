---
phase: 02-interfaces-linear-tire-wear-free-track-optimizer
fixed_at: 2026-11-12T00:00:00Z
review_path: .planning/phases/02-interfaces-linear-tire-wear-free-track-optimizer/02-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 2: Code Review Fix Report

**Fixed at:** 2026-11-12
**Source review:** .planning/phases/02-interfaces-linear-tire-wear-free-track-optimizer/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (WR-01 to WR-04; IN-01 to IN-04 out of scope)
- Fixed: 4
- Skipped: 0

Each fix has a regression test that failed before the fix and passes after it.

## Fixed Issues

### WR-03: Unknown stint merged into stint 0

**Files modified:** `src/f1si/pace/linear.py`, `tests/pace/test_fit_no_stint.py`, `DECISIONS.md`, `tests/test_decisions_log.py`
**Commit:** ff8b7fe
**Applied fix:** `_classify` no longer fills a missing stint with 0; such laps are dropped with the reason "no stint" (in `report.dropped`). DEC-070.
**Regression tests:** `tests/pace/test_fit_no_stint.py` (2 tests; both fail on the old code).

### WR-02: SEs from inv(X'X) with a loose condition limit

**Files modified:** `src/f1si/pace/linear.py`, `tests/pace/test_fit_covariance.py`, `DECISIONS.md`, `tests/test_decisions_log.py`
**Commit:** eb478d1
**Applied fix:** covariance is `s^2 V diag(1/S^2) V'` from the thin SVD already computed; `COND_LIMIT` 1e8 to 1e6; a non-converging SVD returns an unidentified fit. DEC-071.
**Regression tests:** `tests/pace/test_fit_covariance.py` (no `np.linalg.inv` call, limit value, SEs equal the textbook formula without trimming). Two fail on the old code.

### WR-04: Iterated 3-MAD trimming biases sigma and SEs low

**Files modified:** `src/f1si/pace/linear.py`, `tests/pace/test_fit_truncation.py`, `tests/guards/consumers.py`, `DECISIONS.md`, `tests/test_decisions_log.py`
**Commit:** 60d8f80
**Applied fix:** when laps were trimmed, sigma is the root of `sigma^2 v(c/sigma) = RSS/(n-p)` with the truncated-normal variance factor `v` and the actual cutoff `c`; SEs use the corrected sigma. New public helpers `truncated_variance_factor` and `untruncated_sigma` (pure math) are registered as EXEMPT in the consumer guard. DEC-072.
**Regression tests:** `tests/pace/test_fit_truncation.py`: factor values, inversion, trimmed sigma within 0.5% of the untrimmed fit and within 3% of the true 0.15 s over 12 seeds (fails without the correction), wear 2-SE coverage at least 85% over 12 seeds. Evidence: 40 seeds, sigma_s / truth = 0.9735 raw, 0.9874 corrected, 0.9884 with no trimming.

### WR-01: Non-leader cars priced one lap stale

**Files modified:** `src/f1si/state.py`, `src/f1si/strategy/free_track.py`, `src/f1si/cli.py`, `tests/strategy/test_free_track_laps_done.py`, `tests/test_state.py`, `tests/guards/consumers.py`, `DECISIONS.md`, `tests/test_decisions_log.py`
**Commit:** 7b17f22
**Applied fix:** `CarState.laps_done: int | None = None` (filled by the builder, JSON key `laps_done`, optional on read, validated <= `lap`), `RaceState.laps_done_of(car)`. Optimizer fast path, `price_plan_slow`, `price_plan`, `decide` ("pit now" = the car's next lap), refusal check and the CLI "laps to plan" line all use the car's own count. Docstring states the free-track assumption (every car priced through `laps_total`, no lapping). `CAR_KEYS` in `tests/test_state.py` extended deliberately. DEC-073 (logic change: requires human verification of the semantics).
**Regression tests:** `tests/strategy/test_free_track_laps_done.py` (7 tests): hand-computed price for a follower one lap behind, fast equals slow, earliest stop lap 20 vs 21, pit_now, JSON round trip and legacy JSON, validation, builder fills laps_done (followers up to 3 laps behind in the synthetic race). All fail on the old code.

## Skipped Issues

None.

---

_Fixed: 2026-11-12_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
