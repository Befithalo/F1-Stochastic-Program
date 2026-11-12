# Phase 3 explained: the Monte Carlo race simulator

This page is for you, the owner. It is a stub that grows with Phase 3 and is completed in plan 03-07. So far it covers only the first piece, the safety-car rate. Words in code font, such as `ScRateEstimate`, are names you will see in the files.

## What was built and why

**The safety-car rate.** The simulator needs to know how often a safety car comes out. The project counts safety-car deployments in earlier races and divides by the laps of those races. With a tiny history that ratio is noisy, so it starts from a prior belief: about 1 safety car per 100 laps, worth about 300 laps of evidence (roughly five races). The result is a Beta-Binomial estimate with a 90% interval. For the first race in the history, such as Bahrain 2023, there are no earlier races, so the estimate is the prior alone and says so (`is_prior_only`).

**The safety-car length.** The simulator also needs how many laps a safety car lasts. It uses the median length measured in earlier races, or 4 laps when fewer than 5 earlier safety cars exist.

**Test data with safety cars.** The synthetic race generator can now be told on which laps to send a safety car. This gives tests a known true answer.

## How the pieces connect

```
earlier races only (as-of door, no future data)
      |
safety-car rows in track status  -->  estimate_sc_rate (regime/sc_rate.py)
      |
ScRateEstimate: rate per lap, 90% interval, duration in laps
```

## File-by-file tour

Paths are relative to the repository folder.

- `src/f1si/regime/sc_rate.py` is the safety-car estimator: it counts deployments with an edge rule (a safety-car row after a red flag is a restart, not a new deployment), measures lengths in leader laps, and returns the Beta-Binomial posterior mean, its 90% interval and the duration.
- `src/f1si/sim/constants.py` holds the named simulator settings (dirty-air gap, pass-chance curve, safety-car slowdown, restart spacing, input limits); all are documented defaults, not fitted.
- `src/f1si/sim/draws.py` makes the random numbers: scrambled Sobol points paired with their mirror images (antithetic), plain mirrored normals for the noisy parts, and one reproducible stream per lap so changing one driver's plan cannot change anyone else's luck.

## Interview questions

### Q1. Why does the safety-car rate use a prior?

With only a few earlier races, a plain count can say "never" or "twice as often as usual" by luck. A weak prior of 1% per lap, worth about five races, keeps the estimate sensible early on and fades as real races pile up. For the very first race it is the whole answer, and the result is flagged as prior-only.

### Q2. Why only earlier races?

Using the race being replayed, or later ones, would be look-ahead: the estimate would know where the safety cars came. The estimator only receives the history of earlier races from the as-of door, and a scramble test changes all future data and requires the answer to stay the same.

### Q3. How is the estimate tested against a known rate?

Synthetic races are built with safety cars placed at a known chance of 2.5% per lap. The estimator sees 23 earlier races of 100 laps, and its 90% interval must contain 2.5% in at least 4 of 5 random seeds. A dedicated test also checks the counting rules on hand-built track-status sequences.

## Good to know

- **Stub.** This page is incomplete on purpose and is finished in plan 03-07.
- **What is not modelled.** Virtual safety cars and red flags (D-02); a virtual safety car can reuse the same mechanics in Phase 8.
- **Prior.** Beta(3, 297) is an assumption (A3), logged in `DECISIONS.md` as DEC-075.
