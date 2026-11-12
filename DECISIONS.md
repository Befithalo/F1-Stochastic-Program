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
**Status:** Accepted; the rule was changed by DEC-056 (the status string is no longer used). The limitation below still applies.
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

## DEC-053 — The scramble harness refuses a consumer that raises, and registration is enforced

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The code review found that `assert_no_lookahead` compared the outcomes of the two runs, so a consumer that raised the same exception on both databases (a typo, a locked 2026 race, a broken registration) passed while exercising nothing (WR-01). It also found that coverage depended on a hand-kept registry, on any module being able to build `AsOfAccessor` and `RACE_END`, and on 20 randomly sampled combinations (WR-02).
**Decision:** (1) The run on the original data must succeed. A raise there fails the test with `ConsumerFailed`. A deliberate error case names the exception type with `expect_error`, the original run must raise exactly that type, and the scrambled run must raise the same type with the same message. The locked 2026 race is tested this way for the snapshot and history consumers. (2) The import scan allows `AsOfAccessor`, `RACE_END` and `RaceEnd` only in `f1si.data.asof`, `f1si.cli`, `f1si.backtest` and `f1si.replay`, so model and plot code receives snapshots and cannot ask for another lap. (3) `tests/guards/test_consumer_registry.py` lists every public function and method of the designated consumer modules (`f1si.data.asof`, `f1si.plots.stints`); each must be consumed by a registered consumer or exempt with a written reason, and stale entries fail too. (4) A deterministic test runs every consumer at every lap 0..n_laps and RACE_END of every in-sample synthetic race, with a seed that depends only on the race and lap. The Hypothesis test stays, with its `just(RACE_END)` branch, as extra random exploration. All consumers of one race and lap share one scrambled database.
**Why:** A guard that can pass vacuously is worse than no guard. A deterministic grid makes CI repeatable, and the registry test turns a convention into a failing test.
**Alternatives rejected:** Treating a raise as "equal outputs" (the bug). Lowering the grid to a few edge laps (a lap-specific leak in one race would be found only by luck).
**Consequences:** The full grid adds about 40 scramble setups to the guard tests. A new public function in a designated module, or a new consumer module, needs a registry entry before CI is green. The designated-module list in `tests/guards/consumers.py` is still maintained by hand, but a module that uses the accessor without being a driver now fails the import scan.
**Refs:** D-02, D-04, DAT-04

## DEC-054 — One read connection per snapshot, history or results call

**Date:** 2026-10-22
**Status:** Accepted
**Context:** `build_snapshot` opened about eight separate read-only DuckDB connections. A concurrent `f1si load` could take the write lock between them and re-load a race (delete, then insert), so one snapshot could mix a `lap_cutoffs` row of the old load with `laps` of the new one, or fail half-way with `CacheBusyError`. Opening a file per query also cost about 40 ms each (WR-04).
**Decision:** Each door call (`snapshot`, `history`, `final_classification`) opens one read-only connection with `_db.connect_reader` and passes it to every query through an optional `con=` argument of `_db.read_df` and `_db.read_table`. The doors call `_snapshot.guarded_snapshot` / `guarded_history`, which look up the race, run the door's own check (2026 locked, or in-sample refused) and build the result on that connection. The type is exported as `_db.Connection` so only `_db` imports duckdb. A test counts the connections each door call opens.
**Why:** DuckDB does not let another process write while a read-only connection is open, so the whole call sees one load of the cache or fails once with `CacheBusyError`, never a mixture. It is also several times faster.
**Alternatives rejected:** An explicit read transaction (the file lock already gives the guarantee, and a transaction would not stop a writer in another process). A connection pool or a long-lived accessor connection (a Windows file lock would outlive the call, see DEC-010).
**Consequences:** A `f1si load` started while a snapshot is being built waits or reports a busy cache for the length of that call, which is short. The deterministic scramble grid became about twice as fast.
**Refs:** D-01, D-02

## DEC-055 — Bad lap end times are dropped and reported before cutoffs are derived

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Lap cutoffs are the leader's lap-end times followed by a reverse cumulative minimum (DEC-008). That repair is safe for look-ahead because it only moves a cutoff earlier, but one wrong `lap_end_s` (the review used 100 s on lap 10 of one car) pulled the cutoffs of laps 2 to 10 down to it, so every snapshot in that range hid nearly all rows and nothing warned the user (WR-03). The real cache has such a value: 2024 round 4 holds `-1327.2 s` as driver 22's lap 2 end.
**Decision:** The loader runs `derive.sanitize_lap_ends` before it derives anything. An end is dropped (set to NA) if it is not finite, below 0 or above 6 hours, or if it is outside one longest strictly increasing run of that driver's ends ordered by lap number. A dropped end makes its lap visible only at the race end, as for any lap without an end. The loader prints a `note:` line for each race that needed it, with driver, lap and value. If more than 10% of a race's ends have to be dropped it fails the race as corrupt instead. What the reverse cumulative minimum still repairs can only come from a leader whose own lap end is missing; `derive.cutoff_repairs` lists those laps and the loader reports them in a note.
**Why:** Dropping the offending value keeps the other 71 of 72 laps of a race instead of losing a whole race for one glitch, and the longest increasing run drops the outlier in either direction (too early or too late) without a tuned threshold. Nothing can become visible earlier than before, so the look-ahead property is untouched.
**Alternatives rejected:** Rejecting any race with one bad end (it would reject 2024 round 4). A median-based outlier filter (needs a threshold). Failing when the raw leader minimum decreases (that happens legitimately when a leader has a gap, and the repair is safe).
**Consequences:** `f1si load` shows a note for 2024 round 4 when it is reloaded; the cached copy keeps the glitch until that race is loaded again. Laps whose end was dropped keep their other columns, but have no `visible_at_s`.
**Refs:** D-01, D-14

## DEC-056 — Entries use only start facts: pit-lane start from the lap-1 record, start tyre from stint 1

**Date:** 2026-10-22
**Status:** Accepted
**Context:** `entries` is visible from lap 0, and the future-scramble test deliberately leaves the current race's entries alone, so no guard can catch a post-race value there. The review (WR-06) found two. `pit_lane_start` used the final Jolpica status, so any unlisted post-race status turned a grid-0 non-starter into a pit-lane starter. `start_compound` took the lowest stint number among stints with a `lap_start`, so with stint 1 missing it reported the tyre after the first stop.
**Decision:** `pit_lane_start` is true when the Jolpica grid is 0 and OpenF1 has a lap-1 timing record for the car; the status and laps completed are not read at all. `start_compound` and `start_tyre_age` come only from OpenF1 stint number 1, which counts when its `lap_start` is null or 1. When that stint is absent, or says it began after lap 1, both stay NULL and the source prints a `note:` line naming the drivers. A test changes everything after lap 1 and every post-race result field and requires identical entries.
**Why:** A car with no timing record never left the pit lane or the grid, whatever its final status says, and a lap-1 record exists for a car that starts from the pit lane and retires at once. Checked on the cached real data: all 3 pit-lane starters have a lap-1 record, the 1 non-starter has none. A NULL start tyre is honest; the second stint is not the start tyre.
**Alternatives rejected:** The lap-1 `is_pit_out_lap` flag (it is false for all 3 real pit-lane starters). Keeping the status check as a second filter (it keeps a post-race input for no gain). Adding a flag column (a schema change for one rare case; the note and the NULL carry the information).
**Consequences:** Honest limit: neither feed has a signal published before lights out for a pit-lane start (no qualifying or penalty data in Phase 1, D-06). The lap-1 record appears during lap 1, so `pit_lane_start` is a start fact that is observed one lap late, not strictly a pre-race value. Models should treat it as known from lap 1, and a later phase with qualifying data can replace it. One real driver (2023 session 9693, driver 30) has a stint 1 with no `lap_start` and now gets the right tyre.
**Refs:** D-01, D-06, DEC-049

