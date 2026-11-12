# Phase 3: Monte Carlo Simulator - Context

**Gathered:** 2026-11-12
**Status:** Ready for planning

> **How these decisions were made.** The owner selected all four gray areas, then said: "For every question asked, just use what you recommend." Every decision below is therefore *Claude's pick*, the recommended option, with the reason stated. The owner can override any of them before planning. See `03-DISCUSSION-LOG.md`.

<domain>
## Phase Boundary

A vectorized NumPy `SimulatorBackend` that takes any `RaceState` (Phase 2) and simulates N continuations of the race to the flag. It covers pace from a `PaceModel`, pit stops with pit loss, overtaking chance from the pace gap, and a per-lap safety-car (SC) probability that compresses the field and makes pitting cheaper. It returns finishing positions and times for every car in every simulated race.

The phase delivers:
- the simulator;
- the MVP SC-rate estimate (REG-01);
- Sobol plus antithetic variance reduction with a test proving lower variance than plain Monte Carlo at equal N (SIM-03);
- a 50,000-race benchmark under 10 s (SIM-02);
- a `f1si simulate` command that shows one driver's finishing-position distribution for a Bahrain 2023 `RaceState`.

It does not:
- choose strategies under uncertainty (Phase 5, Longstaff-Schwartz);
- estimate a full regime model or regime-dependent pit loss from data (Phase 8);
- filter tire state (Phase 4);
- run a backtest (Phase 6).

Requirements: SIM-01, SIM-02, SIM-03, REG-01.

</domain>

<decisions>
## Implementation Decisions

