# Phase 8: Markov Regimes & Full Backtest - Research

**Researched:** 2026-11-16  
**Domain:** Cutoff-safe regime estimation, Monte Carlo simulation, and one-shot holdout evaluation  
**Confidence:** HIGH for repository contracts; MEDIUM for the proposed kernel integration

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Regime labels and cutoff visibility
- **D-01:** Use one mutually exclusive leader-lap regime derived from cutoff-visible track-control and weather observations. Priority is red, SC, VSC, wet, green. Rainfall marks wet only when red, SC and VSC are not active; yellow maps to green because yellow is not one of the five required states. Missing rainfall is not inferred from tyre choice or future laps.

#### Markov training and holdout isolation
- **D-02:** Estimate one-lap transition counts from earlier completed in-sample races only and apply Dirichlet(1) smoothing to every destination in each source-state row. At each cutoff, derive the starting state from the current snapshot. For 2026 holdout predictions, fit transitions only from 2023–2025 data; do not use any race or cutoff from the locked 2026 group to fit or update the matrix. Use a synthetic sequence with known transitions to test matrix recovery.

#### Pit-loss assumptions
- **D-03:** Retain the existing measured green-flag pit-loss baseline. Use 0.75 times green for VSC and 0.5 times green for SC, preserving the project's existing SC assumption. Keep red and wet at green cost unless the model has defensible measured evidence otherwise. Treat these regime adjustments as explicit assumptions, not measured regime-specific pit times; the existing pit-loss estimator excludes stops on slow-status laps.

#### Backtest and holdout protocol
- **D-04:** Freeze the 20 in-sample race IDs, all predictions' seed derivation, model settings, eligible target mask, metric definitions, and report structure before scoring. Keep Phase 6's 1,000 simulations, base seed 0, risk setting 0.5, same clean-lap and paired-row rules, and race-weighted metric conventions for comparability.
- **D-05:** Freeze 2026-09 through 2026-17 as the single holdout group before any call to the out-of-sample results door. Score it once, only after the phase implementation and lock are committed. Use earlier 2023–2025 history for model fitting and the current race's cutoff-visible snapshot for its state; never use another 2026 holdout race as training history. Publish per-race and per-era denominators and keep the holdout results separate from the 20-race in-sample result.

### Carried forward from Phase 7
- The locked Phase 7 real-data score did not meet PAC-06: Bayesian next-lap MAE was 47.993% higher than the linear baseline. Preserve that result and keep linear pace as the default for Phase 8 scoring. Do not retune the Bayesian model against those races or imply that PAC-06 passed.
- Do not make any UI/UX changes in Phase 8.

### the agent's Discretion
- Choose the Markov model's internal representation, transition-count implementation, synthetic test size and recovery tolerance, and the smallest module/API changes that preserve existing contracts.
- Choose per-race report diagnostics and runtime optimizations that preserve the frozen sample, simulation count, seeds, cutoff rules and holdout protocol.

### Deferred Ideas (OUT OF SCOPE)
Broader physics or machine-learning models, live data, deployment, external odds, and dashboard changes remain outside Phase 8.
</user_constraints>

## Summary

Implement the five-state model using the repository's existing data doors and simulator path. The current composition function already obtains a cutoff snapshot and its strictly earlier `History`, then fits pace, measures visible green-flag pit loss, builds `RaceState`, and estimates a safety-car rate. Keep that orchestration pattern; replace the SC estimate with a history-only transition model, derive the initial label from the snapshot, and pass a validated transition matrix and five-entry pit-loss mapping into state/simulation. [VERIFIED: `src/f1si/cli.py:1090-1161`; `src/f1si/regime/sc_rate.py:107-119`; `src/f1si/state.py:501-520`]

