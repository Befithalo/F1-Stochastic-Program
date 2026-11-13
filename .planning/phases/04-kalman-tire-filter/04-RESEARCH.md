# Phase 4: Kalman Tire Filter - Research

**Researched:** 2026-11-12
**Domain:** Recursive Bayesian (Kalman) estimation of a per-stint tyre-wear rate; wiring into an existing Numba Monte Carlo simulator
**Confidence:** HIGH on the feasibility maths and the integration design (both computed or read from code in this session); LOW on every generic prior value (no authoritative source exists)

<user_constraints>
## User Constraints (from CONTEXT.md)

CONTEXT.md decisions D-01..D-16 are locked ("Claude's pick", owner may override). Copied in short form; the full text is in `04-CONTEXT.md`.

### Locked Decisions
- D-01 One filter per car per stint; state [pace level, wear rate s/lap]; observation = one fuel-corrected clean lap; transition level += rate, rate constant; reports the wear rate.
- D-02 No process noise by default (exact recursive Bayesian linear regression); `q` parameter exists; `q > 0` must widen the band; DEC entry for the limitation (no cliff, no thermal).
- D-03 Reset at every stop: rate prior restarts from the compound prior, level diffuse, tyre age from stint data.
- D-04 Own NumPy implementation, no new dependency (no filterpy), Joseph-form covariance update, docstring states the equations.
- D-05 Rate prior = field-level compound rate from the as-of Phase 2 fit when identified, else a documented wide generic per-compound prior; labelled "prior only".
- D-06 Fuel correction from the as-of fit when identified, else a documented fuel prior with SD; the fuel SD must reach the reported wear SD; say plainly when fuel is prior-only.
- D-07 Observation noise = as-of Phase 2 `sigma_s` when identified, else a documented default (pooled as-of residual allowed). Never use laps after the cutoff.
- D-08 Only clean laps (`f1si.laps.fade_reason`) update; skipped laps run predict only; innovation outlier gate (about 3 SD) skips and counts; research decides when the gate switches on.
- D-09 Filter receives a `RaceSnapshot` or plain arrays, never the accessor; register every new snapshot-reading public function in `tests/guards/consumers.py`.
- D-10 `SyntheticRaceSpec` gains optional per-driver wear-rate deviations exposed in `SyntheticTruth`; default none, existing fixtures byte-identical.
- D-11 Recovery test: at least 1,000 seeded synthetic stints, truth drawn from the prior, fuel and noise known; MAE of relative error at stint lap 8 <= 10%; 95% coverage inside a binomial 99.9% band; posterior SD non-increasing on measured laps; end-to-end variant with prior fuel (coverage must hold, error reported only).
- D-12 Feasibility first; keep the test meaningful (prior alone at lap 0 must miss 10%); if not attainable honestly, say so with the achievable number; do not tune noise, prior or metric to pass.
- D-13 `build_race_state` gains an optional filter result; `CarState.wear_source` ("fit" | "filter", default "fit"); JSON backward compatible.
- D-14 Simulator: a "filter" car uses its own rate and SD for laps on its current tyres (per-car draw from a NEW spawned stream; no change to the Sobol layout or any Phase 3 draw); later stints keep the compound fit; "fit" cars byte-identical.
- D-15 CLI `f1si wear-filter bahrain-2023 --driver ALO [--lap N]` plus PNG `reports/wear-filter-<slug>-<DRV>.png` (Figure API, no pyplot, prepare/build/render split).
- D-16 `docs/explained/phase-04.md`, README needles, DEC entries from DEC-088, bump `MIN_ENTRIES` (87), every new module in the explainer tour.

### Claude's Discretion
- Module layout (for example `f1si/pace/kalman.py`, CLI in `cli.py`, plot in `plots/wear_filter.py`).
- Exact generic prior values and the gate threshold, within D-05 and D-08, logged in DEC entries.
- Whether all cars are filtered in one vectorized pass or one at a time.
- Plot styling.

### Deferred Ideas (OUT OF SCOPE)
- Tyre cliff / non-linear wear; hierarchical pooling across cars (Phase 7); priors learned from earlier races; adaptive noise and traffic/dirty-air models; tyre temperature physics; full live replay (Phase 5).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PAC-03 | Kalman filter estimates hidden tyre wear lap by lap with an uncertainty band | 3-state Joseph-form filter (level, rate, fuel deviation); incremental `update` plus batch; band = marginal posterior SD of the rate; section "Architecture Patterns" |
| PAC-04 | Synthetic recovery: within 10% of true wear by lap 8; 95% intervals cover about 95% | Feasibility section: coverage target is attainable (verified 0.95 +/- MC error); the 10% accuracy target is NOT attainable at honest noise (table below). Planner must raise it with the owner. |
</phase_requirements>

## Summary

**Feasibility verdict (D-12): the PAC-04 accuracy target (mean absolute relative error of the wear-rate estimate <= 10% at stint lap 8, i.e. 7 measured laps) is not attainable at honest noise.** With a diffuse level the only information about the rate is the within-stint spread of ages, `Sxx = K(K^2-1)/12 = 28` for K = 7 (ages 2..8). At the generator default noise 0.15 s the data-only SD of the slope is `0.15/sqrt(28) = 0.0283 s/lap`, against true rates of 0.04 to 0.12 s/lap. Even with fuel known exactly and a wide prior (SD = half the mean) the filter's expected relative error at lap 8 is about 19% (SOFT 0.12), 28% (MEDIUM 0.07) and 35% (HARD 0.04); at the Bahrain 2023 noise (0.28 s as-of lap 14, 0.48 s at race end) it is worse. With a realistic fuel prior (SD 0.02 s/lap) there is an irreducible floor, because inside a stint the data identify only (rate + fuel): no number of laps gets below 10% for MEDIUM or HARD. The 95% coverage target IS attainable (an exact Bayesian filter on correctly specified synthetic data covers 0.95; verified by Monte Carlo). The planner should present the owner with the achievable numbers below and a choice of restated target; it must not tune noise, prior or metric to pass.

**Primary recommendation:** Build the filter as a 3-state Joseph-form Kalman filter (level, rate, fuel deviation; the fuel deviation is a third state with a fixed prior so the fuel SD flows into the rate SD exactly, which satisfies D-06 without ad hoc quadrature). Gate coverage (PAC-04 part 2) and narrowing (criterion 1) as specified; gate accuracy (PAC-04 part 1) only after the owner restates it (options listed under Open Questions). Wire simulator integration through "virtual compound" columns so `kernel.py` is not touched and every Phase 3 test stays byte-identical.

## Architectural Responsibility Map

