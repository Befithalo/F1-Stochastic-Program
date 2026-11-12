# Phase 2 explained: interfaces, tyre wear and the free-track pit plan

This page is for you, the owner. It explains what Phase 2 built, in plain words, with real numbers from the 2023 Bahrain Grand Prix. Words in code font, such as `RaceState`, are names you will see in the files.

## What was built and why

**Plug-in slots (Protocols).** Later phases will bring a Monte Carlo simulator, a Kalman filter, a Longstaff-Schwartz stopping rule and a Bayesian model. To swap any of them in without breaking the rest, the project first defines three "slots" with exact shapes. A slot is called a Protocol in Python: a list of methods an object must have. The three slots are `PaceModel` (predicts a lap time and how uncertain it is), `StrategyPolicy` (decides whether to pit now and ranks whole pit plans) and `SimulatorBackend` (plays out many possible race endings).

**The shared race picture.** `RaceState` is a plain, frozen snapshot of the race at one lap: which lap it is, how many laps there are, and for every car its position, gaps, tyre, tyre age and fitted wear rate. It can be written to JSON text and read back exactly. When a value is unknown it is `None`, never "not a number", so nobody mistakes a guess for a fact. Two fields, the track regime and the pit-loss table, are placeholders (only "green"), until later phases estimate them.

**The clean-lap rule.** A lap only counts for the tyre fit if it is a normal racing lap. Lap 1, pit-in and pit-out laps, and laps under a safety car, virtual safety car or red flag are left out. At Bahrain 2023 this leaves 865 clean laps from 19 drivers.

**The fuel-and-wear fit.** One least-squares line per race. Each driver gets their own base pace, everyone shares one fuel effect, and each tyre compound gets its own wear rate. Every number comes with a 95% interval. Pit loss, the time a stop costs compared with staying out, is measured separately from green-flag stops: the median at Bahrain 2023 is 24.4 s over 42 stops.

**The free-track optimizer.** It tries every legal 1-stop and 2-stop plan for one driver, prices each with the fitted model plus the pit loss, and ranks them by total time. "Free-track" means an empty track: no traffic, no overtaking, no safety cars.

**Two commands.** `uv run f1si wear bahrain-2023` prints the fit and draws a picture. `uv run f1si plan bahrain-2023 --driver ALO` prints the ranked plans.

## How the pieces connect

```
race snapshot (as-of door, no future data)
      |
clean laps (laps.py)  -->  fit (pace/linear.py, a PaceModel)
      |                          |
      +---------->  RaceState (state.py)  <---- fit supplies wear rates
                          |
          optimizer (strategy/free_track.py, a StrategyPolicy)
                          |
                 printed table (cli.py: f1si wear, f1si plan)
```

The look-ahead guard sits on every function that takes a snapshot. A test scrambles all data after the cutoff and requires that the results do not change.

## File-by-file tour

Paths are relative to the repository folder. `__init__.py` files are empty package markers and are left out.

### The package `src/f1si`

- `src/f1si/cli.py` is the command line: besides `load`, `races` and `plot`, it now has `wear` (the fit table and picture) and `plan` (the ranked pit plans for one driver, with the hindsight label).
- `src/f1si/interfaces.py` is the three plug-in slots plus the small result types `Plan`, `PitDecision` and `SimulationResult`.
- `src/f1si/laps.py` is the shared clean-lap rule: lap 1, pit in/out and safety-car, virtual-safety-car and red-flag laps are not clean. The stint plot fades exactly these laps and the tyre-wear fit leaves them out.
- `src/f1si/pace/linear.py` fits one least-squares line per race: each driver's own base pace, one fuel effect shared by everyone and one wear rate per tyre compound. It reports an interval for each number, says plainly when a number cannot be told apart from another (for example before anyone has pitted), and measures the pit loss from green-flag stops.
- `src/f1si/plots/stints.py` is the Phase 1 stint plot, now using the shared clean-lap rule so it fades the same laps the fit leaves out.
- `src/f1si/plots/wear.py` draws the tyre-wear picture written by `f1si wear`: one panel per compound, each point a clean lap with fuel and driver pace taken out, the fitted line and the 95% band of its slope.
- `src/f1si/state.py` is `RaceState` and `CarState`: frozen plain data with exact JSON round trip and checks on every value, plus `build_race_state`, the one pure builder that turns a race snapshot and a fitted tyre-wear model into a state at any lap (unknown values stay empty, never invented).
- `src/f1si/strategy/free_track.py` is the pit-plan optimizer: it checks every legal 1-stop and 2-stop plan (two different dry tyres, stints of at least 5 laps), prices each with the fitted tyre model plus the measured pit loss, and ranks them. It assumes an empty track, so its answer is a lower bound on race time, not a forecast.

