---
phase: 01-foundation-data
plan: 04
subsystem: data
tags: [duckdb, loader, schema, derive, rate-limit, resume, cli, synthetic]

requires:
  - phase: 01-03
    provides: synthetic generator, loader happy path, f1si load / races, green CI
provides:
  - Full Phase 1 race record in the cache (track_status, race_control, weather, lap_cutoffs, results besides races, entries, laps, stints and pit_stops views)
  - f1si.data.derive (derive_lap_cutoffs, annotate_lap_track_status), source-agnostic
  - Resumable, rate-limit-aware, failure-collecting load_races with only= and mixing guard
  - f1si load --seasons and --only
affects: [01-05, 01-06, 01-07, 01-08, 01-09, 01-10]

tech-stack:
  added: []
  patterns:
    - "Derived tables (lap_cutoffs) are TableSpec(derived=True): not required from sources, built by the loader"
    - "Loader returns failures in a report instead of raising; only whole-run problems propagate"
    - "Retry waits go through an injected sleep so tests never wait"

key-files:
  created:
    - src/f1si/data/derive.py
    - tests/data/test_derive.py
    - tests/data/test_loader.py
  modified:
    - src/f1si/data/schema.py
    - src/f1si/data/loader.py
    - src/f1si/data/errors.py
    - src/f1si/eras.py
    - src/f1si/synthetic/generator.py
    - src/f1si/cli.py
    - tests/data/mini_race.py
    - tests/data/test_schema.py
    - tests/data/test_db_roundtrip.py
    - tests/test_synthetic.py
    - tests/test_cli.py

key-decisions:
  - "lap_cutoffs: c(0)=0, c(n)=min lap_end_s over lap n, missing laps +inf, then reverse cumulative minimum; trailing +inf dropped"
  - "laps.track_status is the string of statuses from lap start to lap end (e.g. 167), using only rows at or before the lap end"
  - "load_races collects per-race failures (exit code 2) and only raises for MixedSourceError, CacheBusyError, UnknownEraError and interrupts"

patterns-established:
  - "Loader prints the Done line and the Failed races list itself; the CLI only returns report.exit_code"
  - "UnknownEraError carries .season so the CLI can word its own message"

requirements-completed: [DAT-01]

duration: ~45 min
completed: 2026-10-22
---

# Phase 1 Plan 04: Full Race Record and Resilient Loader Summary

**Every cached race now holds track status, race control, weather, results, precomputed lap cutoffs (reverse cumulative minimum) and per-lap track status strings, and `f1si load` resumes, waits out rate limits, lists failures and refuses to mix sources.**

## Performance

- **Tasks:** 2 of 2 complete
- **Tests:** 114 pass (was 67); ruff check, ruff format --check and mypy strict clean on the whole tree
- No test sleeps for real: slowest loader test is 0.7 s

## Accomplishments

- Schema grew to eight tables in the required order: races, entries, laps, track_status, race_control, weather, lap_cutoffs (derived), results. `validate_race` also checks status codes in {1,2,4,5,6,7} and results drivers against entries.
- `derive_lap_cutoffs` precomputes the leader's lap-N completion time at load time, so the as-of door never has to compute `min(lap_end_s)` over other cars' future rows. Property tests on the loader-written cache check, for every lap N of alpha-2023: exactly one car completes lap N at the cutoff, nobody else has, and everyone has completed lap N-1.
- `annotate_lap_track_status` turns the status timeline into one string per lap, using only rows at or before the lap's end.
- The synthetic generator emits a VSC sequence ("6", "7", "1") around lap 8 of alpha-2023, race control (pre-race green, chequered), weather every 60 s, and results (points 25/18/15/12/10/8, retired driver "R"). Weather noise is drawn after all lap noise, so existing lap times are unchanged.
- `load_races` is resumable (`skipped (cached)`), retries rate limits (waits max(retry_after, 60 s) via injected `sleep`, bounded by `max_attempts`), collects failures into a "Failed races:" list, supports `only=` by slug or race id, and raises `MixedSourceError` before any fetch when the cache holds another source.
- CLI: `--seasons` and `--only`; unknown season exits 1 with "Season X has no regulation era defined (supported seasons: 2022-2026, see f1si/eras.py)".

## Task Commits

