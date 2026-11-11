# Phase 2: Interfaces, Linear Tire Wear & Free-Track Optimizer - Research

**Researched:** 2026-11-11
**Domain:** typed Protocols (mypy strict), joint fuel/wear OLS on F1 lap times, brute-force pit-plan enumeration, immutable shared state
**Confidence:** HIGH on repo facts and on the Bahrain numbers (run against the local cache in this session); MEDIUM on literature ranges and general Python typing behaviour (training knowledge, flagged below)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
D-01 to D-18 are locked (D-10 to D-18 are "Claude's pick" and equally binding). Condensed here; the full text is in `02-CONTEXT.md` and the planner must read it.

- **D-01** Joint OLS over clean laps: `t(d,L) = alpha_d + fuel*(L-1) + wear[c]*age + eps`. `age` = tyre age at END of lap. Per-driver intercept. Docstring must state why fuel and wear separate (age resets at a stop, lap number does not). Report fuel beside the literature range (about -0.03 to -0.06 s/lap). No fixed-constant fallback: if fuel is not identified, say so. Model form identical to `f1si.synthetic.generator`; recovery test must recover `fuel_effect_s_per_lap` and `wear_rate_s_per_lap` from `SyntheticTruth`.
- **D-02** Clean laps = exactly what `_fade_reason` fades (lap 1, pit in, pit out, SC/VSC/red), then a robust (MAD) outlier rule (suggested > 3 robust SD). Move the fade rule to a shared module so plot and fit cannot drift. Report laps dropped and why. Threshold logged in DECISIONS.md.
- **D-03** Fit scope is one race at any cutoff, takes a `RaceSnapshot`. Compound with too few clean laps => "not enough data", no estimate. Minimum at Claude's discretion, logged.
- **D-04** Per-driver intercept, shared per-compound slope, SE and 95% interval per compound. That SE fills `RaceState.cars[].wear_sd`.
- **D-05** Pit loss = median over visible green-flag stops of `(in-lap + out-lap) - two predicted clean laps`; report spread; documented flagged default when no stops visible; SC/VSC stops excluded.
- **D-06** Real rules: at least two different dry compounds used (counting those already used); start tyre and start age fixed to actual; minimum stint length (suggested 5, logged); only compounds with a fitted wear rate are candidates; wet/intermediate stints for the driver => refuse with clear message.
- **D-07** Optimizer plans from any lap's `RaceState` (current lap, compound, tyre age, stops done, compounds used). Free track: total = sum of predicted lap times + pit losses.
- **D-08** Plans are per driver (`--driver ALO`). Default driver: race winner at `RACE_END`; leader at lap N mid-race.
- **D-09** `PaceModel` is vectorized and returns mean and SD per lap (Normal); no sampling inside the model.
- **D-10** Linear fit IS a `PaceModel`; fitting is a separate function `RaceSnapshot -> fitted model`. Optimizer IS a `StrategyPolicy`, returns a pit decision with the best plan attached. `SimulatorBackend` is Protocol only; its suite runs on a minimal conforming test double.
- **D-11** One parametrized suite per Protocol driven by a registry; structure + behaviour checks (shapes/dtypes, finite, no mutation of input RaceState, same input+seed => same output, decision obeys rules); a planted non-conforming stub with a meta-test asserting the suite fails it.
- **D-12** `RaceState` carries all cars as frozen plain data in the BUILD_PLAN shape; JSON round-trip test; internal layout at Claude's discretion.
- **D-13** Unmodeled fields get honest placeholder values: `regime = {"green": 1.0}`, `pit_loss_s` only `green`; placeholders documented, never silently invented.
- **D-14** One pure builder `RaceSnapshot + fitted PaceModel -> RaceState`; gaps/positions from the snapshot (DEC-042 semantics).
- **D-15** `uv run f1si wear bahrain-2023 [--lap N]` table + `reports/wear-bahrain-2023.png` (static matplotlib, no pyplot).
- **D-16** `uv run f1si plan bahrain-2023 --driver ALO [--lap N]`: best 1-stop, best 2-stop, top 5, one "compared against" line for the actual strategy.
- **D-17** Actionable, PowerShell-copy-pasteable error messages; unknown driver lists valid codes.
- **D-18** `docs/explained/phase-02.md` in the Phase 1 D-17 format; `tests/test_docs.py` keeps it complete.

### Claude's Discretion
Regression method (OLS lstsq + classical SEs enough; robust SEs optional), outlier threshold, minimum clean laps per compound, minimum stint length, default pit loss (each logged in DECISIONS.md); module names and layout (suggested `f1si/interfaces.py`, `f1si/state.py`, `f1si/pace/linear.py`, `f1si/strategy/free_track.py`, shared clean-lap module; must register with import-ban policy and scramble registry); brute-force mechanics; hypothesis property tests encouraged.

### Deferred Ideas (OUT OF SCOPE)
Per-driver wear slopes (Phase 4/7); cross-race pooling / priors (Phase 7); free starting-tyre choice; 3-stop and wet strategy; tyre cliff and track-evolution terms; regime-dependent pit loss (Phase 8). Also out of this phase: Monte Carlo, overtaking, SC probability, Kalman, LSM/CVaR, replay loop.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INT-01 | `interfaces.py` with `PaceModel`, `StrategyPolicy`, `SimulatorBackend` | Protocol patterns, mypy-rejection trick, NDArray typing (Architecture Patterns 1-2) |
| INT-02 | Shared test suite across implementations | Check-function + registry + meta-test pattern (Pattern 3), Validation Architecture |
| INT-03 | Shared `RaceState` | Layout, JSON round trip, builder, `laps_total` problem (Pattern 4, Pitfalls 6-7) |
| PAC-01 | Fuel-corrected lap times, linear wear per compound | Identifiability findings and measured Bahrain numbers (Pattern 5) |
| PAC-02 | Brute-force best 1/2-stop plan | Closed-form stint cost, enumeration rules, edge cases (Pattern 6) |
</phase_requirements>

## Summary

Phase 1 left a clean surface: `RaceSnapshot` is plain pandas data; the clean-lap rule exists only as a private `_fade_reason` in `plots/stints.py`; the synthetic generator already uses exactly the D-01 model. Nothing in the repo yet declares Protocols, a `RaceState`, a fit, or an optimizer. No new third-party package is needed (NumPy and pandas suffice; SciPy is NOT installed and is not needed). I ran the proposed regression on the real Bahrain 2023 cache through the public as-of door and on synthetic races, so the numbers below are measured, not assumed.

