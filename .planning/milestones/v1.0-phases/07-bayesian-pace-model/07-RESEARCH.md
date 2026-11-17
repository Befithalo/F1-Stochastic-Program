# Phase 7: Bayesian Pace Model - Research

**Researched:** 2026-11-16
**Domain:** Hierarchical Bayesian regression with PyMC and cutoff-safe F1 lap data
**Confidence:** HIGH for PyMC API and project seams; MEDIUM for prior scales and expected real-world accuracy until measured

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Fit only completed clean laps from earlier in-sample races and the current cutoff-local snapshot. Do not use current-race results, later laps, or 2026 data.
- Use partially pooled team/car and driver effects, compound offsets and wear, fuel proxy, era, and event intercepts. Team name is only a car-performance proxy.
- Keep the linear model's clean-lap rules, benchmark, and fallback.
- Population-shrink sparse groups and report prior-driven predictions.
- Use seeded PyMC variational inference for repeated fits, validate against a bounded NUTS reference, and surface fit failure explicitly.
- PaceModel.predict returns residual lap noise only. Shared driver and tire-parameter uncertainty travels through the existing state fields and is not counted again as per-lap noise.
- Integrate at the current PaceModel composition seam without changing strategy, simulator, or score semantics.
- Evaluate chronological race-grouped walk-forward MAE against the identical scored targets; require at least 15% improvement and freeze split/mask/seed before scoring.
- Use seeded multi-team, multi-driver, multi-compound, multi-race and multi-era synthetic data with declared recovery tolerances and posterior predictive coverage.

### the agent's Discretion
- Select coordinates, prior scales, convergence checks, iteration caps, fit cache key, test size, numerical tolerances, and held-out split before evaluation.
- Use official PyMC documentation and retain only compact posterior summaries required by the simulation interface.
- Fix model or eligibility defects without tuning against scored real outcomes.

### Deferred Ideas (OUT OF SCOPE)
- Markov regimes, regime-specific pit loss, the 20-race per-era strategy report, and the one-time holdout belong to Phase 8.
- UI/UX changes, live data, deployment, and broader model families are out of scope.
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Cutoff-local race data assembly | API/Backend | Database/Storage | Only the replay/backtest composition layer owns AsOfAccessor and History; model code receives plain snapshots. |
| Bayesian pace fit and prediction | API/Backend | — | PyMC operates on prepared numeric training rows and returns the existing PaceModel prediction contract. |
| Monte Carlo uncertainty transport | API/Backend | — | RaceState carries shared driver-offset and wear uncertainty; simulator retains control of random draws. |
| Synthetic and walk-forward evaluation | API/Backend | Database/Storage | Synthetic truth is local; real samples enter through existing as-of accessors. |
</architectural_responsibility_map>

<research_summary>
## Summary

The project already has a prediction-only PaceModel protocol, an as-of snapshot/history boundary, a per-compound linear baseline, a simulator that separates per-lap noise from shared driver-offset and wear draws, and seeded synthetic race data. The Bayesian fit belongs behind the replay/backtest composition point. Training rows should be assembled before entering the model module; fitting code should receive plain rows and no accessor.

The official current PyMC 6.4 documentation exposes pm.fit with method and random_seed, Approximation.sample for variational posterior draws, and pm.sample for a seeded NUTS reference. The official quickstart demonstrates full-rank ADVI, which estimates covariance among parameters. Variational approximations can be faster but less accurate or biased, so the operational method needs an explicit convergence check and a bounded NUTS comparison on synthetic data. Do not present approximate posterior intervals as calibrated until recovery and coverage tests support them.