This is a single-process Python library; the "tiers" are modules.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Kalman math (predict/update/Joseph, gate) | `f1si.pace.kalman` (pure NumPy, plain arrays in/out) | — | No data access; testable with arrays; incremental + batch |
| Turning a snapshot into per-stint filter inputs (clean-lap rule, as-of priors, fuel/noise sources) | `f1si.pace.kalman` snapshot adapter (consumes `RaceSnapshot` + `LinearPaceFit`) | `f1si.laps.fade_reason`, `f1si.pace.linear` | As-of discipline: only a snapshot is read; registered in `tests/guards/consumers.py` |
| Putting wear mean/SD into `RaceState` | `f1si.state.build_race_state` (optional arg) | — | D-13; single builder (Phase 2 D-14) |
| Using per-car current-stint wear in the simulation | `f1si.sim.numpy_backend` (table building) | `f1si.sim.draws` (new stream) | Kernel stays unchanged (virtual compound columns) |
| Synthetic truth with per-driver wear deviations | `f1si.synthetic.generator` | — | D-10, defaulted fields |
| Showing the narrowing band | `f1si.plots.wear_filter` + `cli.py` | — | D-15, copy `plots/wear.py` |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| NumPy | already pinned in repo | Filter matrices, Joseph update, MC tests | D-04: about 30 lines, no new dependency |
| SciPy | already pinned | `scipy.stats.norm` / `binom` for coverage band and `ppf` | Already used by sim/draws |
| Numba | already pinned | Kernel (UNCHANGED in this phase if the virtual-compound design is used) | Existing |
| matplotlib | already pinned | PNG via `Figure` API | Existing pattern `plots/wear.py` |
| pytest + hypothesis | already pinned | Tests | Existing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Own Kalman | filterpy | Unmaintained, untyped (D-04 locks own code) |
| 3-state with fuel deviation | 2-state + fuel SD added in quadrature | Quadrature is simpler but over-widens (SD can exceed the prior SD) and the mean does not use the fuel prior correctly; 3-state is exact and still ~35 lines. Recommended: 3-state. If the owner insists on D-01's literal 2-element state, quadrature is the fallback (coverage then >= 95%, conservative). |

**Installation:** none. No new packages.

## Package Legitimacy Audit

No external packages are installed in this phase (own NumPy implementation, D-04). Audit not applicable.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Feasibility (D-12): computed in this session

Setup. Stint lap 8 = 7 measured laps at tyre ages 2..8 (out-lap age 1 skipped; for the race's first stint lap 1 is skipped). State [level (diffuse, sd 1e3), rate ~ N(mu, tau^2), fuel deviation g ~ N(0, sf^2)]. Observation `y = level + (rate + g) * d + noise` with `d` = laps since the first measured lap (in a stint, tyre age and lap number advance one-for-one, so the fuel deviation and the rate share one column; this is why fuel and wear are not separable inside a stint). Truth rate drawn from the prior; relative error `|rate_hat - rate| / rate`; 60,000 to 200,000 simulated stints per cell. Scripts: `scratchpad/feas.py`, `feas2.py`, `feas3.py` (session-local; the planner's Wave 0 test reproduces the key cells).

**Closed forms [VERIFIED: derivation, matched to the Monte Carlo to 3 decimals]**
- Slope information from K measured laps with a diffuse level: `Sxx = K(K^2-1)/12` (K = 7 gives 28); data-only slope SD `= sigma/sqrt(Sxx)`.
- Fuel known (sf = 0): `Var_post(rate) = (1/tau^2 + Sxx/sigma^2)^-1`.
- Fuel uncertain: `Var_post(rate) = tau^2 - tau^4 / (tau^2 + sf^2 + sigma^2/Sxx)`. Floor as K goes to infinity: `tau^2 sf^2 / (tau^2 + sf^2)`.
- For a Gaussian error the mean absolute error is `sqrt(2/pi) * SD_post = 0.80 * SD_post`; relative error is that over the true rate (slightly larger because of the 1/rate convexity).

**Posterior SD of the wear rate at stint lap 8 (s/lap)** [VERIFIED: analytic + MC]

| sigma (s) | sf (s/lap) | tau = 0.01 | tau = 0.02 | tau = 0.03 | tau = 0.05 | data-only SD |
|-----------|------------|-----------|-----------|-----------|-----------|--------------|
| 0.15 (generator default) | 0 | 0.0094 | 0.0163 | 0.0206 | 0.0247 | 0.0283 |
| 0.15 | 0.02 | 0.0096 | 0.0173 | 0.0227 | 0.0285 | 0.0283 |
| 0.28 (Bahrain 2023, Phase 2 `sigma_s` as of lap 14) | 0 | 0.0098 | 0.0187 | 0.0261 | 0.0363 | 0.0529 |
| 0.48 (Bahrain 2023 `sigma_s`, whole race) | 0 | 0.0099 | 0.0195 | 0.0285 | 0.0438 | 0.0907 |

To meet 10% mean relative error the posterior SD must be below roughly 0.0125 (SOFT 0.12), 0.0088 (MEDIUM 0.07) and 0.0050 (HARD 0.04). Every cell above with a prior wide enough to make the prior alone miss the target exceeds those bounds.

**Mean absolute relative error of the rate estimate at stint lap 8, truth ~ prior** [VERIFIED: MC, filter = the Joseph-form code above]

| Compound (true mean) | Prior SD tau | sigma | Fuel | Prior alone (lap 0) | Posterior at lap 8 | 95% coverage |
|----------------------|-------------|-------|------|--------------------|--------------------|--------------|
| SOFT 0.12 | 0.02 | 0.15 | known | 0.14 | **0.11** | 0.950 |
| SOFT 0.12 | 0.06 (0.5 mu) | 0.15 | known | 0.43 | 0.19 | 0.95 |
| SOFT 0.12 | 0.06 | 0.15 | sf 0.02 | 0.43 | 0.22 | 0.956 |
| SOFT 0.12 | 0.02 | 0.28 | known | 0.14 | 0.13 | 0.950 |
| MEDIUM 0.07 | 0.02 | 0.15 | known | 0.27 | 0.21 | 0.954 |
| MEDIUM 0.07 | 0.035 (0.5 mu) | 0.15 | known | 0.43 | 0.28 | 0.95 |
| MEDIUM 0.07 | 0.035 | 0.15 | sf 0.02 | 0.43 | 0.31 | 0.963 |
| MEDIUM 0.07 | 0.02 | 0.28 | known | 0.27 | 0.25 | 0.954 |
| HARD 0.04 | 0.02 | 0.15 | known | 0.43 | 0.35 | 0.965 |
| HARD 0.04 | 0.02 | 0.15 | sf 0.02 | 0.43 | 0.37 | 0.969 |
| HARD 0.04 | 0.02 | 0.28 | known | 0.43 | 0.40 | 0.972 |

