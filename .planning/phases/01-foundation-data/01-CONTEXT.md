# Phase 1: Foundation & Data - Context

**Gathered:** 2026-10-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers four things:

- A uv-managed Python 3.12 `src/f1si` package, with ruff, mypy strict and pytest.
- GitHub Actions CI that runs green on push.
- One CLI command that fills a local DuckDB cache with Grand Prix race data from FastF1.
- A lap-time-by-stint plot for Bahrain 2023.

It also delivers a single as-of accessor that is the only way to read cached data, plus two CI checks that prove no code can see future rows. Every race carries a regulation-era tag; 2026 races are tagged out-of-sample and locked. All randomness flows through an explicit `np.random.Generator`. `DECISIONS.md` exists with its first entries. A plain-language explainer for the phase is written (UI-03).

Requirements: FND-01, FND-02, FND-03, FND-04, DAT-01, DAT-02, DAT-03, DAT-04, DAT-05, UI-03.

Not in this phase: Protocols/`RaceState` (Phase 2), fuel correction and wear fitting (Phase 2), safety-car probability (Phase 3), the holdout set definition (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### Look-ahead guard (core value of the project)
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

### What gets cached
- **D-05: Seasons are 2023, 2024, 2025, plus 2026.** 2026 races are tagged out-of-sample and locked behind the accessor (D-04). Load only 2026 races that have already happened; skip future rounds cleanly. 2022 is not loaded.
- **D-06: Sessions are Grand Prix races only.** No qualifying, sprints or practice. Grid position comes from the race results.
- **D-07: Beyond laps, stints, pit stops and results, also cache:**
  - per-lap/time-series **track status** (green, yellow, VSC, SC, red);
  - **weather**, at minimum rainfall and track temperature.

  Phase 3 fits the safety-car rate from this data and Phase 8 fits the regime model from it, so nothing needs re-downloading later.
- **D-08: Data source is FastF1 only.** FastF1 is MIT-licensed and already provides laps, stints, compound, tire age, pit in/out times, results, track status and weather. Design the cache tables so OpenF1 could feed them later (M6 live mode), but do not add OpenF1 now.

### CI and test data
- **D-09: Every push runs on synthetic data.** CI tests use small fake races generated in code with known values. CI makes no network calls and commits no real data, which honors BUILD_PLAN's "don't republish raw data". Build the generator so later phases' synthetic-recovery tests can reuse it.
- **D-10: A separate real-data workflow runs weekly and on manual trigger.** It downloads Bahrain 2023 through FastF1, ideally with the FastF1 cache saved between runs, and runs the real-data tests. It is not a required check, so FastF1 outages never block the main build. Real-data tests carry a pytest marker (e.g. `network`) and are excluded from the default run.
- **D-11: CI matrix is Linux + Windows, Python 3.12.** The user develops on Windows, and DuckDB file locking and paths behave differently there.
- **D-12: The repo is `https://github.com/Befithalo/F1-Stochastic-Program`.** It was verified on 2026-10-22: public, empty, no branches. Add it as `origin` and push `main`; the first push triggers CI. Roadmap success criterion 1 requires CI to be green.
- **D-13: Pre-commit hooks run ruff locally** (`ruff check --fix` + `ruff format`) on every commit. mypy and pytest run in CI.

### Commands, plot and walkthrough
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design source
- `F1 Docs/BUILD_PLAN.md` — the full design. Sections most relevant to Phase 1:
  - §Data, validity and honesty: the look-ahead rule, the 2026 break, hidden variables, data coverage, licensing and terms.
  - §Architecture: the `RaceState` JSON shape, whose `lap` semantics D-01 aligns with.
  - §Lean MVP, Week 1.
  - §Reusable resources: FastF1 is MIT, and do not copy LGPL TUMFTM code.
  - §Evaluation: StratBench and synthetic recovery tests.
- `F1 Docs/MASTER_PROMPT.md` — build brief and non-negotiables: seeded RNG, as-of accessor, synthetic tests, DECISIONS.md, 2026 out-of-sample, CI gate, plain-language explanations.

### Project planning
- `.planning/PROJECT.md` — constraints (stack, reproducibility, no look-ahead, quality gate) and audience (owner new to coding, portfolio for employers).
- `.planning/REQUIREMENTS.md` — FND-01..04, DAT-01..05, UI-03.
- `.planning/ROADMAP.md` §Phase 1 — five success criteria this phase must satisfy.

### External
- FastF1 documentation (https://docs.fastf1.dev): session loading, the `Laps` columns (`Time`, `LapStartTime`, `PitInTime`, `PitOutTime`, `TrackStatus`, `Compound`, `TyreLife`), track status, weather data, built-in caching and rate limits. No local copy.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None. The repo is greenfield: only `CLAUDE.md` and `.planning/` are tracked.

### Established Patterns
- None yet. This phase sets them: src layout, the `rng` argument convention, the accessor-only data access rule, synthetic fixtures, the CLI shape.

### Integration Points
- Phase 2's `RaceState` and the Protocols will consume the as-of accessor output. The accessor should return data shaped so a `RaceState` can be built from it at any lap.
- Phase 6's backtest scorer is the only planned consumer of the results door (D-03).

### Environment prerequisites (checked 2026-10-22)
- **uv is not installed.** uv can install Python 3.12 itself. The `python` on PATH is only the Microsoft Store placeholder.
- **GitHub CLI (`gh`) is not installed.** It isn't needed. Git for Windows' credential manager handles the browser login on first push.
- **The `GSD_WORKSTREAM=voice` environment variable is set** in the user's shell. It is stale and points GSD tools at a non-existent workstream. Run gsd-sdk with it unset, or have the user remove it.
- **`F1 Docs/` is untracked in git.** The planner should confirm with the user whether to commit it, so the canonical refs exist in the public repo.

</code_context>

<specifics>
## Specific Ideas

- The owner is new to coding. Commands must be copy-pasteable on Windows (PowerShell). Errors should say what to do next.
- Faded-not-removed slow laps (D-16): the user wants to see the true race with nothing hidden, while the clean tire-wear trend still stands out.
- The interview Q&A in the explainer (D-17) ties to BUILD_PLAN's risk "Interviewers probe a module you can't explain".

</specifics>

<deferred>
## Deferred Ideas

- **Qualifying sessions as a pace prior.** Revisit in Phase 7 (Bayesian pace model).
- **2022 season.** Revisit in Phase 7 if more training data is needed for the era effect. FastF1-only.
- **OpenF1 as a second source or cross-check.** M6 live mode, or earlier if FastF1 data quality issues appear.
- **Interactive plot (plotly).** The Phase 6 Streamlit view covers interactivity.
- **Paper notes in DECISIONS.md** (three ideas each from Heilmeier 2020 and RSRL, per BUILD_PLAN next steps). This is a reading task for the user, not code. It can be added to DECISIONS.md any time.

</deferred>

---

*Phase: 01-foundation-data*
*Context gathered: 2026-10-22*
