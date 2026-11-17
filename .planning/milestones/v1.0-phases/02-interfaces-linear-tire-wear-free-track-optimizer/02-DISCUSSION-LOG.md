# Phase 2: Interfaces, Linear Tire Wear & Free-Track Optimizer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-11
**Phase:** 02-interfaces-linear-tire-wear-free-track-optimizer
**Areas discussed:** Fuel & wear fitting, Optimizer rules, Interface contracts, What you see

---

## Fuel & wear fitting

**Fuel effect**

| Option | Description | Selected |
|--------|-------------|----------|
| Fit jointly | One regression with driver pace, fuel × lap, wear × tire age; identified by the pit-stop reset | ✓ |
| Fixed constant | Subtract a published value (~0.055 s/lap), then fit wear only | |
| Fit, fall back to fixed | Fit jointly; use the constant if the fit is implausible or unidentified | |

**Clean laps**

| Option | Description | Selected |
|--------|-------------|----------|
| Same as plot + outliers | Drop the plot's faded laps and robust outliers; one shared definition | ✓ |
| Same as plot only | Drop the faded laps only | |
| Robust regression, no outlier drop | Huber loss instead of removing outliers | |

**Fit scope**

| Option | Description | Selected |
|--------|-------------|----------|
| One race, any cutoff | Fit from a RaceSnapshot at race end or any lap | ✓ |
| One race, race end only | Complete race only | |
| Same circuit history + this race | Earlier races at the track as a starting estimate | |

**Pace offsets and uncertainty**

| Option | Description | Selected |
|--------|-------------|----------|
| Per-driver offset + SE | Driver intercepts, shared wear per compound, SE and 95% CI | ✓ |
| Per-driver offset, no SE | Point estimates only | |
| Per-driver wear too | Each driver gets their own slopes | |

---

## Optimizer rules

**Pit loss source**

| Option | Description | Selected |
|--------|-------------|----------|
| Measured from in/out laps | In+out lap minus two predicted clean laps, median of visible stops | ✓ |
| Jolpica pit-lane duration | Pit-lane time from Jolpica | |
| Fixed per-circuit table | Hand-entered values | |

**Rules enforced**

| Option | Description | Selected |
|--------|-------------|----------|
| Real F1 rules | Two compounds, actual start tire and age, min stint length, wet races skipped | ✓ |
| Real rules, free start tire | Optimizer also picks the starting compound | |
| Minimal rules | Two-compound rule only | |

**Plan from**

| Option | Description | Selected |
|--------|-------------|----------|
| Any lap's RaceState | Plans the rest of the race from current state | ✓ |
| Lap 0 only | Pre-race plan only | |

**Whose plan**

| Option | Description | Selected |
|--------|-------------|----------|
| Per driver | `--driver`; default race winner | ✓ |
| Generic car | One representative plan | |
| Every driver | Table for all 20 | |

---

## Interface contracts

**PaceModel output**

| Option | Description | Selected |
|--------|-------------|----------|
| Mean + SD per lap | Vectorized Normal mean and SD; simulator samples | ✓ |
| Samples | Model returns N draws | |
| Both | Mean+SD required plus a default sample method | |

**User's note:** After this question the user said: "For the rest of the questions you ask me just pick whats recommended by u." The remaining Interface-contracts questions (implementations in Phase 2, shared test suite, RaceState scope, placeholder fields, builder) and all "What you see" questions were not asked. Claude chose the recommended options (CONTEXT.md D-10..D-18, marked *Claude's pick*).

---

## What you see

Not asked; the recommended options were chosen per the user's instruction above (CONTEXT.md D-15..D-18).

---

## Claude's Discretion

- D-10..D-18 (Claude's picks per user instruction)
- Regression method, outlier threshold, minimum clean laps, minimum stint length, default pit loss, module layout, brute-force mechanics, hypothesis usage

## Deferred Ideas

- Per-driver wear slopes (Phase 4/7)
- Circuit-history prior (Phase 7)
- Free starting-tire choice
- 3-stop and wet-race strategy
- Tire cliff and track evolution (Phase 7 / M2)
- Regime-dependent pit loss (Phase 8)
