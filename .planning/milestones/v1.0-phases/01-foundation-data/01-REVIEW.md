---
phase: 01-foundation-data
reviewed: 2026-10-22T00:00:00Z
depth: standard
files_reviewed: 52
files_reviewed_list:
  - src/f1si/__init__.py
  - src/f1si/__main__.py
  - src/f1si/cli.py
  - src/f1si/eras.py
  - src/f1si/paths.py
  - src/f1si/rng.py
  - src/f1si/data/__init__.py
  - src/f1si/data/_db.py
  - src/f1si/data/_snapshot.py
  - src/f1si/data/asof.py
  - src/f1si/data/derive.py
  - src/f1si/data/errors.py
  - src/f1si/data/loader.py
  - src/f1si/data/out_of_sample.py
  - src/f1si/data/results.py
  - src/f1si/data/schema.py
  - src/f1si/data/slugs.py
  - src/f1si/data/sources/__init__.py
  - src/f1si/data/sources/_http.py
  - src/f1si/data/sources/jolpica.py
  - src/f1si/data/sources/openf1.py
  - src/f1si/data/sources/synthetic_source.py
  - src/f1si/data/sources/track_status_map.py
  - src/f1si/plots/__init__.py
  - src/f1si/plots/stints.py
  - src/f1si/synthetic/__init__.py
  - src/f1si/synthetic/generator.py
  - tests/conftest.py
  - tests/guards/consumers.py
  - tests/guards/import_scan.py
  - tests/guards/scramble.py
  - tests/guards/test_future_scramble.py
  - tests/guards/test_import_ban.py
  - tests/guards/test_meta_guard.py
  - tests/fixtures/leaky_consumer.py
  - tests/fixtures/leaky_through_accessor.py
  - tests/data/test_asof.py
  - tests/data/test_derive.py
  - tests/test_cli.py
  - tests/real/test_bahrain_2023.py
  - .github/workflows/ci.yml
  - .github/workflows/real-data.yml
  - pyproject.toml
  - .pre-commit-config.yaml
findings:
  critical: 1
  warning: 11
  info: 6
  total: 18
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-10-22
**Depth:** standard
**Files Reviewed:** 52 listed in the frontmatter (the remaining test modules under `tests/data`, `tests/plots` and the top-level tests were skimmed only where they bear on a guard)
**Status:** issues_found

## Summary

The as-of door itself is sound. All SQL is bound with `?`, and the f-string table names come only from `schema` constants. Snapshots filter on `visible_at_s <= cutoff` with the cutoff read from `lap_cutoffs`. Stints, pit events and cars are rebuilt from visible laps only. The 2026 lock is enforced in every door. I found no path by which the `AsOfAccessor` serves a future row of a loaded race, apart from the provenance caveats in WR-06 and WR-08.

The guards around the door are weaker than they look. The import-ban scanner has a verified, trivial bypass: `from f1si.data.asof import _db` hands any module a raw-SQL handle, including to the `results` table. The scramble harness can pass vacuously when both runs raise the same exception. It also relies on a manually maintained consumer registry and a randomly sampled Hypothesis run. The data path has a verified fragility: one bad `lap_end_s` silently rewrites every earlier lap cutoff. There is also a verified crash in `f1si races` on an empty cache.

Items I verified by running code (scratchpad scripts, nothing in the repo changed):
- CR-01: the scanner reports no violation for eight bypass forms.
- WR-01: a consumer that always raises `AttributeError` passes `assert_no_lookahead`.
- WR-03: one outlier lap end of 100 s collapses cutoffs 2 to 10 to 100.0.
- WR-07: `f1si races` raises `TypeError` on a cache with an empty `races` table.

## Fix outcomes (2026-10-22)

Scope: CR-01 and WR-01 to WR-11. Info items IN-01 to IN-06 were out of scope and are untouched.

| Finding | Outcome | Commit |
|---------|---------|--------|
| CR-01 | fixed | 5e88d08 |
| WR-01 | fixed | c436b4d |
| WR-02 | fixed | c436b4d |
| WR-03 | fixed | 9ccc229 |
| WR-04 | fixed | 84fc465 |
| WR-05 | fixed | eb7d532 |
| WR-06 | fixed (pre-race signal does not exist; limit documented in DEC-056) | dc1bbd6 |
| WR-07 | fixed | 0844ece |
| WR-08 | fixed, with the deviation noted under the finding | a15aa52 |
| WR-09 | fixed | eb7d532 |
| WR-10 | fixed | 382be42 |
| WR-11 | fixed | 5e88d08 |

