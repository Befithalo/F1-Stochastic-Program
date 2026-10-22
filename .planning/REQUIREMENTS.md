# Requirements: F1 Stochastic Intelligence Platform (M1)

**Defined:** 2026-10-22
**Core Value:** Honest, calibrated, look-ahead-free pit-strategy recommendations, verified against synthetic ground truth.

## v1 Requirements (Milestone M1)

### Foundation

- [ ] **FND-01**: Repo has a uv-managed Python 3.12 `src/f1si` package with ruff, mypy strict and pytest configured
- [ ] **FND-02**: GitHub Actions CI runs lint, type-check and tests on every push and must pass for a phase to count as done
- [ ] **FND-03**: All randomness uses an explicit `np.random.Generator`, and the same seed reproduces identical results
- [ ] **FND-04**: `DECISIONS.md` logs every method choice with its rationale

### Data

- [ ] **DAT-01**: User can load 2023-2025 race laps, stints, pit stops and results through FastF1/OpenF1 into a local DuckDB cache
- [ ] **DAT-02**: User can plot lap time by stint for any cached race (first target: Bahrain 2023)
- [ ] **DAT-03**: All backtest and replay code reads data only through one as-of accessor that returns rows up to a given lap
- [ ] **DAT-04**: A test fails the build if any code reads a future row through or around the as-of accessor
- [ ] **DAT-05**: Every race is tagged with its regulation era, and 2026 races are marked out-of-sample

### Interfaces

- [ ] **INT-01**: `f1si/interfaces.py` defines typed Protocols `PaceModel`, `StrategyPolicy` and `SimulatorBackend`
- [ ] **INT-02**: A shared test suite runs against every implementation of each Protocol
- [ ] **INT-03**: A shared `RaceState` object (per the BUILD_PLAN schema) is the single input to simulator and policy

### Pace and Tire Model

- [ ] **PAC-01**: Lap times are fuel-corrected, and a linear tire-wear rate is fitted per compound
- [ ] **PAC-02**: User can get the free-track optimal plan by brute-forcing every 1- and 2-stop strategy for total race time
- [ ] **PAC-03**: A Kalman filter estimates hidden tire wear per car from noisy lap times, with an uncertainty band
- [ ] **PAC-04**: On synthetic stints the Kalman estimate is within 10% of truth by lap 8 and 95% intervals cover truth about 95% of the time
- [ ] **PAC-05**: A hierarchical Bayesian (PyMC) pace model with car, driver, tire, fuel and era effects implements `PaceModel`
- [ ] **PAC-06**: The Bayesian pace model recovers known parameters from synthetic data and beats a per-compound linear baseline by at least 15% on next-lap error

### Regime Model

- [ ] **REG-01**: A per-lap safety-car probability feeds the simulator (MVP version)
- [ ] **REG-02**: A Markov regime model (green/VSC/SC/red/wet) replaces it, with a synthetic-data test recovering its transition matrix
- [ ] **REG-03**: Pit loss depends on regime (e.g. cheaper under SC)

### Simulator

- [ ] **SIM-01**: A vectorized NumPy `SimulatorBackend` simulates N races from a `RaceState` with pit loss, overtaking chance from pace gap, and regime events
- [ ] **SIM-02**: 50,000 races run in under 10 seconds
- [ ] **SIM-03**: Sobol sequences and antithetic variates reduce variance, with a test showing lower variance than plain Monte Carlo at equal N

### Strategy

- [ ] **STR-01**: Longstaff-Schwartz optimal pit timing implements `StrategyPolicy`
- [ ] **STR-02**: Each option (pit now, pit in 1-5 laps, stay out) is ranked by mean finish and CVaR@10%
- [ ] **STR-03**: A risk-appetite setting shifts ranking between mean and tail risk
- [ ] **STR-04**: Each recommendation includes a one-sentence reason (e.g. undercut threat, cliff risk, safety-car window)

### Replay and Backtest

- [ ] **RPL-01**: User can replay a race lap by lap for any driver and get a recommendation with uncertainty each lap
- [ ] **RPL-02**: Live replay of Bahrain 2023 works end to end (M1 definition of done)
- [ ] **BKT-01**: A walk-forward backtester runs races from 2023-2025 with zero look-ahead
- [ ] **BKT-02**: Backtest reports Brier score (podium, top-10) vs a grid-position baseline and 90% finishing-interval coverage
- [ ] **BKT-03**: Backtest covers at least 20 races (10 at the MVP checkpoint), with results reported per era
- [ ] **BKT-04**: Strategy calls are compared with actual team calls, with confidence intervals
- [ ] **BKT-05**: A locked holdout set is defined and touched only once, at milestone end

### Presentation

- [ ] **UI-01**: A one-page Streamlit view shows strategy table, finishing-position fan chart, regime gauge, tire panel, reason line and risk dial
- [ ] **UI-02**: README documents real measured results, hidden-variable assumptions and data licensing/credits
- [ ] **UI-03**: After each phase, a plain-language explanation of what was built is produced

## v2 Requirements (later milestones)

- **M2**: Point-mass lap sim, tire thermal/wear model, hybrid pace model
- **M3**: XGBoost baseline, neural surrogate, PPO agent vs LSM
- **M4**: Multi-agent undercut game, championship dynamic programming
- **M5**: JAX and Rust backends with parity tests
- **M6**: FastAPI + Next.js, OpenF1 live mode, Docker, deploy
- Prediction-market odds (Kalshi/Polymarket) as a benchmark column in the backtest

## Out of Scope

| Feature | Reason |
|---------|--------|
| Live OpenF1 streaming | Paid; replay is the default, live is M6 |
| Trading/betting bot | Market prices are a read-only benchmark |
| Raw data redistribution, commercial use | FastF1/OpenF1 terms |
| Copying LGPL TUMFTM code | License obligations; reimplement ideas with citation |

## Traceability

(Filled by roadmap creation.)

**Coverage:** 38 v1 requirements

---
*Requirements defined: 2026-10-22*
