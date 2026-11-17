---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "05"
subsystem: backtest
tags: [python, pit-strategy, race-bootstrap, kalman, wear-proxy]
requires:
  - phase: 06
    provides: Frozen ten-race predictions, race-cluster metrics, and measured probability report
  - phase: 04
    provides: As-of Kalman wear estimates and cutoff snapshots
provides:
  - One-to-one, snapshot-safe comparison of observed stops with the latest prior recommendation
  - Per-race top-action agreement and stop-timing error with seeded 95% race-cluster intervals
  - Leave-current-stint-out wear-band proxy coverage, early-fit bias, and own-lap evidence
affects: [BKT-04, backtest, report, phase-06-plans-06-07]
actuals:
  tokens: 14799
  tasks: 2
  commits: 10
  plan_head_before: 95aa997bbc41ea9a5987c710503c467ff0054b02
  plan_head_after: dadafe6ceeaf72745723256b7c1dd78b03d777ab
tech-stack:
  added: []
  patterns:
    - One observed event per match, selected only from a strictly earlier and event-invisible snapshot
    - Equal-race summaries with seeded whole-race bootstrap intervals
    - Retrospective leave-current-stint-out fits isolated from Kalman parameters
key-files:
  created:
    - src/f1si/backtest/strategy.py
    - src/f1si/backtest/wear_diagnostic.py
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-05-01-red.json
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-05-01-red.xml
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-05-02-red.json
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-05-02-red.xml
  modified:
    - src/f1si/backtest/scoring.py
    - src/f1si/cli.py
    - tests/backtest/test_strategy.py
    - tests/backtest/test_wear_diagnostic.py
    - reports/backtest/phase-06.json
key-decisions:
  - "Match each stop to the newest strictly earlier recommendation whose snapshot did not yet show that event."
  - "Resample whole races for team-call agreement and timing intervals so each race has equal weight."
  - "Fit the wear proxy with the existing pace fitter after removing the evaluated driver stint; keep it labeled as retrospective proxy evidence."
  - "Extend the matching Plan 06-04 report with diagnostics only, preserving its verified seed-0, 1,000-simulation probability metrics."
patterns-established:
  - "Report unavailable proxy races explicitly with null race metrics and a reason."
requirements-completed: [BKT-04]
coverage:
  - id: D1
    description: "Each observed team stop is matched once to a strictly earlier recommendation absent from that cutoff snapshot, with per-race agreement and timing intervals."
    requirement: BKT-04
    verification:
      - kind: unit
        ref: "tests/backtest/test_strategy.py"
        status: pass
      - kind: other
        ref: "uv run f1si backtest --report --diagnostics-only --n 1000 --risk 0.5 --seed 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "Wear-band coverage, early-fit bias, and same-stint own-lap evidence are reported against a leave-current-stint-out proxy."
    verification:
      - kind: unit
        ref: "tests/backtest/test_wear_diagnostic.py"
        status: pass
      - kind: other
        ref: "reports/backtest/phase-06.json"
        status: pass
    human_judgment: false
duration: 1h 15m
completed: 2026-11-14
status: complete
---

# Phase 6 Plan 5: Team Calls and Wear Proxy Summary

**The ten-race report now compares 388 observed stops with snapshot-safe recommendations and measures Kalman wear bands against a retrospective reference that excludes the evaluated stint.**

## Performance

- **Duration:** Approximately 1h 15m
- **Started:** 2026-11-14T09:05:00Z
- **Completed:** 2026-11-14T10:20:57Z
- **Tasks:** 2
- **Files modified:** 11, including the report, tests, and RED evidence

## Accomplishments

- Matched all 388 observed stop events once to the latest earlier recommendation whose snapshot did not show that stop. All 388 matches passed the snapshot-visibility check.
- Reported top-action agreement and signed and absolute stop-timing errors by race, with seeded 95% whole-race bootstrap intervals across ten races.
- Added a separately labeled retrospective wear proxy. Its bands covered 6,398 of 7,678 available estimates (83.3%); early-fit bias averaged -0.00695 s/lap across measurable races.
- Reported current-stint clean-lap share separately (mean 5.49%, 5,958 measurements). The report marks 2023-03 and 2025-01 unavailable because no leave-stint-out reference was estimable from their clean laps.
- Preserved the verified Phase 6 probability metrics at seed 0, 1,000 simulations, and risk 0.5. The team comparison is descriptive and makes no performance-superiority claim.

