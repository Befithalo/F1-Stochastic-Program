# Walking Skeleton — F1 Stochastic Intelligence Platform (f1si)

**Phase:** 1
**Generated:** 2026-10-22
**Skeleton plans:** 01-01 (bootstrap: scaffold, dependency approval, uv install), 01-02 (part A: toolchain, failing end-to-end test, leaf modules, schema, DuckDB storage, RaceSource protocol) and 01-03 (part B: synthetic generator and source, loader, catalog, `f1si load` / `f1si races`, first push with CI green). Plans 01-04..01-11 add vertical slices on top without changing the decisions below. Plans run one at a time on `main` in the owner's checkout (workflow.use_worktrees=false).

## Capability Proven End-to-End

> From a fresh clone on Windows or Linux, `uv run f1si --data-dir <folder> load --source synthetic` writes four seeded synthetic races into a DuckDB file, `uv run f1si --data-dir <folder> races` reads them back and shows each race's regulation era (2026 flagged out-of-sample and locked), and the same lint, type-check and test run is green in GitHub Actions on ubuntu-latest and windows-latest after a push to `main`.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language / runtime | Python 3.12 managed by uv (`.python-version` = 3.12, `requires-python = ">=3.12,<3.13"`), `uv_build` backend, `src/` layout, package `f1si` | Locked stack (CLAUDE.md). uv installs Python itself, sidestepping the Microsoft Store `python` stub on the owner's machine |
| Entry point ("routing") | One argparse CLI: console script `f1si = "f1si.cli:main"`, `main(argv: Sequence[str] \| None = None) -> int`, subcommands `load`, `races`, `plot`; global `--data-dir`, `--reports-dir`, `--debug`; also `python -m f1si` | D-14. argparse is stdlib and mypy-clean; three subcommands do not justify typer/click. Exit codes: 0 ok, 1 user-facing error (one line saying what to do next), 2 some races failed, 130 stopped with Ctrl+C (finished races kept; added in 01-08) |
| Data layer | One DuckDB 1.5.x file per data folder: `<data-dir>/f1si.duckdb` (default `data/`, env `F1SI_DATA_DIR`). Only `f1si.data._db` may `import duckdb`. One transaction per race (delete + `INSERT ... BY NAME`, `races` row written last as the completion marker). Times stored as DOUBLE seconds from lights-out (race clock t = 0). Every time-indexed table carries `visible_at_s`. One data folder holds one source (synthetic and real never mix) | DuckDB 2.0.0 is one day old and its files are unreadable by 1.x (DEC-011). Float seconds vectorize cleanly for Phase 3. The visibility column makes the look-ahead rule one generic predicate |
| Normalized schema (contract) | `f1si.data.schema.TABLES`: `races` (calendar), `entries` (pre-race facts), `laps`, `track_status`, `race_control`, `weather`, `lap_cutoffs` (time-indexed), `results` (results door only); SQL views `stints`, `pit_stops` over `laps`. Canonical pandas dtypes: INTEGER→`Int64`, DOUBLE→`Float64`, BOOLEAN→`boolean`, VARCHAR→object(str/None), TIMESTAMP→tz-naive UTC `datetime64[us]` | Every source (synthetic, OpenF1+Jolpica, a future FastF1) emits the same tables, so nothing downstream changes when a source is added (D-08) |
| Data access ("auth" for data) | Three doors: `f1si.data.asof` (as-of snapshots + history + catalog, public), `f1si.data.results` (final outcomes, importable only by `f1si.backtest.scoring`), `f1si.data.out_of_sample` (2026, importable only by `f1si.evaluation.holdout`). No `include_results`/`unlock` flags anywhere. Enforced by an AST import-ban test and a future-scramble property test, both proven by planted leaky fixtures and a CI canary | D-01..D-04, DAT-03, DAT-04. This is the project's core value: no code can read the future |
| User auth | None. Single local user; no secrets in the repo. GitHub push uses Git Credential Manager's browser sign-in on the owner's machine | Nothing to authenticate in a local CLI; OpenF1 and Jolpica need no key |
| Data sources | `RaceSource` Protocol in `f1si.data.sources` (`list_races(season, *, now)`, `fetch(ref) -> NormalizedRace`, `default_seasons`). Implementations: `SyntheticSource` (seeded, known truth, reused by later recovery tests) and `OpenF1Source` (OpenF1 laps/stints/race control/weather/drivers + Jolpica schedule/results/pit stops). All HTTP goes through `f1si.data.sources._http` (requests + requests-cache, JSON serializer). The CLI chooses and constructs the source from `--source` (a deliberate deviation from RESEARCH's responsibility map, logged in DECISIONS.md by plan 01-05) | D-08 (revised): F1's archive now returns 401 without F1 TV. D-09: CI runs on synthetic data only |
| Randomness | `f1si.rng.make_rng(seed)` is the only constructor; library functions take keyword-only `rng: np.random.Generator` with no default; independent streams via `Generator.spawn`; `DEFAULT_SEED = 20230305` | FND-03, DEC-013 |
| Deployment target | GitHub Actions `CI` workflow on every push/PR: `uv sync --locked`, `ruff check`, `ruff format --check`, `mypy` (strict, `src` + `tests`), `pytest` (synthetic only, `-m "not network"`), matrix ubuntu-latest + windows-latest, Python 3.12, `permissions: contents: read`. Separate weekly/manual `Real data (non-blocking)` workflow runs `pytest -m network`; it is non-blocking because it never runs on push/PR and is not a required check, and it writes its result to the run summary. Local full-stack run = the PowerShell commands in README.md | D-10, D-11, D-12. The "dev environment" for a CLI library is CI on both OSes |
| Directory layout | `src/f1si/{cli,paths,rng,eras}.py`, `src/f1si/data/{schema,errors,slugs,derive,_db,loader,asof,_snapshot,results,out_of_sample}.py`, `src/f1si/data/sources/{__init__,_http,jolpica,openf1,track_status_map,synthetic_source}.py`, `src/f1si/synthetic/`, `src/f1si/plots/`; tests mirror the package under `tests/` (packages with `__init__.py`), guards in `tests/guards/`, planted leaks in `tests/fixtures/`, network tests in `tests/real/`; `data/` and `reports/` gitignored | Research §Recommended Project Structure. Phase 2 adds `src/f1si/interfaces.py`; Phase 6 adds `f1si.backtest.scoring`; Phase 8 adds `f1si.evaluation.holdout` |
| Quality tooling | ruff 0.17.1 pinned in the dev group and in `.pre-commit-config.yaml` (bumped together), mypy strict, pytest 9 native `[tool.pytest]`, hypothesis, pytest-cov (advisory); `.gitattributes` `* text=auto eol=lf` | D-13, DEC-014; `core.autocrlf=true` is set system-wide on the owner's machine |
| Docs | `DECISIONS.md` (`## DEC-NNN — Title` + Date/Status/Context/Decision/Why/Alternatives rejected/Consequences/Refs), `docs/explained/phase-NN.md` per phase | FND-04, UI-03, D-17 |

## Stack Touched in Phase 1

- [ ] Project scaffold (uv + uv_build, ruff, mypy strict, pytest + hypothesis, pre-commit) — plans 01-01, 01-02
- [ ] Routing — `f1si load`, `f1si races` (01-03); `f1si plot` (01-09)
- [ ] Database — real write and read in `_db` (01-02), driven by the loader (`_db.write_race`) and `asof.catalog` via `f1si races` (01-03)
- [ ] UI — the CLI commands above: executor-run in 01-03 (synthetic, scratch `--data-dir`); the first owner-run check in PowerShell is 01-08's human-check (`uv run f1si races` on the real cache)
- [ ] Deployment — first push to `https://github.com/Befithalo/F1-Stochastic-Program` turns CI green on both OSes — 01-03; final green run — 01-11

## Out of Scope (Deferred to Later Slices)

Not in the skeleton (added later in Phase 1, in this order):

- Full race record: track status, race control, weather, results, lap cutoffs; resumable loading, retries, failure list (01-04)
- AST import ban, planted leak fixture, CI canary, DECISIONS.md first entries (01-05)
- Rate-limited HTTP client, Jolpica client, track-status mapping (01-06)
- As-of snapshot / history / RACE_END / 2026 lock, results and out-of-sample doors, future-scramble harness and meta-test (01-07)
- OpenF1 adapter, pit-lane start rule and `f1si load` defaulting to OpenF1 + Jolpica (01-08)
- Lap-time-by-stint plot (01-09)
- Real-data network tests, weekly workflow, full 2023-2026 load (01-10)
- Plain-language explainer, decision-log final pass, final push with CI green (01-11)

Not in Phase 1 at all: `interfaces.py` Protocols and `RaceState` (Phase 2), fuel correction and wear fitting (Phase 2), safety-car probability (Phase 3), holdout definition (Phase 8), qualifying sessions, 2022 season, authenticated FastF1, interactive plots (deferred ideas in 01-CONTEXT.md).

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: build a `RaceState` for Bahrain 2023 at any lap from an as-of snapshot; fuel-corrected linear wear per compound; brute-force 1/2-stop plan (adds `f1si/interfaces.py`)
- Phase 3: simulate 50,000 continuations from a `RaceState` in under 10 s (NumPy `SimulatorBackend`), using a safety-car rate fitted from the cached `track_status`
- Phase 4: Kalman tire-wear filter per car, verified on `f1si.synthetic` stints with known wear
- Phase 5: Longstaff-Schwartz pit valuation + CVaR ranking; lap-by-lap Bahrain 2023 replay driven by the as-of door
- Phase 6: 10-race walk-forward backtest (the only consumer of the results door), Streamlit page, README with measured results
- Phase 7: hierarchical Bayesian pace model with era effect (uses `eras` tags and synthetic recovery tests)
- Phase 8: Markov regime model fitted from cached `track_status`/`weather`, 20-race per-era backtest, holdout via the out-of-sample door