## DEC-057 — Pit flags come from one source, and a lap with a duration but no start keeps its end

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The review (WR-08) found two gaps in the OpenF1 laps. (1) A lap with a `lap_duration` but no `date_start` (not lap 1) got no start and so no end, so it was visible only at the race end and `laps_done` and `position` were undercounted. (2) `is_pit_in_lap` came from the Jolpica stop list but `is_pit_out_lap`, and so every rebuilt stop, came from OpenF1, so the two flags could disagree. The reviewer suggested requiring a matching in-lap before counting a stop.
**Decision:** (1) A lap with no `date_start` starts where the same driver's previous lap ended (chained when several are missing), so its end is start plus duration. (2) `is_pit_out_lap` stays OpenF1's flag; `is_pit_in_lap` is now the lap before an out-lap after lap 1, so the flags agree by construction and a stop rebuilt from visible laps always has its in-lap. Jolpica's stop list now supplies only the duration, placed on the lap after its stop lap as before. A pit-lane start (a lap-1 out-lap) is still not a stop.
**Why:** The real cache (87 races) was checked. OpenF1 out-laps and Jolpica in-laps agree everywhere except two Miami 2025 stops whose in-lap row is absent from OpenF1 and all 32 stops of Australia 2026, where Jolpica's stop lap equals OpenF1's out-lap. Requiring a matching in-lap would have dropped those 34 real stops, so it was rejected. Red-flag restarts (for example Australia 2023) show no extra out-laps in the data, so the feared false stops did not occur; a pit-lane exit under a red flag that OpenF1 does flag would count as a stop with no duration, which is what a tyre change under a red flag is.
**Alternatives rejected:** Requiring a matching Jolpica in-lap (loses real stops, see above). Using Jolpica for both flags (loses stops whose lap row is absent). Leaving the lap end empty (hides the lap until the race end).
**Consequences:** `is_pit_in_lap` for the 32 Australia 2026 stops moves from the out-lap to the lap before it; that race is locked and out-of-sample, so nothing in Phase 1 reads it. Jolpica pit durations in that race are placed one lap late and stay unused until the 2026 convention is understood. Cached races keep their old flags until reloaded.
**Refs:** D-01, D-08, DEC-048

## DEC-058 — Recent or incomplete races are not cached forever

