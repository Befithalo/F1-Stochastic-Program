# Phase 2 explained: interfaces, tyre wear and the free-track pit plan

This page is for you, the owner. It explains what Phase 2 builds, in plain words. It grows plan by plan; this first version covers the contracts: the three plug-in interfaces and the shared race state. Words in code font, such as `RaceState`, are names you will see in the files.

## What was built and why

**Plug-in slots (Protocols).** Later phases will bring a Monte Carlo simulator, a Kalman filter, a Longstaff-Schwartz stopping rule and a Bayesian model. To swap any of them in without breaking the rest, the project first defines three "slots" with exact shapes. A slot is called a Protocol in Python: a list of methods an object must have. The three slots are `PaceModel` (predicts a lap time and how uncertain it is), `StrategyPolicy` (decides whether to pit now and ranks whole pit plans) and `SimulatorBackend` (plays out many possible race endings).

**The shared race picture.** `RaceState` is a plain, frozen snapshot of the race at one lap: which lap it is, how many laps there are, and for every car its position, gaps, tyre, tyre age and fitted wear rate. It can be written to JSON text and read back exactly. When a value is unknown it is `None`, never "not a number", so nobody mistakes a guess for a fact. Two fields, the track regime and the pit-loss table, are placeholders for now (only "green"), until later phases estimate them.

**A test suite that polices every plug-in.** For each slot there is one shared check. It tests structure (are the right methods there?) and behaviour (right shapes, finite numbers, positive uncertainty, no changing of the inputs, same input gives the same answer, a pit decision never picks an illegal tyre). To prove the checks really bite, the project plants deliberately broken stubs, one defect each, and requires that every one is rejected. A separate test uses the type checker itself: a wrong stub passed where a slot is expected must be refused by mypy.

## How the pieces connect

```
interfaces.py  (PaceModel, StrategyPolicy, SimulatorBackend, Plan, PitDecision, SimulationResult)
      ^  names RaceState only for type checking, never at run time (no import cycle)
      |
state.py       (CarState, RaceState, JSON, arrays for number crunching)
      |
tests/conformance  (suites + registry of implementations + planted bad stubs)
```

## File-by-file tour

Paths are relative to the repository folder. `__init__.py` files are empty package markers and are left out.

### The package `src/f1si`

- `src/f1si/interfaces.py` is the three plug-in slots plus the small result types `Plan`, `PitDecision` and `SimulationResult`.
- `src/f1si/laps.py` is the shared clean-lap rule: lap 1, pit in/out and safety-car, virtual-safety-car and red-flag laps are not clean. The stint plot fades exactly these laps and the tyre-wear fit leaves them out.
- `src/f1si/pace/linear.py` fits one least-squares line per race: each driver's own base pace, one fuel effect shared by everyone and one wear rate per tyre compound. It reports an interval for each number, says plainly when a number cannot be told apart from another (for example before anyone has pitted), and measures the pit loss from green-flag stops.
- `src/f1si/plots/wear.py` draws the tyre-wear picture written by `f1si wear`: one panel per compound, each point a clean lap with fuel and driver pace taken out, the fitted line and the 95% band of its slope.
- `src/f1si/state.py` is `RaceState` and `CarState`: frozen plain data with exact JSON round trip and checks on every value, plus `build_race_state`, the one pure builder that turns a race snapshot and a fitted tyre-wear model into a state at any lap (unknown values stay empty, never invented).

### Tests

- `tests/conformance/suites.py` holds one check function per slot.
- `tests/conformance/registry.py` lists the implementations under test; adding one is a single line.
- `tests/conformance/stubs.py` holds the deliberately broken stubs.
- `tests/conformance/test_protocols.py` is the type-checker proof that wrong signatures are refused.
- `tests/test_state.py` and `tests/test_import_order.py` test the race state and the import rule.

## Interview questions

### Q1. What does a Protocol buy you, and what does it not?

A Protocol fixes the method names and signatures a plug-in must have, so the type checker can refuse a wrong one before anything runs. It does not check behaviour: at run time Python only checks that the method names exist. That is why the project adds a behaviour suite on top of the Protocols.

### Q2. Why does the conformance suite use planted bad stubs?

A test that has never failed proves little. By planting one defect at a time (wrong shape, NaN, zero uncertainty, changed input, random output, illegal tyre) and requiring the suite to reject each for the right reason, the project shows that the suite can actually catch those mistakes in a real implementation.

### Q3. Why are unknown values None and not NaN?

NaN spreads silently through arithmetic and is not valid JSON, so a missing gap could quietly turn into a wrong number downstream. None forces code to handle the unknown case, and the JSON writer refuses NaN outright. Only the number-crunching view converts None to NaN, on purpose, at the last moment.

## Good to know

- **This page is a work in progress.** Later plans of Phase 2 add the tyre-wear fit, the pit-plan optimizer, the plots and the commands, and extend this page.
- **Placeholders are named.** The track regime and the pit-loss table in `RaceState` hold only "green" until Phases 3 and 8.
- **Run the checks** from PowerShell, in the project folder: `uv run pytest tests/conformance`.
