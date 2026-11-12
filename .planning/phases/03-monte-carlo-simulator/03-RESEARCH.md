# Phase 3: Monte Carlo Simulator - Research

**Researched:** 2026-11-12
**Domain:** Vectorised lap-by-lap race Monte Carlo (NumPy + Numba kernel), Sobol/antithetic variance reduction, Beta-Binomial safety-car rate
**Confidence:** HIGH on codebase facts and measured timings (prototyped in this session); MEDIUM on variance-reduction effect size; LOW on the numeric overtaking/SC constants (documented defaults, not fitted)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Safety-car model (REG-01)**
- **D-01: SC rate from earlier races, else a prior.**
  - The per-lap SC deployment probability is a Beta-Binomial posterior: SC deployments over race laps, pooled from every earlier in-sample race returned by `AsOfAccessor.history(AsOf(race_id, ...))`. That call never returns the current race, later races or the locked 2026 races.
  - The prior is a documented weak literature prior: mean about 1% per lap, weight about 5 races (~300 laps).
  - Bahrain 2023 is round 1 of the cache and has no earlier races, so it gets the prior alone. The output says so.
  - The simulator uses the posterior mean. Parameter uncertainty in the rate is not sampled in the MVP.
  - The cache supports this: 81 of 87 races have track status, with 56 SC deployments over ~5,254 laps, about 1.1% per lap.
  - Circuit-specific rates wait for Phase 8.
- **D-02: SC only, not VSC or red flag.**
  - REG-01 asks for a safety-car probability. VSC (32 events in the cache) and red flags (11) belong to the Phase 8 Markov regime model (REG-02, REG-03).
  - The SC model is built so a VSC event type can be added later with the same mechanics and different parameters.
- **D-03: SC duration is a fixed whole number of laps.**
  - The duration is the median SC length in the same earlier races, measured from deployment to "in this lap". If fewer than 5 earlier SCs exist, it falls back to 4 laps (documented).
  - Duration is not sampled in the MVP. Occurrence is the random part.
  - Only one SC can be active at a time. A new SC can only start on a green lap.
- **D-04: what an SC does in a simulated race.**
  1. Running order is frozen: no overtaking on SC laps.
  2. SC lap times are the leader's green pace times a documented slowdown factor (about 1.4, the factor the synthetic generator already uses for VSC laps). Every car runs at the car ahead's pace or slower.
  3. On the restart lap, gaps are compressed to a fixed spacing of about 1 s per position (documented). This is the "field bunches up" effect that success criterion 3 requires.
  4. Pit loss under SC is a fixed documented fraction (about 0.5) of the green pit loss.
     - The builder fills `RaceState.pit_loss_s["sc"]`, and the docstring and DEC entry mark it as a placeholder.
     - Phase 8 (REG-03) replaces it with a value measured from data.
     - This fills D-13's placeholder early because success criterion 3 says SCs must visibly change pit loss.
  - Tire age still goes up on SC laps. The lower wear under SC is not modeled, and this is documented as a simplification.
- **D-05: current regime at the cutoff.**
  - `build_race_state` reads `track_status` as of lap N.
  - If an SC is active at the cutoff, `regime` becomes `{"sc": 1.0}`; otherwise it is `{"green": 1.0}`.
  - The simulator continues an active SC for the rest of the D-03 duration, counted from its deployment lap.
  - This keeps BUILD_PLAN's "lap 31, safety car" story possible without a regime model.
- **D-06: SC rate recovery test.** This is the project's rule that every model has a synthetic recovery test.
  - Extend the synthetic generator with an optional SC spec. It stays backward compatible: defaults leave existing fixtures byte-identical.
  - Test that the rate estimator recovers a known rate from synthetic history within its interval.
  - Test that the simulator's realised SC frequency over many races matches the input rate.

**Overtaking model (SIM-01)**
- **D-07: lap-by-lap time model with dirty air and a pass chance.** TU Munich / Heilmeier style.
  - Each lap, every car's "free" lap time comes from pace, wear and fuel plus noise (D-11).
  - Cars are processed front to back in running order. If a car would cross the line less than `min_gap_s` (about 0.5 s, documented) behind the car ahead, it attempts a pass.
  - The pass succeeds with probability `p = logistic((Δ - threshold_s) / scale_s)`, where Δ is its pace advantage on that lap: the car ahead's free lap time minus its own.
  - A failed pass leaves it held at `min_gap_s` behind the car ahead (the dirty-air time loss).
  - A successful pass swaps them, and the passer pays a small documented time cost.
  - The passing randomness is one uniform per car per lap. That uniform belongs to the variance-reduced draw set (D-13), so it follows the seed.
- **D-08: overtaking parameters are documented defaults.**
  - `threshold_s`, `scale_s`, `min_gap_s` and the pass cost are named constants with literature or engineering justification in a DEC entry.
  - A sanity test shows that pass probability rises with the pace gap, a much faster car almost always passes, and equal pace rarely does.
  - Fitting them per circuit from real overtakes is deferred to Phase 6 calibration and the backtest.
- **D-09: no lapping interactions.**
  - Blue flags, unlapping under SC and lapped traffic are not modeled.
  - Every car runs to `laps_total`, as in DEC-073's free-track rule.
  - Finishing order is by total race time over the full distance.
  - Retirements (DNFs) are not simulated in Phase 3. This is documented as a limitation; see Deferred.

**Other cars and randomness**
- **D-10: every car follows a fixed legal plan.**
  - A car named in `plans` uses that plan.
  - Every other car uses the free-track optimizer's best plan from the same state (Phase 2 `FreeTrackOptimizer`), computed once per call, not per simulated race.
  - If the optimizer refuses a car (unfitted compound, unidentified fit, too few laps left), the car gets a documented fallback: one stop, roughly at the middle of its remaining laps, onto a fitted compound it has not used. If that is impossible, no further stops.
  - Every fallback is listed in the result's diagnostics.
- **D-11: opportunistic stops under SC (other cars only).**
  - When an SC starts, a car **not** in `plans` whose next planned stop is within the next 5 laps (documented constant) and is still legal takes that stop now, under SC pit loss.
  - Cars with a forced plan (`plans` argument) follow it exactly, so later policy evaluation (Phase 5) prices the plan it asked for.
- **D-12: two sources of uncertainty are sampled.**
  - **Per race, per car:** a parameter draw of the pace offset ~ N(offset, SE) and the wear rate ~ N(rate, wear_sd), using the Phase 2 standard errors. This is where the honest-uncertainty core value comes in.
  - **Per lap, per car:** independent lap-time noise ~ N(0, σ) with σ from `PaceModel.predict`'s SD.
  - Car-level draws come from the variance-reduced set (D-13).
  - The simulator is constructed with a `PaceModel` for mean and SD. `RaceState` supplies the per-car state and the SEs.
  - Where a needed SE is missing from `CarState`, the planner adds it or takes it from the fit object. Claude's discretion; must stay JSON round-trip safe.
- **D-13: variance reduction.**
  - Use scrambled Sobol points from `scipy.stats.qmc.Sobol`, with the scramble seeded from the caller's `np.random.Generator`, for the low-dimensional inputs that drive most of the variance:
    - SC occurrence per lap;
    - per-car parameter draws;
    - pass uniforms where the dimension budget allows.
  - Map them through inverse CDFs. Pair every draw with its antithetic `1 - u`.
  - High-dimensional per-lap noise uses plain pseudo-random antithetic normals from the same Generator.
  - n_races must be even, or the simulator pads and trims internally. Document whichever is chosen.
