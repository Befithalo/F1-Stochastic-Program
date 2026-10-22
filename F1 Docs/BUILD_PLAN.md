# F1 Stochastic Intelligence Platform — Build Plan

Oct 21, 2026 · @Navbir Singh

## Summary

Build a Python platform that recommends F1 pit strategy as a full probability distribution, recomputed every lap, using the same tools quants use to price and risk-manage trades.

The core loop runs once per lap: ingest timing data, update the car's state (tire wear, pace, track regime), simulate 50,000 continuations of the race, value each pit decision, rank strategies by expected finish and tail risk, then show the recommendation with its uncertainty.

Recommended stack in one line: FastF1 and OpenF1 data cached in DuckDB, PyMC for the Bayesian pace model, NumPy and Numba for simulation (JAX and Rust later), Gymnasium and Stable-Baselines3 for reinforcement learning, FastAPI and Next.js for the dashboard, built with Claude Code + GSD and reviewed by Codex.

The differentiator is not "another lap-time predictor". It treats pit timing as an American option and strategy choice as a risk-adjusted portfolio decision, grounds pace in vehicle physics, and proves itself with walk-forward backtests against real team calls.

## Why this project

Race strategy is a decision under uncertainty with a hard deadline, which is exactly the problem a trading desk solves. Pit timing has option-like payoffs, safety cars are jump events, and a team's appetite for risk should depend on its championship position.

That makes one project credible to three kinds of employers. Quant firms see Monte Carlo pricing, optimal stopping, tail risk and calibration. Motorsport and engineering teams see vehicle physics, tire modeling and a strategy tool; Mercedes-AMG publishes research in exactly this area. Software employers see a tested, fast, deployed system.

