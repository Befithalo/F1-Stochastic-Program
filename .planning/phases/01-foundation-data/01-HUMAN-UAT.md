---
status: partial
phase: 01-foundation-data
source: [01-VERIFICATION.md]
started: 2026-10-22
updated: 2026-10-22
---

## Current Test

[awaiting human testing]

## Tests

### 1. Run the weekly real-data workflow by hand
expected: GitHub → Actions → "Real data (non-blocking)" → Run workflow. The run summary shows "Result: success" (8 network tests). This confirms OpenF1/Jolpica accept GitHub's runners, which is not yet verified. A failure only marks that run red and never blocks CI.
result: [pending]

### 2. Read docs/explained/phase-01.md, including the interview questions
expected: You can explain in your own words why "as of lap 15" shows 15 laps for the leader and at most 14 for the others, and why final results sit behind a separate door.
result: [pending]

### 3. `uv run f1si races` on your machine
expected: "87 races cached (17 out-of-sample and locked)."
result: passed (reproduced by the orchestrator after the cache rebuild, 2026-10-22)

### 4. View reports/bahrain-2023.png
expected: 20 driver panels, compound colours, faded slow laps, dotted stint lines.
result: passed (viewed by the orchestrator, 2026-10-22; regenerated from the rebuilt cache)

## Summary

total: 4
passed: 2
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
