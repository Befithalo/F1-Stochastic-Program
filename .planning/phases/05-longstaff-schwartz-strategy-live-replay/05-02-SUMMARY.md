---
phase: 05-longstaff-schwartz-strategy-live-replay
plan: 02
subsystem: strategy
tags: [as-of-replay, longstaff-schwartz, future-scramble, conformance]
requires:
  - phase: 05-01
    provides: Longstaff policy, selected-cutoff replay, and same-cutoff state construction
provides:
  - Full lap-by-lap replay through the same builder used by selected-cutoff replay
  - Explicit unavailable results when cutoff-visible pace data cannot support a strategy model
  - Future-scramble registration and shared StrategyPolicy conformance for Longstaff
affects: [05-03, replay, strategy]
actuals:
  tokens: 7620
  tasks: 2
  commits: 6
plan_head_before: 6c7d88ac5145edbf65a1330a97c60a0ee0396435
plan_head_after: fc6335e93272470f6bdf4f35f9524f09380fefe8
tech-stack:
  added: []
  patterns: [shared per-cutoff builder, registered replay consumer, explicit unavailable cutoff result]
key-files:
  created:
    - .planning/phases/05-longstaff-schwartz-strategy-live-replay/deferred-items.md
    - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-02-task1-red.json
    - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-02-task2-red.json
  modified:
    - src/f1si/cli.py
    - src/f1si/strategy/longstaff.py
    - tests/test_cli_replay.py
    - tests/guards/consumers.py
    - tests/guards/scramble.py
    - tests/guards/test_future_scramble.py
    - tests/conformance/registry.py
    - tests/conformance/test_suites.py
    - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-02-PLAN.md
key-decisions:
  - "Every cutoff is rebuilt independently from its own snapshot, fit, filter, and RaceState."
  - "A cutoff without an identified visible dry-compound fit is reported unavailable in both full and selected replay; no later laps are used to rescue it."
  - "Race distance remains the D-21 public metadata input; the scramble harness preserves its max-lap key while scrambling observed values."
patterns-established:
  - "Selected and full replay format each cutoff through the same result builder."
  - "The as-of guard registry reuses the CLI cutoff builder and includes supported-cutoff strategy output."
requirements-completed: [STR-01, RPL-01, RPL-02]
coverage:
  - id: D1
    description: Full replay emits ordered cutoff results, including explicit unavailable rows, and selected replay matches its full-replay row.
    requirement: RPL-01
    verification:
      - kind: integration
        ref: tests/test_cli_replay.py#full replay ordering and selected-row equivalence
        status: pass
      - kind: integration
        ref: tests/test_cli_replay.py tests/test_cli.py tests/test_cli_simulate.py (54 passed)
        status: pass
    human_judgment: false
  - id: D2
    description: Replay output is unchanged when future race observations are scrambled at a supported cutoff.
    requirement: STR-01
    verification:
      - kind: integration
        ref: tests/guards/test_future_scramble.py#test_strategy_replay_ignores_future_at_a_supported_cutoff
        status: pass
      - kind: integration
        ref: tests/guards (201 passed in the full guard/docs invocation before the deferred docs check)
        status: pass
    human_judgment: false
  - id: D3
    description: LongstaffSchwartzPolicy runs through the shared deterministic, legal-action, no-mutation conformance suite.
    requirement: STR-01
    verification:
      - kind: integration
        ref: tests/conformance (31 passed)
        status: pass
    human_judgment: false
duration: 25min
completed: 2026-11-13
status: complete
commits: 6
---

# Phase 05 Plan 02: Full As-of Replay Summary

**Lap-by-lap strategy replay now rebuilds each cutoff independently and reports unsupported early cutoffs without look-ahead.**

## Performance

- **Duration:** about 25 minutes
- **Started:** 2026-11-13T15:43:58Z
- **Completed:** 2026-11-13T16:08:39Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments

- Made `--lap` optional and added ordered full replay. Every row rebuilds its snapshot, pace fit, Kalman filter result, current wear snapshot, and RaceState through `AsOfAccessor`.
- Used one result builder and row formatter for selected and full replay. Cutoffs without an identified cutoff-local dry-compound model return an explicit unavailable result; the CLI does not use later laps to supply a fit.
- Registered the replay consumer in sampled and full-grid future-scramble checks and registered LongstaffSchwartzPolicy in shared StrategyPolicy conformance.
- Kept the public race-distance input stable in the scramble harness while all future observation values remain scrambled. Routed Longstaff seed creation through `f1si.rng.make_rng` to satisfy the project import boundary.

## Task Commits

1. **Task 1: Replay every cutoff through one shared state builder** — `7b1cf6f` (test), `189bfe7` (feat)
2. **Task 2: Register replay with future-scramble and StrategyPolicy conformance** — `a992671` (test), `fc6335e` (feat)

Additional Phase 5 commits: `127a96a` (RNG boundary fix), `931d0e3` (verification contract aligned with Plan 05-03 ownership).

**Plan metadata:** GSD close-out commit includes this SUMMARY and updated tracking files.

## Files Created/Modified

