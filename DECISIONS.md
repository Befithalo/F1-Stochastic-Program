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
