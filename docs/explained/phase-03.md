# Phase 3 explained: the Monte Carlo race simulator

This page is for you, the owner. It explains what Phase 3 built, in plain words, with real numbers from the 2023 Bahrain Grand Prix. Words in code font, such as `RaceState`, are names you will see in the files.

## What was built and why

**The simulator.** Given a `RaceState` (a snapshot of the race at one lap), it plays out the rest of the race 50,000 times and records where every car finishes. Each run uses the fitted tyre model, a random lap-time wobble, pit stops, a possible safety car and a chance of passing. The answer is not one finishing position but a full distribution: "ALO finishes P4 in 75.3% of runs, P5 in 15.8%", and so on. It is `NumpySimulator` in `sim/numpy_backend.py`, and it fills the `SimulatorBackend` slot from Phase 2.

**The safety-car rate.** A safety car bunches the field and makes a pit stop cheaper, so it changes the best plan. The project counts safety-car deployments in earlier races and divides by the laps of those races. A tiny history is noisy, so the estimate starts from a prior belief of about 1 safety car per 100 laps, worth about 300 laps (roughly five races). Bahrain 2023 is the first race in the local history, so there are no earlier races: the estimate is the prior alone, 1.00% per lap with a 90% interval of 0.27% to 2.09%, and the command prints "prior only". A typical safety car lasts 4 laps (the fallback when fewer than 5 earlier ones exist).

**Pass or hold.** A follower that would end up closer than 0.5 s behind the car ahead either passes or is held at 0.5 s ("dirty air"). The pass chance is a logistic (S-shaped) curve of the pace advantage: 50% at 0.4 s faster, about 12% at equal pace and above 99% at 2 s faster (DEC-078). A successful pass costs the passer 0.3 s. These constants are documented defaults, not fitted yet.

**Variance reduction.** Plain random sampling is noisy. The simulator uses scrambled Sobol points (evenly spread, not clumpy) and pairs each draw with its mirror image (antithetic). At equal sample size this cuts the noise of the estimates by a measured 2.5 to 12 times (see Q3).

**The benchmark.** A test simulates 50,000 races of a 20-car, 57-lap race and requires it to take under 10 s. Measured on this machine: 1.45, 1.38 and 1.49 s, with the compile warm-up excluded (DEC-084).

**The command.** `uv run f1si simulate bahrain-2023 --driver ALO` prints one driver's finishing-position table, the safety-car source, how each car's plan was chosen, and the runtime, and writes a bar chart.

## How the pieces connect

```
race snapshot + History (as-of door, no future data)
      |                          |
 pace fit (pace/linear.py)   safety-car rate (regime/sc_rate.py)
      |                          |
      +--> RaceState (state.py) <+   plans (sim/plans.py), borrowed pace (sim/borrow.py)
                      |
   random draws (sim/draws.py) --> lap kernel (sim/kernel.py)
                      |
        NumpySimulator (sim/numpy_backend.py)
                      |
   finishing distribution --> table and PNG (cli.py, plots/simulate.py)
```

The safety-car rate is read only from earlier races through the as-of door, and a future-scramble test changes all later data and requires the same answer. In `--lap N` mode the snapshot and the history are both cut at lap N. Without `--lap` the pace fit uses the whole race, so the command says "This is a hindsight simulation" and makes no claim of foresight.

## File-by-file tour

Paths are relative to the repository folder. `__init__.py` files are empty package markers and are left out.

### The package `src/f1si`