## Task Commits

1. **Task 06-05-01 RED: Add failing team-stop comparison contract** - 691f536
2. **Task 06-05-01 GREEN: Compare recommendations with observed stops** - b439e52
3. **Task 06-05-02 RED: Add failing leave-stint-out proxy contract** - 724df79
4. **Task 06-05-02 GREEN: Add leave-stint-out wear proxy diagnostics** - 92a36ae
5. **Validate an existing report and compute event-adjacent recommendations** - 0ee92a1
6. **Cache reference fits across cutoffs** - 467aab4
7. **Preserve both RED evidence reports** - c7b3f5b
8. **Publish measured strategy and wear diagnostics** - 8c22b3e
9. **Report unavailable proxy races explicitly** - 54a8edb
10. **Refresh the report with all ten race entries** - dadafe6

## Verification

- uv run python -m pytest tests/backtest/test_strategy.py -q — passed.
- uv run python -m pytest tests/backtest/test_wear_diagnostic.py tests/backtest/test_strategy.py -q — 11 passed.
- Ruff checks and format checks passed for all changed Python files.
- Mypy passed for the strategy, scoring, and wear-diagnostic modules.
- The diagnostics-only report command completed with 388/388 stop matches, ten-race agreement and timing intervals, 7,678 wear-proxy observations, all ten race keys present, and explicit unavailable reasons for two races.

## TDD Gate Compliance

| Task | RED evidence | Semantic RED result | RED commit | GREEN commit |
|---|---|---|---|---|
| 06-05-01 | 06-05-01-red.json and .xml | The target matcher assertion failed because the placeholder returned zero matches; collection and fixtures succeeded. | 691f536 | b439e52 |
| 06-05-02 | 06-05-02-red.json and .xml | The target reference assertion failed because the placeholder returned no other-stint laps; collection and fixtures succeeded. | 724df79 | 92a36ae |

Both RED records passed gsd_run check tdd-red-evidence with RED_EVIDENCE_OK. The focused suite passed after each implementation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Verify event visibility in the chosen cutoff snapshot**
- **Found during:** Task 06-05-01
- **Issue:** A cutoff numerically before an in-lap alone did not prove that the as-of snapshot lacked that event.
- **Fix:** The matcher excludes cutoffs where the event is already visible, then selects the latest remaining safe recommendation.
- **Files modified:** src/f1si/backtest/strategy.py, src/f1si/backtest/scoring.py, tests/backtest/test_strategy.py
- **Verification:** Added a case that backs off from a visible event; focused tests passed.
- **Committed in:** 92a36ae

**2. [Rule 1 - Bug] Exclude the evaluated stint from every part of the retrospective fit**
- **Found during:** Task 06-05-02
- **Issue:** The first proxy draft used a full-race fuel estimate that included the evaluated stint, and a separate fixed-effect regression made lap number and tire age collinear.
- **Fix:** Reuse fit_linear_pace on a race-end snapshot with the evaluated driver stint removed. Cache each resulting reference fit across cutoffs.
- **Files modified:** src/f1si/backtest/wear_diagnostic.py
- **Verification:** Leave-stint-out tests, the full diagnostic report, Ruff, and Mypy passed; kalman.py was not changed.
- **Committed in:** 92a36ae, 467aab4

### Planned Report Extension

The probability report was already measured and verified by Plan 06-04, whose recorded run took 4h27m. Added --diagnostics-only to validate its fixed race IDs, seed, simulation count, and risk before calculating only the new diagnostics. This preserves the existing measured probability section while making the report extension reproducible.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: file_access | src/f1si/cli.py | --diagnostics-only reads the user-selected report path and validates the registered race IDs, seed, simulation count, risk, and metrics section before updating it. |

## Known Unavailable Proxy Races

The leave-stint-out fit did not identify a wear reference for races 2023-03 and 2025-01; the JSON reports these with a zero denominator, null proxy summaries, and an explicit reason. The other eight races have race-level coverage, early-bias, and own-lap summaries.

## Next Phase Readiness

Requirement BKT-04 is complete. The report keeps retrospective proxy evidence separate from the probability score and leaves the Kalman filter parameters unchanged.

## Self-Check: PASSED

All listed source, test, report, and RED evidence files exist. All ten task and report commits are ancestors of HEAD.

---
*Phase: 06-mvp-backtest-streamlit-view-readme*
*Completed: 2026-11-14*