**Primary recommendation:** Implement a hierarchical Gaussian pace model in PyMC using full-rank ADVI for cutoff fits, with a small deterministic posterior sample and a separately seeded NUTS reference test. Translate posterior means/SDs into the current PaceModel plus RaceState fields; keep per-lap residual sigma separate from shared effects.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyMC | 6.4.x, constrain project dependency to >=6.4,<7 | Probabilistic hierarchical regression and variational/NUTS inference | Required by PAC-05; current official stable docs are 6.4.0. |
| NumPy | Existing project bound >=2.3,<3 | Numeric design and posterior prediction arrays | Already used by the simulator and explicit RNG paths. |
| pandas | Existing project bound >=2.3.3,<3 | Assemble clean race-lap rows from snapshots/history | Existing data and baseline representation. |
| ArviZ | Resolved with PyMC 6 | Posterior diagnostics and InferenceData handling | PyMC returns InferenceData by default; use diagnostics supported by its dependency graph. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Full-rank ADVI plus NUTS reference | NUTS for every replay cutoff | Stronger posterior sampling but likely too slow for repeated walk-forward fits. |
| Full-rank ADVI | Mean-field ADVI | Faster but assumes independent variational parameters and can miss coefficient correlations. |
| PyMC | Hand-coded linear algebra or another PPL | Would not satisfy the PyMC requirement and would duplicate probability/inference machinery. |

**Installation:** Add PyMC to runtime project dependencies, then update and verify uv.lock using the locked sync path used in CI.
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Data flow

~~~text
AsOfAccessor.snapshot(current race, lap N) ─┐
                                           ├─ clean, identify, scale ─ PyMC fit
AsOfAccessor.history(current race, lap N) ─┘                            │
                                                                       ├─ PaceModel mean + residual SD
RaceState builder ◀── posterior shared offset/wear summaries ◀─────────┘
       │
       └─ existing strategy + simulator RNG and parameter draws
~~~

### Model form

Use an additive model in seconds:

~~~text
lap_time =
    global pace
  + regulation-era offset
  + race/event offset
  + team/car offset
  + driver offset
  + fresh-compound offset
  + shared fuel proxy × (lap - 1)
  + compound wear × tire_age
  + residual error
~~~

Use zero-centered, partially pooled group effects with explicit reference/centering constraints so the intercept is identified. Use a non-centered parameterization for hierarchical group effects. Center and scale lap and tire-age predictors for fitting; transform coefficients back to seconds per lap in the public fit object. Use the same clean-lap classifier as the linear baseline.

Every 2023-2025 catalog race is tagged ground_effect_2022_2025. The model can carry an era term and synthetic data can exercise multiple era levels, but no real between-era effect is identifiable from this cache. The 2026 out-of-sample door stays locked.

### Project structure

- src/f1si/pace/bayesian.py: immutable fit result and PaceModel prediction implementation.
- src/f1si/pace/training.py or an equivalent private helper: join History and snapshot rows, classify clean laps, normalize identifiers, and build numeric indexes without reading the database.
- tests/pace/test_bayesian_model.py: shape, deterministic seed, prior-only fallback, and protocol behavior.
- tests/pace/test_bayesian_recovery.py: synthetic parameter and predictive-coverage recovery.
- tests/pace/test_bayesian_walk_forward.py: frozen real split and shared-row MAE comparison.

Only create separate modules when they keep the public model module focused; avoid a generic model framework.

### Prediction and uncertainty

The simulator's sd table is independent per-lap noise. RaceState separately supplies shared per-car pace-offset draws and shared tire-wear draws. Therefore predict must return the posterior mean and residual standard deviation only. Combine the applicable team and driver posterior means into the per-car pace offset; propagate their marginal uncertainty through pace_offset_sd. Propagate compound wear posterior uncertainty through wear_sd. Do not double-count shared uncertainties in predict's sd output.

### PyMC usage pattern

Create a fresh model from numeric training arrays, call seeded pm.fit(method="fullrank_advi", n=..., random_seed=...), then draw a bounded reproducible sample from the resulting approximation. Disable the progress bar for application and test runs. Check finite/non-increasing recent loss and parameters, and fail explicitly when the convergence criterion is not met. Use pm.sample with explicit random_seed and four independent chains on a compact synthetic reference fixture; inspect convergence and compare posterior intervals with generated truth.
</architecture_patterns>

<code_examples>
## Code Examples

The official docs show the functional variational entry point and a sampled approximation:

