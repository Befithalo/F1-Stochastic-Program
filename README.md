# F1 Stochastic Intelligence Platform (f1si)

A Python platform that recommends F1 pit strategy as a full probability distribution, recomputed every lap. It uses quant-finance methods (Monte Carlo pricing, optimal stopping, CVaR, regime switching, Kalman filtering) together with vehicle physics, ML/RL and production engineering. Pit timing is treated as an American option and strategy choice as a risk-adjusted portfolio decision.

## Status

Phase 1: foundation and data, in progress.

## Quickstart (Windows PowerShell)

```powershell
uv sync
uv run pre-commit install
uv run f1si --data-dir data/demo load --source synthetic
uv run f1si --data-dir data/demo races
uv run f1si load
uv run f1si races
uv run f1si plot bahrain-2023
uv run pytest
```

## Data and credits

Data comes from OpenF1 (openf1.org, personal non-commercial use) and the Jolpica F1 API (Ergast-compatible). This project is not affiliated with Formula 1. Raw data is never committed or republished.
