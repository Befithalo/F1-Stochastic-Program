---
phase: 06-mvp-backtest-streamlit-view-readme
reviewed: 2026-11-14T11:33:19Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/f1si/app.py
  - src/f1si/backtest/__init__.py
  - src/f1si/backtest/metrics.py
  - src/f1si/backtest/scoring.py
  - src/f1si/backtest/strategy.py
  - src/f1si/backtest/walk_forward.py
  - src/f1si/backtest/wear_diagnostic.py
  - src/f1si/cli.py
  - src/f1si/strategy/longstaff.py
findings:
  critical: 2
  warning: 3
  info: 0
  total: 5
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-11-14T11:33:19Z  
**Depth:** standard  
**Files Reviewed:** 9  
**Status:** issues_found

## Summary

The review found two blocking correctness issues: the dashboard fan chart uses a different strategy for rival cars than the ranked-option analysis, and races without scheduled-distance metadata derive the forecast horizon from completed race data. Three additional robustness issues affect replay cache invalidation, Brier input validation, and validation of the report extended by diagnostics-only mode.

## Narrative Findings (AI reviewer)

### Critical Issues

#### CR-01: [BLOCKER] Fan chart uses a different rival strategy than the ranked options

**File:** `src/f1si/app.py:169-175`  
**Issue:** The chart simulation forces every rival to stay out while forcing only the selected driver to use the ranked plan. `LongstaffSchwartzPolicy.analyze` evaluates each option by forcing only the target driver's plan; `resolve_plans` then supplies optimizer plans for the other cars. The displayed finish distribution therefore describes a different race scenario from the strategy scores and probabilities shown beside it, and can materially mislead a reader about the selected action.
**Fix:** Use the same opponent-plan resolution as the policy by passing only `{code: selected.plan}` to `simulator.simulate`, allowing the optimizer to resolve rival plans. If the chart is intended to use another scenario, label it explicitly and keep it separate from the ranked option's probability summaries.

#### CR-02: [BLOCKER] Missing schedule distance is inferred from post-race observations

**File:** `src/f1si/backtest/walk_forward.py:155-166`; `src/f1si/cli.py:1015-1017`  
**Issue:** When `scheduled_laps` is absent, `_race_laps_total` reads the race-end snapshot and uses the maximum observed lap as the horizon. That value is then passed to `build_race_state` for every earlier cutoff. The simulator and strategy policy use `laps_total` to determine the finish line and legal stop times, so a shortened or abandoned race can make earlier predictions depend on the distance actually completed. This violates the cutoff-local prediction boundary and can contaminate the fixed-sample evaluation.
**Fix:** Obtain the planned race distance from an ex-ante schedule field/source. If it is unavailable, fail preflight for that race rather than deriving the forecast horizon from completed laps.

### Warnings

#### WR-01: [WARNING] Replay cache identity omits prediction dependencies

**File:** `src/f1si/app.py:41-56`  
**Issue:** The explicit source digest includes only six modules, although replay output also depends on modules such as `backtest/walk_forward.py`, `pace/kalman.py`, `regime/sc_rate.py`, `pace/sparse_fallback.py`, and strategy plan resolution. Editing one of those dependencies while the Streamlit process remains alive leaves `model_identity` unchanged, so `st.cache_data` can serve a replay produced by the old model code.
**Fix:** Build the cache identity from a canonical revision/version that changes with all replay code, or include every transitively relevant source module in the digest.

#### WR-02: [WARNING] Brier scoring accepts non-finite and out-of-range probabilities

**File:** `src/f1si/backtest/metrics.py:33-41`  
**Issue:** The docstring promises a finite-probability mask, but `.notna()` also admits positive/negative infinity and values outside `[0, 1]`. Such values produce invalid Brier scores (including scores greater than 1) instead of failing closed, undermining the evaluation report if an upstream prediction becomes malformed.
**Fix:** Convert each probability column once, reject non-finite or out-of-range values, and form the shared model/baseline mask only from validated probabilities.

#### WR-03: [WARNING] Diagnostics-only mode accepts incomplete probability reports

**File:** `src/f1si/backtest/scoring.py:424-434`  
**Issue:** `extend_existing_report` accepts any report whose race IDs and three metadata fields match and whose `metrics` value is merely a dictionary. A partial report such as `{"metrics": {}}` passes validation, receives only the team and wear diagnostics, and is then written by the CLI as if it were the completed Phase 6 report. Required probability scores, denominators, and schema version are never checked.
**Fix:** Validate the report schema and required probability metric fields before extending it; reject the input without writing if any required Phase 6 result is absent.

---

_Reviewed: 2026-11-14T11:33:19Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