1. **Task 1: Complete race record (schema, derive, generator, loader)** - `89465ed` (feat)
2. **Task 2: Resilient loader and CLI --seasons / --only** - `b7053c1` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Edited `tests/data/mini_race.py` and `src/f1si/eras.py`, which are not in the plan's file list**
- **Issue:** The plan says to extend `_mini_race()` in `test_schema.py` and `test_db_roundtrip.py`, but plan 01-02 had put the shared race in `tests/data/mini_race.py`, so the new tables go there once. `UnknownEraError` had no season attribute, so the CLI could not word "Season X has no regulation era defined" without parsing the message; it now takes `season` (message text unchanged).
- **Files modified:** tests/data/mini_race.py, src/f1si/eras.py
- **Commits:** 89465ed, b7053c1

**2. [Rule 1 - Bug] Existing test expected `SourceError` from `load_races` on invalid source data**
- **Issue:** `test_invalid_source_data_writes_nothing` encoded the skeleton behavior (raise). The plan's D-14 behavior turns it into a collected failure.
- **Fix:** Test rewritten to assert the failure reason ("invalid data from synthetic ... missing required table") and that nothing is written.
- **Files modified:** tests/test_cli.py
- **Commit:** b7053c1

**3. `tests/conftest.py` unchanged:** the fixture needs no new keyword arguments.

## Decisions to log (for the next plan that edits DECISIONS.md, 01-05 or 01-08)

- Lap cutoffs are precomputed at load time: c(0)=0.0, c(n)=min non-null lap_end_s of lap n, missing laps +inf, reverse cumulative minimum, trailing +inf dropped. The reverse minimum only moves cutoffs earlier (safe direction). Reason: computing min(lap_end_s) at query time would read other cars' future lap-N rows (DEC-008 follow-up).
- `laps.track_status` is the ordered string of status codes active from lap start to lap end with consecutive duplicates removed ("1", "167"); a lap with NA start or end gets NA; no status rows means "1". It uses only rows with t_s <= lap_end_s, so it is knowable at visible_at_s = lap_end_s.
- Track status codes are restricted to {1 green, 2 yellow, 4 SC, 5 red, 6 VSC deployed, 7 VSC ending}; unknown codes fail validation (plan 01-06's mapping must produce only these).
- `lap_cutoffs` is a `derived=True` table: sources do not supply it, `validate_race` does not require it, `write_race` still does (the loader supplies it).
- Loader failure policy: per-race failures (any `Exception`, including invalid source data and a schedule-listing `SourceError`) are collected and the run continues; exit code 2 if any. `CacheBusyError`, `MixedSourceError`, `UnknownEraError`, `KeyboardInterrupt` and `SystemExit` propagate because they fail every race or mean stop.
- Rate limits: wait max(retry_after_s, 60 s) via an injected `sleep`, up to `max_attempts` (default 3) attempts per race; after the last attempt the race fails with "rate limited by SOURCE; run the same command again later".
- Resume: a race is skipped when `races.load_status = 'complete'` in the cache (checked once at the start). Re-running retries only the missing or failed races.
- One source per cache folder: `MixedSourceError` is raised before any network call when the cache holds a different `races.source`.
- `--only` values are matched against schedule race_ids and slugs only (never interpolated into SQL or paths); unmatched values become failures with "not found in the schedule for seasons ...".
- Synthetic weather noise is drawn after all lap noise to keep lap-time streams stable; synthetic VSC events: "6" at earliest lap start + 1 s, "7" at latest lap end - 1 s, "1" 12 s later.
- `UnknownEraError.season` attribute added; the CLI words the "no regulation era" message.

## Known Stubs

None. `lap_cutoffs`, `laps.track_status`, results and weather are all populated for synthetic data. Real-source track-status mapping arrives in plans 01-06 and 01-08.

## Threat Flags

None beyond the plan's threat model. T-01-11 (validate before write), T-01-12 (precomputed cutoffs with property test), T-01-13 (per-race failure collection, resume, bounded retries), T-01-14 (MixedSourceError test) and T-01-15 (seasons via `era_for_season`, `only` compared only) are implemented and tested.

## Self-Check: PASSED

- All listed files exist; commits `89465ed` and `b7053c1` exist on main.
- Full suite: 114 passed; ruff, ruff format --check and mypy strict clean.
- `derive.py` docstring contains "reverse cumulative minimum"; `loader.py` contains `RateLimitedError`, `completed_race_ids(`, `sources_in_cache(`, `skipped (cached)` and `Failed races:`.
