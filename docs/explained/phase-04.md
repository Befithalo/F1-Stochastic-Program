# Phase 4 explained: the Kalman tyre-wear filter

This page is for you, the owner. It explains what Phase 4 built, in plain words, with real numbers from the 2023 Bahrain Grand Prix (Fernando Alonso, code ALO) and from synthetic races where the true answer is known. Words in code font, such as `WearFilter`, are names you will see in the files.

## What was built and why

**The filter.** Tyres slow a car down by a little more every lap, and nobody tells the team how much. The wear rate (seconds lost per lap of tyre age, s/lap) is hidden: only noisy lap times are visible. A Kalman filter reads one lap time at a time and keeps a best guess of the rate together with a band of uncertainty. Each clean lap narrows the band; a lap that is not clean (lap 1, a pit lap, a safety-car lap) leaves it alone. A lap that is more than three standard deviations from what the filter expected is skipped by an outlier gate, but never twice in a row (DEC-090).

**Three hidden quantities.** The filter tracks the lap-time level, the wear rate, and a small fuel-error term. Fuel and tyres look the same inside one stint (the car gets lighter as the tyres get older), so the data cannot fully separate them. The fuel-error state makes the reported band include that doubt (DEC-088).

**Priors that respect the clock.** Before a stint has any laps, the filter needs a starting belief. It takes one from the Phase 2 pace fit built from the same as-of snapshot, widened by a car-to-car allowance (`tau_car`). If that fit cannot identify a quantity yet, a generic documented guess is used and the output says "prior only" (DEC-091). Nothing from after the cutoff lap is ever read.

**The simulator wiring.** A car whose wear comes from the filter runs its current tyres on its own rate and its own uncertainty. `src/f1si/sim/numpy_backend.py` adds a virtual tyre column for it, `src/f1si/sim/kernel.py` takes one new per-column offset, and `src/f1si/sim/draws.py` supplies an extra random stream. Cars without a filter result are unchanged, and a stored Phase 3 reference proves it byte for byte (DEC-093, DEC-094).

**The command and chart.** `uv run f1si wear-filter bahrain-2023 --driver ALO` replays the race. At every lap it builds a fresh snapshot, pace fit and filter, then prints each stint's labelled priors and the lap-by-lap estimate with its 95% interval. It writes a band chart with the Phase 2 whole-race fit as a dashed line labelled "hindsight" (DEC-095). The full 57-lap replay took 8.1 to 8.4 s.

## How the pieces connect

```
race snapshot at lap N (as-of door, no future data)
      |
 pace fit of that snapshot (pace/linear.py)  -->  priors per stint ("fit" or "prior only")
      |
 WearFilter per stint (pace/kalman.py): predict one lap, update with the lap time
      |
 rows: rate mean, SD and 95% band per lap  -->  cutoff_row (newest visible row)
      |                                              |
 current_stint_snapshots                       chart and table (cli.py, plots/wear_filter.py)
      |
 build_race_state(wear_filter=...)  -->  CarState.wear_source "filter"
      |
 per-car wear draws in NumpySimulator  -->  finishing-position distribution
```

The look-ahead guard has a filter-fed variant: a future-scramble test changes all later data and requires the same filter output and the same race state. The replay command takes a new snapshot at each lap, so a test records that its cutoffs run 1, 2, 3 and so on.

## File-by-file tour

Paths are relative to the repository folder. `__init__.py` files are empty package markers and are left out.

### The package `src/f1si`

