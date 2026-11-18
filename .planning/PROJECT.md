# F1 Stochastic Intelligence Platform (f1si)

## What This Is

A Python platform that recommends F1 pit strategy as a probability distribution, recomputed every lap. The shipped M1 core uses Monte Carlo simulation, optimal stopping, CVaR, regime switching and Kalman filtering. M2 adds a physics-based pace foundation and learns its remaining error from historical data.

Core loop, once per lap: ingest timing data, update car state (tire wear, pace, track regime), simulate 50,000 race continuations, value each pit decision, rank by mean finish and tail risk, show the recommendation with its uncertainty.

Source design docs: `F1 Docs/BUILD_PLAN.md` (full design, data sources, evaluation, risks) and `F1 Docs/MASTER_PROMPT.md` (build brief).

## Core Value

For any driver at any lap of a replayed race, give a pit-strategy recommendation whose uncertainty is honest: cutoff-safe, checked against synthetic ground truth, and evaluated against real race data with limitations disclosed.

## Audience / Context

- Owner is new to coding. After each phase, Claude explains in plain language what was built.
- Portfolio project aimed at quant, motorsport and software employers. Only measured numbers go on the resume.
- Development on Windows. Non-commercial; FastF1/OpenF1 are unofficial and credited.

## Scope: Six Milestones (M1 shipped; M2 active)

M1 was architected so later milestones plug in without rewrites.

- **M1 Core stochastic engine** (shipped v1.0 with acknowledged verification items)
- **M2 Physics** (current): point-mass lap sim, tire thermal/wear model, fuel effects, hybrid pace model
- M3 ML/AI: XGBoost baseline, neural surrogate, PPO agent in a Gymnasium env, benchmark vs LSM and team calls
- M4 Multi-agent + season: reactive cars (undercut game), championship dynamic programming
- M5 Performance: JAX and Rust (PyO3) backends with parity tests vs NumPy
- M6 Product: FastAPI + Next.js dashboard, OpenF1 live mode, Docker, public deploy

## Current Milestone: v2.0 M2 Physics

**Goal:** Add a physically grounded pace model and a Bayesian residual hybrid behind the existing `PaceModel` interface, with a pre-registered held-out-stint gate before M3.

**Target features:**
- Establish provenance-checked track geometry and cutoff-safe optional OpenF1 telemetry/weather inputs. Use cached data and historical OpenF1; do not require new FastF1 downloads or F1 TV Access.
- Build a reduced-order point-mass lap model from geometry and effective power, drag, downforce, grip, and mass/fuel inputs; model hidden tire temperature and energy-driven wear with uncertainty.
- Compose physics with the data-only Bayesian pace model, preserve all existing consumers, verify synthetic parameter recovery for every physics model, and require a locked real-data held-out-stint improvement before M3.

## Requirements

### Validated

- [x] Data layer: FastF1/OpenF1 2023-2025 cached in DuckDB, single as-of accessor, lap-time-by-stint plot — Validated in Phase 1: Foundation & Data
- [x] Typed Protocols in `f1si/interfaces.py`: `PaceModel`, `StrategyPolicy`, `SimulatorBackend`, with a shared test suite every implementation must pass — Validated in Phase 2: Interfaces, Linear Tire Wear & Free-Track Optimizer
- [x] Simple fuel-corrected linear tire wear per compound + free-track brute-force 1/2-stop optimizer — Validated in Phase 2 (Bahrain 2023: HARD +0.121, SOFT +0.125 s/lap, fuel -0.078 s/lap, pit loss 24.4 s)
- [x] Vectorized Monte Carlo simulator (pit loss, overtaking from pace gap, safety-car probability); 50,000 races in under 10 s; Sobol + antithetic variance reduction — Validated in Phase 3: Monte Carlo Simulator (Bahrain 2023 ALO: 50,000 races in 1.7 s, variance cut 3.8x mean finish / 11.7x total time / 2.5x SC share; open flag: real P3 sits outside the 90% interval P4-P6, check coverage in Phase 6)
- [x] Kalman tire-degradation filter (per car and stint, as-of only) feeding the simulator — Validated in Phase 4: Kalman Tire Filter (synthetic: 95% bands cover truth, accuracy matches the Bayes-optimal closed form; owner restated PAC-04: 10% by stint lap 8 is reported, not gated, measured 23/32/38% soft/medium/hard; Bahrain 2023 replay `f1si wear-filter`; open flag: early as-of fit bias at lap 14 (soft 0.26 vs 0.12) and own-laps double counting, measure real-data wear-band coverage in Phase 6)

- [x] Longstaff-Schwartz strategy and cutoff-safe Bahrain replay — Delivered in Phase 5; CLI decision usefulness remains an acknowledged strategist judgment.
- [x] Ten-race walk-forward report and one-page evidence view — Delivered in Phase 6 with 1,000 simulations per prediction; team-call comparisons are descriptive, not superiority claims.
- [x] Bayesian pace implementation and synthetic recovery — Delivered in Phase 7. Its locked real-data gate PAC-06 was not met (Bayesian MAE 0.538745 s versus linear 0.364033 s, -47.99% improvement) and remains active for M2 under DEC-130.
- [x] Markov race-regime model and full in-sample backtest — Delivered in Phase 8 with a separate 2026 report; three judgment-tier review flags remain acknowledged, and the 2026 result is pre-registered but retrospectively unblinded.