### Safety-car model (REG-01)
- **D-01: SC rate from earlier races, else a prior** *(Claude's pick)*.
  - The per-lap SC deployment probability is a Beta-Binomial posterior: SC deployments over race laps, pooled from every earlier in-sample race returned by `AsOfAccessor.history(AsOf(race_id, ...))`. That call never returns the current race, later races or the locked 2026 races.
  - The prior is a documented weak literature prior: mean about 1% per lap, weight about 5 races (~300 laps).
  - Bahrain 2023 is round 1 of the cache and has no earlier races, so it gets the prior alone. The output says so.
  - The simulator uses the posterior mean. Parameter uncertainty in the rate is not sampled in the MVP.
  - The cache supports this: 81 of 87 races have track status, with 56 SC deployments over ~5,254 laps, about 1.1% per lap.
  - Circuit-specific rates wait for Phase 8.
- **D-02: SC only, not VSC or red flag** *(Claude's pick)*.
  - REG-01 asks for a safety-car probability. VSC (32 events in the cache) and red flags (11) belong to the Phase 8 Markov regime model (REG-02, REG-03).
  - The SC model is built so a VSC event type can be added later with the same mechanics and different parameters.
- **D-03: SC duration is a fixed whole number of laps** *(Claude's pick)*.
  - The duration is the median SC length in the same earlier races, measured from deployment to "in this lap". If fewer than 5 earlier SCs exist, it falls back to 4 laps (documented).
  - Duration is not sampled in the MVP. Occurrence is the random part.
  - Only one SC can be active at a time. A new SC can only start on a green lap.
- **D-04: what an SC does in a simulated race** *(Claude's pick)*.
  1. Running order is frozen: no overtaking on SC laps.
  2. SC lap times are the leader's green pace times a documented slowdown factor (about 1.4, the factor the synthetic generator already uses for VSC laps). Every car runs at the car ahead's pace or slower.
  3. On the restart lap, gaps are compressed to a fixed spacing of about 1 s per position (documented). This is the "field bunches up" effect that success criterion 3 requires.
  4. Pit loss under SC is a fixed documented fraction (about 0.5) of the green pit loss.
     - The builder fills `RaceState.pit_loss_s["sc"]`, and the docstring and DEC entry mark it as a placeholder.
     - Phase 8 (REG-03) replaces it with a value measured from data.
     - This fills D-13's placeholder early because success criterion 3 says SCs must visibly change pit loss.
  - Tire age still goes up on SC laps. The lower wear under SC is not modeled, and this is documented as a simplification.
- **D-05: current regime at the cutoff** *(Claude's pick)*.
  - `build_race_state` reads `track_status` as of lap N.
  - If an SC is active at the cutoff, `regime` becomes `{"sc": 1.0}`; otherwise it is `{"green": 1.0}`.
  - The simulator continues an active SC for the rest of the D-03 duration, counted from its deployment lap.
  - This keeps BUILD_PLAN's "lap 31, safety car" story possible without a regime model.
- **D-06: SC rate recovery test** *(Claude's pick)*. This is the project's rule that every model has a synthetic recovery test.
  - Extend the synthetic generator with an optional SC spec. It stays backward compatible: defaults leave existing fixtures byte-identical.
  - Test that the rate estimator recovers a known rate from synthetic history within its interval.
  - Test that the simulator's realised SC frequency over many races matches the input rate.

### Overtaking model (SIM-01)
- **D-07: lap-by-lap time model with dirty air and a pass chance** *(Claude's pick)*. TU Munich / Heilmeier style.
  - Each lap, every car's "free" lap time comes from pace, wear and fuel plus noise (D-11).
  - Cars are processed front to back in running order. If a car would cross the line less than `min_gap_s` (about 0.5 s, documented) behind the car ahead, it attempts a pass.
  - The pass succeeds with probability `p = logistic((Δ - threshold_s) / scale_s)`, where Δ is its pace advantage on that lap: the car ahead's free lap time minus its own.
  - A failed pass leaves it held at `min_gap_s` behind the car ahead (the dirty-air time loss).
  - A successful pass swaps them, and the passer pays a small documented time cost.
  - The passing randomness is one uniform per car per lap. That uniform belongs to the variance-reduced draw set (D-13), so it follows the seed.
- **D-08: overtaking parameters are documented defaults** *(Claude's pick)*.
  - `threshold_s`, `scale_s`, `min_gap_s` and the pass cost are named constants with literature or engineering justification in a DEC entry.
  - A sanity test shows that pass probability rises with the pace gap, a much faster car almost always passes, and equal pace rarely does.
  - Fitting them per circuit from real overtakes is deferred to Phase 6 calibration and the backtest.
- **D-09: no lapping interactions** *(Claude's pick)*.
  - Blue flags, unlapping under SC and lapped traffic are not modeled.
  - Every car runs to `laps_total`, as in DEC-073's free-track rule.
  - Finishing order is by total race time over the full distance.
  - Retirements (DNFs) are not simulated in Phase 3. This is documented as a limitation; see Deferred.

### Other cars and randomness
- **D-10: every car follows a fixed legal plan** *(Claude's pick)*.
  - A car named in `plans` uses that plan.
  - Every other car uses the free-track optimizer's best plan from the same state (Phase 2 `FreeTrackOptimizer`), computed once per call, not per simulated race.
  - If the optimizer refuses a car (unfitted compound, unidentified fit, too few laps left), the car gets a documented fallback: one stop, roughly at the middle of its remaining laps, onto a fitted compound it has not used. If that is impossible, no further stops.
  - Every fallback is listed in the result's diagnostics.
- **D-11: opportunistic stops under SC (other cars only)** *(Claude's pick)*.
  - When an SC starts, a car **not** in `plans` whose next planned stop is within the next 5 laps (documented constant) and is still legal takes that stop now, under SC pit loss.
  - Cars with a forced plan (`plans` argument) follow it exactly, so later policy evaluation (Phase 5) prices the plan it asked for.
- **D-12: two sources of uncertainty are sampled** *(Claude's pick)*.
  - **Per race, per car:** a parameter draw of the pace offset ~ N(offset, SE) and the wear rate ~ N(rate, wear_sd), using the Phase 2 standard errors. This is where the honest-uncertainty core value comes in.
  - **Per lap, per car:** independent lap-time noise ~ N(0, σ) with σ from `PaceModel.predict`'s SD.
  - Car-level draws come from the variance-reduced set (D-13).
  - The simulator is constructed with a `PaceModel` for mean and SD. `RaceState` supplies the per-car state and the SEs.
  - Where a needed SE is missing from `CarState`, the planner adds it or takes it from the fit object. Claude's discretion; must stay JSON round-trip safe.
- **D-13: variance reduction** *(Claude's pick)*.
  - Use scrambled Sobol points from `scipy.stats.qmc.Sobol`, with the scramble seeded from the caller's `np.random.Generator`, for the low-dimensional inputs that drive most of the variance:
    - SC occurrence per lap;
    - per-car parameter draws;
    - pass uniforms where the dimension budget allows.
  - Map them through inverse CDFs. Pair every draw with its antithetic `1 - u`.
  - High-dimensional per-lap noise uses plain pseudo-random antithetic normals from the same Generator.
  - n_races must be even, or the simulator pads and trims internally. Document whichever is chosen.
- **D-14: the variance-reduction test (SIM-03)** *(Claude's pick)*.
  - Over R independent seeds (e.g. 40) at equal N, compare the variance of the estimator "chosen driver's mean finishing position", and of P(top 5), for plain MC against Sobol plus antithetic.
  - The test asserts a lower variance ratio with a margin. It is deterministic by seed.
  - The ratio is reported in DECISIONS.md and the explainer.
- **D-15: reproducibility** *(Claude's pick)*.
  - The same seed gives bit-identical `SimulationResult` arrays.
  - The rng is the only source of randomness. No global state, and Sobol scrambling comes from the rng.
  - Different seeds give different results.

### What you see
- **D-16: CLI** *(Claude's pick)*: `uv run f1si simulate bahrain-2023 --driver ALO [--lap N] [--n 50000] [--seed 0]`. It prints:
  - the state it simulated from;
  - the SC rate used and its source ("prior only: no earlier races" for Bahrain 2023);
  - each car's plan source (optimizer or fallback);
  - the chosen driver's finishing-position distribution: P1..P20 probabilities, mean, median, 90% interval;
  - the share of simulated races with an SC;
  - runtime.

  It also writes a bar-chart PNG to `reports/sim-<slug>-<DRV>-lap<N>.png`, using the `plots/wear.py` pattern (Figure API, no pyplot).
- **D-17: the hindsight rule carries over from Phase 2** (D-20).
  - Without `--lap`, it simulates from lap 0 with a pace fit from the whole race and labels the run "hindsight simulation".
  - With `--lap N`, it uses only data known at lap N and refuses with the Phase 2 message when the fit is not identified.
- **D-18: benchmark (SIM-02)** *(Claude's pick)*.
  - A pytest benchmark simulates 50,000 races of a full 57-lap, 20-car state in under 10 s on CI (Ubuntu and Windows).
  - Any JIT warm-up is excluded and stated.
  - NumPy first. Numba is allowed for the per-lap front-to-back passing loop if NumPy alone misses the budget. Log it in a DEC entry.
  - The CLI prints the runtime.
- **D-19: provisional `SimulationResult` is extended as needed** *(Claude's pick)*.
  - Keep `finish_positions` and `total_time_s` as `(n_races, n_cars)` in `RaceState.cars` order.
  - Add per-race diagnostics needed by the tests and CLI: SC laps per race, actual stop laps per car and pit loss paid.
  - Keep the conformance suite and the `NoisySimulator` test double in sync.
- **D-20: explainer and docs** *(Claude's pick)*.
  - Write `docs/explained/phase-03.md` in the Phase 1/2 format, with real Bahrain 2023 numbers.
  - Add README needles for `f1si simulate`.
  - Add DEC entries for every method choice (next free: DEC-074).

### Claude's Discretion
- Module layout, e.g. `f1si/sim/numpy_backend.py`, `f1si/regime/sc_rate.py`.
- Exact constant values within the documented ranges above.
- Array layout and vectorization.
- How SEs reach the simulator (D-12).
- Odd-N handling (D-13).
- Exact Sobol dimension budget.
- Whether to use Numba (D-18).
- Lap-0 start spacing: grid order with a small fixed spacing, no first-lap chaos model.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and requirements
- `.planning/ROADMAP.md` § Phase 3: goal and the five success criteria.
- `.planning/REQUIREMENTS.md`: SIM-01, SIM-02, SIM-03, REG-01 (and REG-02/REG-03 for what is deferred to Phase 8).
- `.planning/PROJECT.md`: core value (honest, calibrated uncertainty; no look-ahead); constraints (explicit `np.random.Generator`, synthetic recovery test per model, DECISIONS.md, CI gate, 10 s performance budget).
- `CLAUDE.md`: project constraints.

### Design
- `F1 Docs/BUILD_PLAN.md`: Architecture (`SimulatorBackend` runs N races from a state); the lap-31 safety-car walkthrough; week-3 MVP simulator description; evaluation table (90% finishing-interval coverage target, 10 s runtime); risk note that simulations never reproduce one race exactly; references to TU Munich race-simulation and Heilmeier et al. 2020 (method reference only; LGPL code is not copied).
- `F1 Docs/MASTER_PROMPT.md`: build brief.

### Prior phase decisions
- `.planning/phases/02-interfaces-linear-tire-wear-free-track-optimizer/02-CONTEXT.md`, which covers:
  - D-09 PaceModel mean + SD;
  - D-10 SimulatorBackend contract;
  - D-12 / D-13 RaceState and placeholders;
  - D-14 single builder;
  - D-20 hindsight vs `--lap N`;
  - D-21 `laps_total`.
- `.planning/phases/02-interfaces-linear-tire-wear-free-track-optimizer/02-REVIEW-FIX.md`: WR-01 (`CarState.laps_done`, each car priced from its own next lap); WR-02 / WR-04 (SE and sigma corrections the simulator now samples from).
- `DECISIONS.md`: DEC-061..073, especially:
  - DEC-061: Protocol conformance and runtime_checkable scope;
  - DEC-068 / DEC-069: optimizer;
  - DEC-073: every car runs to `laps_total`.
- `.planning/phases/01-foundation-data/01-CONTEXT.md`: the as-of accessor rules; who may name `AsOfAccessor` / `RACE_END`.

### Code (contracts to implement against)
- `src/f1si/interfaces.py`: `SimulatorBackend.simulate(state, *, n_races, rng, plans)`, provisional `SimulationResult`, `Plan`, `PaceModel`.
- `src/f1si/state.py`: `RaceState`, `CarState` (incl. `laps_done`), `build_race_state`, regime and pit_loss placeholders.
- `src/f1si/data/asof.py`: `AsOfAccessor.history(at)` gives earlier in-sample races only (the SC-rate source); cutoff semantics ("lap N" = leader completed lap N).
- `src/f1si/strategy/free_track.py`: `FreeTrackOptimizer` (plans for other cars, D-10).
- `src/f1si/pace/linear.py`: `LinearPaceFit` (`predict`, SEs, `sigma_s`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conformance/registry.py` + `suites.py`: add the NumPy simulator to `SIMULATORS`; the suite already checks shape, permutation rows, determinism by seed and non-mutation. Planted stubs and `NoisySimulator` exist.
- `src/f1si/synthetic/generator.py`: synthetic races with known truth; already emits VSC track-status events (`vsc_laps`, `vsc_slowdown_factor` 1.4). Extend with an SC spec for D-06, keeping defaults byte-identical.
- `tests/conftest.py`: `build_long_db`, `LONG_SLUG`, `LONG_RACE_ID`, `long_synthetic_*` fixtures (57 laps, 20 drivers).
- `src/f1si/plots/wear.py`: the PNG pattern (Figure API, no pyplot; `*_file_name(slug)` slug-safety; prepare-data / build-figure / render split) to copy for the finishing-distribution chart.
- `src/f1si/cli.py`: `_cmd_wear` / `_cmd_plan` are the analogs for `_cmd_simulate`; `_FRIENDLY_VALUE_ERRORS`; hindsight labelling and `--lap` refusal text.
- `src/f1si/pace/linear.py`: `measure_pit_loss` (green-flag pit loss median); SC/VSC predicate from Phase 2 D-22 for identifying SC laps.

### Established Patterns
- **No look-ahead:** model and simulator code receive `RaceState` / `RaceSnapshot` / `History`, never the accessor.
  - New snapshot or history consumers register in `tests/guards/consumers.py` (CONSUMERS, DESIGNATED_MODULES, CONSUMED/EXEMPT per public function).
  - The future-scramble test must stay green.
- **Docs test:** every new `src/f1si` module must appear in a `docs/explained/phase-*.md` tour in the same task that creates it.
- **DECISIONS.md:**
  - heading format `## DEC-NNN — Title` (em dash), 8 labels;
  - bump `MIN_ENTRIES` in `tests/test_decisions_log.py`;
  - next free is DEC-074 and MIN_ENTRIES is 73.
- **Gate:** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (locally `uv run python -m mypy`), `uv run pytest`, plus opt-in `-m network` real-data tests. CI runs on Ubuntu and Windows.
- **Locally on the owner's PC**, `uv run f1si` / `uv run mypy` are blocked by Windows Application Control. Use `uv run python -m f1si` / `uv run python -m mypy`. Docs still show `uv run f1si`.

### Integration Points
- `build_race_state` gains regime detection (D-05) and the `pit_loss_s["sc"]` placeholder (D-04).
- `SimulationResult` extension (D-19) touches `interfaces.py`, the conformance suite and `NoisySimulator`.
- Phase 5 (Longstaff-Schwartz) will call `simulate(..., plans={driver: plan})` per candidate plan, so a forced plan must be followed exactly (D-11) and results must be comparable across calls with the same seed (common random numbers).

</code_context>

<specifics>
## Specific Ideas

- Success-criterion demo: a Bahrain 2023 `RaceState` → ALO's finishing-position distribution.
- Success criterion 3 needs a test showing that, in simulated races with an SC:
  - gaps compress after the restart;
  - a stop taken under SC costs about the SC pit loss, not the green one.
- Bahrain 2023 is round 1, so its SC rate is prior-only. The CLI must say so plainly rather than imply the rate was measured.
- Keep common random numbers in mind: the same seed and the same state with a different forced plan for one driver should reuse the same random draws, so Phase 5's plan comparisons have low variance. Design the draw layout so a forced plan does not shift other draws.

</specifics>

<deferred>
## Deferred Ideas

- VSC and red-flag events, circuit-specific SC rates, a regime transition matrix: Phase 8 (REG-02).
- Pit loss under SC/VSC measured from data: Phase 8 (REG-03). Phase 3 uses a documented placeholder ratio.
- Retirements/DNFs, first-lap incidents, blue flags and lapping: later calibration work (Phase 6 backtest finds whether they matter for interval coverage).
- Fitting overtaking parameters per circuit from real passes: Phase 6 calibration.
- Sampling uncertainty in the SC rate and SC duration: Phase 8.
- Lower tire wear and fuel burn under SC: Phase 7 / M2 physics.
- JAX / Rust simulator backends: M5.

</deferred>

---

*Phase: 03-monte-carlo-simulator*
*Context gathered: 2026-11-12*