- `src/f1si/pace/kalman.py` is the filter: `WearPrior` (starting belief and noise), `WearFilter` (one lap at a time, with an outlier gate), `LapUpdate` and `FilterSnapshot` (what it reports), and `posterior_rate_sd` (the exact answer it must reproduce). The adapter half (`filter_stints`, `resolve_priors`, `current_stint_snapshots`, `cutoff_row`) turns an as-of race snapshot into per-stint, per-lap rate rows and says whether each prior came from the fit or is "prior only".
- `src/f1si/plots/wear_filter.py` draws the filter chart: the as-of wear-rate estimate with its shaded 95% band against race lap, stint boundaries, and the Phase 2 whole-race fit as a dashed line labelled hindsight. It also builds the safe file name `wear-filter-<race>-<DRIVER>.png`.
- `src/f1si/state.py` gives each car a `wear_source` ("fit" or "filter") and lets `build_race_state` take the filter results for the cars' current stints.
- `src/f1si/sim/numpy_backend.py` gives each filter car a virtual tyre column with its own rate and SD, and leaves fit cars alone.
- `src/f1si/sim/kernel.py` takes one new per-column offset so a filter car's uncertainty counts only laps run after the cutoff.
- `src/f1si/sim/draws.py` adds a fifth random stream, used only when a filter car needs it.
- `src/f1si/synthetic/generator.py` can give each driver their own wear-rate deviation, and the truth records it, so the recovery tests have a known answer.
- `src/f1si/cli.py` gained `wear-filter` with `--driver` and `--lap`.

### Tests

- `tests/pace/test_kalman_math.py` checks the filter against exact Bayesian regression and the closed-form band.
- `tests/pace/test_kalman_recovery.py` checks calibrated coverage and Bayes-optimal accuracy on synthetic stints and prints the 10% report.
- `tests/pace/test_kalman_adapter.py` checks the snapshot adapter, its labelled sources and the clean-lap rule.
- `tests/pace/test_kalman_incremental.py`, `tests/pace/test_kalman_narrowing.py` and `tests/pace/test_kalman_gate.py` check lap-by-lap equals batch, the narrowing band and the outlier gate.
- `tests/sim/test_filter_cars.py` checks that a filter car follows its own rate and SD and that fit cars are unchanged.
- `tests/sim/test_phase3_reference.py` guards the stored Phase 3 simulator output (arrays and a sha256 under `tests/fixtures`).
- `tests/test_cli_wear_filter.py` runs the command on a small synthetic cache, including refusals, and records the snapshot cutoffs.
- `tests/plots/test_wear_filter_plot.py` checks the chart.
- `tests/real/test_wear_filter_bahrain.py` is the opt-in check on real Bahrain 2023 data (skipped unless you have the local cache and ask for it).
- `tests/guards/consumers.py` registers the new filter functions and the filter-fed race-state consumer, so the future-scramble guard covers them.
- `tests/test_docs.py` checks that this page and the README stay complete.

## Interview questions

### Q1. What is a Kalman filter here, and why is it exact Bayesian regression when q = 0?

The filter keeps a Gaussian belief about the level, the wear rate and the fuel error, and updates it with each lap time. With no process noise (q = 0) the rate is one fixed unknown number for the whole stint, so every lap time is a straight-line observation of the same unknowns. Updating one lap at a time then gives the same answer as fitting all laps at once with the same prior. The tests check this against a closed-form regression to nine decimals, which shows the recursion has no mistake in it (DEC-088, DEC-089).

### Q2. Why is fuel a hidden third state, and what is the floor?

Inside one stint the car burns fuel and the tyres age at the same pace, so both appear as one straight line in the lap times. The data cannot split them. The fuel state carries a prior SD (`fuel_sd`), and the rate SD cannot fall below `tau * fuel_sd / sqrt(tau^2 + fuel_sd^2)` however many laps are seen, where `tau` is the rate prior SD. The band honestly includes that doubt instead of claiming more certainty than the data allow.

### Q3. Why can the PAC-04 target of 10% by stint lap 8 not be reached, and what is tested instead?

At honest lap noise (0.15 s) the best any estimator can do after 7 measured laps is a mean absolute relative error of about 17% (SOFT), 25% (MEDIUM) and 33% (HARD) when fuel is known. Our filter measured 19.4%, 28.3% and 35.0% on 2,000 synthetic stints each (22.9%, 31.9% and 38.2% with a fuel prior), just above that optimum as it should be. The owner decided (D-17, DEC-092) that accuracy is gated as Bayes-optimal: the filter's SD must match the closed form and its error must sit within Monte Carlo error of the optimum. The 10% figure is reported, not gated. Coverage is gated: the 95% band covered inside the 99.9% binomial band.

