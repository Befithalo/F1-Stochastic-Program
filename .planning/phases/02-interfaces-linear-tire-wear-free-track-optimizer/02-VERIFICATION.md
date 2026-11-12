---
phase: 02-interfaces-linear-tire-wear-free-track-optimizer
verified: 2026-11-11T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Push to GitHub and confirm CI is green on Ubuntu and Windows"
    expected: "lint, format, mypy strict and pytest all pass on both runners"
    why_human: "CLAUDE.md quality gate; nothing has been pushed yet"
  - test: "Open reports/wear-bahrain-2023.png"
    expected: "One panel per compound, fuel-corrected clean lap time vs tyre age, points by driver, fitted line and band"
    why_human: "Visual appearance cannot be checked by grep"
  - test: "Read docs/explained/phase-02.md"
    expected: "Plain-language, understandable explainer with file tour and 3-5 interview Q&As"
    why_human: "Clarity is a judgement call (test_docs.py only checks completeness)"
---

# Phase 2 Verification Report

**Phase Goal:** User can get the fastest free-track 1- or 2-stop plan for a race from fitted, fuel-corrected tire wear, behind interfaces later milestones can plug into.
**Status:** human_needed (all automated checks pass; CI on push pending)
**Re-verification:** No, initial verification

## Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | interfaces.py defines PaceModel, StrategyPolicy, SimulatorBackend; mypy strict accepts | VERIFIED | `src/f1si/interfaces.py` (170 lines); `python -m mypy` gives "no issues in 93 source files"; tests/conformance/test_protocols.py proves mypy accepts conformers and rejects wrong signatures |
| 2 | Shared suite runs against each implementation and fails a non-conforming stub | VERIFIED | tests/conformance/{registry,suites,stubs}.py; test_suites.py has honest-pass and bad-stub-rejected tests for pace, policy and simulator; 117 targeted tests pass |
| 3 | RaceState buildable for Bahrain 2023 at any lap, same type consumed later | VERIFIED | `src/f1si/state.py` (513 lines), `build_race_state(snapshot, fit, laps_total=, pit_loss_s=)`; JSON round trip and builder tests pass; scramble-guard consumer `race_state` registered in tests/guards/consumers.py |
| 4 | Fitted fuel-corrected wear rate per compound for Bahrain 2023 | VERIFIED | Real run `python -m f1si wear bahrain-2023`: HARD +0.121 (0.113 to 0.128), SOFT +0.125 (0.118 to 0.133), MEDIUM "not enough data"; fuel -0.078 s/lap reported as measured |
| 5 | Best 1-stop and 2-stop plan with total race time by checking every combination | VERIFIED | Real run `plan bahrain-2023 --driver ALO`: best 1-stop 1:34:16.1, best 2-stop 1:34:03.1 (laps 17, 37), top 5, "Compared against" line; analytic ground-truth tests pass |

**Score:** 5/5

## Locked decisions D-01..D-25

Spot-checked against real CLI output and DEC-061..069 in DECISIONS.md: D-01/D-04 joint fit with SE and CI; D-02/D-22 shared clean-lap rule (drop counts by reason shown); D-03 "not enough data" for MEDIUM; D-05 pit loss median 24.4 s over 42 green stops with spread; D-06/D-08 per-driver start tyre and age, unknown driver lists valid codes; D-15/D-16 output layout; D-17 actionable errors (`--lap 3` refuses with "try --lap 20"); D-19 near-tie note printed; D-20 "Hindsight plan" label; D-25 fuel not clamped, flagged. D-09..D-14, D-21, D-23 covered by the interface, state and builder tests. No violations found.

## Requirements Coverage

| Req | Plans | Status |
|-----|-------|--------|
| INT-01 | 02-01 | SATISFIED |
| INT-02 | 02-01, 02-02, 02-04 | SATISFIED |
| INT-03 | 02-01, 02-03, 02-05 | SATISFIED |
| PAC-01 | 02-02, 02-03, 02-05 | SATISFIED |
| PAC-02 | 02-04, 02-05 | SATISFIED |

All five IDs appear in PLAN frontmatter and in REQUIREMENTS.md. No orphaned Phase 2 requirements.

## Behavioral Spot-Checks

| Check | Result |
|-------|--------|
| Full `pytest` at HEAD | 655 passed, 13 deselected |
| `python -m mypy` | no issues in 93 files |
| `python -m f1si wear/plan` on real Bahrain cache | correct output, errors actionable |

## Anti-Patterns

No TBD/FIXME/XXX markers in src, tests or the explainer (the only grep hit was the literal driver code "XXX" in a test). No stubs found.

## Notes (non-blocking)

- MEDIUM compound has no fit at Bahrain, so no plan uses it; this is by design (D-03).
- Fuel effect is outside the literature range; documented per D-25.
- Ruff was not re-run by the verifier; relying on the orchestrator's gate result.

## Gaps Summary

None. Remaining items are the human checks listed in the frontmatter, chiefly green CI after push.

_Verifier: Claude (gsd-verifier)_
