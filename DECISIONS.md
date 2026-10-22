# Decisions log

Every method choice in this project, and why we made it (FND-04). One entry per decision, newest at the bottom; a changed decision gets a new entry that refers back to the old one.

## DEC-001 — Leader's-clock lap cutoff

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A backtest asks "what did we know at lap N of race R?". Cars finish lap N at different moments, and lapped cars finish it later than the leader, so "lap N" needs one precise meaning that never lets future information in.
**Decision:** "As of race R, lap N" means the race-clock time at which the leader completes lap N. Lap 0 is lights out (t = 0 s). Every time-indexed row carries `visible_at_s`, and a row is visible if and only if `visible_at_s IS NOT NULL AND visible_at_s <= cutoff`. At cutoff N the leader therefore shows N completed laps and every other car at most N-1.
**Why:** One shared clock gives one shared race state, matches the single `lap` field in the BUILD_PLAN `RaceState`, and errs on the safe side: lapped cars see slightly less than they could, never more.
**Alternatives rejected:** A lap-number cutoff (a lapped car's lap N finishes after the leader's, so it would leak the leader's future). Per-driver clocks (no shared race state, and every table would need its own cutoff).
**Consequences:** Phase 2's `RaceState` needs a per-car `laps_completed`, because cars differ at the same cutoff. Rows with an unknown time (`visible_at_s` NULL) are never visible.
**Refs:** D-01, DAT-03

## DEC-002 — Two look-ahead guards in CI

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The project's core value is that a recommendation never uses future data. A rule written in a document is not enough, because code written later (often by an AI assistant) can reach around it.
**Decision:** Two checks run in CI. (1) An AST import scan (`tests/guards/import_scan.py`) with one `POLICY` table: it lists which modules may import duckdb, sqlite3, the network libraries, the random-number constructors, the storage layer and the two guarded doors. (2) A future-scramble property test using hypothesis (plan 01-07): replace every row after the cutoff with garbage and require the as-of output to be identical. Deliberately leaky fixtures are planted, a meta-test proves both checks catch them, and a CI canary step copies the leaky fixture into `src/f1si` and requires the import-ban test to fail.
**Why:** The scan is chosen over import-linter because it also catches `importlib.import_module` and `__import__` string imports, can scan fixtures outside the package, and needs no second configuration file. The scramble test covers behaviour that no static scan can see.
**Alternatives rejected:** import-linter (misses string imports, duplicate config). A single guard (each one alone has blind spots the other covers).
**Consequences:** Honest limits: Python cannot be sandboxed, so the import ban stops accidents and obvious bypasses, and the scramble test catches behaviour. Two gaps are known and accepted. (a) Asking the as-of door for a lap beyond the race raises `LapOutOfRangeError`, so a consumer that probes later laps learns the race length (a future fact). (b) The scramble rewrites future rows and drops about 20% of them, so a consumer that requests lap N+k and only checks whether a snapshot comes back is caught on some generated examples but not on every one. Lap N+k requests that read the returned rows are always caught.
**Refs:** D-02, DAT-04

## DEC-003 — Two doors: as-of versus results

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Strategy code needs the race so far, but never the outcome. Scoring needs the outcome, but only after the fact.
**Decision:** The as-of door (`f1si.data.asof`) never serves final position, stint end lap, stint length or total stops. It rebuilds stints and pit events from the laps visible so far. Final outcomes come only from `f1si.data.results`, which only `f1si.backtest.scoring` may import (enforced by the import ban).
**Why:** The separation makes "who can see the answer" a property that a test can check, rather than a convention.
**Alternatives rejected:** One accessor with an `include_results=True` flag (explicitly rejected by the owner: a flag can be set by accident).
**Consequences:** Stints and pit events seen through the as-of door are rebuilt, so a stint that is still running has no end lap yet. Phase 6's scorer is the only planned consumer of the results door.
**Refs:** D-03, DAT-04

## DEC-004 — One accessor governs walk-forward; 2026 behind its own door

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Backtests walk forward across seasons, so the accessor must also say what earlier and later races look like. 2026 is held out for the final evaluation.
**Decision:** As of (race R, lap N) the accessor returns all earlier in-sample races in full, including their final results (revised 2026-10-22: finishing positions and status are past facts later models need); pre-race facts for R; and R up to the cutoff. Later races are invisible. 2026 races raise `OutOfSampleLockedError` and are served only by `f1si.data.out_of_sample`, which only `f1si.evaluation.holdout` may import.
**Why:** Past results are legitimate training data for later races; only the current race's outcome must stay hidden. A separate door for 2026 follows the same principle as DEC-003 and can be checked by the import ban.
**Alternatives rejected:** An `unlock=True` flag on the accessor (same weakness as `include_results=True`).
**Consequences:** The out-of-sample door is used once, in Phase 8. Per-season breakdowns stay possible because the season column is kept.
**Refs:** D-04, D-05, DAT-05

## DEC-005 — Data source: OpenF1 and Jolpica replace FastF1

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The original plan used FastF1. Since 2026-10-15 F1's live-timing archive returns HTTP 401 without an F1 TV login. We confirmed it with curl on 2026-10-22 (401 for the 2023 index and the Bahrain 2023 race); FastF1 issue #978 documents it; the FastF1 mirror returns 404 for 2023-2026; `fastf1==3.9.0a0` is an alpha that needs a paid F1 TV account.
**Decision:** OpenF1 (free, no key, history from 2023) supplies laps, stints, race control, weather and drivers. Jolpica (the Ergast successor) supplies schedule rounds, results, grid positions and pit stops. Both sit behind a `RaceSource` protocol whose output is the normalized tables, so an authenticated FastF1 source can be added later without changing anything downstream.
**Why:** It is the only free route to 2023-2025 lap data today, and the protocol keeps the choice reversible.
**Alternatives rejected:** FastF1 only (cannot download any season into an empty cache). Scraping the timing archive (not accessible without login).
**Consequences:** Rate limits are respected: OpenF1 allows 3 requests per second and 30 per minute; Jolpica allows a burst of 4 per second and 500 per hour, and answers HTTP 429 when exceeded. OpenF1 terms are personal, non-commercial use, which this project is; the README must credit it (Phase 6).
**Refs:** D-08, DAT-01

## DEC-006 — Synthetic data on every push; weekly non-blocking real-data workflow

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Real data needs the network, can be slow or rate-limited, and the BUILD_PLAN says not to republish raw data.
**Decision:** Every push runs on small fake races generated in code with known values. Push CI makes no network calls and commits no real data. Tests that need the internet carry the `network` marker and are excluded by default (`-m "not network"`). A separate workflow, weekly and on manual trigger, downloads Bahrain 2023 from OpenF1 and Jolpica and runs those tests; it is not a required check.
**Why:** An outage of a free public API must never block the main build, and synthetic data with known truth is what makes recovery tests possible.
**Alternatives rejected:** Real data in every CI run (flaky, rate-limited). Committing a real-data sample (republishes raw data).
**Consequences:** Whether OpenF1 blocks GitHub datacenter IPs is unverified; if it does, the weekly job fails without blocking anything and the tests stay runnable locally.
**Refs:** D-09, D-10, D-11

## DEC-007 — Regulation era tags

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Car behaviour changes with the rules, so races need an era label, and the 2026 races must be held out.
**Decision:** Two era tags: `ground_effect_2022_2025` (in-sample; the loaded seasons 2023-2025 belong to it) and `reg_2026` (out-of-sample). The `season` column is kept for per-season breakdowns. A season outside the table raises `UnknownEraError`, so a new era must be added to `f1si/eras.py` and logged here.
**Why:** The 2023-2025 cars share one rule set; splitting them per season would lose pooling and add nothing. Failing loudly on an unknown season stops a new era from being silently lumped into an old one.
**Alternatives rejected:** One tag per season (no pooling). No tag, season only (the out-of-sample lock would be a list of years scattered in code).
**Consequences:** Adding 2027 or an earlier season is a deliberate edit plus a new log entry.
**Refs:** DAT-05, D-05

## DEC-008 — Precomputed lap cutoffs

**Date:** 2026-10-22
**Status:** Accepted
**Context:** DEC-001 defines the cutoff as the leader's lap-N completion time. Computing `min(lap_end_s)` over lap N at query time would read other cars' rows for lap N, which may lie in the future of an earlier cutoff.
**Decision:** The loader computes the cutoffs once, at load time, into the `lap_cutoffs` table. Lap 0 is 0.0. Lap n is the minimum non-null `lap_end_s` of lap n; a lap nobody completed is +infinity. A reverse cumulative minimum then makes the sequence non-decreasing (a cutoff may only become earlier, which is the safe direction), and trailing +infinity values are dropped. The as-of door reads only the lap-N row.
**Why:** The door must never touch a row it is not allowed to show; a stored cutoff means it does not need to.
**Alternatives rejected:** Query-time minimum (reads other cars' future rows).
**Consequences:** `f1si.data.derive.derive_lap_cutoffs` has property tests on the loader-written cache: at every cutoff exactly one car has just completed lap N and everyone has completed lap N-1.
**Refs:** D-01, DAT-03

## DEC-009 — RACE_END cutoff for whole-race views

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The stint plot needs every driver's full race. Under DEC-001 a "final lap" cutoff would hide each non-winner's last lap, because the leader finishes first.
**Decision:** The same as-of door accepts `RACE_END`, meaning no time filter for race R. Results stay hidden (DEC-003). The stint plot uses it.
**Why:** The plot gets no private path around the guard; it uses the same door and the same checks as everything else.
**Alternatives rejected:** A "final lap" cutoff (drops laps). A private plotting query (a back door around the guard).
**Consequences:** `RACE_END` is a view of a race that is over, so it is for reporting and plots; strategy code that simulates a live lap uses a lap number.
**Refs:** D-16, D-03

## DEC-010 — Column provenance and pre-race facts

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A column is only safe to store on a row if it was knowable when that row became visible; one careless column (for example "final position" on a lap row) would leak the future through the door.
**Decision:** Every time-indexed table carries `visible_at_s`, and a column may be stored only if it is knowable at its row's `visible_at_s`. Pre-race facts live in `entries` and are visible from lap 0: driver number, three-letter code, Jolpica driver id, name, team, `grid_position` (NULL means pit-lane start), `pit_lane_start`, `start_compound` and `start_tyre_age`. The grid lives in `entries`, not in `results`.
**Why:** The grid is known before the lights go out, so it belongs with the roster; the result is not, so it stays in `results`.
**Alternatives rejected:** Grid in the results table (it would be hidden from strategy code that is entitled to it).
**Consequences:** Adding a column to a time-indexed table requires checking its provenance, and any future source must obey the same rule.
**Refs:** D-03, D-07, DAT-03

## DEC-011 — Storage: DuckDB, one transaction per race

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The cache must be a single local file, fast to query, safe to re-run, and easy to hand to NumPy and pandas.
**Decision:** DuckDB, pinned `>=1.5.6,<2` (2.0.0 shipped 2026-10-21 and 1.x cannot read its files; wait for the first patch release). Times are stored as DOUBLE seconds from lights-out (INTERVAL is awkward in NumPy). One transaction per race: delete the race's old rows, `INSERT BY NAME` the new ones, and write the `races` row last as the completion marker. No PRIMARY KEY constraints; uniqueness is validated in code and tests. Only `f1si.data._db` imports duckdb. One data folder holds one source.
**Why:** A per-race transaction means a crash leaves either the old complete race or nothing. PRIMARY KEY indexes cost memory and write time on large tables.
**Alternatives rejected:** Parquet files per race (no transactions). SQLite (a SQLite file is also a back door the import ban has to block).
**Consequences:** Upgrading to DuckDB 2 needs a re-load or a migration and a new log entry.
**Refs:** D-14, DAT-01

## DEC-012 — pandas stays below 3

**Date:** 2026-10-22
**Status:** Accepted
**Context:** pandas 3 is current, but the optional future FastF1 source (DEC-005) constrains it.
**Decision:** `pandas>=2.3.3,<3` and `pandas-stubs>=2.3.3,<3`.
**Why:** FastF1 3.8.3 and 3.9.0a0 require `pandas<3` (FastF1 issue #944); staying below 3 keeps an authenticated FastF1 source possible.
**Alternatives rejected:** pandas 3 now (rules out FastF1 until it catches up).
**Consequences:** Revisit when FastF1 supports pandas 3.
**Refs:** FND-01

## DEC-013 — Seed convention

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Results must be reproducible by seed, and random streams must not overlap by accident.
**Decision:** `f1si.rng.make_rng(seed)` is the only generator constructor. Library functions take a keyword-only `rng: np.random.Generator` with no default. Independent streams come from `Generator.spawn` (adjacent integer seeds can correlate). Ruff `NPY002` plus the AST ban forbid `RandomState`, `np.random.seed`, stdlib `random`, and `default_rng` or bit generators outside `f1si.rng`. `DEFAULT_SEED = 20230305`.
**Why:** A function with no default `rng` cannot silently fall back to global state, and a single constructor is a single place to audit.
**Alternatives rejected:** Global seeding with `np.random.seed` (hidden shared state). A default `rng=None` that builds its own generator (silent irreproducibility).
**Consequences:** Every test that needs randomness passes a generator explicitly.
**Refs:** FND-03

## DEC-014 — Lint tooling pins

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Local pre-commit and CI must agree on lint results, or code passes on one and fails on the other.
**Decision:** `ruff==0.17.1` in the dev dependency group and the ruff-pre-commit `rev: v0.17.1` are bumped together. Pre-commit runs `ruff check --fix` then `ruff format` on each commit; mypy and pytest run in CI.
**Why:** Exact pins make the two ruff copies identical.
**Alternatives rejected:** A version range for ruff (formatting changes between releases would fail CI unexpectedly).
**Consequences:** Upgrading ruff means editing two files in one commit.
**Refs:** D-13

## DEC-015 — The CLI chooses the data source

**Date:** 2026-10-22
**Status:** Accepted
**Context:** RESEARCH's Architectural Responsibility Map says `f1si.cli` must not import duckdb or sources directly.
**Decision:** Keep the SKELETON.md design: `f1si.cli` constructs `SyntheticSource` (and, from plan 01-08, `OpenF1Source`) from `--source` and passes it to `load_races`. duckdb stays banned in the CLI.
**Why:** The CLI is the program's composition root, and a registry module for two sources adds indirection without adding protection.
**Alternatives rejected:** A `f1si.data.sources` registry keyed by name.
**Consequences:** The import-ban POLICY allows `f1si.data.sources.openf1` only from `f1si.cli`. The deviation from the responsibility map is deliberate and recorded here.
**Refs:** D-08, D-14

## DEC-016 — Cache lock errors are recognised by their text

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A second process opening a DuckDB file that another process is writing fails with a `duckdb.IOException`, and we want a friendly message instead of a traceback.
**Decision:** `f1si.data._db` maps an `IOException` to `CacheBusyError` when its text, compared case-insensitively, contains "lock", "being used by another process" or "already open". A missing file raises `CacheMissingError(path)` ("No cache found at PATH. Run: uv run f1si load"); `CacheBusyError()` takes no arguments.
**Why:** DuckDB has no dedicated lock exception. On Windows the text reads "The process cannot access the file because it is being used by another process. File is already open in ... python.exe"; on Linux "Could not set lock on file ... Conflicting lock is held". Both contain one of the phrases.
**Alternatives rejected:** Catching every `IOException` as busy (hides real disk errors).
**Consequences:** The Linux wording is only exercised by CI's ubuntu job, which runs the same subprocess test (green in plan 01-03). A DuckDB wording change would show up as a failing test.
**Refs:** D-14, DAT-01

## DEC-017 — write_race refuses a partial race

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A race is marked complete by its `races` row; a race with a table missing must never carry that marker.
**Decision:** `_db.write_race` requires every table in `schema.PER_RACE_TABLES` and raises `ValueError` otherwise. Adding a table to the schema therefore requires the loader to supply it.
**Why:** A strict write makes "complete" mean "has every table".
**Alternatives rejected:** Writing whatever was supplied (silent half-races).
**Consequences:** Plan 01-04 added the derived `lap_cutoffs` table; the loader supplies it (DEC-028).
**Refs:** DAT-01

## DEC-018 — Stored visibility is always recomputed

**Date:** 2026-10-22
**Status:** Accepted
**Context:** `visible_at_s` decides what the as-of door shows, so a value that disagrees with its row's time would leak or hide data.
**Decision:** `schema.normalize` fills `visible_at_s` from the row's time column when a source omits it, and the `_db` write paths always recompute it from the time column.
**Why:** Stored visibility can then never disagree with the data, whatever a source supplied.
**Alternatives rejected:** Trusting the source's `visible_at_s` (a buggy source could leak the future).
**Consequences:** Sources do not own visibility; the schema does.
**Refs:** D-01, D-03

## DEC-019 — Views are stored as SELECT bodies

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The `stints` and `pit_stops` views are derived from `laps`, and the schema module must stay free of the duckdb import.
**Decision:** `schema.VIEWS` stores the SELECT text; `_db.ensure_schema` wraps each in `CREATE OR REPLACE VIEW`.
**Why:** The schema module stays pure data, and only the storage module executes SQL.
**Alternatives rejected:** DDL strings with CREATE VIEW in the schema (couples the schema to a statement form).
**Consequences:** Changing a view definition takes effect the next time any command opens the cache.
**Refs:** D-14

## DEC-020 — Prose folders are excluded from ruff; data folders are anchored in .gitignore

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Ruff 0.17 formats code blocks inside Markdown, so `ruff format --check .` failed on planning and design documents. Separately, the unanchored `.gitignore` pattern `data/` also ignored the source package `src/f1si/data` and `tests/data`.
**Decision:** `extend-exclude = [".planning", "F1 Docs"]` under `[tool.ruff]`. The `.gitignore` patterns are anchored to the repo root (`/data/`, `/reports/`).
**Why:** Those folders are prose, not code. Anchored patterns ignore only the real cache and report folders.
**Alternatives rejected:** Disabling Markdown formatting globally (the project's own docs might want it). Renaming the data package.
**Consequences:** New top-level folders of generated output need an anchored ignore line.
**Refs:** D-13

## DEC-021 — One random stream per synthetic race

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A synthetic race should come out the same no matter how many other races are generated beside it.
**Decision:** `generate_dataset` calls `rng.spawn(n)` and gives each race its own child generator.
**Why:** Independent streams keep races reproducible one by one, and spawn is the documented way to get non-overlapping streams (DEC-013).
**Alternatives rejected:** One shared generator consumed in order (adding a race would change every later race).
**Consequences:** Tests can generate a single race and get the same values as in the full dataset.
**Refs:** FND-03, D-09

## DEC-022 — Synthetic noise is drawn up front, in a fixed order

**Date:** 2026-10-22
**Status:** Accepted
**Context:** If the amount of randomness consumed depended on events in the race (pit stops, retirements), changing one parameter would reshuffle every other random value.
**Decision:** Lap noise is drawn up front as an `(n_drivers, n_laps)` array, driver-major, so stream consumption per race is fixed. Weather noise is drawn after all lap noise, so adding weather did not change any lap time.
**Why:** A fixed draw order keeps older tests and recorded values stable when the generator grows.
**Alternatives rejected:** Drawing noise lap by lap inside the loop (consumption depends on the path).
**Consequences:** New random features must be drawn after the existing ones.
**Refs:** FND-03, D-09

## DEC-023 — The synthetic generator exposes its ground truth

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Every model must be tested by recovering known parameters (project constraint), which needs the truth next to the data.
**Decision:** `generate_race` returns a `SyntheticRace` whose `truth` field is a `SyntheticTruth` carrying the true base lap time, pace offsets, fuel effect, wear rates, noise, pit loss, pit laps and VSC laps (`pit_laps` maps driver number to a tuple of stop laps, empty for a driver who retires before a stop). The lap-time model equation is in the `generator.py` docstring, and truth fields are named so recovery tests can read them directly.
**Why:** Later phases compare fitted values with the truth without re-deriving it.
**Alternatives rejected:** Hiding the parameters inside the generator (each test would need to re-implement it).
**Consequences:** Changing the lap-time model means updating the docstring equation and the truth fields together.
**Refs:** FND-02, D-09

## DEC-024 — The catalog returns calendar facts only

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The `f1si races` command and the loader need to list races without going through the as-of door.
**Decision:** `asof.catalog()` returns calendar facts only (race id, season, round, slug, event name, circuit, era, out-of-sample flag, source, load status), never results. Plan 01-07 adds the as-of door proper in the same module.
**Why:** Calendar facts are public before the race and cannot leak an outcome.
**Alternatives rejected:** Letting the CLI query the `races` table directly (a second path to the storage layer).
**Consequences:** Anything beyond calendar facts must go through the doors.
**Refs:** D-03, DAT-05

## DEC-025 — Actions are pinned to exact tags when no floating major tag exists

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The first CI run failed at job setup because `astral-sh/setup-uv@v10` does not exist: that action publishes exact release tags only.
**Decision:** Pin `astral-sh/setup-uv@v10.3.1`. Actions that do publish a floating major tag (such as `actions/checkout@v7`) use it.
**Why:** An exact tag is the only reference that resolves, and it is reproducible.
**Alternatives rejected:** Pinning to a branch (moves under us).
**Consequences:** Bumping setup-uv is a manual edit.
**Refs:** D-11

## DEC-026 — Per-lap track status is a string of codes

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A lap can span several track conditions (green, then VSC, then green), and the lap row must still be knowable at its `visible_at_s` (the lap end).
**Decision:** `laps.track_status` is the ordered string of status codes active from lap start to lap end, with consecutive duplicates removed (for example "1" or "167"). A lap whose start or end is NA gets NA; with no status rows at all the answer is "1". Only status rows with `t_s <= lap_end_s` are used.
**Why:** The string is complete for the lap and uses only information available at the lap's end.
**Alternatives rejected:** The worst status in the lap (loses the order). The status at lap start (misses mid-lap events).
**Consequences:** Models that want "was there a safety car this lap" test for the codes inside the string.
**Refs:** D-07, DAT-03

## DEC-027 — Track status codes are a closed set

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Track status comes from different sources with different vocabularies.
**Decision:** Codes are restricted to {1 green, 2 yellow, 4 safety car, 5 red, 6 VSC deployed, 7 VSC ending}. `validate_race` rejects any other code, so the mapping from race-control messages (plan 01-06) must produce only these.
**Why:** A closed set means every downstream model can enumerate the states.
**Alternatives rejected:** Free-text status (each consumer would parse it differently).
**Consequences:** A new state (for example a double yellow flag distinction) needs a schema change and a log entry.
**Refs:** D-07, D-08

## DEC-028 — Derived tables are not supplied by sources

**Date:** 2026-10-22
**Status:** Accepted
**Context:** `lap_cutoffs` (DEC-008) is computed from laps, not downloaded.
**Decision:** The table is marked `derived=True` in the schema. Sources do not supply it and `validate_race` does not require it, but `write_race` still requires it (DEC-017), so the loader must supply it.
**Why:** Derived data cannot disagree with its source data if only one place builds it.
**Alternatives rejected:** Making each source compute its own cutoffs (duplicated logic, risk of drift).
**Consequences:** Source-agnostic derivation lives in `f1si.data.derive`.
**Refs:** D-01, DAT-03

## DEC-029 — Loader failure policy

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A full load takes many requests, and one bad race should not throw the others away.
**Decision:** The loader validates a whole race before writing anything, and invalid source data becomes a failure for that race. Per-race failures (any `Exception`, including invalid data and a schedule-listing `SourceError`) are collected and the run continues, printing a "Failed races:" list and exiting with code 2. `CacheBusyError`, `MixedSourceError`, `UnknownEraError`, `KeyboardInterrupt` and `SystemExit` propagate, because they fail every race or mean stop.
**Why:** The user asked for a list of failed races instead of a crash on the first failure (D-14).
**Alternatives rejected:** Raising on the first failure (loses the rest of the run). Swallowing every exception (hides whole-run problems).
**Consequences:** The loader returns a `LoadReport` and the CLI only returns its exit code.
**Refs:** D-14, DAT-01

## DEC-030 — Rate-limit waiting

**Date:** 2026-10-22
**Status:** Accepted
**Context:** OpenF1 and Jolpica answer HTTP 429 when asked too fast (DEC-005).
**Decision:** On `RateLimitedError` the loader waits `max(retry_after_s, 60 s)` through an injected `sleep`, trying each race up to `max_attempts` times (default 3). After the last attempt the race fails with "rate limited by SOURCE; run the same command again later".
**Why:** Waiting a full minute matches the per-minute limits; injecting the sleep means tests never wait.
**Alternatives rejected:** Exponential backoff from one second (hammers a limit that resets per minute).
**Consequences:** A big first load may take a while; resuming (DEC-031) makes interrupting it safe.
**Refs:** D-14, D-08

## DEC-031 — Resume by completion marker

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A long load may be interrupted; the user expects to run the same command again.
**Decision:** A race is skipped when `races.load_status = 'complete'` in the cache, checked once at the start of the run. Re-running retries only missing or failed races, and prints "skipped (cached)" for the others.
**Why:** The `races` row is written last in the same transaction as the data (DEC-011), so it is a trustworthy marker.
**Alternatives rejected:** Checking for rows in each table (slow, and a half-written race would look present).
**Consequences:** To force a re-download, delete the race (or the cache folder).
**Refs:** D-14

## DEC-032 — Mixing sources is refused

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Synthetic and real races in one cache would silently contaminate any analysis.
**Decision:** `load_races` raises `MixedSourceError` before any network call when the cache holds races from a different `races.source`.
**Why:** Failing before the first request wastes no quota and no time.
**Alternatives rejected:** Warning and continuing (the mixed cache would still exist).
**Consequences:** Use a different data folder for a different source (`--data-dir`).
**Refs:** D-09, D-14

## DEC-033 — `--only` matches schedule ids and slugs only

**Date:** 2026-10-22
**Status:** Accepted
**Context:** `f1si load --only` takes user text, which must never reach SQL or file paths.
**Decision:** Values are compared with the race ids and slugs from the source's schedule and nothing else. An unmatched value becomes a failure ("not found in the schedule for seasons ...").
**Why:** Comparing, not interpolating, removes injection and path-traversal risk (T-01-15).
**Alternatives rejected:** Treating `--only` as a pattern or path.
**Consequences:** Only races in the chosen seasons can be selected.
**Refs:** D-14

## DEC-034 — Synthetic weather and safety-car events

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The synthetic dataset must contain track status, race control and weather so the whole record can be tested without the network.
**Decision:** Weather is sampled every 60 s. Synthetic virtual-safety-car events are: "6" at the earliest lap-start plus 1 s, "7" at the latest lap-end minus 1 s, "1" 12 s later, around lap 8 of the synthetic race `alpha-2023`. Race control has a pre-race green and a chequered flag.
**Why:** The events are deterministic, so tests can assert on them exactly.
**Alternatives rejected:** Random events (assertions would depend on a seed).
**Consequences:** A recovery test for the safety-car rate (Phase 3) will need a generator with random events built on the same pattern.
**Refs:** D-07, D-09

## DEC-035 — UnknownEraError carries the season

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The CLI should say "Season X has no regulation era defined" without parsing an exception message.
**Decision:** `UnknownEraError` has a `season` attribute; the message text is unchanged. The CLI words its own message: "Season X has no regulation era defined (supported seasons: 2022-2026, see f1si/eras.py)" and exits 1.
**Why:** An attribute is stable; message parsing is not.
**Alternatives rejected:** Regex on the message.
**Consequences:** Other exceptions the CLI reports in its own words should carry their facts as attributes too.
**Refs:** DAT-05

## DEC-036 — HTTP pacing, caching and retries

**Date:** 2026-10-22
**Status:** Accepted
**Context:** OpenF1 and Jolpica are free services with rate limits, and a full multi-season load makes hundreds of calls. Our traffic must respect the limits, and a re-run must not repeat calls.
**Decision:** Every call goes through one `RateLimitedClient`. OpenF1 calls are at least 2.1 s apart (below the 30 per minute limit). Jolpica calls are at least 0.5 s apart and at most 450 per rolling hour (limits are 4 per second burst and 500 per hour). Only real network calls are paced or counted; cache hits are free. HTTP 429 is retried up to four times (the `Retry-After` header if numeric, capped at 3600 s, else 5/15/45/90 s) and then raises `RateLimitedError`; the loader then waits at least 60 s and retries the race, up to 3 attempts. HTTP 5xx is retried twice (5 s, 15 s). Network errors become a single-line `SourceError`; HTTP 404 returns `None`. Responses are cached in SQLite through requests-cache with the JSON serializer (never pickle) under `data/http-cache`; only HTTP 200 is stored; race responses never expire and schedules expire after 12 h.
**Why:** Spacing and a cache keep us inside the terms of service, and the JSON serializer means a restored or swapped cache file cannot execute code.
**Alternatives rejected:** Pacing at the stated limit with no margin (a clock drift or a second process would trip it). A pickle cache (code execution risk). No cache (a re-run would repeat every call).
**Consequences:** The first load of a race takes about 15 s (about 7 paced calls). Re-runs are served from the cache. The hourly Jolpica budget is the limit that matters for a full multi-season load, and the loader's rate-limit wait handles it.
**Refs:** D-08, D-14

## DEC-037 — One network door

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Look-ahead and licensing risks both grow with the number of places that can reach the network.
**Decision:** `requests` and `requests_cache` are imported only in `f1si/data/sources/_http.py`, enforced by the import-ban `POLICY`. The adapters depend on the small `JsonGetter` protocol, so tests supply a fake and run offline. `f1si.data.sources.openf1` may be imported only by `f1si.cli`, and `jolpica` only by `openf1`.
**Why:** One door means one place for pacing, retries and caching, and unit tests never touch the network.
**Alternatives rejected:** Each adapter creating its own session (duplicated pacing, untestable offline).
**Consequences:** A new source reuses `RateLimitedClient` or adds its own entry to the policy table.
**Refs:** D-08, D-02

## DEC-038 — Track status derived from OpenF1 race control

**Date:** 2026-10-22
**Status:** Accepted
**Context:** OpenF1 has no track-status feed like the official timing system's, but the model needs green, yellow, safety car, virtual safety car and red flag periods.
**Decision:** `derive_track_status` rebuilds the timeline from race-control messages. "VIRTUAL SAFETY CAR DEPLOYED" gives 6. "VIRTUAL SAFETY CAR ENDING" gives 7, which returns to 1 at the next Track GREEN or CLEAR flag, or 15 s later, whichever comes first. "SAFETY CAR DEPLOYED" gives 4. "SAFETY CAR IN THIS LAP" returns to 1 at the leader's next lap completion (the first leader lap end strictly after the message), unless a Track GREEN or CLEAR comes first. A RED flag gives 5, ended by a Track GREEN or CLEAR or by a safety car or virtual safety car restart. YELLOW and DOUBLE YELLOW give 2 while any sector yellow is active. Flag messages containing "PIT EXIT" and driver-scope flags are ignored. When several things are true at once the priority is 5 > 4 > 6 > 7 > 2 > 1. The timeline starts implicitly green, so the first row appears at the first change.
**Why:** The mapping uses only messages that exist at the time they are sent, so the timeline is knowable at each row's time. The leader's lap end for "in this lap" is the best available signal for when the field is released.
**Alternatives rejected:** FastF1's native track status (a separate source with its own terms; kept as a later optional source). Guessing safety car end times from lap-time changes (a model, not a rule).
**Consequences:** Lower fidelity than the official feed. The 15 s virtual-safety-car ending delay and the leader-lap-end timing are assumptions. On Bahrain 2023 the mapping gives a virtual safety car around lap 41, as expected.
**Refs:** D-07, D-08

## DEC-039 — Jolpica payloads are untrusted

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Third-party JSON enters the cache; a missing field or wrong type must not become a silent wrong value.
**Decision:** Every Jolpica and OpenF1 payload is shape-validated. Integers come only from `int()` of the API's strings and numbers from `float()`; anything else raises `SourceError("Unexpected response from SERVICE for PATH: WHAT")`. After normalizing, the loader validates the whole race before any write.
**Why:** A loud failure with a path and a reason is easier to fix than a bad number found in a model later, and a failed race is simply retried on the next run.
**Alternatives rejected:** Best-effort parsing with defaults (hides upstream changes).
**Consequences:** An upstream format change fails the affected races with a clear message instead of corrupting the cache.
**Refs:** D-07, D-08

## DEC-040 — Snapshots are plain data

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The as-of door returns what was knowable at a lap; consumers must not be able to reach the door itself and ask for more.
**Decision:** The door returns a `RaceSnapshot`, a plain data object. The accessor stays with the replay or backtest driver, and consumers receive snapshots, never the accessor.
**Why:** A consumer without the accessor cannot ask for a later lap, so the look-ahead question is decided in one place.
**Alternatives rejected:** Passing the accessor into models (any model could probe later laps).
**Consequences:** Phase 2's `RaceState` is built from a snapshot. The driver code is the only place that advances the cutoff.
**Refs:** D-02, DAT-04

## DEC-041 — The door accessors are small and separate

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The as-of, results and 2026 doors must stay independent so that the import ban can allow each one to different callers.
**Decision:** `AsOfAccessor` has exactly two methods and no flags. `ResultsAccessor` and `OutOfSampleAccessor` are separate modules guarded by the import ban. `results.py` and `out_of_sample.py` each carry their own small final-classification query, so `results` does not import `_snapshot` and `out_of_sample` does not import `results` (both are import-policy rules).
**Why:** A small duplicated query is cheaper than a shared module that would let one door reach another.
**Alternatives rejected:** One accessor with flags for results and 2026 (a flag can be set by accident).
**Consequences:** The classification query exists twice and must be changed in both places if the results table changes.
**Refs:** D-02, D-03, D-04

## DEC-042 — Cars at a cutoff: leader N laps, others at most N-1

**Date:** 2026-10-22
**Status:** Accepted
**Context:** DEC-001 defines the cutoff as the leader completing lap N, so the snapshot must say how many laps each car has done at that moment.
**Decision:** At lap N the leader has N laps and every other running car at most N-1. `cars.laps_done` (not `laps_completed`) and `position` are rebuilt from the visible laps, ranked by laps done descending and then last lap end ascending.
**Why:** Rebuilding from visible rows means the position is exactly what a timing screen would show, with no information from after the cutoff.
**Alternatives rejected:** Taking the final classification position (a post-race fact).
**Consequences:** Models see lapped cars as slightly behind their true state, never ahead. Phase 2's `RaceState` carries a per-car laps count.
**Refs:** D-01, DAT-03

## DEC-043 — Stint and pit event rebuild

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A snapshot shows stints and pit stops, but the end of a stint or the length of a stop is only known once the next lap is visible.
**Decision:** Stints expose compound, first_lap, last_visible_lap, laps_so_far and tyre_life_now, with no stint end or length. Pit events are the visible out-laps after lap 1; a lap-1 out-lap (a pit-lane start) is not a stop.
**Why:** Every field is knowable at the cutoff. A stint end appears only when the next stint's first lap becomes visible.
**Alternatives rejected:** Including the planned stint length (not known in the data, and a leak if taken from the full race).
**Consequences:** A pit stop appears one lap after the in-lap, when its out-lap becomes visible.
**Refs:** D-01, DAT-03

## DEC-044 — History: complete earlier races, results included

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A strategy model trained for race R may learn from earlier races, but not from R or later ones.
**Decision:** History is every race of an earlier round in the same season or an earlier season, with `load_status = 'complete'` and not out-of-sample, and it includes all tables including results. `races` in a history result is a list of race ids.
**Why:** Earlier races are finished facts when the current race starts. Excluding 2026 keeps the holdout locked.
**Alternatives rejected:** Excluding results from history (the walk-forward needs earlier outcomes to fit models).
**Consequences:** Round order, not date, decides "earlier"; a race renumbered by the calendar would change history.
**Refs:** D-03, D-04

## DEC-045 — Scramble rules for the future-scramble test

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The scramble property test must change exactly what is future at the cutoff and nothing else.
**Decision:** Future means later races, current-race rows with `visible_at_s` NULL or after the cutoff, and the current race's results. At `RACE_END` the current race's time tables are not scrambled, dropped or added, because `RACE_END` has no time filter. `RACE_END` stays in the hypothesis strategy and is also tested deterministically. The harness changes the time column and `visible_at_s` together, because the writer recomputes visibility (DEC-018). Calendar rows of later races are scrambled too, but `races` rows are never dropped, so "next race" lookups through the catalog stay stable for the meta-test.
**Why:** The rules mirror the visibility rule of DEC-001 exactly, so any difference in output is a leak.
**Alternatives rejected:** Scrambling everything (would break the output even for a correct door).
**Consequences:** A new time-indexed table must be added to the scramble tables or the tests fail.
**Refs:** D-02, DAT-04

## DEC-046 — Unknown race and lap errors

**Date:** 2026-10-22
**Status:** Accepted
**Context:** A mistyped slug or lap should produce a message that tells the user what to do, not a stack trace.
**Decision:** An unknown race raises `UnknownRaceError` with up to 3 close slug or race id matches. A lap beyond the race raises `LapOutOfRangeError` suggesting `RACE_END`. The CLI can use `resolve_slug` for slug arguments.
**Why:** The error carries its facts as attributes, so callers do not parse messages.
**Alternatives rejected:** Returning an empty snapshot (silently wrong).
**Consequences:** DEC-002 records the known limit that asking for a lap beyond the race reveals the race length.
**Refs:** D-02, DAT-04

## DEC-047 — Race calendar and identity

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Round numbers renumber when a race is cancelled or added, and an event name is not a circuit: the 2026 "Bahrain Grand Prix" is held at Kuala Lumpur.
**Decision:** Only Race sessions are loaded (not sprints, qualifying or practice). Sessions that OpenF1 marks `is_cancelled`, and races that started less than 6 h ago, are skipped. The round comes from the Jolpica schedule, matched by UTC start date within one day (the closest wins). `race_id` is `{season}-{round:02d}`. The slug comes from the Jolpica race name, with `-r{round}` added when two races in a season share a slug. The circuit is the Jolpica `circuitId`. A session with no matching Jolpica round is skipped with a message. `scheduled_laps` is left empty for Phase 2.
**Why:** Matching by date to one schedule gives one stable identity per race; the circuit id is the only reliable circuit key.
**Alternatives rejected:** Using OpenF1's meeting name as the circuit (an event is not a circuit). Filling scheduled laps from the winner's lap count (a post-race fact).
**Consequences:** A race that is moved by more than a day between the two services would be skipped with a message rather than mislabelled.
**Refs:** D-05, D-06

## DEC-048 — OpenF1 lap clock and tyre fields

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The schema's time is seconds since lights out, but OpenF1 timestamps are wall-clock, and its stints are one row per stint rather than one per lap.
**Decision:** t = 0 is the earliest lap-1 `date_start` of any car, which is lights out (checked on Bahrain 2023 only; assumption A14). Lap end is lap start plus lap duration, or the same driver's next lap start when the duration is missing. A lap-1 row with no start gets 0.0. `tyre_life` is `tyre_age_at_start` plus the laps into the stint plus 1, and a stint with no end extends to the driver's last lap. Pit-out laps come from OpenF1, pit-in laps from the Jolpica stop laps, and the stop duration is placed on the out-lap. Race control and weather are on the same clock, so messages before lights out have negative times. Pit-lane starts follow the "Pit-lane start rule" entry. `scheduled_laps` stays NULL.
**Why:** Using the car that starts the first lap earliest gives a clock tied to the real start; every derived number is then reproducible from the raw payloads.
**Alternatives rejected:** The session start time as t = 0 (it is before the formation lap). Jolpica lap times (not available per lap in the free API).
**Consequences:** A few laps keep gaps that OpenF1 does not fill: on Bahrain 2023 three in-laps have no end time and no stint. Those rows are only visible at the race end.
**Refs:** D-01, D-08

## DEC-049 — Pit-lane start rule

**Date:** 2026-10-22
**Status:** Accepted
**Context:** `entries.pit_lane_start` says which cars started from the pit lane. Entries are visible from lap 0 (lights out), so every column must be knowable at lights out.
**Decision:** `pit_lane_start` is true when the Jolpica grid is 0 and the status, lower-cased and stripped, is none of "Did not start", "Withdrew", "Did not qualify" or "Did not prequalify". `grid_position` is NULL for grid 0. Laps completed is never used.
**Why:** The earlier draft rule "grid 0 and laps > 0" used a post-race fact and was look-ahead: a pit-lane starter that retires on lap 1 has 0 laps but did start. Whether a car never took the start is settled by lights out.
**Alternatives rejected:** Grid 0 and laps > 0 (look-ahead). Grid 0 alone (marks non-starters as pit-lane starters).
**Consequences:** Limitation: the status string is published in the post-race results feed and Jolpica has no separate pre-race signal, so only its "the car never took the start" meaning is used. A non-starter labelled with some other status would be marked as a pit-lane starter with no laps, which stays visible in the cache. Plan 01-10 checked every grid-0 entry in the full 2023-2026 load: 4 entries in 4 races (three pit-lane starters whose statuses were "Finished", "Collision damage" and "Lapped", and one non-starter, "Withdrew" with 0 laps, correctly marked false), so the rule held on all real cases and the never-started set did not change. Bahrain 2023 has no grid-0 entries.
**Refs:** D-01, D-03

## DEC-050 — Stint plot conventions

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The Phase 1 plot shows lap time by stint for a whole race (DAT-02). It must stay inside the look-ahead rules and stay readable when pit laps and safety-car laps are 20 s or more slower than racing laps.
**Decision:** The plot draws with the matplotlib `Figure` API, never `pyplot`. There is one panel per driver, ordered by grid position (pit-lane starters last); final results are never read. Laps are faded to alpha 0.25 rather than removed when they are lap 1, a pit in-lap, a pit out-lap or have track status 4, 5, 6 or 7. The y-range comes from clean laps only: minimum minus 0.5 s up to the 98th percentile plus 1.0 s. A point outside the range is drawn on the panel edge with a "^" marker. Thin dotted stint-boundary markers (one at half a lap before each stint's first lap) keep consecutive stints on the same compound apart. An empty snapshot (lap 0) gives an empty plot with y-range (0, 1) and "no laps yet" in each panel. Compound colours are SOFT #da291c, MEDIUM #ffd12e, HARD #f0f0ec, INTERMEDIATE #43b02a, WET #0067ad, unknown grey, with dark marker edges because HARD is near-white. The plot reads a `RACE_END` snapshot through the as-of door, and the output file name comes from the catalog slug and validated driver codes, never from the raw command argument. The data preparation is registered as a consumer in the future-scramble test.
**Why:** Faded laps keep the true race on screen while the tyre-wear trend (lap time drifting up inside a stint) stands out. A range from all laps would be flattened by pit and safety-car laps. Clipping with a marker means nothing is hidden. Sharing the as-of door, with a pure data step, lets CI prove the plot cannot see beyond a cutoff.
**Alternatives rejected:** Dropping slow laps (hides what happened). Ordering panels by finishing position (reads results, which is look-ahead for a replay). `pyplot` (global figure state, needs a backend). A y-range from all laps (flat trend).
**Consequences:** Laps with no lap time (three pit in-laps on Bahrain 2023, where OpenF1 gives no lap end) are skipped, not drawn, and counted in the command's output line; a lap with a time but no compound is drawn in grey. Stint boundaries come from the visible stint rows only, so an in-lap without a stint row does not move a boundary.
**Refs:** D-15, D-16, DAT-02

## DEC-051 — A plain-language explainer for every phase, kept complete by a test

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The owner is new to coding and must be able to explain every module in an interview (BUILD_PLAN risk "Interviewers probe a module you can't explain"). An explainer written once goes stale as files are added.
**Decision:** Each phase ends with `docs/explained/phase-NN.md` in the public repo with five sections: what was built and why, how the pieces connect, a file-by-file tour, 3-5 interview questions with answers, and good-to-know caveats. `tests/test_docs.py` checks that the headings exist in order, that every Q has an answer, that every `src/f1si` module path appears in the tour, and that the README links the explainer and the decision log. A short plain-language summary is also shown in chat at the end of the phase.
**Why:** A test that lists the module paths makes a new file without an explanation fail the build instead of being forgotten.
**Alternatives rejected:** A docs generator from docstrings (reads as reference, not explanation). A checklist with no test (drifts).
**Consequences:** Adding a module to `src/f1si` requires a paragraph in the current phase explainer, or a new phase explainer plus a change to the test.
**Refs:** D-17, UI-03

## DEC-052 — The import ban judges private modules by identity, not by the path they were reached through

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The code review (CR-01) showed that `from f1si.data.asof import _db` gave any module a raw-SQL handle on the whole cache, because the scan matched only the exact names `f1si.data._db` and `f1si.data._snapshot`, and the modules that import them (asof, loader) re-exported them as attributes. The same review noted gaps in the scan of random-number constructors and SQL engines (WR-11).
**Decision:** (1) The scan canonicalises every dotted `f1si` path that passes through a component named `_db` or `_snapshot` to the home path `f1si.data._db` / `f1si.data._snapshot` before it applies the policy, so it no longer matters which module re-exports them. (2) It flags the attribute `x._db` / `x._snapshot` on any object, `getattr(x, "_db")`, a full dotted chain such as `f1si.data._db`, and a string literal that spells a protected `f1si` path (`sys.modules["f1si.data._db"]`). A star import yields every protected name below the module. (3) The door and loader modules (`asof`, `loader`, `results`, `out_of_sample`) import `_db` and `_snapshot` inside the functions that use them, so the names are not module attributes; a runtime test walks every public `f1si` module and fails if any attribute is a private storage module, `duckdb` or `sqlite3`. (4) The scan covers the whole `src/` tree. It adds `PCG64DXSM`, `BitGenerator` and `SeedSequence`, an alias of `numpy.random` (`from numpy import random as r; r.seed(1)`), `polars`, `ibis`, `sqlalchemy` and `pandas.read_sql*`. (5) A second planted fixture, `tests/fixtures/leaky_reexport.py`, leaks through `_db` without naming duckdb. The meta-test requires it to be flagged by the scan and to fail at runtime. The CI canary copies both fixtures into `src/f1si` one after the other and greps the pytest output for the expected violation, so a collection or import error cannot pass for "caught".
**Why:** Two independent layers (static identity check, no runtime attribute) mean that a future refactor that re-adds a top-level `from f1si.data import _db` still fails the scan, and a scan blind spot still fails at runtime.
**Alternatives rejected:** Renaming the imported module (`_db as _storage`) in the doors: the scan would then have to guess aliases. Matching only the full path: the original bug.
**Consequences:** The scan is still static. A computed module name (`getattr(m, name)`, `importlib.import_module(var)`) is not seen; the future-scramble test is the second line. Function-local imports in four modules are deliberate and carry a comment.
**Refs:** D-02, D-03, D-04, DAT-04
