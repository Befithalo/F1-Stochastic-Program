# Phase 5: Longstaff-Schwartz Strategy & Live Replay - Research

**Researched:** 2026-11-13  
**Domain:** Monte Carlo optimal stopping, CVaR ranking, deterministic CLI replay  
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

## decisions

## Implementation Decisions

### Strategy ranking and risk setting
- **D-01:** Use one user-facing risk-aversion value on a 0-1 scale. 0 is mean-focused / chase-the-win; 1 is tail-focused / protect-points. Rank options by a blend of expected finishing position and worst-decile CVaR, with lower values better. Keep the mean and CVaR visible as separate reported metrics so the blend remains inspectable.
- **D-02:** Define CVaR@10% as the average finishing position in the worst 10% of simulated outcomes (higher finishing-position numbers are worse). The CLI default risk setting and exact numeric output format are implementation details for planning.

### Replay workflow and output
- **D-03:** Add a f1si replay CLI command. With no lap argument it emits recommendations for successive race cutoffs; --lap N emits the single as-of recommendation at lap N. Use the existing CLI command and plain-text table patterns; reserve the interactive dashboard and fan chart for Phase 6.
- **D-04:** Rebuild the snapshot, fit, filter output, and RaceState from the same as-of cutoff for each recommendation. Keep replay on AsOfAccessor; do not read current-race results, future laps, or hindsight fits to produce a call.
- **D-05:** All stochastic strategy comparisons must use the project's injected, seeded numpy.random.Generator conventions. Preserve common random numbers between competing options where the simulator permits it, so option differences are not dominated by unrelated draws.

### Recommendation reasons
- **D-06:** Produce a concise, deterministic sentence from the current as-of state and the option scores. Mention an undercut, current safety-car stop value, or wear uncertainty only when the visible inputs and simulated outcomes support the claim. Do not claim a tire cliff or forecast an unobserved future regime.
- **D-07:** If the available state cannot support a specific explanation, report the score-based reason plainly instead of inventing a race narrative.

### Carried forward
- Keep the StrategyPolicy.decide(state, *, driver) contract and its shared conformance suite (DEC-061); the policy owns any RNG it needs rather than changing the protocol.
- Use the existing filter-to-RaceState integration for the current tyres (DEC-093/094). The Phase 4 wear-prior double-counting concern remains documented and is to be measured in Phase 6 before changing the method (DEC-091; 04-HUMAN-UAT.md).
- Use only the candidate actions already fixed in the Phase 5 success criteria. Do not add a dashboard, multi-race backtest, new regime model, or nonlinear tire-cliff model to this phase.

## the agent's Discretion
The Longstaff-Schwartz regression basis, numerical details of estimating CVaR, legal-plan handling at race boundaries, CLI formatting, exact reason-rule thresholds, and internal module boundaries may follow the simplest approach that meets the existing contracts and is documented. Any assumption-based threshold must be labeled and kept easy to revisit.

## deferred

## Deferred Ideas
- Streamlit dashboard and fan chart, plus walk-forward evaluation across real races - Phase 6.
- Hierarchical Bayesian pace model - Phase 7.
- Markov race regimes and measured regime-dependent pit loss - Phase 8.
- Nonlinear tire cliff or other tire-physics effects - future scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STR-01 | Longstaff-Schwartz optimal pit timing implements `StrategyPolicy` | Backward induction with fitted conditional continuation value; preserve the `decide(state, *, driver)` contract. |
| STR-02 | Each option (pit now, pit in 1-5 laps, stay out) is ranked by mean finish and CVaR@10% | Use common simulated scenarios, report mean, spread, worst-decile CVaR and the risk blend. |
| STR-03 | A risk-appetite setting shifts ranking between mean and tail risk | A bounded risk-aversion parameter controls one documented blended score; test endpoints and a state where choice changes. |
| STR-04 | Each recommendation includes a one-sentence reason (e.g. undercut threat, cliff risk, safety-car window) | Build deterministic wording only from cutoff-visible fields and simulated scores; disallow unsupported tire-cliff and future-regime claims per D-06. |
| RPL-01 | User can replay a race lap by lap for any driver and get a recommendation with uncertainty each lap | Add replay command and rebuild the full input path for every cutoff using `AsOfAccessor`. |
| RPL-02 | Live replay of Bahrain 2023 works end to end (M1 definition of done) | Use cached Bahrain data and verify both all-cutoff and one-cutoff replay paths, driver selection, and expected refusals. |