(Coverage above 0.95 in some rows is an artefact of truncating the drawn truth to rate > 0.25 mu, which makes the prior slightly too wide for the truncated population. Draw the test truth from the exact stated prior, or accept the 99.9% binomial band; all rows are inside [0.927, 0.973] for N = 1000 except HARD with sigma 0.28.)

Best case anywhere in the table is SOFT, narrow prior, fuel known, generator noise: 11% (target 10%), and there the prior alone is already at 14%, so the data barely does any work. No honest cell has "prior misses at lap 0, posterior meets at lap 8".

**Measured laps needed for 10% (fuel known exactly, tau = 0.5 mu)** [VERIFIED: MC grid, first K in {7,10,12,15,20,25,30,40} with error <= 10%]

| Compound | sigma = 0.15 | sigma = 0.05 |
|----------|--------------|--------------|
| SOFT 0.12 | 12 laps (stint lap 13) | 7 (stint lap 8) |
| MEDIUM 0.07 | 20 laps | 10 laps |
| HARD 0.04 | 25 laps | 12 laps |

With fuel prior SD 0.02 s/lap (the realistic case) no K reaches 10% (floor above) for MEDIUM or HARD at sigma 0.15 or 0.05.

**Error at fixed sigma, K = 7, fuel known, tau = 0.5 mu** (sigma needed for 10%): SOFT passes at sigma <= 0.06 (0.07 at 0.05); MEDIUM needs sigma <= about 0.04 (0.073 at 0.03, 0.12 at 0.05); HARD needs sigma <= about 0.025 (0.085 at 0.02, 0.124 at 0.03).

**Real Bahrain 2023 noise** [VERIFIED: ran the Phase 2 fit on `data/f1si.duckdb`]: `sigma_s` is 0.28 s as of lap 14, 0.41 at lap 18, 0.46 at lap 20 to 40, 0.48 at race end. A hindsight within-stint scatter after removing a per-stint line, restricted to clean laps, gives a robust (MAD) noise of about 0.23 s; the pooled OLS value is 0.72 s because a few stints contain outliers. So the honest noise for real data is 0.23 to 0.48 s, 1.5 to 3 times the generator default. Real Bahrain stints will therefore have a wide band over the first 8 laps (SD 0.02 to 0.04 s/lap at lap 8 for a prior SD of 0.03 to 0.05), which is exactly the "honest uncertainty band" of the roadmap goal, but not a 10% estimate.

**Informative level prior does not rescue it** [VERIFIED: MC, sigma 0.15, sf 0.02, tau 0.5 mu, K = 7]: level prior SD 0.1 s gives 18.5% / 27% / 35% (SOFT/MEDIUM/HARD), 0.3 s gives 21% / 30% / 37%, diffuse gives 22% / 31% / 37%. Not a lever, and D-03 is right that the level should stay diffuse.

**Gate effect on coverage** [VERIFIED: MC, K = 12, MEDIUM, 6000 stints per cell]: clean data, gate off 0.958 coverage, gate on (3 SD, from 3rd measured lap) 0.959: the gate costs nothing on clean Gaussian data. With 5% contaminated laps (+1.0 s): gate off 0.900, gate on 0.926. The gate helps but does not restore 95% under contamination; real traffic laps will make the real-data band somewhat over-confident. State this in the docs rather than hide it.

### What the planner should tell the owner (requirement risk for PAC-04)
1. Coverage (95% within the binomial band), narrowing (SD non-increasing) and "the band narrows on a real stint" ARE achievable and should be gated.
2. "Within 10% by lap 8" is NOT achievable for the rate on synthetic data at noise >= 0.15 s. Honest achievable numbers at lap 8 (sigma 0.15, fuel known, prior wide enough to matter): SOFT about 19%, MEDIUM about 28%, HARD about 35%; with a realistic fuel prior 22% / 31% / 37%.
3. Owner options (research does not choose): (a) restate PAC-04 as "within 10% by stint lap 13 for SOFT" (12 measured laps) and per-compound laps (MEDIUM 20, HARD 25) at sigma 0.15; (b) restate as "posterior SD at lap 8 is less than half the prior SD" (an information criterion; passes at sigma 0.15 for tau about 0.03: 0.0206 vs 0.03 is only 31% narrower, so even this needs tau <= about 0.05 and a threshold of one third narrower; planner should compute the threshold with the Wave 0 script); (c) change the target quantity to the filter's one-step-ahead lap-time prediction error (a different, achievable quantity, but then it is not "wear"); (d) keep 10% and run the test at sigma <= 0.05 s, but that is a different, noise-tuned scenario and violates D-12 if used to claim the real target. Until the owner chooses, write the accuracy test as a reporting test (prints the table, asserts only monotone improvement from the prior and `error(lap 8) < error(lap 0)`), and gate coverage and narrowing.

## Architecture Patterns

### System Architecture Diagram

```
RaceSnapshot (as-of cutoff) ---------------------------------+
   |                                                          |
   |  fit_linear_pace(snapshot) -> LinearPaceFit              |
   |        (identified? fuel, fuel_se, wear[c], se, sigma_s) |
   v                                                          v
 per-stint inputs  <---- priors resolver (fit if identified & sane, else generic) 
   |  (driver, stint, compound, ages[], lap_no[], time[], reason[])
   |   reason from f1si.laps.fade_reason (lap1/pit in/pit out/SC)
   v
 WearFilter.reset(compound prior, fuel prior, sigma)   # once per stint (D-03)
   |
   +-- for each lap in stint, in order:
   |      predict (age += 1; q adds to rate variance only if q > 0)
   |      usable? -- no --> skip (count reason), band does not shrink
   |      gate? (>= 3 measured laps, |innov| > 3 sqrt(S)) -- yes --> skip (count "gate")
   |      update (gain, Joseph form) --> posterior (level, rate, g) + P
   v
 WearEstimate(lap, age, used/skip reason, rate_mean, rate_sd_incl_fuel, 95% interval, source flags)
   |
   +--> build_race_state(..., wear_filter=results)  -> CarState.wear_rate / wear_sd / wear_source="filter"
   |        --> NumpySimulator: virtual compound column for the car's current stint
   +--> CLI wear-filter: table + PNG (band vs race lap, stint boundaries, hindsight dashed)
```

