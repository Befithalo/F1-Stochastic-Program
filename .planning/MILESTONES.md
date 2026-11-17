# Milestones

## v1.0 M1 Core Stochastic Engine (Shipped: 2026-11-17)

**Phases completed:** 8 phases, 55 plans, 66 tasks

**Closeout:** Override closeout; 37/38 requirements met, with PAC-06 unmet and carried into M2 under DEC-130. **Known verification overrides:** 7 newly acknowledged, 0 carried forward (see STATE.md Deferred Items).

**Key accomplishments:**
- uv_build-based f1si package skeleton with ruff/mypy-strict/pytest config, a two-OS GitHub Actions gate, pre-commit ruff hooks, committed design docs, and uv 0.13.5 plus CPython 3.12.15 installed and verified.
- uv.lock plus a committed RED end-to-end test, and the contract modules under it: seeded rng, regulation eras, the normalized schema with a visibility column, and a transactional DuckDB storage module proven on Windows (round trip, rollback, NULLs, cross-process lock, injection).
- Seeded synthetic races with exposed ground truth flow through validation into DuckDB and back out through `f1si load` and `f1si races`; the project is pushed and CI is green on ubuntu-latest and windows-latest.
- Every cached race now holds track status, race control, weather, results, precomputed lap cutoffs (reverse cumulative minimum) and per-lap track status strings, and `f1si load` resumes, waits out rate limits, lists failures and refuses to mix sources.
- An AST import scanner with one policy table fails the build when code reaches around the data doors (duckdb, sqlite3, raw network, the results and 2026 doors, RNG constructors), a planted leaky fixture proves it in pytest and in a CI canary step, and DECISIONS.md records 35 method choices with a structure test.
- One rate-limited, JSON-caching HTTP door (OpenF1 at or under 30 calls per minute, Jolpica at or under 450 per hour), a validated Jolpica client for schedule, results with grid and paginated pit stops, and a documented race-control to track-status state machine, all proven offline.
- Three doors (as-of, results, out-of-sample) with exact lap-cutoff visibility, a 2026 lock, and a hypothesis future-scramble test over every registered consumer that catches planted leaks the import ban cannot see.
- OpenF1Source turns OpenF1 timing and Jolpica calendar, grid, results and pit stops into schema-valid race records on a lights-out clock, `uv run f1si load` now loads real races by default, and real Bahrain 2023 loaded on the first try.
- `uv run f1si plot bahrain-2023` renders the real race as 20 small panels (lap time vs lap, coloured by tyre compound, slow laps faded, stint changes dotted) from a RACE_END snapshot through the as-of door, with the data step covered by the future-scramble test.
- Bahrain 2023 is pinned by eight network tests that GitHub runs weekly in a separate non-required workflow, and `uv run f1si load` filled the owner's cache with every 2023-2025 Grand Prix (70 of 70) plus the 17 locked 2026 rounds, with zero failures and no upstream gaps.
- The owner now has a plain-language explainer with a test that keeps its file-by-file tour complete, the decision log stands at DEC-001..DEC-051, and the final state is on GitHub with CI green on Linux and Windows, including the canary that proves a planted leak fails the build.
- Pure-array three-state Joseph-form Kalman filter for the tyre-wear rate (fuel nuisance state, outlier gate), proven equal to closed-form Bayesian regression to 1e-9, plus a stored Phase 3 simulator reference captured from unmodified code.
- `filter_stints` turns an as-of `RaceSnapshot` plus its own fit into per-stint, per-lap wear-rate rows with labelled prior sources; synthetic recovery proves 95% coverage inside the 99.9% binomial band and Bayes-optimal accuracy, and prints the 10% figure without gating it.
- A car's filtered wear rate and SD now drive its current-tyre laps in the NumPy simulator through one new kernel parameter (`wear_age_off`) and a virtual compound column, while "fit" cars stay byte-identical to the stored Phase 3 reference.
- `f1si wear-filter` replays a race lap by lap, building a fresh as-of snapshot, pace fit and Kalman filter at every cutoff, prints labelled prior sources and per-lap rate estimates with 95% intervals, and writes the band chart.
- Opt-in real-data tests for ALO at Bahrain 2023, a finished Phase 4 explainer with measured numbers (including the early as-of fit bias, reported plainly), the README command entry, and a green gate apart from the known environment-only failures.
- A seeded pathwise LSM policy now ranks selected-cutoff pit actions by finishing-position mean and exact worst-decile CVaR.
- Lap-by-lap strategy replay now rebuilds each cutoff independently and reports unsupported early cutoffs without look-ahead.
- The Phase 5 method is documented, the cached Bahrain replay passes locally, and current-branch GitHub Actions passed on Ubuntu and Windows.
- Every replay cutoff now receives a ranked result using a cutoff-only, explicitly uncalibrated fallback when the joint pace fit is unsupported.
- Five parseable pytest modules now define the walk-forward, scoring, team-call, wear-proxy, and Streamlit acceptance contracts for Phase 6 implementation plans.
- The ten-race walk-forward path now gates on complete caches and freezes seeded, cutoff-local predictions for every eligible driver and lap before scoring is introduced.
- Deterministic backtest metrics and race-cluster uncertainty primitives are implemented and their seven focused metric tests passed.
- A complete 10-race probability evaluation is published after all 10,942 prediction keys are frozen, with no outcome access during prediction.
- The ten-race report now compares 388 observed stops with snapshot-safe recommendations and measures Kalman wear bands against a retrospective reference that excludes the evaluated stint.
- The page now presents measured ten-race evidence beside a read-only Bahrain 2023 / ALO cutoff replay, with explicit fallback and unavailable states.
- The README and explainer now publish the fixed ten-race evidence with its uncertainty and modeling limits, backed by sequential evaluation decisions and regression tests.
- The selected replay now has compact finish quantiles and a forward-simulated position fan chart, styled to the approved Phase 6 visual contract.
- A dark motorsport replay dashboard with a compact measured scorecard, responsive control and result cards, and a readable selected-cutoff finishing chart.
- The Bayesian pace fit now gates posterior sampling on a measured ADVI trajectory and recovers declared synthetic effects against an independent NUTS reference.
- Replay and registered backtests can now select the converged Bayesian pace model at each cutoff while keeping linear behavior as the default.
- The locked score is published with its actual result: the Bayesian model did not meet the real-data improvement gate.
- Regime event priority, race-local transition recovery, and five regime-cost assumptions are now verified and recorded.
- The locked linear-pace evaluation produced a verifiable 20-race report, with independent continuation fit and scoring paths.
- The nine-race 2026 holdout is locked behind a feature-only transition fit, cutoff-local prediction path, and single protected result consumer.

---
