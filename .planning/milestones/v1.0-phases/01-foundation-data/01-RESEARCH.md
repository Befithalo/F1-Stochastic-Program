# Phase 1: Foundation & Data - Research

**Researched:** 2026-10-22
**Domain:** Python 3.12 project scaffold (uv, ruff, mypy, pytest, GitHub Actions), F1 timing-data ingestion, DuckDB local store, look-ahead-proof data access, matplotlib reporting
**Confidence:** MEDIUM overall. The scaffold, CI, DuckDB, guard and plot findings are HIGH. The data-source findings are HIGH on the facts but LOW on the path forward, because the source situation changed 7 days ago and needs a user decision.

## Summary

> **DECISION REQUIRED BEFORE THE INGEST PLAN (blocker for success criteria 2 and 3)**
>
> Since **2026-10-15**, every file under `https://livetiming.formula1.com/static/...` returns **HTTP 401** to requests without authentication. FastF1 3.8.3, the current stable release, therefore cannot download timing data into an empty cache. This applies to any season, including 2023. The FastF1 maintainer confirmed on 2026-10-18 that "an F1 TV Access subscription (or higher tier) will be necessary to access their data". The maintainer shipped `fastf1==3.9.0a0`, an alpha described as "quick and dirty", that adds F1 TV sign-in. FastF1's fallback mirror returns 404 for 2023-2026. [VERIFIED: `curl` from this machine returned 401 for Bahrain 2023 `SessionInfo.json` and 404 from the mirror; CITED: github.com/theOehrly/Fast-F1/issues/978, release v3.9.0-a0]
>
> **Locked decision D-08 ("FastF1 only") and D-10 (weekly CI download) both rest on an assumption that is no longer true.** Since D-08 is locked, the planner must ask the user to choose, either with a `checkpoint:decision` before the source-adapter task or by sending the question back to discuss-phase:
> - **Option A — keep FastF1:** `fastf1==3.9.0a0` plus the user's paid F1 TV Access (or higher) account. CI cannot download, so D-10 shrinks to a local-only real-data run.
> - **Option B — OpenF1 + Jolpica (recommended):** both are free, need no account, and were verified working today for Bahrain 2023 and the 2026 races. DAT-01 already says "FastF1/OpenF1", and BUILD_PLAN lists OpenF1 as the "M1 replay feed".
>
> Everything else in this phase is source-agnostic and can be built and turned CI-green first on synthetic data: scaffold, CI, schema, accessor, guards, eras, RNG, plot, DECISIONS.md and the explainer. This fits the walking-skeleton order.

The phase has five parts:

- **A greenfield uv/Python 3.12 package with a two-OS CI.** Linux plus Windows. This part is low-risk.
- **A source adapter.** It turns one race into a set of normalized tables. Its source is the decision above.
- **A single DuckDB module.** Only this module may `import duckdb`. It writes each race in one transaction, so writes are idempotent and the loader can resume.
- **Three read "doors".** The as-of accessor, the results door and the out-of-sample (2026) door. All share one time rule: a row is visible only if its timestamp is at or before the leader's lap-N completion time (D-01).
- **Two CI guards.** An AST-based import ban and a "future-scramble" property test. Each is proven against a planted leaky fixture by a meta-test.

**Five facts the planner must design around:**

1. **Most of lap N is still in the future at cutoff N.** Under D-01, the cutoff for lap N is the moment the leader finishes lap N. Every other car finishes lap N *after* that moment, so at cutoff N only the leader's lap-N row is visible. Every other car shows at most lap N−1. [VERIFIED: OpenF1 Bahrain 2023 data has P2 finishing lap 1 1.25 s after the leader and lap 57 11.95 s after.]
2. **The plot needs an explicit end-of-race cutoff.** At "the final lap", every non-winner's last lap is still invisible. The plot (D-16) therefore needs a `RACE_END` cutoff through the same as-of door.
3. **Future-scramble cannot see leaks baked into stored columns.** Some FastF1 columns are computed with whole-session knowledge: `Deleted`, `DeletedReason` and `IsPersonalBest`. These must be left out of the as-of view.
4. **The cutoff cannot be computed on the fly.** Taking `min(lap_end) WHERE lap = N` reads other cars' future lap-N rows, so the scramble test would flag the accessor itself. The lap→cutoff table must be precomputed at load time.
5. **The FastF1 path depends on pandas < 3.** FastF1 pins `pandas<3` in both 3.8.3 and 3.9.0a0. Use `pandas>=2.3.3,<3` and `pandas-stubs` 2.3.3.x. [VERIFIED: PyPI metadata]

**Primary recommendation:** Build the skeleton in this order: scaffold → synthetic source → DuckDB write/read → as-of accessor → `f1si load --source synthetic` / `f1si plot` → guards → CI green on both OSes. Then add the real source adapter once the user has decided. Default recommendation: OpenF1 for laps, stints, race control and weather; Jolpica for grid, classification and pit stops. Keep the normalized schema source-agnostic so a FastF1 3.9+ adapter can drop in later.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Look-ahead guard (core value of the project)
- **D-01: Cutoff = leader's clock.** "As of race R, lap N" means the session timestamp at which the race leader completes lap N. A row is visible only if its timestamp is at or before that cutoff. This applies to every table: laps, track status, weather, pit events. Lapped cars therefore see slightly less than they could, which is the safe direction. The cutoff matches the single `lap` field in the BUILD_PLAN `RaceState`. Lap 0 means pre-race: only pre-race facts are visible.
- **D-02: Two enforcement checks, both in CI.**
  1. *Import ban.* A test fails if any code other than the data-access module opens DuckDB or the storage layer directly.
  2. *Future-scramble test.* Replace every row after the cutoff with garbage (random values, NaN, shuffled order). The output at lap N must be identical.

  A deliberately leaky function is planted as a test fixture, and a test asserts that both checks catch it. This proves the guard works and satisfies roadmap success criterion 4.
- **D-03: Two separate doors.**
  - The *as-of accessor* never serves whole-race facts such as final position, total stint length, stint end lap or total stop count. It rebuilds stints and pit events only from the laps visible so far.
  - A separate *results accessor* serves final outcomes. The import ban allows only the backtest scoring code to import it.
  - Do not use a single accessor with an `include_results=True` flag. The user explicitly rejected that.
- **D-04: One accessor also governs cross-race walk-forward.** As of (race R, lap N) the accessor returns:
  - all earlier races in full;
  - pre-race facts for R, such as grid position and starting compound;
  - race R up to the D-01 cutoff.

  Later races are invisible. 2026 races are locked unless explicitly unlocked. The unlock mechanism should follow the D-03 principle: a separate door gated by the import ban, not a boolean flag. The exact form is at Claude's discretion and must be logged in DECISIONS.md.

#### What gets cached
- **D-05: Seasons are 2023, 2024, 2025, plus 2026.** 2026 races are tagged out-of-sample and locked behind the accessor (D-04). Load only 2026 races that have already happened; skip future rounds cleanly. 2022 is not loaded.
- **D-06: Sessions are Grand Prix races only.** No qualifying, sprints or practice. Grid position comes from the race results.
- **D-07: Beyond laps, stints, pit stops and results, also cache:**
  - per-lap/time-series **track status** (green, yellow, VSC, SC, red);
  - **weather**, at minimum rainfall and track temperature.

  Phase 3 fits the safety-car rate from this data and Phase 8 fits the regime model from it, so nothing needs re-downloading later.
- **D-08: Data source is FastF1 only.** FastF1 is MIT-licensed and already provides laps, stints, compound, tire age, pit in/out times, results, track status and weather. Design the cache tables so OpenF1 could feed them later (M6 live mode), but do not add OpenF1 now.

#### CI and test data
- **D-09: Every push runs on synthetic data.** CI tests use small fake races generated in code with known values. CI makes no network calls and commits no real data, which honors BUILD_PLAN's "don't republish raw data". Build the generator so later phases' synthetic-recovery tests can reuse it.
- **D-10: A separate real-data workflow runs weekly and on manual trigger.** It downloads Bahrain 2023 through FastF1, ideally with the FastF1 cache saved between runs, and runs the real-data tests. It is not a required check, so FastF1 outages never block the main build. Real-data tests carry a pytest marker (e.g. `network`) and are excluded from the default run.
- **D-11: CI matrix is Linux + Windows, Python 3.12.** The user develops on Windows, and DuckDB file locking and paths behave differently there.
- **D-12: The repo is `https://github.com/Befithalo/F1-Stochastic-Program`.** It was verified on 2026-10-22: public, empty, no branches. Add it as `origin` and push `main`; the first push triggers CI. Roadmap success criterion 1 requires CI to be green.
- **D-13: Pre-commit hooks run ruff locally** (`ruff check --fix` + `ruff format`) on every commit. mypy and pytest run in CI.

#### Commands, plot and walkthrough
- **D-14: One `f1si` CLI** (console script), run as `uv run f1si load` and `uv run f1si plot bahrain-2023`.
  - The loader defaults to D-05's seasons and has a seasons option.
  - It is **resumable**: it skips races already in the cache.
  - It waits and retries on rate limits.
  - It prints one progress line per race.
  - It finishes with a list of failed races instead of crashing on the first failure.
- **D-15: The plot is a static matplotlib PNG** written to a `reports/` folder.
- **D-16: Plot layout is small multiples.**
  - One panel per driver (all 20), lap time vs lap number, colored by tire compound.
  - Lap 1, pit in/out laps and SC/VSC laps stay **visible but faded**, not removed.
  - A `--drivers` option narrows the grid to chosen drivers.
  - The plot reads data through the as-of accessor at the final lap. It does not get a private path around the guard.
- **D-17: UI-03 explainer.** Write `docs/explained/phase-01.md`, committed to the public repo. It covers:
  - what was built and why;
  - how the pieces connect;
  - a file-by-file tour;
  - 3–5 "how would you explain this in an interview" questions with answers.

  Also give a short plain-language summary in chat at the end of the phase. The same format repeats for every later phase.

### Claude's Discretion
- **Era tag granularity.** Suggested: one `ground_effect_2022_2025` era covering the 2023–2025 races, and a separate `2026` era flagged out-of-sample. Keep the `season` column so per-season breakdowns remain possible. Log the choice in DECISIONS.md.
- **Exact pre-race facts list** (grid, starting compound, roster). Document it.
- **DuckDB schema and table names**, and file locations: suggested `data/` for the DuckDB file and FastF1 cache, gitignored.
- **Import-ban mechanism**: an AST-scan test or import-linter.
- **Seed convention (FND-03).** Suggested:
  - functions take an `rng: np.random.Generator` argument;
  - the CLI creates the generator from one seed;
  - ruff rule `NPY002` bans legacy `np.random.*` calls;
  - a test shows the same seed gives identical output.
- **DECISIONS.md format.** First entries must cover D-01–D-04, D-08, D-09 and the era-tag choice.
- **Coverage reporting** (advisory, not a gate).
- **`.gitignore` contents**: at minimum `data/`, FastF1 cache, `desktop.ini`, `.venv/`.

### Deferred Ideas (OUT OF SCOPE)
- **Qualifying sessions as a pace prior.** Revisit in Phase 7 (Bayesian pace model).
- **2022 season.** Revisit in Phase 7 if more training data is needed for the era effect. FastF1-only.
- **OpenF1 as a second source or cross-check.** M6 live mode, or earlier if FastF1 data quality issues appear.
- **Interactive plot (plotly).** The Phase 6 Streamlit view covers interactivity.
- **Paper notes in DECISIONS.md** (three ideas each from Heilmeier 2020 and RSRL, per BUILD_PLAN next steps). This is a reading task for the user, not code. It can be added to DECISIONS.md any time.