The scoring work has two separate products: the locked 20-race in-sample report and the single 2026 holdout report. Freeze races, cutoff/target rules, seed derivation, settings, metrics and report schemas in committed lock artifacts before scoring. Keep results access outside prediction generation, and put any 2026 outcome access only in the dedicated `f1si.evaluation.holdout` module, which the import policy permits to import `f1si.data.out_of_sample`. Do not open the 2026 results door before that lock commit. [VERIFIED: `src/f1si/backtest/walk_forward.py:18-30,80-85,275-310`; `src/f1si/backtest/scoring.py:149-158`; `tests/guards/import_scan.py:118-125`; `src/f1si/data/out_of_sample.py:1-5`]

**Primary recommendation:** keep regime estimation pure over `History`/snapshot inputs, transition simulation array-based inside the existing Numba kernel, and maintain separate prediction and score layers. Add no dependency and make no UI changes. [VERIFIED: `src/f1si/regime/sc_rate.py:29,107-119`; `src/f1si/sim/kernel.py:74-95`; `pyproject.toml:6-20`]

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REG-02 | A Markov regime model (green/VSC/SC/red/wet) replaces per-lap safety-car probability, with a synthetic-data test recovering its transition matrix. | Estimate counts from earlier completed in-sample race sequences, apply the locked Dirichlet(1) row smoothing, initialize from the cutoff-visible regime, simulate transitions from the current state, and test a seeded synthetic known matrix. |
| REG-03 | Pit loss depends on regime (e.g. cheaper under safety car). | Keep measured green pit-loss and provide the five locked regime values as state data; test exact ratios and simulator stop cost by active regime. |
| BKT-03 | Backtest covers at least 20 races (10 at the MVP checkpoint), with results reported per era. | Lock the 20 calendar-first races before score; retain Phase 6 metrics/row rules; state clearly that all 2023–2025 races map to one in-sample era and report its denominators separately from 2026. |
| BKT-05 | A locked holdout set is defined and touched only once, at milestone end. | Commit the 2026-09…2026-17 holdout lock and implementation before the single scoring run; keep all 2026 fitting on 2023–2025 history and never train across holdout races. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Observed regime labels and transition counts | Data/model | Replay composition | `AsOfAccessor` supplies snapshots and earlier-only `History`; the estimator can remain a pure function over those inputs. |
| Race-state regime and pit-loss contract | Shared state | Replay composition | `RaceState` is the simulator and policy's shared immutable input; the CLI currently builds it from snapshot, fit and measured pit loss. |
| Future regime trajectory and regime-dependent pit charge | Simulation kernel | NumPy simulator adapter | The Numba lap kernel currently handles one safety-car uniform and two pit costs; its Python adapter owns the typed `RaceState` conversion. |
| In-sample predictions and scoring | Backtest | CLI/composition | `walk_forward` produces the full trace without outcomes; scoring joins final classifications afterward. |
| 2026 predictions and scoring | Evaluation | Restricted out-of-sample door | The separate door raises for in-sample races; the import guard reserves it for `f1si.evaluation.holdout`. |

## Standard Stack

No external package is required for this phase. Reuse the existing locked Python/uv, NumPy, pandas, SciPy, Numba, pytest and Hypothesis stack. [VERIFIED: `pyproject.toml:6-20,34-41`]

| Library/tool | Declared constraint | Purpose in this phase |
|---|---|---|
| Python | `requires-python = ">=3.12,<3.13"` | Existing runtime. |
| NumPy | `numpy>=2.3,<3` | Fixed-size state/transition arrays, simulation draws, seeded synthetic sequence. |
| pandas | `pandas>=2.3.3,<3` | Existing normalized snapshots, history tables, report assembly. |
| SciPy | `scipy>=1.15,<2` | Existing Sobol/antithetic sampling and bootstrap/statistical helpers; no new SciPy API is needed. |
| Numba | `numba>=0.68,<1` | Existing compiled per-lap simulator. |
| pytest / Hypothesis | `pytest>=9.1,<10`; `hypothesis>=6.170` | Unit, contract, synthetic recovery and no-look-ahead tests. |
| ruff / mypy | `ruff==0.17.1`; `mypy>=2.4,<3` | Required lint, formatting and strict type checks. |

**Installation:** none; do not add a package for a five-state transition matrix or evaluation runner.