Decision log entries: DEC-052 to DEC-060.

## Critical Issues

### CR-01: Import ban is bypassed by re-exported private modules (`asof._db`, `loader._db`, `asof._snapshot`)

**File:** `tests/guards/import_scan.py:62-119, 137-167, 196-207`
**Issue:** `POLICY` matches only the exact dotted names `f1si.data._db` and `f1si.data._snapshot`. But `f1si/data/asof.py:31` (`from f1si.data import _db, _snapshot`) and `f1si/data/loader.py:29` bind those modules as attributes. Neither `asof` nor `loader` is a protected name, so any module may import them. The module names then resolve to `f1si.data.asof._db`, `f1si.data.loader._db` and so on. These do not equal and do not start with `f1si.data._db.`, so no rule fires.

I ran the scanner on a throwaway `f1si/strategy.py`. All of these were MISSED (not flagged):
- `from f1si.data.loader import _db`
- `from f1si.data.asof import _db`
- `from f1si.data.asof import _snapshot`
- `import f1si.data.asof as a` followed by `a._db.read_df(...)`
- `from f1si.data import asof` followed by `asof._db.read_df(...)`

I also confirmed that `from f1si.data.asof import _db; _db.read_df(db, "SELECT count(*) FROM results")` returns the row count. `read_df` takes arbitrary SQL, so the result is full access to `results`, to the whole current race, and to 2026 races. That defeats D-02 (import ban), D-03 (separate results door) and D-04 (2026 lock).

Failure scenario: a strategy module reads `_db.read_df(db, "SELECT * FROM laps WHERE race_id = ?")` through `loader` or `asof`. CI stays green. The scramble test never sees it, because the module is not a registered consumer. The planted canary uses `import duckdb`, so it proves only the direct case.

**Fix:** Make the rule structural rather than name-prefix based.
```python
_PRIVATE = {"_db", "_snapshot"}

def _is_private_chain(name: str) -> bool:
    return any(part in _PRIVATE for part in name.split("."))

# in scan(): in addition to POLICY, flag any import whose dotted path contains a private
# storage component but whose importer is not in the allowed set
#   ("f1si.data.asof", "f1si.data._snapshot", "f1si.data.results",
#    "f1si.data.out_of_sample", "f1si.data.loader", "f1si.data._db")
# and extend rng_attribute_names-style attribute scanning to flag `.\_db` / `._snapshot`
# attribute access (`a._db.read_df`) in every module outside that set.
```
Better: stop re-exporting. In `asof.py` and `loader.py` use `from f1si.data import _db as _storage`. Add a test asserting that `dir(f1si.data.asof)` and `dir(f1si.data.loader)` expose no `duckdb`-reaching name, or that `__getattr__` raises for those names. Add `from f1si.data.asof import _db` and `a._db` snippets to `SNIPPETS` with `flagged=True`.

**Outcome:** fixed in 5e88d08 (DEC-052). The scan now canonicalises any path through `_db`/`_snapshot` to its home module and flags `x._db`, `getattr(x, '_db')`, protected string literals and star imports, so every bypass listed above is caught (each is a `SNIPPETS` case). The door and loader modules import `_db`/`_snapshot` inside functions, so `from f1si.data.asof import _db` is an ImportError at runtime too (runtime test over all public modules). A second canary fixture, `tests/fixtures/leaky_reexport.py`, leaks without naming duckdb; the meta-test and the CI canary require both fixtures to be caught.

## Warnings

### WR-01: Scramble harness passes vacuously when both runs raise the same exception

**File:** `tests/guards/scramble.py:241-245, 287-308`
**Issue:** `_run` converts every `Exception` to `("raised", (type, str))` and `assert_no_lookahead` only compares the two outcomes. I verified that a consumer which always raises `AttributeError` (`...snapshot(at).no_such_attribute`) passes. So does a consumer that asks for a locked 2026 race. A broken or mis-registered consumer is reported as "ignores the future" and exercises nothing. A leak that happens to raise the same message in both databases is also accepted.
**Fix:** Require the original run to succeed by default.
```python
kind_a, payload_a = result_a
if kind_a == "raised" and not expect_error:
    raise AssertionError(f"consumer failed on the unscrambled data: {payload_a}")
```
Add an `expect_error: type[Exception] | None = None` parameter for the deliberate error cases. Then add a harness self-test that a raising consumer is rejected.

