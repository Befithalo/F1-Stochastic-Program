# Roadmap: F1 Stochastic Intelligence Platform (M1)

## Overview

Milestone M1 builds the core stochastic engine. Phases 1-6 are the lean MVP (BUILD_PLAN weeks 1-6): data, linear tire model and free-track optimizer, Monte Carlo simulator, Kalman filter, Longstaff-Schwartz strategy with live replay, then a 10-race backtest with a Streamlit page and README. A go/no-go check follows Phase 6. Phases 7-8 upgrade the pace model to hierarchical Bayesian and the safety-car rate to a Markov regime model, then finish with the 20-race backtest and the one-time holdout. Each phase ends with CI green and a plain-language explanation of what was built (UI-03).

## Phases

- [ ] **Phase 1: Foundation & Data** - Repo, CI, seeded randomness, DuckDB cache, lap-time-by-stint plot, as-of accessor with look-ahead test
- [ ] **Phase 2: Interfaces, Linear Tire Wear & Free-Track Optimizer** - Protocols and RaceState, fuel-corrected linear wear, brute-force 1/2-stop plan
- [ ] **Phase 3: Monte Carlo Simulator** - Vectorized NumPy simulator, 50,000 races under 10 s, variance reduction, constant SC probability
- [ ] **Phase 4: Kalman Tire Filter** - Hidden tire wear estimated per car with uncertainty, verified on synthetic stints
- [ ] **Phase 5: Longstaff-Schwartz Strategy & Live Replay** - Ranked pit options with CVaR, risk setting, reasons, Bahrain 2023 replay end to end
- [ ] **Phase 6: MVP Backtest, Streamlit View & README** - 10-race walk-forward backtest, team-call comparison, one-page view, README with real results
- [ ] **Phase 7: Bayesian Pace Model** - Hierarchical PyMC pace model with era effect, recovered on synthetic data, beats linear baseline
- [ ] **Phase 8: Markov Regimes & Full Backtest** - Regime model and regime-dependent pit loss, 20-race per-era backtest, holdout touched once

## Phase Details

### Phase 1: Foundation & Data

**Goal**: User can load 2023-2025 races into a local cache, see Bahrain 2023 lap times by stint, and trust that no code can read future data
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, FND-03, FND-04, DAT-01, DAT-02, DAT-03, DAT-04, DAT-05, UI-03
**Success Criteria** (what must be TRUE):

  1. A push to GitHub runs lint, type-check and tests in CI, and CI is green
  2. User runs one command and gets 2023-2025 laps, stints, pit stops and results in a local DuckDB file
  3. User can produce a lap-time-by-stint plot for Bahrain 2023 from the cache
  4. Asking the as-of accessor for lap N never returns rows after lap N, and a deliberately leaking test case fails the build
  5. Every cached race shows its regulation era, and 2026 races are flagged out-of-sample; the same seed gives identical random results; DECISIONS.md exists with the first entries