### Recommended Project Structure
```
src/f1si/pace/kalman.py        # WearFilter (arrays), priors, snapshot adapter, StintEstimate dataclasses
src/f1si/plots/wear_filter.py  # prepare_wear_filter_data / build_wear_filter_figure / render_wear_filter_plot
src/f1si/state.py              # +wear_source, build_race_state(..., wear_filter=None)
src/f1si/sim/numpy_backend.py  # virtual compound columns + new stream (no kernel.py change)
src/f1si/sim/draws.py          # +car_wear_stream helper (no change to make_streams)
src/f1si/synthetic/generator.py# +per-driver wear deviation fields (default empty)
tests/pace/test_kalman_*.py    # recovery, coverage, narrowing, q>0, gate, incremental==batch
tests/guards/consumers.py      # register kalman consumers; add f1si.pace.kalman, f1si.plots.wear_filter to DESIGNATED_MODULES
```

### Pattern 1: Three-state Joseph-form filter, ages re-centred at the first measured lap
State `x = [level, rate, g]`, `P` its covariance. `d_k` = laps since the first measured lap of the stint (so the diffuse level is the pace at that lap; re-centring avoids ill-conditioning when a stint starts at age 17). Observation row `H_k = [1, d_k, d_k]`: `y_k = level + (rate + g) d_k + noise`, `y_k` already has the prior-mean fuel effect removed (`y = t - fuel_mean * (lap-1)`; the `g` state is the residual fuel error). Prior: `level ~ N(y_first, 1e3^2)` (diffuse), `rate ~ N(mu_c, tau^2)`, `g ~ N(0, sf^2)`. With zero process noise and a skipped lap, "predict" is the identity on the state (the observation row carries the age), so a skipped lap only advances `d`. If `q > 0`, add `q^2 * dt` to `P[1,1]` per lap.
```python
# Source: standard Kalman recursion, Joseph form (e.g. Bar-Shalom et al., Estimation with Applications to Tracking and Navigation, sec. 5.2); verified against closed form in this research
def update(x, P, h, y, r):            # h: (3,), r = sigma**2
    s = h @ P @ h + r                 # innovation variance
    k = P @ h / s                     # gain
    innov = y - h @ x
    x = x + k * innov
    a = np.eye(3) - np.outer(k, h)
    P = a @ P @ a.T + r * np.outer(k, k)      # Joseph form
    return x, 0.5 * (P + P.T), innov, s       # symmetrise
```
Reported wear SD = `sqrt(P[1,1])` (marginal, includes the fuel deviation, satisfies D-06). Interval = rate +/- 1.96 SD (`CI_Z` from `f1si.pace.linear`).

### Pattern 2: Gate rule (D-08, decided here)
Compute `s` from the filter itself. Gate = skip when `abs(innov) > 3.0 * sqrt(s)` AND at least 3 laps have been used in this stint. Why: with a diffuse level the first innovation variance is about 1e6 so the 3-SD test never fires (harmless), and after only 1 or 2 used laps `s` still contains the diffuse level so a rejection there would be arbitrary and irreversible. Add a lock-out guard: never reject two laps in a row (the second is accepted), so a real step change cannot freeze the filter. Count gate rejections in the result. Verified harmless on clean data (coverage 0.958 vs 0.959) and helpful on contaminated data (0.900 to 0.926).

### Pattern 3: Priors resolver (D-05/D-06/D-07), values and sources
| Quantity | Identified (as-of fit) | Not identified (generic) | Source status |
|----------|-----------------------|--------------------------|---------------|
| Rate mean | `fit.wear_rate(compound)` | SOFT 0.10, MEDIUM 0.08, HARD 0.06 s/lap | generic values [ASSUMED] |
| Rate prior SD | `sqrt(se^2 + tau_car^2)`, `tau_car = 0.03` | 0.05 | `tau_car` [ASSUMED], see below |
| Fuel mean (in-stint trend incl. track evolution) | `fit.fuel_effect` | -0.05 s/lap | generic [ASSUMED] |
| Fuel SD | `sqrt(fuel_se^2 + 0.02^2)` | 0.025 | [ASSUMED] |
| Noise sigma | `fit.report.sigma_s` | 0.30 s | [ASSUMED]; Bahrain 0.28 to 0.48 [VERIFIED: local cache] |

Evidence and honesty for the numbers:
- No authoritative source gives per-compound degradation in s/lap. A web search found only Pirelli statements that degradation depends strongly on track and temperature and that compounds can degrade similarly (2026 Barcelona: up to 0.2 to 0.3 s per lap, "pretty similar across compounds") [CITED: formula1.com Barcelona-Catalunya GP preview; planetf1 Madring strategy article], a hobby project's assumed inputs (0.085 / 0.050 / 0.028 s/lap, not measured) [LOW], and the repo's own synthetic default 0.12 / 0.07 / 0.04.
- The local data contradict a compound-ordered prior: Bahrain 2023 Phase 2 whole-race fit gives HARD 0.121 and SOFT 0.125 s/lap (MEDIUM not fitted) [VERIFIED: local cache]. So a SOFT >> HARD ordering would mislead; keep the generic means close together and the SD wide (0.05, so the interval 0.0 to 0.2 contains every value seen). The default synthetic values are inside the 2 SD range for all three.
- Fuel: Phase 2 measured -0.078 s/lap at Bahrain 2023 including track evolution [VERIFIED]; `FUEL_SANITY_RANGE` in the repo is -0.06 to -0.03 (approximate literature); per-kg forum estimates vary roughly 4x (0.033 to 0.133 s per kg, average about 0.067 per kg) at about 1.7 to 2.3 kg of fuel per lap [CITED: f1technical.net forum thread via web search; forum-grade, LOW]. A prior of -0.05 +/- 0.025 spans -0.10 to 0.0 at 2 SD and contains both the literature range and the Bahrain value. Because the in-stint trend includes track evolution, a literature-only fuel value understates it: Bahrain's -0.078 vs a -0.045 prior is a 0.033 s/lap bias in the wear estimate, which is why the fuel SD is wide.
- Between-car spread `tau_car`: hindsight per-stint within-stint slopes on clean laps at Bahrain 2023 (HARD, 29 stints) have mean 0.044 and SD 0.033 s/lap; subtracting the slope-estimation noise (about 0.009) leaves about 0.03 [VERIFIED: local computation, hindsight, one race, includes outlier stints]. Use 0.03, [ASSUMED], log it as such. This matters because the field-level SE from Phase 2 (0.004 at race end) is the uncertainty of the FIELD mean, not of one car's rate; using it alone would make every car's prior absurdly tight.
- Mean-slope sanity check: HARD 0.044 within-stint = wear 0.121 + fuel -0.078 [VERIFIED], consistent.

