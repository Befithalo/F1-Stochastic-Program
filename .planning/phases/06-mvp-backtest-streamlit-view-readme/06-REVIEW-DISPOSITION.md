---
phase: 06
review: 06-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "Coverage count is paired with a differently weighted percentage"
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "Required schedule distance is absent from the cache source"
  - id: CR-02
    severity: critical
    disposition: fixed
    title: "CLI replay still takes its horizon from race-end observations"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "Brier scoring accepts non-finite and out-of-range probabilities"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "Diagnostics-only mode accepts incomplete probability reports"
open: 0
total: 5
recorded: 2026-11-14T12:01:28.334Z
---

# Phase 06: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | fixed | 06-REVIEW-FIX.md (not in the current review) |
| CR-01 | critical | fixed | 06-REVIEW-FIX.iter3.md (not in the current review) |
| CR-02 | critical | fixed | 06-REVIEW-FIX.iter3.md (not in the current review) |
| WR-02 | warning | fixed | 06-REVIEW-FIX.iter2.md (not in the current review) |
| WR-03 | warning | fixed | 06-REVIEW-FIX.iter2.md (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
