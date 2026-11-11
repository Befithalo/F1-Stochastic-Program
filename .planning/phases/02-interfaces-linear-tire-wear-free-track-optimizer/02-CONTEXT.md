# Phase 2: Interfaces, Linear Tire Wear & Free-Track Optimizer - Context

**Gathered:** 2026-11-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers four things:

- `f1si/interfaces.py` with typed Protocols `PaceModel`, `StrategyPolicy` and `SimulatorBackend`, accepted by mypy strict, plus a shared test suite that every implementation must pass and that fails a non-conforming stub.
- A shared `RaceState` object (BUILD_PLAN §Architecture schema), built from a `RaceSnapshot` at any lap of any cached race. It is the single object type later modules consume.
- A fuel-corrected linear tire-wear fit per compound, shown for Bahrain 2023.
- A free-track brute-force optimizer that checks every legal 1- and 2-stop plan and reports the fastest with total race time.

It also delivers a plain-language explainer, `docs/explained/phase-02.md` (UI-03, Phase 1 D-17 format).

Requirements: INT-01, INT-02, INT-03, PAC-01, PAC-02 (+ UI-03 recurring).

Not in this phase:
- Monte Carlo simulation, overtaking, safety-car probability (Phase 3).
- Kalman filtering of per-car wear (Phase 4).
- Longstaff-Schwartz, CVaR, the replay loop (Phase 5).
- Pooling across races or Bayesian priors (Phase 7).
- Regime-dependent pit loss (Phase 8).

</domain>

<decisions>
## Implementation Decisions

