# Phase 3: Monte Carlo Simulator - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-12
**Phase:** 03-monte-carlo-simulator
**Areas discussed:** Safety-car model, Overtaking model, Other cars & randomness, What you see

**How the questions were answered:** the owner selected all four areas. They rejected the first per-area question and said: "For every questions asked, just use what you recommend." From then on Claude chose its recommended option for every question without asking. Each one is marked *Claude's pick* in CONTEXT.md. The alternatives below are the options that were considered.

---

## Safety-car model

**Where the per-lap SC probability comes from**

| Option | Description | Selected |
|--------|-------------|----------|
| Earlier races, else a prior | Beta-Binomial pooled over earlier in-sample races via `AsOfAccessor.history`; a weak literature prior when there are too few races (Bahrain 2023 is round 1) | ✓ |
| Fixed literature constant | One documented rate for every race | |
| All cached races, any date | More data, but leaks the future into backtests | |
| Same circuit, earlier years | Too few data points per circuit in 2023–2025 | |

**Which events**

| Option | Description | Selected |
|--------|-------------|----------|
| SC only | REG-01 scope; VSC and red flags go to the Phase 8 regime model | ✓ |
| SC + VSC | Two event types now | |

**SC duration**

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed median from earlier races, fallback 4 laps | Occurrence is the random part | ✓ |
| Sampled from the empirical distribution | More realism, more parameters | |

**SC effect.** Order frozen, slowdown factor ~1.4, gaps compressed to ~1 s on restart, pit loss = ~0.5 × green as a documented placeholder until Phase 8 REG-03. Chosen because success criterion 3 requires SC to visibly change pit loss and gaps.

**Current regime at the cutoff.** `build_race_state` sets `{"sc": 1.0}` when an SC is active at lap N, and the simulator continues it. ✓

---

## Overtaking model

| Option | Description | Selected |
|--------|-------------|----------|
| Lap-by-lap time model with dirty air and a logistic pass chance on pace advantage | TU Munich / Heilmeier style; held at a minimum gap if the pass fails | ✓ |
| Pure pass-probability per lap from the pace gap, no time interaction | Simpler, loses dirty-air time cost | |
| Deterministic threshold pass | No randomness in passing | |

**Parameters**

| Option | Description | Selected |
|--------|-------------|----------|
| Documented defaults + sanity tests; fit per circuit later (Phase 6) | | ✓ |
| Fit from real overtakes now | Needs position-change data cleaning; outside the MVP | |

**Lapping and DNFs.** Not modeled; every car runs to `laps_total` (DEC-073). ✓

---

## Other cars & randomness

**Strategy for the other cars**

| Option | Description | Selected |
|--------|-------------|----------|
| Free-track optimizer's best plan per car, with a documented fallback, plus opportunistic stops under SC for non-forced cars | | ✓ |
| Their actual remaining real-world strategy | Look-ahead: uses the future | |
| No further stops | Breaks the two-compound rule | |

**What is sampled**

| Option | Description | Selected |
|--------|-------------|----------|
| Per-race car parameter draws (offset, wear, using SEs) plus per-lap noise | Honest uncertainty | ✓ |
| Per-lap noise only | Understates uncertainty | |

**Variance reduction.** Scrambled Sobol (seeded from the rng) for SC occurrence, car parameters and pass uniforms; antithetic pairs for everything; plain antithetic normals for per-lap noise. The test compares estimator variance across seeds at equal N. ✓

---

## What you see

| Option | Description | Selected |
|--------|-------------|----------|
| `f1si simulate <race> --driver X [--lap N] [--n] [--seed]`: text distribution table plus a bar-chart PNG | Matches `wear` and `plan` | ✓ |
| Text only | | |
| Python API only | | |

**Hindsight rule.** Kept from Phase 2: no `--lap` means a hindsight fit labelled as such; `--lap N` refuses when the fit is not identified. ✓
**Benchmark.** 50,000 races under 10 s on CI; NumPy first, Numba allowed for the passing loop if needed. ✓

---

## Claude's Discretion

- Module layout
- Constant values within the documented ranges
- Array layout and vectorization
- How SEs reach the simulator
- Odd-N handling
- Sobol dimension budget
- Numba use
- Lap-0 grid spacing

## Deferred Ideas

- VSC, red flags and circuit-specific SC rates (Phase 8)
- Measured SC/VSC pit loss (Phase 8)
- DNFs, first-lap incidents and lapping (Phase 6 calibration)
- Fitted overtaking parameters (Phase 6)
- Sampled SC rate and duration uncertainty (Phase 8)
- Reduced wear under SC (Phase 7 / M2)
- JAX and Rust backends (M5)