> **Researcher note on the deferred "OpenF1" item:** the deferral condition was "or earlier if FastF1 data quality issues appear". What has actually appeared is an **access** problem, not a data-quality one. Paid authentication is now required. Whether this triggers the deferral clause is the user's call; this research does not override it. See §Data Source Decision.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FND-01 | uv-managed Python 3.12 `src/f1si` package with ruff, mypy strict and pytest configured | §Standard Stack (verified versions); §Code Examples: `pyproject.toml`; §Pitfalls: pandas-stubs/FastF1 typing, MS Store python stub |
| FND-02 | GitHub Actions CI runs lint, type-check and tests on every push; must pass | §Code Examples: `ci.yml` (setup-uv v10, checkout v7, matrix ubuntu+windows); §Pitfalls: Windows DuckDB locks, hypothesis deadlines, CRLF |
| FND-03 | All randomness uses explicit `np.random.Generator`; same seed reproduces | §Pattern 7 (rng convention, `Generator.spawn`); NPY002 + AST ban on `RandomState`/stdlib `random`; seed test |
| FND-04 | `DECISIONS.md` logs every method choice with rationale | §Pattern 11 (entry format, required first entries incl. new ones this research surfaced); doc test |
| DAT-01 | Load 2023-2025 laps, stints, pit stops, results via FastF1/OpenF1 into DuckDB | §Data Source Decision; §Pattern 1 (normalized schema), §Pattern 4 (transactional resumable loader), rate limits for each source |
| DAT-02 | Plot lap time by stint for any cached race (Bahrain 2023 first) | §Pattern 9 (matplotlib `Figure` small multiples, faded classes, compound colors), `RACE_END` cutoff |
| DAT-03 | All backtest/replay code reads only through one as-of accessor returning rows up to a lap | §Pattern 2 (cutoff table, lap 0, RACE_END), §Pattern 3 (three doors, capability-style views) |
| DAT-04 | A test fails the build if any code reads a future row through or around the accessor | §Pattern 5 (AST import ban), §Pattern 6 (future-scramble harness + hypothesis + meta-test + canary) |
| DAT-05 | Every race tagged with regulation era; 2026 marked out-of-sample | §Pattern 8 (era mapping, `races` columns, out-of-sample door, `f1si races` listing) |
| UI-03 | Plain-language explanation after each phase | D-17 file `docs/explained/phase-01.md`; doc-existence test; interview Q&A topics listed in §Pattern 11 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Actionable directives the planner must verify compliance with:

| # | Directive | Source |
|---|-----------|--------|
| C1 | Stack: Python 3.12, uv, NumPy, pandas, SciPy, PyMC, Numba, FastF1, OpenF1, DuckDB, pytest + hypothesis, ruff, mypy strict, GitHub Actions CI; `src/` layout, package `f1si` | CLAUDE.md §Constraints |
| C2 | Explicit `np.random.Generator` everywhere; reproducible by seed | CLAUDE.md |
| C3 | Backtests read data only through one as-of accessor; a test enforces it | CLAUDE.md |
| C4 | Every model has a synthetic-data recovery test. Phase 1 has no models, but the synthetic generator must be reusable for later recovery tests | CLAUDE.md + D-09 |
| C5 | Docstrings state the math; DECISIONS.md logs every method choice and why | CLAUDE.md |
| C6 | CI must pass before a phase counts as done | CLAUDE.md |
| C7 | NumPy simulator under 10 s for 50,000 races (not Phase 1, but keep the accessor output NumPy-friendly) | CLAUDE.md |
| C8 | GSD workflow: file edits only through GSD commands (execute-phase for this work) | CLAUDE.md §GSD Workflow Enforcement |
| C9 | Do not copy LGPL TUMFTM code; credit FastF1/OpenF1; no raw-data republishing; non-commercial | BUILD_PLAN §Licensing (canonical ref) |

Note: C1 lists both FastF1 and OpenF1 in the stack, so Option B in the source decision stays within project constraints. Only CONTEXT D-08 narrows the choice.

---

## Data Source Decision (read first)

### What changed (evidence)

| Fact | Evidence | Tag |
|------|----------|-----|
| `livetiming.formula1.com/static/2023/.../SessionInfo.json` → **401** without auth | `curl` from this machine, 2026-10-22 | [VERIFIED: direct probe] |
| `livetiming.formula1.com/static/2023/Index.json` → **401** | same | [VERIFIED: direct probe] |
| FastF1 mirror `livetiming-mirror.fastf1.dev/.../2023-03-05_Race/SessionInfo.json` → **404** | same; issue #978 reports the mirror serves only 2021-2022 indexes | [VERIFIED: direct probe; CITED: issue #978] |
| The 401 started between 2026-10-14 and 2026-10-15; it is a deliberate CloudFront edge rule; the same request with an F1 TV `Authorization: Bearer <subscriptionToken>` returns 200 | github.com/theOehrly/Fast-F1/issues/978 | [CITED] |
| Maintainer: "an F1 TV Access subscription (or higher tier) will be necessary to access their data"; results remain on Jolpica | issue #978 comment by theOehrly, 2026-10-18 | [CITED] |
| `fastf1 3.9.0a0` (pre-release, 2026-10-18): "adds support for now required authentication on F1 livetiming archive endpoints"; the maintainer calls it "quick and dirty"; "The new login flow may fail if bot mitigation measures are activated by F1" | GitHub release v3.9.0-a0; PR #981 | [CITED] |
| 3.9.0a0 source: "An active F1TV subscription is required" (`fastf1/internals/f1account/tokens.py`); credentials via `F1_USERNAME`/`F1_PASSWORD` or `python -m fastf1 auth f1tv --authenticate`; token stored under `platformdirs.user_data_dir("fastf1")` | read from sdist | [VERIFIED: source read] |
| F1 had already blocked datacenter IPs from live timing (May 2026). FastF1's own CI moved to frozen test data because "CI runners were no longer able to access the F1 live timing API" | FastF1 issue #916 comment; PR #963 | [CITED] |
| The FastF1 dev docs page on auth still says post-session data needs no login. The maintainer called that sentence "obviously wrong" | issue #978 comment | [CITED] |
| OpenF1 free tier: historical data from 2023, no account or key, 3 req/s and 30 req/min, JSON or CSV, "personal use", site CC BY-NC-SA 4.0 | openf1.org | [CITED: openf1.org] |
| OpenF1 works today: Bahrain 2023 race (`session_key=7953`) laps (1058 rows, max lap 57), stints, race_control (includes "VIRTUAL SAFETY CAR DEPLOYED" lap 41), weather (161 rows), session_result (20), drivers (20). The 2026 season lists 25 race sessions with `is_cancelled` (Bahrain/Saudi April = true); 2026 Singapore (Oct 11) has 62 laps | direct API calls | [VERIFIED: direct probe] |
| OpenF1 gaps: `pit` returns "No results found" for Bahrain 2023 (but has 42 rows for Bahrain 2025); `starting_grid` returns nothing for race session keys | direct API calls | [VERIFIED: direct probe] |
| Jolpica works: `/ergast/f1/2023/1/results.json` returns 20 results with `grid`, `positionText`, `status`, `laps`, `points`; `/pitstops.json` returns 50 stops (lap, duration). Limits: 4 req/s burst, 500 req/h; HTTP 429 when exceeded | direct API calls; github.com/jolpica/jolpica-f1 docs/rate_limits.md | [VERIFIED + CITED] |

### Options (for the user; the planner inserts a `checkpoint:decision`)

