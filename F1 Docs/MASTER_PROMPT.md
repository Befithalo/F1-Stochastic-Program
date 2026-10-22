# Master prompt for /gsd:new-project

Read docs/BUILD_PLAN.md first. It is the full design: architecture, data sources, evaluation targets and risks. This file is the build brief.

Project: F1 Stochastic Intelligence Platform, a probabilistic F1 race-strategy system combining quant finance methods, vehicle physics, ML/RL, and production engineering.

Full vision (6 milestones; build ONLY M1 now, but design M1's architecture so later milestones plug in without rewrites):
- M1 Core stochastic engine: data layer, hierarchical Bayesian pace model, Kalman tire-degradation filter, Markov race-regime model (green/VSC/SC/red/wet), vectorized Monte Carlo simulator (50,000 races in under 10 s, Sobol + antithetic), Longstaff-Schwartz optimal pit timing ranked by mean finish and CVaR@10%, walk-forward backtester (2023-2025, no look-ahead, Brier score + calibration).
- M2 Physics: point-mass lap sim from telemetry, tire thermal/wear model, fuel effects, hybrid physics+data pace model.
- M3 ML/AI: XGBoost lap-time baseline, neural surrogate of the simulator, PPO agent in a Gymnasium env wrapping the simulator, benchmark vs LSM and real team calls.
- M4 Multi-agent + season: all cars strategize and react (undercut response game); championship-level dynamic programming.
- M5 Performance: JAX and Rust (PyO3) simulator backends with numerical parity tests against the NumPy reference.
- M6 Product: FastAPI + Next.js dashboard, OpenF1 live mode, Docker, public deploy.

Required plug-in interfaces (define in M1, as typed Protocols in f1si/interfaces.py):
- PaceModel: predicts lap-time distributions. M1 = Bayesian; M2 adds Physics and Hybrid; M3 adds XGBoost.
- StrategyPolicy: given race state, returns a pit decision. M1 = LSM; M3 adds RL; M4 adds game-theoretic.
- SimulatorBackend: runs N races from a state. M1 = NumPy; M5 adds JAX and Rust.
- Every implementation of an interface must pass the same shared test suite.

Stack: Python 3.12, uv, NumPy, pandas, SciPy, PyMC, Numba, FastF1, OpenF1, DuckDB, pytest + hypothesis, ruff, mypy strict, GitHub Actions CI. src/ layout, package f1si. Development on Windows.

Non-negotiables:
- Explicit np.random.Generator everywhere; reproducible by seed.
- No look-ahead: backtests read data only through one as-of accessor; a test enforces it.
- Every model gets a synthetic-data test: generate data with known parameters, confirm the model recovers them.
- Docstrings state the math. Keep a DECISIONS.md log of every method choice and why.
- Treat 2026 races as out-of-sample (regulation change); report results per era.
- CI must pass before a phase counts as done.
- I am new to coding: after each phase, explain what was built in plain language.

M1 build order (lean MVP first, weeks 1-6): data + lap-time plot, simple linear tire wear and free-track optimizer, Monte Carlo simulator, Kalman filter + live-replay loop, LSM + CVaR, backtest 10 races + Streamlit page. Then upgrade to the Bayesian pace model and Markov regime model.

M1 definition of done: live replay of the 2023 Bahrain GP gives lap-by-lap strategy recommendations for any driver, plus a backtest report over at least 20 races.