### When the Phase 2 fit is identified at Bahrain 2023 [VERIFIED: ran `fit_linear_pace` for laps 5 to 57]
- First identified: **lap 14** (SOFT only; HARD listed "not enough data"). Lap 10 is not identified.
- As-of values drift a long way and the SEs are over-confident early (misspecification: few stops visible, track evolution): lap 14 SOFT 0.255 +/- 0.027, fuel -0.132 +/- 0.027; lap 15 SOFT 0.273; lap 18 SOFT 0.166 +/- 0.008, HARD 0.040 +/- 0.024, fuel -0.069; lap 20 HARD 0.129, SOFT 0.168; lap 25 HARD 0.138, SOFT 0.158; lap 30 0.136 / 0.152; lap 40 0.111 / 0.131; lap 57 0.121 / 0.122, fuel -0.078 +/- 0.001.
- Consequence: the first stint of every driver (laps 1 to about 13 to 20) is always "prior only". For later stints the fit prior is usable but early values (laps 14 to 25) are 3 to 5 reported SE away from the final answer. Recommendation: use the fit only when `report.fuel_s_per_lap` is not None and the compound is in `fit.fitted_compounds`, and inflate with `tau_car` as above; the planner should add a test or demo-run check at laps 14, 20 and 30 and report it. Open question OQ2 asks whether to add an extra "not before lap N" rule.
- ALO at Bahrain 2023 (number 14): stint 1 SOFT laps 1 to 14 started on a used set (tyre_life 4 at lap 1; 17 at end of lap 14); stint 2 HARD laps 15 to 34 (out-lap 15, first measured lap 16 at age 2); stint 3 HARD laps 35 to 57 (first measured lap 36 at age 2). Lap 13 is the last clean lap of stint 1 (lap 14 is the in-lap). Ages in stint 1 start at 5 on the first measured lap, which is why the filter must re-centre ages.

### Pattern 4: Simulator integration without touching the kernel (D-13/D-14, DEC-087)
Current model (read from `numpy_backend.py`, `kernel.py`): `T = mean_tab[c,k,a] + z_off*off_sd + z_wear[r,k]*wear_sd[k]*(a+1) + eps*sd_tab`. `mean_tab` already contains the fitted compound wear (`wear[k]*(a+1)`) and fuel. `make_streams` does `rng.spawn(4)` and keeps the fourth child (`_spare`) unused.

**Recommended design A, "virtual compound" columns (kernel.py and its tests unchanged, Numba cache unchanged):**
1. In `simulate`, after the existing setup, find the filter cars: `car.wear_source == "filter"` with `car.wear_rate_s_per_lap`, `car.wear_sd` not None, and `start.stops_done[i] == 0` (a car that stops on the cutoff lap already has new tyres, so the filter does not apply).
2. For each such car `i` with current real compound index `k0`, append one extra compound index `K + j`:
   - `mean_tab[:, :, K+j, :] = 0` except for car `i`: `mean_tab[:, i, K+j, :] = mean_tab[:, i, k0, :] + delta_i * (arange(max_age) + 1 - age_start_i)` where `delta_i = filter_rate_i - table_slope_i` and `table_slope_i` is the age slope the pace table actually uses for `(i, k0)`, taken from the table itself (`median(diff(mean_tab[0, i, k0, :]))` over age, valid for the linear model and for `BorrowedPace`, which may borrow a slope for an unfitted compound). The deterministic correction is incremental from the age at the start of the simulation, so the lap-time level at the cutoff is continuous with the fit (a replaced total slope would jump the level by `delta * age`, e.g. 0.05 x 15 = 0.75 s: do not do that).
   - `sd_tab[:, i, K+j, :] = sd_tab[:, i, k0, :]`; for other cars copy `k0` columns (never visited, but must be finite).
   - `wear_sd[K+j] = car.wear_sd` (kernel multiplies by `(age+1)`, the same total-age form the fit cars use today; document the asymmetry in a DEC).
   - `z_wear[:, K+j] = z_car[:, i]` where `z_car` is drawn below; the compound column `k0` in `z_wear` is untouched, so the shared compound draw no longer applies to this car's current stint (replacement, as D-14 says).
   - `start_comp[i] = K + j` (and `start.comp`); `_start` must map a virtual index back to the real compound name when it calls `_mean_lap` (currently `comp_names[int(start_comp[i])]`): keep a `real_name_of` list.
3. `next_comp` / `stop_lap` untouched, so after the first stop the car is on a real compound with the compound fit and the compound draw (D-14 "later stints keep the compound fit").
4. Draws: `z_car` comes from ONE new stream: `car_stream = rng.spawn(1)[0]` called AFTER `make_streams` and only when at least one filter car exists; `z_car = normal_block(self._mode, n_cars, n, car_stream)` (plain antithetic normals, never Sobol, so the Sobol dimension `n_sim + n_cars + len(DRAW_COMPOUNDS)` and every existing column are unchanged). Draw for ALL cars and then pick the filter cars' columns, so a car's draw does not depend on which other cars are filter cars (CRN). `Generator.spawn` continues the child counter, so this yields an independent 5th child; the first four are identical to today's [ASSUMED from NumPy SeedSequence semantics; the planner's Wave 0 test must assert byte equality of a fit-only run against a stored Phase 3 result]. With no filter car nothing is spawned and nothing changes: byte-identical.
5. Test coverage required by D-14: higher filtered rate means worse mean finish (deterministic part), larger filtered SD means larger total-time spread for that car (z part), CRN: forcing another driver's plan does not move this car's draws.

Alternative design B (not recommended): add `z_car (n,C)`, `car_delta (C,)`, `car_sd (C,)`, `car_age0 (C,)`, `car_on (C,)` arguments to `lap_step` and branch on `stops_done[r,c] == 0`. Incremental SD would then be possible, but every caller of `lap_step` (including the positional call in `tests/sim/test_kernel.py::run`) must change and the Numba cache recompiles; Phase 3 test files would no longer be "unchanged".

**State plumbing:** `CarState` gains `wear_source: str = "fit"` (validated to {"fit","filter"}); add `"wear_source"` to `_CAR_KEYS` and `_OPTIONAL_CAR_KEYS` (read with `raw.get("wear_source", "fit")`, as `laps_done` is); write it in `to_json_dict`. `build_race_state(snapshot, fit, *, laps_total, pit_loss_s, wear_filter: Mapping[int, FilterSnapshot] | None = None)`: for a car with an entry for its current stint, set `wear_rate_s_per_lap`, `wear_sd` from the filter and `wear_source="filter"`; else as today. Note `_check_keys` rejects unknown keys, so the JSON key must be added to `_CAR_KEYS` or old/new round-trips fail; and `test_state.py` golden JSON tests may need the new optional key to be absent when "fit" (write it only when "filter" to keep old JSON byte-stable, as `sc_laps_elapsed` does).

