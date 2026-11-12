---
phase: 03-monte-carlo-simulator
reviewed: 2026-11-12T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - src/f1si/cli.py
  - src/f1si/interfaces.py
  - src/f1si/pace/linear.py
  - src/f1si/plots/simulate.py
  - src/f1si/regime/__init__.py
  - src/f1si/regime/sc_rate.py
  - src/f1si/sim/__init__.py
  - src/f1si/sim/borrow.py
  - src/f1si/sim/constants.py
  - src/f1si/sim/draws.py
  - src/f1si/sim/kernel.py
  - src/f1si/sim/numpy_backend.py
  - src/f1si/sim/plans.py
  - src/f1si/state.py
  - src/f1si/synthetic/generator.py
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-11-12
**Depth:** standard. All files and the diffs of the pre-existing ones (`git diff 93d1fc1..HEAD`) were read. `regime/__init__.py` and `sim/__init__.py` were only checked as package markers and exports.
**Status:** issues_found

## Summary

The kernel, draws and plan code are mostly sound: SC start, freeze and restart match the docstring, the pit-reorder rule works, and nothing was found in plan resolution or the CLI file-path handling. Two correctness problems affect headline guarantees: the finishing order is taken from clocks that the kernel does not keep consistent with its running order, and common random numbers are not stable when a forced plan introduces a new compound.

The review did not report the documented simplifications in DEC-074..085 (SC applied for the whole start lap, restart widening of small gaps, no lapping, uniform tyre wear under SC). It found nothing wrong in the SC-start rule, the SC freeze and restart compression, `pit_loss_sc` on SC laps, the catch-up lap in `_start`, the Beta-Binomial SC estimator, or the `state.py` SC-elapsed logic.

## Critical Issues

### CR-01: Finishing order comes from clocks, but the kernel can leave `clock` inconsistent with `order`

**File:** `src/f1si/sim/kernel.py:177-185`, `src/f1si/sim/numpy_backend.py:297-299`

**Issue:** After a successful pass the kernel sets `arr[c] += pass_cost_s` and breaks, so it never re-checks `arr[c]` against the car now ahead of it, `order[r, j-2]`.

Example (corrected by the orchestrator): `b` arrives at 100.0 and `a` is held at 100.5. `c` has raw arrival 99.5 and passes `a`, so `arr[c]` becomes 99.8. `order` puts `c` behind `b`, but on the clock `c` is 0.2 s ahead of `b`.

`simulate` ranks only by `total_time_s` and discards `order`, so on the last lap the reported positions come from inconsistent clocks. On earlier laps, the next lap's gap checks use `order` while the clocks disagree, so a car can effectively gain two places in one lap. That breaks the documented "at most one pass per car per lap".

**Fix:** Keep clocks non-decreasing along `order` after every green lap, either by clamping after the swap or with a final sweep. Rank the result from the final `order`. Add a property test of the invariant.

### CR-02: Common random numbers break when a forced plan adds a compound

**File:** `src/f1si/sim/numpy_backend.py:164-173, 226-231`

**Issue:** `n_comp` is built from the fitted compounds, each car's tyres and each plan's compounds. It sets both the Sobol dimension (`n_sim + n_cars + n_comp`) and every compound's column index (names are sorted).

A forced plan that uses a compound outside that set therefore has two effects:
- It changes the Sobol dimension, so the scrambled points change.
- It shifts the compound indices.

`u_sc`, `z_off` and `z_wear` then change for every car. This contradicts the CRN claim in `draws.py` and the module docstring ("forcing one driver's plan cannot shift anyone else's draws").

**Fix:** Make the draw layout independent of the plans by using a fixed compound slot layout and indexing `z_wear` by a stable name map. Add a test that forces a plan with a new compound and checks that the other cars' draws are unchanged.

## Warnings

### WR-01: `SyntheticRaceSpec.sc_windows` does not validate `last <= n_laps`

**File:** `src/f1si/synthetic/generator.py` (`sc_windows`, `_sc_events`, lap-time loop)

**Issue:** A window that runs past the last lap passes validation. The laps inside the race are still slowed, but `_sc_events` skips the window when `end.empty`, so no status "4" row appears even though `truth.sc_laps` lists the SC. Synthetic data and ground truth then disagree.

**Fix:** Raise `ValueError` when an SC would end after `n_laps`, or emit the "4" row and a closing "1" at the race end. Also validate `sc_slowdown_factor > 0`.

### WR-02: Overflow in the pure-Python `pass_probability`

**File:** `src/f1si/sim/kernel.py:58`

**Issue:** `math.exp((threshold_s - delta) / scale_s)` raises `OverflowError` in the `py_func` twin when the exponent exceeds about 709, that is when delta is about -140 s or less. The compiled path returns 0.

**Fix:** Return 0.0 when the exponent exceeds 700.

### WR-03: Memory at `MAX_RACES` = 1,000,000

**File:** `src/f1si/sim/constants.py:34`, `src/f1si/sim/numpy_backend.py:228-231`

**Issue:** The Sobol block alone is `(n, n_sim + n_cars + n_comp)` float64, about 0.8 GB at 1e6 races, before the copies and other arrays. That is too generous for a user-facing `--n`.

**Fix:** Lower `MAX_RACES` (for example to 200,000) or draw `u_sc` per lap. State the memory cost in the `--n` help.

### WR-04: `_wear_sd_array` is case-sensitive

**File:** `src/f1si/sim/numpy_backend.py:388-403`

**Issue:** `comp_names` are upper-case, but the lookup uses the caller's raw keys. Keys such as "Hard" silently give a wear SD of zero.

**Fix:** Upper-case the keys once, at construction.

### WR-05: An opportunistic stop under SC can end a too-short stint

**File:** `src/f1si/sim/kernel.py:145-150`

**Issue:** The check only covers the stint after the stop (`stop_lap[c, k+1] - lap < min_stint`). It does not check that the stint being ended has at least `min_stint` laps.

**Fix:** Also require `age[r, c] + 1 >= min_stint`, and document the rule.

## Info

### IN-01: The driver-code regex accepts a trailing newline

**File:** `src/f1si/cli.py:55`, `src/f1si/plots/simulate.py:29-30`

`re.match(r"^[A-Z]{3}$", "VER\n")` matches. Use `re.fullmatch`.

### IN-02: The CLI warm-up repeats the full optimizer pass

**File:** `src/f1si/cli.py:649`

The 64-race warm-up resolves every car's plan again. Warm up with a trivial state or cache the resolved plans.

### IN-03: `simulate` and `plan` handle case and wet tyres differently

**File:** `src/f1si/cli.py:591-593`

`plan` upper-cases `--driver` and refuses drivers who ran wet or intermediate tyres. `simulate` rejects lower-case codes and runs wet drivers with borrowed dry pace. Align the two commands or document the difference.

---

_Reviewed: 2026-11-12_
_Reviewer: Claude (gsd-code-reviewer); file written by the orchestrator from the reviewer's report_
_Depth: standard_
