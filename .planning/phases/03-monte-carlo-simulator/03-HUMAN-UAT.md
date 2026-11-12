---
status: partial
phase: 03-monte-carlo-simulator
source: [03-VERIFICATION.md]
started: 2026-11-12T19:00:00Z
updated: 2026-11-12T20:00:00Z
---

## Current Test

[awaiting owner approval of item 3]

## Tests

### 1. CI green on push
expected: After pushing main, the GitHub Actions workflow passes on both Ubuntu and Windows (CLAUDE.md quality gate), including the 50,000-race benchmark under 10 s on the CI runners.
result: passed — CI run 43287052118 on cf34ebd: checks (ubuntu-latest) success, checks (windows-latest) success. The benchmark test is in the default selection.

### 2. Finishing-distribution PNG is readable
expected: `uv run f1si simulate bahrain-2023 --driver ALO` writes `reports/sim-bahrain-2023-ALO-lap0.png` with a readable bar chart of P1..P20 shares.
claude_review: Title names driver, race, lap and "hindsight simulation"; mean marked; caption gives mean, median, 90% interval, SC share with the "prior only" source and the limitations.
result: passed — owner viewed the PNG and approved it ("The barchart is good"), 2026-11-12.

### 3. Kernel logic changes after the plans (CR-01, WR-05)
expected: The order/clock sweep keeps clocks strictly increasing along the running order without allowing a second pass per lap; the opportunistic SC stop refuses to end a stint shorter than `min_stint`.
claude_review: Diffs 39f2e40 and fc8cc82 read: the sweep only holds cars back, finishing places come from the final order, the stint check adds `age + 1 >= min_stint` without touching planned stops; both have tests that fail without the fix.
result: [pending owner approval]

## Summary

total: 3
passed: 2
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