**Outcome:** fixed in c436b4d (DEC-053). `assert_no_lookahead` fails with `ConsumerFailed` when the consumer raises on the original data; deliberate error cases pass `expect_error` and the locked 2026 race is asserted explicitly. Harness self-tests cover a raising consumer, a wrong or missing expected error, and an expected error whose message still leaks the future.

### WR-02: Scramble coverage depends on convention and random sampling

**File:** `tests/guards/consumers.py:47-54`, `tests/guards/test_future_scramble.py:138-167`, `src/f1si/data/asof.py:32,81`
**Issue:** Three gaps combine here.
1. The guard covers only functions registered by hand in `CONSUMERS`. Nothing fails if a new module calls `AsOfAccessor` and is never registered.
2. `asof`, `AsOfAccessor` and `RACE_END` are not protected names, so any module can build `AsOf(race, RACE_END)` and receive the whole race with no scanner objection.
3. `test_consumers_ignore_the_future` samples 20 of roughly 250 combinations (6 consumers x 3 races x 14 laps) with a random seed. The deterministic edge test covers only race `2023-02` at laps 0, 12 and RACE_END. A lap-specific leak in the other races is found only by luck, so CI is non-deterministic.

**Fix:**
- Add a scanner rule that lets only the replay/backtest driver, the CLI and `tests` import `AsOfAccessor` and `RACE_END`.
- Add a test that fails if a `src` module outside that allow-list references `AsOfAccessor`.
- Run the full grid deterministically. Use `@pytest.mark.parametrize` over race, lap and consumer, or at minimum `derandomize=True` plus all laps for one race.

**Outcome:** fixed in c436b4d (DEC-053). The import scan allows `AsOfAccessor`, `RACE_END` and `RaceEnd` only in the replay drivers and the CLI; `test_consumer_registry.py` requires every public function of the designated consumer modules to be consumed or exempt with a reason; a deterministic grid runs every consumer at every lap and RACE_END of every in-sample synthetic race. The Hypothesis test and its `just(RACE_END)` branch are unchanged.

### WR-03: One bad `lap_end_s` silently truncates visibility of all earlier laps

**File:** `src/f1si/data/derive.py:67-86` (consumer: `_snapshot.py:188-199`)
**Issue:** The cutoff is `min(lap_end_s)` per lap followed by a reverse cumulative minimum. The docstring calls moving a cutoff earlier "the safe direction". It is safe for look-ahead but it corrupts the data silently. I verified on the synthetic race that one outlier (`lap_end_s = 100` for lap 10 of one car) turns the cutoffs for laps 2 to 10 into `[100, 100, ..., 100]`. Real OpenF1 data carries `date_start` glitches. Every snapshot from lap 2 to 10 then hides nearly all rows, and `cars.laps_done` and `position` go wrong. Nothing in `schema.validate_race` or the loader warns.
**Fix:** In `validate_race` or `_build_tables`, check per car that `lap_end_s` is strictly increasing in `lap_number` and that `lap_end_s >= lap_start_s`. Reject the race, or null the offending rows, with a message. Also check that the raw per-lap leader minima are already non-decreasing. If they are not, fail loudly instead of repairing.

**Outcome:** fixed in 9ccc229 (DEC-055). `sanitize_lap_ends` drops ends that are non-finite, outside [0, 6 h], or outside each driver's longest increasing run; the loader prints a note, makes those laps visible only at the race end, and rejects a race with more than 10 percent bad ends. The real cache contained one such value (2024 round 4, `-1327.2 s`). Missing leader ends are reported by `cutoff_repairs` but not rejected: the reviewer's "fail loudly if the raw minima decrease" would also reject legitimate gaps.

### WR-04: Every snapshot opens a fresh DuckDB connection per query, so reads are not atomic

