---
phase: 04-kalman-tire-filter
reviewed: 2026-11-13T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/f1si/pace/kalman.py
  - src/f1si/plots/wear_filter.py
  - src/f1si/cli.py
  - src/f1si/state.py
  - src/f1si/sim/kernel.py
  - src/f1si/sim/draws.py
  - src/f1si/sim/numpy_backend.py
  - src/f1si/synthetic/generator.py
findings:
  critical: 0
  warning: 5
  info: 5
  total: 10
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-11-13
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

I traced the Kalman maths, the no-look-ahead path, the simulator wiring, `state.py` and the generator. I found no provable Critical defect. The checks that came out clean:

- **Kalman maths:** the Joseph form, the symmetrisation and the 3-state F and H are correct. The first-lap predict skip is correct. The diffuse start is numerically safe (cancellation error is about 1e-9 relative). `posterior_rate_sd` matches Gaussian conditioning. The q > 0 path works (Q = diag(0, q^2, 0), applied once per lap).
- **Gate:** it behaves as DEC-090 says, with n_used >= 3 and no two rejections in a row.
- **Look-ahead:** the CLI builds a fresh snapshot, fit and filter per cutoff. `cutoff_row` filters `race_lap <= cutoff_lap`, and each row depends only on earlier laps of its own stint.
- **Simulator:**
  - The mean correction `delta*(a+1-age0)` for `a >= age0` matches the wear term `(age+1-wear_age_off)`.
  - Real compounds have offset 0, so fit cars are unchanged.
  - The opportunistic SC rule still sees the real age.
  - The new draw stream is spawned fifth, after the four existing ones, with one column per car, so CRN holds.
  - Eligibility rejects prior-only entries, unknown compounds and negative or non-finite SD.
- **JSON:** `wear_source` is written only for "filter" and read with default "fit", so old JSON loads and re-dumps unchanged.
- **Generator:** with an empty deviation mapping, `wear + 0.0` is bit-identical. Deviations are applied only to the driver at index i, on all of that driver's stints. The truth key `10 + i` matches `number = 10 + i`.

The remaining issues are robustness and display defects, listed below.

## Warnings

### WR-01: CLI never shows rows the driver skipped between cutoffs (undercounted laps, gaps in table and plot)

**File:** `src/f1si/cli.py:818-827`
**Issue:**
- Each cutoff keeps only the single newest visible row, and `shown` dedupes by race lap.
- If a car's newest visible lap jumps by more than one between two cutoffs, the intermediate lap is never collected. This happens when the car sits in the pit lane, or after a long stop while the leader laps at pace.
- Those laps then vanish from the per-stint table, the "laps used / skipped" counts and the plot.
- The as-of data for those laps was visible (at the later cutoff) and is available in `results`, so this is a display and accounting defect, not a look-ahead one.

**Fix:** At each cutoff, add every row of the driver with `race_lap <= cutoff` and `race_lap not in shown`, in lap order. Keep each lap's first as-of version. For example, expose a `cutoff_rows(results, number, cutoff)` that returns all such rows.

### WR-02: Missing lap rows inside a stint are not predicted across

**File:** `src/f1si/pace/kalman.py:413-421`
**Issue:**
- `observe` advances exactly one lap per call, but `filter_stints` calls it once per lap row present.
- If a lap row is absent from the laps table (a data gap, or an unrecorded lap), the level and rate covariance skip a transition.
- The level then moves by one lap's `rate + fuel_dev` instead of two, so a later lap's innovation is biased and the gate or the rate can be wrong.
- `tyre_age` jumps by more than one at such a gap, so the information is available.

**Fix:** Before observing a lap, call `wear_filter.observe(None, "missing lap")` for each race lap between `previous_race_lap + 1` and `race_lap - 1`. Or derive the number of predicts from the `race_lap` difference.

### WR-03: `resolve_priors` can crash on a non-finite fuel SE and mixes fit and generic sources inconsistently

**File:** `src/f1si/pace/kalman.py:344-361`
**Issue:**
- The rate branch checks `rate` and `se` are finite. The fuel branch checks only `fuel` is finite; `report.fuel_se` is used without a finite check.
- A NaN `fuel_se` makes `fuel_sd` NaN, `WearPrior.__post_init__` raises ValueError, and the CLI replay dies with a traceback at that cutoff. `_FRIENDLY_VALUE_ERRORS` may hide the cause.
- `fuel_known` tests only `fuel_s_per_lap is not None`. If `fuel_se` is None while the fuel effect is set, the rate comes from the fit but the fuel correction comes from the generic prior. That mixes a rate prior conditional on the fitted fuel with a different fuel mean.

