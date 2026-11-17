---
phase: 01-foundation-data
plan: 03
subsystem: data
tags: [synthetic, duckdb, cli, loader, ci, github-actions]

requires:
  - phase: 01-02
    provides: rng, eras, RaceSource contract, normalized schema, transactional DuckDB storage, RED end-to-end test
provides:
  - Seeded synthetic race generator that exposes its ground truth (SyntheticTruth) for later recovery tests
  - SyntheticSource implementing RaceSource
  - load_races (happy path) and asof.catalog (calendar facts)
  - "f1si load" and "f1si races" CLI subcommands
  - Session fixtures synthetic_races and synthetic_db
  - Project live on GitHub with CI green on ubuntu-latest and windows-latest
affects: [01-04, 01-05, 01-06, 01-07, 01-08, 01-09]

tech-stack:
  added: []
  patterns:
    - "Randomness only through make_rng and keyword-only rng arguments; one spawned child stream per race"
    - "Loader validates a whole race before any write, then writes one transaction per race"
    - "catalog() returns calendar facts only, never results"

key-files:
  created:
    - src/f1si/synthetic/__init__.py
    - src/f1si/synthetic/generator.py
    - src/f1si/data/sources/synthetic_source.py
    - src/f1si/data/loader.py
    - src/f1si/data/asof.py
    - tests/test_rng.py
    - tests/test_synthetic.py
    - tests/test_cli.py
  modified:
    - src/f1si/cli.py
    - tests/conftest.py
    - .github/workflows/ci.yml

key-decisions:
  - "The CLI constructs the source (SyntheticSource(rng=make_rng(seed))); load_races takes a source object (deviation from the RESEARCH responsibility map, per SKELETON)"
  - "setup-uv is pinned to the exact release tag v10.3.1 because the action publishes no floating major tag"

patterns-established:
  - "SyntheticTruth carries the true parameters so recovery tests in later phases can compare fitted values to it"
  - "Per-race rng streams via rng.spawn(n) keep a race independent of how many other races are generated"

requirements-completed: [FND-02, FND-03, DAT-01, DAT-05]

duration: ~2 sessions
completed: 2026-10-22
---

# Phase 1 Plan 03: Synthetic Skeleton, Loader, CLI and First Green CI Summary

**Seeded synthetic races with exposed ground truth flow through validation into DuckDB and back out through `f1si load` and `f1si races`; the project is pushed and CI is green on ubuntu-latest and windows-latest.**

## Performance

- **Tasks:** 3 of 3 complete (Task 3 was the owner-authorised first push plus CI confirmation)
- **Tests:** 67 pass locally, including the end-to-end skeleton test from plan 01-02, which is now green
- ruff check, ruff format --check and mypy strict are clean on the whole tree
- 10 files changed in tasks 1-2 (785 insertions), plus the CI workflow fix

## Accomplishments

- `generate_race` / `generate_dataset` produce races, entries and laps from a seed. The lap-time model equation is in the `generator.py` docstring, and `SyntheticTruth` exposes wear rates, pace offsets, fuel effect and pit laps. The same seed gives identical tables; a different seed changes the lap times.
- `SyntheticSource` implements `RaceSource`, so the loader treats it like any real source.
- `load_races` validates, stamps the era, and writes one transaction per race. `f1si load --source synthetic` prints one progress line per race.
- `f1si races` shows each race's era: `ground_effect_2022_2025` for 2023-2025 and `reg_2026` marked `yes (locked)` for 2026 (DAT-05).
- Pushed `main` to https://github.com/Befithalo/F1-Stochastic-Program. After one CI fix, run https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/39747858072 for commit `6fb9e9b` concluded `success`:
  - `checks (ubuntu-latest)`: success (job 119720718298)
  - `checks (windows-latest)`: success (job 119720718707)

## Task Commits