- `src/f1si/regime/sc_rate.py` is the safety-car estimator: it counts deployments with an edge rule (a safety-car row after a red flag is a restart, not a new deployment), measures lengths in leader laps, and returns the Beta-Binomial posterior mean, its 90% interval and the duration.
- `src/f1si/sim/constants.py` holds the named simulator settings (dirty-air gap, pass-chance curve, safety-car slowdown, restart spacing, input limits); all are documented defaults, not fitted.
- `src/f1si/sim/draws.py` makes the random numbers: scrambled Sobol points paired with their mirror images (antithetic), plain mirrored normals for the noisy parts, and one reproducible stream per lap so changing one driver's plan cannot change anyone else's luck.
- `src/f1si/sim/kernel.py` is the compiled one-lap step (Numba): it applies pit losses, starts and ends safety cars (frozen order, slower laps, tight restart), holds a follower in dirty air or lets it pass with a logistic chance.
- `src/f1si/sim/plans.py` decides each car's pit plan: a plan you force is used exactly, every other car gets the optimizer's best plan, and a car the optimizer cannot plan gets a simple one-stop fallback. The source of each plan is recorded.
- `src/f1si/sim/borrow.py` stands in for data the fit does not have: an unfitted tyre borrows the average of the fitted tyres, a driver missing from the fit gets the field-average pace. Both are listed in the diagnostics.
- `src/f1si/sim/numpy_backend.py` is the simulator itself: it gives every car a plan, builds lap-time tables, starts from the real gaps (with a catch-up lap for cars a lap behind and retired cars placed last), runs the compiled lap step for every remaining lap and returns finishing positions and times, reproducible by seed.
- `src/f1si/plots/simulate.py` draws the finishing-position chart for one driver (one bar per position, a dashed mean line, a caption naming the source of the safety-car rate) and builds the safe file name `sim-<race>-<DRIVER>-lap<N>.png`.
- `src/f1si/cli.py` now has the `simulate` command with `--driver`, `--lap`, `--n` and `--seed`. Without `--lap` it is labelled a hindsight simulation.
- `src/f1si/state.py` now reads the safety-car regime at the cutoff (`regime` is `sc` only while a safety car is the latest status), adds `sc_laps_elapsed` and each car's pace-offset uncertainty, and holds a placeholder safety-car pit loss.
- `src/f1si/interfaces.py` extends `SimulationResult` with optional diagnostics (safety-car lap mask, stop laps, pit loss paid, plan sources, free-text notes).
- `src/f1si/pace/linear.py` now also reports the standard error of each driver's pace offset, so the simulator can draw it.
- `src/f1si/synthetic/generator.py` can send safety cars on chosen laps, giving tests a known true answer.

### Tests

- `tests/sim/` tests the draws, the kernel against its pure-Python twin, passing, plans, borrowed pace, reproducibility, common random numbers and safety-car behaviour. `tests/sim/test_benchmark.py` is the 50,000-race timing test and `tests/sim/test_variance_reduction.py` measures the noise reduction against plain Monte Carlo.
- `tests/regime/` tests the safety-car estimator, including recovery of a known 2.5% rate from synthetic races.
- `tests/conformance` holds the shared behaviour checks and the deliberately broken stubs, now including the simulator and its diagnostics.
- `tests/guards/consumers.py` registers every function that takes a snapshot or history, so the future-scramble guard covers the safety-car estimator.
- `tests/plots/test_simulate_plot.py` checks the chart.
- `tests/test_cli_simulate.py` runs the `simulate` command on a small synthetic cache, including refusals.
- `tests/real/test_simulate_bahrain.py` is the opt-in check on real Bahrain 2023 data (skipped unless you have the local cache and ask for it).
- `tests/test_docs.py` checks that this page and the README stay complete.

## Interview questions

### Q1. Why does pit timing need a simulation of the whole field, and what does a safety car do?

A pit stop costs about 24 s, but what that costs in finishing position depends on who is around you when you come out, and that depends on everyone else's stops. So one car cannot be priced alone: the simulator runs all 20 cars with their own plans, pit losses and passing chances. A safety car freezes the order and makes laps about 1.4 times slower, so a stop costs roughly half as much (the exact 0.5 is a placeholder until Phase 8). It also squeezes the gaps at the restart. A plan that looked wrong on a green track can become the best one.

### Q2. How is the safety-car rate estimated, and why does Bahrain 2023 get the prior alone?

The estimator counts safety-car starts in earlier races and divides by the laps, as a Beta-Binomial: a Beta(3, 297) prior (1% per lap, worth 300 laps) updated by the counts. With little history the prior stops a lucky or unlucky count from dominating. Only earlier races are allowed, because using the race being replayed would be look-ahead. Bahrain 2023 is the first race in the history, so there is nothing earlier, and the result is flagged "prior only". That gives a safety car in 43.7% of simulated 57-lap races, against the exact 1 - 0.99^57 = 43.6%, as it must.

### Q3. What are Sobol and antithetic sampling, and what did they gain?