| | Option A: FastF1 3.9.0a0 + F1 TV | Option B: OpenF1 + Jolpica (recommended) |
|---|---|---|
| Keeps D-08 as written | Yes (but requires an alpha version and a paid account) | No. Revises D-08; DAT-01 and CLAUDE.md already allow OpenF1 |
| Cost | F1 TV Access (or higher) subscription. Price varies by country [ASSUMED] | Free |
| Credentials | F1 account username/password. Bot-mitigation can break login [CITED] | None |
| Stability | Pre-release alpha, 4 days old, maintainer says "move fast and break things" [CITED] | Stable public API; free tier "free forever" per site [CITED] |
| D-10 weekly CI download | Not viable: needs F1 TV secrets in a public repo's CI, plus the datacenter-IP block and bot mitigation. Becomes a local-only `uv run pytest -m network` | Plausible from GitHub runners, but **unverified**: whether OpenF1 blocks datacenter IPs is unknown [ASSUMED]. Keep it non-blocking |
| Track status | Native FastF1 codes `1,2,4,5,6,7` per lap and as a time series [VERIFIED: source] | Derived from race_control messages (SafetyCar/Flag categories) with a documented mapping. Somewhat lower fidelity |
| Tire data | Per-lap `Compound`, `TyreLife`, `FreshTyre`, `Stint` [VERIFIED: source] | Per-stint `compound`, `lap_start`, `lap_end`, `tyre_age_at_start`, exploded to per-lap at load [VERIFIED: probe] |
| Lap clock | Session-time timedeltas (`Time` = lap end) [VERIFIED: source] | Absolute UTC `date_start` + `lap_duration` (end = start + duration; 3 nulls in Bahrain 2023 → use next lap's start) [VERIFIED: probe] |
| Grid / results | Jolpica via FastF1. Silently missing if Jolpica returns 429 [VERIFIED: source] | Jolpica directly (`grid`, `status`, `positionText`) |
| Full first load (~87 races) | ~10 HTTP calls/race against FastF1's 500/h limit → ~2 h, with ≥1 forced wait [derived from source] | ~7 OpenF1 calls/race at ≤30/min → ~20–25 min, plus ~90 Jolpica calls [derived] |
| Licence/terms | FastF1 is MIT; data is now behind F1 TV terms, which may restrict automated access. A ToS question, not legal advice [ASSUMED] | OpenF1 personal/non-commercial use [CITED] |

**Recommendation:** Option B for Phase 1. Keep a `RaceSource` protocol with the normalized tables as its output contract. A `Fastf1Source` (3.9+, authenticated) can be added later as a second implementation, for a user with F1 TV or once FastF1 stabilizes. DECISIONS.md must record the change to D-08 and why.

**If the user picks Option A:**

- Pin `fastf1==3.9.0a0` exactly, with uv `[tool.uv] prerelease-package = { fastf1 = "allow" }`.
- Authenticate once with `uv run python -m fastf1 auth f1tv --authenticate` (interactive prompt). Do not put the password in `$env:` lines, because PowerShell's PSReadLine history saves them in plain text [ASSUMED: PSReadLine default behaviour].
- Run real-data tests locally only.

**Total races in scope as of today:** 2023: 22 GP races (Imola was cancelled and is absent from the schedule); 2024: 24; 2025: 24; 2026: rounds 1–17 completed. Round 16 is "Bahrain Grand Prix" held at Kuala Lumpur on 2026-10-04; round 18 is the US GP on 2026-10-25, which is in the future. That is about 87 races. [VERIFIED: FastF1 schedule JSON `theOehrly/f1schedule` and OpenF1 sessions]

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Command-line UX (`load`, `plot`, `races`) | CLI (`f1si.cli`) | — | Parses args, wires objects, prints friendly errors. No data logic. Must not import `duckdb` or sources directly |
| Fetch a race from a provider | Source adapters (`f1si.data.sources.*`) | — | Only tier with network I/O. Outputs normalized DataFrames; never writes DB |
| Normalized schema (single source of truth) | Schema module (`f1si.data.schema`) | — | Column names, dtypes, visibility column per table; validated at the adapter→store boundary |
| Synthetic races with known truth | Synthetic generator (`f1si.synthetic`) | Tests | Same normalized output as real sources. Reused by later phases' recovery tests (D-09) |
| Persist and read DuckDB | Storage (`f1si.data._db`) | — | **Only** module importing `duckdb`. Owns connections, DDL, transactional per-race write, parameterized reads |
| Resumable bulk load | Loader (`f1si.data.loader`) | Storage, Sources | Schedule → skip cached → fetch → validate → write → one progress line; retries; failure list |
| As-of reads (lap cutoff, history, pre-race facts) | As-of door (`f1si.data.asof`) | Storage | Enforces D-01/D-03/D-04; rebuilds stints/pits from visible laps; refuses 2026 |
| Final outcomes | Results door (`f1si.data.results`) | Storage | Import-allowed only for `f1si.backtest.scoring` (Phase 6) |
| 2026 access | Out-of-sample door (`f1si.data.out_of_sample`) | As-of door | Import-allowed only for `f1si.evaluation.holdout` (Phase 8) |
| Regulation era tags | `f1si.eras` | Loader | Pure function season → era; the loader stamps it on `races` |
| Seeded randomness | `f1si.rng` | All | One root `Generator` per CLI run; `rng` passed explicitly |
| Lap-time-by-stint PNG | Reporting (`f1si.plots.stints`) | As-of door | Reads only via `AsOf(race, RACE_END)`; matplotlib `Figure` (no pyplot) |
| Look-ahead enforcement | Test guards (`tests/guards/*`) | CI | AST import scan + future-scramble harness + meta-test |
| Quality gate | GitHub Actions | pre-commit (local ruff) | Lint/type/test on ubuntu + windows; separate non-blocking real-data workflow |

---

## Standard Stack

All versions checked against the PyPI JSON API on 2026-10-22 [VERIFIED: pypi.org/pypi/<pkg>/json].

### Core (runtime)
| Library | Version (pin) | Purpose | Why Standard |
|---------|---------------|---------|--------------|
| Python | 3.12.x (`requires-python = ">=3.12,<3.13"`) | Runtime | Locked by C1/D-11 |
| numpy | 2.5.4 latest; pin `>=2.3,<3` | Arrays, `np.random.Generator` | FastF1 requires `numpy<3` [VERIFIED] |
| pandas | **2.3.3**; pin `>=2.3.3,<3` | DataFrames at the source/store boundary | **FastF1 3.8.3 and 3.9.0a0 both require `pandas<3`** [VERIFIED: requires_dist]. Pandas 3.0.6 exists but would close the FastF1 door. Pandas-3 support is FastF1 issue #944 (open) [CITED] |
| duckdb | **1.5.6**; pin `>=1.5.6,<2` | Local analytical store | 2.0.0 shipped **yesterday** (2026-10-21). Its storage format cannot be read by 1.x. DuckDB itself advises mission-critical users to wait for the first patch, expected in November. 1.5 is supported to March 2027 [CITED: duckdb.org/2026/10/21/announcing-duckdb-200.html]. Ships `py.typed` + stubs [VERIFIED: duckdb-python repo tree] |
| matplotlib | 3.11.2; pin `>=3.11,<4` | Static PNG plot | Ships inline types (no stubs needed) [ASSUMED: py.typed since 3.8]; `Figure` API avoids pyplot state [CITED: matplotlib web-server guide] |

### Source adapter dependencies (depends on the decision)
| Library | Version | Option | Purpose |
|---------|---------|--------|---------|
| requests | 2.34.2 | B | HTTP client for OpenF1/Jolpica |
| requests-cache | 1.3.3 | B | Persistent HTTP cache (SQLite), so re-runs and CI cache restores make zero calls. FastF1 uses the same library internally [VERIFIED: fastf1/req.py] |
| types-requests | 2.33.0.20261006 | B (dev) | mypy stubs for requests |
| fastf1 | **3.9.0a0** (pre-release; 3.8.3 cannot download any more) | A | F1 live-timing archive with F1 TV auth |

### Dev / quality
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| pytest | 9.1.1 | Tests | pytest ≥ 9 supports native `[tool.pytest]` TOML table [CITED: docs.pytest.org customize] |
| hypothesis | 6.170.5 | Property test for future-scramble | Auto `ci` profile when `CI` env set: `deadline=None`, `derandomize=True` [CITED: hypothesis API docs] |
| ruff | 0.17.1 | Lint + format | `NPY002` = numpy-legacy-random [CITED: docs.astral.sh/ruff/rules/numpy-legacy-random] |
| mypy | 2.4.0 | Strict typing | 2.0 made `--local-partial-types` and `--strict-bytes` default; 2.4 uses the native parser by default [CITED: mypy changelog] |
| pandas-stubs | **2.3.3.260113**; pin `>=2.3.3,<3` | pandas types for mypy | Must match pandas major. Unconstrained, uv would pick 3.0.5.x [VERIFIED: PyPI] |
| pre-commit | 4.7.0 | Local ruff hooks (D-13) | ruff-pre-commit hook ids `ruff-check` (args `[--fix]`) then `ruff-format` [CITED: github.com/astral-sh/ruff-pre-commit] |
| pytest-cov | 7.1.0 | Advisory coverage | Not a gate (discretion) |

### CI actions (latest tags, 2026-10-22)
| Action | Tag | Note |
|--------|-----|------|
| actions/checkout | v7 (7.0.1) | [VERIFIED: GitHub releases API] |
| astral-sh/setup-uv | v10 (10.3.1, released 2026-10-21) | Inputs `python-version`, `enable-cache` [CITED: setup-uv README]. The README pins a commit SHA; pinning SHAs is optional hardening |
| actions/cache | v6 (6.1.0) | For the real-data HTTP cache |
| actions/upload-artifact | v7 (7.0.2) | Only for derived PNGs, never raw data |
| uv (tool) | 0.13.5 | `uv init` src layout + `uv_build` backend `>=0.13.4,<0.14` [CITED: docs.astral.sh/uv/concepts/projects/init] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AST import-scan test | import-linter 2.15 `protected` contract (`protected_modules` + `allowed_importers`, external packages allowed with `include_external_packages`) [CITED: import-linter docs] | Declarative and mature, but: it scans only the package import graph (not `tests/fixtures`), it does not see `importlib.import_module("duckdb")`, and the D-02 meta-test would need a throwaway package plus a duplicate config, which can drift. **Use the AST test**; import-linter can be added later as extra defence |
| argparse | typer / click | Extra dependency; argparse is enough for 3 subcommands and is mypy-clean |
| DuckDB 1.5.x | DuckDB 2.0.0 | 2.0 is LTS to Oct 2027 but one day old; upgrading later is one-way but trivial because the cache can be rebuilt |
| requests-cache | Hand-rolled JSON file cache | requests-cache already handles cache keys, 200-only caching and expiry |
| Storing time as DuckDB `INTERVAL` | `DOUBLE` seconds | INTERVAL compares by months/days/µs parts and maps awkwardly to NumPy. Seconds as float64 are simple for cutoffs and for Phase 3 vectorization |

**Installation (after `uv` exists; Option B shown):**
```powershell
uv python install 3.12
uv add "numpy>=2.3,<3" "pandas>=2.3.3,<3" "duckdb>=1.5.6,<2" "matplotlib>=3.11,<4" "requests>=2.34,<3" "requests-cache>=1.3,<2"
uv add --dev "pytest>=9.1,<10" "hypothesis>=6.170" "ruff==0.17.1" "mypy>=2.4,<3" "pandas-stubs>=2.3.3,<3" "types-requests" "pre-commit>=4.7" "pytest-cov>=7.1"
```
Option A replaces the requests lines with `uv add "fastf1==3.9.0a0"`. Add `[tool.uv] prerelease-package = { fastf1 = "allow" }` if uv refuses the pre-release [CITED: uv resolution docs].

## Package Legitimacy Audit

slopcheck **could not run**: this machine has no Python interpreter, only the Microsoft Store stub, so `pip install slopcheck` is impossible. Per protocol, every package below is tagged **[ASSUMED]**. Registry existence, age and source repository were checked through the PyPI JSON API. Python wheels have no npm-style postinstall scripts. All have wheels for cp312 / win_amd64 / manylinux, so no `setup.py` runs at install [VERIFIED for duckdb 1.5.6; ASSUMED for others].

| Package | Registry | Age (first upload) | Source Repo | slopcheck | Disposition |
|---------|----------|-------------------|-------------|-----------|-------------|
| numpy | PyPI | 2006 | github.com/numpy/numpy | unavailable | Approved [ASSUMED] |
| pandas | PyPI | 2009 | pandas.pydata.org (github.com/pandas-dev/pandas) | unavailable | Approved [ASSUMED] |
| duckdb | PyPI | 2019 | github.com/duckdb/duckdb-python | unavailable | Approved [ASSUMED] |
| matplotlib | PyPI | 2006 | github.com/matplotlib/matplotlib | unavailable | Approved [ASSUMED] |
| requests | PyPI | 2011 | github.com/psf/requests | unavailable | Approved [ASSUMED] (Option B) |
| requests-cache | PyPI | 2012 | github.com/requests-cache/requests-cache | unavailable | Approved [ASSUMED] (Option B) |
| types-requests | PyPI | 2021 | github.com/python/typeshed | unavailable | Approved [ASSUMED] (Option B) |
| fastf1 | PyPI | 2021 | github.com/theOehrly/Fast-F1 | unavailable | Approved [ASSUMED] (Option A; **pre-release**) |
| pytest | PyPI | 2010 | github.com/pytest-dev/pytest | unavailable | Approved [ASSUMED] |
| hypothesis | PyPI | 2013 | github.com/HypothesisWorks/hypothesis | unavailable | Approved [ASSUMED] |
| ruff | PyPI | 2022 | github.com/astral-sh/ruff | unavailable | Approved [ASSUMED] |
| mypy | PyPI | 2009 | github.com/python/mypy | unavailable | Approved [ASSUMED] |
| pandas-stubs | PyPI | 2021 | github.com/pandas-dev/pandas-stubs | unavailable | Approved [ASSUMED] |
| pre-commit | PyPI | 2014 | github.com/pre-commit/pre-commit | unavailable | Approved [ASSUMED] |
| pytest-cov | PyPI | 2010 | (pytest-dev) | unavailable | Approved [ASSUMED] |

**Packages removed due to slopcheck [SLOP] verdict:** none (not run)
**Packages flagged as suspicious [SUS]:** none (not run)

*slopcheck was unavailable, so all packages are `[ASSUMED]`. Recommended: **one** `checkpoint:human-verify` before the first `uv add`, listing the whole dependency set. All are long-established projects with official source repos.*

---

## Architecture Patterns

### System Architecture Diagram

```
                     ┌──────────────────────── f1si CLI (argparse) ────────────────────────┐
 user (PowerShell) → │ load [--seasons] [--source openf1|fastf1|synthetic] │ plot <slug> │ races │
                     └──────┬───────────────────────────────────────────────┬──────────┬────┘
                            │                                               │          │
                            ▼                                               │          │
                    Loader (resumable)                                      │          │
   schedule ──► for each completed race:                                    │          │
   (skip future/cancelled)  already complete in `races`? ──yes──► "skipped" │          │
                            │ no                                            │          │
                            ▼                                               │          │
             RaceSource.fetch(race) ── network ──► OpenF1 / Jolpica         │          │
             (or FastF1, or Synthetic)   ◄── HTTP cache (data/http-cache) ──┤          │
                            │ rate-limited? → wait → retry                  │          │
                            ▼                                               │          │
             normalize → schema.validate (dtypes, keys, visible_at_s)       │          │
             derive lap_cutoffs (leader clock, monotone)                    │          │
                            ▼                                               │          │
             _db.write_race(): BEGIN; DELETE race; INSERT tables;           │          │
                               INSERT races row (completion marker); COMMIT │          │
                            ▼                                               │          │
                     data/f1si.duckdb  ◄────────── read_only connections ───┼──────────┤
                            ▲                                               ▼          ▼
            ┌───────────────┼───────────────────────────────┐     AsOf(race, lap|RACE_END)
            │ As-of door    │ Results door  │ Out-of-sample │            │
            │ (cutoff, pre- │ (final class.)│ door (2026)   │            ▼
            │ race, history)│ → Phase 6     │ → Phase 8     │     RaceSnapshot (visible only)
            └───────┬───────┴───────────────┴───────────────┘            │
                    │                                                     ▼
                    └──────────────────────────────────────► plots.stints → reports/<slug>.png

 CI guards (every push, synthetic data only):
   import-scan(src/f1si) == []      future-scramble(consumer, lap ~ hypothesis) identical
   meta-test: both detect tests/fixtures/leaky_consumer.py
```

### Recommended Project Structure
```
.github/workflows/ci.yml            # push/PR: ruff, format check, mypy, pytest (ubuntu + windows)
.github/workflows/real-data.yml     # weekly + manual, non-blocking, pytest -m network
.pre-commit-config.yaml             # ruff-check --fix, ruff-format
.gitattributes / .gitignore / .python-version / pyproject.toml / uv.lock
DECISIONS.md                        # FND-04
docs/explained/phase-01.md          # UI-03 / D-17
src/f1si/
  __init__.py                       # version only
  cli.py                            # argparse: load, plot, races
  paths.py                          # data dir, db path, reports dir (env override F1SI_DATA_DIR)
  rng.py                            # make_rng(seed) -> np.random.Generator
  eras.py                           # Era, era_for_season()
  synthetic/                        # SyntheticRaceSpec, generate_race(spec, *, rng), generate_dataset(...)
  data/
    __init__.py                     # EMPTY of door imports (guard test checks this)
    schema.py                       # table specs: columns, dtypes, keys, visibility column
    _db.py                          # ONLY `import duckdb`: connect_writer/connect_reader, DDL, write_race, query helpers
    asof.py                         # AsOf, RACE_END, AsOfAccessor, RaceSnapshot, catalog()
    results.py                      # ResultsAccessor (final outcomes) — restricted importers
    out_of_sample.py                # OutOfSampleAccessor (2026) — restricted importers
    loader.py                       # load_races(...) resumable, retries, progress, failures
    sources/
      __init__.py                   # RaceSource Protocol, RaceRef, NormalizedRace, errors
      openf1.py | fastf1_source.py  # the chosen real adapter (only module importing its HTTP/lib)
      synthetic_source.py           # wraps f1si.synthetic for `--source synthetic`
  plots/
    stints.py                       # prepare_stint_plot_data(snapshot) + render_stint_plot(data, path)
tests/
  conftest.py                       # dataset fixtures (3 races + 1 locked 2026 race), hypothesis profiles
  guards/import_scan.py             # scanner + POLICY table (single source)
  guards/scramble.py                # scramble_future(), assert_no_lookahead()
  guards/consumers.py               # registry of as-of consumers to scramble-test
  guards/test_import_ban.py | test_future_scramble.py | test_meta_guard.py
  fixtures/leaky_consumer.py        # planted leak (NOT under src/)
  data/ plots/ test_rng.py test_eras.py test_cli.py test_decisions_log.py test_docs.py
  real/test_bahrain_2023.py         # @pytest.mark.network
```

### Pattern 1: One normalized schema with an explicit visibility column
**What:** Every adapter (OpenF1, FastF1, synthetic) outputs the same tables. Each time-indexed row carries `visible_at_s DOUBLE NULL`, the race-clock second at which the row became knowable. `NULL` means not knowable mid-race (for example a lap with no end time). Such a row is visible only at `RACE_END` and in history.
**Why:** Visibility then becomes one generic rule, `visible_at_s IS NOT NULL AND visible_at_s <= cutoff_s`. The scramble harness can be generic too. OpenF1 can feed the same tables, as D-08 asks.

Recommended tables. `race_id = f"{season}-{round:02d}"`, for example `2023-01`.

| Table | Grain / key | Visibility | Key columns (beyond keys) |
|-------|-------------|------------|---------------------------|
| `races` | race_id | calendar: always (pre-race facts only) | season, round, slug (`bahrain-2023`), event_name, circuit (location/circuit key), country, race_start_utc, scheduled_laps NULL, era, out_of_sample, source, source_version, loaded_at_utc, load_status |
| `entries` | race_id, driver_number | pre-race (lap 0) | driver_code (TLA), driver_id (Jolpica id; cross-season identity), full_name, team_name, grid_position NULL, start_compound, start_tyre_age, start_fresh_tyre |
| `laps` | race_id, driver_number, lap_number | `lap_end_s` | lap_start_s, lap_end_s, lap_time_s, s1_s, s2_s, s3_s, pit_in_s NULL, pit_out_s NULL, is_pit_out_lap, compound, tyre_life, stint, track_status (per-lap codes string), is_accurate NULL, is_generated, speed traps |
| `track_status` | race_id, seq | `t_s` | t_s, status (`1,2,4,5,6,7`), message |
| `session_status` | race_id, seq | `t_s` | t_s, status (Started/Aborted/Finished…) |
| `weather` | race_id, t_s | `t_s` | air_temp, track_temp, humidity, pressure, rainfall (bool), wind_speed, wind_dir |
| `race_control` (Option B) | race_id, seq | `t_s` | category, flag, scope, sector, driver_number, lap_number, message |
| `lap_cutoffs` | race_id, lap | `cutoff_s` | cutoff_s (lap 0 = race start; laps 1..max = leader completion) |
| `results` | race_id, driver_number | **never via as-of** (results door only) | final_position NULL, classified_position (text), status, points, laps_completed, total_time_s NULL |
| `stints`, `pit_stops` | SQL **VIEWs** over `laps` | n/a (for humans; the as-of door never reads them for the current race) | Satisfies "stints, pit stops in the DuckDB file" (SC2) without a second copy of the data |

**Column-provenance rule:** a stored column is allowed into the as-of view only if its value was knowable at the row's `visible_at_s`. Exclude FastF1 `Deleted`, `DeletedReason` and `IsPersonalBest`: deletions are applied from race-control messages issued later, and the deletion parser even does a "look-ahead pass" for reinstatements [VERIFIED: core.py `_set_laps_deleted_from_rcm`]. Recompute the per-lap position in the accessor from visible lap end times instead of trusting the stored value. `IsAccurate` is safe: it uses only the row and the previous lap [VERIFIED: core.py `_check_lap_accuracy`]. FastF1's per-lap `TrackStatus` uses only status changes that started at or before the lap ends [VERIFIED: core.py `_add_track_status_to_laps`].

### Pattern 2: Resolve "lap N" to a time with a precomputed `lap_cutoffs` table
**What:** At load time, per race:
- `cutoff(0)` = race start. Use the 'Started' session-status time for FastF1, or the leader's lap-1 `date_start` (lights out) for OpenF1.
- `cutoff(n)` = `min(lap_end_s)` over **non-generated** laps with `lap_number = n` and a non-null end.
- Then enforce monotonicity with a **reverse cumulative minimum**. This only ever moves cutoffs earlier, which is the safe direction. Log any correction as a data-quality note.
- `RACE_END` = no time filter for race R. Every row of race R is visible except results, which stay behind their door.

**Why precompute:** computing the min at query time reads the other drivers' lap-N rows, and those are future rows at cutoff N. The scramble test would then fail the accessor itself. The precomputed row for lap N has `cutoff_s = T_N ≤ T_N`, so it is visible by definition.
**Why exclude generated laps:** FastF1 adds retirement laps with an assumed end time, either the red-flag abort time or `ref_time + 150 s`. They can undercut the real leader's time for a lap number [VERIFIED: core.py `_fix_missing_laps_retired_on_track`].
**Consequence to document (DECISIONS.md and accessor docstring):** at cutoff N the leader has N laps visible and every other car has at most N−1. Phase 2's `RaceState` needs a per-car `laps_completed`, and the explainer should say so in plain words.

### Pattern 3: Three doors, and views as capabilities
**What:**
- `AsOfAccessor(db_path).snapshot(AsOf(race_id, lap))` returns a frozen `RaceSnapshot` containing:
  - `race` metadata, `cutoff_s` and `entries` (pre-race facts);
  - visible `laps`, `track_status`, `weather` and `session_status`;
  - `stints` and `pit_events` rebuilt from the visible laps.
- `AsOfAccessor.history(at)` returns earlier races in full.
- `ResultsAccessor` and `OutOfSampleAccessor` live in their own modules. The import ban controls which modules may import each one.

There is no `include_results` or `unlock` flag anywhere (D-03/D-04).
**Model code receives a `RaceSnapshot` (data), not the accessor (a capability).** Only the replay/backtest driver holds the accessor. This shrinks the surface for "through-the-accessor" leaks such as asking for lap N+3.
**Rebuilt stint fields at cutoff:** `stint`, `compound`, `first_lap`, `last_visible_lap`, `laps_so_far`, `tyre_life_now`. There is **no** `last_lap` or stint length. `stops_done` counts pit-out laps after lap 1. Pit-lane starters have a lap-1 out-lap that is **not** a stop.

### Pattern 4: Idempotent, resumable per-race write
**What:**
- One transaction per race: `BEGIN` → `DELETE FROM t WHERE race_id = ?` for every race table → `INSERT INTO t BY NAME SELECT * FROM incoming` → insert the `races` row last, with `load_status='complete'` → `COMMIT`. On any exception (including `KeyboardInterrupt`), `ROLLBACK` and re-raise.
- The loader skips race_ids already `complete`.
- DuckDB's own guidance is to replace rows with delete-then-insert inside a transaction. `INSERT … BY NAME` matches columns by name [CITED: duckdb.org/docs/2.0/sql/indexes.html, /sql/statements/insert.html].
- Avoid `PRIMARY KEY` on large tables because of over-eager constraint checking and ART memory use [CITED: same]. Enforce key uniqueness with a validation query in `schema.validate` and in tests.

**Concurrency facts:**
- One process may read and write; several processes may only read, with `read_only=True`.
- "Within one Python process, all connections to a database file must use the same configuration, `read_only` included" [CITED: duckdb.org/docs/2.0/clients/python/dbapi.html; /connect/concurrency.html].
- On Windows a running `f1si load` therefore blocks `f1si plot`. Catch `duckdb.IOException` and print: "The cache is busy (another f1si command is using it). Wait for it to finish, then run this again."

### Pattern 5: AST import-ban scanner with one policy table
**What:** `tests/guards/import_scan.py` parses every `.py` under `src/f1si` with `ast`. It collects `Import`, `ImportFrom` (resolving relative imports, and also yielding `pkg.name` for `from pkg import name`) and `importlib.import_module(...)`/`__import__(...)` calls with string-literal arguments. Each import is checked against a policy (protected prefix → allowed importer modules):

| Protected | Allowed importers |
|-----------|-------------------|
| `duckdb` | `f1si.data._db` |
| `fastf1` / `requests` / `requests_cache` | the single real adapter module (e.g. `f1si.data.sources.openf1`) |
| `sqlite3` | none (the FastF1/requests-cache SQLite files are a back door to whole races) |
| `f1si.data._db` | `f1si.data.asof`, `f1si.data.results`, `f1si.data.out_of_sample`, `f1si.data.loader` |
| `f1si.data.results` | `f1si.backtest.scoring` (Phase 6; module does not exist yet) |
| `f1si.data.out_of_sample` | `f1si.evaluation.holdout` (Phase 8) |
| `f1si.data.sources` (real adapters) | `f1si.data.loader`, `f1si.cli` |

Also assert that `f1si/data/__init__.py` imports none of the doors. Otherwise `import f1si.data` followed by attribute access would bypass the ban. Flag RNG violations here too: `numpy.random.RandomState`, `numpy.random.seed` and the stdlib `random` module. NPY002 covers legacy *function calls*; whether it flags `RandomState` is not documented [CITED: ruff NPY002 page; ASSUMED for RandomState].
**Honest limit (state it in DECISIONS.md):** Python cannot be sandboxed. The ban stops accidents and obvious bypasses. The scramble test catches behaviour.

### Pattern 6: Future-scramble harness + hypothesis + meta-test + canary
**What:**
- `scramble_future(tables, at, rng)` keeps every row with `visible_at_s <= cutoff_s` of race R byte-identical, plus all rows of earlier races and the calendar. For **future rows** (race R rows with `visible_at_s` NULL or `> cutoff`, all rows of later and 2026 races, and the whole `results` table) it:
  - keeps primary-key columns, so no duplicate keys appear;
  - randomizes every other column (random numbers, NaN, junk strings);
  - redraws `visible_at_s` as `cutoff + U(1, 1e4)`, so future rows stay future;
  - appends extra junk future rows with new keys and drops some future rows;
  - shuffles physical row order with `rng.permutation`.
- `assert_no_lookahead(consumer, tables, at, rng)` writes the original and the scrambled tables to two temp DuckDB files, runs `consumer(db_path, at)` on both, and deep-compares the outputs with `pd.testing.assert_frame_equal(check_exact=True)` for DataFrames, field by field for dataclasses. On mismatch it raises `LookaheadDetected(AssertionError)`.
- The real test is `@given(lap=st.integers(0, n_laps), seed=st.integers(0, 2**63 - 1))` with `@settings(deadline=None, max_examples≈25)`. It runs for every registered consumer (the snapshot itself, the stint/pit rebuild, `prepare_stint_plot_data`) plus `RACE_END`. It also exercises the 2026 lock and the later-race invisibility.
- **Meta-test (D-02):** `tests/fixtures/leaky_consumer.py` does `import duckdb` and averages lap times over the **whole** race. Assert `scan([fixture]) != []` **and** `pytest.raises(LookaheadDetected)` from the harness. A second fixture, `leaky_through_accessor`, calls the accessor with `lap + 3`. Only the scramble test can catch it, which proves the "through" half of DAT-04.
- **Optional canary CI step (ubuntu only):** copy the leaky fixture into `src/f1si/_canary.py`, then assert that `pytest tests/guards/test_import_ban.py` **fails**. This proves literally that "a deliberately leaking test case fails the build" (SC4).

### Pattern 7: Seed convention (FND-03)
- `f1si.rng.make_rng(seed: int) -> np.random.Generator` wraps `np.random.default_rng(seed)`.
- The CLI owns the only call and takes a `--seed` option with a documented default.
- Library functions take `*, rng: np.random.Generator` as a keyword-only argument with **no default**.
- Independent streams use `rng.spawn(n)`. NumPy recommends `SeedSequence`/`spawn` over adjacent integer seeds, and `default_rng([worker_id, root_seed])` for worker IDs [CITED: numpy.org/doc/stable/reference/random/parallel.html, NumPy 2.5 manual].
- Enforce with ruff `NPY002` plus the AST ban above.
- Test: the same seed gives identical `generate_dataset` output (`assert_frame_equal`); a different seed gives different output.

### Pattern 8: Era tags and the 2026 lock (DAT-05)
- `eras.py`: `GROUND_EFFECT = Era("ground_effect_2022_2025", 2022, 2025, out_of_sample=False)` and `REG_2026 = Era("reg_2026", 2026, 2026, out_of_sample=True)`. `era_for_season()` **raises** for unknown seasons (2027+, pre-2022). That forces a logged decision later.
- The 2026 regulations bring a roughly 50/50 ICE/electric split, the MGU-H removed, active aero, reduced ground effect and lighter, narrower cars [CITED: formula1.com FIA 2026 regs article; si.com]. Narrower tyres per BUILD_PLAN [CITED: BUILD_PLAN sources].
- The loader stamps `era` and `out_of_sample` on `races`; keep `season`.
- `AsOfAccessor` raises `OutOfSampleLockedError` with a helpful message for any 2026 race, and never includes 2026 rows in `history()`.
- Add `uv run f1si races` to list race_id, slug, era and out_of_sample. It reads the calendar only, via `asof.catalog()`. This makes SC5 visible to the user.

### Pattern 9: The plot (DAT-02, D-15/16)
- Read through `AsOfAccessor(db).snapshot(AsOf(race_id, RACE_END))`.
- `prepare_stint_plot_data(snapshot, drivers=None)` is pure and testable. It classifies each lap as `clean` or `faded`. Faded means: lap 1, in-laps (`pit_in_s`), out-laps (`pit_out_s`/`is_pit_out_lap`), track status containing `4`, `5`, `6` or `7`, or a generated lap.
- `render_stint_plot(data, out_path)` uses `matplotlib.figure.Figure`, **not pyplot**. Matplotlib "strongly recommend[s]" this for servers: pyplot keeps figure references and leaks [CITED: matplotlib 3.11.2 web_application_server example]. It also needs no backend selection on CI or Windows.
- `fig.subplots(nrows, ncols=5, sharex=True, sharey=True, squeeze=False)`, one panel per driver, ordered by finishing order if available. Do **not** read results for ordering; use grid order from `entries` or the last visible position. Hide unused axes.
- Use a local `COMPOUND_COLORS` dict: SOFT `#da291c`, MEDIUM `#ffd12e`, HARD `#f0f0ec`, INTERMEDIATE `#43b02a`, WET `#0067ad`. These are the same values FastF1 ships for 2023-2026 [VERIFIED: fastf1/plotting/constants.json]. Don't call `fastf1.plotting`, which needs a FastF1 `Session` object [VERIFIED: `_interface.py`].
- Faded laps: `alpha≈0.25`. Set the y-limits from **clean** laps only, using percentiles plus a margin, or pit and SC laps flatten the trend.
- HARD is near-white, so draw markers with dark edges or use a grey facecolor.
- Save with `layout="constrained"` and `dpi≈120` to `reports/<slug>.png`.

### Pattern 10: CLI ergonomics for a new coder
- argparse subcommands; `main(argv: list[str] | None = None) -> int`; `[project.scripts] f1si = "f1si.cli:main"`.
- Every expected failure prints one line saying what to do next: no cache → "run `uv run f1si load`"; cache busy; unknown slug → list close matches; network down; rate limit wait. Show tracebacks only with `--debug`.
- Progress line format: `[ 12/87] 2023-12 belgium-2023  ok  1,034 laps  (era ground_effect_2022_2025)`. Alternatives are `skipped (cached)` and `FAILED: <reason>`. Finish with a failures table. Exit code 0 when everything succeeds, 2 when some races failed.

### Pattern 11: DECISIONS.md and the explainer
- **Entry format:** `## DEC-NNN — Title`, then Date / Status / Context / Decision / Why / Alternatives rejected / Consequences / Refs (requirement IDs, CONTEXT D-xx).
- **Required first entries:** D-01, D-02, D-03, D-04, D-08 (and the source revision, if any), D-09, era tags.
- **Entries this research adds:**
  - `RACE_END` cutoff;
  - "non-leaders show N−1 laps at cutoff N";
  - precomputed lap cutoffs with reverse cumulative min;
  - column-provenance whitelist (`Deleted`/`IsPersonalBest` excluded);
  - grid stored in `entries`, not `results`;
  - AST scan over import-linter;
  - DuckDB 1.5 pin;
  - pandas < 3 pin;
  - time stored as float seconds.
- **Explainer interview topics:** why the leader's clock; why two doors; how scramble testing proves a negative; why synthetic data in CI; what "out-of-sample era" means.

### Anti-Patterns to Avoid
- **`include_results=True` / `unlock=True` flags:** explicitly rejected (D-03/D-04).
- **Computing the cutoff from lap rows at query time:** reads future rows (Pattern 2).
- **Exposing stored whole-race columns** (FastF1 `Deleted`, stint `lap_end`, results `Laps`): baked-in leaks the scramble test cannot see.
- **Relying on row order** (`.iloc[-1]` as "latest"): the scramble shuffles row order. Always `ORDER BY` keys.
- **pyplot in library code:** global state and backend issues on headless/Windows CI.
- **Catching `Exception` around FastF1 loads and trusting the result:** FastF1 swallows most errors as warnings, so data may be partly missing (see Pitfalls).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP caching of immutable historical responses | dict-of-files cache | `requests-cache` (SQLite, never-expire for historical) | Cache keys, 200-only caching, concurrency; FastF1 uses it too |
| Parsing Python imports | regex over source text | `ast` module (stdlib) | Handles relative, multi-line, aliased and `from x import y` forms |
| Property-based input generation | hand loops over laps/seeds | `hypothesis` | Shrinking finds the minimal leaking lap; CI profile is automatic |
| Independent RNG streams | `seed + i` | `Generator.spawn` / `SeedSequence` | Adjacent seeds can correlate; NumPy documents spawn [CITED] |
| Dataframe equality | manual column loops | `pandas.testing.assert_frame_equal(check_exact=True)` | dtype-, index- and NaN-aware |
| Table writes | row-by-row `executemany` | `con.register(df)` + `INSERT … BY NAME SELECT` | DuckDB docs: "Do *not* use `executemany` to insert large amounts of data" [CITED: dbapi page] |
| Lint/format hooks | custom git hooks | `pre-commit` + `astral-sh/ruff-pre-commit` | Standard; same ruff version as CI |
| Python/uv setup in CI | manual pip installs | `astral-sh/setup-uv@v10` + `uv sync --locked` | Lockfile-exact, cached |

**Key insight:** in this phase the subtle part is not plumbing but **time semantics**. Every hand-rolled shortcut, such as computing the cutoff on the fly, trusting a stored column, or relying on row order, is a look-ahead leak that ordinary tests will not notice.

## Common Pitfalls

### Pitfall 1: FastF1 fails silently and returns partial data
**What goes wrong:**
- `Session.load()` wraps every sub-loader in `@soft_exceptions`, so errors become warnings and attributes stay unset. `session.laps` then raises `DataNotLoadedError` [VERIFIED: core.py, logger.py; CITED: issue #916, #978].
- A Jolpica 429 is raised as `ErgastInvalidRequestError` *inside* that wrapper. Results, grid and lap-1 times then go silently missing [VERIFIED: ergast/interface.py `_get`].
- In 3.9.0a0, `F1AuthError` is **not** a `FastF1CriticalError`, so auth failures may also be swallowed [VERIFIED: 3.9.0a0 exceptions.py].
- The stage-2 cache wrapper can call `exit()`, which raises `SystemExit`, when a loader returns `None` [VERIFIED: req.py].

**How to avoid:** after load, validate:
- laps are non-empty;
- 18–22 entries;
- grid present for starters;
- lap-1 times present;
- track status and weather non-empty.

Any gap means the race failed, so it is retried next run. Wrap each race in `except (Exception, SystemExit)` but re-raise `KeyboardInterrupt`. Set `fastf1.set_log_level("ERROR")` so D-14 gets clean progress lines.
**Warning signs:** "Failed to load …" log lines; `DataNotLoadedError`; NaN grid.

### Pitfall 2: Rate limits differ by source and by FastF1 version
**What goes wrong:**
- **FastF1 3.8.3:** a hard limit of 500 calls/h across "any API" (including api.jolpi.ca), with a 0.25 s minimum interval. Exceeding it raises `fastf1.exceptions.RateLimitExceededError`, a subclass of `FastF1CriticalError`/`RuntimeError`; import it from `fastf1.exceptions` [VERIFIED: req.py; CITED: changelog 3.8.0].
- **FastF1 3.9.0a0:** adds 200 calls/h for `*.jolpi.ca` [VERIFIED: source]. The limiter is an in-process sliding window, so restarting the process resets it, but the servers' limits remain.
- **OpenF1 free tier:** 3/s and 30/min [CITED].
- **Jolpica:** 4/s and 500/h, returning HTTP 429 "Request was throttled". IPs shared with other users can trigger it [CITED].

**How to avoid:**
- OpenF1: pace requests at ≥2.1 s each.
- On 429, honour `Retry-After` if present [ASSUMED header], otherwise use exponential backoff.
- FastF1: on `RateLimitExceededError`, print a wait message and sleep about 15 min, then retry the same race up to N times.
- Make `sleep` and `now` injectable so tests run instantly.

### Pitfall 3: Two "lap N" views get mixed up, plus the final-lap gap
**What goes wrong:** Developers assume "as of lap 15" shows 15 laps for every car. Under D-01, non-leaders show ≤ 14. The plot at "final lap" also drops every non-winner's last lap.
**How to avoid:** use the `RACE_END` sentinel for the plot. Put per-car `laps_completed` in the snapshot. Write a docstring and DECISIONS entry. Add a unit test on synthetic data that checks P2 is at N−1 at cutoff N.

### Pitfall 4: NaN vs NULL vs NaT at the pandas→DuckDB boundary
**What goes wrong:**
- FastF1 uses `float64` for integer-like columns (`LapNumber`, `Stint`, `TyreLife`, `Position`) and `timedelta64[ns]` with NaT for times [VERIFIED: Laps._COLUMNS].
- Whether DuckDB stores a pandas float `NaN` as NULL or as NaN is not confirmed in current docs [ASSUMED]. The two behave differently in comparisons.

**How to avoid:**
- Convert times to float seconds and integers to `Int64`.
- Normalize missing values explicitly with nullable dtypes in `schema.normalize()`.
- Write the filter as `visible_at_s IS NOT NULL AND visible_at_s <= ?`.
- Add a round-trip test asserting `IS NULL` counts.

### Pitfall 5: Windows-specific CI and dev breakage
**What goes wrong:**
- An open DuckDB connection blocks other processes, and same-process connections with different `read_only` flags fail.
- `tmp_path` cleanup can error on locked files.
- `core.autocrlf=true` is set system-wide on this machine [VERIFIED: git config], so line endings can churn under `ruff format --check`.
- Non-ASCII event names (`São Paulo`) can hit cp1252 when output is redirected [ASSUMED].
- The Microsoft Store `python` stub is first on PATH [VERIFIED: `command -v python`].

**How to avoid:**
- Context-managed, short-lived connections, closed before the next open.
- Writer closed before reader in tests.
- `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)` in property tests.
- `.gitattributes` with `* text=auto eol=lf`.
- `PYTHONUTF8=1` in CI env.
- `uv python install 3.12` plus a `.python-version` file, and always `uv run …`, never bare `python`.

### Pitfall 6: Hypothesis flakiness and health checks
**What goes wrong:** Locally the default `deadline` is 200 ms; DuckDB file I/O on Windows exceeds it. Using the function-scoped `tmp_path` fixture inside `@given` trips the `function_scoped_fixture` health check. The `.hypothesis/` example database appears in the working directory [CITED: hypothesis API docs].
**How to avoid:** `@settings(deadline=None)` on DB-touching properties; create temp dirs inside the test body; gitignore `.hypothesis/`. CI automatically uses the `ci` profile (`derandomize=True`), so CI runs are reproducible [CITED].

### Pitfall 7: Event names are not circuits, and rounds renumber after cancellations
**What goes wrong:**
- 2026 "Bahrain Grand Prix" was held at **Kuala Lumpur** ("FORMULA 1 GULF AIR BAHRAIN GRAND PRIX IN MALAYSIA 2026") [VERIFIED: OpenF1 meetings].
- 2026 has both "Barcelona" and "Spanish (Madrid)" GPs [VERIFIED: schedule].
- Cancelled events are removed and later rounds renumbered in FastF1's schedule. OpenF1 keeps them with `is_cancelled=true` and has **no round number** [VERIFIED].

**How to avoid:**
- Slugs are `<event-slug>-<season>`, ASCII-folded.
- Track identity uses circuit/location, never the event name.
- For Option B, take the round from the Jolpica season schedule matched by date, or the date rank among non-cancelled races.
- Skip `is_cancelled` sessions and any race whose start time plus a margin of about 6 h [ASSUMED margin] is later than `now`.

### Pitfall 8: pandas / numpy / stubs version drift
**What goes wrong:** If FastF1 is in the tree, uv must use pandas 2.3.3. Unpinned `pandas-stubs` resolves to 3.x and mypy then checks against the wrong API. NumPy 2.5 deprecates unit-less `np.timedelta64`, and pandas internals still trigger that warning [CITED: FastF1 PR #945]. Whether pandas 2.3.3 (Sept 2025) is fully clean on NumPy 2.5 is unverified [ASSUMED].
**How to avoid:**
- Pin `pandas-stubs>=2.3.3,<3`.
- Escalate warnings to errors only for our own code: `filterwarnings = ["error::DeprecationWarning:f1si"]`.
- If NumPy 2.5 causes real failures, pin `numpy<2.5` and log it.

### Pitfall 9: mypy strict with an untyped FastF1
**What goes wrong:** FastF1 ships no `py.typed` [VERIFIED: sdist has none], so `import fastf1` errors (`import-untyped`), and `warn_return_any` flags every value passed through.
**How to avoid:** a `[[tool.mypy.overrides]] module = ["fastf1", "fastf1.*"]` with `ignore_missing_imports = true`. Confine FastF1 to one adapter that converts to typed `pd.DataFrame` through explicit constructors or casts. DuckDB is typed [VERIFIED]. requests needs `types-requests`.

### Pitfall 10: Scheduled workflows and caches on a public repo
**What goes wrong:**
- GitHub disables scheduled workflows in public repos after 60 days without repository activity [CITED: docs.github.com disable-and-enable-workflows].
- Uploading the DuckDB file or raw cache as an **artifact** effectively republishes raw data; public-repo artifacts are downloadable [ASSUMED].
- The FastF1 stage-2 cache is **pickle** [VERIFIED: req.py], so restoring an untrusted cache is code execution.

**How to avoid:** Use `actions/cache` (repo-scoped), not artifacts, for raw data. Upload only derived PNGs. Keep real-data runs non-blocking with `continue-on-error`. Mention in the explainer that the weekly job may need re-enabling.

### Pitfall 11: Pre-commit ruff drifts from CI ruff
**What goes wrong:** The hook's `rev` and the `uv.lock` ruff version differ, so the commit hook formats differently from CI.
**How to avoid:** pin `ruff==0.17.1` in the dev group, match the hook `rev: v0.17.1`, and log the rule: "bump both together".

### Pitfall 12: The scramble harness itself has a false negative
**What goes wrong:** Garbage values could equal the originals by chance. The harness might also scramble only `laps`, leaving weather and track status unchecked.
**How to avoid:** Garbage is guaranteed different: numeric values offset by ≥ 1e3 or set to NaN; strings get a `"JUNK-"` prefix. Make the harness iterate over **every** table in `schema.TABLES` with a visibility column. The meta-test proves detection for at least one non-laps table too, for example a leaky weather consumer.

## Code Examples

### `pyproject.toml` (core; Option-specific lines marked)
```toml
# Source: uv init docs (uv_build backend), pytest 9 native TOML, mypy/ruff docs
[project]
name = "f1si"
version = "0.1.0"
description = "F1 Stochastic Intelligence Platform"
readme = "README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
  "numpy>=2.3,<3",
  "pandas>=2.3.3,<3",
  "duckdb>=1.5.6,<2",
  "matplotlib>=3.11,<4",
  "requests>=2.34,<3",          # Option B
  "requests-cache>=1.3,<2",     # Option B
  # "fastf1==3.9.0a0",          # Option A
]

[project.scripts]
f1si = "f1si.cli:main"

[build-system]
requires = ["uv_build>=0.13.4,<0.14"]
build-backend = "uv_build"

[dependency-groups]
dev = [
  "pytest>=9.1,<10", "hypothesis>=6.170", "ruff==0.17.1", "mypy>=2.4,<3",
  "pandas-stubs>=2.3.3,<3", "types-requests", "pre-commit>=4.7", "pytest-cov>=7.1",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "NPY", "RUF", "SIM", "PT", "N"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["src", "tests"]

[[tool.mypy.overrides]]
module = ["fastf1", "fastf1.*"]
ignore_missing_imports = true

[tool.pytest]
minversion = "9.0"
testpaths = ["tests"]
addopts = ["-ra", "--strict-markers", "-m", "not network"]
markers = ["network: needs internet and a real data source; excluded by default"]
filterwarnings = ["error::DeprecationWarning:f1si"]
```

### Transactional per-race write (only in `f1si/data/_db.py`)
```python
# Source pattern: DuckDB docs — delete+insert in a transaction; INSERT ... BY NAME
import duckdb
import pandas as pd

RACE_TABLES: tuple[str, ...] = ("entries", "laps", "track_status", "session_status",
                                "weather", "lap_cutoffs", "results")  # constants only

def write_race(con: duckdb.DuckDBPyConnection, race_id: str,
               tables: dict[str, pd.DataFrame], race_row: pd.DataFrame) -> None:
    con.begin()
    try:
        for name in RACE_TABLES:  # table names never come from user input
            con.execute(f"DELETE FROM {name} WHERE race_id = ?", [race_id])
            con.register("incoming", tables[name])
            con.execute(f"INSERT INTO {name} BY NAME SELECT * FROM incoming")
            con.unregister("incoming")
        con.execute("DELETE FROM races WHERE race_id = ?", [race_id])
        con.register("incoming", race_row)          # completion marker written last
        con.execute("INSERT INTO races BY NAME SELECT * FROM incoming")
        con.unregister("incoming")
        con.commit()
    except BaseException:
        con.rollback()
        raise
```

### As-of query shape (inside `asof.py`, through `_db` helpers)
```python
# cutoff resolution reads ONLY the lap-N row of the precomputed table
CUTOFF_SQL = "SELECT cutoff_s FROM lap_cutoffs WHERE race_id = ? AND lap = ?"
VISIBLE_LAPS_SQL = """
SELECT * EXCLUDE (visible_at_s) FROM laps
WHERE race_id = ? AND visible_at_s IS NOT NULL AND visible_at_s <= ?
ORDER BY driver_number, lap_number
"""
# RACE_END: same query without the time predicate. Results are never queried here.
```

### Import-scan core
```python
# Source: Python stdlib ast docs; policy is the single table in tests/guards/import_scan.py
import ast
from pathlib import Path

def imported_names(tree: ast.Module, module: str, is_pkg: bool) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    pkg_parts = module.split(".") if is_pkg else module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base_parts = pkg_parts[: len(pkg_parts) - (node.level - 1)] if node.level else []
            base = ".".join([*base_parts, *(node.module.split(".") if node.module else [])])
            out.append((base, node.lineno))
            out += [(f"{base}.{a.name}", node.lineno) for a in node.names]
        elif (isinstance(node, ast.Call) and node.args
              and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
              and ((isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
                   or (isinstance(node.func, ast.Name) and node.func.id == "__import__"))):
            out.append((node.args[0].value, node.lineno))
    return out
```

### Future-scramble property test (shape)
```python
from hypothesis import given, settings, strategies as st

@settings(deadline=None, max_examples=25)
@given(lap=st.integers(min_value=0, max_value=SYN_LAPS), seed=st.integers(0, 2**63 - 1))
def test_snapshot_ignores_future(dataset: Dataset, lap: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    for consumer in CONSUMERS:                       # registry in tests/guards/consumers.py
        assert_no_lookahead(consumer, dataset, AsOf(CURRENT_RACE, lap), rng=rng)
```
Note: `dataset` must be a **module- or session-scoped** fixture that is built once, otherwise hypothesis raises the function-scoped-fixture health check.

### Plot without pyplot
```python
# Source: matplotlib 3.11 "embedding in a web application server" guidance
from matplotlib.figure import Figure

def render_stint_plot(data: StintPlotData, out: Path) -> Path:
    ncols = 5
    nrows = -(-len(data.drivers) // ncols)
    fig = Figure(figsize=(4 * ncols, 2.8 * nrows), layout="constrained")
    axes = fig.subplots(nrows, ncols, sharex=True, sharey=True, squeeze=False)
    for ax, drv in zip(axes.flat, data.drivers, strict=False):
        for row in data.points_for(drv):   # x=lap, y=lap_time_s, compound, faded
            ...
    for ax in list(axes.flat)[len(data.drivers):]:
        ax.set_visible(False)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    return out
```

### `.github/workflows/ci.yml`
```yaml
name: CI
on: [push, pull_request]
concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }
jobs:
  checks:
    strategy:
      fail-fast: false
      matrix: { os: [ubuntu-latest, windows-latest] }
    runs-on: ${{ matrix.os }}
    env: { PYTHONUTF8: "1" }
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10
        with: { python-version: "3.12", enable-cache: true }
      - run: uv sync --locked
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy
      - run: uv run pytest --cov=f1si --cov-report=term
```

### `.github/workflows/real-data.yml` (non-blocking)
```yaml
name: Real data (non-blocking)
on:
  schedule: [{ cron: "17 6 * * 1" }]
  workflow_dispatch:
jobs:
  bahrain-2023:
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10
        with: { python-version: "3.12", enable-cache: true }
      - uses: actions/cache@v6
        with: { path: data/http-cache, key: real-data-bahrain-2023-v1 }
      - run: uv sync --locked
      - run: uv run pytest -m network -v
```
(Option A: drop this workflow or make it `workflow_dispatch`-only with a clear "requires F1 TV; run locally" note. The download cannot work from CI.)

### `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.17.1          # keep equal to ruff in uv.lock
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
```

### `.gitignore` / `.gitattributes` essentials
```
# .gitignore
.venv/
data/
reports/
desktop.ini
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.hypothesis/
.coverage
htmlcov/
*.duckdb
*.duckdb.wal

# .gitattributes
* text=auto eol=lf
*.png binary
*.duckdb binary
```
(If the user wants the Bahrain PNG in the README, copy it into `docs/img/`. That is a derived plot, not raw data.)

### PowerShell bootstrap for the owner (copy-paste)
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# close and reopen the terminal so `uv` is on PATH
uv python install 3.12
cd $HOME\Documents\f1si
uv sync
uv run pre-commit install
uv run f1si load --source synthetic   # works offline
uv run f1si load                      # real data (after the source decision)
uv run f1si plot bahrain-2023
git remote add origin https://github.com/Befithalo/F1-Stochastic-Program.git
git push -u origin main               # Git Credential Manager opens a browser login
```
[CITED: uv installation docs for the installer command; ASSUMED that a terminal restart is needed for PATH]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free unauthenticated F1 live-timing archive (FastF1 ≤ 3.8.3) | Archive requires F1 TV token; FastF1 3.9.0a0 adds sign-in | 2026-10-15 / 2026-10-18 | Phase 1 source decision; CI cannot download from F1 |
| F1 live timing reachable from cloud/CI IPs | Datacenter IPs blocked | ~May 2026 | FastF1's own CI moved to frozen test data (PR #963) |
| `fastf1.Cache.enable_cache(dir)` | `fastf1.Cache.configure(cache_dir=...)`; `enable_cache` deprecated | 3.9.0a0 | Option A uses `configure` |
| `from fastf1 import RateLimitExceededError` | `from fastf1.exceptions import RateLimitExceededError` | 3.8.0 | Old import removed two minor releases after deprecation |
| DuckDB 1.x storage | DuckDB 2.0 storage (1.x can't read it) | 2026-10-21 | Pin `<2` now; one-way upgrade later |
| mypy 1.x defaults | mypy 2.x: local-partial-types and strict-bytes on, native parser default (2.4) | 2.0–2.4 | Minor; strict config unchanged |
| `[tool.pytest.ini_options]` strings | `[tool.pytest]` native TOML | pytest 9.0 | Use native table |
| ruff-pre-commit hook id `ruff` | `ruff-check` | ruff-pre-commit README | Use `ruff-check` |

**Deprecated/outdated:**
- FastF1 3.8.3 for **new** downloads: it now gets 401. It still works offline against an existing warm cache, which this project does not have.
- The FastF1 dev-docs sentence that post-session data needs no login is outdated, per the maintainer.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OpenF1 is reachable from GitHub-hosted runners (no datacenter IP block) | Data Source, CI | Weekly real-data job fails; it is non-blocking, so low impact |
| A2 | F1 TV Access price/terms (cost varies; automated access may conflict with ToS) | Data Source Option A | User cost or ToS exposure; user must check |
| A3 | DuckDB stores pandas float NaN as NULL (or not) — unverified | Pitfall 4 | Wrong visibility for NaN rows. Mitigated by explicit normalization + round-trip test |
| A4 | pandas 2.3.3 works cleanly with NumPy 2.5.x | Stack, Pitfall 8 | Import/deprecation errors. Fallback: pin `numpy<2.5` |
| A5 | NPY002 does not flag `np.random.RandomState` | Pattern 5/7 | Only redundancy; the AST ban covers it |
| A6 | OpenF1 returns `Retry-After` on 429 | Pitfall 2 | Fall back to exponential backoff |
| A7 | Race "completed" margin ≈ 6 h after scheduled start is enough for data availability | Pitfall 7 | A just-finished race fails once and is retried next run |
| A8 | Jolpica/Ergast `grid = 0` means pit-lane start | Pattern 1 (`entries`) | Grid misread for pit-lane starters; verify on a known case |
| A9 | Public-repo artifacts are downloadable by others | Pitfall 10 | Already avoided by never uploading raw data |
| A10 | FastF1 'Started' session status ≈ formation-lap start, not lights out | Pattern 2 (lap 0) | Lap-0 cutoff a few minutes early: safe direction |
| A11 | `uv` skips the Microsoft Store python stub during interpreter discovery | Environment | Explicit `uv python install 3.12` + `.python-version` sidesteps it |
| A12 | PowerShell PSReadLine history stores `$env:F1_PASSWORD = ...` lines | Option A security | Password exposure; use the interactive auth prompt instead |
| A13 | matplotlib ships `py.typed` (no stubs needed) | Stack | Minor mypy override if wrong |
| A14 | OpenF1 lap-1 `date_start` equals lights-out for all cars (observed for Bahrain 2023 only) | Pattern 2 (Option B lap 0) | Lap-0 cutoff slightly off. Validate on more races |

## Open Questions (RESOLVED)

All five were resolved with the user on 2026-10-22. See 01-CONTEXT.md.

1. **Data source (blocks SC2/SC3).** RESOLVED: D-08 (revised). OpenF1 + Jolpica; D-10 revised to match.
   - What we know: FastF1 needs F1 TV plus an alpha release. OpenF1 and Jolpica are free and working.
   - What's unclear: the user's preference, and whether they already have F1 TV.
   - Recommendation: `checkpoint:decision` before the adapter plan; default to Option B. Revise D-08 and D-10 in DECISIONS.md.
2. **Do "earlier races in full" (D-04) include their final classifications?** RESOLVED: D-04 (revised). Yes.
   - What we know: D-04 says "in full"; D-03's concern is the *current* race's outcomes.
   - Recommendation: yes. Expose earlier races' `results` in `history()`, since they are past facts. Log it, and confirm with the user at plan review.
3. **`RACE_END` cutoff for the plot.** RESOLVED: D-16 (revised). Race-end cutoff in the as-of door.
   - What we know: D-16 says "at the final lap", which hides each non-winner's last lap.
   - Recommendation: add `RACE_END` to the as-of door, log it, and mention it to the user.
4. **`scheduled_laps` (Phase 2 needs `laps_total`).** RESOLVED: nullable column in Phase 1 and never filled from post-race lap counts; Phase 2 decides the source.
   - What we know: FastF1's `total_laps` takes the *last* `TotalLaps` value, which may be revised mid-race [VERIFIED: core.py]. OpenF1 has no scheduled-laps field.
   - Recommendation: nullable column now; Phase 2 decides. Never fill it from the winner's completed laps, which is a post-race fact.
5. **Commit `F1 Docs/`?** RESOLVED: D-18. Commit it, and gitignore desktop.ini.
   - What we know: the folder is untracked; the canonical refs point to it.
   - Recommendation: ask the user. The BUILD_PLAN text is the user's own document, so committing it is fine if they agree.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | everything | ✗ | — (latest 0.13.5) | Install via PowerShell one-liner or `winget install --id=astral-sh.uv -e` [CITED] |
| Python 3.12 | runtime | ✗ (only the MS Store stub on PATH) | — | `uv python install 3.12` |
| Git for Windows | VCS, push | ✓ | 2.55.0.windows.5; `core.autocrlf=true`; credential helper `manager` | — |
| gh CLI | not required | ✗ | — | Git Credential Manager handles the push login |
| GitHub remote | D-12 | ✓ (empty, `git ls-remote` returned nothing) | — | — |
| Node.js | not required | ✓ | v24.20.0 | — |
| OpenF1 API | Option B ingest | ✓ (HTTP 200, 2026-10-22) | v1 | Jolpica covers results/grid/pit stops |
| Jolpica API | grid/results | ✓ (HTTP 200) | ergast-compatible | — |
| F1 live-timing archive | Option A ingest | ✗ without F1 TV token (HTTP 401) | — | Option B |
| FastF1 mirror | Option A fallback | ✗ (HTTP 404 for 2023-2026) | — | — |
| slopcheck | package audit | ✗ (no Python) | — | All packages [ASSUMED]; one human-verify checkpoint |
| `GSD_WORKSTREAM=voice` env var | gsd tooling | stale (set) | — | Run gsd-sdk with it unset |

**Missing dependencies with no fallback:**
- None for the source-agnostic work. For real data, a source decision is required (see Open Question 1).

**Missing dependencies with fallback:**
- uv and Python: install via uv (first plan task, with copy-paste PowerShell).
- F1 archive: OpenF1 + Jolpica (Option B) or F1 TV + FastF1 3.9.0a0 (Option A).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x + hypothesis 6.170.x (+ pytest-cov advisory) |
| Config file | `pyproject.toml` `[tool.pytest]` — none yet (Wave 0) |
| Quick run command | `uv run pytest -x -q` (synthetic only, target < 30 s) |
| Full suite command | `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run pytest` |
| Real-data command (not in push CI) | `uv run pytest -m network -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FND-01 | Package imports; `f1si --help` exits 0; ruff and mypy configured and clean | smoke | `uv run pytest tests/test_smoke.py` + `uv run mypy` | ❌ Wave 0 |
| FND-02 | CI runs lint/format/type/test on ubuntu and windows and is green | CI observation | GitHub Actions `CI` run on push (verifier checks run status) | ❌ Wave 0 (`.github/workflows/ci.yml`) |
| FND-03 | Same seed → identical synthetic dataset; different seed → different; no legacy RNG in src | unit + guard | `uv run pytest tests/test_rng.py tests/guards/test_import_ban.py` (+ ruff NPY002) | ❌ Wave 0 |
| FND-04 | `DECISIONS.md` exists and contains the required entries (D-01..D-04, D-08, D-09, era) | doc test | `uv run pytest tests/test_decisions_log.py` | ❌ Wave 0 |
| DAT-01 | Loader writes all tables transactionally; resumes (2nd run skips); retries on rate limit (fake clock); lists failures; synthetic source end to end | integration | `uv run pytest tests/data/test_loader.py tests/data/test_db_roundtrip.py` | ❌ Wave 0 |
| DAT-01 (real) | Bahrain 2023: 20 entries, max lap 57, ~1,050–1,100 lap rows, compounds ⊆ {SOFT, MEDIUM, HARD}, VSC around lap 41, VER grid 1 | integration (network) | `uv run pytest -m network tests/real/test_bahrain_2023.py` | ❌ |
| DAT-02 | Plot data classes (clean/faded) are correct; PNG written; panel count = drivers; `--drivers` narrows | unit + integration | `uv run pytest tests/plots/test_stint_plot.py tests/test_cli.py::test_plot_command` | ❌ |
| DAT-03 | Snapshot at lap N contains only rows ≤ cutoff; leader has N laps, P2 has N−1; lap 0 has pre-race facts only; RACE_END has all laps and no results; history = earlier races only; 2026 raises | unit | `uv run pytest tests/data/test_asof.py` | ❌ |
| DAT-04 | Import scan of `src/f1si` is empty; future-scramble identical for every consumer and lap (hypothesis); meta-test: both detectors catch `tests/fixtures/leaky_consumer.py`, scramble catches the through-accessor leak | guard | `uv run pytest tests/guards` | ❌ |
| DAT-05 | `era_for_season` mapping; unknown season raises; every `races` row has an era; 2026 → out_of_sample; `f1si races` prints era | unit | `uv run pytest tests/test_eras.py tests/test_cli.py::test_races_lists_era` | ❌ |
| UI-03 | `docs/explained/phase-01.md` exists with the four D-17 sections | doc test | `uv run pytest tests/test_docs.py` | ❌ |

### Success Criteria → Verification
| SC | How verified | Where |
|----|--------------|-------|
| 1 CI green on push | GitHub Actions run status for the pushed commit on both OSes | push CI |
| 2 One command → 2023-2025 data in DuckDB | `uv run f1si load` (manual, real source) + `test_loader.py` (synthetic) + network test | local / real-data workflow |
| 3 Bahrain 2023 plot | `uv run f1si plot bahrain-2023` → `reports/bahrain-2023.png` (manual look) + plot tests | local + push CI (synthetic) |
| 4 No future rows; leaky case fails the build | `tests/guards/*` + optional canary step | push CI |
| 5 Era shown, 2026 out-of-sample, seed reproducibility, DECISIONS.md | `test_eras.py`, `test_rng.py`, `test_decisions_log.py`, `uv run f1si races` | push CI + manual |

### Sampling Rate
- **Per task commit:** `uv run pytest -x -q` (pre-commit runs ruff automatically)
- **Per wave merge:** full suite command above
- **Phase gate:** push CI green on ubuntu and windows, plus one local real-data run (`uv run f1si load`, `uv run f1si plot bahrain-2023`, `uv run pytest -m network`) before `/gsd:verify-work`

### What runs where
| Check | Push CI (every push) | Weekly/manual real-data workflow | Local only |
|-------|----------------------|----------------------------------|------------|
| ruff, format, mypy | ✓ | — | pre-commit (ruff) |
| Synthetic unit/integration/guard tests | ✓ (no network) | — | ✓ |
| `-m network` Bahrain 2023 tests | — | ✓ (Option B; non-blocking) | ✓ (required under Option A) |
| Full multi-season load | — | — | ✓ (`uv run f1si load`) |

### Wave 0 Gaps
- [ ] `pyproject.toml`, `uv.lock`, `.python-version`, `src/f1si/__init__.py` — scaffold (FND-01)
- [ ] `tests/conftest.py` — synthetic dataset fixture (3 in-sample races + 1 locked 2026 race), scoped to the session or module
- [ ] `src/f1si/synthetic/` generator (needed before any data test)
- [ ] `tests/guards/{import_scan,scramble,consumers}.py` + `tests/fixtures/leaky_consumer.py`
- [ ] `.github/workflows/ci.yml` (FND-02), `.pre-commit-config.yaml` (D-13)
- [ ] Framework install: `uv sync` (after `uv` and Python 3.12 are installed)

## Security Domain

`security_enforcement` is absent from config, so it is treated as enabled.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Only Option A (F1 account) | Interactive `python -m fastf1 auth f1tv --authenticate`; never commit, log or echo credentials; no CI secrets for F1 TV |
| V3 Session Management | Only Option A | FastF1 token store in the user data dir; `--clear` to revoke |
| V4 Access Control | yes (internal) | The "doors" plus the import ban are an access-control design for data, not users |
| V5 Input Validation | yes | Validate CLI args (season ints in range, slug matched against the catalog, driver codes against entries); validate API responses in `schema.validate` (types, ranges, key uniqueness) |
| V6 Cryptography | no | — (never hand-roll) |
| V10/V14 Config & supply chain | yes | `uv.lock` (hash-pinned) with `uv sync --locked` in CI; actions at major tags (SHA pinning optional); one human-verify of the dependency list |
| V12 Files | yes | Output paths built from catalog slugs, never raw user strings; `data/` and `reports/` gitignored |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection through slug/driver args | Tampering | DuckDB parameter binding (`?`); table names only from constants [CITED: dbapi "Pass values separately from the SQL text"] |
| Credential leak (Option A) in shell history, logs or CI | Information disclosure | Interactive prompt; never log the env; no F1 TV secrets in a public repo |
| Pickle deserialization from a restored FastF1 cache | Elevation of privilege | Only restore caches produced by this repo's own workflows; never import cache folders from strangers |
| Raw data republished through artifacts or commits | Repudiation / licensing | `data/` gitignored; `actions/cache` not artifacts; only derived PNGs leave the machine |
| Dependency confusion / typosquat | Tampering | Lockfile, exact well-known names, human verification (slopcheck unavailable) |
| Look-ahead leak (integrity of results) | Tampering (of evaluation) | Import ban + future-scramble + meta-test + canary, as CI gates |

## Sources

### Primary (HIGH confidence)
- FastF1 3.8.3 and 3.9.0a0 sdists (read locally): `req.py` (Cache, rate limits, `exit()` paths), `core.py` (Laps/SessionResults columns, lap-start logic, track-status-to-lap rule, deleted-lap look-ahead pass, retired-lap generation, accuracy check), `_api.py` (time column types, mirror URL), `events.py` (schedule backends), `exceptions.py`, `plotting/constants.json`, `internals/f1account/*`
- github.com/theOehrly/Fast-F1 issues #978, #916, #917; PRs #981, #963, #945; release notes v3.9.0-a0, v3.8.x; docs.fastf1.dev/changelog
- Direct probes (2026-10-22): livetiming.formula1.com (401), livetiming-mirror.fastf1.dev (404), api.openf1.org (sessions, laps, stints, pit, race_control, weather, session_result, drivers, position, meetings), api.jolpi.ca (results, pitstops), raw.githubusercontent.com/theOehrly/f1schedule (2023, 2026)
- PyPI JSON API (versions, dates, requires_dist): fastf1, duckdb, pandas, numpy, matplotlib, pytest, hypothesis, ruff, mypy, pandas-stubs, pre-commit, pytest-cov, requests, requests-cache, types-requests, import-linter, uv
- duckdb.org: 2.0 announcement and preview; docs 2.0 concurrency, Python DB-API, indexes, INSERT
- docs.astral.sh: uv project init, installation, resolution (pre-releases, universal lock); ruff NPY002
- github.com/astral-sh/setup-uv README; github.com/astral-sh/ruff-pre-commit README; GitHub releases API for actions versions
- numpy.org parallel RNG docs (v2.5); matplotlib 3.11.2 web-application-server example; hypothesis API reference; docs.pytest.org customize
- openf1.org (tiers, limits, terms); github.com/jolpica/jolpica-f1 docs/rate_limits.md

### Secondary (MEDIUM confidence)
- import-linter docs (forbidden/protected contracts), via search results and the protected-contract page
- docs.github.com: disabling scheduled workflows after 60 days in public repos
- mypy changelog 2.0–2.4
- F1 2026 regulations coverage: formula1.com FIA article, si.com, racer.com (search results)
- 2026 calendar changes: planetf1.com, the-race.com, crash.net (search results)

### Tertiary (LOW confidence)
- DuckDB NaN→NULL behaviour (search found nothing authoritative)
- pandas 2.3.3 × NumPy 2.5 compatibility (no direct evidence)
- Windows DuckDB lock error wording (forum posts)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH. Versions verified on PyPI today; pins justified by verified `requires_dist`.
- Data source facts: HIGH (direct probes plus maintainer statements). Path forward: LOW until the user decides.
- Architecture (schema, doors, cutoffs, guards): HIGH for the reasoning, checked against FastF1 source and real OpenF1 timing data. Policy details are recommendations.
- Pitfalls: HIGH for the FastF1/DuckDB/hypothesis items (source or docs); MEDIUM for the Windows items.
- CI: HIGH (official READMEs, latest tags).

**Research date:** 2026-10-22
**Valid until:** 2026-10-29 for the data-source section (fast-moving: FastF1 3.9 alpha, F1 auth rollout, DuckDB 2.0.1 due in November). About 30 days for everything else.