1. **Task 1: Seeded synthetic generator with known truth, and SyntheticSource** - `0adf313` (feat)
2. **Task 2: Loader, catalog, `f1si load` / `f1si races`; e2e test green** - `63728c8` (feat)
3. **Task 3: First push and CI confirmation** - pushed by the orchestrator under the owner's delegation; CI fix `6fb9e9b` (fix)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] CI failed at job setup: `astral-sh/setup-uv@v10` does not exist**
- **Found during:** Task 3 (CI check of the first pushed sha `63728c8`)
- **Issue:** The first run failed in 9 s on both matrix jobs at "Set up job". The check annotation read "Unable to resolve action `astral-sh/setup-uv@v10`, unable to find version `v10`". setup-uv publishes exact release tags only (latest v10.3.1), no floating major tag. `actions/checkout@v7` does exist.
- **Fix:** Pinned `astral-sh/setup-uv@v10.3.1` in `.github/workflows/ci.yml`.
- **Verification:** Local ruff, format, mypy and pytest were clean before the push; the re-run for `6fb9e9b` was green on both OS jobs.
- **Files modified:** .github/workflows/ci.yml
- **Commit:** `6fb9e9b`

**2. [Rule 1 - Bug] Test lint and typing fixes during Tasks 1-2**
- `PT011` in `tests/test_rng.py` (broad `pytest.raises`) was tightened; a `tuple[int, ...]` annotation was corrected. Both were fixed before their task commits.

### Process notes

- A heredoc quoting failure while creating a file was recovered by using the Write tool instead.
- The commit trailer in this session follows the harness attribution reminder (Claude Sonnet 5.5); earlier plan commits carry "Claude Opus 5.5".
- The first push used the owner's cached Git Credential Manager credential with the owner's delegation; the CI-fix push reused it (`GIT_TERMINAL_PROMPT=0`), no prompt appeared.

## Design Choices (for the record)

- `SyntheticTruth.pit_laps` maps driver_number to a tuple of stop laps; it is empty for a driver who retires before a stop.
- A pit-lane starter pays a lap-1 cost of 3.0 + 5.0 s.
- `race_start_utc` is timezone-naive UTC.
- `SyntheticSource.list_races` ignores `now`.
- `load_races` calls `era_for_season` twice (once to validate, once to stamp).

## Decisions to log (for plan 01-05 to append to DECISIONS.md with the next free DEC numbers)

- The CLI chooses and constructs the source (`SyntheticSource(rng=make_rng(seed))`); `load_races` receives the source. This deviates from the RESEARCH responsibility map, per SKELETON.
- `generate_dataset` uses `rng.spawn(n)` so each race has its own stream.
- Noise is drawn up front as an `(n_drivers, n_laps)` array, driver-major, so the stream consumption is fixed per race.
- The lap-time model equation lives in the `generator.py` docstring; truth fields are named so recovery tests can read them directly.
- `catalog()` returns calendar facts only (never results); plan 01-07 adds the as-of door.
- The loader validates before any write and raises `SourceError` on invalid source data.
- CI pins GitHub Actions to exact tags where the action has no floating major tag (setup-uv `v10.3.1`).

## Known Stubs

None. `LoadReport.skipped` and `LoadReport.failed` are empty by design until plan 01-04 adds resume, retries and the failure list. `laps.track_status` is NA for synthetic data until plan 01-04 fills it.

## Threat Flags

None beyond the plan's threat model. Mitigations:

- T-01-09: pre-push audit found no `data/`, `reports/`, `.duckdb`, `desktop.ini` or secret files among the 65 tracked files.
- T-01-49: validate-before-write is tested (an invalid race writes nothing).
- T-01-50: `rng` arguments are keyword-only and `default_rng(` appears only in `rng.py`.
- T-01-51: CI polling stayed within limits (one poll at 60 s spacing for the fix run, a handful of requests in total, all parsed defensively).

## Next Phase Readiness

Walking skeleton (plans 01-01..01-03) is complete and CI is green on both operating systems. Plan 01-04 can add resume, retries, the failure list and track status on top of `load_races`. The Linux lock-error wording in the `CacheBusyError` subprocess test passed on ubuntu-latest.

## Self-Check: PASSED

- All files listed under key-files exist; commits `0adf313`, `63728c8` and `6fb9e9b` exist on main.
- `git ls-remote origin main` matched local HEAD (`63728c8`) at resume time, and `6fb9e9b` was pushed afterwards.
- CI run 39747858072 for `6fb9e9b`: both matrix jobs `success`.
