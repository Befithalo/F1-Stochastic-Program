---
phase: 01-foundation-data
plan: 08
subsystem: data
tags: [openf1, jolpica, race-source, track-status, pit-lane-start, cli, decisions]

requires:
  - phase: 01-04
    provides: loader, normalized schema, lap_cutoffs and per-lap track status derivation
  - phase: 01-06
    provides: RateLimitedClient, JolpicaClient, derive_track_status
provides:
  - OpenF1Source, the real RaceSource (OpenF1 timing + Jolpica calendar, grid, results, pit stops)
  - "f1si load" defaults to the real source; Ctrl+C exits 130 and keeps finished races
  - Real Bahrain 2023 race in data/f1si.duckdb
  - DECISIONS.md DEC-036..DEC-049
affects: [01-09, 01-10, 01-11, phase-2]

tech-stack:
  added: []
  patterns:
    - "Adapter depends on the JsonGetter protocol, so every adapter test is offline with invented payloads"
    - "Incomplete upstream data raises SourceError ending 'It will be retried on the next run.'"

key-files:
  created:
    - src/f1si/data/sources/openf1.py
    - tests/data/test_openf1.py
  modified:
    - src/f1si/cli.py
    - tests/test_cli.py
    - DECISIONS.md
    - tests/test_decisions_log.py

key-decisions:
  - "pit_lane_start = Jolpica grid 0 AND status not in the never-started set; laps completed is never used (look-ahead)"
  - "Race clock t = 0 at the earliest lap-1 date_start; lap end falls back to the next lap's start"
  - "Circuit is the Jolpica circuitId; round comes from the Jolpica schedule matched by UTC date within one day"

requirements-completed: [DAT-01, FND-04]

duration: ~45 min
completed: 2026-10-22
---

# Phase 1 Plan 08: OpenF1 + Jolpica Source Summary

**OpenF1Source turns OpenF1 timing and Jolpica calendar, grid, results and pit stops into schema-valid race records on a lights-out clock, `uv run f1si load` now loads real races by default, and real Bahrain 2023 loaded on the first try.**

## Performance

- **Tasks:** 2 of 2
- **Files:** 2 created, 4 modified

## Accomplishments

- `OpenF1Source` (`list_races`, `fetch`): Race sessions only, cancelled and under-6-hours-old races skipped, rounds matched to the Jolpica schedule by UTC date, completeness checks (laps, 18 to 22 entries, at least 15 drivers with lap 1, weather, race control) that fail one race with a retry message.
- `entries.pit_lane_start` uses only lights-out facts. An offline test changes the Jolpica laps from "0" to "57" and asserts the value is unchanged.
- CLI: `--source {openf1,synthetic}` with default `openf1`, a start banner, and `KeyboardInterrupt` giving exit 130 with "Finished races are kept".
- Source decisions DEC-036..DEC-049 appended; `MIN_ENTRIES` raised to 49.

## Real Bahrain 2023 smoke load

Command: `uv run f1si load --seasons 2023 --only bahrain-2023` (about 15 s, first attempt, no fixes needed).

```
Loading seasons 2023 from OpenF1 + Jolpica. New races take about 15 s each; finished races are kept if you stop with Ctrl+C.
[1/1] 2023-01 bahrain-2023         ok  1,058 laps  (era ground_effect_2022_2025)
Done: 1 loaded, 0 skipped, 0 failed. Cache: data
```

- Entries: 20. Laps: 1,058. Max lap: 57 (driver 1 has laps 1 to 57). Race ends at 5,728.0 s. Weather rows: 161. Race-control rows: 75. Lap cutoffs: 58 (0 to 57).
- Track status: yellow, then "6" VIRTUAL SAFETY CAR DEPLOYED at t = 4,000.5 s, "7" at 4,096.5 s, "1" (TRACK CLEAR) at 4,109.5 s. Driver 1's lap 41 runs 3,959.0 to 4,079.5 s and shows track_status "126", lap 42 shows "671". So the VSC sits on lap 41 as expected.
- Pit stops: 50 pit-in laps and 50 pit-out laps. Grid: 20 starters, no grid-0 entries, so no pit-lane starters (the pit-lane rule has no real-data case here).
- Second run printed `skipped (cached)`. `uv run f1si races` lists `2023-01 bahrain-2023 ... ground_effect_2022_2025 no`.
- `data/` is gitignored; `git ls-files data` is empty.

Data quirk seen (not fixed, logged in DEC-048): 3 of 1,058 laps (drivers 16 lap 40, 31 lap 42, 81 lap 14, all pit in-laps) have no OpenF1 lap end, stint or compound. They have a start time, so they are only visible at the race end.

## DEC numbers assigned

| DEC | Title | Source |
|-----|-------|--------|
| 036 | HTTP pacing, caching and retries (includes the cache format) | 01-06, 01-08 |
| 037 | One network door | 01-06 |
| 038 | Track status derived from OpenF1 race control | 01-06, 01-08 |
| 039 | Jolpica payloads are untrusted | 01-06 |
| 040 | Snapshots are plain data | 01-07 |
| 041 | The door accessors are small and separate | 01-07 |
| 042 | Cars at a cutoff: leader N laps, others at most N-1 | 01-07 |
| 043 | Stint and pit event rebuild | 01-07 |
| 044 | History: complete earlier races, results included | 01-07 |
| 045 | Scramble rules for the future-scramble test (includes the visible_at_s pairing and calendar rows) | 01-07 |
| 046 | Unknown race and lap errors | 01-07 |
| 047 | Race calendar and identity | 01-08 |
| 048 | OpenF1 lap clock and tyre fields | 01-08 |
| 049 | Pit-lane start rule | 01-08 |

## Task Commits

1. **Task 1: OpenF1Source with schedule matching, normalization and completeness checks** - `ac8cf3c` (feat)
2. **Task 2: CLI default source, DECISIONS entries, decision-log test** - `a280983` (feat)

## Deviations from Plan

None - plan executed exactly as written. The `test_load_requires_source` test was replaced by `test_load_default_source_is_openf1` as specified; two extra tests were added (Ctrl+C exit code, source decisions by title).

## Human checks (collected for the end of the phase)

- In PowerShell: `cd $HOME\Documents\f1si` then `uv run f1si races`. Expect `2023-01 bahrain-2023` with era `ground_effect_2022_2025` and out-of-sample `no`. (Confirms the owner's own terminal can run the CLI against the real cache.)

## Known Stubs

None. `scheduled_laps` is deliberately NULL (Phase 2 decides it; DEC-047).

## Threat Flags

None beyond the plan's threat model. T-01-32 (strict parsing, completeness checks, validate before write), T-01-33 (2.1 s spacing, cache first), T-01-34 (data/ untracked, credits in README and the module docstring), T-01-35 (round from the schedule, circuit from circuitId), T-01-36 (MixedSourceError, no old cache existed) and T-01-52 (offline test on laps independence) are implemented.

## Next Phase Readiness

Plan 01-10 can run the full multi-season load. It should list every grid-0 entry with its Jolpica status (the DEC-049 real-data check), and look at any 2026 refs (the Jolpica schedule match for rounds renumbered or cancelled). Network cost per race is about 7 paced calls.

## Self-Check: PASSED

- Files exist: `src/f1si/data/sources/openf1.py`, `tests/data/test_openf1.py`, `.planning/phases/01-foundation-data/01-08-SUMMARY.md`.
- Commits `ac8cf3c` and `a280983` exist on main.
- Full suite 326 passed offline; ruff check, ruff format --check and mypy strict clean; `git ls-files data` empty.