The timing is good. The 2026 rules cut front tire width by 25 mm and rear by 30 mm ([F1 rule guide](https://www.flashscore.com/news/auto-racing-formula-1-tyres-wings-and-drs-a-guide-to-the-major-f1-rule-changes-for-2026/ltHDbdak)), and Pirelli says drivers have about 10% less grip, with the opening races dominated by one-stop strategies ([GrandPrix.com](https://www.grandprix.com/news/pirelli-expects-more-two-stop-races-as-2026-progresses.html)). A rule reset is a structural break, and testing whether your models survive one is a classic quant question.

| Quant concept | F1 equivalent | Where it lives |
| --- | --- | --- |
| Monte Carlo pricing | 50,000 simulated race continuations | Simulator |
| American option, optimal stopping | When to pit | Strategy optimizer |
| CVaR, tail risk | Worst-case finishing positions | Strategy optimizer |
| Regime switching, jump process | Green flag, VSC, safety car, red flag, rain | Race-state model |
| Kalman filter | Hidden tire wear estimated from noisy lap times | Tire filter |
| Factor model | Lap time = car + driver + tire + fuel + track | Pace model |
| Structural break | 2026 regulation reset | Validation |
| Walk-forward backtest | Replaying past seasons with no future data | Backtester |
| Market-implied probability | Kalshi and Polymarket F1 odds | Benchmark |

## Landscape

Serious F1 strategy simulation exists in academia and inside teams, but no open project combines live Bayesian updating, option-style pit valuation, tail-risk ranking, physics grounding and honest calibration, and none is built for the 2026 rules.

| Project or study | What it does | Gap this project fills |
| --- | --- | --- |
| [TUMFTM race-simulation](https://github.com/TUMFTM/race-simulation) (TU Munich) | Lap-wise race simulation with Monte Carlo effects and a "Virtual Strategy Engineer" (supervised neural nets plus a DQN reinforcement learner); parameter files for 121 F1 races, 2014 to 2019 | Pre-2020 data, dry compounds only for the RL agent, no live state updating or risk measures. LGPL-3.0, so learn from it rather than copy it |
| [Heilmeier et al. 2020](https://www.mdpi.com/2076-3417/10/12/4229/html) | The paper behind that simulator: models accidents, safety cars and other random events, and uses Monte Carlo to judge how robust a strategy is | The method to reproduce and extend; read it first |
| [RSRL, Imperial College + Mercedes-AMG 2025](https://arxiv.org/abs/2501.04068v1) | Reinforcement learning on Mercedes' own Monte Carlo simulator; averaged P5.33 on the 2023 Bahrain GP against a best baseline of P5.63 | The simulator is proprietary. An open reproduction on the same race is a concrete, citable benchmark |
| [Mercedes tyre-energy forecasting](https://www.catalyzex.com/author/Joseph%20McMillan) | Deep learning and XGBoost forecasts of tyre energy from team telemetry, with explainability | Uses private team data; shows the ML-versus-trees comparison is industry-relevant |
| [Community tools](https://github.com/subinium/awesome-f1) (Armchair Strategist, F1 Race Replay, F1 Pitwall) | Strategy dashboards, race replays, Monte Carlo for fantasy teams | Descriptive or fantasy-focused; they show what happened, not what to do next |
| Prediction markets ([Kalshi, Polymarket](https://deadspin.com/prediction-markets/sports/formula-1/)) | Real-money contracts on race winner, podium, safety car and red flag | Not a tool, but a free market forecast to benchmark your probabilities against |

The niche is the decision engine: given the state right now, which pit call has the best risk-adjusted outcome, and how sure are we?

## Reusable resources and repos

Almost all the plumbing exists; the new work is the race-state model, the strategy valuation and the evaluation. Take, don't rebuild.

**Data**

| Resource | License or access | What to take | Use in |
| --- | --- | --- | --- |
| [FastF1](https://github.com/theOehrly/Fast-F1) | MIT | Timing, tire stints, telemetry and results as pandas DataFrames, with built-in caching | M1 data layer |
| [OpenF1](https://github.com/br-g/openf1) | Historical data from 2023 free, no key; live streaming is paid ([docs](https://docsearch.algolia.com/mcp/docs/repo/br-g/openf1)) | Laps, pit stops, stints, race control flags, weather, telemetry at about 3.7 Hz ([spec](https://apis.apievangelist.com/store/openf1)) | M1 replay feed, M6 live mode |
| [TUMFTM f1-timing-database](https://github.com/TUMFTM/f1-timing-database), [racetrack-database](https://github.com/TUMFTM/racetrack-database) | Open source (check each license) | Older timing history; track center lines and widths for 20+ circuits | M1 priors, M2 physics |
| Kalshi and Polymarket public market data | Read-only | Pre-race and in-race implied probabilities | M1 benchmark |

**Modeling and simulation**

| Resource | License | What to take | Use in |
| --- | --- | --- | --- |
| [TUMFTM race-simulation](https://github.com/TUMFTM/race-simulation) | LGPL-3.0 | Lap-wise race structure, pit-loss and overtaking logic, the free-track "basic strategy" idea | M1 reference design |
| [TUMFTM laptime-simulation](https://github.com/TUMFTM/laptime-simulation) | Open source (check) | Quasi-static lap-time simulation approach | M2 physics |
| PyMC or NumPyro | Apache-2.0 | Hierarchical Bayesian pace model | M1 |
| SciPy (`scipy.stats.qmc`) | BSD-3 | Sobol sequences for variance reduction | M1 |
| NumPy, Numba | BSD | Vectorized simulator, hot loops | M1 |
| filterpy (or your own 30 lines) | MIT | Kalman filter reference | M1 |
| DuckDB | MIT | Local analytical store for laps and backtests | M1 |

**ML, performance and product**

| Resource | License | What to take | Use in |
| --- | --- | --- | --- |
| Gymnasium, Stable-Baselines3 | MIT | RL environment interface; PPO and DQN | M3 |
| XGBoost, PyTorch | Apache-2.0, BSD-3 | Lap-time baseline; neural surrogate | M3 |
| JAX | Apache-2.0 | GPU simulator backend | M5 |
| PyO3 + Rust | Apache-2.0 / MIT | Fast simulator core callable from Python | M5 |
| FastAPI, Next.js | MIT | API and dashboard | M6 |
| Claude Code + GSD, Codex | n/a | Build loop and independent code review | All |

On LGPL code: reading it and reimplementing the ideas with a citation is fine. Copying files into your repo brings license obligations, so don't.

## Architecture

Each lap passes through the same chain of modules, and the key ones sit behind fixed interfaces, so later milestones swap in better versions without rewrites.

```text
Data layer (DuckDB; FastF1, OpenF1, market odds; as-of accessor, no look-ahead)
        |                     |                       |
   Pace model           Tire filter (Kalman)     Race regime (Markov)
 (Bayesian -> physics/ML) (hidden wear per car)  (green/VSC/SC/red/rain)
        \                     |                       /
                 Race state (this lap)
                         |
          Simulator backend (50,000 races; NumPy -> JAX/Rust)
                         |
     Strategy policy (Longstaff-Schwartz + CVaR; RL, game theory later)
            /                                  \
 Dashboard (FastAPI + Next.js)        Backtester (walk-forward, StratBench)
```

Read it top to bottom once per lap: data feeds three models, they combine into one race state, the simulator runs it forward 50,000 times, and the policy ranks the pit options.

**Plug-in interfaces** (typed Protocols in `f1si/interfaces.py`; every implementation passes the same shared tests)

- `PaceModel` predicts lap-time distributions. Bayesian in M1; physics, hybrid and XGBoost versions later.
- `StrategyPolicy` takes a race state and returns a pit decision. Longstaff-Schwartz in M1; RL and game-theory versions later.
- `SimulatorBackend` runs N races from a state. NumPy in M1; JAX and Rust in M5.

**Race state, the object every module shares** (one car shown, values illustrative):

```json
{"lap": 15, "laps_total": 57,
 "regime": {"green": 0.93, "vsc": 0.03, "sc": 0.04},
 "pit_loss_s": {"green": 22.1, "sc": 11.5},
 "cars": [
  {"driver": "ALO", "position": 6, "gap_ahead_s": 1.4, "gap_behind_s": 1.8,
   "compound": "SOFT", "tire_age": 14,
   "wear_rate_s_per_lap": 0.071, "wear_sd": 0.012,
   "pace_offset_s": -0.18, "stops_done": 0, "compounds_used": ["SOFT"]}
 ]}
```

The regime probabilities and the wear uncertainty are what make it stochastic: the simulator samples from them instead of assuming one future.

## How a strategy call works

Every lap the platform answers one question: pit now, or wait, and what does each choice cost in expected position and in tail risk? The numbers below are illustrative, to show the shape of the output.

A typical live-replay session, following one driver through the 2023 Bahrain GP:

1. **Lap 1 to 10.** The Kalman filter learns this car's tire wear from lap times. Uncertainty is wide at first and narrows each lap. Recommendation: stay out, no decision value yet.
2. **Lap 14.** Degradation estimate firms up; the car behind is 1.8 s back on fresher tires. The optimizer flags an undercut threat: pitting on lap 15 versus 18 changes expected finish from P6.4 to P6.1, and the worst-10% outcome from P11 to P9.
3. **Lap 15.** Recommendation: box this lap. The dashboard shows the finishing-position fan chart for each option and the reason ("undercut risk from car 2").
4. **Lap 31, safety car.** The regime model jumps to "safety car" and pit loss drops sharply. All 50,000 continuations are re-run from the new state; a cheap second stop now beats running to the end.
5. **After the race.** The backtester compares the platform's calls with the team's actual calls and the final result, and logs calibration.

**What the user sees each lap**

| Output | Meaning |
| --- | --- |
| Strategy table | Each option (pit now, pit in 1 to 5 laps, stay out) with mean finish, standard deviation and CVaR at 10% |
| Fan chart | Finishing-position distribution for the top options |
| Regime gauge | Current probabilities of green flag, VSC, safety car and rain in the next 5 laps |
| Tire panel | Estimated wear rate with its uncertainty band, per car |
| Reason line | One sentence on what drives the call (undercut threat, cliff risk, safety-car window) |
| Risk dial | The risk-appetite setting, from "protect points" to "chase the win" |

## Data, validity and honesty

The biggest risk is not a crash but a model that runs fine and quietly gives believable wrong answers. These rules are as important as any feature.

**Look-ahead.** Every backtest function receives only data up to the current lap, through one "as-of" accessor. A test fails the build if anything reads a future row. One leak can make a useless model look brilliant.

**The 2026 break.** Cars and tires changed, grip dropped about 10% and strategy shifted toward one-stops. Treat 2022 to 2025 as training eras and 2026 as out-of-sample. Give the pace model an era effect, and report results separately per era.

**Hidden variables.** Fuel loads, tire temperatures and wear are not public. Tire state is a latent variable you estimate, which is exactly why the Kalman filter exists. Say so in the README.

**Data coverage.**

- FastF1 timing and telemetry start in 2018.
- OpenF1 history is free from 2023, but live streaming is paid. Default to live replay of past races; treat live mode as optional.
- Simulations never reproduce one real race exactly (the TU Munich authors say the same), so validate distributions across many races, not single results.

**Overfitting.** Testing many strategy variants on the same races inflates results. Lock one holdout set (for example the second half of 2026) and touch it once, at the end of each milestone.

**Honest claims.** Put only measured numbers on the resume. "Beats real team strategy" needs holdout evidence with confidence intervals; without it, write "compared against".

**Licensing and terms.** FastF1 and OpenF1 are unofficial and not affiliated with Formula 1. Keep the project non-commercial, don't republish raw data dumps, and credit sources. Use prediction-market prices as a read-only benchmark; this is not a trading or betting bot.

## Lean MVP: one race, end to end (6 weeks)

Get one race working completely before anything fancy: the 2023 Bahrain GP, because OpenF1 has it free and the Mercedes RSRL paper used it, so you get a published number to compare against. Build it with Claude Code + GSD, and have Codex review each phase.

**Week 1.** Set up the repo (uv, ruff, pytest, GitHub Actions) and run `/gsd:new-project` with the master prompt. Pull 2023 to 2025 data through FastF1 into DuckDB. Plot lap time by stint for Bahrain 2023. Read the Heilmeier 2020 paper and skim TUM's `racesim_basic`.

**Week 2.** Fuel-correct lap times and fit simple linear tire wear per compound (no Bayes yet). Build the free-track optimizer: brute-force every one- and two-stop plan for the fastest total race time.

**Week 3.** Build the Monte Carlo simulator: pit loss, overtaking chance from pace gap, and a simple per-lap safety-car probability. Vectorize it until 50,000 races run in under 10 seconds.

**Week 4.** Add the Kalman tire filter and the live-replay loop that steps through the race lap by lap.

**Week 5.** Add the Longstaff-Schwartz pit valuation and CVaR ranking. Compare its calls on Bahrain 2023 with what the teams actually did.

**Week 6.** Backtest 10 races, add a one-page Streamlit view, and write the README with real results and a `DECISIONS.md` explaining every method choice.

**Go or no-go at week 6:** the simulated finishing distributions roughly match real results across the 10 races, and you can explain every module out loud. If yes, continue to the full roadmap and upgrade pieces one at a time (simple wear model to Bayesian, constant safety-car rate to the Markov regime model). If no, fix the simulator before adding anything.

## Build roadmap

Six milestones over roughly 40 weeks of part-time work, each one shipping something that works on its own and passing a gate before the next begins.

| Milestone | Weeks | Contents | Gate before next |
| --- | --- | --- | --- |
| M1 Core stochastic engine | 1-10 | Data layer, Bayesian pace, Kalman tire filter, Markov regimes, Monte Carlo, LSM + CVaR, backtester (MVP in weeks 1-6) | Calibrated on 20 races, zero look-ahead |
| M2 Physics | 11-16 | Point-mass lap sim, tire thermal/wear model, hybrid pace model | Hybrid beats data-only on held-out stints |
| M3 ML and AI | 17-24 | XGBoost baseline, neural surrogate, PPO agent vs LSM and team calls | RL vs LSM reported on Bahrain 2023 |
| M4 Multi-agent and season | 25-30 | Cars react to each other; championship dynamic programming | Undercut responses realistic in replay |
| M5 Performance | 31-34 | JAX and Rust (PyO3) backends, parity tests | Matches NumPy; 50,000 races under 1 s |
| M6 Product | 35-40 | FastAPI + Next.js, OpenF1 live mode, Docker, deploy | Public link; live replay end to end |

The order is deliberate: RL needs a working simulator to train in, the Rust and JAX versions need a correct NumPy version to check against, and the product needs results worth showing. Start each milestone after M1 with `/gsd:new-milestone`, implementing against the existing interfaces.

## Evaluation

Measure three things separately: are the models statistically correct, are the predictions calibrated, and do the strategy calls beat sensible alternatives?

**1. StratBench, an in-house race set.** About 40 races from 2023 to 2026: normal dry races, safety-car-heavy races, wet races, and 2026 races as a separate out-of-sample group. Each race stores the real lap data, the real strategies and the result, so scoring is automatic.

**2. Synthetic recovery tests.** Generate fake races from known parameters and check each model recovers them. This catches "runs but wrong" bugs that real data hides.

**3. Metrics.** Targets below are proposed starting points; adjust after the MVP.

| Metric | What it checks | Proposed target |
| --- | --- | --- |
| Next-lap time error (fuel-corrected) | Pace and tire models | At least 15% lower than a per-compound linear baseline |
| Kalman wear estimate on synthetic stints | Filter correctness | Within 10% of truth by lap 8; 95% intervals cover truth about 95% of the time |
| 90% finishing-position interval coverage | Simulator calibration | 85% to 95% of real finishes inside the interval |
| Brier score, podium and top-10 | Probability calibration | Better than a grid-position baseline; reported next to market-implied odds |
| Strategy value on holdout races | Decision quality | Expected positions gained vs. actual team calls, with confidence intervals |
| RL vs. Longstaff-Schwartz, Bahrain 2023 | Method comparison | Report both; RSRL's published P5.33 as the outside reference |
| Simulator runtime, 50,000 races | Performance | Under 10 s in NumPy; under 1 s in JAX or Rust |
| Backend parity | Correctness of fast versions | JAX and Rust match NumPy within tolerance for the same seeds |
| Look-ahead violations | Backtest integrity | Zero, enforced in CI |

**4. External comparisons.** Three outside yardsticks: what the teams actually did, what prediction markets priced before and during the race, and the published RSRL result.

## Risks, open questions and next steps

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| AI-written statistics code is wrong but looks right | High | Synthetic recovery tests, Codex review per phase, docstrings that state the math, `DECISIONS.md` |
| 2026 rules break models trained on earlier years | High | Era effects in the pace model, 2026 kept out-of-sample, results reported per era |
| Scope sprawl across six milestones | High | Each milestone ships and works alone; go/no-go gate before the next |
| Key variables (fuel, tire temperature) are not public | Certain | Model them as hidden state; state the assumption plainly |
| Live data costs money | Medium | Live replay of past races as the default; live mode optional |
| RL does not beat the Longstaff-Schwartz optimizer | Medium | Still a valid result; report it honestly with the reasons |
| Interviewers probe a module you can't explain | Medium | Have Claude walk through each file after every phase; practice explaining one module per week |

**Open questions**

- Which audience comes first, quant, motorsport or software? That decides which milestone gets the most polish.
- One driver's strategy, or every car on the grid at once (needed for M4)?
- Pay for OpenF1 live access during the 2027 season, or stay with replay?
- PyMC (simpler) or NumPyro (faster, pairs with JAX in M5)?

**Next steps (first two weeks)**

- [ ] Install uv, Claude Code, Codex and GSD; create the GitHub repo
- [ ] Run `/gsd:new-project` with the master prompt
- [ ] Pull the 2023 Bahrain GP with FastF1 and plot lap time by stint
- [ ] Read Heilmeier et al. 2020 and the RSRL paper; note three ideas from each in `DECISIONS.md`
- [ ] Pick the first 10 StratBench races

## Sources

- [TUMFTM race-simulation (GitHub)](https://github.com/TUMFTM/race-simulation)
- [Heilmeier et al. 2020, Monte Carlo methods in a race simulation (Applied Sciences)](https://www.mdpi.com/2076-3417/10/12/4229/html)
- [Thomas et al. 2025, Explainable RL for F1 Race Strategy (arXiv)](https://arxiv.org/abs/2501.04068v1)
- [Mercedes-AMG tyre-energy forecasting research (CatalyzeX)](https://www.catalyzex.com/author/Joseph%20McMillan)
- [awesome-f1 list of tools and data](https://github.com/subinium/awesome-f1)
- [FastF1 (GitHub)](https://github.com/theOehrly/Fast-F1)
- [OpenF1 (GitHub)](https://github.com/br-g/openf1) and [OpenF1 access tiers](https://docsearch.algolia.com/mcp/docs/repo/br-g/openf1)
- [OpenF1 API spec](https://apis.apievangelist.com/store/openf1)
- [2026 F1 rule changes guide (Flashscore/AFP)](https://www.flashscore.com/news/auto-racing-formula-1-tyres-wings-and-drs-a-guide-to-the-major-f1-rule-changes-for-2026/ltHDbdak)
- [Pirelli expects more two-stop races (GrandPrix.com)](https://www.grandprix.com/news/pirelli-expects-more-two-stop-races-as-2026-progresses.html)
- [Pirelli's plan against one-stop races (Motorsport.com)](https://www.motorsport.com/f1/news/pirellis-plan-to-combat-continuous-one-stop-races-in-f1-2026/10807616/)
- [F1 prediction markets overview (Deadspin)](https://deadspin.com/prediction-markets/sports/formula-1/)
- [GSD for Claude Code and Codex (open-gsd)](https://p.codekk.com/detail/6a19d1d45b02fc5c75bba164)
