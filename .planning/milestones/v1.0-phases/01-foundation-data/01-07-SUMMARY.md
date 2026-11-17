---
phase: 01-foundation-data
plan: 07
subsystem: data
tags: [as-of, look-ahead-guard, hypothesis, scramble, duckdb, out-of-sample, results-door]

requires:
  - phase: 01-04
    provides: full race record, lap_cutoffs, normalized schema
  - phase: 01-05
    provides: import-ban POLICY, leaky_consumer fixture
provides:
  - The as-of door (AsOfAccessor.snapshot / history, AsOf, RACE_END, RaceSnapshot, History, resolve_slug)
  - Separate results door (ResultsAccessor) and out-of-sample door (OutOfSampleAccessor)
  - 2026 lock (OutOfSampleLockedError) in the as-of and results doors
  - Future-scramble harness, consumer registry, property test and D-02 meta-test
affects: [01-08, 01-09, 01-10, 01-11, phase-2, phase-5, phase-6, phase-8]

tech-stack:
  added: []
  patterns:
    - "Snapshots are plain data; only the replay/backtest driver holds the accessor"
    - "A consumer is a function (db_path, AsOf) -> output; every one is registered in tests/guards/consumers.py"
    - "Scramble harness changes the time column and visible_at_s together because write_tables recomputes visibility (DEC-018)"

key-files:
  created:
    - src/f1si/data/_snapshot.py
    - src/f1si/data/results.py
    - src/f1si/data/out_of_sample.py
    - tests/data/test_asof.py
    - tests/data/test_doors.py
    - tests/guards/scramble.py
    - tests/guards/consumers.py
    - tests/guards/test_future_scramble.py
    - tests/guards/test_meta_guard.py
    - tests/fixtures/leaky_through_accessor.py
  modified:
    - src/f1si/data/asof.py
    - src/f1si/data/errors.py

key-decisions:
  - "Snapshot reads only the lap-N row of lap_cutoffs; at lap N the leader shows N laps, everyone else N-1"
  - "Results and 2026 are separate modules with no flags; results.py duplicates its tiny query rather than importing _snapshot"
  - "RACE_END scrambles nothing in the current race's time tables (no time filter, so every row is visible)"

patterns-established:
  - "History races is a list[str] of earlier in-sample race ids; snapshot/history dataclasses use eq=False because they hold DataFrames"
  - "Edge points (lap 0, last lap, RACE_END) are tested deterministically in addition to the random property test"

requirements-completed: [DAT-03, DAT-04, DAT-05]

duration: ~60 min
completed: 2026-10-22
---

# Phase 1 Plan 07: Data Doors and the Future-Scramble Guard Summary

**Three doors (as-of, results, out-of-sample) with exact lap-cutoff visibility, a 2026 lock, and a hypothesis future-scramble test over every registered consumer that catches planted leaks the import ban cannot see.**

## Performance

- **Tasks:** 2 of 2 complete
- **Tests:** 290 pass (was 158); ruff check, ruff format --check and mypy strict clean
- `tests/guards` runs in about 26 s (property test about 11 s at max_examples=20, so no need to lower it)

## Accomplishments

- `AsOfAccessor(db).snapshot(AsOf(race, lap | RACE_END))` returns a frozen `RaceSnapshot` (race, at, cutoff_s, entries, laps, track_status, race_control, weather, stints, pit_events, cars). Cutoff comes from `SELECT cutoff_s FROM lap_cutoffs WHERE race_id = ? AND lap = ?`; time tables use `visible_at_s IS NOT NULL AND visible_at_s <= ?`. Verified on every lap of alpha-2023: leader N laps, others N-1; lap 0 shows only pre-race facts; RACE_END shows all 72 laps with `cutoff_s=None`.
- Stints, pit events and per-car `laps_done`/`stops_done`/`position` are rebuilt from visible laps; no snapshot frame has a final or future-dependent column (final_position, points, laps_completed, total_time_s, last_lap, n_laps, stint_length). Pit-lane starter 14 has 1 stop (lap-1 out-lap ignored), retiree 15 has 0 stops and 4 laps.
- `history(at)` returns earlier in-sample races with results (D-04 revised); never the current race, later races or 2026.
- 2026 races raise `OutOfSampleLockedError` from the as-of and results doors; `OutOfSampleAccessor` opens them, `ResultsAccessor` serves in-sample finals. A signature test proves no `include`/`unlock`/`allow` parameter exists; an injection string is only an `UnknownRaceError`.
- `tests/guards/scramble.py`: `scramble_future` (visible rows and earlier races byte-identical; every future cell differs; NOT NULL columns never NA; junk later race 2099-99; junk new-key rows; about 20% dropped; shuffled) and `assert_no_lookahead` (two DuckDB files, exact comparison, exceptions compared too). `RACE_END` leaves the current race's time tables untouched.
- `test_consumers_ignore_the_future`: hypothesis over race in {2023-01, 2023-02, 2024-01}, lap in 0..12 or `RACE_END`, seed, consumer; `just(RACE_END)` is in the strategy. Extra deterministic test covers lap 0, lap 12 and RACE_END for every consumer.
- Meta-test: `mean_lap_time_whole_race` is flagged by `scan()` and raises `LookaheadDetected`; `lap_plus_three`, `race_end_weather` and `history_of_next_race` raise `LookaheadDetected` while `scan()` of their file returns `[]`.

