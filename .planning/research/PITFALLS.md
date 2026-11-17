# Domain Pitfalls

**Domain:** Physics grounded F1 race pace and tire model using public timing / telemetry  
**Researched:** 2026-11-17  
**Scope:** M2 Physics; existing simulator must remain cutoff-safe and preserve the `PaceModel` seam.  
**Overall confidence:** MEDIUM — the data limitations, simulator simplifications, validation rules, and license signals are documented by primary/official sources. Actual identifiability and error size for this project's chosen model remain empirical questions until M2 calibration and holdout results exist.

## Critical Pitfalls

### Pitfall 1: Treating poorly identified vehicle parameters as measured facts

**What goes wrong:** A point-mass model can produce plausible lap times from many compensating parameter combinations. Effective power, drag, downforce, mass, grip, and track curvature can trade off against one another. Lap-time residuals also absorb driver behavior, fuel load, traffic, tire condition, weather, setup, and energy deployment. Public timing data does not uniquely identify those effects. A single best-fit parameter vector may look precise while being weakly identified.

**Why it happens:** A simple model has fewer latent variables than a real F1 car, while its observations are coarse (often just lap or sector time). Calibration can therefore assign omitted effects to whichever parameter is easiest to move. A point-mass/QSS model is a useful approximation, not a full vehicle-dynamics solution; the literature distinguishes QSS methods from optimal-control methods and documents their assumptions. [A Simple Mono-Dimensional Approach for Lap Time Optimisation](https://www.mdpi.com/2076-3417/10/4/1498), [Optimal Control for a Formula One Car with Variable Parameters](https://ora.ox.ac.uk/objects/uuid:ce1a7106-0a2c-41af-8449-41541220809f/files/m776aa23411ad9d78c36f96620a0e0f0b)

**Consequences:** Parameters may not transfer to another driver, circuit, team, tire state, or regulation era. The hybrid may learn a large correction that cancels a bad physics base, creating misleading physical interpretation and unstable extrapolation.

**Prevention:**
- Keep a minimal identifiable set of free parameters. Fix or tightly constrain parameters that cannot be learned from public timing; use externally justified ranges and label them as assumptions.
- Fit multiple conditions and races, not one lap. Examine parameter correlations, posterior intervals, profile likelihood or sensitivity, and out-of-sample errors. If the data only identifies a combined effect, report that combined effective parameter instead of claiming separate power / drag / grip measurements.
- State explicitly that the model is a point-mass approximation. Do not imply it resolves tire slip, transient load transfer, suspension, setup, or real team power deployment.
- Calibrate to a declared target (e.g. clean, fuel-corrected lap pace), and keep driver, traffic, regime and tire terms distinct where data supports them.

**Detection:** Very wide or multimodal parameter posteriors; strong parameter correlations; materially different parameter sets yielding nearly identical pace; a fit that is excellent in training but collapses on another race/circuit; or a residual model consistently cancelling the physics output.

**Phase:** Point-mass model and calibration phase. Establish bounds, sensitivity/identifiability diagnostics, and the interpretation contract before physics outputs become simulator inputs.

### Pitfall 2: Inferring tire temperature or wear as if public telemetry directly measured it

**What goes wrong:** Sparse public signals are used to produce precise latent tire-temperature, energy, or wear estimates. A latent thermal state is then presented as observed tire condition, or the same lap-time evidence is used both to estimate the state and to claim independent pace validation.

**Why it happens:** Public telemetry is appealingly detailed but does not equal team telemetry. OpenF1 documents car channels at about 3.7 Hz and location at about 3.7 Hz; location is approximate, has no left/right placement, and its origin is arbitrary. The public API does not promise tire temperature, tire pressure, carcass state, or detailed power-unit energy deployment. The distinction between latent states and observed measurements is central to tire state-space modeling. [OpenF1 API docs](https://openf1.org/docs/), [A State-Space Approach to Modeling Tire Degradation in Formula 1 Racing](https://journals.sagepub.com/doi/full/10.1177/22150218261446170)

**Consequences:** Wear, temperature, driver management, fuel, track temperature, traffic, and weather can be confounded. A plausible, smooth hidden-state trace can be a model assumption rather than evidence. Overconfident latent-state estimates will narrow race outcome uncertainty and distort pit timing.

**Prevention:**
- Keep latent state explicit in types, reports, and documentation: distinguish observed weather / timing / telemetry from inferred temperature, energy, and wear.
- Start with a small thermal model and weakly informative, physically bounded priors. Use synthetic parameter recovery to verify implementation, then report posterior uncertainty and sensitivity to priors / state equations.
- Use only information available at the prediction cutoff. Do not estimate full-stint latent state from future laps when scoring an earlier lap.
- Treat unobserved tire temperature as an assumed state with uncertainty, not a telemetry-derived fact. Do not let its posterior uncertainty disappear when passing pace to M1's simulator.

**Detection:** Very narrow state bands despite missing direct measurements; estimates that shift sharply with prior choice; implausible temperature or wear jumps; retrospective features using later stint laps; or a model described as having “measured tire temperature” without a source channel.

**Phase:** Tire thermal / wear phase. Implement state observability disclosures, cutoff-safe filtering, and uncertainty propagation at the same time as the latent model.

### Pitfall 3: Building track curvature from misaligned or under-sampled GPS

**What goes wrong:** Approximate public location samples are projected directly onto a track map and treated as exact distance-along-track or centerline coordinates. A coordinate offset, reversed orientation, wrong circuit variant, pit-lane point, or GPS noise can create false curvature spikes and erroneous corner speeds.

**Why it happens:** OpenF1 location uses an arbitrary origin and does not report lateral track placement. TUMFTM's useful geometry is sourced from OpenStreetMap, smoothed, and the maintainers explicitly state that the smoothed lines may no longer lie perfectly in the track center. Its widths are extracted from satellite imagery. A driver's sampled racing line is also not the same object as the circuit centerline. [OpenF1 location docs](https://openf1.org/docs/), [TUMFTM racetrack-database README](https://github.com/TUMFTM/racetrack-database)

**Consequences:** Distance alignment errors shift corners relative to telemetry and sector timing; curvature noise produces unstable grip limits; GPS-derived driver lines can leak setup / driver variation into nominal circuit geometry; circuit variants can be incorrectly pooled.

**Prevention:**
- Prefer a versioned, circuit-specific track reference with known direction, lap length, start/finish, and variant. Keep coordinate transforms and provenance with each track asset.
- Resample and smooth geometry with a documented method; validate closure, cumulative distance, curvature bounds, and visual/map overlays. Compare computed lap distance with authoritative scheduled/circuit distance and known sectors.
- Align telemetry to the reference using multiple landmarks or a robust circular-distance mapping. Flag pit entry/exit, missing samples, and low-confidence alignments rather than silently forcing a match.
- Use location for coarse validation or progress alignment, not to claim precise tire line, lateral placement, or exact curvature unless independently demonstrated.

**Detection:** Curvature spikes at the start/finish seam; distance drift across a lap; mismatched timing sectors; implausible corner speed predictions; discontinuous coordinates after pit lane; or large changes under minor smoothing/resampling changes.

**Phase:** Track data and point-mass foundation phase. Make geometry quality gates and alignment diagnostics prerequisites for calibration.

### Pitfall 4: Leaking race/stint information into PAC-06 or hybrid evaluation

**What goes wrong:** Lap rows are randomly split, or preprocessing / parameter fitting sees held-out outcomes. Adjacent laps from the same stint then appear on both sides of the split. Repeated observations from one race are treated as independent evidence, and the hybrid is tuned against the held-out set while it is still called a holdout.

**Why it happens:** Lap observations are temporally autocorrelated and grouped by race, driver, stint, circuit, and weather. Standard random K-fold assumes independent samples; scikit-learn explicitly warns that ordinary K-fold / ShuffleSplit can yield unreasonable correlation between train and test on time series and recommends evaluation on future observations. It also says transformations must be learned only on training data. [scikit-learn cross-validation guide](https://scikit-learn.org/stable/modules/cross_validation.html), [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls)

**Consequences:** Error reductions can be due to memorized race, driver, circuit, fuel trajectory, or stint identity rather than generalizable physics. Uncertainty intervals are too narrow if the number of laps is mistaken for the number of independent races. This would falsely close the already-unmet PAC-06 gate.

**Prevention:**
- Before fitting or scoring, commit a new M2 held-out-stint lock as required by DEC-130/132. Keep M1's locked results and 2026 report separate; do not retune the old lock.
- Keep every lap from a held-out stint together; for broader claims, also report race-clustered uncertainty and a chronological or leave-race-out sensitivity check. Use race-equal aggregation or explicitly justify another weighting.
- At each prediction cutoff, train on eligible completed history only. Fit scalers, filters, residual features, parameters, and hyperparameters using training data alone.
- Report sample counts at race, stint, driver, and lap levels. Do not use lap count as an independent-sample denominator.

**Detection:** Train/test split contains rows from the same stint or race without an explicit within-race estimand; globally fitted normalization; a held-out result changing after tuning; or confidence intervals built by resampling individual laps.

**Phase:** Hybrid / PAC-06 evaluation phase. Freeze the split, feature cutoff, metrics, and tuning budget before predictions; preserve the existing M1 gate miss as historical context.

### Pitfall 5: Mistaking synthetic recovery for real-world evidence

**What goes wrong:** A model passes parameter-recovery tests on generated data and this is reported as proof that it describes F1 or improves real pace accuracy.

**Why it happens:** Synthetic data uses the same equations and assumptions as the estimator. Recovery proves that the implementation can recover a known answer when its assumptions hold; it cannot test omitted physics, public-data noise, regime mismatch, or selection bias.

**Consequences:** A mathematically correct inverse can be wrong for the real observation process. This project already has a concrete warning: M1's Bayesian pace model recovered synthetic truth but missed its locked real-data PAC-06 comparison (0.538745 s MAE versus 0.364033 s linear baseline; DEC-130).

**Prevention:**
- Retain synthetic recovery tests as implementation checks, with multiple noise levels and intentionally misspecified cases.
- Separate test labels: `synthetic recovery`, `historical real-data predictive score`, and `strategy decision evaluation`. Never combine them into one “validated” claim.
- Require the M2 hybrid to beat the data-only Bayesian comparator on a separately locked held-out-stint set to satisfy PAC-06. Also report absolute error, interval calibration, baseline, denominators, and failures by race / era.
- If the locked gate fails, record the miss and diagnose on training data or a new future lock; do not rescore after looking at holdout outcomes.

**Detection:** Roadmap or resume language equates generated data recovery with real-world accuracy; improvements are reported only against synthetic truth; or the held-out sample is repeatedly reused after a miss.

**Phase:** Synthetic model verification belongs in each implementation phase; real evidence and gate adjudication belong in the hybrid / PAC-06 evaluation phase.

### Pitfall 6: Pooling 2026 cars with the 2022–2025 model without a regime boundary

**What goes wrong:** One set of effective power, aero, tire, and pace relationships is trained over the previous regulations and 2026 as if observations came from a stationary data-generating process.

**Why it happens:** 2026 introduces a substantial technical reset, including changes to aerodynamic components and power-unit energy rules. FIA regulations are also versioned and amended. The active project context already treats 2026 as a distinct out-of-sample era; its result is retrospectively unblinded and must remain disclosed. [FIA current 2026 technical regulation index](https://www.fia.com/regulation/category/2182), [FIA Section C technical regulations, Issue 21 (2026-10-19)](https://api.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_21_-_2026-10-19.pdf)

**Consequences:** The model averages incompatible vehicle and energy regimes, contaminates historical calibration with future evidence, and reports pooled metrics that hide structural failure. An apparently successful fit can be an artifact of the sample composition.

**Prevention:**
- Keep 2022–2025 / 2026 as explicit eras in parameter provenance, reports, and evaluation. Do not pool them by default.
- Treat 2026 as held out for generalization claims, preserve the existing retrospective-unblinding disclosure, and use only ex-ante regulation/version context for design until the authorized evaluation.
- If 2026-specific calibration is necessary, give it a versioned parameter set and label the target as 2026-specific; compare within era and do not claim historical transfer.
- Record the exact FIA regulation issue and effective date associated with each calibration.

**Detection:** Mixed-era calibration tables without era indicators; a “single F1 car” parameter vector across regulation eras; or 2026 results merged into the M1 baseline.

**Phase:** Model calibration and hybrid evaluation phases. Enforce era labels when defining data contracts and scoring, not as a post-hoc report filter.

## Moderate Pitfalls

### Residual hybrid cancels physics or double-counts pace effects

**What goes wrong:** The Bayesian residual model receives raw lap-time features that already encode fuel, tire age, track, or driver effects represented in the physics base, so it adds them twice. Alternatively, it learns a large offset that simply hides a miscalibrated physics model.

**Prevention:** Define the residual target as observed clean pace minus the physics prediction at the same as-of cutoff. Keep an explicit feature and ownership map so a latent quantity is represented once. Train the residual with out-of-fold physics predictions (or within-fold fit/predict) to avoid training on unrealistically in-sample base predictions. Plot base, residual, and hybrid errors by driver, race, circuit, stint age, and era. Fall back to a calibrated data-only baseline when physics inputs are missing or out of supported range.

**Phase:** Hybrid interface and PAC-06 phase.

### Tire state confounds wear with thermal, fuel, driver management, and race regime

**What goes wrong:** The model calls every within-stint pace trend “wear.” In reality, warm-up, thermal degradation, track evolution, fuel burn, graining, traffic, lift-and-coast, and safety-car laps can change lap times in different directions.

**Prevention:** Separate fuel correction, compound/age effect, thermal state, and race regime where possible; use an explicit excluded/adjusted-lap policy. Let uncertain/unobservable state remain uncertain. Avoid fitting thermal time constants from a handful of laps with no direct temperature readings. Compare against a simpler monotone-wear baseline and report when the additional state does not improve locked predictive performance.

**Phase:** Thermal/wear phase and subsequent hybrid evaluation.

### Misreading telemetry channels or sparse samples as complete signals

**What goes wrong:** Approximately 3.7-Hz speed/throttle/brake/gear or position samples are assumed continuous, aligned across channels, or equivalent to high-frequency team telemetry. Differentiating noisy positions to obtain acceleration or curvature magnifies sampling and alignment errors.

**Prevention:** Keep raw timestamps and channel provenance; join channels with a declared tolerance; inspect missingness and duplicate/out-of-order samples; avoid claiming precision that sampling cannot support. Use lap and sector timing as primary calibration targets, and use telemetry to check trends or constrain broad behavior. Do not treat arbitrary OpenF1 coordinates as a global geodetic frame.

**Phase:** Data/geometry contract and point-mass calibration phases.

### Reusing LGPL code or redistribution rights without reviewing the actual artifacts

**What goes wrong:** “Open source” is interpreted as permission to copy files or redistribute raw timing/geometry data without retaining notices or considering the underlying data provider's terms.

**Why it happens:** TUMFTM racetrack-database and laptime-simulation identify LGPL-3.0; OpenF1 describes itself as unofficial and says it does not claim ownership of F1 data or marks. The software/API license is not blanket permission over the source competition data. [TUMFTM track database](https://github.com/TUMFTM/racetrack-database), [TUMFTM lap-time simulation](https://github.com/TUMFTM/laptime-simulation), [OpenF1 project terms and disclaimer](https://openf1.org/)

**Prevention:** Continue the project's plan to reimplement methods rather than copy TUMFTM files; if any code or geometry file is adopted, preserve its license and attribution and meet LGPL conditions. Keep data source, retrieval date, and redistribution status attached to cached assets. Do not publish raw OpenF1 / FastF1 dumps; review source terms before adding public downloads or commercial use.

**Phase:** Track/data ingestion phase, and again before any public artifact or product release.

### Reproducibility assumed to mean bit-for-bit parity on Windows and Ubuntu

**What goes wrong:** Same seed is expected to yield byte-identical outputs across different Python/NumPy builds, CPUs, or BLAS/LAPACK libraries. Parallel reductions and linear algebra can differ in floating-point order and values, changing downstream stochastic paths.

**Why it happens:** NumPy documents strict conditions for Generator stream reproduction: same build, environment, machine, seed, and identical method sequence; different CPU and LAPACK can change results. [NumPy random compatibility policy](https://numpy.org/doc/stable/reference/random/compatibility.html), [NumPy Generator reference](https://numpy.org/doc/stable/reference/random/generator.html)

**Prevention:** Use explicit `np.random.Generator` and deterministic seeds as the project requires, pin Python and dependency versions, record platform / numerical library metadata in benchmark reports, and test Windows plus Ubuntu with scientifically justified numeric tolerances. Require exact same-environment replay for fixed golden artifacts; require behavioral/statistical parity, not undocumented bitwise identity, cross-platform.

**Phase:** Physics package and CI/integration phase. Add a Windows and Ubuntu CI matrix before closing M2.

### Physics work overwhelms the existing Monte Carlo budget

**What goes wrong:** The point-mass solver, Bayesian fit, or full thermal integration runs inside every simulated future lap and every Monte Carlo path. A per-lap model that is cheap once becomes prohibitive at 50,000 continuations.

**Prevention:** Fit/calibrate physics offline; precompute circuit pace maps or lookup arrays by feasible car/tire/fuel state; vectorize per-lap state evolution; keep Bayesian updates outside the inner race-path loop. Benchmark the complete `PaceModel` + simulator integration against the existing under-10-second/50,000-race constraint at representative race lengths and candidate strategies. Preserve cutoff-safe behavior if optional physics assets are unavailable.

**Phase:** Point-mass implementation phase and simulator integration/performance phase.

## Minor Pitfalls

### Track asset provenance disappears after preprocessing

**What goes wrong:** A smoothed/resampled track array no longer records source circuit layout, variant, coordinate transform, sample spacing, or algorithm.

**Prevention:** Store provenance, source/license, hash, units, circuit variant, and transformation parameters alongside every generated track asset; make the geometry digest part of calibration metadata.

**Phase:** Track data contract phase.

### Calibration report hides excluded laps and sample coverage

**What goes wrong:** Outlier filtering silently removes laps under SC/VSC, pit in/out, yellow flags, or missing telemetry and makes results appear representative of all race conditions.

**Prevention:** Define the clean-lap mask before fitting; report included and excluded counts by reason and race. Keep strategy-level validation separate, since excluding disrupted laps from pace calibration does not make the race simulator exempt from modeling those regimes.

**Phase:** Calibration and hybrid evaluation phases.

## Phase-Specific Warnings

| Phase topic | Likely pitfall | Mitigation |
|-------------|---------------|------------|
| Track data and geometry alignment | Arbitrary-origin, sparse GPS mapped directly to curvature or distance | Use versioned reference geometry; validate closure, distance, curvature, sector mapping, variants, and coordinate transforms before use |
| Point-mass lap model | Non-identifiable effective parameters and hidden compensation among drag, power, mass, grip, and driver/fuel effects | Fit a minimal parameterization with bounds/priors; inspect sensitivity and posterior correlation; hold out races/circuits; label approximation scope |
| Thermal / wear model | Hidden temperature and wear treated as measured; thermal/wear/fuel/driver/regime confounding | Explicitly mark latent state; propagate uncertainty; use cutoff-only filtering; check prior sensitivity and compare with simple wear baseline |
| Hybrid pace model | Residual double-counting or canceling physics; train/test contamination | Define residual ownership and as-of features; use fold-safe base predictions; maintain data-only Bayesian comparator |
| PAC-06 evaluation | Same-race/stint leakage, false independent sample size, post-hoc tuning | Lock a new held-out-stint protocol in advance; group by stint/race; train chronologically; race-cluster uncertainty; preserve M1 and 2026 disclosures |
| 2026 transfer analysis | Regulatory structural break pooled into old calibration | Version parameters by era and regulation issue; leave 2026 separate; disclose retrospective unblinding |
| Simulator integration / CI | Physics and latent-state loops exceed the 50,000-race budget or yield platform-sensitive results | Precompute pace maps, vectorize state updates, benchmark end-to-end, pin dependencies, test Windows/Ubuntu with deterministic seeds and documented tolerances |
| Publishing data/code artifacts | LGPL obligations or unsupported assumption that API software licensing covers raw race data | Preserve required notices for any adopted artifacts; reimplement referenced methods; retain provenance and avoid raw-data redistribution |

## Sources

- OpenF1, [API documentation](https://openf1.org/docs/) and [project terms / disclaimer](https://openf1.org/).
- TUMFTM, [racetrack-database](https://github.com/TUMFTM/racetrack-database) (geometry source, smoothing caveat, format, and LGPL-3.0) and [laptime-simulation](https://github.com/TUMFTM/laptime-simulation) (QSS implementation and LGPL-3.0).
- Rossi et al., [A Simple Mono-Dimensional Approach for Lap Time Optimisation](https://www.mdpi.com/2076-3417/10/4/1498); Oxford, [Optimal Control for a Formula One Car with Variable Parameters](https://ora.ox.ac.uk/objects/uuid:ce1a7106-0a2c-41af-8449-41541220809f/files/m776aa23411ad9d78c36f96620a0e0f0b).
- Cappello and Hoegh, [A State-Space Approach to Modeling Tire Degradation in Formula 1 Racing](https://journals.sagepub.com/doi/full/10.1177/22150218261446170).
- scikit-learn, [cross-validation guide](https://scikit-learn.org/stable/modules/cross_validation.html) and [data leakage guidance](https://scikit-learn.org/stable/common_pitfalls).
- NumPy, [random compatibility policy](https://numpy.org/doc/stable/reference/random/compatibility.html) and [Generator reference](https://numpy.org/doc/stable/reference/random/generator.html).
- FIA, [2026 regulation index](https://www.fia.com/regulation/category/2182) and [Section C Technical Regulations, Issue 21, 2026-10-19](https://api.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_21_-_2026-10-19.pdf).
- Project context: `DECISIONS.md` DEC-130 through DEC-132, `.planning/PROJECT.md`, and `.planning/M1-BASELINE.md`.
