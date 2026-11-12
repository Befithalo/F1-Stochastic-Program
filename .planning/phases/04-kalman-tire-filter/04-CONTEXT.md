# Phase 4: Kalman Tire Filter - Context

**Gathered:** 2026-11-12
**Status:** Ready for planning

> **How these decisions were made.** The owner asked for discuss, plan and execute in one go and said: "Choose whatever you recommend." Every decision below is therefore *Claude's pick*, the recommended option, with the reason stated. The owner can override any of them. See `04-DISCUSSION-LOG.md`.

<domain>
## Phase Boundary

A Kalman filter that estimates each car's hidden tire-wear rate, lap by lap, from noisy lap times, with an uncertainty band. It uses only data known at each lap.

The phase delivers:
- the filter;
- a synthetic recovery test proving the PAC-04 targets:
  - within 10% of the true wear rate by stint lap 8;
  - 95% intervals that cover the truth about 95% of the time;
- a command that shows the estimate and its band narrowing over a real Bahrain 2023 stint;
- the wiring that puts the filter's wear mean and SD into the `RaceState` fields that the simulator reads (success criterion 4).

It does not:
- choose pit strategy (Phase 5);
- step through a full live replay (RPL-01 / RPL-02, Phase 5);
- fit a hierarchical Bayesian pace model (Phase 7);
- model a tyre cliff (deferred).

Requirements: PAC-03, PAC-04.

</domain>

<decisions>
## Implementation Decisions

