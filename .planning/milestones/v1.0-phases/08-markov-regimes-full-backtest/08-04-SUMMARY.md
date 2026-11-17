---
phase: 08-markov-regimes-full-backtest
plan: "04"
subsystem: evaluation
tags: [holdout, out-of-sample, markov-regimes, future-data-guard]
requires:
  - phase: 08-markov-regimes-full-backtest
    provides: Locked in-sample scoring settings and Markov regime behavior
  - phase: 06-mvp-backtest-streamlit-view-readme
    provides: Cutoff-local predictions and race-cluster scoring conventions
provides:
  - Digest-locked 2026-09 through 2026-17 holdout contract
  - Isolated feature-only transition fitting, cutoff prediction, score-once, and read-only verify paths
  - Guard tests for protected result imports and future-insensitive fit/cutoff features
affects: [08-05, 08-06, BKT-05]
actuals:
  tokens: 10106
  tasks: 2
  commits: 3
tech-stack:
  added: []
  patterns:
    - Complete 2023-2025 RACE_END feature snapshots produce one shared transition fit
    - All holdout predictions freeze before the evaluator requests final classifications
key-files:
  created:
    - .planning/phases/08-markov-regimes-full-backtest/08-holdout-lock.json
    - src/f1si/evaluation/__init__.py
    - src/f1si/evaluation/holdout.py
    - tests/backtest/test_holdout.py
  modified:
    - src/f1si/cli.py
    - tests/guards/import_scan.py
    - tests/guards/consumers.py
    - tests/guards/test_consumer_registry.py
    - tests/guards/test_future_scramble.py
key-decisions:
  - "Freeze 2026-09 through 2026-17 with linear pace, 1,000 simulations, seed 0, risk 0.5, and CRC32 race/driver/cutoff seed derivation."
  - "Fit transition and safety-car inputs from complete feature-only 2023-2025 RACE_END snapshots; never use 2026 as training history."
  - "Keep OutOfSampleAccessor import and final-classification access inside f1si.evaluation.holdout, after all predictions freeze."
  - "Do not run the holdout score in this plan; it is reserved for 08-05 after these commits are pushed."
patterns-established:
  - "Verify-existing reads only the committed lock and saved JSON report."
  - "Holdout feature-fit access is registered separately from generic in-sample cutoff consumers."
requirements-completed: []
coverage:
  - id: D1
    description: "Digest-locked holdout evaluator validates settings and preflights before result access."
    requirement: BKT-05
    verification:
      - kind: unit
        ref: tests/backtest/test_holdout.py#test_holdout_lock_freezes_exact_contract_and_digest
        status: pass
      - kind: unit
        ref: tests/backtest/test_holdout.py#test_score_freezes_predictions_before_first_classification
        status: pass
    human_judgment: false
  - id: D2
    description: "Historical transition sequences and current cutoff regime labels ignore unseen future feature rows."
    requirement: BKT-05
    verification:
      - kind: unit
        ref: tests/guards/test_future_scramble.py#test_holdout_fit_and_cutoff_state_ignore_unseen_future_feature_rows
        status: pass
    human_judgment: false
  - id: D3
    description: "Only the holdout evaluator may import the protected out-of-sample accessor."
    requirement: BKT-05
    verification:
      - kind: unit
        ref: tests/guards/test_import_ban.py
        status: pass
    human_judgment: false
plan_head_before: c6ba71928abbee1050ef87d210eab5b275b7a461
plan_head_after: 1ced95816f6635596231f553dfe9a9c2629b51b0
commits: 3
duration: 15min
completed: 2026-11-17
status: complete
---

# Phase 8 Plan 04: Isolated Holdout Evaluator Summary

**The nine-race 2026 holdout is locked behind a feature-only transition fit, cutoff-local prediction path, and single protected result consumer.**

## Performance