**Fix:** Treat fuel as fit-derived only when both the fuel and `fuel_se` are finite. Use the same flag (`fuel_ok`) for the rate branch, so both fall back together.

```python
fuel_ok = (
    report.fuel_s_per_lap is not None
    and report.fuel_se is not None
    and math.isfinite(report.fuel_s_per_lap)
    and math.isfinite(report.fuel_se)
)
```

### WR-04: No compound or stint consistency check when `wear_filter` replaces the fit values

**File:** `src/f1si/state.py:603-608`, `src/f1si/pace/kalman.py:450-463`
**Issue:**
- `FilterSnapshot` carries no compound or stint.
- `build_race_state` takes the compound and tyre age from the stints table (latest stint row) and the filter's "current stint" from the laps table (the stint of the car's last lap row).
- If the two disagree (a stop around the cutoff, or a retired car's last stint), the old tyre's rate and SD are applied to the new compound's state, and the simulator then uses the filter rate as the new tyre's slope.
- The `cutoff_lap` check does not catch this.

**Fix:** Add `compound: str` and `stint: int` to `FilterSnapshot`. In `build_race_state`, use the filter entry only if `flt.compound == name`. Otherwise keep the fit values and "fit".

### WR-05: Rate prior from the fit includes the very stint being filtered (data used twice)

**File:** `src/f1si/pace/kalman.py:341-373`, `src/f1si/pace/kalman.py:409`
**Issue:**
- `fit_linear_pace(snapshot)` is fitted on all clean laps up to the cutoff, including the current stint's laps of the car being filtered.
- The filter then updates the prior with the same laps. This data double-counts, so the posterior can be too tight on real data.
- `TAU_CAR` softens it, and the recovery tests use independent priors, so the tests cannot reveal it.
- DEC-091 describes the early-fit bias but not this reuse.

**Fix:** At least log it in DEC-091 as a known limitation. Better, refit with the filtered driver's current stint removed, or inflate the SE by `1 / sqrt(1 - leverage)`.

## Info

### IN-01: Gate threshold wording in the module docstring disagrees with the code

**File:** `src/f1si/pace/kalman.py:41-42` and `kalman.py:250`
**Issue:**
- The docstring says the gate applies "from the GATE_MIN_USED-th used lap on", which would be the 3rd used lap (`n_used == 2`).
- The code (`n_used >= GATE_MIN_USED`) first gates the 4th lap, after 3 laps are used. DEC-090 says "at least 3 laps have been used", so the code and DEC agree.

**Fix:** Reword the docstring to "once at least GATE_MIN_USED laps have been used".

### IN-02: `_finite` rejects numpy integer and non-Python float scalars

**File:** `src/f1si/pace/kalman.py:98-100`
**Issue:**
- `isinstance(value, int | float)` accepts `np.float64` (a float subclass) but rejects `np.int64` and `np.float32`.
- A caller passing `fit.report` numbers is fine. A caller passing an array element of an integer dtype gets a confusing "must be a finite number".

**Fix:** Use `numbers.Real` (excluding bool) or convert with `float(value)` after a type check.

### IN-03: `$` in the slug and driver regexes accepts a trailing newline

**File:** `src/f1si/plots/wear_filter.py:28-29`
**Issue:**
- `re.match(r"^[a-z0-9-]+$", "bahrain\n")` succeeds, so `wear_filter_file_name` can build a file name containing a newline when called directly.
- The CLI uses `fullmatch` for the driver and takes the slug from the catalog, so it is not reachable from the CLI today.

**Fix:** Use `re.fullmatch` (or `\Z`) in both checks.

### IN-04: Generator validation of `wear_rate_deviation_s_per_lap` keys is incomplete

**File:** `src/f1si/synthetic/generator.py:303-309`
**Issue:**
- The check `0 <= key < n_drivers` raises a bare TypeError for non-numeric keys and lets non-integer keys such as `1.5` pass. A key like `1.5` is then silently never applied, because `dev.get(i)` looks up integers only.
- `True` is accepted as driver index 1.

**Fix:** Require `isinstance(key, int) and not isinstance(key, bool)` and raise ValueError otherwise.

### IN-05: Gate-rejection count printed by the CLI comes from a different basis than the rows shown

**File:** `src/f1si/cli.py:812-817` and `cli.py:848-849`
**Issue:**
- The "gate rejections" figure is taken from the filter run at the last cutoff (fit as of the last lap).
- The "used / skipped" counts come from rows frozen at their first appearance, each with its own as-of fit. The two can disagree (a lap rejected under the final fit but used when first shown), and the line mixes the two.

**Fix:** Count rejections from the collected rows (`reason == "outlier gate"`), or label the figure "under the final-lap fit".

---

_Reviewed: 2026-11-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