### What the filter estimates
- **D-01: state model** *(Claude's pick)*.
  - **State.** There is one filter per car per stint. Its two-element state is [pace level at the current tyre age, wear rate in s/lap]. This is a local linear trend.
  - **Observation.** Each observation is one fuel-corrected clean lap time: `y = level + noise`.
  - **Transition.** From one lap of tyre age to the next: `level += rate` and `rate` is unchanged.
  - **Reported value.** The filter reports the wear rate, which is what `CarState.wear_rate_s_per_lap` holds. The cumulative wear (rate × age) can be derived for the plot.
  - **Why the level is in the state.** The car's baseline pace is unknown. Keeping it in the state means the filter does not depend on the Phase 2 driver offset, which is unidentified early in a race.
- **D-02: no process noise by default** *(Claude's pick)*.
  - **Default.** The rate is constant within a stint, matching the Phase 2 linear model, the simulator's linear wear and the synthetic truth. With zero process noise the filter is exact recursive Bayesian linear regression, so its intervals are correctly specified on synthetic data.
  - **Option.** The code accepts a process-noise SD (`q`) for later use.
  - **Required test.** `q > 0` must widen the band.
  - Log this choice and its limitation (no cliff, no thermal effects) in a DEC entry.
- **D-03: reset at every stop** *(Claude's pick)*.
  - **Wear rate.** On a new stint the rate starts again from the compound prior (D-05).
  - **Level.** The level starts diffuse, because new tyres change the pace.
  - **Tyre age.** It comes from the stint data, so a used set starts at its real age.
- **D-04: own implementation, no new dependency** *(Claude's pick)*.
  - About 30 lines of NumPy, with the Joseph-form covariance update for numerical stability.
  - No filterpy: it is unmaintained, untyped, and the BUILD_PLAN allows "your own 30 lines".
  - The docstring states the equations: predict, update, gain, Joseph form.

### Inputs and priors (as-of only)
- **D-05: wear-rate prior** *(Claude's pick)*.
  - **When the Phase 2 fit is identified.** The prior mean and SD are that compound's field-level wear rate, taken from the fit as of the lap.
  - **When it is not.** Use a documented generic prior per compound (SOFT, MEDIUM, HARD), set wide on purpose. This covers the first stint of every race, because no driver has two visible stints yet.
  - **Labelling.** The output says "prior only", as the safety-car rate does in Phase 3.
  - Research proposes the prior values with sources. Log them in a DEC entry.
- **D-06: fuel correction** *(Claude's pick)*.
  - **Source.** Subtract the fuel effect from the as-of Phase 2 fit when it is identified, otherwise from a documented fuel prior with an SD.
  - **Why the fuel uncertainty must reach the band.** Within one stint, fuel and wear move along the same straight line, so the data cannot separate them (Phase 2 docstring). The reported wear SD must therefore include the fuel uncertainty.
  - **Labelling.** Say plainly when fuel is prior-only.
- **D-07: observation noise** *(Claude's pick)*.
  - **Source.** Use the as-of Phase 2 `sigma_s` when it is identified, otherwise a documented default. Research may propose a pooled residual estimate across the field instead, provided it is as-of.
  - **Hard rule.** Never use a value computed from laps after the cutoff.
- **D-08: which laps update the filter** *(Claude's pick)*.
  - **Clean laps only,** by the Phase 2 rule `f1si.laps.fade_reason`. Excluded laps are lap 1, pit in-laps, pit out-laps and SC/VSC/red-flag laps.
  - **Skipped laps** run the predict step only (tyre age still advances), so the band does not shrink on them.
  - **Outlier gate.** A lap whose innovation exceeds a documented gate (about 3 SD) is also skipped and counted in the diagnostics. This guards against traffic laps the clean-lap rule misses. Research decides when the gate switches on, since the level is diffuse at the start of a stint.
- **D-09: no look-ahead** *(Claude's pick)*.
  - The filter receives a `RaceSnapshot` (or plain arrays from it), never the accessor.
  - Every new public function that reads a snapshot is registered in `tests/guards/consumers.py`, and the future-scramble test stays green.

### How PAC-04 is tested
- **D-10: synthetic truth per car** *(Claude's pick)*.
  - **Generator change.** `SyntheticRaceSpec` gains optional per-driver wear-rate deviations, exposed in `SyntheticTruth`, plus support for stints long enough to reach stint lap 8 and beyond.
  - **Default.** The default is no deviation, so every existing fixture stays byte-identical (the Phase 3 approach to adding SC to the generator).
- **D-11: the recovery test** *(Claude's pick)*.
  - **Setup.** Run many seeded synthetic stints, at least 1,000. Draw the true per-car rates from the same distribution the filter's prior states, and pass fuel and noise in as known. This isolates the filter, and the model is correctly specified.
  - **"By lap 8"** means 8 laps on the tyres. With the out-lap skipped, that is 7 measured laps.
  - **Accuracy.** The mean absolute relative error of the wear-rate estimate at stint lap 8 must be at most 10%.
  - **Coverage.** The share of 95% intervals that contain the truth, at each stint lap and pooled, must be within a binomial 99.9% band around 0.95.
  - **Narrowing (criterion 1).** The posterior SD must not increase on a measured lap.
  - **End-to-end variant.** Fuel comes from its prior. Coverage must still hold, because the fuel SD is in the band. The error is reported, not gated.
- **D-12: feasibility before tests** *(Claude's pick)*.
  - **What research does first.** It computes the expected stint-lap-8 error analytically from the Kalman posterior, at the generator's default noise (0.15 s) and at the noise measured for Bahrain 2023.
  - **Keep the test meaningful.** The prior spread must be wide enough that the prior alone (stint lap 0) misses the 10% target, so the data has to do the work.
  - **If the target is not attainable honestly,** research says so. The planner then raises it with the owner as a requirement risk, with the achievable number. Noise, prior and metric are not tuned to make the test pass. (Phase 3 lesson: a tolerance was loosened with a wrong argument and had to be restored.)

### Simulator integration (criterion 4)
- **D-13: builder** *(Claude's pick)*.
  - **New input.** `build_race_state` gains an optional filter result.
  - **With it.** Each car's `wear_rate_s_per_lap` and `wear_sd` are the filter's posterior for the car's current stint at the cutoff, with the fuel SD included.
  - **Without it.** The values come from the Phase 2 fit, as now.
  - **Provenance.** A new optional `CarState.wear_source` field (`"fit"` | `"filter"`, default `"fit"`) records where they came from. This is an addition only: the JSON stays backward compatible and no field is renamed.
- **D-14: simulator** *(Claude's pick)*.
  - **For a `"filter"` car.** For the laps on its current tyres, the simulator replaces the compound wear slope with the car's own rate and uses the car's own SD, as a per-car draw.
  - **Later stints** (new tyres) keep the compound fit, as now.
  - **For a `"fit"` car** the behavior is byte-identical to Phase 3.
  - **Draws.** The per-car wear draws come from a new spawned stream that does not touch the existing Sobol layout. All Phase 3 tests, including the variance ratios and common random numbers, stay green unchanged.
  - **New tests:**
    - a car with a higher filtered rate finishes worse on average;
    - a larger filtered SD widens that car's total-time spread;
    - the CRN property still holds.

### What you see
- **D-15: CLI** *(Claude's pick)*.
  - **Command.** `uv run f1si wear-filter bahrain-2023 --driver ALO [--lap N]`. The existing `f1si wear` command stays the Phase 2 hindsight wear plot.
  - **What it does.** It replays the race as-of every lap up to N (default: the end) and prints, per stint:
    - the compound;
    - the sources of the prior, fuel and noise ("prior only" where applicable);
    - per lap: race lap, tyre age, whether the lap was used or skipped (with the reason), the wear-rate estimate and its 95% interval.
  - **Chart.** It writes a PNG, `reports/wear-filter-<slug>-<DRV>.png`, with:
    - the estimate line and shaded 95% band against race lap;
    - stint boundaries;
    - the Phase 2 full-race compound estimate as a dashed reference, labelled "hindsight".
  - **Pattern.** Copy `plots/wear.py`: Figure API, no pyplot, a slug-safe file name, and a split into prepare-data, build-figure and render.
- **D-16: docs** *(Claude's pick)*.
  - Write `docs/explained/phase-04.md` in the Phase 1–3 format, with real Bahrain 2023 numbers.
  - Add README needles for `f1si wear-filter`.
  - Add DEC entries from DEC-088 for every method choice, and bump `MIN_ENTRIES` (87 now).
  - Every new module goes into the explainer tour in the same task that creates it.

### Claude's Discretion
- Module layout, for example `f1si/pace/kalman.py` with the CLI in `cli.py` and the plot in `plots/wear_filter.py`.
- Exact generic prior values and the gate threshold, within D-05 and D-08, logged in DEC entries.
- Whether all cars are filtered in one vectorized pass or one at a time.
- Plot styling.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and requirements
- `.planning/ROADMAP.md` § Phase 4: goal and the four success criteria.
- `.planning/REQUIREMENTS.md`: PAC-03, PAC-04. Also PAC-05 / PAC-06, for what Phase 7 will replace.
- `.planning/PROJECT.md`: core value (honest, calibrated uncertainty; no look-ahead) and constraints (synthetic recovery test per model, docstrings state the math, DECISIONS.md, CI gate).
- `CLAUDE.md`: project constraints.

### Design
- `F1 Docs/BUILD_PLAN.md`:
  - methods table: "Kalman filter: hidden tire wear estimated from noisy lap times";
  - walkthrough laps 1–14: "uncertainty is wide at first and narrows each lap";
  - "Hidden variables" paragraph: tire state is latent, say so in the README;
  - evaluation table row: "within 10% of truth by lap 8; 95% intervals cover truth about 95% of the time";
  - filterpy or "your own 30 lines".
- `F1 Docs/MASTER_PROMPT.md`: build brief.

### Prior phase decisions
- `.planning/phases/02-interfaces-linear-tire-wear-free-track-optimizer/02-CONTEXT.md`, which covers:
  - the clean-lap rule (D-02 / D-22);
  - fuel and wear identification;
  - D-12 / D-13 RaceState fields and placeholders;
  - D-14 the single builder;
  - D-20 hindsight vs `--lap N`.
- `.planning/phases/03-monte-carlo-simulator/03-CONTEXT.md`:
  - D-12 how SEs reach the simulator;
  - D-13 / D-15 the draw layout and reproducibility;
  - the "prior only" labelling precedent.
- `DECISIONS.md`:
  - DEC-070..073: the Phase 2 fit and pit-loss rules;
  - DEC-077: the parameter-draw form;
  - DEC-086 / DEC-087: clock/order invariant and fixed draw slots, which must not move.
- `.planning/phases/03-monte-carlo-simulator/03-VERIFICATION.md`: the open flag that the ALO 90% interval excluded the real P3. Per-car wear uncertainty is one of the inputs to that interval width.

### Code (contracts to implement against)
- `src/f1si/pace/linear.py`: `fit_linear_pace`, `LinearPaceFit` (`wear_rate`, `wear_se`, `fuel_effect`, `report.sigma_s`, `is_identified`), and the module docstring on why fuel and wear separate only across stints.
- `src/f1si/laps.py`: `fade_reason`, `slow_status` (the clean-lap rule).
- `src/f1si/state.py`: `CarState`, `RaceState`, `build_race_state`, JSON round trip.
- `src/f1si/sim/numpy_backend.py`, `src/f1si/sim/kernel.py`, `src/f1si/sim/draws.py`, `src/f1si/sim/constants.py`: the current wear term `z_wear[k] * wear_sd[k] * (a + 1)`, the draw streams and `DRAW_COMPOUNDS`.
- `src/f1si/synthetic/generator.py`: `SyntheticRaceSpec`, `SyntheticTruth` (lap-time model with `wear[c] * a`).
- `src/f1si/data/asof.py`: `RaceSnapshot`, cutoff semantics.
- `tests/guards/consumers.py`: consumer registry for the future-scramble test.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `f1si.laps.fade_reason`: the clean-lap rule shared by the stint plot and the Phase 2 fit. Reuse it as is.
- `LinearPaceFit`: as-of fuel effect, compound wear rates with SEs, and `sigma_s` (trim-corrected). These are the identified-case inputs for D-05..D-07.
- `src/f1si/plots/wear.py`: the PNG pattern to copy for the filter chart.
- `src/f1si/cli.py` `_cmd_wear` / `_cmd_simulate`: analogs for `_cmd_wear_filter`, with `_FRIENDLY_VALUE_ERRORS` and the hindsight and prior-only labelling.
- `tests/conftest.py`: the long synthetic fixtures (57 laps, 20 drivers).
- The synthetic generator: extend it as Phase 3 did for SC, with defaulted fields and existing fixtures byte-identical.

### Established Patterns
- **No look-ahead.** Models receive a `RaceSnapshot` or `RaceState`, never the accessor. Register new consumers.
- **Synthetic recovery test** for every model (CLAUDE.md).
- **Docs test.** Every new `src/f1si` module appears in a `docs/explained/phase-*.md` tour.
- **DECISIONS.md.** Headings use `## DEC-NNN — Title`. The next free number is DEC-088 and `MIN_ENTRIES` is 87.
- **Gate.** Run ruff check, ruff format --check, mypy strict and pytest. CI runs on Ubuntu and Windows.
- **Running locally.** Use `uv run python -m f1si` and `uv run python -m mypy`, because Windows Application Control blocks the uv shims. Docs still show `uv run f1si`.

### Integration Points
- `build_race_state` gains the optional filter result (D-13).
- `CarState` / JSON gain `wear_source` (D-13). Keep `from_json` accepting old JSON without it.
- `NumpySimulator` gains the per-car current-stint wear path and a new draw stream (D-14). Phase 3 conformance, CRN and variance tests must stay green unchanged.
- Phase 5 will call the filter every lap of a replay, so the update must be incremental (one lap at a time) as well as available as a batch over a stint.

</code_context>

<specifics>
## Specific Ideas

- Success-criterion demo: ALO's stints at Bahrain 2023, with the band visibly narrowing over the first laps of each stint.
- Bahrain 2023 is round 1, and no driver has two visible stints before the first stops. The first stint's prior and fuel therefore come from the documented priors, and the output must say so, as the SC rate does.
- The Phase 3 open flag: the ALO 90% finishing interval (P4–P6) excluded the real P3. When the filter feeds the simulator, report whether ALO's interval at a mid-race lap widens. This is an observation, not a gate.

</specifics>

<deferred>
## Deferred Ideas

- Tyre cliff and non-linear wear (process noise or a regime switch on the rate). Phase 5's "cliff risk" reason will need something here; for now the code supports `q > 0`.
- Pooling wear across cars (hierarchical): Phase 7, Bayesian pace model.
- Wear priors learned from earlier races via `AsOfAccessor.history`: Phase 7 or Phase 6 calibration.
- Adaptive noise estimation and traffic or dirty-air models for lap times: later calibration.
- Tyre temperature and physics-based wear: M2.
- Full lap-by-lap live replay with recommendations: Phase 5 (RPL-01 / RPL-02).

</deferred>

---

*Phase: 04-kalman-tire-filter*
*Context gathered: 2026-11-12*
