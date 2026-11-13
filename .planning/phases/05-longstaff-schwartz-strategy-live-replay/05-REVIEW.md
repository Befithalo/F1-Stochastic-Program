---
phase: 05-longstaff-schwartz-strategy-live-replay
reviewed: 2026-11-13T21:57:09Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - DECISIONS.md
  - README.md
  - docs/explained/phase-05.md
  - src/f1si/cli.py
  - src/f1si/sim/numpy_backend.py
  - src/f1si/strategy/longstaff.py
  - tests/conformance/registry.py
  - tests/conformance/test_suites.py
  - tests/guards/consumers.py
  - tests/guards/scramble.py
  - tests/guards/test_future_scramble.py
  - tests/strategy/test_longstaff.py
  - tests/test_cli_replay.py
  - tests/test_docs.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-11-13T21:57:09Z  
**Depth:** standard  
**Files Reviewed:** 14  
**Status:** issues_found

## Summary

Reviewed the Phase 5 implementation, tests, and documentation changes from plans 05-01/02/03. The cutoff-local replay construction and branch comparisons are covered by focused tests and the future-scramble guard. One input-boundary issue remains: replay accepts simulation counts beyond the simulator's configured maximum and reports the invalid request as a successful replay with unavailable cutoffs.

## Warnings

### WR-01: Replay accepts simulation counts above the simulator limit

**Severity:** WARNING  
**File:** `src/f1si/cli.py:1048-1049, 1080-1082`  
**Issue:** Replay validates only that `--n` is positive. The simulator rejects counts above `MAX_RACES` (200,000), but that `ValueError` is converted into an unavailable result for each cutoff and `_cmd_replay` still returns exit code 0. A user who requests an unsupported count therefore receives a successful command with no recommendations, and full replay repeats the misleading unavailable result across the race.
**Fix:** Validate `n_simulations <= MAX_RACES` in `_cmd_replay` before loading race state, and return `_refuse(...)` with exit code 1 when it exceeds the simulator bound. Add a CLI test asserting the over-limit count is rejected before state construction.

---

_Reviewed: 2026-11-13T21:57:09Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
