---
phase: 01-foundation-data
verified: 2026-10-22T18:30:00Z
status: human_needed
score: 5/5 roadmap success criteria verified (10/10 requirements satisfied); 4 owner-only human checks outstanding
overrides_applied: 0
gaps: []
human_verification:
  - test: "Run the weekly real-data workflow by hand (Actions tab -> 'Real data (non-blocking)' -> Run workflow)"
    expected: "Job 'bahrain-2023' passes (8 network tests). Confirms OpenF1/Jolpica accept GitHub's shared runners; the workflow file itself says this is unverified."
    why_human: "Needs the owner's GitHub session; the workflow has never been dispatched (the 6 most recent runs listed by the API are all 'CI'). Not part of any roadmap success criterion and cannot block pushes."
  - test: "Read docs/explained/phase-01.md, including its 'Interview questions'"
    expected: "Owner can explain in their own words why 'as of lap 15' shows 15 laps for the leader and at most 14 for others, and why final results sit behind a separate door."
    why_human: "UI-03 artifact exists and is substantive, but whether it is understandable to this reader is a subjective judgement."
  - test: "Owner runs `uv run f1si races` on their own machine"
    expected: "87 races cached (17 out-of-sample and locked); 2023-2025 rows show ground_effect_2022_2025 / no; 2026 rows show reg_2026 / yes (locked)."
    why_human: "Already reproduced by the verifier on this machine (see Behavioral Spot-Checks); listed only because 01-11-SUMMARY collected it as an owner check. Can be ticked immediately."
  - test: "Owner views reports/bahrain-2023.png"
    expected: "20 driver panels, compound colours, faded pit/slow laps, stint lines."
    why_human: "Visual. Already observed and confirmed by the orchestrator; listed for the owner's own sign-off only."
---

# Phase 1: Foundation & Data - Verification Report

**Phase Goal:** User can load 2023-2025 races into a local cache, see Bahrain 2023 lap times by stint, and trust that no code can read future data
**Verified:** 2026-10-22
**Status:** human_needed (all automated and goal-backward checks pass; only owner sign-off items remain)
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A push runs lint, type-check and tests in CI, and CI is green | VERIFIED | `.github/workflows/ci.yml` runs on `push`/`pull_request`, matrix ubuntu+windows: `uv sync --locked`, `ruff check`, `ruff format --check`, `mypy`, `pytest --cov`, plus a Linux canary step. GitHub API: run 39809071665 (head_sha 96f0830 = current HEAD) and run 39808481318 (269cf29) both `status: completed, conclusion: success`; jobs `checks (ubuntu-latest)` and `checks (windows-latest)` every step success, including the canary. Locally: `ruff check` clean, `ruff format --check` 68 files clean, `mypy` strict "no issues in 64 source files", `pytest -q` 359 passed (8 network deselected). |
| 2 | One command gives 2023-2025 laps, stints, pit stops and results in a local DuckDB file | VERIFIED | `uv run f1si races` on the real cache: 87 races, 70 in-sample (22+24+24) + 17 locked 2026, all `load_status = complete`. `data/f1si.duckdb` tables: laps 97,018; stints 4,964; pit_stops 3,243; results 1,772; entries, race_control, weather, track_status, lap_cutoffs also populated. Query: zero in-sample races with an empty laps/stints/pit_stops/results table. `f1si load` exists in the CLI (`load,races,plot`), defaults to OpenF1+Jolpica (DEC-005). |
| 3 | User can produce a lap-time-by-stint plot for Bahrain 2023 from the cache | VERIFIED | `f1si plot` subcommand; `src/f1si/plots/stints.py` builds from `AsOfAccessor(...).snapshot(RACE_END)`-style snapshot (registered as consumer `stint_plot_data`); `reports/bahrain-2023.png` exists (orchestrator viewed: 20 panels, compound colours, faded slow laps, stint lines, plausible patterns). Bahrain 2023 in cache: 1,058 laps, 20 drivers, max lap 57. `tests/plots/test_stint_plot.py` and `tests/real/test_bahrain_2023.py` pass (8 network tests re-run by verifier: 8 passed). |
| 4 | As-of accessor for lap N never returns rows after lap N, and a deliberately leaking test case fails the build | VERIFIED | Real data, race 2023-01: lap 0 -> 0 laps; lap 1 -> max lap_number 1; lap 10 -> 181 rows, max lap 10; lap 30 -> max lap 30; RACE_END -> max 57. Cutoff rule is `visible_at_s IS NOT NULL AND visible_at_s <= cutoff` (DEC-001). Both guard halves exist and pass, see DAT-04 below. CI canary step copies `tests/fixtures/leaky_consumer.py` into `src/f1si/_canary.py` and requires the import-ban test to fail - passed in both CI runs. |
| 5 | Every cached race shows its era, 2026 flagged out-of-sample; same seed gives identical results; DECISIONS.md exists with first entries | VERIFIED | `f1si races` ERA column: 70 x `ground_effect_2022_2025` / no, 17 x `reg_2026` / `yes (locked)`. DB: `(complete, False, ground_effect_2022_2025, 70)`, `(complete, True, reg_2026, 17)`. `AsOfAccessor.snapshot/history` on `2026-01` raises `OutOfSampleLockedError` (run live). `f1si.rng.make_rng` is the only `default_rng` caller (import ban POLICY enforces; `tests/test_rng.py` passes). `DECISIONS.md` has 51 `DEC-` entries with context/decision/why/alternatives/consequences. |