- **D-14: the variance-reduction test (SIM-03).**
  - Over R independent seeds (e.g. 40) at equal N, compare the variance of the estimator "chosen driver's mean finishing position", and of P(top 5), for plain MC against Sobol plus antithetic.
  - The test asserts a lower variance ratio with a margin. It is deterministic by seed.
  - The ratio is reported in DECISIONS.md and the explainer.
- **D-15: reproducibility.**
  - The same seed gives bit-identical `SimulationResult` arrays.
  - The rng is the only source of randomness. No global state, and Sobol scrambling comes from the rng.
  - Different seeds give different results.

**What you see**
- **D-16: CLI:** `uv run f1si simulate bahrain-2023 --driver ALO [--lap N] [--n 50000] [--seed 0]`. It prints:
  - the state it simulated from;
  - the SC rate used and its source ("prior only: no earlier races" for Bahrain 2023);
  - each car's plan source (optimizer or fallback);
  - the chosen driver's finishing-position distribution: P1..P20 probabilities, mean, median, 90% interval;
  - the share of simulated races with an SC;
  - runtime.

  It also writes a bar-chart PNG to `reports/sim-<slug>-<DRV>-lap<N>.png`, using the `plots/wear.py` pattern (Figure API, no pyplot).
- **D-17: the hindsight rule carries over from Phase 2 (D-20).**
  - Without `--lap`, it simulates from lap 0 with a pace fit from the whole race and labels the run "hindsight simulation".
  - With `--lap N`, it uses only data known at lap N and refuses with the Phase 2 message when the fit is not identified.
- **D-18: benchmark (SIM-02).**
  - A pytest benchmark simulates 50,000 races of a full 57-lap, 20-car state in under 10 s on CI (Ubuntu and Windows).
  - Any JIT warm-up is excluded and stated.
  - NumPy first. Numba is allowed for the per-lap front-to-back passing loop if NumPy alone misses the budget. Log it in a DEC entry.
  - The CLI prints the runtime.
- **D-19: provisional `SimulationResult` is extended as needed.**
  - Keep `finish_positions` and `total_time_s` as `(n_races, n_cars)` in `RaceState.cars` order.
  - Add per-race diagnostics needed by the tests and CLI: SC laps per race, actual stop laps per car and pit loss paid.
  - Keep the conformance suite and the `NoisySimulator` test double in sync.
- **D-20: explainer and docs.**
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

### Deferred Ideas (OUT OF SCOPE)
- VSC and red-flag events, circuit-specific SC rates, a regime transition matrix: Phase 8 (REG-02).
- Pit loss under SC/VSC measured from data: Phase 8 (REG-03). Phase 3 uses a documented placeholder ratio.
- Retirements/DNFs, first-lap incidents, blue flags and lapping: later calibration work (Phase 6 backtest finds whether they matter for interval coverage).
- Fitting overtaking parameters per circuit from real passes: Phase 6 calibration.
- Sampling uncertainty in the SC rate and SC duration: Phase 8.
- Lower tire wear and fuel burn under SC: Phase 7 / M2 physics.
- JAX / Rust simulator backends: M5.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SIM-01 | Vectorised NumPy simulator from any `RaceState` (pace, pit stops, pit loss, overtaking from pace gap, SC) | Lap-major Numba kernel + NumPy draws/tables prototype, 1.7-2.5 s per 50k x 20 x 57 (section "Architecture Patterns"); per-car start laps, catch-up lap, unfitted-compound fallback (Pitfalls 4-7) |
| SIM-02 | 50,000 races in under 10 s, benchmarked | NumPy-only prototype measured 6.4-7.5 s (too close to the limit on CI), Numba lap kernel 1.7-2.5 s; benchmark test design with warm-up excluded |
| SIM-03 | Sobol + antithetic lower variance than plain MC at equal N, tested | `scipy.stats.qmc.Sobol` facts (max 21,201 dims, `rng=` keyword, `random_base2`), measured variance ratios 1.4-1.9 on mean finish, ~1 on P(top 5); robust test design (D-14 section) |
| REG-01 | Safety-car per-lap probability from history | Beta-Binomial on `History.track_status` rising edges into status "4" (44 deployments over 3,861 in-sample laps, median duration 3 leader laps), as-of safe via `AsOfAccessor.history` |
</phase_requirements>

## Summary

The simulator is feasible inside the 10 s budget, but **not safely with NumPy alone**. A faithful NumPy prototype (front-to-back passing loop vectorised over races, layouts tried: race-major, position-major, chunked 1k-16k races, boolean-mask and compacted variants) measured 6.4-7.5 s per 50,000 x 20 x 57 on a fast desktop. GitHub-hosted runners are typically 1.5-2x slower, so that design would fail on CI. A lap-major design (all race state held as `(n_races, n_cars)` arrays, one `@njit` call per lap that loops races x positions, NumPy for all draws and pace tables) measured **1.7-2.5 s including all Sobol and normal draws**, with ~1 s one-off compile excluded by warm-up. D-18 explicitly permits Numba for the passing loop. Neither `scipy` nor `numba` is currently in `pyproject.toml` or `uv.lock` (CLAUDE.md lists them as the intended stack), so Wave 0 must `uv add` them and commit the lock (CI runs `uv sync --locked`).

Several things in the existing code do not match what CONTEXT.md assumes and the planner must absorb them: (a) neither `CarState` nor `FitReport` carries the pace-offset standard error, and `CarState.wear_sd` is only for the car's *current* compound, so SEs for other compounds and for offsets need new plumbing; (b) the wear-rate uncertainty is a *shared* per-compound parameter in the fit, so sampling it independently per car (D-12 as written) understates correlation; (c) on real Bahrain 2023 the fit identifies only HARD and SOFT (MEDIUM "not enough data"; at lap 15 only SOFT), one car (PIA) is retired and absent from the fit, so the simulator and D-10 fallbacks must handle unpriceable compounds and drivers routinely, not as an edge case; (d) followers have `laps_done = lap - 1`, so a one-lap catch-up step is needed; (e) the regime mapping has no field for "SC laps already elapsed" (D-05).

Variance reduction works but is modest on a noise-dominated model: on a prototype with 57 x 20 per-lap normals, Sobol + antithetic vs plain MC gave variance ratios of about 1.4-1.9 on "mean finishing position" (R=150, N=1024) and about 1.0 (not reliably better) on P(top 5); the SC-occurrence estimator alone gave 3.0. D-14's test must therefore use enough seeds (R >= 100), assert on mean finish (and total time), assert only a conservative margin, and treat P(top 5) as report-only.

**Primary recommendation:** Add `scipy` and `numba` (and `scipy-stubs` as a dev dependency), implement a lap-major simulator: NumPy builds pace tables via `PaceModel.predict` once and draws via spawned child generators (fixed layout independent of plans), and a single `@njit(cache=True)` lap-step kernel does pit loss, SC, front-to-back passing and restart compression; keep a `py_func` equivalence test and benchmark with warm-up excluded.

## Architectural Responsibility Map