Descriptions copied from [VERIFIED: .planning/REQUIREMENTS.md:52-55 — `Longstaff-Schwartz optimal pit timing implements `StrategyPolicy``; `Each option (pit now, pit in 1-5 laps, stay out) is ranked by mean finish and CVaR@10%`; `A risk-appetite setting shifts ranking between mean and tail risk`; `Each recommendation includes a one-sentence reason (e.g. undercut threat, cliff risk, safety-car window)`; and .planning/REQUIREMENTS.md:59-60 — `User can replay a race lap by lap for any driver and get a recommendation with uncertainty each lap`; `Live replay of Bahrain 2023 works end to end (M1 definition of done)`.]
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Start file changes through a GSD workflow command. CLAUDE.md says to use `/gsd-quick` for small fixes and docs, `/gsd-debug` for investigations, and `/gsd-execute-phase` for planned execution; do not edit outside a GSD workflow unless explicitly asked.
- The owner is new to coding; provide a plain-language explanation after each phase.
- Respect the documented Windows development environment, existing Python package conventions, no-look-ahead rule, explicit seeded NumPy generators, and CI quality gate.
- Project skill directories `.claude/skills/` and `.agents/skills/` and root `AGENTS.md` were checked; none were present. [VERIFIED: project directory probe.]

## Summary