~~~python
with model:
    approx = pm.fit(
        n=iterations,
        method="fullrank_advi",
        random_seed=seed,
        progressbar=False,
    )
    posterior = approx.sample(draws=draw_count, random_seed=seed)
~~~

The reference sampler should also use explicit seeds:

~~~python
with model:
    idata = pm.sample(
        draws=draws,
        tune=tune,
        chains=4,
        random_seed=seed,
        progressbar=False,
        return_inferencedata=True,
    )
~~~
</code_examples>

<common_pitfalls>
## Common Pitfalls

### Look-ahead through training assembly
Build current rows from RaceSnapshot.laps only and earlier rows from History.laps only. Do not call RACE_END for the current event, import results, or allow a model object to retain the accessor.

### Unidentified effects from F1 data
Fuel trend is confounded with track evolution; team and driver effects are nested; there is only one regulation era in 2023-2025. Use explicit centering, weakly informative priors, and report which effects are supported by data. Synthetic multi-era recovery is not evidence that a real 2026-era coefficient was measured.

### Unfair baseline comparison
Freeze race split, cutoff rule, clean-lap eligibility, target rows, and seed derivation before scoring. Both models must be evaluated on the exact same finite next-lap targets. Do not tune the held-out model after inspecting its outcomes.

### Double-counting uncertainty
The simulator already draws driver offset and tire wear from RaceState. If Bayesian parameter uncertainty is also returned as per-lap sd, the simulator treats one shared uncertainty source as fresh noise every lap.

### ADVI uncertainty overconfidence
Variational inference is approximate and its marginal bands may be narrow or biased. Compare against NUTS on known synthetic data; if diagnostics or coverage fail, do not claim the output is calibrated.

### Categorical identifier drift
Driver numbers are not stable across events. Train using entry.driver_id and team_name keyed by race_id; translate the current snapshot's driver number to the fitted identity for prediction.
</common_pitfalls>

<validation_architecture>
## Validation Architecture

- Unit: input row selection and grouping are cutoff safe; output shape, positivity, finite values, stable fixed seed, unknown-group prior behavior, and unchanged shared PaceModel conformance.
- Synthetic recovery: seeded panels with multiple eras, races, teams, drivers, and dry compounds. Declare effect-specific tolerances before fitting. Require principal known effects inside posterior 90% intervals and report predictive interval coverage.
- Reference inference: NUTS on a bounded fixture, four chains with explicit seed; check convergence diagnostics and compare recovered effects and posterior uncertainty to the operational ADVI result.
- Real evaluation: 2025 held-out race group(s), each target predicted from earlier in-sample History plus the target race prefix. Freeze cutoff and clean-row rules before scoring; compute MAE on a common row mask and require at least 15% improvement over the per-compound linear baseline.
- Integration: run replay and one backtest path with the Bayesian fit selected at the existing seam; verify no future-scramble guard failures and no simulator API change.
- Quality gate: focused tests, then ruff check/format, mypy, full pytest coverage, locked environment, and CI on the pushed exact head.
</validation_architecture>

<sources>
## Sources

### Primary
- https://www.pymc.io/projects/docs/en/stable/api/generated/pymc.fit.html — current pm.fit arguments, including method and random_seed.
- https://www.pymc.io/projects/docs/en/stable/api/generated/pymc.sample.html — NUTS sampling, chains, seeds, and InferenceData.
- https://www.pymc.io/projects/examples/en/latest/introductory/api_quickstart.html — official full-rank ADVI, approximation sampling, and variational accuracy caveat.
- https://www.pymc.io/projects/docs/en/stable/installation.html — current PyMC installation and optional samplers.
- https://www.pymc.io/blog/pymc_v6_ecosystem_updates.html — PyMC 6/PyTensor 3 release changes and ecosystem notes.
- .planning/ROADMAP.md, .planning/REQUIREMENTS.md, .planning/PROJECT.md — project scope and requirements.
- src/f1si/interfaces.py, src/f1si/data/asof.py, src/f1si/data/_snapshot.py, src/f1si/pace/linear.py, src/f1si/state.py, src/f1si/sim/numpy_backend.py — local protocol and data/uncertainty contracts.
</sources>