**Score:** 5/5 roadmap criteria verified.

### DAT-04 two-halves check (explicitly requested)

DAT-04 was ticked by 01-05 (import ban only) before the scramble half landed in 01-07. Both halves now exist and pass:

| Half | Artifact | Evidence |
|------|----------|----------|
| Around the accessor: import ban | `tests/guards/import_scan.py` (AST scan, single `POLICY` table; protects duckdb, sqlite3, network libs, RNG constructors, `_db`, `_snapshot`, results door, out_of_sample door) + `tests/guards/test_import_ban.py` (27 snippet cases incl. `importlib`/`__import__` string imports, relative imports; real tree clean; canary copy of src tree; planted fixture flagged) | Real `src/` scan returns `[]`; planted `leaky_consumer.py` flagged with `duckdb`; canary copy caught. All pass in the 359. |
| Through the accessor: future scramble | `tests/guards/scramble.py` (`scramble_future`, `assert_no_lookahead`: writes original and future-scrambled DBs, runs consumer on each, exact deep compare) + `tests/guards/test_future_scramble.py` (harness self-checks: every table covered, visible rows byte-identical, every future row differs, junk later race, row order shuffled; hypothesis property test over race x lap x seed x consumer; explicit edge laps 0/12/RACE_END) | Passes. `tests/guards/consumers.py` registers 6 consumers incl. `stint_plot_data`. |
| Meta-test | `tests/guards/test_meta_guard.py` | `leaky_consumer` (direct duckdb) caught by BOTH scan and scramble; three through-accessor leaks (`lap_plus_three`, `race_end_weather`, `history_of_next_race`) produce zero scan violations yet raise `LookaheadDetected`; all honest consumers pass. All pass. |