### Alternatives Considered

The phase context locks the method and the allowed discretion is internal representation. No alternate regime package or external data source is needed.

## Architecture Patterns

### Data path

```text
earlier in-sample History ──> observed five-state sequences ──> smoothed transition matrix
cutoff RaceSnapshot ──> current state label + measured green pit loss ──> RaceState
RaceState + matrix + seeded uniforms ──> Numba per-lap simulation ──> frozen predictions
frozen predictions ──> separate results/evaluation door ──> in-sample or holdout report
```

### Pattern 1: Label a leader-lap regime from visible observations

Use the phase's mutually exclusive priority verbatim: `red > SC > VSC > wet > green`. The normalized track-status codes are exactly `"1", "2", "4", "5", "6", "7"`; the schema describes them as `1 green, 2 yellow, 4 safety car, 5 red flag, 6 virtual safety car (VSC) deployed, 7 VSC ending`. Weather has a nullable `rainfall` boolean. These values are from the source of truth. [VERIFIED: `src/f1si/data/schema.py:152-200`]

The track-status builder's own priority is `red "5" > safety car "4" > VSC deployed "6" > VSC ending "7" > any yellow "2" > green "1"`; its VSC-ending event remains active until the later clear or assumed expiry. The phase priority supersedes yellow and the builder's no-weather view. Treat codes 6/7 as the VSC bucket while the cutoff-visible timeline reports them; treat yellow as green; consult only rainfall rows visible at the same cutoff; if rainfall is missing, do not infer wetness. [VERIFIED: `src/f1si/data/sources/track_status_map.py:7-34,49,149-152`; `src/f1si/data/_snapshot.py:11,20-25`; locked D-01 above]

For history, create exactly one label per leader lap from track-control and weather rows visible at that lap's cutoff, then count consecutive labels within each race. Do not form transitions across race boundaries. A race's current snapshot supplies the initial simulated label; its own events are not training transitions. [VERIFIED: `src/f1si/data/_snapshot.py:11-25,155`; `src/f1si/data/asof.py:90-121`; locked D-02 above]

### Pattern 2: Fit only from `History`; smooth each source row

Follow `estimate_sc_rate(history)`: accept `History`, not an accessor, and let the caller obtain `accessor.history(at)`. The data door documents history as earlier complete in-sample races only; its predicate excludes out-of-sample rows. Count the five-by-five transitions on this input and apply the locked pseudocount of one to each destination in every row, including unseen rows. Validate finite nonnegative entries and that each row sums to 1 before returning it. [VERIFIED: `src/f1si/regime/sc_rate.py:29,107-119`; `src/f1si/data/_snapshot.py:150-155`; locked D-02 above]

Recommended representation: a stable five-label constant tuple and a `float64[5,5]` array, with conversion and row validation in Python before passing it to the kernel. This keeps labels readable at the data/state boundary and indices simple in compiled code. This is an implementation recommendation, not a locked external API. The current kernel is `@njit(cache=True)` and array-oriented; Numba's official docs state nopython is its default fast mode and has supported-type limits. Keep Python objects, pandas rows and dictionary lookups outside the hot loop. [VERIFIED: `src/f1si/sim/kernel.py:65-95`; CITED: https://numba.readthedocs.io/en/stable/user/jit.html]

Synthetic recovery should use a fixed seeded generator and a known five-state transition matrix with observed departures from every row. Compare recovered row probabilities against a declared numeric tolerance and separately assert valid normalized rows. With Dirichlet(1), the test size must be large enough that the expected smoothing bias is below that tolerance; do not claim exact equality to the generating probabilities. [RECOMMENDATION based on locked D-02 and `src/f1si/rng.py`]

### Pattern 3: Keep RaceState plain and preserve shared simulation draws

`RaceState` currently freezes mapping inputs and verifies a non-empty regime distribution sums to 1. The builder currently returns one-hot `{"sc": 1.0}` or `{"green": 1.0}` and a two-key pit-loss map. Generalize that contract to the five required labels and all five costs; do not make the state object reach back into the cache. [VERIFIED: `src/f1si/state.py:234-267,501-520,652-653`]

