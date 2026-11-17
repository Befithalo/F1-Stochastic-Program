---
phase: 01-foundation-data
plan: 02
subsystem: data
tags: [duckdb, pandas, schema, rng, eras, uv, pytest]

requires:
  - phase: 01-01
    provides: scaffold, pinned dependencies, CI workflow, pre-commit config
provides:
  - uv.lock (hash-pinned lock; CI's `uv sync --locked` can now succeed)
  - RED end-to-end skeleton test (load synthetic, then list races) that plan 01-03 turns green
  - f1si.rng.make_rng (only generator constructor), f1si.eras, f1si.paths
  - f1si.data.slugs, errors, and the RaceSource protocol with shared source errors
  - f1si.data.schema (races, entries, laps, stints and pit_stops views, normalize, validate_race)
  - f1si.data._db (only duckdb importer; transactional per-race write, parameterized reads)
affects: [01-03, 01-04, 01-05, 01-06, 01-07, 01-08, 01-09]

tech-stack:
  added: []
  patterns:
    - "One DuckDB transaction per race, races row written last as completion marker"
    - "Single visibility predicate: visible_at_s IS NOT NULL AND visible_at_s <= cutoff"
    - "Canonical pandas dtypes via schema.normalize; NA stored as SQL NULL"
    - "Tests for a real DuckDB file use a child process to hold the write lock"

key-files:
  created:
    - uv.lock
    - tests/test_e2e_skeleton.py
    - src/f1si/rng.py
    - src/f1si/eras.py
    - src/f1si/paths.py
    - src/f1si/data/__init__.py
    - src/f1si/data/slugs.py
    - src/f1si/data/errors.py
    - src/f1si/data/sources/__init__.py
    - src/f1si/data/schema.py
    - src/f1si/data/_db.py
    - tests/test_eras.py
    - tests/data/__init__.py
    - tests/data/mini_race.py
    - tests/data/test_slugs.py
    - tests/data/test_schema.py
    - tests/data/test_db_roundtrip.py
  modified:
    - pyproject.toml
    - .gitignore

key-decisions:
  - "Lock errors map to CacheBusyError by matching 'lock', 'being used by another process' or 'already open' in the duckdb.IOException text"
  - "write_race requires every per-race table (strict), so a race can never be marked complete with a table missing"
  - "normalize fills visible_at_s from lap_end_s when a source omits it; write paths always recompute it"

patterns-established:
  - "schema.VIEWS stores SELECT bodies; _db.ensure_schema wraps them in CREATE OR REPLACE VIEW"
  - "Shared hand-written race in tests/data/mini_race.py for schema and storage tests"

requirements-completed: [FND-01, FND-03, DAT-01, DAT-05]

duration: ~40 min
completed: 2026-10-22
---

# Phase 1 Plan 02: Toolchain, Contract Modules and DuckDB Storage Summary

**uv.lock plus a committed RED end-to-end test, and the contract modules under it: seeded rng, regulation eras, the normalized schema with a visibility column, and a transactional DuckDB storage module proven on Windows (round trip, rollback, NULLs, cross-process lock, injection).**

## Performance

- **Tasks:** 3 of 3 complete
- **Tests:** 47 pass; 1 fails by design (`tests/test_e2e_skeleton.py::test_load_synthetic_then_list_races`, "unrecognized arguments: --data-dir ... load --source synthetic")
- ruff check, ruff format --check and mypy strict are clean on the whole tree

## Accomplishments

- Toolchain online: `uv lock`, `uv sync`, `pre-commit install`, ruff, mypy and pytest all run on Windows.
- The end-to-end skeleton test was written first and fails for the right reason (argparse rejects `--data-dir`/`load`), not an import error.
- `make_rng` is the only `default_rng(` call in `src`. `era_for_season` maps 2023-2025 to the in-sample ground-effect era and 2026 to the out-of-sample `reg_2026`; anything else raises `UnknownEraError` pointing to `eras.py`.
- `RaceSource` protocol, `RaceRef`, `NormalizedRace`, `SourceError` and `RateLimitedError(retry_after_s)` fix the data-source contract.
- `schema.py` defines `races`, `entries`, `laps`, the `stints` and `pit_stops` views, `normalize`, `add_visibility`, `validate_race` and `ddl`.
- `_db.py` is the only duckdb importer. Verified on Windows: round trip equals what was written, NA becomes SQL NULL, re-writing a race is idempotent, a failed write leaves no rows (and a failed re-write keeps the previous complete race), a child process holding the write lock yields `CacheBusyError` for both reads and writes, a missing file yields `CacheMissingError`, and a `'; DROP TABLE laps; --` race_id is inert.

## Task Commits

1. **Task 1: Toolchain and failing end-to-end test** - `229f841` (test)
2. **Task 2: Leaf modules (rng, eras, paths, slugs, errors, RaceSource)** - `bb1c4a4` (feat)
3. **Task 3: Normalized schema and transactional DuckDB storage** - `bbca935` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ruff 0.17 format check reformatted Markdown in `.planning/` and `F1 Docs/`**
- **Found during:** Task 1 (`ruff format --check .`)
- **Issue:** ruff 0.17 formats code blocks inside Markdown, so `ruff format --check .` failed on five planning documents, which would also have made the pre-commit hook rewrite them.
- **Fix:** `extend-exclude = [".planning", "F1 Docs"]` under `[tool.ruff]`.
- **Files modified:** pyproject.toml
- **Commit:** 229f841

**2. [Rule 1 - Bug] `.gitignore` pattern `data/` ignored the source package `src/f1si/data` and `tests/data`**
- **Found during:** Task 2 (`git add` refused the new files)
- **Issue:** the unanchored pattern matched any directory named `data`, so the whole data layer and its tests were untrackable.
- **Fix:** anchored the patterns to the repo root (`/data/`, `/reports/`); verified the real `data/` and `reports/` folders are still ignored.
- **Files modified:** .gitignore
- **Commit:** bb1c4a4

**3. [Rule 1 - Bug] Slug of a bare "Grand Prix" did not raise**
- **Found during:** Task 2 (own test)
- **Fix:** trailing "grand prix" is removed with a regex that also matches at the start of the string.
- **Commit:** bb1c4a4

**4. Added `tests/data/mini_race.py`** (not in the plan's file list): the shared hand-written race helper both test files use, instead of duplicating it. No behavior impact.

The plan's version note about pandas/NumPy did not apply: pandas 2.3.3 works with the resolved NumPy, so no extra pin was added.

## Decisions to log (for plan 01-05 to append to DECISIONS.md)

- Lock detection: `duckdb.IOException` text is matched case-insensitively on "lock", "being used by another process" or "already open". Observed on Windows (this machine): `IO Error: Cannot open file "...": The process cannot access the file because it is being used by another process. File is already open in ...python.exe (PID n)`. The Linux wording ("Could not set lock on file ... Conflicting lock is held") is covered by the "lock" phrase but is only checked by CI's ubuntu job, which runs the same subprocess test.
- No PRIMARY KEY constraints; key uniqueness is enforced by `schema.validate_race` and tests (research Pattern 4).
- `write_race` is strict: all of `schema.PER_RACE_TABLES` must be supplied, otherwise `ValueError`. Plan 01-04 appending tables to `TABLES` therefore requires the loader to supply them.
- `normalize` adds `visible_at_s` from the time column when absent; `_db` write paths always recompute it from the time column so stored visibility cannot disagree with the data.
- Views are stored as SELECT bodies in `schema.VIEWS` and wrapped by `_db.ensure_schema`.
- ruff excludes `.planning/` and `F1 Docs/` (prose, not code); `.gitignore` data folders are anchored to the repo root.
- `CacheMissingError(path)` takes the path and builds the message "No cache found at PATH. Run: uv run f1si load"; `CacheBusyError()` takes no arguments.

## Known Stubs

None. Every module is functional; `cli.py` still has no `load`/`races` subcommands by design (plan 01-03).

## Threat Flags

None beyond the plan's threat model. Mitigations T-01-06 (bound parameters, name allow-list, injection test), T-01-07 (per-race transaction with rollback, test), T-01-08 (short-lived connections, CacheBusyError, subprocess lock test) and T-01-48 (`validate_race`) are implemented and tested. T-01-SC: `uv.lock` was created from the approved dependency list.

## Next Phase Readiness

Plan 01-03 can build the synthetic generator, loader and CLI commands on `_db.write_race`, `schema.validate_race` and `RaceSource`, and turn `tests/test_e2e_skeleton.py` green. Nothing was pushed in this plan; CI's `uv sync --locked` now has a committed `uv.lock`.

## Self-Check: PASSED

- All listed source and test files exist; commits 229f841, bb1c4a4 and bbca935 exist on main.
- `grep -rlE '^[[:space:]]*(import|from) duckdb' src` prints only `src/f1si/data/_db.py`; `grep -rl 'default_rng(' src` prints only `src/f1si/rng.py`; `src/f1si/data/__init__.py` has no import lines.