The documented known gaps (DEC-002 consequences: lap-range error reveals race length; ~20% row drop means probing-only consumers are caught probabilistically) are honestly recorded and do not contradict criterion 4 (rows after lap N are never returned).

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `pyproject.toml`, `uv.lock`, `src/f1si/` (64 typed modules, `py.typed`) | VERIFIED | `uv sync --locked` in CI; mypy strict clean |
| `.github/workflows/ci.yml` | VERIFIED | Wired; green on 2 OSes |
| `.github/workflows/real-data.yml` | VERIFIED (not yet dispatched) | Schedule + manual only; non-blocking by design |
| `src/f1si/data/{_db,_snapshot,asof,results,out_of_sample,loader,schema,derive}.py` | VERIFIED | Substantive (1,690 lines across `data/*.py`), wired through CLI and plots |
| `src/f1si/data/sources/{openf1,jolpica,_http,synthetic_source,track_status_map}.py` | VERIFIED | Real adapters + 8 network tests pass |
| `src/f1si/{eras,rng,paths,cli}.py`, `plots/stints.py`, `synthetic/generator.py` | VERIFIED | Exercised by tests and live commands |
| `tests/guards/*`, `tests/fixtures/*` | VERIFIED | See DAT-04 section |
| `DECISIONS.md`, `README.md`, `docs/explained/phase-01.md` | VERIFIED | Exist, substantive |
| `data/f1si.duckdb`, `reports/bahrain-2023.png` | VERIFIED | Real data present; untracked by git as intended |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| CLI `plot` | cache | `AsOfAccessor.snapshot` -> `prepare_stint_plot_data` -> matplotlib | WIRED |
| CLI `load` | OpenF1/Jolpica -> loader -> `_db.write` | `RaceSource` protocol; transactional per-race | WIRED (87 races in real DB) |
| Strategy/model code | race rows | only `f1si.data.asof` (POLICY forbids `_db`, `_snapshot`, `duckdb`) | WIRED + enforced |
| Results / 2026 data | consumers | separate doors restricted to `backtest.scoring` / `evaluation.holdout` | WIRED + enforced (POLICY rules; live `OutOfSampleLockedError`) |
| Any RNG creation | `f1si.rng.make_rng` | POLICY bans `random`, `RandomState`, `seed`, `default_rng` etc. elsewhere | WIRED + enforced |

### Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Real data | Status |
|----------|---------------|--------|-----------|--------|
| Stint plot | snapshot laps/stints | DuckDB tables via as-of door | Yes (Bahrain 2023: 1,058 laps, 20 drivers) | FLOWING |
| `f1si races` | catalog | `races` table | Yes (87 rows) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `uv run pytest -q` | 359 passed, 8 deselected (157 s) | PASS |
| Lint / format / types | `ruff check .`, `ruff format --check .`, `mypy` | all clean | PASS |
| Real-data tests | `uv run pytest -m network -q` | 8 passed | PASS |
| Cache listing | `uv run f1si races` | 87 races (17 out-of-sample and locked) | PASS |
| As-of cutoff on real data | `AsOfAccessor.snapshot(AsOf("2023-01", n))` for n=0,1,10,30,RACE_END | max lap_number = n (0 rows at lap 0); 57 at end | PASS |
| 2026 lock | `snapshot`/`history` on `2026-01` | `OutOfSampleLockedError` both | PASS |
| TBD/FIXME/XXX/TODO/HACK scan of src, tests, .github | grep | no matches | PASS |

### Probe Execution

Step 7c: no `probe-*.sh` scripts declared or present - SKIPPED.

### Requirements Coverage

All 10 IDs appear in at least one PLAN `requirements:` frontmatter; REQUIREMENTS.md maps exactly these 10 to Phase 1 (no orphans). INT/PAC/etc. belong to Phases 2+.

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| FND-01 | 01-01, 01-02 | SATISFIED | uv-managed Python 3.12 `src/f1si`, ruff + mypy strict + pytest all run clean |
| FND-02 | 01-01, 01-03, 01-05, 01-11 | SATISFIED | CI green on HEAD, both OSes |
| FND-03 | 01-02, 01-03, 01-05 | SATISFIED | `make_rng`; import ban on other RNG constructors; `tests/test_rng.py` |
| FND-04 | 01-05, 01-08, 01-09, 01-11 | SATISFIED | `DECISIONS.md`, 51 entries; `tests/test_decisions_log.py` passes |
| DAT-01 | 01-02, 01-03, 01-04, 01-06, 01-08, 01-10 | SATISFIED | 70/70 in-sample races loaded, all tables populated |
| DAT-02 | 01-09, 01-10 | SATISFIED | `f1si plot bahrain-2023` -> PNG verified |
| DAT-03 | 01-07, 01-09 | SATISFIED | `AsOfAccessor` only door; lap-N cutoff verified on real data |
| DAT-04 | 01-05, 01-07, 01-11 | SATISFIED | Both halves + meta-test exist and pass (see section above) |
| DAT-05 | 01-02, 01-03, 01-07, 01-10 | SATISFIED | Era column; 2026 `out_of_sample` + locked door |
| UI-03 | 01-11 | SATISFIED (artifact) | `docs/explained/phase-01.md` substantive; comprehension is a human check |

### Anti-Patterns Found