The kernel draws one safety-car uniform per simulated race/lap from the same fixed-dimension block used for Sobol/antithetic draws, then applies fixed SC duration mechanics. Replace that binary event with a cumulative categorical draw from the current state's transition row, update each path's regime index, and use that lap's regime pit-loss value. Reuse the per-path/lap uniform dimension where possible so the locked seed scheme and common-random-number structure do not change unnecessarily. Preserve explicit `np.random.Generator` construction in the Python adapter. [VERIFIED: `src/f1si/sim/numpy_backend.py:335-336,401-407`; `src/f1si/sim/kernel.py:23-24,92-95,133-151`; `src/f1si/rng.py`]

Locked pit map: green is the measured value; VSC is `0.75 * green`; SC is `0.5 * green`; red and wet each equal green. The current measured pit-loss function identifies the green baseline from complete in/out-lap pairs and counts any SC/VSC/red stop as slow-excluded; it returns the documented default if no eligible measured stop exists. Keep multiplier values labeled as assumptions in decisions and reports. [VERIFIED: `src/f1si/pace/linear.py:558-626`; locked D-03 above]

The simulator currently has special SC time compression, restart spacing, and opportunistic stop handling. The phase decisions specify regime transitions and pit costs, but do not define new wet-pace, red-flag suspension, or VSC lap-time mechanics. Keep plan scope to the specified regime model/pit-cost behavior plus established SC behavior; describe unsupported effects plainly rather than inventing measured physics. [VERIFIED: `src/f1si/sim/kernel.py:23-24,133-151`; recommendation constrained by D-01–D-03]

### Pattern 4: Freeze then score; keep race-level summaries race-weighted

The 20 in-sample IDs are locked by context as `2023-01`–`2023-07`, `2024-01`–`2024-07`, and `2025-01`–`2025-06`; the holdout IDs are `2026-09`–`2026-17`. Catalog/load metadata was inspected before this research; no 2026 result was opened. All 2023–2025 eras are `ground_effect_2022_2025`, and `reg_2026` is explicitly out-of-sample, so show only one in-sample era row and disclose the between-era limitation. [VERIFIED: `src/f1si/eras.py:16-31`; locked D-04/D-05 above]

Reuse Phase 6's equal-race aggregation and whole-race bootstrap conventions. Freeze the exact sample, eligible rows, report schema, 1,000 simulations, seed 0, risk 0.5, and current seed function (`(seed + crc32(f"{race_id}:{driver}:{lap}")) & 0x7fffffff`) before the prediction run. Publish denominators for each race and each displayed era, including rows with no eligible observations. Preserve Phase 6 metrics and pairwise masks instead of changing score definitions to improve the result. [VERIFIED: `src/f1si/backtest/walk_forward.py:80-85,224-225,275-310`; `src/f1si/backtest/scoring.py:691-754`; `reports/backtest/phase-06.json:metadata`]

The holdout scorer is a separate implementation boundary. `out_of_sample.py` says only the Phase 8 holdout evaluator may import it; `tests/guards/import_scan.py` enforces that. Make lock verification read-only, and put `OutOfSampleAccessor` use solely in that evaluator. The lock, implementation and report protocol must be committed before opening 2026 outcomes; perform one score, then verify its existing artifact without rescoring. [VERIFIED: `src/f1si/data/out_of_sample.py:1-5,34-58`; `tests/guards/import_scan.py:118-125`; locked D-05 above]