Four findings change the plan and need explicit handling. (1) The D-01 model has no per-compound pace offset, so on real Bahrain data SOFT and HARD come out with essentially the same wear slope (0.125 vs 0.121 s/lap) and the optimizer cannot know soft is faster per lap; plan rankings between compounds are then driven by noise-level differences. (2) A pre-race (lap 0) plan cannot be fitted from this race's own data under D-03 (a lap-0 snapshot has no laps); `plan` needs a stated policy (see Open Questions). (3) `races.scheduled_laps` is NULL for every cached race, so `laps_total` cannot come from `RaceInfo`. (4) `tests/test_docs.py` is hard-wired to `phase-01.md` and requires its tour to name EVERY module under `src/f1si`, so adding Phase 2 modules breaks it until that test is generalised.

**Primary recommendation:** Build `clean-lap module -> LinearPaceFit (PaceModel) -> RaceState builder -> FreeTrackOptimizer (StrategyPolicy, PaceModel injected via constructor) -> CLI`, with closed-form stint costs, a rank-based identification check that names which parameters are unidentified, and conformance suites written as plain check functions so a meta-test can prove they reject a bad stub.

## Architectural Responsibility Map

This is a single-process Python library plus CLI; the web tiers do not apply. Tiers used instead:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Reading race data at a cutoff | Data door (`f1si.data.asof`) | CLI driver | Only the door and the CLI may hold the accessor; models get `RaceSnapshot` only |
| Clean-lap classification | Shared pure module (new) | plots, pace | One rule for plot and fit (D-02) |
| Wear/fuel fit | Pace layer (`f1si.pace.linear`) | — | Pure function `RaceSnapshot -> LinearPaceFit` |
| Pit-loss measurement | Pace layer | State builder | Needs fitted model; value stored on `RaceState` |
| `RaceState` build | State layer (`f1si.state`) | — | Pure function; single type consumed downstream |
| Plan enumeration | Strategy layer (`f1si.strategy.free_track`) | — | Receives `RaceState` + `PaceModel`; never sees accessor |
| `laps_total`, default driver, actual-strategy comparison | CLI/replay driver | — | Need `RACE_END` or other whole-race facts; only drivers may use them |
| Tables and PNG | CLI + plots | — | Presentation only |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | >=2.3,<3 (already pinned) | lstsq, SVD rank, vectorized enumeration | Already the project's numeric base [VERIFIED: pyproject.toml] |
| pandas | >=2.3.3,<3 (pinned) | snapshot frames | Snapshot types are DataFrames [VERIFIED: src/f1si/data/_snapshot.py] |
| matplotlib | >=3.11,<4 (pinned) | wear PNG via `Figure` API | Same as stint plot, no pyplot [VERIFIED: pyproject.toml, plots/stints.py] |
| typing.Protocol / dataclasses / json | stdlib | interfaces, frozen state, round trip | No dependency needed |

### Supporting (dev, already pinned)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=9.1 | parametrized suites | conformance + recovery tests |
| hypothesis | >=6.170 | property tests | "total time >= N x min lap", closed form == loop, JSON round trip |
| mypy | >=2.4 strict | Protocol acceptance | also proves rejection (see Pattern 2) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| NumPy lstsq + hand-written SE | statsmodels | Not installed; extra heavy dependency for ~20 lines of algebra |
| Normal 1.96 for 95% CI | `scipy.stats.t.ppf` | SciPy absent; with df ~ 900 the difference is < 0.1%. Require df >= 30 else "not enough data" and log it (DEC) |
| Per-driver dummy columns | Within-driver demeaning (Frisch-Waugh) | Demeaning is numerically nicer and cheaper for 20 drivers, but per-driver dummies make intercepts directly available for pace offsets; keep dummies (23 columns is tiny) |

**Installation:** none. `uv sync --locked` is sufficient. Do NOT add statsmodels/scipy for this phase.

**Version verification:** versions above are the project pins in `pyproject.toml`; `uv run python -c "import scipy"` fails (SciPy not installed) [VERIFIED: run in this session]. No new package is recommended, so no registry check is required.

## Package Legitimacy Audit

No external packages are installed by this phase. Table intentionally empty.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | — | — | — | — | n/a | No install |