### Validated (M2)

- [x] Geometry-driven point-mass PaceModel with deterministic uncertainty and independently tested effective-scale recovery - Validated in Phase 10; absolute vehicle terms remain assumptions and the real-data fit is boundary-limited.

### Active (M2)

- [ ] PAC-06: on a separately locked held-out-stint comparison, improve next-lap error over the data-only Bayesian pace model; do not retune or rescore the M1 lock
- [ ] Tire thermal and wear model driven by temperature and energy, with hidden state disclosed where direct measurements are unavailable
- [ ] Hybrid PaceModel with physics as base and the M1 Bayesian model learning the residual, preserving the existing interface

### Out of Scope (for now)

- M3-M6 features (ML/RL, multi-agent, JAX/Rust, FastAPI/Next.js, live mode, deploy) - separate milestones
- Live OpenF1 streaming (paid) - default is replay of past races
- Trading/betting bot behaviour - prediction-market prices are a read-only benchmark only
- Republishing raw data dumps; commercial use

## Context

- 2026 regulation reset (narrower tires, ~10% less grip, more one-stops) is a structural break: 2022-2025 are training eras, 2026 races are out-of-sample, results reported per era.
- Fuel load, tire temperature and wear are not public: modeled as hidden state.
- Reference benchmark: Bahrain GP 2023 (RSRL paper, Mercedes-AMG/Imperial 2025, published P5.33). Reference design: Heilmeier et al. 2020 and TUMFTM race-simulation (LGPL: reimplement ideas with citation, do not copy files).
- Overfitting guard: lock a holdout set, touch once per milestone end.
- M1 strategy baseline from the locked 20-race 2023-2025 report: podium Brier 0.055456 (grid 0.073693), top-10 Brier 0.144645 (grid 0.169086), P05-P95 coverage 82.26% (16,508/20,001), signed stop error +1.174 laps, team-call agreement 17.22% (695 matched stops). See `.planning/M1-BASELINE.md`; keep the separate 2026 report out of this baseline.
- M1 closed with an override: 37/38 requirements met. PAC-06 is not met. Phases 1, 5, and 8 retain acknowledged UAT or judgment items; seven GSD audit items are recorded in `.planning/STATE.md`.

## Constraints

- **Stack**: Python 3.12, uv, NumPy, pandas, SciPy, PyMC, Numba, FastF1, OpenF1, DuckDB, pytest + hypothesis, ruff, mypy strict, GitHub Actions CI; src/ layout, package `f1si`
- **Reproducibility**: explicit `np.random.Generator` everywhere; reproducible by seed
- **No look-ahead**: backtests read data only through one as-of accessor; a test enforces it
- **Model validation**: every model has a synthetic-data recovery test (known parameters recovered)
- **Documentation**: docstrings state the math; DECISIONS.md logs every method choice and why
- **Quality gate**: CI must pass before a phase counts as done
- **Performance**: NumPy simulator under 10 s for 50,000 races

## M1 Definition of Done

Live replay of the 2023 Bahrain GP gives lap-by-lap strategy recommendations for any driver, plus a backtest report over at least 20 races. M1 was administratively closed with the PAC-06 miss and human review items disclosed; they are not represented as passed.

## M1 Build Order

Lean MVP first (weeks 1-6): data + lap-time plot, linear tire wear + free-track optimizer, Monte Carlo simulator, Kalman filter + live-replay loop, LSM + CVaR, backtest 10 races + Streamlit page. Go/no-go at week 6. Then upgrade to the Bayesian pace model and Markov regime model.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build M1 behind plug-in Protocols, then start M2 at the milestone boundary | Avoid scope sprawl; later milestones swap in implementations | Accepted; `PaceModel` remains the M2 seam |
| Lean MVP (linear wear, constant SC rate) before Bayes/Markov | Get one race working end to end first | Accepted; M1 established the baseline before upgrades |
| 2026 races held out-of-sample | Regulation break; honest validation | Accepted with disclosure; the separate result is retrospectively unblinded |
| Vertical MVP phase structure | Each phase delivers an end-to-end capability | Accepted; M1 shipped eight phases |
| Replay of past races, not live | Live OpenF1 is paid | Accepted; M2 uses historical OpenF1 data |
| PyMC vs NumPyro | Open question in BUILD_PLAN; PyMC is the stated stack | PyMC accepted and implemented; real-data PAC-06 remains unmet |
| Carry PAC-06 into M2 and compare hybrid vs data-only Bayesian on a new held-out-stint lock | Preserve the M1 measurement and prevent retuning its lock | Accepted under DEC-130/132 |
| Build a deterministic cyclic point-mass PaceModel and fit only the identifiable effective power-to-mass scale | Keep physics behind the existing consumer seam and avoid claiming hidden vehicle values from sparse observations | Accepted in Phase 10 under DEC-140/141; synthetic recovery passed and the real-data fit remained boundary-limited |

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
*Last updated: 2026-11-18 after Phase 10*