There is a history-door gap to resolve explicitly in the plan: `AsOfAccessor._check` rejects out-of-sample anchors, and its history predicate includes only races earlier than its anchor. Therefore `AsOfAccessor.history(AsOf("2026-09", ...))` cannot produce the desired 2023–2025 history, and history at the final 2025 anchor omits that anchor race. The current import allowlist is exactly `_REPLAY_DRIVERS: Final = ("f1si.data.asof", "f1si.cli", "f1si.backtest", "f1si.replay")`, while `out_of_sample.py` reserves its door for `f1si.evaluation.holdout`. Do not use raw storage or results to work around this. Recommended path: make the holdout evaluator an explicitly allowed orchestration consumer of `AsOfAccessor`, enumerate only complete, in-sample 2023–2025 catalog entries, obtain feature-only full-race snapshots with `RACE_END`, derive leader-lap sequences from their normalized laps/status/weather, and pass those observed sequences to the pure transition fitter. Add import and no-future coverage for that route. [VERIFIED: `src/f1si/data/asof.py:86-121`; `src/f1si/data/_snapshot.py:150-155,475-492`; `tests/guards/import_scan.py:73-74,128-140`; `src/f1si/data/out_of_sample.py:1-5`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Raw race-data access | Direct DuckDB reads from the estimator or simulator | `AsOfAccessor.snapshot` and `.history` | The accessor is the cutoff and earlier-history boundary. |
| 2026 results access | An `unlock` flag or generic results accessor | Dedicated `OutOfSampleAccessor` inside `f1si.evaluation.holdout` | Existing import rules keep the one-shot holdout result door isolated. |
| Green pit-loss estimation | A new estimator from SC/VSC/red-flag stops | `measure_pit_loss(snapshot, fit)` | It already filters slow stops and marks fallback use. |
| Prediction metrics | A new Brier/interval/bootstrap implementation | Existing `f1si.backtest.scoring` and `metrics` functions | Phase 8 is required to remain comparable to the Phase 6 report. |
| RNG / Markov sampling | Module-global random calls or Python `random` | Existing `make_rng`/uniform draw plumbing | FND-03 requires explicit generators and repeatable seeded output. |
| New external Markov package | A dependency for a five-state count matrix | NumPy arrays and the current Numba kernel | Keeps runtime, CI and lock files unchanged. |

## Common Pitfalls

### Pitfall 1: Build a regime sequence from future rows
**What goes wrong:** a race's event transition or rain observation changes a recommendation at an earlier cutoff.  
**How to avoid:** form each historical label only from rows with `visible_at_s <= cutoff`; use the existing snapshot for current state and `History` only for earlier races. Add the new state/backtest consumer to `tests/guards/consumers.py` and preserve `test_future_scramble` coverage. [VERIFIED: `src/f1si/data/_snapshot.py:11-25`; `tests/guards/consumers.py:1-14`]

### Pitfall 2: Count transitions across the end of a race
**What goes wrong:** the last lap of one event is counted as transitioning to the first lap of another, creating artificial counts.  
**How to avoid:** partition and count one sequence per `race_id`, then sum source/destination counts. [RECOMMENDATION from locked D-02]

### Pitfall 3: Collapse weather or VSC-ending semantics incorrectly
**What goes wrong:** a rain observation overrides a red/SC/VSC condition, a yellow flag becomes a sixth regime, or a visible VSC-ending interval is mislabeled green.  
**How to avoid:** apply the locked precedence and rainfall rule in one pure label function; handle track code `"7"` as the VSC bucket while the status timeline remains at VSC-ending. Test each precedence collision and missing-rainfall case. [VERIFIED: `src/f1si/data/schema.py:152-200`; `src/f1si/data/sources/track_status_map.py:7-34,49`]

### Pitfall 4: Let holdout races become training history
**What goes wrong:** prediction rows from 2026-09..17 or a current 2026 race's future affect transition counts.  
**How to avoid:** use only completed 2023–2025 history for every holdout matrix, use the current cutoff snapshot solely for current state, keep the out-of-sample import inside the holdout evaluator, and run a future-scramble/import-policy check. [VERIFIED: `src/f1si/data/_snapshot.py:150-155`; `src/f1si/data/out_of_sample.py:1-5`; `tests/guards/import_scan.py:118-125`]

### Pitfall 5: Call the discounted pit values measurements
**What goes wrong:** the report describes assumed VSC/SC discounts as calibrated from real pit-stop samples.  
**How to avoid:** use the measured green baseline only; retain the exact D-03 multipliers and label them as assumptions because slow-status stops are excluded from the baseline. [VERIFIED: `src/f1si/pace/linear.py:558-626`; locked D-03]

### Pitfall 6: Break Numba or stochastic reproducibility while adding states
**What goes wrong:** Python dicts/enums enter the hot kernel, a draw dimension changes silently, a new transition redraws from global RNG, or cache behavior masks a helper change.  
**How to avoid:** pass integer state indices and a contiguous numeric matrix; keep draws in the Python adapter and preserve the fixed per-lap uniform input. Official Numba docs caution that cached compiled functions may not detect changes in imported helper functions and treat globals as compile-time constants; keep hot-path changes local or validate a fresh compile. [CITED: https://numba.readthedocs.io/en/stable/user/jit.html; VERIFIED: `src/f1si/sim/numpy_backend.py:335-407`; `src/f1si/sim/kernel.py:65-95`]

### Pitfall 7: Change the score after seeing results
**What goes wrong:** removing races with sparse targets or revising report rules after the score creates selection bias.  
**How to avoid:** commit both lock artifacts before any real score; retain empty/unavailable race denominators and report measured results without tuning the holdout. [VERIFIED: `.planning/phases/07-bayesian-pace-model/07-05-evaluation-lock.json`; `.planning/phases/07-bayesian-pace-model/07-05-SUMMARY.md`; locked D-04/D-05]

## Code Examples

Existing composition pattern to extend (simplified from `src/f1si/cli.py:1090-1161`):

```python
snapshot = accessor.snapshot(at)
history = accessor.history(at)
fit = fit_linear_pace(snapshot)
pit = measure_pit_loss(snapshot, fit)
regimes = estimate_regime_model(history)
state = build_race_state(
    snapshot,
    fit,
    laps_total=laps_total,
    pit_loss_s=pit.median_s,
    regime_model=regimes,
)
```

`estimate_regime_model` and the added argument above are proposed interfaces, not existing source symbols; the planner should lock concrete names in the artifact list. Current source-backed pattern is that `estimate_sc_rate` accepts `History` and `build_race_state` accepts `RaceSnapshot`, pace fit, race distance, and measured pit loss. [VERIFIED: `src/f1si/regime/sc_rate.py:107-119`; `src/f1si/state.py:501-520`]

For the compiled transition step, keep only numeric inputs in the kernel: use the current regime index to select a probability row, compare the existing per-path uniform against cumulative row probabilities, update the integer regime index, then choose the pit cost for that index. This describes the recommended algorithm; it is not existing code. [RECOMMENDATION; Numba constraints cited above]

## Validation Architecture

Nyquist validation is enabled in `.planning/config.json`; CI uses the following exact commands. [VERIFIED: `.planning/config.json:14-25`; `.github/workflows/ci.yml:1-45`]

| Property | Value |
|---|---|
| Framework | pytest with Hypothesis |
| Config | `pyproject.toml` |
| Quick run | `uv run pytest tests/test_state_builder.py tests/sim/test_safety_car.py -q` |
| Full suite | `uv run pytest --cov=f1si --cov-report=term` |
| Required CI checks | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, and full pytest on Ubuntu and Windows |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| REG-02 | Seeded five-state synthetic data recovers all five transition rows; output rows normalize; labels use cutoff-visible observations. | unit/property | `uv run pytest tests/regime/test_markov.py tests/test_state_builder.py -q` | New Markov test expected; state tests exist. |
| REG-03 | All regime pit-cost multipliers are correct; simulator charges the active path's regime cost when it stops. | unit/integration | `uv run pytest tests/test_state_builder.py tests/sim/test_regime.py -q` | New regime simulation test expected; state and SC tests exist. |
| BKT-03 | Locked sample contains 20 complete in-sample races; paired metrics and report include per-race and per-era denominators. | unit/integration | `uv run pytest tests/backtest/test_walk_forward.py tests/backtest/test_scoring.py -q` | Existing backtest tests; extend for sample/report. |
| BKT-05 | 2026 set lock and score are separate; lock verifies before any one-shot scorer call; out-of-sample imports remain confined. | unit/guard | `uv run pytest tests/backtest/test_holdout.py tests/guards/test_import_ban.py tests/guards/test_future_scramble.py -q` | New holdout test expected; guards exist. |

**Wave 0 gaps:** no Markov transition model or Phase 8 evaluation module currently exists; tests for transition recovery, regime-driven kernel state, 20-race report validation and dedicated one-shot holdout behavior must be added with their implementation. `src/f1si/evaluation/holdout.py` is not present yet, and the import policy reserves that path for the protected results door. [VERIFIED: codebase file discovery; `tests/guards/import_scan.py:118-125`]

## Security Domain

No user authentication, external API integration, secrets, or UI changes are in scope. Keep the main validation control focused on numeric data boundaries: the matrix must be finite, nonnegative, exactly five-by-five, and row-normalized before entering the Numba kernel; race IDs and report paths must remain from the locked allow-list. Keep the out-of-sample import restriction as the principal data-access control. [VERIFIED: `src/f1si/state.py:259-267`; `tests/guards/import_scan.py:118-125`; implementation recommendation]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | Status code `"7"` (VSC ending) should map to the VSC bucket until its timeline expires. | Architecture Pattern 1 | A different interpretation changes transition counts and the cutoff state. This is the narrowest reading of the visible VSC-ending timeline and should be explicitly tested. |
| A2 | Existing SC-specific timing/opportunistic-stop behavior remains in scope; this phase does not invent unmeasured red-flag or wet-lap pace effects. | Architecture Pattern 3 | The five-state model could be misread as a full physical weather/red-flag model; docs must state its actual modeled effects. |
| A3 | The 2026 complete calendar and load metadata seen during discussion still describe the authorized holdout IDs; outcomes remain unopened until the committed lock. | Pattern 4 | Catalog changes before scoring would invalidate the lock; preflight should fail rather than silently replace IDs. |

## Open Questions

1. How much simulation mechanics should change for VSC and red beyond transition probabilities and the locked pit-loss map? CONTEXT.md does not lock pace compression, suspension, restart, or wet-lap effects. Recommendation: scope changes to the required transition process, regime-specific pit cost, and existing SC mechanics; state unsupported red/wet effects as limitations.
2. How should the holdout report handle a registered race absent/incomplete in the local cache? Recommendation: preserve the locked IDs and fail preflight; never replace a race after the score lock.

## Sources

### Primary (HIGH confidence)
- `08-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, `DECISIONS.md`
- `src/f1si/data/asof.py`, `src/f1si/data/_snapshot.py`, `src/f1si/data/out_of_sample.py`, `src/f1si/data/sources/track_status_map.py`, `src/f1si/data/schema.py`
- `src/f1si/state.py`, `src/f1si/regime/sc_rate.py`, `src/f1si/pace/linear.py`, `src/f1si/sim/kernel.py`, `src/f1si/sim/numpy_backend.py`
- `src/f1si/backtest/walk_forward.py`, `src/f1si/backtest/scoring.py`, `tests/guards/import_scan.py`, `tests/guards/consumers.py`
- `F1 Docs/BUILD_PLAN.md`, Phase 6 context/report, Phase 7 evaluation lock and summary

### Secondary (MEDIUM confidence)
- Numba official JIT documentation — `https://numba.readthedocs.io/en/stable/user/jit.html` (nopython limits, helper calls, and cache behavior).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — read directly from project `pyproject.toml` and CI.
- Architecture: HIGH — repository contracts and module implementations were read; the matrix representation/kernel adaptation is an implementation recommendation.
- Pitfalls: HIGH — cutoff, import, seed, and score boundaries are enforced or documented in code; VSC-ending mapping and unmodeled regime mechanics are listed as assumptions.

**Research date:** 2026-11-16  
**Valid until:** 2026-12-16 for repository patterns; external dependency versions were not changed or newly selected.
