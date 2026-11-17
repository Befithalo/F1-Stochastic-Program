---
phase: 02-interfaces-linear-tire-wear-free-track-optimizer
reviewed: 2026-11-11T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - src/f1si/cli.py
  - src/f1si/laps.py
  - src/f1si/pace/linear.py
  - src/f1si/plots/wear.py
  - src/f1si/state.py
  - src/f1si/strategy/free_track.py
  - src/f1si/data/_snapshot.py
  - tests/pace/test_linear_recovery.py
  - tests/strategy/test_free_track.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 2: Code Review Report

**Depth:** standard. Source files were read in full. Tests and the remaining listed files were only skimmed (test names and tolerances).

## Summary

The optimizer's prefix-sum indexing checks out: stop at k means in-lap k and out-lap k+1 at age 1, the stint-length bounds are right, and the `table[start, m]` indexing stays in range. The joint OLS design, the rank/condition checks and the MAD loop are mostly sound. No security issues were found. There are no crashes or data-loss defects, but four correctness and robustness warnings remain.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Non-leader cars are priced one lap stale (tire age, lap index, remaining laps)

**File:** `src/f1si/state.py:440-475` (consumed at `src/f1si/strategy/free_track.py:62-65,265-271`)
**Issue:** `RaceState.lap` is the leader's completed laps, N. The snapshot only guarantees that every other car has completed at most N-1 laps (see `asof.py`). `tire_age`, `compound` and `stops_done` come from the car's own last visible lap, so for a car with laps_done = N-1 they describe the end of lap N-1. The optimizer assumes they describe the end of lap N. It prices laps N+1..L starting at age `tire_age+1`.
- The first priced lap carries a tire age that is too low by one, and the fuel index is off by one.
- That driver's own lap N is never priced.
- Plan totals are therefore not comparable between drivers.
- A car that pitted on lap N has its stop missing from `stops_done`.
- `--driver X --lap N` is affected. The default leader is not.

**Fix:** Carry `laps_done` in `CarState` and have the optimizer plan from `car.laps_done`, not `state.lap`, with `remaining = laps_total - laps_done`. Alternatively, document and test that planning is only valid for cars with `laps_done == state.lap`, and refuse otherwise.

### WR-02: Standard errors come from `inv(X'X)` with a condition limit that is too loose

**File:** `src/f1si/pace/linear.py:430` (limit at line 65)
**Issue:** `COND_LIMIT = 1e8` is applied to cond(X), so cond(X'X) can reach 1e16. At that level `np.linalg.inv(X'X)` is numerically meaningless or raises `LinAlgError`, and nothing catches it. The docstring promises that the fit "never raises on shortage". The SE and CI, which feed `wear_sd` and the plotted band, can be garbage while the fit still reports "identified".
**Fix:** Take the covariance from the SVD already computed. Compute `_, sv, vt = np.linalg.svd(X, full_matrices=False)`, then `cov = s2 * (vt.T / sv**2) @ vt`. Also lower the condition limit to about 1e6.

### WR-03: Unknown stint is silently merged into stint 0, which distorts the stint count that gates compounds

**File:** `src/f1si/pace/linear.py:235` (used at `:311-313` and `:440-447`)
**Issue:** `stint.fillna(0)` gives every lap with a missing stint the same id, 0. All of a driver's NaN-stint laps then collapse into one pseudo-stint. `MIN_STINTS_PER_COMPOUND` is then satisfied or failed on fabricated stint identities, and `CompoundFit.n_stints` is wrong. Laps without stint data should be dropped with a reason, not placed into stint 0.
**Fix:** In `_classify`, set `reason = "no stint"` when the stint is NaN. The reason string is also surfaced in `dropped`.

### WR-04: Iterated 3-MAD trimming biases sigma low; `sigma_s` and the SEs are then too small

**File:** `src/f1si/pace/linear.py:412-426,429`
**Issue:** Up to five passes of re-fit and clip at 3 robust sigma truncate the residual distribution. The final `s2 = RSS/(n-p)` is computed on the truncated sample without any consistency correction. `sigma_s` is used as the predictive sd and `se` as `wear_sd`, so both are understated. This conflicts with the "honest uncertainty" goal. Trimming also uses a symmetric rule, although slow outliers (traffic) are the dominant contamination, so it removes more good fast laps than necessary.
**Fix:** Inflate `s2` by the truncated-normal variance factor for a 3-sigma cut (about 1/0.9733 for one pass). Alternatively, report the pre-trim robust sigma. Document the bias in DECISIONS.md.

## Info

### IN-01: Dead assignment

**File:** `src/f1si/pace/linear.py:364`
**Issue:** `design = _build(table, active)` is rebuilt immediately inside the loop at line 366. This costs a wasted pass and creates a variable that could be used unbound if the loop is edited.
**Fix:** Delete line 364.

### IN-02: Identification message is misleading

**File:** `src/f1si/pace/linear.py:398`
**Issue:** The text says "a driver needs two stints on different tyres". Two stints on the same compound with different start laps also identify fuel against wear. The message can mislead users.
**Fix:** Reword to "a driver needs two stints that start on different laps".

### IN-03: `assert` used for control-flow narrowing in CLI

**File:** `src/f1si/cli.py:272-274`
**Issue:** These asserts are stripped under `python -O`. They are guarded by `is_identified`, so this is low risk. It is a robustness smell.
**Fix:** Use explicit `if ... is None: return 1` checks, or narrow through a typed accessor.

### IN-04: Case-sensitive compound handling in `RaceState` JSON

**File:** `src/f1si/state.py:141,147-150`; `src/f1si/strategy/free_track.py:136`
**Issue:** `CarState.compound` and `compounds_used` are not normalised to upper case. The optimizer upper-cases `compound` but not `compounds_used`, so JSON-supplied lower-case names make `used` disagree with `compound`. The effect is wrong legality (an extra or missing "two compounds" check).
**Fix:** Normalise both fields to upper case in `CarState.__post_init__`.

---

_Reviewed: 2026-11-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
