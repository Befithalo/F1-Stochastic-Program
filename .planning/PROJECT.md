# F1 Stochastic Intelligence Platform (f1si)

## What This Is

A Python platform that recommends F1 pit strategy as a full probability distribution, recomputed every lap. It uses quant-finance methods (Monte Carlo pricing, optimal stopping, CVaR, regime switching, Kalman filtering) together with vehicle physics, ML/RL and production engineering. Pit timing is treated as an American option and strategy choice as a risk-adjusted portfolio decision.

Core loop, once per lap: ingest timing data, update car state (tire wear, pace, track regime), simulate 50,000 race continuations, value each pit decision, rank by mean finish and tail risk, show the recommendation with its uncertainty.

Source design docs: `F1 Docs/BUILD_PLAN.md` (full design, data sources, evaluation, risks) and `F1 Docs/MASTER_PROMPT.md` (build brief).

## Core Value

For any driver at any lap of a replayed race, give a pit-strategy recommendation whose uncertainty is honest: calibrated, free of look-ahead, and verified against synthetic ground truth.

## Audience / Context

- Owner is new to coding. After each phase, Claude explains in plain language what was built.
- Portfolio project aimed at quant, motorsport and software employers. Only measured numbers go on the resume.
- Development on Windows. Non-commercial; FastF1/OpenF1 are unofficial and credited.

## Scope: Six Milestones (build ONLY M1 now)

M1 must be architected so later milestones plug in without rewrites.

- **M1 Core stochastic engine** (current)
- M2 Physics: point-mass lap sim, tire thermal/wear model, fuel effects, hybrid pace model
- M3 ML/AI: XGBoost baseline, neural surrogate, PPO agent in a Gymnasium env, benchmark vs LSM and team calls
- M4 Multi-agent + season: reactive cars (undercut game), championship dynamic programming
- M5 Performance: JAX and Rust (PyO3) backends with parity tests vs NumPy
- M6 Product: FastAPI + Next.js dashboard, OpenF1 live mode, Docker, public deploy

## Requirements

### Validated

(None yet, ship to validate)

### Active (M1)

- [ ] Data layer: FastF1/OpenF1 2023-2025 cached in DuckDB, single as-of accessor, lap-time-by-stint plot
- [ ] Typed Protocols in `f1si/interfaces.py`: `PaceModel`, `StrategyPolicy`, `SimulatorBackend`, with a shared test suite every implementation must pass
- [ ] Simple fuel-corrected linear tire wear per compound + free-track brute-force 1/2-stop optimizer
- [ ] Vectorized Monte Carlo simulator (pit loss, overtaking from pace gap, safety-car probability); 50,000 races in under 10 s; Sobol + antithetic variance reduction
- [ ] Kalman tire-degradation filter + lap-by-lap live-replay loop
- [ ] Longstaff-Schwartz optimal pit timing, ranked by mean finish and CVaR@10%
- [ ] Walk-forward backtester (2023-2025, no look-ahead) with Brier score and calibration; 10 races at MVP, at least 20 for M1 done
- [ ] Streamlit one-page view
- [ ] Upgrade: hierarchical Bayesian pace model (PyMC) with era effect
- [ ] Upgrade: Markov race-regime model (green/VSC/SC/red/wet)
- [ ] README with real results; DECISIONS.md logging every method choice

### Out of Scope (for now)

- M2-M6 features (physics, ML/RL, multi-agent, JAX/Rust, FastAPI/Next.js, live mode, deploy) - separate milestones via `/gsd:new-milestone`
- Live OpenF1 streaming (paid) - default is replay of past races
- Trading/betting bot behaviour - prediction-market prices are a read-only benchmark only
- Republishing raw data dumps; commercial use

## Context

- 2026 regulation reset (narrower tires, ~10% less grip, more one-stops) is a structural break: 2022-2025 are training eras, 2026 races are out-of-sample, results reported per era.
- Fuel load, tire temperature and wear are not public: modeled as hidden state.
- Reference benchmark: Bahrain GP 2023 (RSRL paper, Mercedes-AMG/Imperial 2025, published P5.33). Reference design: Heilmeier et al. 2020 and TUMFTM race-simulation (LGPL: reimplement ideas with citation, do not copy files).
- Overfitting guard: lock a holdout set, touch once per milestone end.

## Constraints

- **Stack**: Python 3.12, uv, NumPy, pandas, SciPy, PyMC, Numba, FastF1, OpenF1, DuckDB, pytest + hypothesis, ruff, mypy strict, GitHub Actions CI; src/ layout, package `f1si`
- **Reproducibility**: explicit `np.random.Generator` everywhere; reproducible by seed
- **No look-ahead**: backtests read data only through one as-of accessor; a test enforces it
- **Model validation**: every model has a synthetic-data recovery test (known parameters recovered)
- **Documentation**: docstrings state the math; DECISIONS.md logs every method choice and why
- **Quality gate**: CI must pass before a phase counts as done
- **Performance**: NumPy simulator under 10 s for 50,000 races

## M1 Definition of Done

Live replay of the 2023 Bahrain GP gives lap-by-lap strategy recommendations for any driver, plus a backtest report over at least 20 races.

## M1 Build Order

Lean MVP first (weeks 1-6): data + lap-time plot, linear tire wear + free-track optimizer, Monte Carlo simulator, Kalman filter + live-replay loop, LSM + CVaR, backtest 10 races + Streamlit page. Go/no-go at week 6. Then upgrade to the Bayesian pace model and Markov regime model.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build only M1 now, with plug-in Protocols | Avoid scope sprawl; later milestones swap in implementations | Pending |
| Lean MVP (linear wear, constant SC rate) before Bayes/Markov | Get one race working end to end first | Pending |
| 2026 races held out-of-sample | Regulation break; honest validation | Pending |
| Vertical MVP phase structure | Each phase delivers an end-to-end capability | Pending |
| Replay of past races, not live | Live OpenF1 is paid | Pending |
| PyMC vs NumPyro | Open question in BUILD_PLAN; PyMC is the stated stack | Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? Move to Out of Scope with reason
2. Requirements validated? Move to Validated with phase reference
3. New requirements emerged? Add to Active
4. Decisions to log? Add to Key Decisions
5. "What This Is" still accurate? Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check, still the right priority?
3. Audit Out of Scope, reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-22 after initialization*