## Mutation check (T-01-31)

Replacing `AND visible_at_s IS NOT NULL AND visible_at_s <= ? ORDER` in `_snapshot._visible_rows` with `AND ? IS NOT NULL ORDER` made `tests/guards/test_future_scramble.py` fail (`test_consumers_ignore_the_future`: LookaheadDetected; the four harness self-checks still passed). The file was restored with `git checkout -- src/f1si/data/_snapshot.py`; `git status` showed it clean. Note: hypothesis shrinking of a failing example takes about 3 minutes locally, only when the guard is broken.

## Task Commits

1. **Task 1: three doors** - `4c13720` (feat)
2. **Task 2: scramble harness, property test, meta-test** - `2dd6660` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in test design] Harness self-check assumed future rows exist in every table**
- **Found during:** Task 2
- **Issue:** `track_status` of bravo-2023 has no rows after lap 5, so "all surviving future rows differ" had nothing to compare.
- **Fix:** The comparison is skipped for a table with no original future rows; laps and weather must have some. The scrambler and property test were not weakened.
- **Files modified:** tests/guards/test_future_scramble.py

**2. [Rule 3 - Blocking] `write_tables` recomputes `visible_at_s` from the time column (DEC-018)**
- **Issue:** scrambled `visible_at_s` alone is overwritten on insert, so future rows would silently become visible.
- **Fix:** the harness moves the time column and `visible_at_s` together (current-race future rows to cutoff + U(1, 1e4)).
- **Files modified:** tests/guards/scramble.py

**3. Added (not in plan):** `test_consumers_ignore_the_future_at_edges` (deterministic lap 0 / 12 / RACE_END run of every consumer), because a random strategy with 20 examples may skip the boundaries.

No honest consumer failed the scramble; no consumer, harness or test property was loosened.

## Decisions to log (for DECISIONS.md, next free DEC numbers)

- Snapshots are plain data, the accessor stays with the replay/backtest driver; consumers receive a `RaceSnapshot`, never the accessor.
- `AsOfAccessor` has exactly two methods and no flags; `ResultsAccessor` and `OutOfSampleAccessor` are separate modules guarded by the import ban. `results.py` and `out_of_sample.py` each carry their own small final-classification query so `results` does not import `_snapshot` (import policy) and `out_of_sample` does not import `results`.
- At lap N the leader has N laps and every other running car at most N-1; `cars.laps_done` (not `laps_completed`) and `position` are rebuilt from visible laps, ranked by laps_done desc then last_lap_end_s asc.
- Stint rebuild fields: compound, first_lap, last_visible_lap, laps_so_far, tyre_life_now; no stint end or length. Pit events: visible out-laps after lap 1; a lap-1 out-lap (pit-lane start) is not a stop.
- History: earlier = same-season lower round or earlier season, `load_status = 'complete'` and not out-of-sample, all tables including results; `races` is a list of race ids.
- Scramble rules: later races, current-race rows with `visible_at_s` NULL or after the cutoff, and the current race's results are future; at `RACE_END` the current race's time tables are not scrambled, dropped or added (RACE_END has no time filter); `RACE_END` stays in the hypothesis strategy and is also tested deterministically.
- Scramble and DEC-018: the harness changes the time column and `visible_at_s` together because the writer recomputes visibility.
- Calendar rows of later races are scrambled too (later `races` rows are future); `races` rows are never dropped so that "next race" lookups through the catalog stay stable for the meta-test.
- An unknown race raises `UnknownRaceError` with up to 3 close slug/race_id matches; lap beyond the race raises `LapOutOfRangeError` suggesting `RACE_END`.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-01-27..T-01-31 are implemented and tested (scramble property test with three through-accessor leaks, no results columns in any snapshot frame, 2026 lock without flags, bound parameters with an injection test, harness self-checks plus the mutation check above).

## Next Phase Readiness

Plan 01-09 (stint plot) must register its data builder in `tests/guards/consumers.py`. Plan 01-08's CLI can use `resolve_slug` for slug arguments. Phase 2's `RaceState` consumes `RaceSnapshot`; the N-1 laps rule for non-leaders is documented in `_snapshot.py` and `asof.py`.

## Self-Check: PASSED

- Files exist: src/f1si/data/{_snapshot,results,out_of_sample}.py, tests/data/{test_asof,test_doors}.py, tests/guards/{scramble,consumers,test_future_scramble,test_meta_guard}.py, tests/fixtures/leaky_through_accessor.py.
- Commits `4c13720` and `2dd6660` exist on main.
- Full suite: 290 passed; ruff check, ruff format --check, mypy strict clean.