This is a local Python library plus CLI (no browser/server tiers). Tiers are the project's own layers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Reading cache / history for SC rate | Data door (`f1si.data.asof`, called by `f1si.cli` only) | — | Only replay drivers may hold `AsOfAccessor`; model code receives `History` |
| SC rate + duration estimate | Regime model (`f1si.regime.sc_rate`, pure function of `History`) | CLI (passes History) | Plain data in, numbers out; registered as scramble consumer |
| Regime at cutoff + `pit_loss_s["sc"]` placeholder | State builder (`f1si.state.build_race_state`) | — | D-05/D-04 put it in the single builder |
| Pace tables (mean, sd per car/lap/compound/age) | Pace model (`PaceModel.predict`, called once by simulator) | Fallback adapter for unfitted compounds/drivers | Keeps the simulator model-agnostic |
| Plans for non-forced cars | Strategy policy (`FreeTrackOptimizer`, once per call) | Fallback plan rule in simulator package | D-10 |
| Draw generation (Sobol, antithetic, normals) | Simulator Python layer (NumPy/SciPy) | — | Memory-light, per-lap just-in-time |
| Lap step (pit loss, SC, passing, restart) | Compiled kernel (Numba, in simulator package) | Python `py_func` reference for tests | 20-50x faster than NumPy for the sequential front-to-back dependency |
| Distribution summary + PNG | CLI + `f1si.plots.simulate` (Figure API) | — | Same pattern as `plots/wear.py` |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | 2.5.4 (already locked) | arrays, draws, `Generator.spawn`, `standard_normal` | project baseline [VERIFIED: uv.lock] |
| scipy | `>=1.15,<2` (1.18.1 current) | `scipy.stats.qmc.Sobol` (scrambled, `rng=`), `scipy.stats.norm.ppf` | named in CLAUDE.md stack; `rng=` keyword needs >=1.15 [VERIFIED: introspected in scratch venv, `Sobol.__init__(d, *, scramble, bits, rng, optimization, seed)`; CITED: docs.scipy.org Sobol page, "keyword changed from seed to rng in 1.15.0"] |
| numba | `>=0.68,<1` (0.68.1 current) | `@njit` lap-step kernel | named in CLAUDE.md stack, allowed by D-18; imported and JIT-ran with numpy 2.5.4 on Python 3.12 in a scratch venv [VERIFIED: local run] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy-stubs | `>=1.18` (dev group) | mypy strict needs stubs for `scipy.stats` | without it `mypy` fails with `import-untyped` for `scipy.stats`; with it a strict check of a file using `njit`, `qmc.Sobol`, `norm.ppf` passed [VERIFIED: ran mypy --strict in scratch venv] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Numba lap kernel | pure NumPy masks | 6.4-7.5 s locally (measured); would likely exceed 10 s on CI runners |
| Numba lap kernel | Cython / Rust | build tooling, out of stack; Rust is deferred to M5 |
| `qmc.Sobol` | own Sobol/Halton | direction numbers + scrambling are easy to get subtly wrong; scipy supports 21,201 dims |

**Installation:**
```bash
uv add "scipy>=1.15,<2" "numba>=0.68,<1"
uv add --dev "scipy-stubs>=1.18"
# commit pyproject.toml AND uv.lock (CI runs `uv sync --locked`)
uv run python -c "from scipy.stats import qmc; import numba"   # Wave 0 smoke check, see Pitfall 1
```

**Version verification:** PyPI JSON queried 2026-11-12: scipy 1.18.1 (first upload 2010, requires >=3.12), numba 0.68.1 (first upload 2012, requires >=3.10), scipy-stubs 1.18.1.1 (first upload 2024-08-22, repo github.com/scipy/scipy-stubs, ~3.4M downloads/month). `uv pip install --dry-run scipy numba` resolved cleanly alongside numpy 2.5.4 (adds llvmlite 0.50.0).

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| scipy | PyPI | 16 yrs | very high | github.com/scipy/scipy | [OK] | Approved (named in CLAUDE.md stack) |
| numba | PyPI | 14 yrs | very high | github.com/numba/numba | [SUS] TYPOSQUAT_RISK (name close to `numpy`) | Flagged, **false positive**: 140 releases since 2012, homepage numba.pydata.org, named in CLAUDE.md stack. Planner may add a trivial `checkpoint:human-verify` before the `uv add`. |
| llvmlite | PyPI | 12+ yrs | high | github.com/numba/llvmlite | [OK] | Approved (numba dependency) |
| scipy-stubs | PyPI | 2.2 yrs | ~3.4M/month | github.com/scipy/scipy-stubs | [OK] | Approved; not named in CLAUDE.md, so confirm with owner via normal review |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** numba (typosquat heuristic only). `numba` [WARNING: slopcheck flagged as suspicious (name similarity to numpy) - verify before using.]
Postinstall scripts: Python wheels, no install-time scripts. slopcheck 0.6.1 was run via `slopcheck scan <pkg> --pkg pypi --json`.

## Architecture Patterns

### System Architecture Diagram

```
CLI `f1si simulate SLUG --driver ALO [--lap N] [--n] [--seed]`
  |  (only module holding AsOfAccessor)
  |-- snapshot(AsOf(race,N or 0)) --> fit_linear_pace --> measure_pit_loss --> build_race_state
  |                                     (regime from track_status, pit_loss_s{"green","sc"})
  |-- history(AsOf(race,N)) ----------> estimate_sc_rate(History)  --> SafetyCarModel(rate, duration, source)
  v
NumpySimulator(model, sc, constants, uncertainty).simulate(state, n_races, rng, plans)
  1. validate; resolve plan per car:  forced | FreeTrackOptimizer best | fallback  (+ diagnostics)
  2. tables via PaceModel.predict (once):  mean[car, lap, comp, age], sd[car, lap, comp, age]
       (unfitted compound / driver not in fit -> documented borrowed pace, flagged)
  3. initial state per race: clocks from cumulative gap_ahead (or fixed spacing),
       order from positions, catch-up lap for cars with laps_done < state.lap
  4. streams = rng.spawn(4): [sc+params Sobol] [pass Sobol per lap] [noise normals] [spare]
  5. for each remaining lap j:                                  <-- Python loop, ~57 iterations
        eps_j  = antithetic normals (h, cars)      pu_j = Sobol(h, cars) + antithetic
        lap_step_kernel(j, ...)  @njit over races: SC start, pit decisions, free time T,
              arrivals in running order, front-to-back pass/hold, SC freeze+sort, restart compress
  6. total_time = clock; finish_positions = rank(total_time) ; diagnostics arrays
  v
SimulationResult(finish_positions, total_time_s, + sc_lap_mask, stop_laps, pit_loss_paid_s, plan_source...)
  v
summary (P1..P20, mean, median, 90% interval, SC share, runtime) + PNG (Figure API, no pyplot)
```

### Recommended Project Structure
```
src/f1si/
├── sim/
│   ├── __init__.py
│   ├── numpy_backend.py     # NumpySimulator: tables, draws, loop (SimulatorBackend)
│   ├── kernel.py            # @njit lap_step (+ plain-Python reference via .py_func)
│   ├── draws.py             # Sobol/antithetic/normal generators, CRN layout (pure, tested alone)
│   ├── plans.py             # per-car plan resolution + fallback rule + diagnostics
│   └── constants.py         # MIN_GAP_S, PASS_*, SC_*, documented with justification
├── regime/
│   ├── __init__.py
│   └── sc_rate.py           # estimate_sc_rate(History) -> ScRateEstimate (consumer)
└── plots/simulate.py        # prepare/build/render + sim_file_name(slug, driver, lap)
```
Every new `src/f1si` module must appear in the `## File-by-file tour` of `docs/explained/phase-03.md` in the same task that creates it (tests/test_docs.py globs `src/f1si/**/*.py`).