**Packages removed due to slopcheck [SLOP] verdict:** none. **Packages flagged [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
 CLI (only module allowed AsOfAccessor / RACE_END)
   |  resolve slug -> race_id ; AsOf(race_id, N | RACE_END)
   v
 AsOfAccessor.snapshot(at) ----> RaceSnapshot (plain pandas, no accessor)
   |                                   |
   |  laps_total, default driver,      +--> clean_laps(snapshot)  [shared module, also used by plots/stints]
   |  actual strategy (RACE_END only)  |        -> CleanLaps (mask + reasons + counts)
   |                                   +--> fit_linear_pace(snapshot) -> LinearPaceFit  (implements PaceModel)
   |                                   |        identifiability check -> params / "not identified: <names>"
   |                                   |        MAD trimming loop, SE, 95% CI, laps dropped by reason
   |                                   +--> measure_pit_loss(snapshot, fit) -> median, spread, n, is_default
   |                                   v
   |                         build_race_state(snapshot, fit, pit_loss, laps_total) -> RaceState (frozen)
   |                                   |            JSON <-> RaceState (BUILD_PLAN shape)
   v                                   v
 FreeTrackOptimizer(pace_model).decide(RaceState, driver) -> PitDecision(+ best plan, ranked plans)
        enumerate (stop laps, compounds) legal plans -> closed-form cost -> sort
        refuse: wet stints, no fitted compound, driver retired, laps remaining too few
   |
   v
 tables to stdout + reports/wear-bahrain-2023.png
 (SimulatorBackend: Protocol only; suite runs on a test double)
```

### Recommended Project Structure
```
src/f1si/
├── interfaces.py          # PaceModel, StrategyPolicy, SimulatorBackend (+ PitDecision/Plan value types if shared)
├── state.py               # CarState, RaceState, build_race_state, to_json/from_json
├── laps.py                # shared clean-lap rule (moved _fade_reason, FADE_TRACK_CODES), CleanLaps
├── pace/
│   ├── __init__.py
│   └── linear.py          # fit_linear_pace, LinearPaceFit (PaceModel), FitReport, measure_pit_loss
├── strategy/
│   ├── __init__.py
│   └── free_track.py      # FreeTrackOptimizer (StrategyPolicy), Plan, enumerate/price
└── plots/wear.py          # fuel-corrected lap time vs age, one panel per compound
tests/
├── conformance/           # suites + registry + planted stub + meta-test
├── pace/test_linear_fit.py, test_clean_laps.py
├── strategy/test_free_track.py
└── test_state.py, test_cli_wear_plan.py
```
`plots/stints.py` keeps importing `_fade_reason` behaviour from `f1si.laps` (re-export under the old private name or update the import and tests; `tests/plots/test_stint_plot.py` exercises fade classes).

### Pattern 1: Typed Protocols with NumPy arrays under mypy strict
**What:** Use `typing.Protocol` with `numpy.typing.NDArray[np.float64]` / `NDArray[np.int64]` / `NDArray[np.str_]` parameters. Mark Protocols `@runtime_checkable` so the registry can do an `isinstance` smoke check. Limit: `isinstance` against a runtime-checkable Protocol only checks that attribute/method NAMES exist, not signatures, dtypes or behaviour (and `issubclass` is not allowed for Protocols with non-method members) [ASSUMED: standard typing-module behaviour from training; verify with a 3-line experiment in Wave 0]. Therefore structure checks are necessary but not sufficient; the behavioural suite does the real work.
**Recommended signatures (for the planner to lock):**
```python
# Source: design recommendation; pattern per PEP 544 / typing docs
@runtime_checkable
class PaceModel(Protocol):
    def predict(
        self,
        *,
        driver: NDArray[np.int64],    # driver_number (stable int key; RaceState also carries the code)
        compound: NDArray[np.str_],
        tire_age: NDArray[np.int64],  # age at END of the lap
        lap: NDArray[np.int64],       # 1-based lap number
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:  # (mean_s, sd_s), same shape as inputs
        ...
```
`StrategyPolicy.decide(self, state: RaceState, *, driver: str) -> PitDecision` (no rng needed for the deterministic optimizer, but keep a keyword-only `rng: np.random.Generator | None = None`? Prefer NOT: Phase 5 LSM can take rng in its constructor; avoid forcing an unused parameter into the contract. Log in DECISIONS.) `SimulatorBackend.simulate(self, state: RaceState, plan_or_policy..., n_races: int, *, rng: np.random.Generator) -> ...` must be designed so Phase 3 does not need to change it; keep the return a small frozen result type (finish positions array shape `(n_races, n_cars)` int, total times float). Mark the shape as provisional in the docstring and DECISIONS.
**Driver key choice:** use int `driver_number` in array APIs (vectorizable, matches DB key and the synthetic generator's numbers 10..), keep `driver` (code) in `RaceState` JSON for the BUILD_PLAN shape plus an additive `driver_number`.

### Pattern 2: Prove mypy rejects a non-conforming stub
**What:** In a test module type-checked by CI (`files = ["src","tests"]`), pass a deliberately wrong stub to a Protocol-typed function with a targeted ignore:
```python
def _needs_pace_model(m: PaceModel) -> None: ...
_needs_pace_model(BadStub())  # type: ignore[arg-type]
```
Because `strict = true` enables `warn_unused_ignores`, mypy FAILS if the stub were accepted, so the ignore proves rejection. Conversely, assign each real implementation to a Protocol-typed variable in the same file so non-conformance of real code fails mypy [ASSUMED: strict implies warn_unused_ignores; mypy docs list it under --strict; confirm by running `uv run mypy` once].

### Pattern 3: Conformance suites as plain check functions + registry + meta-test
**What:** Write `check_pace_model(impl)`, `check_strategy_policy(impl, state)`, `check_simulator_backend(impl, state)` as ordinary functions that `assert`. A parametrized pytest test iterates the registry (`PACE_MODELS`, `POLICIES`, `BACKENDS`: dict name -> factory) and calls them. The meta-test calls the same check function with the planted bad stub inside `pytest.raises(AssertionError)` (no pytest-in-pytest). Plant several single-defect stubs (wrong shape, NaN output, mutates input state, nondeterministic, returns illegal compound, missing method) and assert each is rejected, so each behavioural clause is shown to bite. This mirrors Phase 1's `tests/fixtures/leaky_consumer.py` pattern (Phase 1 D-02 style).
**Behaviours to check (D-11):** output shape == input shape, dtype float64, all finite, SD > 0; `predict` pure (calling twice equal; inputs not mutated); `decide` does not mutate `RaceState` (compare `to_json()` before/after and verify arrays read-only), same input gives same decision, decision compound legal (dry, in `compounds` with a fitted rate, satisfying the two-compound rule once plan completes).
**Simulator test double:** a minimal conforming class returning deterministic arrays of the promised shape; enough to prove the suite passes a conformer and fails the stubs.

### Pattern 4: Frozen `RaceState`
**What:** `@dataclass(frozen=True)` for `CarState` and `RaceState`; sequences as `tuple`, not `list`; `regime`/`pit_loss_s` as `Mapping` copied into `types.MappingProxyType` (frozen dataclass does not deep-freeze). Provide `to_arrays() -> CarArrays` returning read-only (`arr.flags.writeable = False`) struct-of-arrays (driver_number int64, position int64, gap_ahead float64 with NaN for none, compound as `np.str_`, tire_age, wear_rate, wear_sd, pace_offset, stops_done) built on demand. Phase 3's simulator uses the arrays; JSON stays the list-of-cars shape. Equality: keep default dataclass `eq` on tuple-of-records (no arrays as fields, so `==` works and hypothesis round-trip asserts are trivial).
**JSON:** `to_json_dict()` / `from_json_dict()` with `json.dumps(..., allow_nan=False)`; unidentified values (wear for a compound with no data, first car's `gap_ahead_s`) are `None`, never NaN. Round trip test: `from_json(to_json(s)) == s` and the output matches BUILD_PLAN keys exactly (`lap, laps_total, regime, pit_loss_s, cars[driver, position, gap_ahead_s, gap_behind_s, compound, tire_age, wear_rate_s_per_lap, wear_sd, pace_offset_s, stops_done, compounds_used]`) plus clearly documented additive keys only if needed.
**Planning-sufficiency problem:** BUILD_PLAN carries ONE `wear_rate_s_per_lap` per car (its current compound). The optimizer also needs rates for compounds the car might switch to. Resolution: inject the `PaceModel` into `FreeTrackOptimizer` at construction; the policy gets pace_offset/tire state from `RaceState` and compound rates through the model. No schema change. (Alternative: add a race-level `compound_wear` map; rejected here because D-12 wants a stable field set.) Log in DECISIONS.
**Gaps and position (D-14):** from `snapshot.cars` (`position`, `laps_done`, `last_lap_end_s`; leader N laps, others <= N-1, DEC-042). A gap is only well defined between cars with the same `laps_done`; for lapped or `laps_done`-different neighbours compute from `last_lap_end_s` differences only if laps_done equal, else store `None` and document. `position` is `Int64` with NA for cars without a finished lap (lap 0): map NA to None/absent; a lap-0 RaceState has no positions (use grid position from `entries.grid_position` if present, documented as such, or leave None).

### Pattern 5: Joint fuel/wear OLS (D-01)
**Design matrix** (per clean lap i): one dummy column per driver present, one fuel column `L-1`, one column per compound `c` equal to `age` where compound == c else 0. Solve with `np.linalg.lstsq`.
**Identification (measured):**
- Within a single stint `age = L + const`, so fuel and the compound's wear are perfectly collinear *from slopes alone*. They separate only through the SHARED per-driver intercept: stint 1 and stint 2 of one driver have a level difference that depends on wear*start-age offsets, not on fuel. This means identification rests on "no stint-level effects other than tyre age". Document this in the docstring; it is also why the fuel estimate absorbs track evolution and any common drift (see below).
- Practical rank rule: build X, compute `np.linalg.matrix_rank(X)` (SVD) after every column cleanup. If `rank < ncols`, take the SVD null-space vectors (`Vt[rank:]`); parameters with |loading| above a small tolerance on any null vector are the unidentified ones; report them by NAME ("fuel effect", "HARD wear") and refuse to report them. Also guard `cond(X)` > ~1e8 as near-singular.
- Measured on Bahrain 2023 (cache, as-of door):
  - cutoff 8: rank 22 of 23, fuel/HARD collinear (only 5 HARD laps), garbage numbers (fuel -29.5, SE 6.7e5) if not trapped.
  - cutoff 15: 14 drivers already have >= 2 stints; first stops occur at lap 9 or later, so cutoff <= ~9 has no multi-stint driver (stint counts: cutoff 5 and 10 give 0 drivers with 2 stints; 15 gives 14; 20 gives 19).
  - cutoff 30: fuel -0.0947 (SE 0.0038), HARD 0.136 (0.0080), SOFT 0.152 (0.0061) before trimming; fully identified.
  - RACE_END (MEDIUM removed, 3-MAD iterative trim, classical SE): fuel **-0.0778** (SE 0.0013, HC3 0.0015), HARD **0.1213** (SE 0.0039, HC3 0.0040; 504 laps), SOFT **0.1246** (SE 0.0041, HC3 0.0047; 371 laps); 20 drivers, 875 laps kept of 916 clean, 22 columns, cond ~334; residual SD ~0.86 s before trimming, MAD ~0.44.
  - HC3 vs classical SE differ by < 15%: classical is adequate; log "HC3 optional".
- **Fuel outside the literature range:** -0.078 s/lap at RACE_END (and -0.095 at lap 30) is steeper than the -0.03..-0.06 sanity range. Likely cause: track evolution/rubbering-in and cooling are common to all cars and indistinguishable from lap number, so they load onto "fuel" (track evolution is explicitly deferred). The CLI should print the range beside the estimate and a plain note "outside the literature range; includes any track-evolution gain" rather than hide it. [CITED: range from CONTEXT.md D-01; the explanation is analysis, tag as ASSUMED until a second race shows the same bias]
- **No per-compound pace offset in D-01.** Adding a HARD dummy gave HARD offset +0.256 s (SE 0.13), wear SOFT 0.148 / HARD 0.121, rank 24 of 24 — weakly identified and still far below the ~0.5 s a real soft-hard gap would be. Without it SOFT (0.125) and HARD (0.121) are statistically indistinguishable, so the optimizer sees almost no reason to prefer soft early or hard late. See Open Question 1.
- **MEDIUM at Bahrain 2023** has 10 laps (one stint, driver 4 laps 28-37): too few => "not enough data" (D-03). Choose a minimum such as 30 clean laps AND >= 2 distinct stints/drivers per compound AND residual df >= 30; log. Candidates for the optimizer on Bahrain 2023 are therefore SOFT and HARD only. Stints 4 compounds: HARD 34 stints, SOFT 35, MEDIUM 1.
**Outlier rule (D-02):** iterate: fit, residuals `r`, `sigma = 1.4826*MAD(r)`, drop `|r - median(r)| > k*sigma` (k = 3), refit, repeat until nothing is dropped or 5 iterations. Rebuild the design matrix EVERY iteration (drop all-zero driver/compound columns, re-check minimum laps per compound and identification) — a prototype that reused dummies failed with `LinAlgError: Singular matrix` because trimming left a column empty. Bahrain RACE_END: 28 + 4 + 1 laps trimmed (3.6% of 916). Using the joint-fit residual (driver intercept + fuel + wear) satisfies "driver's stint trend" more simply than per-stint trends.
**Report object (`FitReport`):** params with SE/CI/n_laps per compound, fuel with SE/CI and literature range flag, per-driver intercepts, `n_clean`, `n_trimmed`, `dropped` Counter by reason (`lap 1`, `pit in`, `pit out`, `safety car/VSC/red`, `outlier`, `no lap time`), `unidentified: tuple[str,...]`, `not_enough_data: tuple[str,...]`, `df_resid`, `sigma` (residual SD for `PaceModel` SD output).
**Pace offsets:** `pace_offset_s` for driver d = `alpha_d - mean(alpha)`; (BUILD_PLAN example is negative = faster). Define and document the reference (field mean over drivers with enough laps) and note intercepts also contain each driver's lap-time level over their clean laps.
**`PaceModel` mean/SD:** mean = `alpha_d + fuel*(L-1) + wear[c]*age`; SD = fit residual SD (single homoskedastic value, vectorized `np.full_like`). Unknown driver/compound or unidentified parameter => raise `ValueError` naming it (no silent NaN); a driver with no fitted intercept: raise, do not guess.

### Pattern 6: Brute-force enumeration (D-05..D-08)
**Closed-form stint cost.** For a stint on compound `c`, driver intercept `a`, covering laps `L1..L2` (inclusive), first lap age `g` (age at end of lap L1):
`cost = n*a + fuel*sum(L-1) + w_c*sum(age)` with `n = L2-L1+1`, `sum(L-1) = n*(L1+L2-2)/2`, `sum(age) = n*g + n*(n-1)/2`. O(1) per stint, so the whole search is a few thousand to ~10^5 evaluations; plain Python loops are acceptable (<1 s), NumPy vectorization optional. Write a slow reference lap-by-lap `price_plan_slow` and hypothesis-test equality with the closed form.
**Conventions to fix (log in DECISIONS):**
- State at lap N means the car has completed N laps (for the leader; DEC-042 others N-1). Plan decisions are about laps `N+1 .. laps_total`. A stop at "lap k" means lap k is the in-lap and lap k+1 is the out-lap on fresh tyres with age 1 (matches `rebuild_pit_events`: `in_lap = out_lap - 1`; synthetic: out-lap `tyre_life = 1`). "Pit now" = `k = N+1`.
- Lap cost used in the total: model-predicted CLEAN lap for every lap; each stop adds `pit_loss` (which by D-05 is already `in-lap + out-lap - 2 clean predicted`). Do not also add model terms for in/out laps.
- Current stint: first lap age = `tire_age_now + 1`; starting age for a lap-0 plan is `start_tyre_age + 1` (Bahrain: start_tyre_age 3 for used softs; first lap `tyre_life` = 4 in data).
- Candidate number of additional stops `r` so total stops T in {1,2}: `r = T - stops_done`; if `stops_done >= 2` only `r = 0` (report as "no further stop"), if `stops_done = 1` then `r in {0,1}`; for `stops_done = 0`, `r in {1,2}`. (A 0-stop plan is only legal if the two-compound rule is already satisfied.) Output labels: best 1-stop, best 2-stop where T is TOTAL stops.
- Min stint length (suggest 5, logged) applies to every NEW stint and to the final stint; also require the current stint to run at least 1 more lap before a stop (`k >= N+1`). The already-running stint is exempt from the minimum (e.g. a car 3 laps into a stint may legitimately pit).
- Two-compound rule: `len(set(compounds_used) | set(plan compounds)) >= 2` over DRY compounds only; stints on a non-fitted compound are excluded; the starting compound is fixed.
- Search size at lap 0, 57 laps, 2 fitted compounds: 1-stop <= 52 stop laps x 2 compounds; 2-stop <= C(~45,2)=~1000 x 4 compound pairs: ~4-5k plans total. With 3 fitted compounds ~9k. [VERIFIED by arithmetic]
- **Ties:** with near-identical slopes (SOFT 0.125, HARD 0.121) many plans differ by < 0.1 s. Rank deterministically (total time, then fewer stops, then earlier first stop, then compound alphabetical) so output and the "same input => same output" contract are stable, and print "gap to best" so near-ties are visible. Do not claim a unique optimum.
- **Free-track is a lower bound:** unrealistically ignores traffic, SC, overtaking — say so in output and explainer.
**Edge cases to test:** driver already stopped twice; laps remaining < min stint (no stop possible; only the no-stop plan if legal, else refuse with message); laps remaining 0 (race over); driver retired (`cars.laps_done < lap` below the field and no more laps visible — detect and refuse); driver's visible stints include INTERMEDIATE/WET => refuse (D-06; entries contain 107 INTERMEDIATE and 2 WET starters in the cache so this path is reachable); `start_compound` NULL (12 entries in the cache) or `compound` NULL laps (100 laps in 2023) => use the first visible stint's compound, else refuse with a clear message; pit-lane starter (`pit_lane_start`) fine; compound with no fitted rate in `compounds_used` is allowed as history but never as a candidate.

### Pit loss (D-05) — measured
Implementation: for each pit event (`snapshot.pit_events` has `driver_number, in_lap, out_lap, pit_duration_s`), take the in-lap and out-lap rows from `snapshot.laps`, require both lap times present, both compounds fitted, driver has an intercept, and **both laps free of SC/VSC/red status**. NOTE: `_fade_reason` returns `"pit in"`/`"pit out"` BEFORE it checks track status, so it cannot tell a green stop from an SC stop; the shared module must expose a separate predicate (e.g. `slow_status(track_status) -> bool` using `FADE_TRACK_CODES`) and the pit-loss code must call it. `pit_loss = lap_in + lap_out - sum(pred clean laps)` using the lap's own compound and tyre_life.
Bahrain RACE_END (48 usable stops): median **24.9 s**, SD 7.7 s, 10-90% range 23.6-43.5 s; distribution is bimodal (bulk 22.4-27.4 s; a tail 29-48 s from slow stops/VSC around race-clock 4000 s/unflagged slow laps). Use the MEDIAN and report IQR/10-90%, not the SD. `pit_duration_s` is ~25 s (pit-lane time) and agrees with the median, a useful cross-check but not the definition.
Default when no stop is visible (cutoff <= 8 at Bahrain): Claude's discretion; recommend a documented constant 22.0 s labelled `is_default=True` and shown as "default (no stops seen yet)" [ASSUMED value; the BUILD_PLAN illustration uses 22.1 s; Bahrain measured 24.9 s]. Log in DECISIONS.

### Anti-Patterns to Avoid
- **Reusing one-hot columns after trimming:** produces zero columns and a singular matrix (observed). Rebuild each iteration.
- **Letting lstsq silently return a minimum-norm answer** when rank-deficient: it returns plausible-looking but meaningless numbers (observed fuel -29.5). Always check rank and refuse.
- **Importing `RACE_END`/`AsOfAccessor` in `state.py`, `pace/`, `strategy/`:** the import ban and `test_only_the_drivers_name_the_accessor` (allows only `f1si.cli`, `f1si.data.asof`, `f1si.data._snapshot`) fail the build.
- **Computing `laps_total` from the snapshot max lap at a mid-race cutoff:** it would equal the cutoff (look-ahead-free but wrong).
- **Pretending the lap-0 plan is fitted from lap-0 data.**
- **NaN in JSON** (invalid JSON; `allow_nan=False`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Least squares / rank / conditioning | normal-equation solver, custom QR | `np.linalg.lstsq`, `np.linalg.matrix_rank`, `np.linalg.svd` | Numerically safe, rank-aware |
| Robust scale | std-based thresholds | `1.4826 * median(|r - median(r)|)` (MAD) | Std is inflated by the very outliers being removed |
| Run-time structural interface checks | custom ABC registries | `typing.Protocol` + `runtime_checkable` + behaviour checks | Matches later plug-ins |
| Immutable containers | custom freeze logic | `@dataclass(frozen=True)`, tuples, `MappingProxyType`, `arr.flags.writeable=False` | Standard |
| Property testing | hand-built random loops | `hypothesis` (already a dev dependency) | Shrinking, reproducible |
| RNG | any new generator | `f1si.rng.make_rng` + keyword-only `rng` | FND-03; import ban forbids `default_rng` elsewhere |
| Per-stint cost loops in the hot path | repeated lap loops | closed-form arithmetic-series cost (keep a slow reference for tests) | Exact and O(1) |

**Key insight:** the fit is 20 lines of linear algebra; the risk is not the algebra but identifiability, bookkeeping of conventions (age at end of lap, in-lap/out-lap), and honest reporting of what the data cannot say.

## Runtime State Inventory

Not a rename/refactor/migration phase. Skipped. (One adjacent note: moving `_fade_reason` out of `plots/stints.py` changes an internal import; `tests/plots/test_stint_plot.py` and `tests/guards/consumers.py` reference `prepare_stint_plot_data`, not `_fade_reason` directly — grep before moving.)

## Common Pitfalls

### Pitfall 1: Silent non-identification
**What goes wrong:** early cutoffs (Bahrain <= ~lap 9: no completed stops, so no driver has two stints) or a compound with one driver give a rank-deficient X; lstsq returns finite nonsense.
**Why:** within a stint age = lap + const, fuel and wear collinear without a second stint on the same driver intercept.
**How to avoid:** rank/SVD check, name unidentified parameters, refuse; never fall back to a constant (D-01).
**Warning signs:** `matrix_rank < ncols`, SE of 1e5, |fuel| > 1.

### Pitfall 2: Trimming empties a column
**What goes wrong:** `LinAlgError: Singular matrix` after outlier removal (observed at RACE_END and cutoff 15).
**How to avoid:** rebuild the design each loop; drop drivers/compounds that fall below minimum laps and recheck identification inside the loop.

### Pitfall 3: Pit laps under SC treated as green
**What goes wrong:** `_fade_reason` hides the SC flag behind "pit in/out".
**How to avoid:** separate status predicate; exclude SC/VSC/red stops from the pit-loss median (D-05).

### Pitfall 4: CONTEXT says yellow laps are dropped, code does not
D-02 text lists "SC/VSC/red/yellow laps" but `FADE_TRACK_CODES = {"4","5","6","7"}`: codes "2" (yellow) are NOT faded (Bahrain has 20 laps "1212", 20 "21", 5 "12", 5 "2671" etc.). D-02 also says "drop exactly the laps the stint plot fades". Follow the code (single shared rule; the MAD rule catches yellow-affected outliers). Flag in DECISIONS; if the owner wants yellow dropped it changes the plot too.

### Pitfall 5: Fuel estimate absorbs track evolution
Measured -0.078 s/lap vs literature -0.03..-0.06. Present honestly; do not clamp.

### Pitfall 6: `laps_total` unavailable
`races.scheduled_laps` is NULL for ALL 87 cached races (OpenF1 adapter hard-codes `scheduled_laps=None`, `openf1.py:260`); `RaceInfo.scheduled_laps` is `None`. At `RACE_END` the max `lap_number` is 57 for Bahrain, but at lap N the snapshot only reaches N. Options: (a) CLI (a driver, allowed RACE_END) reads the race distance from a RACE_END snapshot's max lap and passes `laps_total` to the builder explicitly, logged as "race distance is public pre-race knowledge; read from the completed race"; (b) fix the OpenF1 adapter/loader to populate `scheduled_laps` (touches Phase 1 code, scramble tests and cache reload). Recommend (a) with `build_race_state(..., laps_total: int)` required keyword, and note (b) as follow-up. Red-flag-shortened races make "max lap" differ from the scheduled distance; Bahrain 2023 is unaffected.

### Pitfall 7: Lap-0 plan has no data
See Open Question 2.

### Pitfall 8: Docs test tied to Phase 1
`tests/test_docs.py` points at `docs/explained/phase-01.md` only and `test_tour_covers_every_module` requires every non-`__init__` module in `src/f1si` to appear in the Phase 1 tour; `test_readme_commands_and_links` checks README needles. New Phase 2 modules will fail it. Generalise: parametrize over `docs/explained/phase-*.md`, with the "every module" check run against the union of all explainers' tours (or each phase's explainer covers modules newly added in that phase). Add `wear`/`plan` command needles and `docs/explained/phase-02.md` link to README and its test. Keep headings (`## What was built and why`, `## How the pieces connect`, `## File-by-file tour`, `## Interview questions`, `## Good to know`), 3-5 Q&A with answers >= 40 chars.

### Pitfall 9: Guard registration
- `tests/guards/consumers.py` `CONSUMERS` must gain entries for each new function that takes a `RaceSnapshot` and returns derived output (clean-lap mask, fit report, pit loss, `build_race_state`, wear plot data); each consumer is `(db_path, at) -> output` and compared exactly by the scramble test, so outputs must be comparable (DataFrames, dataclasses, tuples, floats; NaN comparisons handled by the scramble comparer — check `tests/guards/scramble.py` for NaN/numpy-array handling before returning arrays; prefer returning dataclasses of Python floats/tuples).
- `DESIGNATED_MODULES` currently `("f1si.data.asof", "f1si.plots.stints")`; add the new snapshot-consuming modules so `test_every_public_function_is_consumed_or_exempt` forces classification; every public function in them must be CONSUMED (a registered consumer calls it by name — the test inspects `consumer.__code__.co_names`) or EXEMPT with a >= 4-word reason. Public functions of `strategy/free_track.py` (takes `RaceState`) need not be designated modules, but if listed they must be classified; simplest: designate only modules whose public functions accept snapshots.
- The scramble test needs a race with a mid-race cutoff and enough data for a fit; synthetic default races are 12 laps with one stop at lap 6/7 — fit identifiable only from cutoff >= ~8-9. Make consumers tolerate "not identified" (return the report with `unidentified` filled) rather than raise, or the scramble run errors on early cutoffs.
- Import ban: new modules may import `RaceSnapshot` from `f1si.data.asof` (not banned). They must not import `_db`, `_snapshot`, `duckdb`, `results`, `out_of_sample`, or use `RACE_END`/`AsOfAccessor`. Only `f1si.cli` (and future `f1si.replay`/`f1si.backtest`) may.
- Ruff selects `E,W,F,I,B,UP,NPY,RUF,SIM,PT,N`; line length 100. Names: `L` as a variable trips `N806` (lowercase function variables) — use `lap`.

### Pitfall 10: Synthetic recovery spec
Default 12-lap/6-driver spec IS identifiable (rank 9/9, one stop at lap 6 or 7) but loose: fuel -0.0303 (SE 0.0153), MEDIUM 0.061 (0.030), HARD 0.077 (0.0136) vs truth -0.03/0.07/0.04. A 57-lap, 20-driver spec recovers tightly: fuel -0.0305 (SE 0.0007), MEDIUM 0.0404 (0.0013), HARD 0.0689 (0.0007) — NOTE: the generator names start compound MEDIUM (true 0.07) and second compound HARD (true 0.04); the sorted-compound output order was HARD, MEDIUM so values map HARD 0.0404 ~ 0.04 and MEDIUM 0.0689 ~ 0.07. Recovery test: tolerance as `|est - truth| < 3*SE` (and a coverage check across ~50 seeds: 95% CI contains truth in roughly 90-100% of seeds) rather than fixed absolute tolerances. Use `make_rng`, spec with `n_laps=57, n_drivers=20`; also `start_tyre_age=3` works (identical accuracy). Remember the generator stops exactly once per driver, so a 2-stop recovery of the optimizer is a synthetic-spec extension question (see Validation).
Also note synthetic `track_status` is NA (VSC only via track_status table); the fit's clean mask uses `laps.track_status` strings, so VSC laps in synthetic data (`vsc_laps`) are NOT flagged by `laps.track_status` (NA). Check how `_fade_reason` tests treat this in `tests/plots/test_stint_plot.py::test_clean_points_have_no_slow_track_status`; VSC-lap synthetic data multiplies lap time by 1.4 and would be caught only by MAD. For the recovery test use specs without `vsc_laps`, or confirm the DB path populates `laps.track_status` from the track_status table (the loader/`derive` does: real Bahrain shows strings like "2671").

## Code Examples

### Rank check naming unidentified parameters
```python
# Source: NumPy linear algebra docs (np.linalg.svd, matrix_rank); design pattern for this phase
u, s, vt = np.linalg.svd(X, full_matrices=False)
tol = s.max() * max(X.shape) * np.finfo(float).eps
rank = int((s > tol).sum())
if rank < X.shape[1]:
    null = vt[rank:]                              # rows span the null space
    bad = np.where(np.abs(null).max(axis=0) > 1e-8)[0]
    unidentified = [names[j] for j in bad]        # e.g. ["fuel", "wear[HARD]"]
```
(For the full-rank case classical SE: `s2 = resid@resid/(n-p)`; `se = sqrt(diag(s2 * inv(X.T@X)))`; 95% CI = est +- 1.96*se; require `n-p >= 30`.)

### Closed-form stint cost
```python
# Sum over laps L1..L2 of alpha + fuel*(L-1) + w*age, first-lap age g
n = L2 - L1 + 1
cost = n * alpha + fuel * n * (L1 + L2 - 2) / 2 + w * (n * g + n * (n - 1) / 2)
```

### Meta-test that the suite rejects a bad stub
```python
@pytest.mark.parametrize("stub", BAD_PACE_STUBS, ids=lambda s: s.__name__)
def test_suite_rejects_bad_pace_stub(stub: type) -> None:
    with pytest.raises(AssertionError):
        check_pace_model(stub())
```

### Pytest-friendly mypy rejection
```python
def _accepts(model: PaceModel) -> None: ...
_accepts(WrongSignatureStub())  # type: ignore[arg-type]   # strict => unused ignore fails mypy
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| ABC base classes for plug-ins | `typing.Protocol` (PEP 544) structural typing | Implementations need not inherit; the shared suite supplies behaviour checks |
| Fixed fuel constant (e.g. 0.03 s/lap) | Fit jointly (D-01) | Honest but only identifiable after stops are visible |
| Legacy `np.random.*` | `np.random.Generator` | Already enforced by ruff NPY002 and import ban |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `runtime_checkable` isinstance checks names only, not signatures/dtypes; issubclass disallowed with data members | Pattern 1 | Suite structure check weaker/stronger than assumed; confirm in Wave 0 with a 3-line test |
| A2 | mypy `--strict` includes `warn_unused_ignores` so an unused `# type: ignore[arg-type]` fails | Pattern 2 | Rejection proof would not bite; verify once with `uv run mypy` on a deliberately accepted case |
| A3 | Track evolution is the cause of fuel -0.078 outside literature range | Pattern 5 | Wrong explanation in docs; wording must say "likely" |
| A4 | Default pit loss 22.0 s | Pit loss | Only used at cutoffs with no visible stops; flagged in output |
| A5 | Minimum thresholds (30 clean laps, df >= 30, min stint 5, MAD k = 3) are reasonable | Pattern 5/6 | Owner may prefer different; all logged as DEC entries |
| A6 | Literature range -0.03..-0.06 s/lap is taken from CONTEXT.md, not independently verified | Pattern 5 | Displayed sanity range could be off; mark as "approximate" in output |

## Open Questions

1. **Per-compound pace offset is missing from D-01.**
   - Known: with D-01's form SOFT 0.125 vs HARD 0.121 s/lap at Bahrain; adding a HARD offset gives +0.26 s (SE 0.13), weakly identified. The optimizer cannot encode that soft is faster per lap, so plan rankings between compounds are near-ties and arguably misleading.
   - Unclear: whether the owner wants the model extended (generator would also need a compound offset to keep the "identical form" and recovery test).
   - Recommendation: implement D-01 as locked; make the output explicitly state "compound pace offsets are not modeled; compound choice among near-ties is not meaningful"; surface to the owner and log as a DECISIONS entry with the measured +0.26 s figure; propose an additive offset term as a candidate for Phase 7 or a Phase 2 amendment.
2. **Lap-0 / pre-race plan has no same-race data under D-03.**
   - Known: lap-0 snapshot has zero laps; CONTEXT D-07 wants "at lap 0 it is the classic pre-race plan"; D-03 forbids pooling.
   - Recommendation: `plan` with `--lap N` fits and prices using only data at N and, if the fit is not identified (N <= ~9 at Bahrain) or N = 0, prints a plain refusal ("not enough laps yet to fit wear; try --lap 20"). With NO `--lap` (default) it uses a whole-race (RACE_END) fit applied to the lap-0 state and labels the result **"hindsight plan: priced with a fit from the whole race"** (no claim of foresight). The builder already accepts snapshot-for-state and model separately, so this needs no extra interface. Needs owner confirmation.
3. **`laps_total` source** (Pitfall 6): recommend CLI passes it; confirm.
4. **Yellow laps** (Pitfall 4): confirm "exactly what the plot fades" overrides the text "yellow".
5. **Position/gap fields at lap 0 or for lapped cars** (Pattern 4): `None` with documentation.
6. **Two-stop synthetic ground truth for the optimizer:** the generator makes exactly one stop per driver, so "optimizer recovers the true best plan" needs either a hand-built analytic case (equal-slope compounds, known pit loss, closed-form optimum) or a generator extension. Recommend the analytic case (no generator change).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | all commands | yes | 0.13.5 | — |
| Python 3.12 | project | yes via uv (`python` shim on PATH is the Windows Store stub; always use `uv run`) | 3.12 | — |
| NumPy/pandas/matplotlib | fit, plots | yes (venv) | pinned | — |
| SciPy | not required | no | — | normal 1.96 |
| Local Bahrain 2023 cache | wear/plan demo, real tests | yes: `data/f1si.duckdb` has 87 complete races incl. `bahrain-2023` (20 drivers, 57 laps, 1058 lap rows) | — | synthetic races (conftest `synthetic_db`) |
| Network | none needed | — | — | — |

**Missing blocking dependencies:** none. Real-data tests must stay out of default CI (existing `tests/real/` uses marker/`network` conventions and rebuilds from the HTTP cache); the default suite should use `synthetic_db`, with an opt-in real test for Bahrain numbers (skip if cache or race absent).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1 + hypothesis 6.170, mypy strict, ruff 0.17.1 |
| Config file | `pyproject.toml` (`[tool.pytest]`, testpaths `tests`, `-m "not network"`) |
| Quick run command | `uv run pytest tests/pace tests/strategy tests/conformance tests/test_state.py -x -q` |
| Full suite command | `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run pytest` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INT-01 | Protocols exist, mypy strict accepts conformers and REJECTS a wrong stub (`# type: ignore[arg-type]` unused-ignore trick) | static + unit | `uv run mypy` ; `pytest tests/conformance/test_protocols.py` | Wave 0 |
| INT-02 | One suite per Protocol over registry; planted stubs (wrong shape, NaN, mutation, nondeterminism, illegal compound, missing method) each fail the suite | unit/meta | `pytest tests/conformance -x` | Wave 0 |
| INT-02 | `LinearPaceFit` passes pace suite; `FreeTrackOptimizer` passes policy suite; simulator test double passes backend suite | unit | `pytest tests/conformance` | Wave 0 |
| INT-03 | `build_race_state` for synthetic (and real Bahrain, skip if absent) at lap 0, mid, last lap; frozen (assign raises `FrozenInstanceError`, arrays read-only); JSON round trip equals and keys match BUILD_PLAN; placeholders documented (`regime == {"green": 1.0}`, `pit_loss_s` only `green`) | unit + hypothesis | `pytest tests/test_state.py` | Wave 0 |
| INT-03 | Builder registered in scramble consumers, equal under future scramble | property | `pytest tests/guards/test_future_scramble.py tests/guards/test_consumer_registry.py` | extend existing |
| PAC-01 | Synthetic recovery: fuel and each compound wear within 3 SE of `SyntheticTruth` on a 57-lap/20-driver spec; CI coverage across seeds | unit | `pytest tests/pace/test_linear_recovery.py` | Wave 0 |
| PAC-01 | Non-identification: cutoff before first stop / single-stint data returns `unidentified` naming fuel/wear (no numbers); compound under minimum laps => "not enough data" | unit | `pytest tests/pace/test_identification.py` | Wave 0 |
| PAC-01 | Clean-lap rule shared: plot fade classes unchanged (existing tests) and fit drop counts by reason; MAD trimming deterministic | unit | `pytest tests/pace tests/plots` | Wave 0 + existing |
| PAC-01 | Real Bahrain: SOFT/HARD ~0.12 s/lap (loose bands, e.g. 0.08-0.17), MEDIUM "not enough data", fuel negative, pit loss median 22-28 s (opt-in, skipped if cache missing) | integration | `pytest tests/real/test_wear_bahrain.py` | Wave 0 |
| PAC-01 | CLI `wear bahrain-2023` prints table and writes PNG; errors actionable (unknown slug, lap too early) | integration | `pytest tests/test_cli_wear_plan.py` | Wave 0 |
| PAC-02 | Closed-form price == slow lap-by-lap price (hypothesis) | property | `pytest tests/strategy/test_free_track.py::test_closed_form_matches_slow` | Wave 0 |
| PAC-02 | Brute force optimality: analytic case with known best plan; best of enumeration <= every enumerated plan; total >= N x min lap; every plan legal (two dry compounds, min stint, start tyre fixed) | unit/property | `pytest tests/strategy/test_free_track.py` | Wave 0 |
| PAC-02 | Edge cases: stops_done=2, laps remaining < min stint, retired driver, wet stint refusal, NULL compound, deterministic tie-breaking | unit | same file | Wave 0 |
| PAC-02 | CLI `plan bahrain-2023 --driver ALO` prints best 1-stop, best 2-stop, top 5, "compared against" line; default driver = winner | integration | `pytest tests/test_cli_wear_plan.py` | Wave 0 |
| UI-03 | `docs/explained/phase-02.md` complete, README mentions `wear`/`plan` | unit | `pytest tests/test_docs.py` | update existing |
| DEC log | New DEC entries (thresholds, conventions) pass `tests/test_decisions_log.py` format | unit | `pytest tests/test_decisions_log.py` | existing |

### Sampling Rate
- **Per task commit:** the quick command for touched dirs plus `uv run mypy`
- **Per wave merge:** full suite command above
- **Phase gate:** full suite green on CI (Ubuntu + Windows matrix) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/conformance/` (suites, registry, planted stubs, meta-tests, simulator double)
- [ ] `tests/pace/` recovery, identification, clean-laps tests
- [ ] `tests/strategy/test_free_track.py`
- [ ] `tests/test_state.py`
- [ ] `tests/test_cli_wear_plan.py`, `tests/real/test_wear_bahrain.py` (opt-in)
- [ ] Update `tests/test_docs.py` for multiple explainers (Pitfall 8) and `tests/guards/consumers.py` (Pitfall 9)
- [ ] A long synthetic spec fixture (57 laps, 20 drivers, no VSC) for recovery; optionally a 2-stop analytic case
- [ ] No framework install needed

## Security Domain

`security_enforcement` is not set in `.planning/config.json` (absent = enabled), but this phase has no network, auth, session, or user-supplied data beyond CLI arguments.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no (look-ahead boundary is enforced by the import ban/scramble tests instead) | register new consumers |
| V5 Input Validation | yes (CLI `--driver`, `--lap`, slug) | validate against `^[A-Z]{3}$` and known codes (reuse `_select_drivers`-style errors), lap >= 0 int, slug through `asof.resolve_slug`; output file name from validated slug only (existing `_SLUG` regexp) |
| V6 Cryptography | no | — |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal in report file name | Tampering | build file name from validated slug, as `plot_file_name` does |
| Look-ahead leak through new modules | Information disclosure (of future rows) | import ban + scramble registration (Pitfall 9) |
| Malformed JSON into `RaceState.from_json` | Tampering | validate keys/types/ranges in `from_json`, raise `ValueError` with a clear message |

## Sources

### Primary (HIGH confidence — verified in this session)
- Repo code read: `src/f1si/data/_snapshot.py`, `asof.py`, `plots/stints.py`, `synthetic/generator.py`, `cli.py`, `tests/guards/{consumers,import_scan,test_consumer_registry}.py`, `tests/test_docs.py`, `tests/conftest.py`, `pyproject.toml`, `.github/workflows/ci.yml`, `DECISIONS.md` (DEC-040..060), `F1 Docs/BUILD_PLAN.md` (lines 105-125).
- Computation against `data/f1si.duckdb` via `AsOfAccessor` (Bahrain 2023, cutoffs 8, 15, 30, RACE_END) and against `generate_race` synthetic specs; scripts were throwaway in the session scratchpad.

### Secondary (MEDIUM)
- CONTEXT.md D-01 for the literature fuel range (not independently re-verified).

### Tertiary (LOW / training knowledge)
- Python typing behaviour of `runtime_checkable` and mypy strict flag set (A1, A2) — verify in Wave 0.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; versions are project pins.
- Architecture: HIGH — grounded in the real repo and guard tests; interface signatures are recommendations.
- Fit/identifiability and Bahrain numbers: HIGH (measured), with the caveat that exact values shift slightly with the final trimming/threshold choices.
- Pitfalls: HIGH for those observed; MEDIUM for typing-behaviour items (A1, A2).

**Research date:** 2026-11-11
**Valid until:** 30 days (repo-internal; invalidated if Phase 1 code or the cache changes)
