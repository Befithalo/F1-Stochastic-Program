---
status: partial
phase: 04-kalman-tire-filter
source: [04-VERIFICATION.md]
started: 2026-11-13T00:00:00Z
updated: 2026-11-13T00:00:00Z
---

## Current Test

[awaiting owner decisions on items 1, 2 and 4; CI on item 3]

## Tests

### 1. Narrowing threshold on real data (criterion 1)
expected: The band narrows over the first laps of a real stint. On Bahrain 2023 ALO, 7 used laps narrow the SD by only 5-7% (ratios 0.95, 0.95, 0.93), because the fit prior is tight (SD about 0.03 s/lap) and real noise is high (about 0.48 s). `tests/real/test_wear_filter_bahrain.py` gates "SD after 7 used laps < prior SD" and "SD non-increasing on measured laps". It applies the planned "< 0.9 x prior SD" only when the prior SD is at least 0.05, which ALO never triggers.
claude_review: This is the honest Bayesian result, not a defect. Recommendation: replace the conditional (dead for ALO) with a printed ratio, keeping the two gated assertions, so nothing is silently off.
result: [pending owner decision]

### 2. Early as-of fit bias and WR-05 (honest-band goal on real data)
expected: At lap 14 the as-of Phase 2 fit gave SOFT +0.255 +/- 0.041 s/lap; the end-of-race value is +0.12 to +0.125, so the 95% band excluded it. WR-05: the fit prior includes the filtered car's own laps (4-6% of the prior's clean laps). Both are documented only (DEC-091, explainer).
claude_review: Recommendation: accept for Phase 4 and measure real-data coverage of the wear band across races in the Phase 6 backtest before changing the method. A "not before lap N" rule tuned on one race would be overfitting; a leave-one-car-out fit costs one refit per car per lap.
result: [pending owner decision]

### 3. CI green on the final commit
expected: GitHub Actions passes on Ubuntu and Windows for 41d844b (CLAUDE.md quality gate).
result: [pending: Ubuntu passed, Windows running]

### 4. Wear-filter PNG is readable
expected: `reports/wear-filter-bahrain-2023-ALO.png` shows the estimate line, shaded 95% band, stint boundaries and dashed hindsight line, readably.
result: [pending owner approval]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
