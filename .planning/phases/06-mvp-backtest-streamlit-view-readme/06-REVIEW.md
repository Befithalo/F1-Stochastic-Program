---
phase: 06-mvp-backtest-streamlit-view-readme
reviewed: 2026-11-14T09:05:58Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/f1si/backtest/walk_forward.py
  - src/f1si/backtest/scoring.py
  - src/f1si/backtest/metrics.py
  - src/f1si/cli.py
  - tests/backtest/test_walk_forward.py
  - tests/backtest/test_metrics.py
  - tests/test_cli.py
  - .gitignore
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-11-14T09:05:58Z  
**Depth:** standard  
**Files Reviewed:** 8  
**Status:** issues_found

## Summary

Reviewed the Plan 06-04 walk-forward generation, freeze-gated results join, metric calculations, CLI output path, tests, and report ignore rules. The measured artifact is `reports/backtest/phase-06.json`; the summary records serial/parallel equality through `tests/backtest/test_walk_forward.py::test_serial_and_parallel_full_trace_match_exactly` and the representative Bahrain 2023 ALO cutoffs 12–15 parity check. Those measurements do not replace the implementation review. The prediction module does not import final results, and scoring validates the frozen key set before opening results. One metric API contract defect remains.

## Warnings

### WR-01: `finish_interval` ignores `observed=False` for DataFrame inputs

**Severity:** WARNING  
**File:** `src/f1si/backtest/metrics.py:100-114`  
**Issue:** The DataFrame branch always computes and returns `{"covered", "classified_finishers"}`, regardless of the `observed` argument. Consequently `finish_interval(rows)` silently performs observed-coverage summarization even though the function signature and docstring make that behavior optional. A caller relying on the default gets a different result type and operation than the declared API suggests.
**Fix:** Honor `observed`: reject DataFrame inputs unless `observed=True`, or define and implement a documented non-observed DataFrame result. Add a test that calls the DataFrame form with the default argument and asserts the intended behavior.

---

_Reviewed: 2026-11-14T09:05:58Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