### Pattern 1: Lap-major state, one jitted call per lap
**What:** State arrays `order, clock, age, comp, pitted(n_stops), sc_left, ...` are `(n_races, n_cars)`; the Python loop runs over laps; per lap generate that lap's draws (memory stays at a few `(n, cars)` arrays, about 8 MB each at 50,000 x 20) and call the kernel, which loops `for r in range(n)` then positions.
**When to use:** always; avoids both the 1 GB all-laps draw tensors of a race-major kernel and per-op NumPy overhead.
**Measured:** 1.73 / 2.28 / 2.48 s for 50,000 races (3 runs, includes `qmc.Sobol` per lap, `standard_normal`, antithetic concat), compile 0.75 s. Race-major kernel with all draws up front was 2.4 s but needs ~1.1 GB of draws unless chunked, and breaks the per-lap Sobol layout.
```python
# Source: prototype validated in this session (scratchpad nbsim2.py); logic per D-04/D-07
@njit(cache=True)
def lap_step(lap, u_sc, off, wz, eps, pu, tables..., order, clock, age, comp, stops_done,
             sc_left, had_sc, pit_paid):
    for r in range(n):
        if sc_left[r] == 0 and u_sc[r] < sc_rate: sc_left[r] = sc_len
        under = sc_left[r] > 0
        # free time T[c] = table[c,lap,comp,age] + off[r,c] + z_comp*se_comp*age + eps[r,c]
        # arrival[p] = clock[order[p]] + (T or leader_T*SC_SLOW) + pit loss (green or SC ratio)
        # green: for p in 1..C-1: if arr[p] < arr[p-1] + MING: logistic pass test with pu[r, car]
        # SC: stable insertion sort by arrival (pit stops reorder), no passing
        # SC ends this lap: arr[p] = arr[0] + SPACING * p   (restart compression)
```
Use `fastmath=False`, no `parallel=True` (race loop is independent so `prange` would stay deterministic, but CI core counts vary and Windows thread start-up adds noise; 2 s does not need it).

### Pattern 2: Common random numbers (CRN) layout (Phase 5 requirement)
**What:** `rng.spawn(k)` always yields the same children for the same freshly seeded parent and does not consume the parent's stream, so all draw streams are fixed functions of the seed. Rule: *every* draw is indexed by (race, car identity, lap) and is generated unconditionally, never conditioned on plans, order, or SC state.
- stream 0 (`sc_params`): Sobol d = n_laps_remaining + n_cars + n_compounds; first dims = SC uniform per lap, then pace-offset normal per car, then wear normal per compound.
- stream 1 (`passing`): `.spawn(n_laps)` children, one `Sobol(d=n_cars)` per lap; uniform indexed by the car *attempting* the pass (car column, not position).
- stream 2 (`noise`): one `standard_normal((h, n_cars))` per lap, antithetic `[e; -e]`.
- Order of consumption is lap order, never skipped (draw even when a car is idle, in the SC, or already finished).
A forced plan for one driver changes only that driver's pit schedule; SC realisations, parameter draws, noise and pass uniforms of every car are identical, so Phase 5 plan comparisons are paired. CRN holds when callers pass identically seeded generators (`make_rng(s)` per call). Reusing one `Generator` object across calls advances its spawn counter and gives fresh independent draws (also correct, but not paired). `import_scan` forbids `SeedSequence`/`default_rng` outside `f1si.rng`; use only `rng.spawn`.

### Pattern 3: Sobol construction and odd N
**What:** Build `h = ceil(n/2)` base points with `m = ceil(log2(h))`, call `Sobol(d, scramble=True, rng=child).random_base2(m)`, take the first `h` rows (prefix), form `[u; 1-u]` (2h rows), trim to `n`. 50,000 races -> h = 25,000, m = 15 (32,768 generated, 31% discarded). Never call `.random(n)` for non-powers of 2: it emits `UserWarning: The balance properties of Sobol' points require n to be a power of 2` [VERIFIED: ran it]. Document "pad and trim, N need not be even" (D-13 allows either).
**Facts:** max dimension 21,201 (21,202 raises "Maximum supported dimensionality is 21201") [VERIFIED]; `rng=` accepts a `Generator` (the spawned child) and is deterministic: same child -> identical points [VERIFIED]; use `rng=`, not the deprecated `seed=`, because `pyproject.toml` has `filterwarnings = ["error::DeprecationWarning:f1si"]`. Generating 2^15 x 1,200 dims takes 0.24 s and 315 MB if done at once, so do the per-lap engines (20 dims, ~29 ms for 2^15) instead.
**Dimension budget (57 laps, 20 cars):** SC 57 + offsets 20 + wear 3 = 80 dims in one engine (the dimensions where Sobol helps most go first); pass 20 dims x 57 laps in separate per-lap engines = 1,140 dims total; well under 21,201.
**Inverse CDF:** `scipy.stats.norm.ppf(np.clip(u, 1e-12, 1 - 1e-12))`.

### Pattern 4: SC rate from `History` (REG-01)
Encoding in the cache (`track_status` table: `race_id, seq, t_s, status, message`; codes "1" green, "2" yellow, "4" SC, "5" red, "6" VSC deployed, "7" VSC ending) [VERIFIED: schema.py + queries on data/f1si.duckdb].
- **Deployment = a row with status "4" whose previous row's status is in {None, "1", "2", "6", "7"}.** This gives 44 in-sample deployments across the 70 in-sample races. A naive "status "4" and previous != "4"" gives 50 because 6 SC rows follow a red flag (`TRACK CLEAR` re-emitted as "4" after "5"). Counting only the message text "SAFETY CAR DEPLOYED" also gives 44 but is OpenF1-specific; the synthetic generator must emit the same message if the planner prefers that rule. Use the edge rule.
- **Exposure laps** = `lap_cutoffs.lap` max per earlier race (History carries `lap_cutoffs`: `race_id, lap, cutoff_s`). In-sample: 3,861 laps over races that have track status. (CONTEXT's "56 over 5,254 laps" counts all 87 races including the locked 2026 races; `history()` never returns those. In-sample posterior = (3+44)/(300+3861) = **1.13 %/lap**.)
- **Duration** = leader laps between deployment and the next row with status != "4": `laps_at(t) = count(cutoff_s <= t) - 1`. Of 44 deployments, 39 end at a green "TRACK CLEAR", 4 at a red flag (exclude: red flag is not SC length), 1 never ends in the data (exclude). Median over the 39 = **3 laps**, mean 3.4, range 1-7 (IQR 2-4). D-03's fall-back of 4 laps is slightly longer than the measured median; keep D-03 (it is the user's decision) but note the measured value in the DEC.
- Posterior: `Beta(a0 + k, b0 + n - k)` with prior `a0=3, b0=297` (mean 1%, weight 300 laps ~5 races); mean `(a0+k)/(a0+b0+n)`; report a 90% interval from `scipy.stats.beta.ppf` for the CLI/tests. D-01 defines the denominator as race laps. SCs only start on green laps, so the exact hazard denominator is non-SC laps; the bias is about 4% of the rate (SC laps ~4% of laps), negligible versus the prior weight; follow D-01 and note it.
- Requires >= 5 earlier SC events for the empirical median (D-03) else 4.

### Pattern 5: SEs for the sampler (D-12) - what exists and what to add
Exists: `CarState.wear_rate_s_per_lap`, `CarState.wear_sd` (SE of the car's *current* compound only), `CarState.pace_offset_s` (offset minus mean offset), `LinearPaceFit.wear_se(compound)`, `fit.report.sigma_s`, `PaceModel.predict -> (mean, sd)` [VERIFIED: state.py, linear.py].
Missing: (1) **no SE for the driver offset** anywhere (`FitReport.driver_offsets` is a plain `dict[int, float]`; the SE is `se[i]` inside `fit_linear_pace` and is discarded). (2) No wear SE for compounds other than the car's current one (a car pitting onto HARD from SOFT needs HARD's SE).
Recommended minimal plumbing: add `FitReport.driver_offset_se: Mapping[int, float]` (default empty; computed from `se[:nd]`), `LinearPaceFit.pace_offset_se(driver_number)`, and optional `CarState.pace_offset_sd: float | None = None` (optional JSON key, precedent: `laps_done`, DEC-073); pass per-compound wear SEs to the simulator constructor as `wear_sd_by_compound: Mapping[str, float]` built from `fit.wear_se` (falls back to the SEs found on cars in the state, then to 0 with a diagnostic). Apply parameter draws as `mean_table + z_offset * offset_sd + z_comp * wear_sd[comp] * tire_age` so the simulator never needs the rate itself (the table already holds it). Independent-draw caveat: the fit's offsets, fuel and wear are correlated (the SVD covariance has off-diagonals); sampling them independently ignores that. Document as a simplification in the DEC entry.