Sobol points fill the space of random draws evenly instead of clumping, and antithetic pairing runs each draw together with its mirror image so the errors cancel. Over 120 repeats of 1,024 races (DEC-083), the variance of plain Monte Carlo divided by the variance of the new scheme was 3.8 for mean finishing position, 11.7 for mean total time and 2.5 for the safety-car share. The fourth estimate, the chance of finishing in the top 5, improved by 3.3 times as well. I expected little gain there, because a threshold indicator is jumpy, but the measurement says otherwise on the test race, so it is reported and not asserted. The gain depends on the state: if nobody can ever pass, the finishing position never varies and the ratio means nothing.

### Q4. Why Numba, and how do 50,000 races fit in 10 s?

The lap step is a tight loop over races, cars and laps, which plain Python would run too slowly. Numba compiles that one function to machine code, and the rest stays in NumPy. A full 50,000-race, 20-car, 57-lap run took 1.45, 1.38 and 1.49 s (DEC-084), so the 10 s budget has about 6 times headroom for slower CI machines. The first call compiles the function (about 1 s), so the benchmark excludes a warm-up call. The real Bahrain command printed 1.9 s for 50,000 races.

### Q5. How do reproducibility and common random numbers work?

All randomness comes from one explicit seeded generator, so the same seed gives the same table bit for bit. The generator is split into one stream per lap, and each car's draws are indexed by race, car and lap, never by its plan, the running order or the safety-car state. If you force a different plan on one driver, every other car gets exactly the same random numbers as before. Differences between the two runs are then caused by the plan and not by luck, which is called common random numbers and makes comparing strategies far less noisy.

## Good to know

- **Real Bahrain 2023 result (hindsight).** `uv run f1si simulate bahrain-2023 --driver ALO` gave P3 3.1%, P4 75.3%, P5 15.8%, P6 3.8%, mean 4.27, median 4.0, 90% interval 4 to 6, with a safety car in 43.7% of races and 1.6 s for 50,000 races. Alonso actually finished P3. The simulated 90% interval of P4 to P6 does not contain that, so the hindsight interval is narrow and overconfident for this driver. That is not yet a tested claim: Phase 6 checks whether intervals like this cover the real result as often as they claim. With `--lap 20` the same command gives P4 5.9%, P5 38.2%, P6 25.1%, P7 17.6%, P8 12.7%, mean 5.93 and 90% interval 4 to 8, in 0.9 s, with a safety car in 31.1% of races.
- **The hindsight label (D-17).** Without `--lap` the fit uses the whole race, so the output says "hindsight simulation". With `--lap 20` only data known after lap 20 is used.
- **Limits.** The safety-car pit loss of 0.5 times the green loss is a placeholder until Phase 8. The overtaking constants are documented defaults, fitted in Phase 6 (the pass curve uses a 0.4 s threshold and a 0.2 s scale, DEC-078). There are no retirements, lapping, virtual safety cars or red flags. Rivals follow the free-track best plan. Wear is not reduced under a safety car. The safety-car rate's own uncertainty is not sampled, and the parameter draws are independent, ignoring the fit's covariance.
- **Borrowed pace.** MEDIUM tyres have too little data to fit at Bahrain 2023, so a car on them borrows the average of SOFT and HARD. Piastri (PIA, number 81) retired on lap 13 and is not in the fit, so the plan optimizer refuses him, he gets a one-stop fallback plan with field-average pace, and from lap 20 he is placed last. All of this is printed as notes.
- **Where choices are logged.** DEC-074 to DEC-087 in `DECISIONS.md`: libraries (074), safety-car prior (075), regime and placeholder pit loss (076, 077), pass model (078), safety-car mechanics (079), draws (080), plans (081), starts and borrowing (082), variance ratios (083), benchmark (084), the command (085), clock and order (086), fixed draw slots (087).
- **Not here yet.** The Kalman filter, Longstaff-Schwartz stopping, a regime Markov model and a model of how the safety-car rate varies by circuit.
- **Run the checks** from PowerShell: `uv run pytest`. The real-data check is `uv run pytest -m network -v tests/real/test_simulate_bahrain.py`. CI on Ubuntu and Windows must be green before the phase counts as done.
