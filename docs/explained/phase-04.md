# Phase 4 explained: the Kalman tyre-wear filter

This page is for you, the owner. It is a skeleton that plan 04-05 completes with real numbers. Words in code font, such as `WearFilter`, are names you will see in the files.

## What was built and why

**The filter.** Tyres slow a car down by a little more every lap, and nobody tells the team how much. The wear rate (seconds lost per lap of tyre age) is hidden: only noisy lap times are visible. A Kalman filter reads one lap time at a time and keeps a best guess of the rate together with a band of uncertainty. Each clean lap narrows the band; a lap that is not clean (lap 1, a pit lap, a safety-car lap) leaves it alone. The band includes the doubt about how much of the slowing is really fuel burning off, because fuel and tyres look the same inside one stint.

**The Phase 3 reference.** Before the simulator is touched in later plans, its output for a fixed seed and a fixed hand-built race is stored in the repository. A test compares the live simulator with it, so cars that keep the old fitted wear stay byte-identical.

## How the pieces connect

```
fuel-corrected lap times (one per lap, clean laps only)
      |
 WearFilter (pace/kalman.py): predict one lap, update with the lap time
      |
 wear rate mean and SD per lap  -->  FilterSnapshot (used by later plans)
```

The array core takes plain numbers. A later plan adds the adapter that reads a race snapshot through the as-of door.

## File-by-file tour

Paths are relative to the repository folder. `__init__.py` files are empty package markers and are left out.

### The package `src/f1si`

- `src/f1si/pace/kalman.py` is the filter: `WearPrior` (starting belief and noise), `WearFilter` (one lap at a time, with an outlier gate), `LapUpdate` and `FilterSnapshot` (what it reports), and `posterior_rate_sd` (the exact answer it must reproduce).

### Tests

- `tests/pace/test_kalman_math.py` checks the filter against exact Bayesian regression and the closed-form band.
- `tests/pace/test_kalman_incremental.py`, `test_kalman_narrowing.py` and `test_kalman_gate.py` check lap-by-lap equals batch, the narrowing band and the outlier gate.
- `tests/sim/test_phase3_reference.py` guards the stored Phase 3 simulator output.

## Interview questions

### Q1. Why is a Kalman filter exactly Bayesian regression when q = 0?

With no process noise the wear rate is one fixed unknown number for the whole stint, so every lap time is a straight-line observation of the same unknowns. Updating a Gaussian belief one observation at a time gives the same result as fitting all the laps at once with the same prior. The tests check this to nine decimals, which shows the recursion has no mistake in it.

### Q2. Why is fuel a third hidden state?

Inside one stint the car gets lighter and the tyres get older at the same pace, so both appear as one straight line in the lap times. The data cannot split them. A fuel-error state lets the filter admit that, so the reported band includes the doubt and does not claim more certainty than the data allow.

### Q3. What does the outlier gate protect against?

One bad lap, for example a lap lost in traffic, would drag the rate estimate and the filter could not forget it. The gate skips a lap that is more than three standard deviations from what the filter expected, but only after three laps have been used and never twice in a row, so a real change in pace cannot lock the filter out.

## Good to know

- **Status.** This page is a skeleton from plan 04-01; real-race numbers and the coverage results come in plan 04-05.
- **Limits.** The filter assumes a constant wear rate inside a stint (q = 0 by default), a linear trend, and no tyre cliff.
- **Where choices are logged.** DEC-088 to DEC-090 in `DECISIONS.md`: the three-state model (088), zero process noise (089), which laps update and the gate (090).