### Pattern 6: Starting a race from a mid-race `RaceState`
- Lap synchronisation: the leader has `laps_done = lap`, followers `lap - 1` (DEC-073). Recommended: **step 0 "catch-up lap"** for cars with `laps_done < state.lap`: their next lap (number `laps_done+1`) is run alone, clock = `gap_to_leader + (T_i - T_leader_mean)` plus pit loss if their plan stops on that lap; age/compound updated; no passing resolution; then re-sort the order by clock. With hand-built states (`laps_done=None`) step 0 is empty. This keeps "pit now" for the focal driver (k = laps_done+1) priceable, which Phase 5 needs.
- Initial clocks: cumulative sum of `gap_ahead_s` down the order; where `gap_ahead_s` is None (lap 0, lapped cars, missing lap-ends) use a documented fixed spacing (0.8 s/position suggested for the grid at lap 0; mid-race unknown gaps use the same spacing, listed in diagnostics). Cars with `laps_done < lap - 1` (retired or lapped, e.g. PIA at Bahrain lap 30 with 13 laps) must not become phantom leaders: give them `clock += (lap - 1 - laps_done) * reference_lap_time` so they finish last, and list them in diagnostics ("retired/lapped, placed last"). D-09 already forbids simulating DNFs; this keeps the result a permutation of 1..n_cars.
- Position None cars sort after known positions by driver number.

