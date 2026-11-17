---
phase: 01-foundation-data
plan: 10
subsystem: data
tags: [network-tests, github-actions, real-data, full-load, duckdb, openf1, jolpica]

requires:
  - phase: 01-08
    provides: OpenF1Source, loader completeness checks, pit-lane start rule
  - phase: 01-09
    provides: stint plot used in the Bahrain 2023 network test
provides:
  - tests/real/test_bahrain_2023.py (8 network-marked real-data checks)
  - .github/workflows/real-data.yml (weekly + manual, non-blocking, result on the run summary)
  - Full 2023-2026 cache in data/f1si.duckdb (87 races, 70 in-sample, 17 locked 2026)
affects: [01-11, phase-2]

tech-stack:
  added: []
  patterns:
    - "Network tests load into a temp DuckDB through the shared data/http-cache, so reruns make no API calls"
    - "Non-blocking by construction: separate workflow, no push/PR trigger, not a required check, no error masking"

key-files:
  created:
    - tests/real/__init__.py
    - tests/real/test_bahrain_2023.py
    - .github/workflows/real-data.yml
  modified: []

key-decisions:
  - "No completeness check was loosened and no loader change was needed: the real load produced all 70 in-sample races"

requirements-completed: [DAT-01, DAT-02, DAT-05]

duration: ~35 min (Task 1 about 15 min, full load 15 min)
completed: 2026-10-22
---

# Phase 1 Plan 10: Real-data tests, weekly workflow and the full load Summary

**Bahrain 2023 is pinned by eight network tests that GitHub runs weekly in a separate non-required workflow, and `uv run f1si load` filled the owner's cache with every 2023-2025 Grand Prix (70 of 70) plus the 17 locked 2026 rounds, with zero failures and no upstream gaps.**

## Accomplishments

- `tests/real/test_bahrain_2023.py` (module marker `network`): 20 entries with VER on grid 1; 57 laps, 1,050 to 1,100 lap rows, compounds within SOFT/MEDIUM/HARD; VSC status "6" between the lap 39 and lap 42 cutoffs followed by "1" by lap 45; 35 to 60 pit-in laps and a non-empty `pit_stops` view; non-decreasing cutoffs for laps 0..57 with cutoff(57) between 5,400 and 6,000 s; results door has VER P1; as-of snapshot at lap 15 has exactly one car on 15 laps and all others at most 14; stint plot on the RACE_END snapshot has 20 drivers, 20 visible axes and writes a real PNG. All pass locally in about 3 s (HTTP cache warm). `uv run pytest -q` deselects all 8 (353 passed, 8 deselected).
- `.github/workflows/real-data.yml`: name "Real data (non-blocking)", triggers `schedule` (cron `17 6 * * 1`) and `workflow_dispatch` only, `permissions: contents: read`, one job with `timeout-minutes: 30`, `PYTHONUTF8`, HTTP cache only via `actions/cache@v6` on `data/http-cache`, step `id: network` running `uv run pytest -m network -v`, and an `if: always()` bash step that writes the heading, `Result: ${{ steps.network.outcome }}` and the "not a required check" line to `$GITHUB_STEP_SUMMARY`. No error masking, no push/PR trigger, no artifact upload. YAML comments explain the non-blocking design, owner emails on failed scheduled runs, the 60-day inactivity disable, and that OpenF1 access from GitHub runners is unverified.
- Full real load: `uv run f1si load`, one run, `Done: 86 loaded, 1 skipped, 0 failed` (the skip is Bahrain 2023 from 01-08).

## Full load results

| Season | Races loaded | Era | Out-of-sample |
|--------|--------------|-----|---------------|
| 2023 | 22 | ground_effect_2022_2025 | no |
| 2024 | 24 | ground_effect_2022_2025 | no |
| 2025 | 24 | ground_effect_2022_2025 | no |
| 2026 | 17 | reg_2026 | yes (locked), all 17 |

- `uv run f1si races` footer: "87 races cached (17 out-of-sample and locked)". In-sample loaded = 70, documented gaps = 0, so 70 + 0 accounts for all 70 in-sample races. Every 2026 row shows `reg_2026` and `yes (locked)`. All 87 rows have `load_status = complete`.
- Runtime: started 14:54:13 UTC, finished before 15:09:43 UTC, about 15 minutes (faster than the 20-30 minutes estimated). Exit code 0, no retries needed.
- Entries per race: 2023 all 20; 2024 and 2025 between 19 and 20; 2026 all 22.
- Oddity (upstream naming, not a bug): 2026 round 16 is `bahrain-grand-prix-in-malaysia-2026` (event "Bahrain Grand Prix in Malaysia", circuit `sepang`, race start 2026-10-04 07:00 UTC). The slug comes from the Jolpica event name through the slug rule from 01-08 (DEC-047); it loads, is locked, and is correct for the data. Worth a glance by the owner if a shorter slug is wanted; not changed here.

