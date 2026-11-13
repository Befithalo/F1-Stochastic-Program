# F1 Stochastic Intelligence Platform (f1si)

A Python platform that recommends F1 pit strategy as a full probability distribution, recomputed every lap. It uses quant-finance methods (Monte Carlo pricing, optimal stopping, CVaR, regime switching, Kalman filtering) together with vehicle physics, ML/RL and production engineering. Pit timing is treated as an American option and strategy choice as a risk-adjusted portfolio decision.

## Status

Phase 1 (foundation and data): done. Phase 2 (tyre wear and the free-track pit plan): built. Phase 3 (Monte Carlo race simulator): built. Phase 4 (Kalman tyre-wear filter): built, waiting for green CI.

## What Phase 1 gives you

- One command, `uv run f1si load`, downloads every 2023-2025 Grand Prix (70 races) plus the locked 2026 races (17) from OpenF1 and Jolpica into a local DuckDB cache. It is safe to run again: finished races are skipped.
- `uv run f1si plot bahrain-2023` draws lap time by stint for a whole race, one panel per driver, coloured by tyre.
- `uv run f1si wear bahrain-2023` fits fuel-corrected tyre wear per compound and prints it with the fuel effect and the pit loss (it also writes `reports\wear-bahrain-2023.png`).
- `uv run f1si plan bahrain-2023 --driver ALO` prints the fastest free-track 1-stop and 2-stop plans, labelled "Hindsight plan" because it uses the whole race. Add `--lap 30` to plan from only what was known after lap 30. Free-track means no traffic or safety cars, so the time is a lower bound, and the actual strategy is compared against the plan, never said to be beaten by it.
- `uv run f1si simulate bahrain-2023 --driver ALO` prints Alonso's finishing-position distribution from 50,000 simulated continuations of the race, labelled "hindsight simulation" because it uses the whole race. Add `--lap 30` to use only data known after lap 30. The safety-car rate for Bahrain 2023 comes from the prior alone (there are no earlier races), printed as "prior only". It also writes `reports\sim-bahrain-2023-ALO-lap0.png`.
- `uv run f1si wear-filter bahrain-2023 --driver ALO` replays the race and prints, for each of the driver's stints, the tyre wear-rate estimate and its 95% band lap by lap, using only data known at each lap. Tyre state is hidden; the filter infers it. A stint whose starting belief has no data behind it yet is labelled "prior only", and the dashed line in the chart is the Phase 2 "hindsight" estimate. Add `--lap 30` to stop the replay at lap 30. It writes `reportswear-filter-bahrain-2023-ALO.png`.
- No code can read future data: every read goes through one as-of door, guarded in CI by an import scan and a future-scramble test, with deliberately planted leaks to prove the guards work.
- Two-OS CI (ubuntu and Windows), seeded randomness, synthetic races with known ground truth, and a decision log.

Read [docs/explained/phase-04.md](docs/explained/phase-04.md) for the Phase 4 tour (the Kalman tyre-wear filter, its priors, real Bahrain numbers). Read [docs/explained/phase-03.md](docs/explained/phase-03.md) for the Phase 3 tour (the safety-car rate, passing, variance reduction, the simulator). Read [docs/explained/phase-02.md](docs/explained/phase-02.md) for the Phase 2 tour (interfaces, tyre wear, the pit plan). Read [docs/explained/phase-01.md](docs/explained/phase-01.md) for a plain-language tour of everything built (what, why, how the pieces connect, a file-by-file tour and interview questions). Every method choice is logged in [DECISIONS.md](DECISIONS.md).

## Quickstart (Windows PowerShell)

```powershell
uv sync
uv run pre-commit install
uv run f1si --data-dir data/demo load --source synthetic   # offline demo with fake races
uv run f1si --data-dir data/demo races
uv run f1si load                                           # real races, about 15 minutes the first time
uv run f1si races
uv run f1si plot bahrain-2023                              # writes reports\bahrain-2023.png
uv run f1si wear bahrain-2023                              # writes reports\wear-bahrain-2023.png
uv run f1si plan bahrain-2023 --driver ALO                 # hindsight plan for Alonso
uv run f1si plan bahrain-2023 --driver ALO --lap 30        # plan using only data up to lap 30
uv run f1si simulate bahrain-2023 --driver ALO             # hindsight simulation, writes reports\sim-bahrain-2023-ALO-lap0.png
uv run f1si simulate bahrain-2023 --driver ALO --lap 30    # simulation using only data up to lap 30
uv run f1si wear-filter bahrain-2023 --driver ALO           # as-of wear-rate band, writes reportswear-filter-bahrain-2023-ALO.png
uv run f1si wear-filter bahrain-2023 --driver ALO --lap 30   # replay stopped at lap 30
uv run pytest
```

## Data and credits

Data comes from OpenF1 (openf1.org, personal non-commercial use) and the Jolpica F1 API (Ergast-compatible). This project is not affiliated with Formula 1. Raw data is never committed or republished.