### Anti-Patterns to Avoid
- **Reading the accessor in the filter.** Take a `RaceSnapshot` or arrays (D-09).
- **Tuning noise/prior/metric to pass the 10% test** (D-12; Phase 3 lesson).
- **Using `sigma_s` from laps after the cutoff** (hard rule D-07): only `fit_linear_pace(snapshot)` of the same snapshot.
- **Replacing the total slope in the simulator** (level jump at the cutoff, see Pattern 4).
- **Gating on the first one or two laps**: the diffuse level makes the innovation variance meaningless there.
- **Treating the field-level Phase 2 SE as the per-car prior SD** (needs `tau_car`).
- **Plain 2-state with fuel ignored**: the SD would understate the uncertainty by the fuel confound; coverage fails in the end-to-end variant.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Clean-lap rule | New lap filter | `f1si.laps.fade_reason` (and `_classify` logic in `pace/linear.py`) | Shared with plot and fit; one definition (D-08) |
| 95% multiplier | Literal 1.96 | `f1si.pace.linear.CI_Z` | One constant |
| Binomial band for coverage | Normal approximation by hand | `scipy.stats.binom.interval(0.999, n, 0.95)` | Exact; band for N = 1000 is about [0.927, 0.973] |
| Figure/PNG | New plotting style | Copy `plots/wear.py` (Figure API, `COMPOUND_COLORS`, slug regex) | Pattern already in repo |
| Draws | A new RNG | `rng.spawn(1)` + `normal_block` | Reproducibility, CRN (project constraint) |
| Matrix inverse | `np.linalg.inv(P)` | None needed: scalar `s`, gain `P h / s` | Joseph form is stable |

**Key insight:** the only genuinely new maths is a 3x3 recursion; everything else (rules, constants, plotting, draws) exists and must be reused so that the shared definitions cannot drift.

## Common Pitfalls

### Pitfall 1: The accuracy target is a statement about information, not code quality
**What goes wrong:** Tests are written, fail at 20 to 35% error, and are "fixed" by shrinking noise or the prior.
**Why:** 7 laps with a diffuse level carry `Sxx/sigma^2 = 1244` of slope precision at sigma 0.15, versus the `1/0.0088^2 = 12,900` needed for MEDIUM.
**Avoid:** Resolve the target with the owner (Open Question OQ1) before writing the gated accuracy test.
**Warning signs:** a test that sets `noise_sd_s` below 0.05 or `tau` below 0.02 to pass.

### Pitfall 2: Fuel/wear confounding makes a floor
**What goes wrong:** Even infinite laps cannot beat `sqrt(tau^2 sf^2/(tau^2+sf^2))`. For tau 0.05, sf 0.025 that is 0.022 s/lap.
**Avoid:** Report it; carry the fuel SD (3-state). Label "fuel prior only" in the CLI.

### Pitfall 3: Truncated truth distorts coverage
**What goes wrong:** Drawing true rates from a Normal truncated at > 0 gives coverage 0.956 to 0.97 instead of 0.95.
**Avoid:** Either draw truth from the exact prior and report the sign problem separately, or keep the pass band at the 99.9% binomial band and state the truncation in the test docstring. For the relative-error metric, floor the truth (for example truth > 0.25 mu) and say so.

### Pitfall 4: Early Phase 2 fits are far from the truth (Bahrain)
**What goes wrong:** Using the lap 14 to 25 fit as a prior (SOFT 0.255 or 0.27 against 0.125 final) drags the filter and breaks coverage on real data.
**Avoid:** Inflate with `tau_car` and demonstrate at laps 14, 20, 30; see OQ2.

### Pitfall 5: Level jump at the stint boundary in the simulator
See Pattern 4: apply the correction to the incremental age only.

### Pitfall 6: Age bookkeeping
`LinearPaceFit` uses age at the END of the lap; stint 1 may begin at a nonzero age (ALO: lap 2 is age 5). The generator's `tyre_life = lap - stop` for stint 2 and `start_tyre_age + lap` for stint 1. Use `d = lap - first_measured_lap`, not the raw age, inside the filter; carry the raw age only for display.

### Pitfall 7: Registry and docs tests will fail until updated
`tests/guards/test_consumer_registry.py` fails if a public function in a `DESIGNATED_MODULES` module is neither CONSUMED nor EXEMPT. Add `f1si.pace.kalman` and `f1si.plots.wear_filter` to `DESIGNATED_MODULES`, a `wear_filter` consumer `(db_path, at) -> output` that runs the snapshot adapter, and EXEMPT entries (with reasons) for the pure-array functions. `tests/test_docs.py` requires every new module in a `docs/explained/phase-*.md` tour; `tests/test_decisions_log.py` requires `MIN_ENTRIES` bumped (87 now; add the number of DECs written).

### Pitfall 8: Windows shims
Run everything as `uv run python -m pytest` / `-m mypy` / `-m ruff` / `-m f1si wear-filter ...`, not `uv run <shim>` (Application Control).

## Code Examples

### Closed-form check used as a test oracle
```python
# Source: derived in this research; matches the Monte Carlo to 3 decimals
def posterior_rate_sd(tau, sigma, fuel_sd, n_measured):
    sxx = n_measured * (n_measured**2 - 1) / 12.0
    data_var = sigma**2 / sxx
    return math.sqrt(tau**2 - tau**4 / (tau**2 + fuel_sd**2 + data_var))
# n=7, sigma=0.15, tau=0.02, fuel_sd=0.02 -> 0.0173 (MC 0.0173)
```

### Coverage gate
```python
# Source: scipy.stats.binom API
from scipy.stats import binom
lo, hi = binom.interval(0.999, n_stints, 0.95)   # counts; divide by n_stints
assert lo <= covered <= hi
```

### Synthetic generator extension (D-10), defaulted
`SyntheticRaceSpec.wear_rate_deviation_s_per_lap: Mapping[int, float] = field(default_factory=dict)` keyed by driver index; in `generate_race` use `wear[compound] + dev.get(i, 0.0)`; add `driver_wear_rate_s_per_lap: Mapping[int, Mapping[str, float]]` (default empty) to `SyntheticTruth`. No new random draws, so noise and weather streams (and every existing fixture) are unchanged. For stint lap 8 and beyond use `n_laps >= 24` (stop at `n_laps//2 + i%2`; stint 1 has `n_laps//2` laps). The 1,000-stint recovery test should not need a DuckDB: the filter takes plain arrays, so drive it directly from `generate_race(...).race.tables["laps"]` or even straight from the model equation, with a smaller end-to-end test through the snapshot adapter.

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Hindsight per-compound OLS (Phase 2) | Per-stint, as-of Kalman posterior with honest band | The rate is per car and per stint, with fuel uncertainty carried |
| Fixed wear SD from the field fit in the simulator (Phase 3) | Per-car current-stint rate and SD for filter cars | Wider, more honest finishing intervals for cars with uncertain wear (the Phase 3 ALO flag) |