### Q4. How are priors chosen as-of, and why is the early fit a problem?

At each lap the Phase 2 pace fit is run on that lap's own snapshot, and its wear rate becomes the prior mean, with its standard error widened by `tau_car` because one car is not exactly the field average. Until the fit identifies a compound the prior is a generic guess, labelled "prior only". The fit is least reliable early. For ALO's SOFT stint the prior was "prior only" until lap 13; at lap 14 the fit gave +0.255 +/- 0.041 s/lap, while the whole-race hindsight value is about +0.12. At lap 20 (HARD) the prior was +0.129 +/- 0.035 and at lap 30 +0.136 +/- 0.031, against a hindsight HARD value of +0.121. So the early fit was biased high and its band did not reach the hindsight value; later laps agree much better.

### Q5. How does a filtered car differ in the simulator?

A filtered car runs its current tyres on its own rate and its own SD, drawn from a separate random stream, while cars without a filter result keep the fitted compound rate and the original streams. For ALO at lap 20 (5,000 races, seed 20260101) the simulated finish was mean 5.92 without the filter and 5.98 with it, and the 90% interval was P4 to P8 in both cases (width 4). So on this race and lap the filter did not change the interval at the precision of whole positions. This answers the open Phase 3 question about the ALO interval: the filter alone does not widen or narrow it here.

## Good to know

- **The band can step.** When a stint's prior switches from "prior only" to "fit" the displayed band can jump, so it is not monotone across that lap. The command prints a note at that lap. In the real replay the inputs behind the band changed at many laps (14, 15, 17 to 35), because the as-of fit updates every lap; only 10 consecutive pairs had unchanged inputs, and the band narrowed in all of them.
- **Early as-of fit bias (OQ2, D-19).** ALO's SOFT estimate went from about 0.17 to 0.26 s/lap when the fit first identified SOFT at lap 14, then the stint ended; the hindsight value is about 0.12. Reported as measured. Priors and `tau_car` were not tuned to hide it; changing them is a decision for the owner.
- **The prior includes the car's own laps (known limitation).** The field-wide fit used as the rate prior is fitted on all clean laps up to the cutoff, including the car's own laps in the stint being filtered, so those laps count twice. `tau_car` softens this. In the Bahrain 2023 cache ALO's current stint is about 6% of the clean laps behind the SOFT prior at lap 14 (12 of 193), which makes it a likely contributor to the lap-14 SOFT bias above. The method is unchanged; changing it is the owner's decision (DEC-091).
- **Narrowing depends on the prior.** With the whole-race fit as prior, ALO's three stints had a prior SD of about 0.030 s/lap and a noise estimate of 0.48 s, so seven measured laps narrowed the SD by only 5 to 7% (ratio 0.93 to 0.95). During the as-of replay the HARD stint 2 half-width fell from about 0.074 s/lap at its first used lap (lap 16) to about 0.045 by lap 30, and stint 3 from 0.060 (lap 36) to about 0.040 (lap 56).
- **Limits.** The filter assumes a constant rate inside a stint (q = 0), a straight line, and no tyre cliff or thermal effects. Fuel and wear cannot be separated inside a stint. Contaminated laps make the real band somewhat over-confident: with 5% contaminated laps the 95% interval covered 0.926 with the gate and 0.900 without (DEC-090).
- **Assumptions.** The generic priors, `tau_car` and the outlier gate are assumptions, logged in DEC-090 and DEC-091. The accuracy target restatement is DEC-092.
- **Where choices are logged.** DEC-088 to DEC-095 in `DECISIONS.md`: the three-state model (088), zero process noise (089), which laps update and the gate (090), priors (091), the accuracy target (092), `wear_source` and the state builder (093), simulator integration (094), the replay command (095).
- **Not here yet.** Strategy choice with filter output is Phase 5. Pooling wear information across cars and races (hierarchical models), which should improve accuracy, is Phase 7. The ALO interval comparison is one race and one lap, not a calibration study.