**Plans:** 5/11 plans executed

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Bootstrap: scaffold, CI config, repo hygiene + F1 Docs commit; owner approves dependencies and installs uv (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Walking skeleton part A: toolchain, failing end-to-end test, leaf modules, normalized schema, transactional DuckDB storage, RaceSource protocol (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Walking skeleton part B: synthetic generator → loader → `f1si load` / `f1si races` with eras; end-to-end test green; first push, CI green on both OSes (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — Complete race record (track status, race control, weather, results, lap cutoffs) and resilient resumable loader (wave 4)
- [x] 01-05-PLAN.md — AST import-ban guard, planted leak, CI canary; DECISIONS.md first entries (wave 4)
- [ ] 01-06-PLAN.md — Rate-limited caching HTTP client, Jolpica client, race-control → track-status mapping (wave 4)

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 01-07-PLAN.md — As-of / results / out-of-sample doors, RACE_END, 2026 lock; future-scramble property test and meta-test (wave 5)
- [ ] 01-08-PLAN.md — OpenF1 source and pit-lane start rule; `f1si load` defaults to OpenF1 + Jolpica; real Bahrain 2023 load (wave 5)

**Wave 6** *(blocked on Wave 5 completion)*

- [ ] 01-09-PLAN.md — Lap-time-by-stint plot (`f1si plot bahrain-2023`) with stint-boundary markers, scramble-registered (wave 6)

**Wave 7** *(blocked on Wave 6 completion)*

- [ ] 01-10-PLAN.md — Network tests + weekly real-data workflow (not a required check); full 2023-2026 load with every in-sample race accounted for (wave 7)

**Wave 8** *(blocked on Wave 7 completion)*

- [ ] 01-11-PLAN.md — Plain-language explainer, decision-log final pass, final push with CI green (wave 8)

### Phase 2: Interfaces, Linear Tire Wear & Free-Track Optimizer

**Goal**: User can get the fastest free-track 1- or 2-stop plan for a race from fitted, fuel-corrected tire wear, behind interfaces later milestones can plug into
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: INT-01, INT-02, INT-03, PAC-01, PAC-02
**Success Criteria** (what must be TRUE):

  1. `f1si/interfaces.py` defines `PaceModel`, `StrategyPolicy` and `SimulatorBackend`, and mypy strict accepts them
  2. A shared test suite runs against each implementation that exists and fails a non-conforming stub
  3. User can build a `RaceState` for Bahrain 2023 at any lap and the same object type is what later modules consume
  4. User sees a fitted wear rate (seconds per lap) for each compound on Bahrain 2023, from fuel-corrected lap times
  5. User gets the best 1-stop and 2-stop plan with total race time, found by checking every combination

**Plans**: TBD

### Phase 3: Monte Carlo Simulator

**Goal**: User can simulate 50,000 continuations of a race from any `RaceState` in under 10 seconds with a reliable, low-variance result
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: SIM-01, SIM-02, SIM-03, REG-01
**Success Criteria** (what must be TRUE):

  1. User passes a Bahrain 2023 `RaceState` and gets a finishing-position distribution for a chosen driver
  2. A benchmark test shows 50,000 races finish in under 10 seconds
  3. Safety cars occur at a per-lap probability and visibly change pit loss and gaps in simulated races
  4. A test shows Sobol plus antithetic sampling has lower variance than plain Monte Carlo at the same N
  5. The same seed reproduces identical results

**Plans**: TBD

### Phase 4: Kalman Tire Filter

**Goal**: User can watch the hidden tire-wear estimate for a car sharpen lap by lap, with an honest uncertainty band
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: PAC-03, PAC-04
**Success Criteria** (what must be TRUE):

  1. User runs the filter on a real stint and sees a wear-rate estimate with a band that narrows over the first laps
  2. On synthetic stints the estimate is within 10% of the true wear by lap 8
  3. On synthetic stints the 95% intervals contain the true value about 95% of the time
  4. The filter's wear mean and sd populate the `RaceState` fields the simulator reads

**Plans**: TBD

### Phase 5: Longstaff-Schwartz Strategy & Live Replay

**Goal**: User can replay Bahrain 2023 lap by lap for any driver and get a ranked, explained pit recommendation with uncertainty
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: STR-01, STR-02, STR-03, STR-04, RPL-01, RPL-02
**Success Criteria** (what must be TRUE):

  1. User starts a replay for any Bahrain 2023 driver and steps through every lap, seeing a recommendation each lap using only data up to that lap
  2. Each lap shows pit now, pit in 1-5 laps and stay out, ranked by mean finish and CVaR@10%, with the finish spread
  3. Moving the risk-appetite setting changes the ranking between mean-focused and tail-focused
  4. Each recommendation carries a one-sentence reason such as undercut threat, cliff risk or safety-car window
  5. The Longstaff-Schwartz policy passes the shared `StrategyPolicy` test suite

**Plans**: TBD

### Phase 6: MVP Backtest, Streamlit View & README

**Goal**: User can see how well the platform's calls and probabilities hold up across 10 real races, in one page and a README of measured results, and decide go or no-go
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: BKT-01, BKT-02, BKT-04, UI-01, UI-02
**Success Criteria** (what must be TRUE):

  1. User runs the walk-forward backtest on 10 races from 2023-2025 and the look-ahead test still passes
  2. The report shows Brier score for podium and top-10 next to a grid-position baseline, plus 90% finishing-interval coverage
  3. The report compares platform strategy calls with actual team calls, with confidence intervals
  4. User opens one Streamlit page showing strategy table, finishing fan chart, regime gauge, tire panel, reason line and risk dial for a driver and lap
  5. The README lists measured results only, states hidden-variable assumptions, and credits FastF1/OpenF1 with licensing notes

**Plans**: TBD
**UI hint**: yes

### Phase 7: Bayesian Pace Model

**Goal**: User can swap the linear pace model for a hierarchical Bayesian one that is proven to recover truth and predict better
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: PAC-05, PAC-06
**Success Criteria** (what must be TRUE):

  1. The PyMC model with car, driver, tire, fuel and era effects fits real 2023-2025 data and implements `PaceModel`
  2. On synthetic data generated from known parameters the model recovers them within stated tolerance
  3. On held-out laps the next-lap error is at least 15% lower than the per-compound linear baseline
  4. The replay and backtest run with the Bayesian model without changes outside the model swap

**Plans**: TBD

### Phase 8: Markov Regimes & Full Backtest

**Goal**: User gets regime-aware strategy calls and a final 20-race, per-era backtest with a once-only holdout evaluation
**Mode:** mvp
**Depends on**: Phase 7
**Requirements**: REG-02, REG-03, BKT-03, BKT-05
**Success Criteria** (what must be TRUE):

  1. The Markov model over green, VSC, SC, red and wet replaces the constant SC probability, and a synthetic test recovers its transition matrix
  2. Simulated pit loss differs by regime (for example cheaper under SC), and a safety car in replay changes the recommendation
  3. The backtest covers at least 20 races and reports every metric separately per regulation era
  4. A holdout set is defined and locked, then evaluated exactly once, with the result recorded in the README
  5. Live replay of Bahrain 2023 still works end to end and CI is green (M1 definition of done)

**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Data | 5/11 | In Progress|  |
| 2. Interfaces, Linear Tire Wear & Free-Track Optimizer | 0/0 | Not started | - |
| 3. Monte Carlo Simulator | 0/0 | Not started | - |
| 4. Kalman Tire Filter | 0/0 | Not started | - |
| 5. Longstaff-Schwartz Strategy & Live Replay | 0/0 | Not started | - |
| 6. MVP Backtest, Streamlit View & README | 0/0 | Not started | - |
| 7. Bayesian Pace Model | 0/0 | Not started | - |
| 8. Markov Regimes & Full Backtest | 0/0 | Not started | - |