None blocking. No debt markers (TBD/FIXME/XXX/TODO/HACK) in src, tests or workflows.

### Warnings (non-blocking, for the next planner)

1. **Partial lap data for some real races.** Laps per race vs. max lap x 20 drivers: Miami 2025 (`2025-06`) holds only 559 laps (about 52% coverage; most finishers have ~33 of 57 laps, driver 87 only 5). Four in-sample races are below 80% coverage (2025-06, 2023-20 at 78%, 2024-08 at 79%, plus others near 80-86%). The loader's completeness check (`_check_complete` in `openf1.py`) validates entry counts and non-empty tables but not per-driver lap coverage, so the summary's "zero upstream gaps" is true by the loader's definition but not by lap completeness. Bahrain 2023 (the phase target) is fine (20 drivers, 57 laps, 3 null lap times). Does not violate any Phase 1 criterion (laps ARE loaded), but Phase 2 pace fitting and the Phase 6 backtest should either exclude or flag races with low coverage (suggest a per-race `lap_coverage` figure in the catalog or a note in DECISIONS.md).
2. **Odd 2026 slug** `bahrain-grand-prix-in-malaysia-2026` (upstream Jolpica naming, locked race; documented in 01-10-SUMMARY). Cosmetic.
3. **Real-data workflow never dispatched on GitHub**; OpenF1 acceptance of GitHub runners is unverified (see human item 1). It is non-required and cannot affect CI.

### Human Verification Required

See frontmatter `human_verification`. Items 3 and 4 have already been reproduced/observed by the verifier/orchestrator; items 1 and 2 need the owner. None indicates a defect.

### Gaps Summary

No gaps. Every roadmap success criterion is observably true in the code, the real cache and GitHub CI; all 10 requirement IDs are accounted for with implementation evidence; DAT-04's import-ban, future-scramble and meta-test halves all exist and pass. Status is `human_needed` only because the owner-sign-off items collected in 01-11-SUMMARY remain open (workflow dispatch, explainer comprehension); the lap-coverage observation is a recommendation for Phase 2, not a Phase 1 blocker.

---

## Post-Review Addendum (2026-10-22, after the code-review fixes)

The verification above ran before the code review fixes. The phase code review (`01-REVIEW.md`) found 1 critical issue and 11 warnings, and all 12 were fixed in commits 5e88d08 through a475717 (DEC-052 to DEC-060). The orchestrator re-checked afterwards:

- **CR-01 (import-ban bypass) is closed.** Three throwaway modules each produced 1 violation:
  - `from f1si.data.asof import _db`;
  - `asof._db` attribute access;
  - `importlib.import_module("f1si.data._db")`.

  Before the fix, the first one produced 0 violations. A second canary fixture (`tests/fixtures/leaky_reexport.py`) now has to be caught in the meta-test and in the CI canary.
- **Gates.**
  - ruff check, ruff format --check and mypy strict (67 files) are clean.
  - `pytest -q` gives 509 passed, 8 deselected, up from 359.
  - `pytest -m network` gives 8 passed, run against the rebuilt cache.
- **Real cache rebuilt with the fixed loader.** The pre-fix cache is kept as `data/f1si.pre-review-fixes.duckdb`.
  - The load finished with "87 loaded, 0 skipped, 0 failed" and `f1si races` reports "87 races cached (17 out-of-sample and locked)".
  - The new checks reported 3 notes:
    - 2024-04 has 1 corrupt lap end dropped (driver 22, lap 2, -1327.2 s).
    - qatar-2024 has an unknown starting tyre for 2 drivers.
    - australian-2026 has an unknown starting tyre for 7 drivers.
- **Known limits (documented, not gaps):**
  - DEC-056: `pit_lane_start` is observed during lap 1 but is visible in `entries` from lap 0, which is one lap early for that single flag.
  - Upstream lap coverage is partial in some races. Miami 2025 is about 52%, and 2023-20, 2024-08 and 2025-01 are 78-80%. Phase 2 and Phase 6 should flag or exclude low-coverage races.

The status stays `human_needed`, and only the owner sign-off items above remain.

---

_Verified: 2026-10-22 (addendum after the review fixes)_
_Verifier: Claude (gsd-verifier); addendum by the orchestrator_