- `src/f1si/cli.py` — optional selected lap, shared cutoff builder, ordered full replay, and explicit unavailable rows.
- `tests/test_cli_replay.py` — full-series ordering, unavailable early cutoff, and selected/full output equivalence.
- `tests/guards/consumers.py` — registered strategy replay consumer using the CLI cutoff builder.
- `tests/guards/test_future_scramble.py` — supported-cutoff future-scramble coverage; existing sampled and full-grid tests automatically include the consumer.
- `tests/guards/scramble.py` — preserve the max-lap key as public distance metadata and keep synthetic future lap rows from changing that distance.
- `tests/conformance/registry.py`, `tests/conformance/test_suites.py` — real Longstaff policy setup and shared conformance registration.
- `src/f1si/strategy/longstaff.py` — use the shared RNG factory.
- `.planning/phases/05-longstaff-schwartz-strategy-live-replay/05-02-PLAN.md` — move the module-tour documentation check to its owning Plan 05-03.

## Decisions Made

- Unsupported cutoff fits produce a clear per-cutoff unavailable result in both replay modes. This preserves same-cutoff behavior and avoids future-lap leakage.
- Kept D-21's public race-distance input. The guard harness now retains a maximum-lap key as metadata while scrambling all its non-key observation values.

## Deviations from Plan

**1. [Rule 3 - Blocking] Fixed the Phase 5 RNG import-boundary failure.**
- **Found during:** Task 2 guard verification
- **Issue:** The guard suite flagged direct `numpy.random.default_rng` use in the Plan 05-01 Longstaff implementation.
- **Fix:** Replaced it with `f1si.rng.make_rng`.
- **Files modified:** `src/f1si/strategy/longstaff.py`
- **Verification:** `tests/guards/test_import_ban.py::test_real_src_tree_is_clean` and the shared policy test passed (4 passed together).
- **Committed in:** `127a96a`.

**2. [Rule 3 - Blocking] Preserved public race-distance metadata under future scrambling.**
- **Found during:** Task 2 supported-cutoff future-scramble test
- **Issue:** Dropping every future lap row could remove the maximum lap key, changing D-21's race-distance input; junk lap 900 rows could also inflate it.
- **Fix:** Retained one max-lap key while scrambling its observation values, and assigned junk future rows new driver keys at lap 1.
- **Files modified:** `tests/guards/scramble.py`
- **Verification:** Supported lap-35 replay remained available and identical after future scrambling; the full guard suite passed.
- **Committed in:** `fc6335e`.

**3. [Plan adjustment] Moved the explainer module-tour test to Plan 05-03.**
- The original Plan 05-02 verification command ran `tests/test_docs.py` before the plan that creates `docs/explained/phase-05.md`. The verification contract now runs guards and decision-log tests here; Plan 05-03 owns the docs test.
- **Committed in:** `931d0e3`.

**Total deviations:** 2 auto-fixed blocking issues and 1 plan verification adjustment. Both fixes were needed to satisfy the Phase 5 guard contract; the documentation adjustment restores plan dependency order.

## TDD Gate Compliance

- **Task 1 RED:** `test_replay_parser_allows_full_series` and related tests failed because `--lap` was required. The persisted unittest report passed `gsd-tools check tdd-red-evidence` with `RED_EVIDENCE_OK` (`05-02-task1-red.json`).
- **Task 1 GREEN:** Full replay integration tests passed (54 passed across replay, core CLI, and simulate CLI).
- **Task 2 RED:** The named conformance registration test failed because `longstaff_schwartz` was absent from `POLICIES`. The persisted report passed `gsd-tools check tdd-red-evidence` with `RED_EVIDENCE_OK` (`05-02-task2-red.json`).
- **Task 2 GREEN:** Future-scramble/conformance registration was implemented; conformance passed 31 tests and the supported-cutoff scramble passed.

## Verification

- `pytest tests/test_cli_replay.py tests/test_cli.py tests/test_cli_simulate.py -x -q` — **54 passed**.
- `pytest tests/conformance -x -q` — **31 passed**.
- `pytest tests/guards/test_future_scramble.py::test_strategy_replay_ignores_future_at_a_supported_cutoff -q` — **1 passed**.
- Full guard/docs invocation — **201 passed**, then the existing docs module-tour assertion failed because Plan 05-03 has not yet added `docs/explained/phase-05.md`. All guard tests had completed successfully before that docs failure. The Plan 05-02 command was corrected to defer docs tests to Plan 05-03.
- `pytest tests/test_docs.py tests/test_decisions_log.py -k 'not test_tour_covers_every_module' -x -q` — **42 passed, 1 deselected**.
- `pytest tests/test_decisions_log.py -x -q` — **29 passed**.
- Ruff check, Ruff format check, and `git diff --check` passed on changed files.

## Issues Encountered

- The current full replay intentionally marks early cutoffs unavailable until a cutoff-visible fit identifies a dry compound. The synthetic long-race fit becomes identified around lap 35; no later rows are used to backfill earlier decisions.
- The Phase 5 explainer test remains assigned to Plan 05-03; no placeholder documentation was added in this plan.
- The GSD progress recalculation handler skipped its update because Phase 5 remains in progress; the plan pointer and ROADMAP counts were advanced to Plan 05-03 / 2 of 3.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 05-03 can document the full/selected replay commands and limitations, then run the Phase 5 documentation test and remaining phase-level validation. The Bahrain cache smoke remains assigned to that plan.

## Self-Check: PASSED

- SUMMARY file exists at the required phase path.
- All six plan commits are ancestors of the current branch HEAD.
- The persisted plan ledger measures six commits from `plan_head_before` to the pre-metadata HEAD.

---
*Phase: 05-longstaff-schwartz-strategy-live-replay*
*Completed: 2026-11-13*
