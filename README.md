# F1 Stochastic Intelligence Platform (f1si)

A Python platform that recommends F1 pit strategy as a full probability distribution, recomputed every lap. It uses quant-finance methods (Monte Carlo pricing, optimal stopping, CVaR, regime switching, Kalman filtering) together with vehicle physics, ML/RL and production engineering. Pit timing is treated as an American option and strategy choice as a risk-adjusted portfolio decision.

## Status

Phase 1 (foundation and data): done. Phase 2 is next.

## What Phase 1 gives you

- One command, `uv run f1si load`, downloads every 2023-2025 Grand Prix (70 races) plus the locked 2026 races (17) from OpenF1 and Jolpica into a local DuckDB cache. It is safe to run again: finished races are skipped.
- `uv run f1si plot bahrain-2023` draws lap time by stint for a whole race, one panel per driver, coloured by tyre.
- No code can read future data: every read goes through one as-of door, guarded in CI by an import scan and a future-scramble test, with deliberately planted leaks to prove the guards work.
- Two-OS CI (ubuntu and Windows), seeded randomness, synthetic races with known ground truth, and a decision log.

Read [docs/explained/phase-01.md](docs/explained/phase-01.md) for a plain-language tour of everything built (what, why, how the pieces connect, a file-by-file tour and interview questions). Every method choice is logged in [DECISIONS.md](DECISIONS.md).

## Quickstart (Windows PowerShell)

```powershell
uv sync
uv run pre-commit install
uv run f1si --data-dir data/demo load --source synthetic   # offline demo with fake races
uv run f1si --data-dir data/demo races
uv run f1si load                                           # real races, about 15 minutes the first time
uv run f1si races
uv run f1si plot bahrain-2023                              # writes reports\bahrain-2023.png
uv run pytest
```

## Data and credits

Data comes from OpenF1 (openf1.org, personal non-commercial use) and the Jolpica F1 API (Ergast-compatible). This project is not affiliated with Formula 1. Raw data is never committed or republished.
