---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "10"
subsystem: ui, validation
tags: [owner-acceptance, ci, streamlit, phase-gate]
requires:
  - phase: 06-11
    provides: Bahrain replay, real charts and post-rework gates
  - quick: 261116-0hq
    provides: UI design pass (race-strip decision band, DEC-114, DEC-115)
provides:
  - Owner acceptance of the redesigned replay page at desktop and phone widths
  - Exact-head Ubuntu and Windows CI evidence for the accepted implementation
affects: [phase-06-completion]
actuals:
  tasks: 2
  commits: 0
key-files:
  created:
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-10-SUMMARY.md
---

# Plan 06-10 Summary: owner acceptance and exact-head CI

## Outcome

**Approved by the owner on 2026-11-16.** The checkpoint closes on the page the owner reviewed, not
on tests or screenshots alone.

## Task 06-10-01: gates (historical, completed)

The original local and CI gate task completed at commit `4997c1e`. Plan 06-11 reran all gates after
its rework. This summary adds the gates for the final implementation head below.

## Task 06-10-02: blocking owner checkpoint

After Plan 06-11, the owner rejected the earlier page and commissioned the UI design pass (quick
task 261116-0hq: research, ten-problem review, prototype B chosen, copy approved, decisions in
`docs/design/DESIGN_SYSTEM_V2.md` section 10). The redesigned page was then served locally with the
real cache and opened in the owner's Chrome.

The owner reviewed it with this checklist and answered:

| Check | Owner's answer |
| --- | --- |
| 1. Read the decision band ("Stay out to the flag") and check the reasoning reads right | "Makes sense." |
| 2. Set "After lap" to about 10 and check the planned stop and pit window on the strip | "Yes." |
| 3. Pick another team's driver and check the page takes that team's color | "Yes." |
| 4. Narrow the window to phone width and check the layout | "Looks good while small." |

The owner then asked for the Phase 6 wrap-up and the merge into `main`.

Evidence reviewed alongside: full-page captures at 1440 px and 390 px
(`reports/ui-review/v2-1440.png`, `reports/ui-review/v2-390.png`, taken at 1440x900 and 390x844
device metrics and expanded to full height) and the contrast audit
(`reports/ui-review/contrast-v2.md`, 23 measured pairs across every 2023 to 2025 team color, all
passing).

## Exact-head CI

| Commit | Content | Ubuntu | Windows |
| --- | --- | --- | --- |
| `0b428bd` | UI design pass | success | success |
| `08672fe` | Verification warnings resolved (accepted head) | success (run 43829374437) | success (run 43829374437) |

`2759d60` (Bahrain lap-15 test update) sits between them and is covered by the `08672fe` run.

## Local gates on the accepted head

- ruff, ruff format, mypy strict: clean over `src` and `tests`.
- Full suite: 1,131 passed; the only local failures are the `-I` subprocess tests (import order,
  plot import checks, cache lock), which CI runs and passes.
- Network suite `tests/real/test_bahrain_2023.py`: 16 passed.

## Verification

`06-VERIFICATION.md`: 7 of 7 must-haves verified. Its three warnings (README credits, Quickstart
commands, uncalibrated marker on fallback calls) were fixed in `08672fe`.