## Upstream data gaps

None. All 70 in-sample races loaded, so `01-UPSTREAM-GAPS.md` was not created (the plan says to create it only if at least one gap exists). `MIN_ENTRIES: Final = 18` and `MAX_ENTRIES: Final = 22` in `src/f1si/data/sources/openf1.py` are untouched (no commit since 01-08 touched that file).

## Grid-0 entries (pit-lane start rule check)

Query: entries with `grid_position IS NULL` joined to results. 4 entries across 4 races.

| race_id | driver | pit_lane_start | Jolpica status | laps_completed |
|---------|--------|----------------|----------------|----------------|
| 2023-13 (dutch-2023) | MAG | True | Finished | 72 |
| 2023-15 (singapore-2023) | STR | False | Withdrew | 0 |
| 2023-19 (mexico-city-2023) | STR | True | Collision damage | 66 |
| 2024-20 (mexico-city-2024) | OCO | True | Lapped | 70 |

Reading: the three pit-lane starters have statuses of cars that ran (finished, collision damage after 66 laps, lapped on lap 70), and the one car that never took the start (STR, Singapore 2023, "Withdrew", 0 laps) is correctly `pit_lane_start = False`. The DEC-049 rule held on all real cases; `NON_STARTER_STATUSES` did not need a change, and the rule still ignores laps completed (look-ahead). No status additions.

## Task Commits

1. **Task 1: Bahrain 2023 network tests and the weekly real-data workflow** - `d12e552` (test)
2. **Task 2: full real load** - no code change (the load wrote only to the gitignored `data/`); nothing to commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The plan's verify grep for MIN_ENTRIES does not match the source text**
- **Found during:** Task 2 verification
- **Issue:** The plan greps `MIN_ENTRIES = 18` and `MAX_ENTRIES = 22`, but the source (from 01-08) writes `MIN_ENTRIES: Final = 18`, so the literal grep fails although the values are unchanged.
- **Fix:** Checked the values directly (`MIN_ENTRIES: Final = 18`, `MAX_ENTRIES: Final = 22`, lines 46-47) and confirmed `git log` shows the file unchanged since 01-08. No code change.

**2. [Rule 3 - Blocking] YAML comment contained the word the verify forbids**
- **Found during:** Task 1
- **Issue:** My first comment in real-data.yml named the forbidden option, which the plan's `! grep -q "continue-on-error"` would catch.
- **Fix:** Reworded the comment to "error-masking option" before committing.

**3. [Rule 1 - Consistency] setup-uv pinned to `@v10.3.1`, not `@v10`**
- ci.yml already uses `astral-sh/setup-uv@v10.3.1`; the new workflow uses the same pin for consistency. No acceptance check depends on the tag.

**4. Lint**: the first draft of the test used `zip()` without `strict=`; replaced with `strict=True` and `itertools.pairwise` for ruff.

Otherwise the plan was executed as written; no parsing quirk surfaced, so openf1.py and tests/data/test_openf1.py were not modified.

## Decisions to log

None. No DECISIONS.md change in this plan (DEC-050 is the last entry; MIN_ENTRIES unchanged). For plan 01-11: the Grid-0 table above is real-data confirmation for the existing "Pit-lane start rule" (DEC-049); the rule did not change.

## Human checks (collected for the end of the phase)

- In PowerShell: `cd $HOME\Documents\f1si` then `uv run f1si races`. Expect 87 rows: every 2023-2025 Grand Prix with era `ground_effect_2022_2025` and out-of-sample `no`, each 2026 race with `reg_2026` and `yes (locked)`, last line "87 races cached (17 out-of-sample and locked)".
- After 01-11 pushes: run the "Real data (non-blocking)" workflow once by hand from the Actions tab and confirm the run summary shows "Result: success" (OpenF1 access from GitHub runners is unverified; a failure there does not affect CI).

## Known Stubs

None.

## Threat Flags

None beyond the plan. T-01-42 (cache only, no artifact upload, data/ and reports/ untracked: `git ls-files data reports` empty), T-01-44 (`contents: read`, no secrets), T-01-45 (one race, weekly, cached), T-01-53 (completeness checks untouched, zero gaps) and T-01-54 (outcome written on every run with `if: always()`) are implemented.

## Self-Check

- Files exist: tests/real/__init__.py, tests/real/test_bahrain_2023.py, .github/workflows/real-data.yml.
- Commit d12e552 exists on main.
- ruff check, ruff format --check, mypy strict clean; 353 passed offline, 8 network tests passed with `-m network`.

## Self-Check: PASSED