**File:** `src/f1si/data/_db.py:146-149`, `src/f1si/data/_snapshot.py:166, 192, 217, 322-323`
**Issue:** `build_snapshot` makes about 8 independent `connect_reader` calls. Between them a concurrent `f1si load` process can take the write lock and re-load a race (delete then insert, in `_db.write_race`). The snapshot can then mix a `lap_cutoffs` row from the old load with `laps` from the new one. Or it raises `CacheBusyError` halfway through a walk-forward run. Opening and closing the database per query is also slow, which compounds with walk-forward use.
**Fix:** Open one read-only connection per `snapshot`/`history` call and pass it down. For example, add `_db.reader(db_path)` as a context manager, and let `read_df` accept an optional `con`. This also gives a consistent view of one load.

**Outcome:** fixed in 84fc465 (DEC-054). Each door call opens one read connection and passes it to every query (`guarded_snapshot`/`guarded_history`); a test counts connections per call.

### WR-05: HTTP responses are cached forever even when the data may be incomplete or provisional

**File:** `src/f1si/data/sources/_http.py:141-147`, `src/f1si/data/sources/openf1.py:316-348, 255-261`, `.github/workflows/real-data.yml:36-40`
**Issue:** All timing and results endpoints use `freshness="forever"` and `NEVER_EXPIRE`. `list_races` accepts a race 6 hours after its start (`COMPLETED_MARGIN`). OpenF1 backfills laps, stints and weather after a session, and Jolpica results can change with post-race penalties. A partial or provisional HTTP 200 is cached permanently. `_check_complete` then tells the user "It will be retried on the next run", which is false. The retry replays the same cached body, so the race fails until `data/http-cache` is deleted, or it loads with stale, wrong results. The CI cache key `real-data-http-cache-bahrain-2023` is static, so `actions/cache` never overwrites it either.
**Fix:**
- Use `freshness="short"` for any season in the current year, or for any race that started less than about 7 days before `now`.
- On `SourceError` from `_check_complete`, delete that race's cache entries. For example, call `session.cache.delete(urls=...)` or key the "forever" class on the race age.
- Change the message to say what to do ("delete `data/http-cache` and re-run").

**Outcome:** fixed in eb7d532 (DEC-058). Current-season and under-a-week-old races use the 12 h expiry; `JsonGetter.forget` removes a race's cached responses when it fails the completeness check, and the loader calls an optional `discard_cached` hook on any `SourceError`; the message now says what happened; the CI cache key is per run with a prefix restore key.

### WR-06: `entries` (visible from lap 0) is filled from post-race facts

**File:** `src/f1si/data/sources/openf1.py:426-428, 435, 459-463`
**Issue:** The module docstring states that every `entries` column may use only facts fixed at lights out. Two columns do not meet that rule.
- `pit_lane_start` is `grid == 0 and status not in NON_STARTER_STATUSES`. `status` is the final Jolpica race status ("Finished", "Engine", "Disqualified", ...). Any unlisted post-race status turns a grid-0 non-starter into a "pit lane start" that never raced. This is a post-race value in a pre-race table.
- `start_compound` and `start_tyre_age` come from the lowest stint number present in OpenF1 `/stints`. `_parse_stints` drops any stint whose `lap_start` is null (line 398). If stint 1 is dropped, stint 2 is taken as the "starting" compound, which is the tyre after the first stop.

No guard can catch this, because the scramble harness deliberately leaves the current race's `entries` untouched.
**Fix:** Derive `pit_lane_start` from facts available at the start. For example, use the lap-1 `is_pit_out_lap` flag, or `grid == 0` together with the driver having a lap 1 row. Take `start_compound` only from the stint whose `lap_start == 1` (or `number == 1`), and set it to `None` otherwise. Add a unit test for the missing-stint-1 case.

**Outcome:** fixed in dc1bbd6 (DEC-056, DEC-049 status updated). `pit_lane_start` is grid 0 plus a lap-1 timing record (no status, no laps completed); `start_compound`/`start_tyre_age` come only from stint number 1 and stay NULL with a printed note when it is absent. A provenance test changes everything after lap 1 and every result field and requires identical entries. Honest limit recorded: neither feed has a pre-lights-out signal, the lap-1 record appears during lap 1.

### WR-07: `f1si races` crashes with `TypeError` when the cache has no races