### Pattern 7: Pace tables and unpriceable cars (real Bahrain 2023 forces this)
Tabulate once with a single `predict` call over `(car, lap, compound, age)`: 20 x 58 x 3 x 58 ~ 200k elements (fast; `LinearPaceFit.predict` loops over unique drivers/compounds, not elements). Then the kernel is model-agnostic.
Real Bahrain 2023 facts [VERIFIED: ran build_race_state on data/f1si.duckdb]: whole-race fit has HARD and SOFT only (MEDIUM "compound with too few laps", `not_enough_data=('MEDIUM',)`); at lap 15 only SOFT is fitted, yet 13 of 20 cars are on HARD; at lap 30 one car runs MEDIUM; PIA is not in the driver fit (`pace_offset_s=None`) and retired on lap 13. `LinearPaceFit.predict` raises `ValueError` for unfitted compound/driver. So the simulator needs a documented **borrow rule** for pace (e.g. adapter `BorrowedPace(model, ...)`: unfitted compound -> mean of the fitted compounds' wear; driver absent from fit -> field-mean offset with SE from the spread), tagged in diagnostics, plus D-10 fallback plans that only use fitted compounds. State this plainly in the CLI output ("HARD pace borrowed from SOFT for 13 cars").
Also known from the same run: fit sigma_s 0.482 s, fuel -0.078 s/lap, wear SE ~0.004-0.008 s/lap, pit-loss median 24.4 s, whole-race fit lap-0 state has all `gap_ahead_s = None`.

### Anti-Patterns to Avoid
- **Per-op NumPy front-to-back loop over 50,000 races:** measured 6.4-7.5 s; do not "optimise later".
- **Drawing only what is needed** (e.g. pass uniform only when blocked, noise only for active cars): shifts the stream and destroys CRN.
- **Indexing draws by position instead of car:** a different order under another plan would reassign draws.
- **Calling `qmc.Sobol.random(n)` with n not a power of 2.**
- **Sampling `seed=` instead of `rng=`** (DeprecationWarning is an error in this project).
- **Global `np.random`, `default_rng`, `SeedSequence` in src** (import scan fails the build).
- **Race-major kernel with all draws up front:** 57 x 20 doubles per race x 50,000 = 456 MB per draw tensor.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Low-discrepancy points | own Sobol / Halton | `scipy.stats.qmc.Sobol(rng=child).random_base2(m)` | direction numbers, Owen/LMS scrambling, 21,201 dims |
| Inverse normal CDF | rational approximation | `scipy.stats.norm.ppf` | accuracy in the tails |
| Beta credible interval | normal approximation | `scipy.stats.beta.ppf` | exact for small counts |
| Independent streams | seeding by `seed + i` | `rng.spawn(k)` | statistically independent, documented project approach (`rng.py`) |
| Plans for other cars | new strategy search | `FreeTrackOptimizer.rank_plans(state, driver=...)[0]` | D-10; deterministic, tested |
| SC/VSC/red predicate | new status parsing | `f1si.laps.slow_status`, `FADE_TRACK_CODES` | same rule as Phase 2; deployment edge rule is new but lives only in `sc_rate.py` |
| Stable ordering | custom sort in NumPy | insertion sort inside the kernel (<= 20 items) / `np.argsort(kind="stable")` | tiny n; stability gives determinism |

**Key insight:** the only genuinely custom algorithm here is the sequential front-to-back pass resolution, and it is small; everything around it (QMC, quantiles, interval maths, plans) is library code.

## Common Pitfalls

### Pitfall 1: scipy/numba are not installed, and Windows Application Control may block their DLLs
**What goes wrong:** `from scipy.stats import qmc` fails on the owner's PC with `ImportError: DLL load failed while importing _special_ufuncs: An Application Control policy has blocked this file` when scipy was run out of uv's cache directory (`uv run --with scipy`). The same wheels worked when installed into an ordinary venv under a normal folder; `line_profiler`'s compiled module was blocked in that venv too, so the policy is path/reputation based and unpredictable [VERIFIED: both observed in this session].
**How to avoid:** Wave 0 task: `uv add scipy numba`, then `uv run python -c "from scipy.stats import qmc; import numba; numba.njit(lambda x: x)(1)"` from the project's own `.venv`. If blocked locally, CI still passes (Ubuntu/Windows runners are unaffected); record it as a local-environment note, not a design change. Do not substitute a hand-written Sobol to dodge a local policy.
**Warning signs:** `ImportError ... Application Control` at collection time of every new test.

### Pitfall 2: pure NumPy misses the budget on CI
Measured 6.4-7.5 s on a fast desktop; CI runners are slower. Use the Numba lap kernel; exclude the compile with a warm-up call (`simulate(n_races=64)` first) and say so in the test docstring and DEC (D-18).

### Pitfall 3: Wear uncertainty is a shared parameter, not a per-car one
`wear[c]` is one number shared by all drivers; its SE is the error of that single estimate. Drawing it independently per car (D-12 wording) makes cars on the same compound disagree about the tyre, which injects spurious relative-pace noise and makes the output *more* random than the data support. Recommended: draw **one wear normal per compound per race** (3 dims, shared by all cars) and one pace-offset normal per car. If the owner insists on per-car heterogeneity, keep it as a separate documented "car-to-car wear scatter" parameter, not the fit SE. Log the choice in the DEC (it refines D-12; the sampling still happens "per race" from the Phase 2 SEs).

### Pitfall 4: Unfitted compound / driver crashes the pace model
See Pattern 7. Without a borrow rule, `--lap 15` and any state with a MEDIUM or the retired PIA raises `ValueError` from `predict`. Test with a real-data (`network`) Bahrain case and a synthetic state with an unfitted compound.

### Pitfall 5: Mixed lap counts at a cutoff (DEC-073)
Treating all cars as having `state.lap` laps done mis-prices followers (age off by one, wrong stop lap). Use the catch-up step (Pattern 6). Test: a two-car state with `laps_done` 20/19 equals a hand calculation.

### Pitfall 6: Regime has no "SC laps elapsed"
D-05 says an active SC continues "for the rest of the D-03 duration counted from its deployment lap", but `RaceState.regime` is `{"sc": 1.0}` only. Recommended: add optional `RaceState.sc_laps_elapsed: int = 0` (optional JSON key like `laps_done`; builder computes it from the deployment time and the snapshot's leader lap-ends). Simplest alternative: assume the SC has just started (remaining = full duration) and document it. Planner decides; the first needs a `STATE_KEYS` test update.

### Pitfall 7: `build_race_state` changes break existing assertions
`tests/test_state_builder.py` asserts `dict(state.regime) == {"green": 1.0}` and `set(state.pit_loss_s) == {"green"}`. D-04/D-05 change both. Update those tests, `tests/test_state.py` key pins if a field is added, and keep `tests/guards/consumers.py::race_state` consumer green (it already exercises the builder under scramble).

### Pitfall 8: Variance reduction is modest and P(top 5) may not improve
Measured (prototype: 57 x 20 per-lap normals sd 0.3 s, pass chance, SC, one-stop plans): var(MC)/var(Sobol+antithetic) of mean finishing position at N=1024, R=150: cars 3/9/15 -> 1.39 / 1.86 / 1.55; antithetic alone 0.9-1.4; P(top 5): 1.12 / 0.92 (no reliable gain); SC-occurrence indicator alone 3.0 (R=150). At R=40 the same ratios scattered 0.8-1.9 because the sampling error of a variance ratio is about +/-30% at R=40. See "D-14 test design".

### Pitfall 9: `SimulationResult` extension breaks positional constructors
`NoisySimulator` and the planted stubs build `SimulationResult(positions, total)` positionally and `WrongShapeSim` slices both fields. Add new fields **after** the two existing ones with defaults (`None`), keep `eq=False`, and mypy-check `tests/conformance/stubs.py`. Do not reorder existing fields (interfaces.py docstring forbids changing them).

### Pitfall 10: Look-ahead hygiene
The SC-rate function takes `History` (type from `f1si.data.asof`); only `f1si.cli` may name `AsOfAccessor`/`RACE_END` (`test_only_the_drivers_name_the_accessor_in_src`). Register in `tests/guards/consumers.py`: new consumer(s) (e.g. `sc_rate`), add `f1si.regime.sc_rate` to `DESIGNATED_MODULES`, and list each public function in `CONSUMED` or `EXEMPT` (pure math with reason >= 4 words). `test_consumed_function_is_really_called_by_its_consumer` checks the consumer's `co_names`. The simulator itself takes `RaceState` only, so it does not need a consumer. The scramble tests use `CURRENT = "2023-02"` over the 4-race synthetic db; history of 2023-02 is 2023-01 (a VSC, no SC), so also register a case whose earlier races contain SC events (use a dedicated synthetic fixture with `sc_laps`).

### Pitfall 11: Numba determinism and platform
Same seed gives bit-identical results *in one environment*. Do not pin cross-platform golden arrays; tests compare two runs in the same process, and statistical expectations (SC frequency, pass probability monotonicity) with tolerances. Keep `fastmath` off. `math.exp` in jitted code may differ in the last ulp across OSes, which is fine for same-process reproducibility.

### Pitfall 12: Coverage with jitted code
`pytest --cov` cannot trace inside `@njit` bodies; the kernel will report as uncovered. Exercise the `py_func` (un-jitted) version in an equivalence test so line coverage is real, and keep the gate unchanged (no `--cov-fail-under` is set in CI).

## D-14 variance-reduction test design (robust, CI-fast)

- Expose a constructor switch (`variance_reduction: Literal["none", "antithetic", "sobol_antithetic"]`, default `"sobol_antithetic"`) so the test compares plain MC and Sobol+antithetic through the *same code path* at equal N. "none" = iid uniforms/normals from the same spawned streams.
- Estimators: (a) chosen driver's mean finishing position (asserted), (b) chosen driver's mean total time (asserted; nearly linear in the noise, so antithetic helps strongly), (c) P(top 5) (report only, or assert non-inferiority with tolerance; measured ~1.0), (d) SC share (asserted, ratio ~3).
- Statistics: R >= 100 seeds `make_rng(1000+s)`, N = 1024 (a power of 2, h = 512, m = 9), a smaller synthetic state (e.g. 10 cars x 30 laps) so each call is ~10-20 ms; total around 5-10 s. Measure the ratio once during implementation and assert `ratio >= 1.15` for mean position (observed 1.4-1.9, leaves room for the +/-15% estimation error at R=100-150) and `>= 2.0` for the SC-share estimator. Record the measured ratios in the DEC and explainer rather than quoting these prototype numbers.
- Determinism: seeds are fixed so the outcome is a deterministic function of library versions pinned in `uv.lock`; the margin protects against NumPy/SciPy bumps.
- Do not use the 40-seed example from D-14 as the only evidence; at R=40 the estimator of a variance ratio has about 30% relative error.

## Benchmark test (SIM-02)

```python
# Source: design for D-18; measured prototype 1.7-2.5 s locally
def test_50k_races_under_10_seconds(long_state, model) -> None:
    sim = NumpySimulator(model, ...)
    sim.simulate(long_state, n_races=64, rng=make_rng(0))        # warm-up: JIT compile excluded
    t0 = time.perf_counter()
    result = sim.simulate(long_state, n_races=50_000, rng=make_rng(1))
    elapsed = time.perf_counter() - t0
    assert result.finish_positions.shape == (50_000, 20)
    assert elapsed < 10.0, f"{elapsed:.1f} s"
```
State: the 57-lap/20-driver `long_synthetic_*` race at lap 0 (needs `fit_linear_pace` over the end snapshot as in `registry._free_track`). Unmarked so it runs in the normal CI job on both OSes (expected headroom 4x). If CI proves noisy, register a `benchmark` marker in `[tool.pytest] markers` (`--strict-markers` is on; only `network` exists today) but keep the test in the default selection, because the CI gate is what makes SIM-02 count. Warm-up caveat: with `cache=True` the first CI run compiles (~1 s), later runs reuse `__pycache__`; the warm-up call makes both cases equal. Memory at 50,000 x 20: about a dozen `(n, 20)` float64/int64 arrays (8 MB each) plus the result and an optional `(n, laps)` SC mask, under ~250 MB; no chunking needed. Cap `--n` in the CLI (see Security).

## Code Examples

### Spawned, plan-independent streams and Sobol draws
```python
# Source: scipy.stats.qmc.Sobol (verified signature/behaviour in scipy 1.18.1), numpy Generator.spawn
def make_streams(rng: np.random.Generator, n_laps: int):
    sc_params, passing, noise, _spare = rng.spawn(4)
    return sc_params, passing.spawn(n_laps), noise

def sobol_pairs(d: int, n: int, child: np.random.Generator) -> NDArray[np.float64]:
    h = (n + 1) // 2
    m = max(1, math.ceil(math.log2(h)))
    u = qmc.Sobol(d=d, scramble=True, rng=child).random_base2(m)[:h]
    return np.concatenate([u, 1.0 - u])[:n]            # antithetic partner; trim odd n
```

### Beta-Binomial SC rate
```python
# Source: standard conjugate update; counts from History.track_status / lap_cutoffs
a0, b0 = 3.0, 297.0                      # mean 1 %, weight 300 laps (~5 races)  [ASSUMED prior]
a, b = a0 + k_deployments, b0 + (n_laps - k_deployments)
rate = a / (a + b)
lo, hi = beta.ppf([0.05, 0.95], a, b)
```

### SC deployment edge rule
```python
prev = None
for status in ts.sort_values(["t_s", "seq"])["status"]:       # per race
    if status == "4" and prev in (None, "1", "2", "6", "7"):
        deployments += 1
    prev = status
```

### Sanity of the pass probability (D-08 test)
`p = 1 / (1 + exp((THR - delta) / SCALE))`; assert `p(+2 s) > 0.99`, `p(0) < 0.2`, and monotone in delta. Constants are `[ASSUMED]` engineering defaults (suggested starting values, to be justified in the DEC: `MIN_GAP_S=0.5`, `THRESHOLD_S=0.3`, `SCALE_S=0.25`, `PASS_COST_S=0.3`, `SC_SLOWDOWN=1.4`, `SC_PIT_RATIO=0.5`, `RESTART_SPACING_S=1.0`, `SC_STOP_WINDOW_LAPS=5`).

### Equivalence of jitted and Python kernel
Run `lap_step.py_func(...)` and `lap_step(...)` on the same small (n=16) inputs and assert array equality (state arrays and clocks); this also gives real line coverage.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Sobol(seed=...)` | `Sobol(rng=...)` | scipy 1.15 | `seed=` will warn; project turns DeprecationWarnings into errors |
| `Sobol.random(n)` any n | `random_base2(m)` for balance | scipy >= 1.7 | avoids the balance UserWarning |
| Heilmeier et al. lap-wise race simulation with probabilistic SC, overtaking, pit models | same structure here | 2020 | method reference only (Appl. Sci. 10(12) 4229); numeric parameters here are not taken from the paper |

**Deprecated/outdated:** global `np.random.*` (banned by ruff NPY002 and the import scan).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Overtaking constants (min gap 0.5 s, threshold 0.3 s, scale 0.25 s, pass cost 0.3 s) | Code Examples | Over/under-passing; wrong finishing spreads (calibrated in Phase 6) |
| A2 | SC pit-loss ratio 0.5, slowdown 1.4, restart spacing 1.0 s, opportunistic window 5 laps | Pattern 1/4 | Documented placeholders from CONTEXT; wrong values shift SC effect size |
| A3 | Prior Beta(3, 297) is a sensible "literature" weak prior | Pattern 4 | Only matters for the first races; the cache gives 1.1%/lap which agrees |
| A4 | GitHub runners are ~1.5-2x slower than the measuring desktop | Pitfall 2 | Budget headroom (4x with Numba) shrinks if runners are slower still |
| A5 | GitHub-hosted Windows runners are not subject to the owner's Application Control policy | Pitfall 1 | CI would fail on import of scipy/numba (not seen in other projects) |
| A6 | Variance ratios of the real model resemble the prototype (1.4-1.9) | Pitfall 8 | Test margin must be re-calibrated on the real implementation |
| A7 | Heilmeier et al. 2020 uses a comparable lap-wise structure | State of the Art | Citation wording only (I did not read the paper's numbers) |

## Open Questions

1. **Shared vs per-car wear draw (D-12).**
   - Known: wear is one shared parameter per compound in the fit.
   - Unclear: whether the owner wants car-level wear scatter in addition.
   - Recommendation: shared per-compound draw (Pitfall 3); log as a refinement of D-12 in DEC-074+.
2. **Where to put "SC laps elapsed" (D-05).**
   - Recommendation: optional `RaceState.sc_laps_elapsed` (default 0); fallback "assume just started".
3. **Borrow rule for unfitted compounds/drivers.**
   - Recommendation: mean of fitted compounds' wear (SE: max of them), field-mean offset for absent drivers; flag in diagnostics and CLI. Needs one DEC entry.
4. **Pace-offset SE plumbing.**
   - Recommendation: `FitReport.driver_offset_se` + `CarState.pace_offset_sd` optional field (precedent DEC-073); update the CAR_KEYS pin in `tests/test_state.py`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 + uv | everything | yes | uv 0.13.5 | — |
| numpy | draws | yes | 2.5.4 (locked) | — |
| scipy | Sobol, norm, beta | no (not in pyproject/uv.lock) | 1.18.1 on PyPI | none; `uv add` (Wave 0) |
| numba | lap kernel | no (not in pyproject/uv.lock) | 0.68.1 on PyPI; JIT ran in a scratch venv | NumPy-only kernel (6.4-7.5 s, not CI-safe) |
| scipy-stubs | mypy strict | no | 1.18.1.1 | `[[tool.mypy.overrides]] ignore_missing_imports` for `scipy.*` (weaker) |
| Local cache `data/f1si.duckdb` | real-data checks | yes | Bahrain 2023 + 69 other in-sample races | tests skip if absent |
| App Control (owner PC) | scipy/numba import | partial: blocked from uv cache path, OK in a normal venv | — | run in `.venv`; CI unaffected |

**Missing dependencies with no fallback:** scipy (Sobol is required by D-13/SIM-03).
**Missing dependencies with fallback:** numba (NumPy path exists but fails the CI budget).

## Validation Architecture

`workflow.nyquist_validation` is enabled (key present and true in `.planning/config.json`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1 + hypothesis 6.170, mypy strict, ruff 0.17.1 |
| Config file | `pyproject.toml` (`[tool.pytest]`, `-m "not network"`, `--strict-markers`) |
| Quick run command | `uv run python -m pytest tests/sim tests/regime tests/conformance -x -q` |
| Full suite command | `uv run ruff check . ; uv run ruff format --check . ; uv run python -m mypy ; uv run python -m pytest` |
| Estimated runtime | about 60-90 s (benchmark ~3 s + VR test ~5-10 s) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIM-01 / SC1 | Bahrain-like `RaceState` -> finishing distribution for a driver; rows are permutations; shapes | integration (synthetic long race) | `uv run python -m pytest tests/sim/test_simulate_state.py -x` | Wave 0 |
| SIM-01 / SC1 | Real Bahrain 2023, ALO distribution sums to 1 (opt-in) | integration (`network`) | `uv run python -m pytest -m network tests/real/test_simulate_bahrain.py` | Wave 0 |
| SIM-01 | Simulator passes the backend conformance suite (registered in `SIMULATORS`) | conformance | `uv run python -m pytest tests/conformance -x` | extend `registry.py` |
| SIM-01 | Pass probability monotone in pace gap; huge gap ~1; equal pace small (D-08) | unit | `uv run python -m pytest tests/sim/test_overtaking.py` | Wave 0 |
| SIM-01 | Kernel jitted == `py_func` on small input; hand-computed 2-car case (no noise) | unit | `uv run python -m pytest tests/sim/test_kernel.py` | Wave 0 |
| SIM-01 | Forced plan followed exactly (stop laps, pit loss paid); other cars' draws unchanged (CRN): same seed, different forced plan -> other drivers' noise/params/SC identical | unit/property | `uv run python -m pytest tests/sim/test_crn_and_plans.py` | Wave 0 |
| SIM-01 | Follower `laps_done = lap-1` catch-up lap equals hand calculation; retired car placed last; unfitted compound/driver borrowed and listed | unit | `uv run python -m pytest tests/sim/test_state_start.py` | Wave 0 |
| SIM-02 / SC2 | 50,000 x 20 x 57 under 10 s, warm-up excluded | benchmark | `uv run python -m pytest tests/sim/test_benchmark.py` | Wave 0 |
| SIM-03 / SC4 | Variance of mean finish (and total time, SC share) lower with Sobol+antithetic at equal N over R>=100 seeds | statistical | `uv run python -m pytest tests/sim/test_variance_reduction.py` | Wave 0 |
| SIM-03 | `draws.py`: Sobol uses `rng=`, powers of 2, no UserWarning (`-W error::UserWarning`), antithetic pairs sum to 1, odd N trims | unit | `uv run python -m pytest tests/sim/test_draws.py -W error` | Wave 0 |
| D-15 / SC5 | Same seed -> identical arrays; different seeds differ; rng not mutated beyond spawn | unit | `uv run python -m pytest tests/sim/test_reproducibility.py` | Wave 0 |
| REG-01 | Estimator recovers known SC rate from synthetic history within its 90% interval; prior-only for first race; median duration fallback to 4 with < 5 events | unit | `uv run python -m pytest tests/regime/test_sc_rate.py` | Wave 0 |
| REG-01 / D-06 | Simulated SC frequency over many races matches input rate (binomial tolerance) | statistical | `uv run python -m pytest tests/sim/test_sc_frequency.py` | Wave 0 |
| REG-01 | Rate function ignores the future (scramble consumer) | property | `uv run python -m pytest tests/guards` | extend `consumers.py` |
| SC3 | In races with SC: restart gaps equal the spacing constant; stop under SC pays `pit_loss["sc"]` not green; order frozen on SC laps | unit (rate=1.0 forcing, `record_gaps`) | `uv run python -m pytest tests/sim/test_safety_car.py` | Wave 0 |
| D-05 | Builder sets `regime {"sc":1.0}` and `pit_loss_s["sc"]` when status "4" is active at cutoff; JSON round-trip | unit | `uv run python -m pytest tests/test_state_builder.py tests/test_state.py` | update existing |
| D-06 | Synthetic generator `sc_laps` emits "4" rows and keeps default fixtures byte-identical | unit | `uv run python -m pytest tests/test_synthetic.py` | extend |
| D-16/D-17 | `f1si simulate` prints state, SC source ("prior only"), plan sources, P1..Pn, runtime; hindsight label; refuses unidentified fit; writes PNG | integration | `uv run python -m pytest tests/test_cli_simulate.py` | Wave 0 |
| D-16 | PNG data/figure/file-name (slug safety) | unit | `uv run python -m pytest tests/plots/test_simulate_plot.py` | Wave 0 |
| D-20 / FND-04 | Explainer headings/module tour, README needles, DEC format, `MIN_ENTRIES` bumped | unit | `uv run python -m pytest tests/test_docs.py tests/test_decisions_log.py` | update |

### Sampling Rate
- **Per task commit:** `uv run python -m pytest tests/sim tests/regime -x -q` and `uv run python -m mypy`
- **Per wave merge:** full suite command
- **Phase gate:** full suite green locally and on CI (Ubuntu + Windows) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `uv add scipy numba`, `uv add --dev scipy-stubs`, lock committed, import smoke check from `.venv`
- [ ] `tests/sim/`, `tests/regime/` packages with the files above
- [ ] Synthetic generator `sc_laps` spec (extend `SyntheticRaceSpec`, `SyntheticTruth` with defaulted fields; emit "4" at deployment and "1" at the end, plus race-control messages; SC laps time x1.4) and a conftest fixture building a multi-race SC history with a known rate (test draws its own Bernoulli laps; generator stream unchanged, so existing fixtures stay byte-identical)
- [ ] Update `registry.py` (`SIMULATORS["numpy_sim"]`, a `SimCase` from the long synthetic state), `tests/guards/consumers.py`, `test_state_builder.py`, `test_decisions_log.py::MIN_ENTRIES` (73 -> 73 + number of new DECs), `test_docs.py` README needles
- [ ] Optional: register a `benchmark` marker if the planner wants it deselectable

## Security Domain

Local CLI, no network in this phase, no auth, no secrets. `security_enforcement` is not set to false, so ASVS L1 applies where relevant.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | partial | the as-of door and 2026 lock stay the only data path; `OutOfSampleLockedError` handled like Phase 2 |
| V5 Input Validation | yes | argparse types; slug through `asof.resolve_slug` and `^[a-z0-9-]+$`; `--driver` `^[A-Z]{3}$` and must be in state (`RaceState.car`); `--lap >= 0`; `--n` bounded (e.g. 2 <= n <= 1,000,000, friendly error) to prevent memory exhaustion; `--seed >= 0` via `make_rng`; JSON states only via `RaceState.from_json` (no eval/pickle) |
| V6 Cryptography | no | no randomness for security; seeded PCG64 is for simulation only |
| V12 Files | yes | output path built from validated slug + validated driver code + int lap into the reports dir (`sim_file_name`), never a raw user path; overwrite of the same generated name is intended |
| V14 Config / supply chain | yes | `uv.lock` committed, `uv sync --locked`; numba JIT cache writes to `__pycache__` only |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via slug/driver in PNG name | Tampering | regex-validated components, fixed prefix `sim-`, `Path(reports_dir)/name` |
| Memory/CPU exhaustion via huge `--n` or crafted state with thousands of cars | DoS | cap `--n`; `RaceState` car count bound (e.g. <= 30) in the simulator; reject `laps_total` above a sanity limit |
| Look-ahead leak via History/snapshot | Information disclosure | `History`-only estimator, scramble consumer, import scan (already enforced) |
| Untrusted JSON state | Tampering | `from_json` validation (existing) |
| Supply-chain (new compiled deps) | Tampering | slopcheck run (OK except benign numba heuristic), versions pinned in lock |

## Sources

### Primary (HIGH confidence)
- Local code and data (read in full): `src/f1si/interfaces.py`, `state.py`, `data/asof.py`, `data/_snapshot.py`, `data/schema.py`, `strategy/free_track.py`, `pace/linear.py`, `laps.py`, `synthetic/generator.py`, `plots/wear.py`, `cli.py`, `rng.py`, `tests/conformance/*`, `tests/guards/*`, `tests/conftest.py`, `DECISIONS.md` (DEC-068..073), `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`
- Queries against `data/f1si.duckdb` (read-only): track-status counts and SC deployment/duration statistics; Bahrain 2023 states at laps 0/15/30/40
- Scratch-venv experiments (scipy 1.18.1, numba 0.68.1, numpy 2.5.4, Python 3.12.15): Sobol signature/max dim/warning/reproducibility; NumPy vs Numba timings; mypy strict with scipy-stubs; variance ratios
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html (rng keyword since 1.15.0, random_base2 balance)
- PyPI JSON for scipy, numba, scipy-stubs; slopcheck 0.6.1 results

### Secondary (MEDIUM confidence)
- https://www.mdpi.com/2076-3417/10/12/4229/html (Heilmeier et al. 2020, Appl. Sci. 10(12) 4229): structure of lap-wise probabilistic race simulation; numeric parameters not read

### Tertiary (LOW confidence)
- Numeric overtaking/SC constants (engineering defaults, assumptions A1-A2)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions resolved and executed locally; the only uncertainty is the owner-PC policy and CI-runner speed
- Architecture: HIGH for performance and layout (measured), MEDIUM for fidelity of the pass/SC model (defaults)
- Pitfalls: HIGH - each came from reading code or running it against the real cache
- Variance reduction margin: MEDIUM - prototype only, must be re-measured on the real simulator

**Research date:** 2026-11-12
**Valid until:** 2026-12-12 (stable libraries; re-check scipy/numba pins if the lock is bumped)