### Tests

- `tests/conformance/suites.py` holds one check function per slot.
- `tests/conformance/registry.py` lists the implementations under test; adding one is a single line.
- `tests/conformance/stubs.py` holds the deliberately broken stubs.
- `tests/conformance/test_protocols.py` is the type-checker proof that wrong signatures are refused.
- `tests/pace/` tests the clean-lap rule, the fit recovering known parameters from synthetic races, and the refusal cases (what the fit does when it cannot separate fuel from wear).
- `tests/strategy/test_free_track.py` checks the optimizer against a hand-computed answer and a slow reference pricer.
- `tests/test_state.py` and `tests/test_import_order.py` test the race state and the import rule.
- `tests/test_cli_wear_plan.py` runs the two new commands on a small synthetic cache.
- `tests/guards/consumers.py` registers every function that takes a snapshot so the future-scramble guard covers the new fit, builder and plots.
- `tests/real/test_wear_bahrain.py` is the opt-in check on real Bahrain 2023 data (skipped unless you have the local cache and ask for it).
- `tests/test_docs.py` checks that this page and the README stay complete.

## Interview questions

### Q1. Why can fuel burn and tyre wear be told apart?

The lap number goes up for everyone together, but tyre age resets to zero at a stop. A driver who has run two stints on different tyre ages at similar lap numbers lets the fit tell a "slower because the tyre is old" effect from a "faster because the car is lighter" effect. This needs at least one driver with two stints. When it cannot separate them, for example before anyone has pitted, the fit refuses and says so, instead of printing a made-up number.

### Q2. What does a Protocol buy you, and how is it proven?

A Protocol fixes the method names and signatures a plug-in must have, so mypy refuses a wrong one before anything runs. At run time Python only checks that the names exist, not the behaviour. So a shared behaviour suite runs against every implementation, and deliberately broken stubs (wrong shape, NaN, zero uncertainty, changed input) must each be rejected. That shows the suite can catch real mistakes.

### Q3. Why is the free-track plan a lower bound, and why does the output say "compared against"?

The optimizer assumes an empty track, so it ignores traffic, overtaking limits and safety cars. Real races are slower than that, so the plan time is a lower bound on what a driver could achieve, not a forecast. The plan is also built with hindsight from the whole race, so the output says the actual strategy is compared against the plan, priced with the same model. It never says the plan "beats" what the team did. For ALO the best 2-stop plan (stops on laps 17 and 37) is 1:34:03.1, and his real strategy, priced the same way, is 1:34:03.9, only 0.8 s apart.

### Q4. What does the fuel estimate of -0.078 s/lap mean, and why are compound offsets missing?

The literature suggests about -0.06 to -0.03 s/lap (the car gets faster as fuel burns off). The Bahrain 2023 fit gives -0.078 s/lap, outside that range. The likely reason is that it also absorbs track evolution (the track getting faster as rubber is laid down). The command reports the number as measured and says so, and does not clamp it. Compound pace offsets are not modelled yet: SOFT wears at 0.125 s/lap and HARD at 0.121 s/lap, nearly the same, and the HARD offset of +0.26 s has a standard error of 0.13 s, so it is weakly identified. Modelling it is a Phase 7 candidate, and until then the choice among near-tied compounds is not meaningful.

## Good to know

- **The hindsight label.** `f1si plan SLUG --driver CODE` without `--lap` prints "Hindsight plan": it uses the fit from the whole race and makes no claim of foresight (D-20). With `--lap 30` only data visible after lap 30 is used.
- **Race length is supplied by the command line.** The cache has no scheduled lap count, so the command reads it from the completed race (D-21).
- **Unknown stays None.** Gaps that cannot be known stay empty and never become 0 or NaN (D-23).
- **Thresholds.** At least 30 clean laps per compound, a 5-lap minimum stint, and 22.0 s as the default pit loss when no green-flag stop has been seen. Each is logged in `DECISIONS.md` (DEC-063 to DEC-069). Compounds with too little data print "not enough data" (MEDIUM at Bahrain 2023) and are never offered as candidates.
- **Real numbers at Bahrain 2023.** HARD +0.121 s/lap (interval +0.113 to +0.128, 496 laps), SOFT +0.125 s/lap (+0.118 to +0.133, 369 laps).
- **Not here yet.** Monte Carlo simulation, Kalman filtering, Longstaff-Schwartz stopping and a pit loss that depends on the track regime. The regime and pit-loss fields in `RaceState` hold only "green" placeholders until Phases 3 and 8.
- **Run the checks** from PowerShell, in the project folder: `uv run pytest`. The real-data check is `uv run pytest -m network -v tests/real/test_wear_bahrain.py`.
