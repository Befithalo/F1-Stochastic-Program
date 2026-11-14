---
phase: 06-mvp-backtest-streamlit-view-readme
fixed_at: 2026-11-14T09:08:39Z
review_path: .planning/phases/06-mvp-backtest-streamlit-view-readme/06-REVIEW.md
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 06: Code Review Fix Report

**Fixed at:** 2026-11-14T09:08:39Z  
**Source review:** `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-REVIEW.md`  
**Iteration:** 1

**Summary:**
- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Fixed Issues

### WR-01: `finish_interval` ignores `observed=False` for DataFrame inputs

**Files modified:** `src/f1si/backtest/metrics.py`, `tests/backtest/test_metrics.py`  
**Commit:** `8b1cc80`  
**Applied fix:** DataFrame inputs now raise `ValueError` unless `observed=True`; added a regression test that calls the DataFrame form with the default argument.  
**Verification:** `uv run pytest tests/backtest/test_metrics.py -k 'interval_coverage or dataframe_finish_interval'` — 2 passed, 11 deselected. Verification ran in the main checkout (worktrees are disabled in project config).

---

_Fixed: 2026-11-14T09:08:39Z_  
_Fixer: the agent (gsd-code-fixer)_  
_Iteration: 1_
