---
phase: 06-mvp-backtest-streamlit-view-readme
reviewed: 2026-11-14T12:27:24Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - src/f1si/backtest/scoring.py
  - src/f1si/cli.py
  - tests/backtest/test_metrics.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-11-14T12:27:24Z  
**Depth:** standard  
**Files Reviewed:** 3  
**Status:** issues_found

## Summary

Reviewed the diagnostics-only report extension, its CLI input path, and its focused scoring tests. An existing report can pass validation after plausible but fabricated probability metrics, denominators, or uncertainty metadata are substituted; the extension then rewrites that report with new diagnostics while preserving the altered probability results. Invalid JSON roots also escape the CLI's friendly error handling as uncaught exceptions.

## Narrative Findings (AI reviewer)

### CR-01: Diagnostics-only trusts tampered probability metrics and sample metadata

**Severity:** BLOCKER  
**File:** `src/f1si/backtest/scoring.py:438-623`
**Issue:** The validator checks the seed, simulation count, and risk, but ignores the report's deterministic `bootstrap_seed` and `bootstrap_resamples` and the paired-mask/uncertainty method declarations. It only checks that a paired interval is numerically plausible and its mean matches model mean minus baseline mean; fabricated `low`/`high` values still pass. It also accepts any positive `brier_observation_count`, any positive plausible `classified_finishers`, and a coverage `per_race` subset (including fewer than all ten registered races) as long as its mean and count agree internally. For example, a ten-race report can be changed to a one-race coverage summary with a matching one-cluster interval, arbitrary positive Brier/finisher counts, and self-consistent Brier means/intervals, then pass the checks and be rewritten by `extend_existing_report`. The checked-in report's measured denominators are 10,942 Brier observations and 9,602 classified finishers, but validation does not establish that incoming counts are those for the authoritative sample. The synthetic extension tests exercise malformed values and internal consistency, not these coherent tampering cases.
**Fix:** Fail closed unless the probability section is bound to trusted measurements. Recompute/verify the probability section and its masks, denominators, deterministic intervals, and method metadata from the authoritative frozen inputs before extending it, or require and verify an integrity binding produced by the original scoring step. Independently require the exact ten coverage race IDs and exact expected bootstrap seed/resample count and method declarations; do not treat internally consistent, user-editable summaries as proof of their provenance.

### WR-01: Invalid report JSON escapes the CLI's handled-error path

**Severity:** WARNING  
**File:** `src/f1si/cli.py:1262-1268`
**Issue:** The report file is parsed directly into `extend_existing_report` without checking that the JSON root is an object or translating JSON decode errors. A truncated/invalid file raises `json.JSONDecodeError`, and valid JSON such as `[]` reaches `.get()` in the validator and raises `AttributeError`; neither is caught by `main`'s `ValueError` handler, so the command produces a traceback instead of its normal diagnostic error.
**Fix:** Parse and validate the root before extension, converting `json.JSONDecodeError` and non-object roots to a `ValueError` with the report path/context so `main` returns its normal nonzero status and concise error.

---

_Reviewed: 2026-11-14T12:27:24Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