The user chose the first eight decisions (D-01–D-08) and the PaceModel output (D-09). Partway through the interface-contracts area, the user said: "for the rest of the questions you ask me just pick whats recommended by u." Decisions marked *(Claude's pick)* are the recommended options under that instruction. They are binding for planning unless the user revises them.

### Fuel & wear fitting
- **D-01: Fuel effect is fitted jointly, not assumed.** One regression over clean laps:
  `t(d, L) = alpha_d + fuel * (L - 1) + wear[c] * age + eps`.
  - `alpha_d` is a per-driver intercept.
  - `L` is the lap number and `age` is the tire age at the end of the lap.
  - Fuel and wear are separated because tire age resets at a pit stop while lap number keeps rising. The docstring must state this.
  - Report the fitted fuel value beside a literature sanity range (about −0.03 to −0.06 s/lap; negative means the car gets faster).
  - Do not fall back to a fixed constant. If fuel cannot be identified (for example, no driver has two stints visible), report that plainly instead of guessing.
  - The model form matches `f1si.synthetic.generator` exactly, so the synthetic-recovery test must recover both `fuel_effect_s_per_lap` and `wear_rate_s_per_lap` from `SyntheticTruth`.
- **D-02: Clean laps follow one shared definition.**
  - Drop exactly the laps the stint plot fades: lap 1, pit in/out laps, SC/VSC/red/yellow laps (the current `_fade_reason` in `src/f1si/plots/stints.py`).
  - Then drop outliers (traffic, mistakes) with a robust rule. Suggested: more than 3 robust SDs (MAD-based) from the driver's stint trend. Exact threshold at Claude's discretion; log it in DECISIONS.md.
  - Move the fade rule into a shared module so the plot and the fit cannot drift apart.
  - The fit reports how many laps it dropped and why.
- **D-03: Fit scope is one race, at any cutoff.**
  - The fit takes a `RaceSnapshot`. At `RACE_END` it gives the headline Bahrain 2023 numbers. At lap N it uses only laps visible at N, which honors the as-of rule.
  - Earlier races are not used; cross-race pooling is Phase 7.
  - A compound with too few clean laps reports "not enough data" (no estimate) instead of a guess. The minimum is at Claude's discretion; log it.
- **D-04: Per-driver pace offset, shared wear slope per compound, with standard errors.**
  - Each driver has their own intercept. The wear slope per compound is shared across the field.
  - Each compound's wear rate is reported with a standard error and 95% interval. That SE fills `RaceState.cars[].wear_sd`.
  - Per-driver wear slopes are out of scope; Phase 4's Kalman filter does that.

### Optimizer rules
- **D-05: Pit loss is measured from in/out laps.**
  - `pit_loss = (in-lap + out-lap) − two predicted clean laps from the fitted model`.
  - Take the median across stops visible at the cutoff and report the spread.
  - With no stops visible yet (for example, lap 5), fall back to a documented default and flag it in the output. The default's value is at Claude's discretion; log it in DECISIONS.md.
  - Green-flag stops only. Stops under SC/VSC are excluded from the median, because regime-dependent pit loss is Phase 8.
- **D-06: Real F1 rules.**
  - At least two different dry compounds must be used (counting compounds already used).
  - The starting tire is fixed to what the driver actually started on, including its starting age (for example, used softs from qualifying).
  - There is a minimum stint length. 5 laps is suggested; exact value at Claude's discretion, logged.
  - Only compounds with a fitted wear rate (D-03) are candidates.
  - A race with intermediate or wet stints for the chosen driver is flagged and refused with a clear message; wet strategy is out of scope.
- **D-07: The optimizer plans from any lap's `RaceState`.**
  - Inputs: current lap, current compound and tire age, stops done, compounds used.
  - At lap 0 it is the classic pre-race plan. At lap N it plans the rest of the race. Phase 5 reuses it as a baseline.
  - Free track means no traffic, no overtaking and no safety cars. Total time = sum of predicted lap times + pit losses.
- **D-08: Plans are per driver.**
  - `--driver ALO` selects the driver. That driver's start tire, tire age, pace offset and stops so far feed the plan.
  - The default when no driver is given is the race winner at `RACE_END`. Mid-race (`--lap N`), the default is the leader at that lap. This keeps the default inside the as-of rule.

### Interface contracts
- **D-09: `PaceModel` returns a mean and SD per lap (Normal).**
  - Vectorized: given arrays of driver, compound, tire age and lap, it returns arrays of mean lap time and SD.
  - No sampling inside the model. The Phase 3 simulator draws with its own rng, which keeps Sobol and antithetic draws under its control.
  - The Phase 7 Bayesian model satisfies this by summarizing its posterior predictive.
- **D-10: Implementations that exist in Phase 2.** *(Claude's pick)*
  - The linear wear fit **is** a `PaceModel` implementation. Fitting is a separate step (a function from `RaceSnapshot` to a fitted model object), so the Protocol covers only prediction.
  - The free-track optimizer **is** a `StrategyPolicy` implementation. Given a `RaceState`, it returns a pit decision (pit this lap and which compound, or stay out) with the full best plan attached.
  - `SimulatorBackend` is a Protocol only in Phase 2; the NumPy backend arrives in Phase 3. Its shared suite runs against a minimal conforming test double now, so the suite exists and is proven before Phase 3.
- **D-11: The shared test suite.** *(Claude's pick)*
  - One parametrized pytest suite per Protocol, driven by a registry of implementations. Adding an implementation means adding one registry entry.
  - Each suite checks both structure (mypy-visible Protocol, runtime-checkable attributes) and behavior. The behavioral contract covers: output shapes and dtypes; finite outputs; no mutation of the input `RaceState`; the same input and seed giving the same output; and the decision respecting the rules (for example, never an illegal compound).
  - A deliberately non-conforming stub is planted as a fixture, and a meta-test asserts that the suite fails it. This follows the Phase 1 pattern of planting a leaky consumer to prove the guard works. This satisfies success criterion 2.
- **D-12: `RaceState` carries all cars, as frozen plain data.** *(Claude's pick)*
  - Follows the BUILD_PLAN schema: `lap`, `laps_total`, `regime`, `pit_loss_s`, and `cars[]` with driver, position, gaps, compound, tire age, `wear_rate_s_per_lap`, `wear_sd`, `pace_offset_s`, `stops_done`, `compounds_used`.
  - Immutable. It round-trips to and from the BUILD_PLAN JSON shape, which gives a test of the schema.
  - Internal layout (list of car records, struct-of-arrays, or both) is at Claude's discretion, with the Phase 3 vectorized simulator in mind.
- **D-13: Fields not yet modeled get honest values.** *(Claude's pick)*
  - `regime` is `{"green": 1.0}`, documented as a placeholder until Phase 3/8.
  - `pit_loss_s` has only `green`, from D-05. There is no `sc` key until Phase 8.
  - `wear_rate`, `wear_sd` and `pace_offset` come from the D-01/D-04 fit.
  - Placeholders are named as such in the docstring and in DECISIONS.md, and are never silently invented.
- **D-14: One builder.** *(Claude's pick)* `RaceState` is built by one pure function from a `RaceSnapshot` plus a fitted `PaceModel`. Model and strategy code receive `RaceState` and never the accessor (Phase 1 rule). Gaps and positions come from the snapshot at the cutoff (DEC-042 semantics: leader at N laps, others at most N−1).

### What you see *(all Claude's picks)*
- **D-15: `uv run f1si wear bahrain-2023 [--lap N]`** prints a table with:
  - per compound: wear (s/lap), 95% CI, clean laps used;
  - the fitted fuel effect with its CI;
  - the measured pit loss with its spread;
  - laps dropped, by reason.

  It also writes `reports/wear-bahrain-2023.png`: fuel-corrected clean lap time vs tire age, one panel per compound, points by driver, with the fitted line and its band. Static matplotlib, no pyplot (D-15/DEC-050 conventions).
- **D-16: `uv run f1si plan bahrain-2023 --driver ALO [--lap N]`** prints:
  - the best 1-stop and best 2-stop plans, plus the top 5 overall. Each shows stop laps, compounds, total race time and gap to best.
  - one comparison line: the driver's actual strategy priced by the same model, labeled "compared against", not "beats" (BUILD_PLAN honesty rule). At `RACE_END` the actual strategy is read through the as-of door. Mid-race, only the visible stints are shown.
- **D-17: Error messages say what to do next, and commands are copy-pasteable in PowerShell** (Phase 1 specifics). An unknown driver lists the valid codes. A wet race, or a compound without enough data, explains why there is no answer.
- **D-18: Explainer `docs/explained/phase-02.md`**, in the Phase 1 D-17 format: what was built and why, how the pieces connect, a file-by-file tour, and 3–5 interview Q&As. Suggested topics: why fuel and wear are separable, what a Protocol buys you, why free-track is a lower bound. A short plain-language summary goes in chat at phase end. `tests/test_docs.py` (DEC-051) keeps it complete.

### Claude's Discretion
- The exact regression method (OLS via NumPy/SciPy lstsq with classical SEs is enough; heteroskedasticity-robust SEs are optional). Log it.
- The outlier threshold, minimum clean laps per compound, minimum stint length and default pit loss (D-02, D-03, D-05, D-06). Log each in DECISIONS.md.
- Module names and layout. Suggested: `f1si/interfaces.py`, `f1si/state.py` (RaceState and builder), `f1si/pace/linear.py`, `f1si/strategy/free_track.py`, a shared clean-lap module. These must be registered with the Phase 1 import-ban policy table and the scramble-test consumer registry if they read snapshots.
- Brute-force mechanics. Enumerate every (stop lap, compound) sequence; vectorizing is optional, since a 57-lap race has only a few thousand plans.
- Whether the shared test suites also use hypothesis property tests (encouraged where natural, for example "total time is never below N × min lap").

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design source
- `F1 Docs/BUILD_PLAN.md`:
  - §Architecture: the plug-in interfaces and the `RaceState` JSON shape (D-12).
  - §How a strategy call works: the shape of later outputs that `StrategyPolicy` must allow.
  - §Lean MVP, Week 2: fuel correction, linear wear, free-track optimizer.
  - §Data, validity and honesty: look-ahead, hidden variables, honest claims ("compared against").
- `F1 Docs/MASTER_PROMPT.md` — required plug-in interfaces; every implementation passes the same shared tests.

### Project planning
- `.planning/PROJECT.md` — constraints (mypy strict, rng convention, synthetic recovery tests, DECISIONS.md) and audience (owner new to coding).
- `.planning/REQUIREMENTS.md` — INT-01..03, PAC-01..02, UI-03.
- `.planning/ROADMAP.md` §Phase 2 — the five success criteria.
- `.planning/phases/01-foundation-data/01-CONTEXT.md` — the as-of rules (D-01..D-04), the CLI shape (D-14), plot conventions (D-15/D-16), the explainer format (D-17).
- `DECISIONS.md` — especially DEC-041..DEC-045 (doors, cars at a cutoff, stint/pit rebuild, history, scramble rules) and DEC-050 (stint plot conventions, clean-lap fade rule).

### Existing code this phase builds on
- `src/f1si/data/asof.py` — `AsOfAccessor`, `RaceSnapshot`, `RACE_END`. The only data door.
- `src/f1si/data/_snapshot.py` — `RaceSnapshot` fields (`entries`, `laps`, `stints`, `pit_events`, `cars`, `track_status`).
- `src/f1si/synthetic/generator.py` — lap-time model identical to D-01. `SyntheticTruth` holds the true fuel and wear values for recovery tests.
- `src/f1si/plots/stints.py` — `_fade_reason`, the clean-lap rule to be shared (D-02).
- `tests/guards/` — the import-ban policy and the scramble consumer registry that new snapshot consumers must join.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **The synthetic generator** (`f1si.synthetic.generator`): it already produces races with known fuel, per-compound wear, driver offsets and pit loss. Recovery tests for D-01/D-04/D-05 can use it directly. Its default races are short (12 laps, 6 drivers), so a longer spec with two stints per driver may be needed for fuel identification.
- **The stint-plot data prep** (`prepare_stint_plot_data`, `_fade_reason`): reuse it for the clean-lap mask and for the wear PNG's styling.
- **The CLI** (`src/f1si/cli.py`): add `wear` and `plan` subcommands alongside `load`/`races`/`plot`. Follow its slug resolution and error style.

### Established Patterns
- Model code receives snapshots (plain data), never the accessor. The import ban and the future-scramble test enforce this; new consumers must register.
- An explicit keyword-only `rng: np.random.Generator` everywhere. Legacy `np.random.*` is banned by ruff NPY002.
- Frozen dataclasses for value objects (`AsOf`, `RaceInfo`, `RaceSnapshot`).
- Every method choice gets a `DEC-NNN` entry in DECISIONS.md. Phase 1 ended at DEC-060.
- Plots are static matplotlib without pyplot, written to `reports/`.

### Integration Points
- `RaceState` (D-12/D-14) is the input to Phase 3's `SimulatorBackend` and Phase 5's `StrategyPolicy`. Its field set must not need breaking changes later; only placeholder values (D-13) get filled in.
- `PaceModel` mean+SD (D-09) is what the Phase 3 simulator samples. The Phase 4 Kalman filter refines the per-car `wear_rate`/`wear_sd`.
- The free-track optimizer (D-07) is Phase 5's baseline policy.

</code_context>

<specifics>
## Specific Ideas

- The owner is new to coding. Outputs should be readable tables with units (s, s/lap). Every number that is a placeholder or fallback is labeled as such.
- Honesty rule: the comparison with the actual strategy is "compared against", never "beats".
- The fitted fuel effect is shown next to a literature range so a reader can sanity-check it at a glance.

</specifics>

<deferred>
## Deferred Ideas

- **Per-driver wear slopes.** Phase 4 (Kalman) and Phase 7 (Bayesian).
- **Pooling wear across earlier races at the same circuit as a prior.** Phase 7.
- **Free starting-tire choice ("what should they have started on?").** A possible later analysis; not needed by any M1 phase.
- **3-stop plans and wet-race strategy.** Outside PAC-02's 1/2-stop scope.
- **Tire cliff (non-linear wear) and track evolution terms.** Upgrades beyond the linear MVP model (Phase 7 / M2 physics).
- **Regime-dependent pit loss (cheaper under SC).** Phase 8 (REG-03).

</deferred>

---

*Phase: 02-interfaces-linear-tire-wear-free-track-optimizer*
*Context gathered: 2026-11-11*
