---
status: partial
phase: 02-interfaces-linear-tire-wear-free-track-optimizer
source: [02-VERIFICATION.md]
started: 2026-11-12T00:00:00Z
updated: 2026-11-12T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. CI green on push
expected: After pushing main, the GitHub Actions workflow passes on both Ubuntu and Windows (CLAUDE.md quality gate).
result: passed — CI run 43163632905 on 29648fa, checks (ubuntu-latest) and checks (windows-latest) both success

### 2. Wear PNG is readable
expected: `uv run f1si wear bahrain-2023` writes `reports/wear-bahrain-2023.png` with one panel per compound (HARD, SOFT, MEDIUM "not enough data"), points coloured by driver, a fitted line and a band.
result: [pending]

### 3. Phase 2 explainer reads clearly
expected: `docs/explained/phase-02.md` explains the wear fit, the free-track plan and its limits in plain language (the docs test only checks completeness).
result: [pending]

## Summary

total: 3
passed: 1
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