**Deprecated/outdated:** none relevant.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Generic rate prior means SOFT 0.10 / MEDIUM 0.08 / HARD 0.06 s/lap, SD 0.05 | Pattern 3 | Real first stints biased or mis-covered; mitigated by the wide SD; owner may override |
| A2 | Fuel prior -0.05 +/- 0.025 s/lap (incl. track evolution) | Pattern 3 | Biases the first-stint wear estimate; band is wide so coverage should hold |
| A3 | Default observation sigma 0.30 s when the fit is unidentified | Pattern 3 | Too tight or too wide a band on real first stints; Bahrain measured 0.23 to 0.48 |
| A4 | Between-car rate spread `tau_car` = 0.03 s/lap | Pattern 3 | Fit-prior stints over- or under-confident; derived from one race, hindsight, including outlier stints |
| A5 | `rng.spawn(1)` after `spawn(4)` leaves the first four children unchanged (NumPy SeedSequence counter semantics) | Pattern 4 | "fit" cars would not be byte-identical; caught by the Wave 0 byte-equality test |
| A6 | 3-state filter is acceptable in place of D-01's literal 2-element state (the third element is a fuel nuisance state, the reported quantity is unchanged) | Standard Stack | Owner may prefer the 2-state with quadrature SD; both are given |
| A7 | Gate: 3.0 SD, active from the 3rd used lap, no two consecutive rejections | Pattern 2 | Too strict/lax on real data; tested only on synthetic contamination |
| A8 | Forum fuel-per-kg figures (0.033 to 0.133 s/kg, 1.7 to 2.3 kg/lap) | Pattern 3 | Context only; not used to set a number except through the wide fuel SD |

## Open Questions (RESOLVED)

1. **OQ1 (requirement risk, PAC-04 accuracy half): which restated target?**
   - Known: the 10% at stint lap 8 target is unattainable honestly (tables above); coverage and narrowing are attainable.
   - Unclear: whether the owner wants a longer horizon per compound, an information criterion, or a different quantity.
   - Recommendation: planner raises it as a checkpoint with the achievable numbers; until then implement the accuracy test as report-only and gate coverage and narrowing.
   - RESOLVED: owner chose "Test optimal accuracy" (CONTEXT D-17): gate the closed-form (Bayes-optimal) match, error(lap 8) < error(lap 0), coverage and narrowing; the 10% figure is reported, not gated; revisit in Phase 7. Logged in DEC-092.
2. **OQ2: minimum evidence before the Phase 2 fit becomes the prior.**
   - Known: Bahrain's as-of fit is first identified at lap 14 but is 3 to 5 SE from the final value until about lap 30 to 40.
   - Unclear: whether to add a "fit prior only after N laps / SE below X" rule.
   - Recommendation: ship with `tau_car` inflation only, run the demo at laps 14, 20, 30, and let the verifier report coverage on real data as an observation.
   - RESOLVED: CONTEXT D-19: fit prior only when identified and the compound is fitted, inflated by `tau_car`; no "not before lap N" rule; 04-05 reports the Bahrain prior at laps 14, 20 and 30.
3. **OQ3: ALO interval observation (Phase 3 open flag).** Not computable until the integration exists; the CLI/verification step should report ALO's 90% interval width with and without the filter at a mid-race lap.
   - RESOLVED: reported as an observation (not a gate) by plan 04-05 Task 1 and the verifier.

## Runtime State Inventory

Not a rename/refactor/migration phase. Omitted. (Note: `data/f1si.duckdb` and `data/http-cache` exist and are only read.)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 + uv | everything | yes | project `.venv` | — |
| Bahrain 2023 cache (`data/f1si.duckdb`, `F1SI_DATA_DIR` default `data`) | demo, real-data check | yes (resolved slug `bahrain-2023`; 20 drivers; 865 clean laps at race end) | — | Synthetic only |
| Numba | simulator | yes (existing) | existing | — |
| matplotlib | PNG | yes (existing) | existing | — |
| Network | none needed | — | — | — |

**Missing dependencies with no fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + hypothesis (existing) |
| Config file | `pyproject.toml` (`testpaths = ["tests"]`, `-m "not network"`, strict markers) |
| Quick run command | `uv run python -m pytest tests/pace tests/test_state.py tests/test_state_builder.py -x -q` |
| Full suite command | `uv run python -m pytest -q` plus `uv run python -m ruff check .`, `uv run python -m ruff format --check .`, `uv run python -m mypy` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PAC-03 | Joseph-form update equals closed-form Bayesian linear regression (mean and covariance) | unit | `uv run python -m pytest tests/pace/test_kalman_math.py -x` | Wave 0 |
| PAC-03 | Incremental `update` lap by lap equals batch over a stint | unit/property (hypothesis) | `uv run python -m pytest tests/pace/test_kalman_incremental.py -x` | Wave 0 |
| PAC-03 | Posterior SD never increases on a measured lap; unchanged on skipped lap | unit | `uv run python -m pytest tests/pace/test_kalman_narrowing.py -x` | Wave 0 |
| PAC-03 | `q > 0` widens the band; `q = 0` default | unit | same file as above or `test_kalman_math.py` | Wave 0 |
| PAC-03 | Skipped laps (lap 1, pit in/out, SC) do not update; reason counted; gate counts rejections; no gate before 3rd used lap; never two rejections in a row | unit | `uv run python -m pytest tests/pace/test_kalman_gate.py -x` | Wave 0 |
| PAC-04 | Coverage of 95% intervals at each stint lap and pooled within binomial 99.9% band (N >= 1000 stints, truth ~ prior, fuel and noise known) | statistical recovery | `uv run python -m pytest tests/pace/test_kalman_recovery.py::test_coverage -x` | Wave 0 |
| PAC-04 | Fuel-prior variant: coverage still holds with fuel from its prior (SD in band) | statistical recovery | `...::test_coverage_with_fuel_prior` | Wave 0 |
| PAC-04 | Accuracy at stint lap 8: REPORT-ONLY until OQ1 resolves; asserts error(lap 8) < error(lap 0) and matches the closed form `posterior_rate_sd` within MC error | statistical recovery | `...::test_accuracy_report` | Wave 0 |
| PAC-04 | Posterior SD matches closed form `posterior_rate_sd` at stint lap 8 (verifies the table in this research) | unit | `...::test_posterior_sd_matches_closed_form` | Wave 0 |
| PAC-04 | Generator with per-driver wear deviation: existing fixtures byte-identical when unset; truth exposes the deviations | unit | `uv run python -m pytest tests/test_synthetic.py -x` | extend existing |
| Criterion 1 | Real Bahrain 2023 ALO stint: band narrows over the first laps of each stint (opt-in, needs cache) | real-data | `uv run python -m pytest -m network tests/real/test_wear_filter_bahrain.py -x` (or skip-unless-cache pattern as `tests/real/test_wear_bahrain.py`) | Wave 0 |
| Criterion 4 / D-13 | `build_race_state(..., wear_filter=...)` fills `wear_rate_s_per_lap`, `wear_sd`, `wear_source="filter"`; without it identical to today; JSON round trip; old JSON (no key) loads | unit | `uv run python -m pytest tests/test_state.py tests/test_state_builder.py -x` | extend existing |
| D-14 | "fit" run byte-identical to a stored Phase 3 result (guards A5); higher filtered rate finishes worse; larger SD widens total-time spread; CRN holds (forcing another driver's plan does not move this car's `z_car`) | unit | `uv run python -m pytest tests/sim/test_filter_cars.py -x` | Wave 0 |
| D-14 | All Phase 3 sim tests green unchanged (variance ratios, CRN, kernel twin) | regression | `uv run python -m pytest tests/sim tests/conformance -x` | existing |
| D-09 | Future-scramble: filter consumer ignores laps after the cutoff; registry complete | guard | `uv run python -m pytest tests/guards -x` | extend `consumers.py` |
| D-15 | CLI `wear-filter` prints per-stint sources ("prior only"), per-lap rows, writes PNG; friendly errors; add `"wear-filter"` to `_FRIENDLY_VALUE_ERRORS` | CLI | `uv run python -m pytest tests/test_cli_wear_filter.py -x` | Wave 0 |
| D-16 | Docs tour mentions new modules; README needles; `MIN_ENTRIES` bumped | docs | `uv run python -m pytest tests/test_docs.py tests/test_decisions_log.py -x` | extend existing |