Implement a Longstaff–Schwartz policy that estimates continuation value by regressing simulated future outcomes on a small, documented basis of the cutoff state, working backward through future pit opportunities. The foundational paper describes this as least-squares estimation of the conditional expected payoff from continuing, not merely ranking a fixed list of complete schedules. [CITED: https://academic.oup.com/rfs/article/14/1/113/1587472] This matters for planning: the existing simulator returns final positions and times, with optional safety-car, stop, pit-loss and clock diagnostics; it does not expose the full per-path race state needed to train a continuation rule. [VERIFIED: src/f1si/interfaces.py:120-145 — “`finish_positions` has shape (n_races, n_cars) and each row is a permutation of 1..n_cars;”; “`clock_s` (n_races, n_laps, n_cars) float64, cumulative time at each lap end, filled only on request.”] The plan must define how regression training paths and their cutoff-visible state features are produced without weakening the `RaceState`-only policy boundary.

For ranking, retain shared scenarios across the competing actions, then report mean finishing position, spread, CVaR@10%, and the user-selected blended score. Lower positions are better, so compute and sort all objective values consistently as costs. [VERIFIED: .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-CONTEXT.md:22 — “Rank options by a blend of expected finishing position and worst-decile CVaR, with lower values better.”] Make the blend, empirical tail convention for ties, stable tie-break, default risk setting, regression basis, fallback on an unstable regression, and reason-rule thresholds explicit implementation decisions. The linear blend formula and thresholds are not fully locked and remain assumptions for discussion or easy later revision.

Replay should mirror the established wear-filter path: for each requested lap cutoff rebuild the snapshot, fit, filter result, and `RaceState` from that cutoff; use that state for one recommendation; and never pass the accessor into the strategy or simulator. [VERIFIED: DECISIONS.md:1045-1047 — “builds a fresh `RaceSnapshot` with `AsOfAccessor.snapshot(AsOf(race, L))` for every cutoff L = 1..N”; “The accessor stays in cli.py; only `RaceSnapshot` and `LinearPaceFit` reach the filter”; “Reusing one fit would be faster but would leak the future into every earlier lap.”] Current environment note: `uv` is installed, but `uv run python --version` could not spawn Python because Windows Application Control blocked the child process (OS error 4551). [VERIFIED: environment probe.]

**Primary recommendation:** Use an explicit backward stopping recursion with small least-squares continuation regressions over shared simulator paths; add only the minimal path/state outputs the regression needs; retain existing interfaces and as-of replay architecture.

The public decision output also needs a planning decision: `PitDecision` currently contains only `driver`, `lap`, `pit_now`, `compound`, `best_plan`, and `ranked_plans`, while `Plan` stores `stop_laps`, `compounds`, and `total_time_s`. [VERIFIED: src/f1si/interfaces.py:43-56 — “`stop_laps: tuple[int, ...]`”, “`compounds: tuple[str, ...]`”, “`total_time_s: float`”; src/f1si/interfaces.py:83-100 — “`driver: str`”, “`lap: int`”, “`pit_now: bool`”, “`compound: str | None`”, “`best_plan: Plan`”, “`ranked_plans: tuple[Plan, ...]`”.] These current fields do not represent mean finish, spread, CVaR, risk score, or the reason sentence. Plan a backward-compatible output representation (for example trailing optional score/reason fields or a structured report owned by the policy/CLI) without changing the locked `decide(state, *, driver)` method signature. The chosen representation must let both CLI and conformance tests inspect the metrics.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pit-now versus wait valuation | API / Backend | — | Pure policy computation over `RaceState` and injected model/simulator; strategy has no data accessor. [VERIFIED: src/f1si/interfaces.py:167-175 — “The state is never mutated.”] |
| Monte Carlo continuation scenarios | API / Backend | — | Simulator owns stochastic race evolution and accepts an explicit generator. [VERIFIED: src/f1si/interfaces.py:180-190 — simulator signature accepts `rng: np.random.Generator`.] |
| Replay cutoff preparation | API / Backend | Database / Storage | CLI/replay driver owns `AsOfAccessor`; storage provides snapshots and history. [VERIFIED: .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-CONTEXT.md:89 — “its replay driver owns the AsOfAccessor”.] |
| Human-readable recommendation and table | API / Backend | — | Existing `f1si` CLI owns parsing and friendly refusal patterns. [VERIFIED: .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-CONTEXT.md:26,85 — “Use the existing CLI command and plain-text table patterns”; “return a friendly refusal instead of exposing a traceback for expected data limitations.”] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | `>=3.12,<3.13` | Strategy and replay implementation | Project runtime constraint. [VERIFIED: pyproject.toml:1-2 — `requires-python = ">=3.12,<3.13"`] |
| NumPy | `>=2.3,<3` | Scenario arrays, regression inputs, empirical statistics, seeded `Generator` | Already in the application stack and simulator. [VERIFIED: pyproject.toml:5 — `"numpy>=2.3,<3"`] |
| SciPy | `>=1.15,<2` | Existing Sobol/quasi-random simulation support | Already in the simulator stack; preserve its established random-number layout. [VERIFIED: pyproject.toml:12 — `"scipy>=1.15,<2"`] |
| pytest | `>=9.1,<10` | Conformance, regression and replay tests | Existing test framework. [VERIFIED: pyproject.toml:23 — `"pytest>=9.1,<10"`] |

No new external package is needed for this phase. Use NumPy least squares and order statistics unless implementation evidence shows a missing capability; avoid a new finance/optimization dependency for this small fixed candidate set. No package legitimacy audit is required because the phase does not install external packages.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Backward continuation-value regression | Rank only complete forced schedules | Simpler and can rank candidates, but does not implement the regression-based optimal stopping method in STR-01. |
| Empirical worst-tail mean from common samples | Parametric tail fit | A tail fit adds distribution assumptions and is unnecessary for the explicitly sample-defined CVaR. |

## Architecture Patterns

### System Architecture Diagram

```text
CLI: f1si replay [race] [driver] [--lap]
          |
          v
Replay driver: cutoff sequence / selected cutoff
          |
          v
AsOfAccessor.snapshot(cutoff) + as-of history
          |
          v
fit -> per-cutoff wear filter -> RaceState
          |
          v
StrategyPolicy.decide(state, driver)
          |                          \
          v                           v
Backward LSM continuation       SimulatorBackend
regressions / legal stop rule <- shared seeded paths,
          |                     forced plans, diagnostics
          +------------+-------------+
                       v
             metrics + ranked plans
                       |
                       v
             deterministic reason/table
```

The diagram reflects the locked separation: the replay driver holds the accessor, the policy receives a state, and the simulator receives the state and injected RNG. [VERIFIED: .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-CONTEXT.md:89 — “its replay driver owns the AsOfAccessor, while policy code receives only a RaceState.”]

### Recommended Project Structure

Follow existing `src/f1si/` layout and module boundaries rather than introducing a new package tier. A new `src/f1si/strategy/` policy module is explicitly the intended home; replay composition belongs in `src/f1si/cli.py` or a replay driver module that keeps accessor ownership. [VERIFIED: .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-CONTEXT.md:88-89 — “Add the Longstaff-Schwartz policy under src/f1si/strategy/” and “Add f1si replay through src/f1si/cli.py; its replay driver owns the AsOfAccessor”.]

### Pattern 1: Discrete Longstaff–Schwartz backward induction

**What:** Simulate pathwise state evolution and candidate outcomes; initialize the terminal value at the race boundary; then walk stopping opportunities backward. At each decision time, regress realized future continuation value on a compact basis of state variables, compare the fitted continuation cost with the simulated immediate-stop cost, and store the chosen stopping rule. For a minimizing finishing-position objective, lower estimated cost is preferred. The original method estimates conditional continuation payoff from simulated states by least squares. [CITED: https://academic.oup.com/rfs/article/14/1/113/1587472]

**When to use:** Required for STR-01, which explicitly names Longstaff–Schwartz. Do not label simple ranking of pit-now / fixed-delay / stay-out simulations as LSM unless an actual continuation regression and backward decision step are implemented.

**Planning choice:** Use the smallest basis supported by the current model, such as an intercept plus scaled current position/gap, own tire age, filtered wear mean and uncertainty, remaining laps, stops/compounds already used, and current regime indicator only if present in `RaceState`. Normalize features; monitor rank/conditioning; fall back to a documented simpler rule when training data are insufficient. Exact basis and fallback are discretion, so mark parameter thresholds as assumptions.

**Example (conceptual, minimize finish-position cost):**

```python
for decision_time in reversed(stopping_times):
    continuation_fit = least_squares(basis(state_at_time), realized_value_if_wait)
    continuation_cost = continuation_fit.predict(basis(state_at_time))
    stop_now = simulated_finish_cost_if_pitting_now
    value_at_time = minimum(stop_now, continuation_cost)
```

The pseudo-code is conceptual, not an API contract. It captures the direction of the comparison; simulated terminal finish positions remain the outcome being valued. [CITED: https://academic.oup.com/rfs/article-abstract/14/1/113/1587472]

### Pattern 2: Shared scenarios for action comparisons

**What:** Compare options under the same random scenarios. The existing simulator already generates unconditional draws indexed by race, car and lap, and its draw dimensions for wear are kept fixed when plans are forced. [VERIFIED: src/f1si/sim/numpy_backend.py:28-39 — “Every draw is indexed by (race, car, lap) and generated unconditionally”; “wear normals use a fixed slot per canonical compound name (`DRAW_COMPOUNDS`), so the dimension and every compound's draw are the same whatever plans are forced”.]

**When to use:** For pit-now, each fixed-delay candidate, stay-out, and continuation targets, where the simulator permits forcing comparable options. The policy owns/reset-derives its seed per decision so the conformance contract that repeated `decide` calls are identical still holds. [VERIFIED: src/f1si/interfaces.py:167-175 — `class StrategyPolicy(Protocol):`; “Deterministic: the contract has no rng. The state is never mutated.”] Keep Monte Carlo sample size/draw layout stable across actions.

For common random numbers across separate simulator calls, initialize a fresh generator for each alternative from the same stable decision seed. Reusing and advancing one generator sequentially would give each alternative a different random block; derive the seed from policy configuration plus decision identity or use a deterministic state seed, then reconstruct it per candidate. `[ASSUMED]` The seed derivation is an implementation detail and should not alter the public protocol.

**Numerical note:** SciPy’s current Sobol guidance recommends `random_base2` for `2**m` samples to preserve balance and warns that arbitrary sample sizes, skipping the first point, or thinning loses the balance properties. [CITED: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html] The project already fixes variance-reduction conventions; do not change those as part of the policy without a measured reason.

### Pattern 3: As-of reconstruction at every replay cutoff

**What:** For each requested leader-lap cutoff, make a fresh snapshot, refit pace on visible rows, rerun filter on that snapshot, and build the state with the filter result from the same cutoff. For a car behind the leader, use the newest visible lap at or before the leader cutoff; its last completed lap may be earlier. [VERIFIED: DECISIONS.md:1045-1048 — “keeps the driver's newest row at that cutoff”; “A car behind the leader has not completed the leader's lap L at cutoff L, so its newest visible lap is usually L-1”.]

**When to use:** Both whole-race replay and `--lap N`; the selected-lap path must be observationally equivalent to selecting that row from a full as-of replay.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Race cutoff access | New query path or direct DuckDB reads from strategy | `AsOfAccessor.snapshot(AsOf(...))` in the replay driver | Central look-ahead enforcement and consumer scramble guard. |
| Current-tyre wear uncertainty | Duplicate tire state/filter logic | `filter_stints` plus `current_stint_snapshots` and `build_race_state(..., wear_filter=...)` | Established integration preserves current simulator semantics. |
| Simulation randomness | Per-option unrelated seeds or module-level random calls | Injected seeded `numpy.random.Generator` and existing common-random-number draws | Makes option deltas more comparable and keeps seeded conventions. |
| Shared strategy interface checks | A separate ad hoc policy contract | `tests/conformance/suites.py` shared `check_strategy_policy` | Makes policy behavior uniform and is a phase success criterion. |

**Key insight:** The existing components already enforce the high-risk boundaries—cutoff isolation, filter/state compatibility, and stable random draw slots. The new policy should use these seams and focus new code on continuation valuation and decision explanations.

## Common Pitfalls

### Pitfall 1: Calling fixed-plan ranking “Longstaff–Schwartz”

**What goes wrong:** A Monte Carlo average for each complete fixed schedule can rank the candidate options but cannot learn the value of continuing conditional on the evolving state.  
**Why it happens:** Both approaches simulate future outcomes, so they look similar in a table.  
**How to avoid:** Require explicit backward recursion and conditional continuation regression in STR-01 acceptance criteria, with a synthetic problem whose optimal stop boundary is known. [CITED: https://academic.oup.com/rfs/article/14/1/113/1587472]  
**Warning signs:** No regression basis, training targets, stopping-time loop, or out-of-sample policy replay appears in the design.

### Pitfall 2: Simulator does not expose regression trajectories

**What goes wrong:** Regression is trained on final position only or on an inconsistent proxy, so the policy never conditions on state at each candidate stopping time.  
**Why it happens:** Existing `SimulationResult` guarantees final position/time matrices and optional diagnostics; only cumulative clocks, not full pathwise states, are optional. [VERIFIED: src/f1si/interfaces.py:120-145 — “`finish_positions` has shape (n_races, n_cars)”; “`clock_s` ... cumulative time at each lap end, filled only on request.”]  
**How to avoid:** Plan the smallest simulator extension needed to surface cutoff-state features or pathwise value targets, while keeping `SimulatorBackend` return compatibility via trailing defaulted fields or a separate internal result. Test shape, dtype, seed-repeatability, memory, and unchanged existing simulator behavior.

### Pitfall 3: Regression overfit or singular basis

**What goes wrong:** A large polynomial basis or too few eligible scenarios yields unstable continuation estimates, flips the stopping boundary, or produces non-finite scores.  
**Why it happens:** State variables are correlated and Monte Carlo path count may be small in conformance tests or late-race cutoffs.  
**How to avoid:** Begin with a compact scaled basis, use stable least-squares (`lstsq`) with rank/finite checks, reserve independent seeded scenarios for policy evaluation where feasible, and define deterministic fallback/tie behavior. Add recovery tests on a synthetic stopping problem and sensitivity checks across seeds/sample sizes.

### Pitfall 4: CVaR tail convention and noisy tail ranks

**What goes wrong:** For finishing positions, treating the best-decile as risk tail reverses preference; rounding `0.1 * n` can also make the reported “worst 10%” vary with sample count or tied integer places.  
**Why it happens:** Usual finance examples model positive losses in the upper tail, while race position numbers are worse when higher.  
**How to avoid:** Sort positions from worst to best and define how to handle a fractional boundary observation so exactly 10% probability mass contributes; keep that convention explicit. The phase’s CVaR meaning is locked in D-02. The CVaR source formulates conditional tail loss and scenario estimation. [CITED: https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf]  
**Warning signs:** Endpoint risk values do not recover mean-only versus worst-decile-only ranking, or a ranking changes drastically from one seed with no uncertainty note.

### Pitfall 5: Misleading risk slider / unsupported reason

**What goes wrong:** Numerical risk value has no clear monotonic effect, or a generated reason describes a safety car/undercut/tire cliff not supported at the cutoff.  
**Why it happens:** Blend scaling is unspecified and reason thresholds are discretionary.  
**How to avoid:** Use a transparent, documented blend on the same position scale (for example `(1-risk)*mean + risk*CVaR`, explicitly an `[ASSUMED]` formula pending confirmation); test endpoints and a constructed case where ranking flips. Reasons must be deterministic and grounded in visible state plus score differences; use a score-based sentence when no specific cause is supported. Do not claim a cliff or predict an unobserved regime per D-06.

### Pitfall 6: Treating static CVaR ranking as dynamic CVaR-optimal stopping

**What goes wrong:** An LSM recursion that fits expected continuation position and then ranks the final options by CVaR does not by itself prove the policy is optimal under a tail-risk objective.  
**Why it happens:** LSM continuation regression estimates a conditional expectation, while CVaR describes a tail functional over a distribution of outcomes; these are different objects. [CITED: https://academic.oup.com/rfs/article/14/1/113/1587472; https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf]  
**How to avoid:** Explicitly scope the MVP interpretation: either LSM learns expected-position continuation and CVaR only ranks the current cutoff’s candidate action distributions, or define a dynamic, time-consistent risk recursion and extra state it requires. Do not claim the first design is dynamically CVaR-optimal. [ASSUMED: this consequence follows from combining the LSM conditional-expectation method with static tail-risk ranking.]  
**Warning signs:** Risk changes only printed scores while the decision logic is described as “CVaR-optimal” without showing how tail risk enters continuation values.

### Pitfall 7: Incorrect pit legality or lap semantics at boundaries

**What goes wrong:** “Pit now” means the leader’s next lap instead of the driver’s own next lap, or a delayed stop becomes illegal / impossible when fewer race laps remain.  
**Why it happens:** At one cutoff cars can have different `laps_done`; existing plan rules enforce stint minimums and dry-compound usage.  
**How to avoid:** Reuse `state.laps_done_of(car)` and existing plan legality; enumerate only feasible actions, document how unavailable candidates are represented in ranked output, and handle race-over/last-lap/no-legal-action cases with the established friendly refusal style. [VERIFIED: src/f1si/strategy/free_track.py:5-12 — “A car that has completed N laps (`RaceState.laps_done_of(car)`) is planned from its own next lap”; “pit now is k = N+1”.]

### Pitfall 8: Seeded output confused with cross-platform bitwise identity

**What goes wrong:** Tests promise identical stochastic arrays across all machines or dependency builds.  
**Why it happens:** “Seeded” is interpreted as unlimited stream compatibility.  
**How to avoid:** Guarantee repeatability for the project’s fixed generator, seed, call sequence and supported environment; compare deterministically within supported CI. NumPy documents these strict conditions and warns that build/machine differences can change results. [CITED: https://numpy.org/doc/stable/reference/random/compatibility.html]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest `>=9.1,<10` [VERIFIED: pyproject.toml:23 — `"pytest>=9.1,<10"`] |
| Config file | `pyproject.toml` (`testpaths = ["tests"]`; network tests excluded by default) |
| Quick run command | `uv run pytest -q tests/test_strategy_longstaff.py` (new focused file; plan as Wave 0 if absent) |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STR-01 | Backward stopping regression recovers a simple known optimal boundary; policy satisfies protocol | unit + conformance | `uv run pytest -q tests/strategy/test_longstaff.py tests/conformance/test_suites.py` | Add Phase 5 test; shared suite exists at `tests/conformance/test_suites.py`. |
| STR-02 | All required options report comparable mean, spread and worst-decile CVaR; CVaR orientation/tie behavior | unit | `uv run pytest -q tests/strategy/test_longstaff.py -k cvar` | Add Phase 5 tests. |
| STR-03 | Risk endpoints and intermediate setting alter score/ranking as defined and remain deterministic | unit | `uv run pytest -q tests/strategy/test_longstaff.py -k risk` | Add Phase 5 tests. |
| STR-04 | One-sentence reason deterministic and claims supported by state/simulation; unsupported narrative falls back to score | unit | `uv run pytest -q tests/strategy/test_longstaff.py -k reason` | Add Phase 5 tests. |
| RPL-01 | All cutoffs and selected `--lap N` replay use same-cutoff fit/filter/state and honor driver lap count | integration + future-scramble guard | `uv run pytest -q tests/test_cli_replay.py tests/guards/test_future_scramble.py` | Add replay tests; guard exists at `tests/guards/test_future_scramble.py`. |
| RPL-02 | Cached Bahrain 2023 completes end-to-end; outputs recommendations and expected friendly refusals | smoke / manual CLI | `uv run f1si replay <race> --driver <driver>` | Add CLI end-to-end test and perform one manual run when Python execution is available. |

**Existing contract evidence:** `check_strategy_policy` verifies structural protocol, `PitDecision` return, no state mutation, repeated-call determinism, correct driver/lap, legal compounds, and that `best_plan` is first in `ranked_plans`. [VERIFIED: tests/conformance/suites.py:115-150 — “decision = policy.decide(state, driver=case.driver)”; “determinism: the same state gave different decisions”; “best_plan != ranked_plans[0]”.] Add its invocation for the new policy instead of duplicating these checks.

### Sampling Rate

- **Per task commit:** focused new unit/conformance tests.
- **Per wave merge:** full pytest suite, lint and strict mypy.
- **Phase gate:** full CI green, as-of future-scramble test includes replay consumer, and cached Bahrain 2023 replay completes for all cutoffs and one selected cutoff.

### Wave 0 Gaps

- [ ] Add synthetic LSM continuation-recovery and regression-rank fallback tests.
- [ ] Add CVaR worst-tail orientation, fractional cutoff/ties, finite-sample uncertainty, and risk-endpoint tests.
- [ ] Add replay selected-cutoff equality-to-full-replay and future-scramble consumer registration.
- [ ] Ensure the shared StrategyPolicy suite is parameterized with this policy and a legal-compound case.

## Security Domain

Security enforcement is enabled because `.planning/config.json` does not set `security_enforcement: false`. This is a local CLI and local cached-data feature; it introduces no user authentication, sessions, network endpoint, or cryptographic operation. Keep input validation and path/error handling in scope. ASVS is currently at version 5.0.0 and is a security verification standard. [CITED: https://asvs.owasp.org/]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No authenticated users or credentials are added in this CLI phase. |
| V3 Session Management | no | No browser or server sessions. |
| V4 Access Control | yes | Validate race/driver selection and keep DB-path ownership in CLI composition; do not grant new filesystem access through strategy. |
| V5 Input Validation | yes | Validate lap and risk numeric bounds, race slug and driver using existing friendly CLI refusal patterns; reject non-finite values. |
| V6 Cryptography | no | No secrets, token handling or cryptographic feature is added. |

### Known Threat Patterns for Python CLI + Local DuckDB

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path or argument injection through race/lap/driver input | Tampering | Parse typed arguments, resolve known race/driver values, validate bounds before composing paths/queries. |
| Accidental future-data access during replay | Information disclosure / integrity | Keep accessor only in replay driver; register replay consumer in future-scramble guard. |
| Verbose tracebacks on expected missing data | Information disclosure | Preserve friendly expected-error handling; reserve traceback for explicit debug mode. |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | Python env and test commands | yes | `0.13.5` [VERIFIED: `uv --version` probe] | — |
| Python runtime | Strategy, replay, pytest, lint/typecheck | blocked | Probe `uv run python --version` failed: “An Application Control policy has blocked this file. (os error 4551)” [VERIFIED: runtime probe] | Run validation in CI/another authorized Python environment; local end-to-end execution remains blocked until runtime is available. |
| Cached race data | Bahrain 2023 replay | data directory exists | not probed [VERIFIED: `Test-Path data` probe] | Expected friendly refusal if cache entry is missing; load using established data workflow. |

**Missing dependencies with no local fallback:** Python execution is blocked in this environment by Application Control. The planner should make an available CI/runner validation step explicit and avoid treating a CLI run here as completed.

## Code Examples

### Empirical lower-is-better option ranking

Use the required metrics on the same scenario set, then sort by the documented risk score. The precise blend below is an assumption, because D-01 fixes its endpoints and intent but not its algebra. [VERIFIED: .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-CONTEXT.md:22-23 — “Use one user-facing risk-aversion value on a 0-1 scale.” and “Define CVaR@10% as the average finishing position in the worst 10% of simulated outcomes (higher finishing-position numbers are worse).”]

```python
mean_finish = samples.mean()
spread = samples.std(ddof=1)
cvar_10 = mean_of_worst_ten_percent(samples)  # larger positions are worse
score = (1.0 - risk_aversion) * mean_finish + risk_aversion * cvar_10
```

`[ASSUMED]` Define the tail estimator with fractional weight at the boundary so ties and sample counts not divisible by ten still represent exactly 10% of probability mass; document sample uncertainty for that tail statistic.

### Deterministic reason fallback

```text
if cutoff evidence supports an undercut / current SC stop value / wear uncertainty:
    emit the corresponding concise, evidence-backed sentence
else:
    emit a sentence naming the selected plan and its score advantage
```

Keep reason thresholds stable, centralized and documented. Never infer an unobserved future regime or tire cliff from the currently linear tire model, as D-06 explicitly forbids that claim.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed schedule ranking only | Least-squares conditional continuation estimates and backward stopping decisions | Longstaff & Schwartz, 2001 | Use regression to approximate the conditional continuation value for each stopping date. [CITED: https://academic.oup.com/rfs/article/14/1/113/1587472] |
| NumPy/SciPy legacy `RandomState`/`seed` style | Inject `numpy.random.Generator`; SciPy Sobol uses the current `rng` API | SciPy `qmc.Sobol` changed `seed` to `rng` in SciPy 1.15 | Follow project Generator conventions and existing lock; do not add a second random API. [CITED: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html] |

**Deprecated/outdated:** Do not introduce `RandomState` or module-level random calls; project lint and phase decisions require explicit generators. The NumPy compatibility page also documents that bitwise stream guarantees have strict environment conditions. [CITED: https://numpy.org/doc/stable/reference/random/compatibility.html]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Use a linear blend `score = (1-risk)*mean + risk*CVaR`; the decision locks endpoints and intent but not the formula. | Pitfall 5 / Code Examples | Risk dial semantics or user preference may differ; keep the formula isolated and documented. |
| A2 | Use fractional boundary weighting for empirical worst-decile CVaR when the sample has tied integer finishes or its size is not divisible by ten. | Code Examples | Different estimator conventions can produce slightly different tail scores and option ranks. |
| A3 | A compact normalized basis plus rank/finite checks and a simple fallback is sufficient for this MVP’s simulated continuation regression. | Pattern 1 / Pitfall 3 | Basis may omit predictive state or regressions may be unstable; use synthetic recovery and seed/sample sensitivity. |
| A4 | Python execution remains blocked locally until environment policy changes; CI/another runner can perform execution checks. | Environment Availability | If CI also lacks supported Python, planning must include a runtime setup resolution before execution. |
| A5 | CVaR may be used only to rank candidate distributions at the current cutoff while LSM regression optimizes conditional mean position. | Pitfall 6 | This scope can satisfy the reported risk ranking but is not a dynamic CVaR-optimal policy; clarify desired claim before locking the implementation. |

## Open Questions

1. **What continuation-value paths can the policy consume without breaking the simulator protocol?**
   - What we know: `SimulationResult` provides final outcomes and optional cumulative clocks; current `StrategyPolicy` receives only `RaceState`.
   - What's unclear: Whether a minimal trailing diagnostics addition, internal simulator method, or separate path result best supports the LSM regression.
   - Recommendation: Planner should inspect the simulator kernel and choose the smallest typed extension; preserve `decide(state, *, driver)` and conformance contracts.
2. **Where does CVaR enter the stopping recursion?**
   - What we know: LSM estimates expected continuation value, while the decision also reports and blends tail risk.
   - What's unclear: Whether risk appetite should affect only the current cutoff’s ranking of complete option distributions or the continuation rule itself.
   - Recommendation: State the MVP interpretation explicitly and avoid labeling it dynamically CVaR-optimal unless a dynamic risk recursion is implemented.
3. **Which risk blend and exact default risk value should the CLI use?**
   - What we know: risk lies between mean-only and tail-only endpoints; both metrics remain visible.
   - What's unclear: exact algebra/default and the required CLI spelling/format.
   - Recommendation: Use the linear normalized blend as a labeled initial assumption unless discussion locks a different formula; make default and bounds visible in help.
4. **How should unavailable actions at the race boundary appear?**
   - What we know: candidates are pit now, pit in 1–5 laps, and stay out; existing strategy legality includes minimum stint constraints.
   - What's unclear: whether impossible delays are omitted or retained with a refusal marker in the output.
   - Recommendation: Keep ranked plans legal and explain omitted actions plainly; never rank an invalid plan as a valid recommendation.

## Sources

### Primary (MEDIUM confidence)

- Longstaff & Schwartz, *Valuing American Options by Simulation: A Simple Least-Squares Approach*, Review of Financial Studies 14(1), 113–147 (2001), DOI 10.1093/rfs/14.1.113 — original method / continuation regression. [CITED: https://academic.oup.com/rfs/article-abstract/14/1/113/1587472]
- Rockafellar & Uryasev, *Optimization of Conditional Value-at-Risk* — scenario tail-risk definition and optimization formulation. [CITED: https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf]
- SciPy `scipy.stats.qmc.Sobol` reference — current `rng`, power-of-two sample balance, warning on thinning/skipping. [CITED: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html]
- NumPy random compatibility reference — conditions on reproducible streams. [CITED: https://numpy.org/doc/stable/reference/random/compatibility.html]

### In-repo (HIGH confidence)

- `.planning/phases/05-longstaff-schwartz-strategy-live-replay/05-CONTEXT.md` — locked choices, discretion, deferred boundary.
- `src/f1si/interfaces.py` — `StrategyPolicy`, `PitDecision`, `Plan`, `SimulationResult` contracts.
- `src/f1si/data/asof.py`, `src/f1si/state.py`, `src/f1si/pace/kalman.py` — cutoff snapshot, state and filter seam.
- `src/f1si/strategy/free_track.py`, `src/f1si/sim/numpy_backend.py`, `src/f1si/sim/draws.py` — legality, path simulation and common random draws.
- `src/f1si/cli.py`, `tests/conformance/suites.py`, `tests/guards/consumers.py` — CLI, policy contract tests and look-ahead consumer registry.
- `pyproject.toml`, `CLAUDE.md`, `.planning/config.json` — stack, project instructions, validation/security settings.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — read current project dependency declarations; no new dependency is recommended.
- Architecture: HIGH — grounded in phase decisions and opened source-of-truth contracts.
- LSM algorithm: MEDIUM — grounded in the original paper; exact race-state basis and simulator trajectory seam remain phase decisions.
- Pitfalls and validation: HIGH — contracts and existing project guard patterns are verified; recommended new test cases are planning guidance.

**Research date:** 2026-11-13  
**Valid until:** 2026-12-13 for the stable algorithm and architecture; recheck dependencies if the phase adds packages.