- **Duration:** About 15 minutes
- **Started:** 2026-11-17T08:22:00Z
- **Completed:** 2026-11-17T08:37:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Added the SHA-256-bound lock for 2026-09 through 2026-17: era `reg_2026`, linear pace, 1,000 simulations, seed 0, risk 0.5, CRC32 prediction and pace-fit seed derivation, ordered cutoffs, score masks, metrics, and report schema. Lock digest: `a3c1d0c1a7cbd35949ff4811517304295ed090e63ed96ffb20bbebe8e24880da`.
- Added the evaluator and `f1si backtest --report --holdout` / `--verify-existing` paths. The transition model uses only complete 2023-2025 `RACE_END` feature snapshots; a synthetic feature-only history is supplied to cutoff preparation so no 2026 history anchor is requested.
- Enforced preflight ordering: lock, exact settings, output absence, and catalog completeness are checked before prediction; all predictions are frozen before final classifications are requested; verification reads only the lock and report.
- Restricted `OutOfSampleAccessor` to the evaluator, registered the single feature-fit accessor consumer, and added synthetic future-feature scrambling coverage.
- Did not run the holdout score or access any 2026 final classifications/outcomes.

## Task Commits

1. **Task 08-04-01: Implement and commit the holdout lock and evaluator** — `3732f59`
2. **Task 08-04-01 correctness follow-up: Align score targets and locked seed derivation** — `05edeeb`
3. **Task 08-04-02: Restrict protected imports and guard future-sensitive fit paths** — `1ced958`

All three commits were pushed to `gsd/phase-06-mvp-backtest-streamlit-view-readme` before the next plan work.

## Verification

- `uv run pytest tests/backtest/test_holdout.py -q` — **5 passed**.
- `uv run pytest tests/backtest/test_holdout.py tests/guards/test_import_ban.py -q` — **99 passed**.
- `uv run pytest tests/guards/test_future_scramble.py::test_holdout_fit_and_cutoff_state_ignore_unseen_future_feature_rows tests/guards/test_import_ban.py tests/guards/test_consumer_registry.py -q` — **115 passed**.
- Ruff check and formatting passed; task commits also passed the repository pre-commit hooks.
- The complete legacy `tests/guards/test_future_scramble.py` module was not run because its table-level fixture reads and rewrites synthetic 2026 result rows. The required holdout-specific synthetic feature-scramble test, import-ban tests, and consumer-registry tests passed without calling the final-classification door.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Matched scoring targets and deterministic seeds to the committed contract**
- **Found during:** Task 08-04-01 review
- **Issue:** Initial evaluator seed derivation differed from the established CRC32 contract, and unclassified starters were omitted from Brier denominators.
- **Fix:** Reused Phase 6 CRC32 race/driver/cutoff seed derivation, included unclassified starters as podium/top-ten failures, and refreshed the lock digest.
- **Files modified:** `src/f1si/evaluation/holdout.py`, `08-holdout-lock.json`
- **Verification:** Holdout unit tests passed.
- **Committed in:** `05edeeb`

**2. [Rule 3 - Verification boundary] Kept the legacy fixture-backed future-scramble suite unrun**
- **Found during:** Task 08-04-02 verification
- **Issue:** The broad legacy suite reads and mutates synthetic 2026 result rows, conflicting with the explicit no-outcome-access instruction for this work.
- **Fix:** Added and ran targeted synthetic feature-only scramble coverage, import-ban tests, and consumer-registration tests. No production or synthetic final-classification call was made.
- **Files modified:** `tests/guards/test_future_scramble.py`
- **Verification:** The targeted guard command passed (115 passed).
- **Committed in:** `1ced958`

## Issues Encountered

- The GSD shell helper was unavailable in PowerShell; the installed `gsd-tools.cjs` CLI was used for state updates.
- Requirement BKT-05 remains pending until the once-only score in Plan 08-05 is completed.

## User Setup Required

None.

## Next Phase Readiness

Plan 08-05 can perform the single holdout score against this pushed lock and evaluator. Do not tune or rescore the holdout after seeing its results.

---
*Phase: 08-markov-regimes-full-backtest*
*Completed: 2026-11-17*

## Self-Check: PASSED

- The lock, evaluator, tests, and summary are present.
- Task commits `3732f59`, `05edeeb`, and `1ced958` are ancestors of the current head.
- No holdout report was created and no 2026 final classification was requested.