**Date:** 2026-10-22
**Status:** Accepted
**Context:** Every timing and results response was cached with no expiry. The schedule accepts a race six hours after it started, OpenF1 backfills laps, stints and weather after a session, and Jolpica results change with post-race penalties. A partial or provisional HTTP 200 was therefore kept for good, the incompleteness message said "It will be retried on the next run" although the retry replayed the same body, and the CI cache key was a fixed string that `actions/cache` never overwrites (WR-05).
**Decision:** (1) The OpenF1 and Jolpica calls of a race use the 12-hour `short` expiry when the race is in the current season or started less than 7 days ago; older races of finished seasons stay `forever`. (2) `JsonGetter` gains `forget(path, params)`, which removes one cached request. When a race fails the completeness check, `OpenF1Source` forgets all of its cached responses (five OpenF1 paths, the Jolpica results and every pit-stop page) before it raises, and the message now says the saved responses were discarded. The loader also calls an optional `discard_cached(ref)` hook on a source for any `SourceError` from validation (including DEC-055's corrupt-clock failure), so the next run asks the services again. (3) The weekly real-data workflow keys its cache by run id and restores the newest older entry by prefix.
**Why:** A provisional body is wrong only for a while, so a short expiry fixes it without re-downloading finished seasons. Forgetting a failed race makes "run the same command again" true.
**Alternatives rejected:** Never caching races younger than a month (it spends rate limit on every re-run). Clearing the whole cache on a failure (loses the finished races). Leaving the CI key static (the first cached body would be used for ever).
**Consequences:** The current season's races (2026) are fetched again after 12 hours if they are loaded again. The weekly real-data run still replays cached Bahrain 2023 bodies, so it checks the code more than the live service.
**Refs:** D-08, D-10, D-14

## DEC-059 — The Jolpica hourly budget survives the process

**Date:** 2026-10-22
**Status:** Accepted
**Context:** The rolling limit of 450 real calls per hour lived in an in-memory deque. The loader tells the user to run the same command again after a rate limit or a failure, and every re-run started with an empty window, so several quick re-runs could exceed Jolpica's 500 per hour (WR-09).
**Decision:** A client with an hourly limit records the wall-clock time of each real network call in a JSON file beside its cache (`jolpica.calls.json`), by read, merge, drop entries older than an hour and atomic replace. At start-up it seeds its window from the entries younger than an hour, converting their age to its monotonic pacing clock. Responses served from the cache are not recorded. An unreadable or unwritable file is ignored. The OpenF1 client has no hourly limit and writes no file.
**Why:** Plain JSON keeps the import ban on `sqlite3` absolute, and a few hundred timestamps need nothing more.
**Alternatives rejected:** A table in `jolpica.sqlite` (would need an exception to the `sqlite3` ban). Seeding from the `created_at` of cached responses (calls that returned 429 or 5xx, and forgotten races, would not be counted).
**Consequences:** Two loads running at the same moment can still lose an entry in the file; the loader refuses a busy cache, so this is unlikely. Setting the system clock back can make an entry look younger than it is, which only makes the client wait longer.
**Refs:** D-08, D-14

## DEC-060 — An empty cache lists nothing, and only real lock messages mean "busy"

**Date:** 2026-10-22
**Status:** Accepted
**Context:** `f1si races` crashed with a `TypeError` on a cache file that had the schema but no finished race (WR-07). The storage layer reported any DuckDB `IOException` whose text contained "lock" as a busy cache, and "block" contains "lock", so a corrupt file ("computed checksum of block ...") or a short read told the user to wait for another command that did not exist (WR-10).
**Decision:** `f1si races` on an empty cache prints "No races cached yet. Run: uv run f1si load" and exits 0. `_db` treats an `IOException` as a busy cache only when its text contains one of "could not set lock", "conflicting lock", "being used by another process" or "already open"; anything else is raised as it is. Tests cover the three real lock messages and four messages that must not match.
**Why:** A traceback tells a new user nothing, and a wrong "busy" message hides corruption.
**Alternatives rejected:** A word-boundary match on "lock" (still matches "unlocked block"-like text and other future messages). Exit code 1 for an empty cache (it is a valid state, not an error; a missing cache file still exits 1).
**Consequences:** If a future DuckDB version rewords its lock message, a busy cache would surface as the raw error until the phrase list is extended; the process-level lock test in `test_db_roundtrip.py` would catch that.
**Refs:** D-14

## DEC-061 — Plug-in interface signatures

**Date:** 2026-11-11
**Status:** Accepted
**Context:** Phases 3 to 8 plug pace models, strategy policies and simulators into the platform. Their signatures must be fixed now so later phases add implementations without changing callers (D-10, D-11).
**Decision:** `PaceModel.predict` is keyword-only and vectorised over int64 `driver` (the driver number, the stable database key; the three-letter code stays in `RaceState`), str `compound`, int64 `tire_age` (laps on the tyres at the end of the lap) and int64 `lap` (1-based); it returns `(mean_s, sd_s)` as float64 arrays of the input shape and never samples (D-09). `StrategyPolicy.decide(state, *, driver)` has no rng parameter: the optimizer is deterministic, and a Phase 5 policy takes its rng in its constructor. `SimulatorBackend.simulate(state, *, n_races, rng, plans=None)` returns a `SimulationResult` with `finish_positions` (n_races, n_cars) and `total_time_s`; the shape is provisional (Phase 3 may add fields, not change these two). `Plan` and `PitDecision` are frozen value types validated in `__post_init__`. The Protocols are `runtime_checkable`, which checks method names only (outcome A1 confirmed: a class with the right name and a wrong signature passes `isinstance`), so the behaviour suites in `tests/conformance` carry the weight. Rejection of wrong signatures is proven by mypy itself: `tests/conformance/test_protocols.py` passes wrong stubs with `# type: ignore[arg-type]`, and strict mode reports an unused ignore if the stub were accepted (outcome A2 confirmed: removing one ignore makes `mypy` fail). `interfaces.py` imports `RaceState` only under `TYPE_CHECKING` (with `from __future__ import annotations`), keeping interfaces, state and pace.linear free of import cycles; `tests/test_import_order.py` guards it.
**Why:** Integer driver keys vectorise cleanly and match the database. Keeping rng out of `decide` keeps the free-track optimizer a pure function. Behaviour suites catch what name checks cannot.
**Alternatives rejected:** Passing a driver code string array to `predict` (slow, not numeric). An rng argument on `decide` (no use in a deterministic optimizer). Importing `RaceState` at run time (cycle risk once state.py imports pace.linear).
**Consequences:** A Monte Carlo policy that needs randomness must hold its own generator. Every new implementation is one registry entry in `tests/conformance/registry.py`.
**Refs:** D-09, D-10, D-11

## DEC-062 — RaceState layout, JSON and placeholders

**Date:** 2026-11-11
**Status:** Accepted
**Context:** Policies and simulators share one description of the race at one lap. The BUILD_PLAN fixes its JSON shape, and D-12 forbids breaking changes later.
**Decision:** `CarState` and `RaceState` are frozen dataclasses with tuples and read-only `MappingProxyType` mappings. The JSON keys equal the BUILD_PLAN shape plus one additive key, `driver_number`. Unknown values are `None`, never NaN, and `to_json` uses `allow_nan=False` (D-23); non-finite floats are rejected when a car is built, and `from_json` rejects NaN constants, unknown keys and bool-as-int. `regime = {"green": 1.0}` and a `pit_loss_s` with only the "green" key are placeholders until Phases 3 and 8 (D-13), and the module docstring says so. The `PaceModel` is injected into the optimizer at construction, so no per-compound rate map is added to the schema (D-10, D-12). `to_arrays()` gives a read-only struct-of-arrays view (NaN, -1 or "" for None) for Phase 3.
**Why:** Frozen plain data cannot be changed behind a caller's back, and exact JSON round trip makes states storable and testable. None is honest about unknowns where NaN hides them.
**Alternatives rejected:** NaN for unknowns (silently propagates and is invalid JSON). Putting a per-compound wear map in the state (the schema would change whenever a model changes).
**Consequences:** Later phases fill the placeholders without touching the field set. A new field needs a new additive key and a DECISIONS entry.
**Refs:** D-12, D-13, D-23

## DEC-063 — Joint OLS fuel and wear fit

**Date:** 2026-11-11
**Status:** Accepted
**Context:** PAC-01 asks for tyre wear in seconds per lap after removing the lighter-car effect. Fuel and wear separate only because tyre age resets at a stop while the lap number keeps rising (D-01).
**Decision:** One ordinary least squares fit over clean laps, `t = alpha_d + fuel*(L-1) + wear[c]*age + eps`, solved with `numpy.linalg.lstsq`, with classical standard errors `sqrt(diag(s2 (X'X)^-1))` and a normal 1.96 interval because SciPy is not installed. It needs residual degrees of freedom of at least 30. An SVD rank and condition check (`COND_LIMIT` 1e8) names the parameters that cannot be separated and the fit then reports no number for them; the minimum-norm answer is never used. A compound needs `MIN_CLEAN_LAPS_PER_COMPOUND` 30 clean laps from at least `MIN_STINTS_PER_COMPOUND` 2 stints, a driver needs `MIN_DRIVER_LAPS` 5 laps. Heteroskedasticity-robust standard errors are not used: HC3 differed by under 15% from the classical ones at Bahrain 2023.
**Why:** A silent minimum-norm answer would look like a measurement. The refusal makes the limits of the data visible (D-03), and the wear slope SE feeds `RaceState` `wear_sd` (D-04).
**Alternatives rejected:** A fixed fuel constant from the literature (hides the data). Robust SEs (no material change). A mixed-effects model (more machinery, same point estimates).
**Consequences:** Before the first stop the CLI says "not enough laps yet" rather than printing a number. A 95% interval from a normal quantile is slightly narrow when residual degrees of freedom are near 30.
**Refs:** D-01, D-03, D-04

## DEC-064 — Clean laps are what the plot fades

**Date:** 2026-11-11
**Status:** Accepted
**Context:** The stint plot already fades lap 1, pit in-laps, pit out-laps and laps under a safety car, VSC or red flag. The fit must not disagree with what the user sees.
**Decision:** The rule lives once in `f1si/laps.py` (`fade_reason`, `slow_status`, `FADE_TRACK_CODES`) and both the plot and the fit import it. Yellow flags (code "2") are not dropped, which overrides the word "yellow" in D-02 (D-22). After a first solve, laps with a residual more than `MAD_K` = 3 robust standard deviations (1.4826 * MAD) from the median are trimmed, for up to 5 passes, and the design matrix is rebuilt from scratch every pass. The fit reports how many laps were dropped and why.
**Why:** One rule cannot drift between the picture and the numbers. Rebuilding the design every pass keeps compounds and drivers that fall under their minimum from staying in by accident.
**Alternatives rejected:** A separate cleaning rule in the fit (can drift). Dropping yellow laps (removes many ordinary laps). A single trim pass (a large outlier can mask a smaller one).
**Consequences:** `fade_reason` checks pit reasons before track status, so it cannot separate green from slow stops; pit loss uses `slow_status` directly.
**Refs:** D-02, D-22, DEC-050

## DEC-065 — No compound pace offset; fuel reported as measured

**Date:** 2026-11-11
**Status:** Accepted
**Context:** A fresh hard tyre may be slower than a fresh soft at age zero. Measured at Bahrain 2023, the wear slopes were SOFT 0.125 and HARD 0.121 s/lap, and a HARD offset came out at +0.26 s with standard error 0.13 s: weakly identified. The fuel estimate was -0.078 s/lap, outside the usual -0.06 to -0.03 range.
**Decision:** No compound pace offset is modeled and the wear output says so: compound choice among near-ties is not meaningful (D-19). An additive compound-offset term is the named Phase 7 candidate. Fuel is reported as measured and never clamped; when it lies outside the literature range the output says it likely also absorbs track evolution (D-25).
**Why:** A weakly identified extra term would widen every interval and shift wear, while clamping fuel would hide a real signal.
**Alternatives rejected:** Fitting the offset now (SE half the estimate). Clamping fuel to the literature range (silently wrong).
**Consequences:** Wear slopes are within-stint degradation only; the optimizer inherits the caveat.
**Refs:** D-19, D-25

## DEC-066 — Pit loss measured from in-laps and out-laps

**Date:** 2026-11-11
**Status:** Accepted
**Context:** The optimizer needs a cost of stopping. The pit lane time alone misses the slow in-lap and out-lap.
**Decision:** For each visible stop, loss = (in-lap + out-lap time) minus the fit's clean prediction for the same two laps. The estimate is the median with a 10-90% range. Only green-flag stops count: a stop where either lap has a safety car, VSC or red code (`slow_status`) is excluded and counted. With no usable stop, or an unidentified fit, `DEFAULT_PIT_LOSS_S` = 22.0 s is returned and flagged as a default. At Bahrain 2023 the median measured about 24 to 25 s.
**Why:** The median resists the odd slow stop, and the spread shows how uncertain the cost is.
**Alternatives rejected:** The mean (pulled by slow stops). Pit-lane duration from timing data (leaves out the lap-time cost). A fixed constant (not measured).
**Consequences:** The default is a placeholder that is always labeled as such.
**Refs:** D-05

## DEC-067 — RaceState builder rules and laps_total

**Date:** 2026-11-11
**Status:** Accepted
**Context:** Simulators and policies need one trusted state object at any lap, and model code must not hold the as-of accessor. `races.scheduled_laps` is NULL for all 87 cached races because the OpenF1 adapter hard-codes None.
**Decision:** One pure builder, `build_race_state(snapshot, fit, *, laps_total, pit_loss_s)`, turns a `RaceSnapshot` and a `LinearPaceFit` into a `RaceState`. It is typed to `LinearPaceFit` because the `PaceModel` Protocol exposes only `predict`, while the builder needs per-compound rate and SE; Phases 4 and 7 will fill the same fields from their own estimators. `laps_total` is an explicit keyword argument, supplied by the CLI from the race-end maximum lap as public pre-race knowledge; fixing the adapter is the named follow-up (D-21). Position and gap are None when unknown. The gap to the car ahead is the time gap on the last lap both cars completed; it is None for the leader, when laps done differ by more than 1 (lapped), when a lap end is missing, or when the computed gap is <= 0 because the car ahead finished that lap later or together (position swaps in timing data) (D-14, D-23). The lap-0 state uses the entry's start compound and start tyre age; `tire_age` means laps already on the tyres.
**Why:** It keeps the accessor out of model code and the schema stable, and an approximate gap that says None beats an invented or negative one.
**Alternatives rejected:** `scheduled_laps` from the adapter now (touches Phase 1 code, scramble tests and a cache reload). The maximum lap of the cutoff snapshot (equals the cutoff, wrong).
**Consequences:** A red-flag-shortened race would have a smaller race distance than scheduled; Bahrain 2023 is unaffected. Import-cycle rule: `interfaces.py` imports `RaceState` only under TYPE_CHECKING, `pace.linear` never imports `f1si.state`, and a fresh-subprocess test covers both import orders.
**Refs:** D-12, D-13, D-14, D-21, D-23, DEC-042

## DEC-068 — Free-track plan rules and conventions

**Date:** 2026-11-11
**Status:** Accepted
**Context:** PAC-02 needs the fastest 1- or 2-stop plan for one driver, and Phase 5 will reuse the optimizer as its baseline policy. The plan rules, lap convention and pricing method must be fixed so results are comparable and testable.
**Decision:** State at lap N means N laps completed and a plan covers laps N+1 to the race end. A stop at lap k means lap k is the in-lap and lap k+1 is the out-lap on fresh tyres of age 1; "pit now" is k = N+1. A plan is legal when it has 1 or 2 total stops (stops already made count), uses at least two different dry compounds counting those already used, keeps the running tyre and its age fixed, gives every new stint and the final stint at least 5 laps (the running stint is exempt), and fits only compounds that have a fitted wear rate. Every legal plan is enumerated, a few thousand at lap 0 of a 57-lap race with two compounds. Each plan is priced by calling `PaceModel.predict` and taking prefix sums (one call per compound for fresh stints, one for the running stint), so any model plugs in; the optimizer never reads closed-form parameters, and a slow lap-by-lap reference is checked against it with hypothesis. The `PaceModel` is injected at construction. Total time is the predicted clean laps plus `pit_loss_s["green"]` per new stop. Ties break on total time rounded to 1e-9, then fewer stops, then earlier stop laps, then compound names. The optimizer refuses, with a message saying what to do next, for wet or intermediate tyres, an unknown or unfitted current compound, a finished race, and no legal plan.
**Why:** Brute force over a few thousand plans is exact and cheap, and the prefix sums keep pricing model-agnostic. Fixed tie-breaks make output reproducible.
**Alternatives rejected:** Closed-form optimum from wear slopes (ties the optimizer to one model). Dynamic programming (not needed at this size). Allowing three or more stops (outside the stated scope).
**Consequences:** Free track means no traffic, overtaking or safety cars, so the result is a lower bound, and compound choice among near-ties is not meaningful because pace offsets are not modeled.
**Refs:** D-05, D-06, D-07, D-10, D-19

## DEC-069 — Plan cutoff policy and analytic ground truth

**Date:** 2026-11-11
**Status:** Accepted
**Context:** A plan can be made from data visible at a lap, or with hindsight from the whole race. The optimizer also needs a ground truth that the synthetic generator cannot give, because it makes exactly one stop per driver.
**Decision:** With `--lap N` the fit, pit loss, state and default leader come from the snapshot at N only; the command refuses at N = 0 or when the fit is not identified (about N <= 9 at Bahrain 2023), and says which lap to try. Without `--lap` it applies a whole-race fit to the lap-0 state and labels the output as a hindsight plan with no claim of foresight (refines D-07's "pre-race plan"); it also refuses a driver who ran on wet or intermediate tyres, read from the race-end stints. The default driver is the leader of the shown snapshot, never read from final results. Optimizer ground truth is a hand-built analytic case with known slopes and pit loss: with equal slopes the one-stop optimum is lap n/2, and with a small pit loss the two-stop optimum is n/3 and 2n/3; the generator is unchanged. The line about the real strategy is worded "compared against" and never "beats".
**Why:** The hindsight label keeps look-ahead honest and visible, and an analytic optimum can be checked by hand.
**Alternatives rejected:** A generator change to make multi-stop races (D-24 forbids it). A silent pre-race fit that uses future laps. Wording such as "beats", which would imply the model proves the team wrong.
**Consequences:** Mid-race plans need enough laps for the fit; the hindsight mode reads only the race-end data for the fit and the actual strategy.
**Refs:** D-08, D-16, D-20, D-24

## DEC-070 — Laps with no stint number are dropped, not merged into stint 0

**Date:** 2026-11-12
**Status:** Accepted
**Context:** Code review WR-03. `_classify` filled a missing stint with 0, so every such lap of a driver became one invented stint. That could satisfy or fail `MIN_STINTS_PER_COMPOUND` on fabricated identities and made `CompoundFit.n_stints` wrong.
**Decision:** A lap with a lap time, a dry compound and a tyre age but no stint number is dropped with the reason "no stint", shown in `report.dropped`. Stint identity is only ever a real stint number.
**Why:** The stint count gates which compounds are fitted and is reported to the user; an invented stint is a made-up fact. Dropping loses a few laps at worst, and the reason is visible.
**Alternatives rejected:** Keeping `fillna(0)` (fabricates stints). Inferring the stint from pit events (a second source of truth that can disagree; no real case needs it, Bahrain 2023 and the synthetic generator always carry a stint).
**Consequences:** Data with no stint column at all fits nothing and says "no stint" in the dropped counts. Order of drop reasons: lap time, fade or status, compound or age, stint, wet.
**Refs:** D-01, D-03, D-25

## DEC-071 — Coefficient covariance from the SVD; condition limit 1e6

**Date:** 2026-11-12
**Status:** Accepted
**Context:** Code review WR-02. Standard errors came from `inv(X'X)`, while the identification check allowed cond(X) up to 1e8, so cond(X'X) could reach 1e16 and the inverse could be meaningless or raise `LinAlgError` although the fit promises never to raise on shortage.
**Decision:** The covariance is `s^2 V diag(1/S^2) V'` from the thin SVD `X = U S V'` that the identification check already computes, so no inverse is formed. `COND_LIMIT` drops from 1e8 to 1e6, which keeps cond(X'X) = cond(X)^2 at or below 1e12, about four digits above double-precision breakdown. An SVD that fails to converge returns an unidentified fit with a message. The point estimates are unchanged (still `lstsq`).
**Why:** The SVD route is the stable way to get (X'X)^-1 and costs nothing extra; a tighter limit makes "identified" mean "the standard errors are numerically reliable".
**Alternatives rejected:** Keeping `inv` and catching `LinAlgError` (still unreliable below the error threshold). A pseudo-inverse with a cutoff (a silent minimum-norm answer, which the fit forbids). Ridge (biases the wear and fuel numbers).
**Consequences:** A design with condition number between 1e6 and 1e8 that was reported before is now reported as unidentified. Real Bahrain 2023 and the synthetic races sit far below 1e6, so their numbers are unchanged. Supersedes the 1e8 value in the module docstring only; no earlier DEC pinned it.
**Refs:** D-01, D-03, D-04

## DEC-072 — Residual variance corrected for the 3-MAD trimming

**Date:** 2026-11-12
**Status:** Accepted
**Context:** Code review WR-04. Up to five passes of re-fit and trim at 3 robust sigma cut the tails of the residuals, and the final `s^2 = RSS / (n - p)` was taken on the trimmed sample as if it were complete. That understates the noise: on 40 synthetic races with Gaussian noise of 0.15 s the reported `sigma_s` averaged 2.7% low, against 1.2% low with no trimming at all (the remaining 1.2% is a property of the generator and the fit, not of trimming). `sigma_s` is the predictive spread and the wear SE fills `wear_sd`, so both were too small.
**Decision:** When any lap was trimmed, `sigma_s` is the root of `sigma^2 * v(c / sigma) = RSS / (n - p)` where `v(k) = 1 - 2 k phi(k) / (2 Phi(k) - 1)` is the variance of a standard normal cut at +/- k (v(3) = 0.9733) and `c` is the cutoff the last pass applied, or the largest kept deviation if that is larger. The SEs use the same corrected sigma: `cov = sigma^2 (X'X)^-1`. With no trimming nothing changes. Solved by bisection (no new dependency). The trimming rule itself (symmetric, 3 MAD, up to 5 passes) is unchanged; DEC-065 and earlier decisions are not contradicted.
**Why:** It makes the reported spread unbiased under Gaussian noise, which is the honest-uncertainty goal. Inflating the SE as well is deliberately conservative: the trimmed estimator picks its own sample, which the naive formula ignores.
**Alternatives rejected:** The pre-trim robust sigma (MAD of the first-pass residuals), which is biased by the first-pass fit and by contamination. Multiplying by a fixed 1/sqrt(0.9733) (wrong when the iterated cutoff is tighter than 3 sigma). Asymmetric trimming of slow laps only (a behaviour change that needs its own evidence).
**Consequences:** On real Bahrain 2023 (41 laps trimmed, more than a Gaussian would give) sigma_s rises about 3% and wear SEs about 3%. Real data are contaminated by traffic, so the correction assumes the bulk is Gaussian and the trimmed laps are outliers; heavy tails remain a known limit.
**Refs:** D-01, D-04, D-25

## DEC-073 — Each car carries its own completed-lap count; plans start from it

**Date:** 2026-11-12
**Status:** Accepted
**Context:** Code review WR-01. `RaceState.lap` is the leader's completed laps N, but at a cutoff every other car has completed at most N-1 laps (DEC-042), and its `tire_age`, `compound` and `stops_done` describe the state after its own last lap. The optimizer priced laps `state.lap + 1`..L for every car from those values, so a follower's first priced lap had a tyre age one (or more) too low and a fuel index one too high, its own lap N was never priced, and plan totals of different drivers were not comparable. DEC-068 defines the state at lap N as "N laps completed", which holds for the leader only.
**Decision:** `CarState` gets a new field `laps_done: int | None = None` (laps this car has completed; None means `RaceState.lap`), filled by `build_race_state` from the snapshot, and written to and read from JSON as the key `laps_done`. The key is optional when reading, so older JSON loads with None. This deliberately extends the BUILD_PLAN key set pinned by `CAR_KEYS` in `tests/test_state.py`. `RaceState` rejects a `laps_done` above `lap`. `RaceState.laps_done_of(car)` returns the car's own count. `FreeTrackOptimizer` (fast path, `price_plan_slow`, `price_plan`, `decide` and the CLI "laps to plan" line) uses `n = laps_done_of(car)` in place of `state.lap`: laps n+1..L, first tyre age `tire_age + 1`, earliest stop lap n+1, and "pit now" means a stop on the car's own next lap. Every car is priced through `laps_total`, which assumes nobody is lapped (free track), so totals of different drivers are comparable. DEC-068's "state at lap N" is refined, not reversed: N is the car's own laps done.
**Why:** The car's own lap count is the only index at which its tyre age, compound and stops are all true at once. Reading it from the car removes a silent off-by-one from every non-leader plan.
**Alternatives rejected:** Refusing to plan for any car with `laps_done != lap` (loses `--driver X --lap N`, the main mid-race use). Shifting the state to the car's lap by re-deriving tyre age (needs the lap data the state is meant to hide). Making `laps_done` a required field (breaks every hand-built state and older JSON).
**Consequences:** A car that pitted on leader-lap N but whose own lap N is not yet visible still shows the old tyre and `stops_done`; that is the timing data, not a pricing error. For the leader and for hand-built states nothing changes. Real Bahrain 2023 plan numbers for `--lap 0` are unchanged because every car has 0 laps done.
**Refs:** D-12, D-14, D-23, DEC-042, DEC-068

## DEC-074 — scipy, numba and scipy-stubs; the lap kernel is compiled with Numba

**Date:** 2026-11-12
**Status:** Accepted
**Context:** Phase 3 needs scrambled Sobol sampling, normal and beta quantiles, and a simulator that runs 50,000 races in under 10 s. CLAUDE.md names SciPy and Numba in the stack. Numba was flagged by slopcheck only on name similarity to numpy (false positive: 140 releases since 2012, github.com/numba/numba).
**Decision:** Add scipy (Sobol, norm.ppf, beta.ppf), numba (the lap-step kernel only; NumPy does draws and tables) and scipy-stubs (dev, so mypy strict passes). Versions are bounded in pyproject.toml and uv.lock is committed; CI uses `uv sync --locked`.
**Why:** The NumPy-only prototype measured 6.4-7.5 s for 50,000 x 20 x 57 on a fast desktop, too close to the 10 s limit on CI runners; the Numba lap kernel measured 1.7-2.5 s including draws (RESEARCH).
**Alternatives rejected:** Pure NumPy masks (too slow). Cython or Rust (out of stack; Rust is M5). A hand-written Sobol (direction numbers are easy to get wrong).
**Consequences:** The first call compiles (about 1 s, excluded by warm-up in the benchmark). `pytest --cov` cannot trace inside jitted bodies, so a `py_func` equivalence test gives real coverage. Determinism is per environment.
**Refs:** D-13, D-18, SIM-02, SIM-03

## DEC-075 — Safety-car rate: Beta-Binomial on earlier races, edge-rule deployments, fixed median duration

**Date:** 2026-11-12
**Status:** Accepted
**Context:** REG-01 needs a per-lap safety-car probability and a duration that use earlier in-sample races only, and that work for the first race of the history.
**Decision:** The per-lap rate is the Beta-Binomial posterior mean with prior Beta(3, 297) (mean 1%, weight about 300 laps, five races; an assumed literature prior, assumption A3, that only matters for early races), with a 90% interval from `scipy.stats.beta.ppf`. Deployments are counted with an edge rule: a status "4" row after None, "1", "2", "6" or "7" (the cache has 50 naive "4" starts but 44 true deployments across the 70 in-sample races, because 6 SC rows follow red flags). Exposure laps are the maximum lap of `lap_cutoffs` per race with track-status rows. The duration is the lower median of measured lengths (leader laps from deployment to the next non-"4" row; red-flag ends and never-ending SCs excluded) when at least 5 exist, else 4 laps. The measured in-sample median over 39 usable events is 3; the owner-set fallback of 4 is kept. A first race returns the prior alone with `is_prior_only`. VSC and red flags are not modelled and are deferred to Phase 8.
**Why:** A conjugate prior gives an honest interval with a tiny history and no fitting code. The edge rule avoids counting restarts as new events. The denominator is race laps, not non-SC laps; an SC can only start on a green lap, so the hazard is biased low by about 4% of the rate with real data, which is accepted for simplicity.
**Alternatives rejected:** A plain frequency (zero or huge on small history). Non-SC laps as exposure (more exact, but needs per-lap status joins for a 4% effect). A per-circuit rate (too few races per circuit).
**Consequences:** Recovery test: 24 races x 100 laps x 4 drivers with one-lap SCs at a known 2.5% per lap, 5 seeds; the 90% interval contains the truth in 5 of 5 seeds. An earlier design with 40-lap races covered only 3 of 5, because the prior (mean 1%, weight 300 laps) still pulled the posterior down with 920 laps of data; this is shrinkage, not a bug, so the test uses a sample large enough for the prior to matter little. Estimates for real seasons stay prior-heavy until about 10 races are in the history.
**Refs:** D-01, D-02, D-03, D-06

## DEC-076 — Regime at the cutoff, SC laps elapsed and the SC pit-loss placeholder

**Date:** 2026-11-12
**Status:** Accepted
**Context:** The simulator must start from the true situation: a safety car may be out at the cutoff, and a stop under it costs less time. Phase 8 (REG-03) will measure SC pit loss, but success criterion 3 of Phase 3 needs a value now.
**Decision:** `build_race_state` sets `regime = {"sc": 1.0}` only while status "4" is the latest visible track-status row, else `{"green": 1.0}`. `RaceState.sc_laps_elapsed` is a new optional field (default 0, optional JSON key written only when nonzero; precedent DEC-073): the leader laps since the first row of the final run of "4" rows, with leader laps at time t counted as lap numbers whose earliest lap end is at or before t (the same convention as the estimator's lap cutoffs). `pit_loss_s["sc"] = SC_PIT_LOSS_RATIO (0.5) x` the green value, an explicit placeholder until Phase 8. VSC and red flags are not modelled; tyre wear under SC is not reduced.
**Why:** RESEARCH Pitfall 6 offered two options (assume the SC just started, or carry the elapsed laps); carrying the field keeps the lap-31 story exact at the cost of one optional int. The ratio is defined in `f1si.state`, not `f1si.sim`, to avoid an import cycle (DEC-061).
**Alternatives rejected:** Assuming the SC just started (wrong mid-period). Probabilistic regime mixture at the cutoff (the cutoff status is observed, not uncertain). Maximum lap end over drivers as the lap clock (counts the slowest car, so elapsed laps came out one too high).
**Consequences:** A state with no SC differs from before only by the new `pit_loss_s["sc"]` key. Real SC pit loss replaces the ratio in Phase 8.
**Refs:** D-02, D-04, D-05

## DEC-077 — Parameter uncertainty plumbing: offset SE, shared per-compound wear draw

**Date:** 2026-11-12
**Status:** Accepted
**Context:** The simulator samples parameter uncertainty (D-12) and reports diagnostics (D-19); both need plumbing through the fit, the state and the result.
**Decision:** `FitReport.driver_offset_se` (last field, defaulted) holds the standard error of each driver intercept, and `LinearPaceFit.pace_offset_se(number)` returns it, None for an unknown driver. `CarState.pace_offset_sd` is an optional field (optional JSON key) filled from it. This is the SE of the raw intercept, not of the intercept minus the mean intercept; the raw value is the conservative per-driver choice. Per-compound wear SEs reach the simulator through its constructor from `fit.wear_se`. This REFINES D-12: the wear rate is one shared parameter per compound in the fit, so the simulator draws one normal per compound per race (shared by all cars) and one offset normal per car, not an independent wear rate per car (Pitfall 3). Independent draws ignore the fit's covariance between offsets, fuel and wear, a documented simplification. `SimulationResult` keeps `finish_positions` and `total_time_s` first and unchanged and gains defaulted `sc_lap_mask`, `stop_laps`, `pit_loss_paid_s`, `plan_sources`, `diagnostics` and `clock_s`; the conformance suite checks their leading dimensions.
**Why:** Sharing the wear draw across cars reproduces the actual correlation in the fit; independent per-car draws would understate the spread of relative outcomes. Defaulted fields keep every existing backend and stub valid.
**Alternatives rejected:** Independent wear rate per car (wrong correlation). Sampling from the full covariance (needs the covariance in the state; deferred). SE of the mean-centred offset (needs the covariance of the mean).
**Consequences:** Plans 03-03 and 03-04 need no further cross-cutting edits to state, fit or result.
**Refs:** D-12, D-19, WR-02, WR-04

## DEC-078 — Overtaking: dirty-air hold plus logistic pass chance

**Date:** 2026-11-12
**Status:** Accepted
**Context:** The simulator must let cars interact on track (SIM-01) with a rule simple enough to hand-check and cheap enough for 50,000 races.
**Decision:** Cars are processed front to back each green lap. A follower that would arrive less than `MIN_GAP_S` (0.5 s) behind the car ahead either passes or is held at exactly that gap (dirty air). The pass chance is `p = 1 / (1 + exp((THRESHOLD_S - delta) / SCALE_S))` with `delta` the pace gap (ahead's free lap time minus the follower's), `THRESHOLD_S = 0.4`, `SCALE_S = 0.2`. One uniform per car per lap decides it (`pu < p`), so a car gains at most one position per lap by passing. A successful passer pays `PASS_COST_S` (0.3 s) and the passed car is pushed to at least passer plus `MIN_GAP_S`. A car that did not pit moves ahead of a car that pitted this lap deterministically (no chance, no cost). No lapping, blue flags or retirements (D-09). All constants are `[ASSUMED]` engineering defaults (A1) and are fitted per circuit only in Phase 6. Sanity values: p(+2.0 s) > 0.99, p(0) = 0.12, p(-2.0 s) < 0.01, p(0.4 s) = 0.5.
**Why:** A logistic curve is monotone, bounded and has two readable parameters; the hold reproduces the main strategic effect of traffic (undercut value, being stuck behind a slower car) without a car-following model.
**Alternatives rejected:** Always pass when faster (no traffic cost). A fixed time penalty for being close (no chance of escape). A full gap-based Markov passing model (needs data not yet available).
**Consequences:** The first draft used `THRESHOLD_S = 0.3`, `SCALE_S = 0.25`, which gives p(0) = 0.23: equal-pace cars within the dirty-air gap would swap about every fourth lap, against D-08 ("equal pace rarely passes"). The curve was moved, not the test bound, so p(0) < 0.2 holds.
**Refs:** D-07, D-08, D-09

## DEC-079 — Safety-car mechanics in the simulator

**Date:** 2026-11-12
**Status:** Accepted
**Context:** Pit timing is the product, and a safety car changes both the cost of a stop and the field spacing.
**Decision:** A safety car starts only on a green lap, with probability `sc_rate` per lap per race, lasts a fixed `sc_duration` laps, and the whole lap it starts on runs under it. Order is frozen (only pit stops reorder it), and every car's lap time is `SC_SLOWDOWN` (1.4) times the leader's green free time. On the last SC lap the field is compressed to `RESTART_SPACING_S` (1.0 s) between consecutive cars. A stop on an SC lap pays `pit_loss_s["sc"]` (placeholder 0.5 x green until Phase 8) instead of the green loss. On the lap an SC starts (or the first simulated lap when an SC is already active at the cutoff), cars with the opportunistic flag (free-strategy cars, never forced plans) whose next planned stop lies within `SC_STOP_WINDOW_LAPS` (5) laps and whose following stop is at least a minimum stint later take that stop now. Tyre wear under SC is not reduced. VSC and red flags are not modelled.
**Why:** These are the smallest rules that produce the cheap-stop and bunching effects behind SC strategy calls; the 1.4 factor matches the synthetic generator so recovery tests are consistent.
**Alternatives rejected:** Letting a new SC start during an SC (double counting). Reduced tyre wear under SC (no data yet). Restart spacing from real gaps (would need a restart model).
**Consequences:** Constants are `[ASSUMED]` (A2). The kernel does not import the generator.
**Refs:** D-03, D-04, D-11

## DEC-080 — Draw layout: Sobol plus antithetic, per-lap streams, common random numbers

**Date:** 2026-11-12
**Status:** Accepted
**Context:** SIM-03 needs a low-variance estimate and Phase 5 needs plans compared on the same random luck.
**Decision:** `rng.spawn(4)` gives `sc_params`, `passing`, `noise` and a spare stream; `passing.spawn(n_laps)` gives one stream per lap. Low-dimensional blocks (SC start, per-car offset and per-compound wear draws, one `Sobol(d=n_cars)` engine per lap for pass uniforms) use scrambled Sobol with `Sobol(..., rng=child).random_base2(m)`, `m = max(1, ceil(log2(ceil(n/2))))`, first `ceil(n/2)` rows, stacked with their antithetic `1 - u` and trimmed to `n` (odd N is padded and trimmed). Rows `i` and `i + ceil(n/2)` are mirrors across all blocks. High-dimensional per-lap noise uses plain antithetic normals `[e; -e]`, never Sobol (D-13). Every draw is generated unconditionally, in lap order, indexed by (race, car, lap), never conditioned on plans, order or SC state. SciPy's `rng=` keyword is used, not `seed=`; `random_base2` avoids the balance warning for non powers of two. A mode switch (`none`, `antithetic`, `sobol_antithetic`) runs plain MC and variance-reduced draws through one code path. Sobol dimension is bounded by 21,201 and `MAX_RACES`, `MAX_CARS`, `MAX_LAPS` cap input sizes.
**Why:** Sobol points plus antithetic pairing reduce variance for the smooth low-dimensional integrand; plain antithetic normals stay robust in high dimension. Unconditional per-lap streams make common random numbers exact.
**Alternatives rejected:** Sobol over all dimensions (poor quality and a huge engine). A single stream consumed in race order (a forced plan would shift other drivers' draws).
**Consequences:** Plan 03-04 assembles the simulator from these blocks; the variance comparison against plain MC is tested in plan 03-05.
**Refs:** D-13, D-14, D-15, SIM-03

## DEC-081 — Plan resolution for every car, fallback rule, opportunistic SC stops

**Date:** 2026-11-12
**Status:** Accepted
**Context:** The simulator must give every car a pit plan, while a caller (Phase 5) prices a specific plan for one driver and needs exactly that plan simulated.
**Decision:** `resolve_plans` uses a forced plan unchanged (stop laps must lie in `(laps_done, laps_total]`, unknown codes raise the friendly `state.car` error). Every other car gets `FreeTrackOptimizer.rank_plans(state, driver=code)[0]`, computed once per call. Only `PlanRefusedError` is caught; the fallback is one stop at `laps_done + round(remaining / 2)` onto the first fitted compound (sorted) the car has not used, with stints of at least `MIN_STINT_LAPS` on both sides and at most `MAX_TOTAL_STOPS - stops_done` stops, else no stop. Fallback plans carry `Plan.total_time_s = 0.0` because they are not priced. The opportunistic safety-car stop applies only to cars not named in `plans`, so a forced plan is simulated exactly as asked. A safety car already active at the cutoff counts as starting on the first simulated lap. Every car's plan source ("forced", "optimizer", "fallback") and the refusal reason are returned in `plan_sources`.
**Why:** Pricing a plan means simulating that plan, not a version the simulator improved on; a car the optimizer cannot price (unknown or unfitted tyre) still has to race.
**Alternatives rejected:** Letting forced cars also take opportunistic stops (the priced plan would differ from the requested one). A bare `except` (would hide real bugs). Dropping cars the optimizer refuses (breaks the one-column-per-car contract).
**Consequences:** Plan 03-05 may cache the optimizer plans if profiling shows the 20 brute-force calls matter. The fallback ignores the car's pace.
**Refs:** D-10, D-11, D-12

## DEC-082 — Starting a simulation from a real RaceState: catch-up lap, spacing, retired cars, borrowed pace

**Date:** 2026-11-12
**Status:** Accepted
**Context:** Real states are cut at the leader's line crossing: the leader has `lap` laps, others usually `lap - 1`, some cars have retired, and a whole-race fit may lack tyres or drivers (Bahrain 2023 whole-race fit has only HARD and SOFT; PIA retired on lap 13 and is absent from the fit).
**Decision:** Clocks are relative to the leader's line crossing at lap `state.lap`. The leader holds its predicted lap time; the others the cumulative `gap_ahead_s` down the position order, `START_SPACING_S` where a gap is None (cars without a position sort last by number). A follower with `laps_done < lap` runs one noise-free catch-up lap first (age +1, plan stop and pit loss applied, slowed to `SC_SLOWDOWN` times the leader's lap under a cutoff safety car) and the order is re-sorted by clock. A car more than one lap behind (retired or lapped) gets a penalty of the missing laps times the leader's lap time and is then forced behind every other car, with a diagnostics line "driver X: retired or lapped, placed last", so results stay a permutation (D-09). An unknown start tyre is assigned the first fitted compound. Pace is wrapped in `BorrowedPace`: an unfitted compound gets the mean of the fitted compounds' means (max SD), a driver absent from the fit the field-average of the fitted drivers; the pace-offset SD of an absent driver is the standard deviation of the state's `pace_offset_s` values (0 with fewer than two). All substitutions are listed in diagnostics. Inputs are capped (`MAX_RACES`, `MAX_CARS`, `MAX_LAPS`) and validated before the compiled kernel runs.
**Why:** These are the smallest rules that let the simulator start from any real state without refusing cars, and they say loudly when they approximate.
**Alternatives rejected:** Refusing states with unfitted tyres or absent drivers (fails on the first real race). Dropping retired cars (changes the column contract). Per-compound wear differences for unfitted tyres (not identified by the data).
**Consequences:** The borrowed pace for SOFT at Bahrain is an average of HARD and SOFT behaviour, not a measurement; Phase 6 recalibration may replace it. Followers' catch-up lap carries no noise, so their first-lap luck is not simulated.
**Refs:** D-09, D-12, DEC-073

## DEC-083 — Variance reduction: Sobol plus antithetic, measured against plain Monte Carlo

**Date:** 2026-11-12
**Status:** Accepted
**Context:** SIM-03 requires that the variance-reduced sampling is measurably less noisy than plain Monte Carlo at equal N, not just that it is implemented.
**Decision:** The same `NumpySimulator` is run with `variance_reduction` set to `none` and `sobol_antithetic` over R = 120 independent seeds (`make_rng(1000 + s)`), N = 1024 races, on a 10-car, 30-lap trimmed copy of the long synthetic race with cars 0.5 s apart, mixed pace offsets (SD 0.2 s) and a safety-car rate of 0.03 per lap (duration 3). Measured variance ratios var(none)/var(sobol_antithetic) for the car in grid slot 5: mean finishing position 4.54, mean total time 16.43, safety-car share 3.19. The report-only P(top 5) ratio is 4.22. Asserted margins are about 75% of the measured values: 3.4, 12.0 and 2.4. The test also checks that the two arms agree on the mean within 4 standard errors (no bias) and that the whole comparison is deterministic by seed (scipy and numpy versions pinned in uv.lock).
**Why:** R = 120 puts the sampling error of a variance ratio near 13% (R = 40 gives about 30%), so the 75% margins are safe yet still fail if the reduction disappears. A first attempt used the default synthetic grid, where the pace offsets are sorted by grid slot and nobody ever passes: finishing positions were deterministic and the estimator carried no information, so the test state was made contested on purpose.
**Alternatives rejected:** Asserting on P(top 5) (RESEARCH Pitfall 8 expected little gain; here it was 4.22, so it stays report-only because a threshold indicator can change with the model). R = 40 (ratio noise too large).
**Consequences:** The explainer can quote 16x for total time and 3 to 5x for the discrete estimators. The gain depends on the state: with a field that never reshuffles the finishing estimator is constant and the ratio is meaningless.
**Refs:** D-13, D-14, SIM-03

## DEC-084 — Benchmark: 50,000 x 20 x 57 under 10 s with the Numba warm-up excluded

**Date:** 2026-11-12
**Status:** Accepted
**Context:** SIM-02 requires 50,000 simulated races within 10 s; CI runners are slower than the development PC.
**Decision:** `tests/sim/test_benchmark.py` simulates 50,000 races of the full 57-lap, 20-car long synthetic state (default `sobol_antithetic`, safety-car rate 0.01, `record_clocks=False`) after a 64-race warm-up call. Three local timings: 1.45 s, 1.38 s and 1.49 s, so the 10 s budget has about 6x headroom locally. The warm-up is excluded because `cache=True` compiles on the first CI run (about 1 s) and loads from cache afterwards. No `benchmark` marker or skip: the test stays in the default selection on Ubuntu and Windows. The two result arrays take 16 MB each at 50,000 x 20 (the sum is asserted below 40 MB), no per-lap tensors are kept and `clock_s` is None.
**Why:** The warm-up makes first and later CI runs equal; the 10 s limit is never raised, headroom absorbs slower runners.
**Alternatives rejected:** A `benchmark` marker that CI deselects (the gate would not prove SIM-02). Timing the compile (varies with cache state).
**Consequences:** No simulator optimisation was needed in this plan; the 20 optimizer calls per simulate stay uncached.
**Refs:** D-18, SIM-02
