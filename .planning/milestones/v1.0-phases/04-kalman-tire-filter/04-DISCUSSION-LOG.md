# Phase 4: Kalman Tire Filter - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-12
**Phase:** 04-kalman-tire-filter
**Areas discussed:** What the filter estimates, Inputs and priors, How PAC-04 is tested, Simulator integration, What you see

**How the questions were answered:** the owner asked for discuss, plan and execute in one go and said: "Choose whatever you recommend." The workflow therefore ran in auto mode. All areas were selected, and Claude chose its recommended option for every question. Each pick is marked *Claude's pick* in CONTEXT.md.

---

## What the filter estimates

**State**

| Option | Description | Selected |
|--------|-------------|----------|
| Level + wear rate (local linear trend) | Two states per car per stint; the level absorbs unknown baseline pace | ✓ |
| Wear rate only | Needs a known baseline (driver offset), which is unidentified early in a race | |
| Cumulative wear (s) only | Same information as the rate, but RaceState holds a rate | |

**Process noise**

| Option | Description | Selected |
|--------|-------------|----------|
| Zero by default, `q` parameter available | Matches the linear truth and the simulator, so synthetic coverage is exact | ✓ |
| Small random walk on the rate | Allows drift and cliffs, but over-covers on linear synthetic truth | |

**Implementation**

| Option | Description | Selected |
|--------|-------------|----------|
| Own NumPy, Joseph form | No dependency; typed; about 30 lines | ✓ |
| filterpy | Unmaintained and untyped | |

## Inputs and priors

| Question | Selected | Alternatives considered |
|----------|----------|-------------------------|
| Wear prior | As-of Phase 2 compound fit, else a documented wide generic prior labelled "prior only" | Earlier races via history (deferred); a flat prior (too weak) |
| Fuel | As-of fit, else a documented prior; the fuel SD goes into the wear band | Ignore fuel (biased); estimate it inside the filter (not identifiable within a stint) |
| Noise | As-of `sigma_s`, else a documented default; a pooled field estimate is allowed | Full-race sigma (look-ahead) |
| Laps used | Phase 2 clean-lap rule plus a ~3 SD innovation gate; skipped laps run predict only | All laps (in/out laps and SC laps would distort the estimate) |

## How PAC-04 is tested

| Question | Selected | Alternatives considered |
|----------|----------|-------------------------|
| Synthetic truth | Optional per-driver wear deviations; defaults byte-identical | Shared compound rate only (the test would be trivial) |
| Metric | Mean absolute relative error at stint lap 8 ≤ 10% over ≥ 1,000 stints; coverage inside a binomial 99.9% band | Median error (weaker); every stint within 10% (impossible at real noise) |
| Feasibility | Compute analytically first; if not attainable, raise it with the owner, never tune to pass | Tune noise or prior until it passes (rejected: Phase 3 lesson) |

## Simulator integration

| Question | Selected | Alternatives considered |
|----------|----------|-------------------------|
| How the state carries the filter | Optional builder input plus a new `wear_source` field (`"fit"` / `"filter"`) | Always overwrite the wear fields (changes Phase 3 results) |
| How the simulator uses it | Per-car rate and SD for the current stint, from a new draw stream; `"fit"` cars byte-identical | Per-car for all stints (new tyres have no car data); reuse the Sobol slots (moves the CRN draws) |

## What you see

| Question | Selected | Alternatives considered |
|----------|----------|-------------------------|
| Command | New `f1si wear-filter <race> --driver X [--lap N]`, printing per lap and writing a PNG | Add a flag to `f1si wear` (that command is the hindsight fit, which would mix two meanings) |

## Claude's Discretion

Module layout, exact prior values and gate threshold (logged in DEC entries), vectorization, and plot styling.

## Deferred Ideas

Tyre cliff and non-linear wear; hierarchical pooling (Phase 7); wear priors from earlier races; adaptive noise and traffic models; physics wear (M2); the live replay loop (Phase 5).
