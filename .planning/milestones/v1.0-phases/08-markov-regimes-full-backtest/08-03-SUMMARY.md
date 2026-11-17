---
phase: 08-markov-regimes-full-backtest
plan: "03"
subsystem: backtesting
tags: [walk-forward, cross-fitting, markov-regimes, locked-report]

requires:
  - phase: 08-markov-regimes-full-backtest
    provides: Cutoff-visible Markov regime state and per-regime pit-loss assumptions
  - phase: 06-mvp-backtest-streamlit-view-readme
    provides: Comparable scoring metrics, clean-lap rules, and race-cluster bootstrap
provides:
  - One locked 20-race in-sample report with per-race and per-era denominators
  - Read-only verification of the report against the committed score contract
affects: [08-04, 08-05, 08-06, BKT-03]

actuals:
  tokens: 24533
  tasks: 3
  commits: 9

tech-stack:
  added: []
  patterns:
    - Two-fold cross-fitting excludes each scoring fold from continuation-regression fit paths
    - Ignored measured reports are force-added individually after the locked run

key-files:
  created:
    - reports/backtest/phase-08.json
  modified:
    - .planning/phases/08-markov-regimes-full-backtest/08-in-sample-evaluation-lock.json
    - src/f1si/backtest/scoring.py
    - src/f1si/backtest/walk_forward.py
    - src/f1si/cli.py
    - tests/backtest/test_metrics.py
    - tests/backtest/test_walk_forward.py
    - DECISIONS.md

key-decisions:
  - "D-04 / DEC-124: Score the frozen 20-race 2023–2025 sample with linear pace, 1,000 simulations, seed 0, and risk 0.5."
  - "Fit continuation regressions with two-fold cross-fitting; exclude each scoring fold from its fit paths."
  - "Keep the 2026 holdout separate; this task accessed no 2026 outcomes."

patterns-established:
  - "Freeze the complete cutoff prediction trace before opening final results."
  - "After the single scoring invocation, use only read-only verify-existing checks."

requirements-completed: [BKT-03]

coverage:
  - id: D1
    description: "The exact registered 20-race in-sample sample is scored once under the committed contract, with race and era denominators."
    requirement: BKT-03
    verification:
      - kind: integration
        ref: "uv run f1si backtest --report --output reports/backtest/phase-08.json --verify-existing (parent-run, exit 0)"
        status: pass
    human_judgment: false

duration: 4h 42m
completed: 2026-11-17
status: complete
plan_head_before: 0a1daad4423b9544163eef32bca560268cac368e
plan_head_after: b7c8944da99249957178e41bc692d154dbd14353
commits: 9
---

# Phase 8 Plan 03: Locked In-Sample Backtest Summary

**The locked linear-pace evaluation produced a verifiable 20-race report, with independent continuation fit and scoring paths.**

## Performance

- **Duration:** 4h 42m
- **Started:** 2026-11-17T03:36:57Z
- **Completed:** 2026-11-17T08:18:39Z
- **Tasks:** 3 / 3
- **Files modified by the plan:** 21

## Accomplishments

- Scored the exact ordered sample 2023-01 through 2023-07, 2024-01 through 2024-07, and 2025-01 through 2025-06. All 20 races are `ground_effect_2022_2025`; each race row and the era denominator are retained.
- Used the locked settings: linear pace, 1,000 simulations per prediction, base seed 0, risk 0.5, 2,000 whole-race bootstrap resamples, and lock digest `b13c4ba36eb3b39420407f0c5372fad2224b25eb1c4f260b43a85f78ba751a88`.
- Cross-fitted the continuation regression in two folds. The report confirms each scoring fold is excluded from its regression-fit paths.
- Committed the single report and had the parent run the read-only `--verify-existing` command successfully. No later prediction run was made.

## Report Results

Metrics are race-weighted after within-race averaging. Confidence intervals resample whole races.

| Metric | Model | Baseline / target | Paired or cluster result |
|---|---:|---:|---|
| Podium Brier | 0.0555 | baseline 0.0737 | difference −0.0182; 95% CI [−0.0356, 0.0006] |
| Top-10 Brier | 0.1446 | baseline 0.1691 | difference −0.0244; 95% CI [−0.0526, 0.0082] |
| Inclusive P05–P95 finish interval coverage | 82.26% (16,508 / 20,001 classified finishers) | target 90% | 95% race-cluster CI [77.81%, 86.27%] |
| Matched team stop events | 695 / 712 observed | 17 unmatched | latest recommendation strictly before in-lap |
| Top-action agreement | 17.22% | — | 20 race clusters |
| Signed planned-stop timing error | +1.17 laps | — | 95% race-cluster CI [−1.70, 2.92] |
| Absolute planned-stop timing error | 4.63 laps | — | 95% race-cluster CI [3.18, 6.97] |
| Top action “wait and decide next lap” | 12,002 / 22,213 (54.03%) | — | observed post-fix report frequency |
| Retrospective wear-proxy coverage | 14,095 / 17,126 (82.30%) | — | early-fit bias −0.028 s/lap |

The Brier point estimates favor the model, while both paired 95% intervals include zero. The report labels the wear comparison as retrospective proxy evidence, not latent ground truth; no estimable leave-stint-out reference was available for 2023-03 or 2025-01. Strategy comparisons are descriptive, not claims of competitive superiority.

## Task Commits

1. **Task 08-03-01: Commit the exact in-sample lock and score decisions** — `dcff4da`, `0e24b9f`
2. **Task 08-03-02: Implement the registered runner and Phase 6 metrics** — `020c873`, `149c8ec`, `4996021`, `93332b0`, `e8bc25f`, `e3ef4bf`
3. **Task 08-03-03: Score the committed in-sample lock exactly once** — `b7c8944`

## Decisions Made

- Followed D-04 / DEC-124 for the fixed sample, settings, target masks, scoring definitions, and report structure.
- Used the report’s two-fold cross-fitting scheme to keep continuation-regression fitting independent from each scoring fold.
- Preserved the distinct D-05 holdout boundary. This scoring task did not access 2026 outcomes.

## Deviations from Plan

None in sample or settings. The scorer and report were produced under the committed lock. Because `.gitignore` excludes generated reports, only `reports/backtest/phase-08.json` was force-added for its task commit.

## Verification and Issues Encountered

- `uv run f1si backtest --report --output reports/backtest/phase-08.json --verify-existing`: **passed, exit 0**, run by the parent after score completion. This check was read-only.
- The score command was run once and exited 0. The report records 20 ordered races, the committed lock digest, and per-race/per-era denominators.
- Ubuntu and Windows CI for the preceding implementation commits passed before the scoring task.

## User Setup Required

None.

## Next Phase Readiness

The in-sample backtest report is committed and verified. Plan 08-04 can implement the separately locked holdout evaluator while preserving its result-access boundary.

## Self-Check: PASSED

- The report exists and contains the 20 registered race IDs and the expected lock digest.
- Task commit `b7c8944` exists and is the current plan head before metadata updates.
- The report verifier passed without rescoring.

---
*Phase: 08-markov-regimes-full-backtest*
*Completed: 2026-11-17*