**File:** `src/f1si/cli.py:134`
**Issue:** `max(len(h), *(len(row[i]) for row in rows))` is `max(len(h))` when `rows` is empty. That raises `TypeError: 'int' object is not iterable`. I reproduced it on a DuckDB file with the schema but no races. This state occurs when the file exists but no race has completed (for example, every first load failed after `ensure_schema`). The user sees a traceback instead of guidance.
**Fix:**
```python
widths = [max([len(h), *(len(row[i]) for row in rows)]) for i, h in enumerate(header)]
...
if not rows:
    print("No races cached. Run: uv run f1si load")
    return 0
```

**Outcome:** fixed in 0844ece (DEC-060). `f1si races` prints guidance and exits 0 on an empty cache; regression test added.

### WR-08: Lap holes and inconsistent stop counting from mixed OpenF1/Jolpica flags

**File:** `src/f1si/data/sources/openf1.py:510-519, 538-540`, `src/f1si/data/_snapshot.py:278-286, 297-306`
**Issue:**
- When a lap has `lap_duration` but no `date_start` (and it is not lap 1), `start` is None and `end = None if start is None`. The row gets `visible_at_s = NULL` and appears only at `RACE_END`. `rebuild_cars` then undercounts `laps_done` and mis-ranks `position`. The end can be reconstructed from the previous lap's end plus the duration, or from the next lap's start.
- `is_pit_in_lap` comes from the Jolpica pit-stop list, but `is_pit_out_lap`, and so `rebuild_pit_events` and `stops_done`, comes from OpenF1. Cars that leave the pit lane after a red flag are, as far as I know, flagged `is_pit_out_lap` by OpenF1 although Jolpica records no stop. They would be counted as stops, with a NA `pit_duration_s`. This is not verified against real data, so confirm it on a red-flag race such as 2023 Australia.

**Fix:** Fill `end` as `prev_end + duration` when only the start is missing. In `rebuild_pit_events`, require a matching in-lap (`is_pit_in_lap` on `lap_number - 1`), or use one source for both flags. Add a regression fixture for each case.

