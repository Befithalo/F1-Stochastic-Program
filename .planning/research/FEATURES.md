# Feature Landscape

**Domain:** Physics-grounded F1 lap pace and tire-state modeling using public race telemetry  
**Researched:** 2026-11-17  
**Confidence:** MEDIUM (primary technical papers and the OpenF1 endpoint documentation support the model structure and measurement boundaries; public telemetry cannot establish private vehicle/tire parameters)

## Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Point-mass, quasi-steady lap-time foundation | A physics milestone must explain how track curvature and vehicle limits create pace, rather than adding an opaque correction to lap times. Quasi-steady point-mass formulations are an established lower-complexity minimum-lap-time approach; TUMFTM publishes a Python quasi-steady lap-time simulator and race-specific F1 parameter examples. | High | Discretize track centerline by distance and curvature. Solve a speed envelope constrained by lateral grip and longitudinal acceleration/braking; include drag, downforce, power ceiling, and mass. Keep this as a pace prior/model, not a claim of full F1 car fidelity. Sources: [TUMFTM laptime-simulation](https://github.com/TUMFTM/laptime-simulation), [Online Time-Optimal Trajectory Planning on Three-Dimensional Race Tracks](https://arxiv.org/abs/2304.10954). |
| Circuit geometry and track-specific grip inputs | Curvature, gradient, and distance are necessary to compute cornering limits and lap time. | Medium | Start with versioned centerline distance/curvature and elevation only where trustworthy geometry exists. Record source and coordinate frame, and report geometry coverage. Do not silently synthesize exact racing lines or use future timing outcomes to tune track geometry. Public TUM track databases are useful references, with per-dataset license and provenance checks. |
| Fuel mass effect across a race | Fuel load changes vehicle mass, making lap-time comparisons across stint and race age confounded. | Medium | Use scheduled race distance / cutoff lap and a declared fuel-burn prior to propagate fuel mass; fuel mass itself is not published in the public race feed. Estimate only a low-dimensional fuel-time coefficient if the data support it, and label initial fuel and burn rate as assumptions. Never call fuel-corrected timing an observed measurement. |
| Tire temperature and wear state evolution | Tire temperature affects grip and wear, while energy and abrasion contribute to degradation. Thermal models distinguish fast tread response from slower carcass heat storage; treating tire age alone as the physical state misses this dynamic. | High | A compact two-node tread/carcass energy balance is a reasonable research default, coupled to a bounded temperature-to-grip curve and an accumulated wear state. The literature models frictional heating, convection, conduction and load/force effects, and fits free parameters against tire temperature telemetry unavailable in the public feed. Therefore calibrate only what public lap-time responses identify, expose the rest as priors/assumptions, and propagate broad state uncertainty. Source: [Optimal Tyre Management of a Formula One Car](https://ifatwww.et.uni-magdeburg.de/ifac2020/media/pdfs/0335.pdf). |
| Hybrid PaceModel preserves the M1 interface | M2 must plug into the shipped strategy system without rewriting the simulator or policy. | Medium | Use physics-derived lap pace as the structured baseline; let the existing Bayesian model estimate a regularized residual conditional on cutoff-visible covariates. Return a predictive distribution, including residual and latent-state uncertainty, through the existing `PaceModel` contract. Keep data-only Bayesian and linear models runnable as paired controls. |
| Compound/stint reset semantics | A new set changes tire age and thermal starting conditions; pit events create a state reset. | Medium | Derive stint boundaries incrementally from visible pit/out-lap/compound rows. At a pit stop, reset wear to the declared new-set prior and model thermal state as uncertain rather than assuming a perfectly hot or cold tire. Public compound labels and tire age are observable, but they do not reveal a full tire condition measurement. |
| Uncertainty and assumption reporting | A point estimate hides the fact that fuel, tire thermal state and vehicle parameters are latent. | Medium | Return pace mean and spread, plus a compact provenance/assumption record: fitted versus fixed parameter, data support, latent state interval, and fallback use. Preserve finite, inspectable output when the track/covariate coverage is weak. |

## Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Physics base plus Bayesian residual with fallback | Combines interpretable track/vehicle structure with adaptation to driver, car, conditions and setup mismatch. | High | Residual training must be regularized toward zero, be fitted on earlier-only data, and retain the data-only Bayesian comparison. This is especially relevant because M1's locked Bayesian gate failed: MAE 0.538745 s vs linear 0.364033 s. Synthetic parameter recovery is not proof of real-data gains. Sources: [M1 baseline](../M1-BASELINE.md), [A State-Space Approach to Modeling Tire Degradation in Formula 1 Racing](https://arxiv.org/abs/2512.00640). |
| Energy-informed degradation proxy | Sliding/tyre energy is more physically meaningful than age alone and is an active strategy research signal. | High | Estimate a proxy from available speed, throttle, binary brake, gear, DRS, track curvature and modeled vehicle forces. Clearly label it proxy energy: the public data do not disclose tire forces/slip, tire temperature, pressure or ERS deployment. The Mercedes/Imperial study forecasts energy from proprietary team telemetry, so its predictive result cannot be reproduced from the public feature set as-is. Sources: [Explainable Time Series Prediction of Tyre Energy in Formula One Race Strategy](https://arxiv.org/abs/2501.04067), [OpenF1 car-data schema](https://openf1.org/docs/). |
| Held-out-stint gate before M3 | Prevents model complexity from advancing on synthetic success or in-sample fit alone. | Medium | Lock a new race/stint-grouped holdout before fitting/tuning, use identical finite next-lap targets and cutoff features for hybrid and data-only Bayesian baselines, and require hybrid MAE improvement. Recommended minimum: at least 500 paired targets and at least 15% lower MAE; additionally publish paired uncertainty intervals and calibration/coverage. A failed gate remains failed—do not retune or rescore that lock. M3 starts only after the gate passes. This is a recommended M2 bar, not a previously measured result. |
| Synthetic recovery suite with known physics and residual truth | Separates implementation correctness and parameter identifiability from real-world predictive skill. | Medium | Generate synthetic tracks/races with known curvature, aero/power/grip, fuel-burn coefficient, thermal parameters, tire-energy/wear process and Bayesian residual. Assert sensible parameter recovery within predeclared tolerances, interval coverage, correct reset behavior, and no response to future-only perturbations. Include deliberately unidentifiable cases and assert the fitter widens uncertainty or reports non-identifiability instead of inventing precision. |
| As-of replay with feature and fit audit trail | Makes the hybrid usable in the existing lap-by-lap recommendation loop and auditable after the fact. | Medium | At each cutoff, use only rows visible by that cutoff and prior completed races. Save fit sample IDs or a stable digest, feature cutoff, model/config version, seed, fit diagnostics, and missingness. A future-row scramble must leave the current prediction unchanged. |

## Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Claiming measured tire temperature, pressure, tire force/slip, fuel load, or ERS energy from OpenF1/FastF1 public feeds | These feeds document speed, throttle, brake state, RPM, gear and DRS at roughly 3.7 Hz; those variables do not directly expose the private thermal and energy states needed for a team-grade tire model. | Separate directly observed fields from modeled latent states and derived proxies in names, docs, serialized state and reports. Use explicit assumptions and uncertainty. Sources: [OpenF1 documentation](https://openf1.org/docs/), [FIA technical regulations telemetry provision](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss11_-_2025-02-26.pdf). |
| Fitting a high-dimensional tire/aero model from public lap time alone | Track, fuel, driver management, traffic, setup, weather and latent tire state are confounded. Public data cannot uniquely identify a full force/slip and heat model. A recent public-data state-space study notes compound differences were not statistically distinct in its case study. | Start with a small, physically constrained parameter set; fix published/engineering priors where necessary; fit only identifiable scale terms; use hierarchical shrinkage; report sensitivity and identifiability. Source: [Cappello & Hoegh, 2025](https://arxiv.org/abs/2512.00640). |
| Treating synthetic recovery, in-sample fit or a single race as PAC-06 success | Parameter recovery checks whether known synthetic truth can be recovered under the generator; it does not show improved real race prediction. | Keep synthetic tests and the registered real held-out-stint gate separate and report each denominator/result. |
| Updating the model with full-race stint lengths, final pit sequence, classification, or future telemetry | These fields reveal information unavailable at the decision cutoff and can make race replay appear unrealistically accurate. | Route features through the existing single as-of accessor; rebuild stints from rows visible so far; keep the results door separate and open only during locked scoring after all predictions are fixed. |
| Per-lap random cross-validation across the same stint/race | Adjacent laps share latent state and leak driver/car/track context between train and validation. | Group the split by complete stints or races, with chronological training history and a pre-registered holdout. Evaluate identical target rows. |
| Unconstrained residual model that cancels physics | A flexible correction can memorize track/cutoff quirks and makes the physics base decorative. | Shrink residuals, limit features to cutoff-known fields, compare against data-only Bayesian and physics-only controls, and require ablations to show which layer helps. |
| Precise team-performance or strategy superiority claims from the public-data pace model | The feed is lower fidelity and omits team-private signals; strategy calls are also constrained by traffic, rivals and information unavailable to replay. | Describe this as an open-data decision-support model; publish limitations and compare predictions under the same locked sample, not as a claim of team-equivalent fidelity. |

## Feature Dependencies

```text
Track geometry + provenance
  → point-mass speed envelope and physics lap-time map
  → fuel/temperature/wear latent-state propagation
  → physics PaceModel distribution
  → Bayesian residual layer
  → held-out-stint paired score and M3 gate

As-of data access + cutoff-visible telemetry
  → safe feature construction for every stage above

Synthetic race/track generator with known truth
  → parameter recovery, interval coverage, reset and future-scramble checks
```

The as-of boundary and reproducible seed plumbing are prerequisites, not a final evaluation add-on. Build synthetic truth tests alongside each new state equation, then lock the real-data gate before any held-out scoring.

## Observability: Fit vs Assume

| Quantity | Public evidence | Recommended treatment |
|----------|----------------|-----------------------|
| Lap times, compound labels, visible tire age/stint starts, weather, speed/throttle/brake-on-off/gear/RPM/DRS | Directly available in documented public timing/telemetry feeds, with known sampling/missingness. | Fit and validate only on cutoff-visible observations; preserve missingness and timestamp provenance. |
| Track distance and curvature | Available only where a track-geometry source has a usable centerline; source coverage and coordinate quality vary. | Version and validate the geometry; fit circuit-level pace offset or scale only if needed. Treat exact racing line and local grip as assumptions. |
| Fuel mass and burn rate | No per-car public fuel-load measurement. Lap, distance and schedule constrain possible fuel burn but do not identify it by themselves. | Set a declared prior/burn-rate assumption; fit one low-dimensional fuel-time coefficient only against grouped historical data with uncertainty. |
| Tread/carcass temperature and tire pressure | Not present in the public telemetry schema. | Hidden state initialized from compound/ambient/track conditions with a broad prior; temperatures are modeled outputs, never reported as sensed. |
| Tire forces, slip velocity, per-wheel energy, wear depth | Not directly public; energy research uses proprietary telemetry and model-derived forces. | Use model-based proxy features and weakly identified latent parameters; constrain and label them. Avoid parameter-level claims of truth. |
| Effective power, drag, downforce, grip | Not directly published per car/race in public timing feeds; telemetry response under throttle/brake can provide indirect evidence, confounded by setup, deployment, DRS, traffic and driver control. | Parameterize per era/team-class with priors and estimate a small effective pace scale where data supports it; use sensitivity analysis rather than claiming true component values. |

## MVP Recommendation

Prioritize:

1. A deterministic point-mass lap map based on sourced track distance/curvature, effective power, drag/downforce and grip bounds, with an explicit fuel-mass assumption.
2. A compact latent tire thermal/wear state model whose temperature and energy states are explicitly labeled unobserved; start with a two-node thermal state only if parameters remain low-dimensional, otherwise use a one-node state for the MVP.
3. A `PaceModel` hybrid that adds a shrunk Bayesian residual over physics and passes the synthetic recovery suite plus a newly locked, race/stint-grouped real holdout with at least 500 paired targets and at least 15% lower next-lap MAE than the data-only Bayesian pace model.

Defer: per-wheel high-fidelity vehicle dynamics, full thermal telemetry reconstruction, learned energy forecasting that presumes private sensor features, and any M3 RL/strategy learner until PAC-06 passes. Report calibration/interval coverage and per-race denominators with MAE; do not claim M1 strategy metrics improved unless the strategy layer is separately reevaluated against the locked M1 baseline contract.

## Sources

- [OpenF1 API documentation](https://openf1.org/docs/) — official project schema for public car telemetry, sampling rate and historical access.
- [TUMFTM laptime-simulation](https://github.com/TUMFTM/laptime-simulation) — primary open-source quasi-steady lap simulation reference.
- [Online Time-Optimal Trajectory Planning on Three-Dimensional Race Tracks](https://arxiv.org/abs/2304.10954) — primary research on point-mass, quasi-steady race-track planning with acceleration limits.
- [Optimal Tyre Management of a Formula One Car](https://ifatwww.et.uni-magdeburg.de/ifac2020/media/pdfs/0335.pdf) — primary technical paper describing tread/carcass thermal dynamics, frictional heating and wear modeling; its fit used temperature telemetry unavailable in public feeds.
- [Explainable Time Series Prediction of Tyre Energy in Formula One Race Strategy](https://arxiv.org/abs/2501.04067) — primary research using Mercedes-AMG team telemetry for tire-energy forecasting; informs the value of energy features and public-data limitations.
- [A State-Space Approach to Modeling Tire Degradation in Formula 1 Racing](https://arxiv.org/abs/2512.00640) — primary public FastF1 timing-data study; useful precedent for latent tire pace and pit resets, with results limited to a single-race case study.
- [FIA 2026 Formula One Technical Regulations, Section C](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss11_-_2025-02-26.pdf) — primary regulatory evidence that teams transfer telemetry to FIA; supports distinction between team/FIA telemetry and what public OpenF1 exposes.
- Project constraints: [PROJECT.md](../PROJECT.md), [DECISIONS.md](../../DECISIONS.md) DEC-130–132, [M1-BASELINE.md](../M1-BASELINE.md), and [BUILD_PLAN.md](../../F1%20Docs/BUILD_PLAN.md).
