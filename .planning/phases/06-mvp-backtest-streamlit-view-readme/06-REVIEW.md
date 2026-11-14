---
phase: 06-mvp-backtest-streamlit-view-readme
reviewed: 2026-11-14T12:33:16Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - src/f1si/backtest/scoring.py
  - src/f1si/cli.py
  - tests/backtest/test_metrics.py
findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-11-14T12:33:16Z
**Depth:** standard  
**Files Reviewed:** 3  
**Status:** issues_found

## Summary

The two reported defects are fixed: the source-pinned SHA-256 digest matches the checked-in Phase 06 probability payload, and it binds the complete metadata object plus all four probability metric objects, including their denominators and intervals. Diagnostics validate the digest before running either extension or mutating the report. Invalid JSON and non-object roots now become concise CLI errors. One related integrity gap remains: the digest omits the report's top-level `carry_forward_diagnostic`, which can be edited and then silently preserved while diagnostics are added.

## Narrative Findings (AI reviewer)

### CR-01: Diagnostics extension preserves an unbound carry-forward claim

**Severity:** BLOCKER  
**File:** `src/f1si/backtest/scoring.py:62-67, 671-675`
**Issue:** `_probability_evidence_digest` binds `schema_version`, `race_ids`, the full `metadata` object, and the selected probability metrics, but omits the separately stored `carry_forward_diagnostic` field emitted by `score_registered_sample`. A user can change its `observed_finish` or other historical reference values without changing the digest. `extend_existing_report` then adds diagnostics and returns the same report with that edited claim still present. This lets diagnostics-only processing bless a report containing fabricated, apparently measured carry-forward evidence.
**Fix:** Include `carry_forward_diagnostic` in the source-pinned evidence digest, or compare it against the expected Phase 6 diagnostic payload before adding any diagnostics.

---

_Reviewed: 2026-11-14T12:33:16Z_
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