**Outcome:** fixed in a15aa52 (DEC-057), with one deviation. A lap with a duration but no `date_start` starts at the previous lap end (chained). `is_pit_in_lap` is now the lap before an OpenF1 out-lap (one source for both flags). The suggested "require a matching Jolpica in-lap" was NOT applied: on the real cache it would drop 34 real stops (32 in Australia 2026 where Jolpica's stop lap equals the out-lap, 2 in Miami 2025 where the in-lap row is absent). The red-flag false-stop concern was checked and did not occur in the data (Australia 2023 has no unmatched out-laps).

### WR-09: The Jolpica hourly budget is not persisted across processes

**File:** `src/f1si/data/sources/_http.py:136-137, 240-258`, `src/f1si/data/sources/jolpica.py:107-117`, `src/f1si/data/loader.py:186-190`
**Issue:** The rolling 450 calls per hour window lives in an in-memory `deque`. The loader tells the user to "run the same command again" after a rate limit or failure, which starts a new process with an empty window. Several quick re-runs can exceed Jolpica's 500 per hour. OpenF1 has the same property, but its 2.1 s spacing keeps it safe.
**Fix:** Persist call timestamps next to the cache, for example a small table in `jolpica.sqlite`. Alternatively, seed the window from the cache database's non-cached-response timestamps at start-up.

**Outcome:** fixed in eb7d532 (DEC-059). The rolling hourly window is written to `jolpica.calls.json` beside the cache and seeds the next process.

### WR-10: `_is_lock_error` treats any message containing "lock" as a busy cache

**File:** `src/f1si/data/_db.py:25, 34-36`
**Issue:** `"lock" in text` also matches "bLOCK". DuckDB corruption and short-read `IOException`s mention a block ("Corrupt database file: computed checksum of block ...", "Could not read enough bytes ... block"). A corrupt cache is then reported as "busy, wait for the other command" and the user waits forever.
**Fix:** Match specific phrases only: `"could not set lock"`, `"conflicting lock"`, `"being used by another process"`, `"already open"`. Drop the bare `"lock"`.

**Outcome:** fixed in 382be42 (DEC-060). Only "could not set lock", "conflicting lock", "being used by another process" and "already open" mean busy; "block" messages no longer match (unit tests).

### WR-11: Smaller gaps in the scanner and in the canary

**File:** `tests/guards/import_scan.py:121, 170-187, 210-212`, `.github/workflows/ci.yml:36-46`
**Issue:**
- `_RNG_CONSTRUCTORS` omits `PCG64DXSM`, `BitGenerator` and `SeedSequence`. I confirmed `from numpy.random import PCG64DXSM` is not flagged.
- `from numpy import random as r; r.seed(1)` is missed, because the `seed` check requires `node.value.attr == "random"`.
- `scan_package` scans only `src/f1si/`, so a module placed anywhere else in `src/` is never checked.
- `pandas.read_sql`, `polars` and `ibis` are not covered. Only `duckdb` and `sqlite3` are.
- The CI canary step treats any non-zero pytest exit as "caught". A collection or import error also passes it.

**Fix:** Extend the names. Scan all of `src/**` and use `ast` to resolve import aliases. In the canary, assert on the output, for example `pytest ... 2>&1 | grep -q "_canary imports duckdb"`.

**Outcome:** fixed in 5e88d08 (DEC-052). `PCG64DXSM`, `BitGenerator`, `SeedSequence`, `numpy.random` aliases, `polars`, `ibis`, `sqlalchemy` and `pandas.read_sql*` are covered; the scan covers all of `src/`; the CI canary greps the pytest output for the expected violation, so a collection error cannot pass for "caught".

## Info

### IN-01: `$` in the slug and driver-code regexes accepts a trailing newline

**File:** `src/f1si/plots/stints.py:65-66, 115, 332, 337`
**Issue:** `re.match(r"^[A-Z]{3}$", "VER\n")` matches. A `--drivers` value or slug with a trailing newline passes validation and would reach the file name. This is low risk (the slug comes from the database), but the validation is meant to be strict.
**Fix:** Use `re.fullmatch` for both patterns.

### IN-02: HTTP clients are never closed

**File:** `src/f1si/data/sources/openf1.py:139-166`, `src/f1si/data/sources/_http.py:153-156`
**Issue:** `RateLimitedClient.close()` exists but `OpenF1Source` and `JolpicaClient` expose no way to call it. The SQLite cache handles stay open until interpreter exit. On Windows this keeps the file locked, which causes `PermissionError` on temp-directory cleanup and when another process opens the cache.
**Fix:** Give `OpenF1Source` a `close()` and context-manager methods. Call them from `_cmd_load` in a `try/finally`.

### IN-03: Workflow hygiene

**File:** `.github/workflows/ci.yml:23-25`, `.github/workflows/real-data.yml:26-40`
**Issue:** Third-party actions are pinned to mutable tags (`@v7`, `@v10.3.1`, `@v6`) rather than commit SHAs. The real-data cache key is static (see WR-05). `permissions: contents: read` is correct.
**Fix:** Pin by SHA with a version comment. Use a key such as `real-data-http-cache-${{ github.run_id }}` with `restore-keys`, or drop the cache.

### IN-04: `AsOf` rejects NumPy integers

**File:** `src/f1si/data/_snapshot.py:71`
**Issue:** `isinstance(np.int64(5), int)` is False, so `AsOf(race, np.int64(5))` raises `ValueError`. Walk-forward code that loops over a pandas or NumPy lap column will hit this.
**Fix:** Accept `numbers.Integral`, excluding `bool`, and coerce with `int(...)`.

### IN-05: CLI input validation is uneven for `load`

**File:** `src/f1si/cli.py:190-194`
**Issue:** For every command except `plot`, a `ValueError` is re-raised and the user gets a traceback. Examples are `--seed -1` (from `make_rng`) and a bad `--seasons` value that gets past the era check. There is no range check on `--seasons` or `--seed` at the argparse level. The `UnknownEraError` branch is the only friendly one.
**Fix:** Print `str(err)` and return 1 for `ValueError` in all commands unless `--debug`. Validate `--seed >= 0` with an `argparse` type function.

### IN-06: Integer parsing in `_whole` can raise `OverflowError`

**File:** `src/f1si/data/sources/openf1.py:75-81`
**Issue:** `float("inf")` and the text "Infinity" pass `_number`. `int(number)` then raises `OverflowError`. The loader's generic `except Exception` turns this into a vague `LoadFailure`, not a `SourceError` with the "Unexpected response" wording.
**Fix:** Check `math.isfinite(number)` in `_number` (return None or raise `_unexpected`).

---

_Reviewed: 2026-10-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