### Sampling Rate
- **Per task commit:** the quick command plus the single test file touched.
- **Per wave merge:** full suite and the three lint/type commands.
- **Phase gate:** full suite green on CI (Ubuntu and Windows) before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/pace/test_kalman_math.py`, `test_kalman_incremental.py`, `test_kalman_narrowing.py`, `test_kalman_gate.py`, `test_kalman_recovery.py` (the recovery file reproduces the key cells of the feasibility table with fixed seeds; 1,000 stints of 7 steps vectorised run in well under a second)
- [ ] `tests/sim/test_filter_cars.py`, `tests/test_cli_wear_filter.py`, `tests/real/test_wear_filter_bahrain.py`
- [ ] Stored Phase 3 reference (hash of `finish_positions` and `total_time_s` for a fixed seed and state) captured BEFORE touching `numpy_backend.py`, to prove "fit" cars are byte-identical
- [ ] Framework install: none

## Security Domain

`security_enforcement` is not set to false in config (treated as enabled); the phase is local, offline, read-only on the cache.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | out-of-sample lock (2026 races) already enforced by the accessor; CLI must keep catching `OutOfSampleLockedError` |
| V5 Input Validation | yes | slug regex `^[a-z0-9-]+$` for the PNG name (as `plots/wear.py`); driver code validated against the state; `--lap` >= 0; `wear_source` validated to {"fit","filter"}; filter inputs finite (reject NaN/inf like `CarState._check_float`); `q`, sigma, SDs > 0 |
| V6 Cryptography | no | — |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via slug in output file name | Tampering | slug regex + `reports_dir()` join (existing pattern) |
| NaN/inf poisoning the covariance | Tampering / DoS | validate observations finite; Joseph form + symmetrise; skip non-finite laps with a reason |
| Unbounded draw arrays in the simulator | DoS | extra virtual columns bounded by `MAX_CARS`; n_races bound already enforced |
| Look-ahead leakage | Information disclosure | snapshot-only inputs; scramble test and registry |

## Sources

### Primary (HIGH confidence)
- Local code read this session: `src/f1si/pace/linear.py`, `laps.py`, `state.py`, `sim/numpy_backend.py`, `sim/kernel.py`, `sim/draws.py`, `sim/constants.py`, `synthetic/generator.py`, `paths.py`, `tests/guards/consumers.py`, `tests/sim/test_kernel.py`, `plots/wear.py` (header), `cli.py` (wear and simulate commands)
- Local computation on `data/f1si.duckdb` (Bahrain 2023): as-of fits laps 5 to 57, ALO stints, per-stint slopes, noise estimates
- Monte Carlo and closed-form scripts in the session scratchpad (feas.py, feas2.py, feas3.py, gate.py, real.py, real2.py)

### Secondary (MEDIUM confidence)
- Pirelli chief-engineer statements on degradation (compound-dependent, track-dependent, can be similar across compounds): https://www.formula1.com/en/latest/article/the-key-challenge-f1-teams-will-need-to-get-to-grips-with-in-sundays-barcelona-catalunya-grand-prix.6Wu7w5DNSGOnt6y6FgZIpe and https://www.planetf1.com/f1-data/spanish-grand-prix-madring-tyre-degradation-strategy (search result summaries; not fetched in full)

### Tertiary (LOW confidence)
- Fuel-effect per-kg and per-lap consumption figures from forum threads (https://www.f1technical.net/forum/viewtopic.php?p=1091875 and similar) and Michelin Canopy article https://simulation.michelin.com/canopy/technical-articles/fuel-saving-secrets-why-f1-cars-conserve-fuel-while-f2-cars-go-all-out (units unclear); hobby-project degradation constants (0.085 / 0.050 / 0.028). Used only for context; all generic priors are [ASSUMED].

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new packages, own NumPy code, all libraries already in the repo
- Feasibility maths: HIGH - closed form and Monte Carlo agree; real noise measured from the local cache
- Architecture (simulator integration): MEDIUM-HIGH - design read against the actual code, but not yet executed; A5 needs the byte-equality test
- Generic priors: LOW - no authoritative source; flagged [ASSUMED]
- Pitfalls: HIGH for items measured here, MEDIUM for test-registry details (read from `consumers.py`)

**Research date:** 2026-11-12
**Valid until:** 2026-12-12 (stable domain; only repo changes would invalidate it)

## Suggested DEC entries (from DEC-088)
DEC-088 filter model (3-state, local linear trend + fuel nuisance state, why); DEC-089 zero process noise default and its limits; DEC-090 priors and their [ASSUMED] status (generic rate, fuel, sigma, `tau_car`); DEC-091 clean-lap and gate rule; DEC-092 feasibility result and the PAC-04 accuracy restatement (once the owner decides); DEC-093 simulator integration (virtual compound columns, new stream, incremental deterministic correction, total-age SD asymmetry); DEC-094 `wear_source` field and builder argument. Bump `MIN_ENTRIES` to 87 + number added.
