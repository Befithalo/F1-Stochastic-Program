---
phase: 06-mvp-backtest-streamlit-view-readme
fixed_at: 2026-11-14T12:35:09Z
review_path: .planning/phases/06-mvp-backtest-streamlit-view-readme/06-REVIEW.md
iteration: 2
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 06: Code Review Fix Report

**Fixed at:** 2026-11-14T12:35:09Z
**Source review:** `.planning/phases/06-mvp-backtest-streamlit-view-readme/06-REVIEW.md`
**Iteration:** 2

**Summary:**
- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Verification

Focused checks ran in the main checkout (`workflow.use_worktrees=false`):

- `uv run python -m pytest tests/backtest/test_metrics.py -q -k trusted_probability_evidence` — 5 passed.
- `uv run ruff check src/f1si/backtest/scoring.py tests/backtest/test_metrics.py` passed.
- `git diff --check` passed for the source and test changes before commit; the report was checked afterward.

## Fixed Issues

### CR-01: Diagnostics extension preserves an unbound carry-forward claim

**Files modified:** `src/f1si/backtest/scoring.py`, `tests/backtest/test_metrics.py`
**Commit:** `7d06058`
**Applied fix:** Added the complete top-level `carry_forward_diagnostic` object to the canonical SHA-256 evidence payload and updated the source-pinned digest. Added a regression case that changes the historical observed-finish value and verifies diagnostics extension rejects the report without mutation or running either diagnostic.

---

_Fixed: 2026-11-14T12:35:09Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 2_
