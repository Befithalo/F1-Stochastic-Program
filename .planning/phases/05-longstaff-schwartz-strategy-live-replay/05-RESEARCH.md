# Phase 5: Longstaff-Schwartz Strategy & Live Replay - Research

**Researched:** 2026-11-13
**Domain:** Monte Carlo optimal stopping, conditional-mean continuation regression, empirical tail-risk ranking, as-of replay
**Confidence:** HIGH for algorithm/scope and repository contracts; MEDIUM for recommended simulator extension shape

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Strategy ranking and risk setting
- **D-01:** Use one user-facing risk-aversion value on a 0-1 scale. 0 is mean-focused / chase-the-win; 1 is tail-focused / protect-points. Rank current-cutoff options by score = (1 - risk_aversion) × mean_finish + risk_aversion × CVaR10, with lower values better. Keep the mean and CVaR visible separately so the blend remains inspectable.
- **D-02:** Define CVaR@10% as the average finishing position in the worst 10% of simulated outcomes (higher finishing-position numbers are worse), with fractional weight at the sample boundary so the tail represents exactly 10% of probability mass. Default the CLI risk setting to 0.5, a neutral blend; expose its bounds and meaning in help.
- **D-08:** The Longstaff-Schwartz continuation regression estimates conditional mean finishing position. Apply the risk blend when ranking the current-cutoff candidate distributions; describe this as a CVaR-aware option ranking, not as a dynamically CVaR-optimal stopping policy. A nested or dynamically consistent CVaR recursion is outside Phase 5.

### Replay workflow and output
- **D-03:** Add a f1si replay CLI command. With no lap argument it emits recommendations for successive race cutoffs; --lap N emits the single as-of recommendation at lap N. Use the existing CLI command and plain-text table patterns; reserve the interactive dashboard and fan chart for Phase 6.
- **D-04:** Rebuild the snapshot, fit, filter output, and RaceState from the same as-of cutoff for each recommendation. Keep replay on AsOfAccessor; do not read current-race results, future laps, or hindsight fits to produce a call.
- **D-05:** All stochastic strategy comparisons must use the project's injected, seeded numpy.random.Generator conventions. Preserve common random numbers between competing options where the simulator permits it, so option differences are not dominated by unrelated draws. Repeated decide calls for the same state and policy configuration must remain identical, as required by the shared StrategyPolicy contract.

### Recommendation reasons
- **D-06:** Produce a concise, deterministic sentence from the current as-of state and the option scores. Mention an undercut, current safety-car stop value, or wear uncertainty only when the visible inputs and simulated outcomes support the claim. Do not claim a tire cliff or forecast an unobserved future regime.
- **D-07:** If the available state cannot support a specific explanation, report the score-based reason plainly instead of inventing a race narrative.

### Carried forward
- Keep the StrategyPolicy.decide(state, *, driver) contract and its shared conformance suite (DEC-061); the policy owns any RNG it needs rather than changing the protocol.
- Use the existing filter-to-RaceState integration for the current tyres (DEC-093/094). The Phase 4 wear-prior double-counting concern remains documented and is to be measured in Phase 6 before changing the method (DEC-091; 04-HUMAN-UAT.md).
- Use only the candidate actions already fixed in the Phase 5 success criteria. Do not add a dashboard, multi-race backtest, new regime model, or nonlinear tire-cliff model to this phase.

### the agent's Discretion
The Longstaff-Schwartz regression basis, numerical details of estimating CVaR, legal-plan handling at race boundaries, CLI formatting, exact reason-rule thresholds, and internal module boundaries may follow the simplest approach that meets the existing contracts and is documented. Any assumption-based threshold must be labeled and kept easy to revisit.

### Deferred Ideas (OUT OF SCOPE)
- Streamlit dashboard and fan chart, plus walk-forward evaluation across real races - Phase 6.
- Hierarchical Bayesian pace model - Phase 7.
- Markov race regimes and measured regime-dependent pit loss - Phase 8.
- Nonlinear tire cliff or other tire-physics effects - future scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STR-01 | Longstaff-Schwartz optimal pit timing implements `StrategyPolicy` | Genuine backward conditional-mean regression and pathwise continuation targets; keep `decide(state, *, driver)` deterministic. |
| STR-02 | Each option (pit now, pit in 1-5 laps, stay out) is ranked by mean finish and CVaR@10% | Use common scenarios; report mean, spread, worst-decile CVaR, and blended score for each current-cutoff option. |
| STR-03 | A risk-appetite setting shifts ranking between mean and tail risk | Apply the locked 0..1 linear blend only to current-cutoff option distributions; test endpoints and a rank-changing sample. |
| STR-04 | Each recommendation includes a one-sentence reason | Base deterministic reason rules on cutoff-visible state and option scores, with a plain score-based fallback. |
| RPL-01 | User can replay a race lap by lap for any driver and get a recommendation with uncertainty each lap | Rebuild snapshot, pace fit, wear filter, and state at each cutoff through `AsOfAccessor`. |
| RPL-02 | Live replay of Bahrain 2023 works end to end (M1 definition of done) | Add the replay CLI using established parsing/table/refusal conventions and verify cached Bahrain replay in an authorized Python runtime. |

Descriptions copied from [VERIFIED: .planning/REQUIREMENTS.md:52-60 — “Longstaff-Schwartz optimal pit timing implements `StrategyPolicy`”; “Each option (pit now, pit in 1-5 laps, stay out) is ranked by mean finish and CVaR@10%”; “A risk-appetite setting shifts ranking between mean and tail risk”; “Each recommendation includes a one-sentence reason (e.g. undercut threat, cliff risk, safety-car window)”; “User can replay a race lap by lap for any driver and get a recommendation with uncertainty each lap”; “Live replay of Bahrain 2023 works end to end (M1 definition of done)”.]
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Start file changes through a GSD workflow command; use `/gsd-quick` for small fixes/docs, `/gsd-debug` for investigations, and `/gsd-execute-phase` for planned execution. Do not edit outside a GSD workflow unless explicitly asked.
- The owner is new to coding; give a plain-language explanation after each phase.
- Follow Windows development conventions and the project stack; use explicit seeded NumPy generators, preserve no-look-ahead, and pass CI quality gates.
- Project skills directories and root `AGENTS.md` were checked; none were present. [VERIFIED: project directory probe.]

## Summary

The key planning distinction is now locked: implement Longstaff–Schwartz as a real backward stopping recursion whose fitted continuation value is the **conditional mean finishing-position cost**. At each simulated future decision time, regress realized value from continuing under the already learned later stopping rule on the path state, then compare that fitted continuation cost with the value from stopping now. Iterate backward. Ranking a fixed list of forced stop schedules, even with a least-squares model added elsewhere, is not the required stopping method. [CITED: https://academic.oup.com/rfs/article-abstract/14/1/113/1587472]

The current-cutoff actions are separately compared by mean finishing position and worst-decile CVaR. Use the locked score `score = (1 - risk_aversion) * mean_finish + risk_aversion * CVaR10`, lower is better, default risk 0.5; keep these metrics visible. This makes the current recommendation a CVaR-aware ranking over candidate distributions. It does **not** make the backward stopping rule dynamically CVaR-optimal: CVaR is not fed into the continuation regression, and nested/time-consistent tail-risk recursion is explicitly out of scope. [VERIFIED: 05-CONTEXT.md, D-01/D-02/D-08 — “Rank current-cutoff options by score = (1 - risk_aversion) × mean_finish + risk_aversion × CVaR10”; “The Longstaff-Schwartz continuation regression estimates conditional mean finishing position”; “A nested or dynamically consistent CVaR recursion is outside Phase 5.”]

The simulator already returns pathwise terminal finishing positions and optional lap clocks, but it does not expose enough of each simulated race's evolving state to fit a continuation rule and branch “pit now” versus “continue” at future laps. The planner should explicitly decide a minimal path seam: per-path predictor state at each relevant future decision time, plus a way to price pit-now and continue outcomes from the same checkpoint with common random numbers. Avoid an entire general-purpose simulator redesign. [VERIFIED: src/f1si/interfaces.py:120-144 — “`finish_positions` has shape (n_races, n_cars)”; “`clock_s` (n_races, n_laps, n_cars) float64, cumulative time at each lap end, filled only on request.”] [MEDIUM: simulator source inspection indicates the existing mutable path state contains additional fields needed to resume.]

**Primary recommendation:** Plan a compact backward LSM engine with a small, normalized basis and explicit pathwise checkpoints/resume or equivalent branching support. Keep the strategy policy a pure deterministic consumer of the current `RaceState`; keep replay data access in the replay driver. Use CVaR only for the current-cutoff option score and output.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Backward conditional-mean stopping rule | API / Backend | — | Strategy computes the stopping rule over simulated paths; it must receive no accessor and preserve the `StrategyPolicy` contract. [VERIFIED: src/f1si/interfaces.py:167-175 — “`def decide(self, state: RaceState, *, driver: str) -> PitDecision`”; “Deterministic: the contract has no rng. The state is never mutated.”] |
| Simulated path evolution and branch/checkpoint state | API / Backend | — | Simulator owns lap mechanics, path state, and seeded draws. Current loop has order, clock, tire age/compound, stops, and safety-car state. [VERIFIED: src/f1si/sim/numpy_backend.py:286-303 — “`order`”, “`clock`”, “`age`”, “`comp`”, “`stops_done`”, “`sc_left`”, “`sc_fresh`”, “`pit_paid`”; src/f1si/sim/kernel.py:115-121.] |
| Race cutoff reconstruction | API / Backend | Database / Storage | Replay driver owns `AsOfAccessor`, fits/filters each cutoff, and builds `RaceState`; policy receives state only. [VERIFIED: 05-CONTEXT.md — “its replay driver owns the AsOfAccessor, while policy code receives only a RaceState.”] |
| Metrics, explanation, and replay table | API / Backend | — | CLI presents score components and concise reason using the established plain-text pattern. [VERIFIED: 05-CONTEXT.md, D-03/D-06/D-07.] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | `>=3.12,<3.13` | Policy, regression orchestration, CLI | Project runtime declaration. [VERIFIED: pyproject.toml:1-2 — `requires-python = ">=3.12,<3.13"`] |
| NumPy | `>=2.3,<3` | Path arrays, `Generator`, least squares, empirical statistics | Existing simulator/runtime dependency. [VERIFIED: pyproject.toml:5 — `"numpy>=2.3,<3"`; official `lstsq` returns solution, effective rank, singular values: [NumPy documentation](https://numpy.org/doc/stable/reference/generated/numpy.linalg.lstsq.html).] |
| SciPy | `>=1.15,<2` | Existing Sobol-based simulator and common scenario generation | Already used by the established simulation stack; keep its random layout stable. [VERIFIED: pyproject.toml:12 — `"scipy>=1.15,<2"`.] |
| pytest | `>=9.1,<10` | Synthetic recovery, strategy conformance, replay and future-scramble tests | Existing test stack and phase validation contract. [VERIFIED: pyproject.toml dev dependencies and 05-VALIDATION.md.] |

No new package is needed. Use NumPy `lstsq` for the small linear basis and existing empirical samples for CVaR; adding a finance package would add no needed capability. [CITED: https://numpy.org/doc/stable/reference/generated/numpy.linalg.lstsq.html] No Package Legitimacy Audit is required because Phase 5 should not install external packages.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Backward regression plus pathwise decisions | Rank fixed forced schedules only | Fixed schedules can answer current option comparisons but do not estimate conditional continuation value, so they do not meet STR-01. [CITED: https://academic.oup.com/rfs/article-abstract/14/1/113/1587472] |
| NumPy least squares | New regression dependency | Existing NumPy supports the required linear solve and reports effective rank; a new dependency adds install and legitimacy work. [CITED: https://numpy.org/doc/stable/reference/generated/numpy.linalg.lstsq.html] |
| Scenario empirical CVaR | Parametric tail fit | Parametric assumptions are unnecessary for the finite Monte Carlo option samples and locked sample-tail convention. [CITED: https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf] |

## Architecture Patterns

### System Architecture Diagram

```text
CLI replay request
      |
      v
Replay driver (owns AsOfAccessor)
      | each cutoff: fresh snapshot -> fit -> wear filter -> RaceState
      v
StrategyPolicy.decide(current RaceState, driver)
      |                         \
      | current-cutoff options  \ future simulated path training
      v                          v
Shared seeded scenarios    Simulator path checkpoints / branch from a future cutoff
      |                          |
      |                   backward conditional-mean LSM recursion
      |                          |
      +-----------> per-option finishing samples
                                  |
                                  v
        mean + spread + CVaR10 + locked risk blend + deterministic reason
```

The accessor stays in replay composition. The strategy gets only the state snapshot and the simulator/model dependencies. The simulator path seam exists for simulated future states, not for reading historical race rows. [VERIFIED: 05-CONTEXT.md, D-04 and code integration points.]

### Recommended Project Structure

Follow existing `src/f1si/strategy/` for the policy. Keep any optional path-checkpoint data type or resume/branch support adjacent to `SimulationResult`/`SimulatorBackend` and the NumPy backend rather than exposing kernel arrays to policy callers. Keep replay orchestration beside current CLI commands or in a replay module composed by `cli.py`. [VERIFIED: 05-CONTEXT.md, Code Integration Points; src/f1si/interfaces.py:120-144.] Exact module split is discretionary.

### Pattern 1: Backward stopping regression over simulated paths

**What:** Build a pathwise target for the value of continuing at each stopping time. Initialize the value at the terminal horizon from simulated finishing-position cost. Moving backward, regress the later policy's realized path value on state features at this time, then compare the fitted conditional-mean continuation cost against the path's pit-now terminal finishing cost. Store the stopping decision/policy and its realized value for the next earlier step. Because finishing position is a cost, choose the lower value. [CITED: https://academic.oup.com/rfs/article-abstract/14/1/113/1587472]

**When to use:** Required for STR-01. The tutorial's exact payoff is different from racing, but its least-squares conditional-expectation and backward policy logic transfer to finite-horizon pit stopping.

**Suggested first basis:** intercept plus scaled current position or time gap, tire age, remaining laps, filtered wear mean/uncertainty, stops already made, and safety-car indicator/elapsed duration only where present in the simulated state. Keep the basis intentionally small; compare sample count with feature count, inspect least-squares rank/singular values, and define a deterministic fallback if the fit is underdetermined. These basis/fallback choices are discretionary; numeric thresholds must be labeled as assumptions. [CITED: https://numpy.org/doc/stable/reference/generated/numpy.linalg.lstsq.html]

**Pseudocode:**

```text
value[path] = terminal finishing-position cost[path]
for cutoff in future decision times, latest to earliest:
    continuation_mean = fit(state_features[path, cutoff], value[path])
    stop_value[path] = simulated pit-now finishing-position cost[path]
    stop[path] = stop_value[path] <= continuation_mean[path]
    value[path] = stop_value[path] if stop[path] else realized later-policy value[path]
```

The regression target must be realized value under the learned later stopping rule, not just the next-lap position or the output of a fixed-plan ranker. The predictor state and branch outcomes must be aligned by simulation path.

### Pattern 2: Minimal simulator path seam for true continuation

**What exists:** `SimulationResult` has final finishing positions and optional cumulative clocks. During each one-lap step, the NumPy implementation mutates order, clocks, tire ages, compounds, stops completed, safety-car countdown/fresh flag, and pit loss; the current public result does not return those checkpoint states. [VERIFIED: src/f1si/interfaces.py:120-144 — exact fields include `finish_positions`, `total_time_s`, `sc_lap_mask`, `stop_laps`, `pit_loss_paid_s`, `plan_sources`, `diagnostics`, `clock_s`; src/f1si/sim/numpy_backend.py:286-303 — exact mutable path arrays; src/f1si/sim/kernel.py:115-121.]

**Planning seam:** Expose only what regression and branching need, behind an optional result field or narrow internal API:

1. For the chosen driver at each future stopping time: simulated position/order, relative gap or clocks, tire age/current compound, stops already made, remaining distance, and regime/SC remaining duration. Use a small fixed feature representation for regression.
2. For branching an action from a checkpoint: enough whole-race state to preserve interactions with rivals (running order and cumulative clocks for all cars, each car's tire age/compound/stop count, and SC active/remaining state), or a deterministic resume operation that holds this checkpoint internally.
3. Path identity / reproducible future draw alignment so pit-now and continue values use common random numbers. Do not store every generated draw if deterministic seeded replay can reproduce it.

`clock_s` by itself is insufficient: it lacks order, tire ages/compounds, stops, and future safety-car state. Conversely, returning all per-lap arrays publicly is likely more than needed; keep checkpoint history opt-in and compact. This is a planning recommendation based on inspected simulator internals, not a locked API design. [MEDIUM: source inspection, cited above.]

**Scope control:** Avoid fitting the regression only to the current real `RaceState`—that is one observation, not cross-sectional simulated training data. Avoid presenting independent full-race forced plans as a substitute for state-conditioned continuation. At the current live cutoff, generate each candidate distribution with shared seeds/draws, then calculate the locked mean/CVaR score. [CITED: https://academic.oup.com/rfs/article-abstract/14/1/113/1587472] [VERIFIED: 05-CONTEXT.md, D-05/D-08.]

### Pattern 3: Current-cutoff risk score and empirical CVaR

For each fixed current action, compute the Monte Carlo sample mean, a transparent spread statistic/interval, and CVaR from the worst finishing-position tail (higher numeric position is worse). Sort ascending by:

```text
score = (1 - risk_aversion) * mean_finish + risk_aversion * CVaR10
```

Use fractional mass at the 10% boundary; default `risk_aversion` to 0.5 and reject non-finite/out-of-range values. Keep the mean/CVaR columns, since the blend alone hides why a selection changed. These are locked requirements, not assumptions. [VERIFIED: 05-CONTEXT.md D-01/D-02 — verbatim score, lower-is-better rule, fractional sample boundary, and default 0.5.]

**Interpretation guard:** The recursive LSM value remains conditional mean finishing-position cost. The risk blend ranks only candidate action distributions evaluated from the current cutoff. Do not pass CVaR or a blended tail objective back into the LSM continuation regression or claim dynamic CVaR optimality. [VERIFIED: 05-CONTEXT.md D-08 — “The Longstaff-Schwartz continuation regression estimates conditional mean finishing position”; “Apply the risk blend when ranking the current-cutoff candidate distributions”; “A nested or dynamically consistent CVaR recursion is outside Phase 5.”]

### Pattern 4: As-of replay composition

At each leader-lap cutoff, build a fresh snapshot, fit, filter output, and `RaceState`; pass that state to one deterministic policy call. The policy receives no accessor and no future observed rows. `--lap N` and the N row of full replay should share the exact same construction path. [VERIFIED: 05-CONTEXT.md D-03/D-04; `AsOfAccessor` documentation in src/f1si/data/asof.py read this session.]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Linear least-squares fitting | Custom matrix inverse / normal-equation solver | `numpy.linalg.lstsq` | Exposes least-squares solution and effective rank/singular values; avoids hand-built numerical solver. [CITED: https://numpy.org/doc/stable/reference/generated/numpy.linalg.lstsq.html] |
| Scenario generation | New random-number framework | Injected `numpy.random.Generator` and existing simulator/Sobol conventions | Reproducibility and common-random-number behavior are project contracts. [VERIFIED: src/f1si/interfaces.py:183-193; 05-CONTEXT.md D-05.] |
| CVaR optimizer / tail model | Parametric tail-fitting framework | Empirical worst-decile average over current option samples | Context defines an exact sample-tail statistic; no fitted tail distribution is needed. [VERIFIED: 05-CONTEXT.md D-02.] |
| As-of filtering | New policy-level data access | Existing `AsOfAccessor` replay composition | Maintains the guarded no-look-ahead boundary. [VERIFIED: src/f1si/data/asof.py; 05-CONTEXT.md D-04.] |

**Key insight:** LSM's core requirement is not a regression library; it is correctly aligned simulated states and future stopping values at each decision date. Avoid custom numerical machinery, but prioritize pathwise simulator support.

## Common Pitfalls

### Pitfall 1: Calling schedule ranking LSM
**What goes wrong:** A fixed list of complete forced plans is ranked and described as backward optimal stopping.
**Why it happens:** The forced-plan simulator already gives end-of-race samples, which makes schedule ranking convenient.
**How to avoid:** Require backward steps, a regression of later realized policy value on path state, and pathwise compare/continue decisions.
**Warning signs:** No regression at future stopping times; all candidate plans are chosen before looking at state-conditioned continuation values. [CITED: https://academic.oup.com/rfs/article-abstract/14/1/113/1587472]

### Pitfall 2: Regressing without enough simulated state
**What goes wrong:** Fitted continuation ignores race position/gaps or tire state and cannot distinguish paths with materially different stop value.
**Why it happens:** Existing result has terminal position and optional clocks but no full path checkpoint.
**How to avoid:** Add compact decision-time state features and a whole-race resume/branch seam; ensure the action outcomes and feature rows refer to the same path.
**Warning signs:** Regression gets one real `RaceState`, terminal-only samples, or clock history alone. [VERIFIED: src/f1si/interfaces.py:120-144; MEDIUM: src/f1si/sim/numpy_backend.py:286-303.]

### Pitfall 3: Describing the blend as CVaR-optimal stopping
**What goes wrong:** Users infer that future stop decisions optimize tail risk recursively.
**Why it happens:** The current-cutoff risk score can change the selected action even though the LSM continuation target is a conditional mean.
**How to avoid:** Use D-08 wording: conditional-mean LSM continuation plus CVaR-aware current option ranking. Do not make a dynamically CVaR-optimal claim.
**Warning signs:** Regression labels use the risk-blended score or CVaR is said to alter future continuation values. [VERIFIED: 05-CONTEXT.md D-08.]

### Pitfall 4: Misoriented or inconsistent CVaR
**What goes wrong:** Best finishes are accidentally put in the tail, or the boundary sample contributes more than exactly 10% mass.
**Why it happens:** Finish positions are costs where large values are worse; small integer outcomes create tied boundary values.
**How to avoid:** Sort high-to-low for the worst tail and fractional-weight the final observation to make exactly 10% mass; cover ties and sample counts not divisible by ten.
**Warning signs:** Tail score is unexpectedly better than mean on a clearly worse distribution. [VERIFIED: 05-CONTEXT.md D-02.]

### Pitfall 5: Broken determinism or unfair option comparisons
**What goes wrong:** Repeated `decide` calls differ, or option ranks are mostly driven by independent Monte Carlo noise.
**Why it happens:** The protocol has no RNG argument, and sequentially advancing one stream across options assigns different draws.
**How to avoid:** Own a deterministic RNG strategy inside the policy, reproduce scenario streams for each option from the same stable decision seed, and preserve simulator draw layout. Test repeated calls and common-random-number behavior.
**Warning signs:** Mutable generator state is advanced across equivalent calls; no seed path is apparent. [VERIFIED: src/f1si/interfaces.py:167-193; 05-CONTEXT.md D-05.]

### Pitfall 6: Replay leakage through final-fit reuse
**What goes wrong:** Early recommendations use pace/filter values fitted from later laps or results.
**Why it happens:** Full replay loops can reuse the final snapshot to save work.
**How to avoid:** Reconstruct snapshot, fit, filter, and state from each cutoff and keep the accessor in the replay driver. Use the existing future-scramble guard.
**Warning signs:** A single full-race fit is passed to all cutoff decisions. [VERIFIED: 05-CONTEXT.md D-04; 05-VALIDATION.md RPL-01 test requirement.]

### Pitfall 7: Unsupported explanation
**What goes wrong:** A reason asserts a tire cliff or future regime based on model inputs that cannot show it.
**Why it happens:** Narrative examples are mistaken for data-supported facts; the present model has linear wear and only coarse safety-car state.
**How to avoid:** Use a concise deterministic score reason unless visible as-of state and simulated outcomes support an undercut, current SC stop value, or wear-uncertainty statement.
**Warning signs:** Explanation mentions hidden future conditions or tire cliff. [VERIFIED: 05-CONTEXT.md D-06/D-07 and deferred ideas.]

## Code Examples

### Backward conditional-mean recursion

```text
For each future decision time in reverse:
    fit conditional mean of later-policy realized finish cost on path state
    compare fitted continuation cost with pathwise cost after stopping now
    record stop/continue choice and realized path value
```

This is an algorithm sketch rather than a source API. Its conditional-expectation and backward-induction structure is from the original paper. [CITED: https://academic.oup.com/rfs/article-abstract/14/1/113/1587472]

### Current-cutoff candidate score

```text
for each required candidate action:
    estimate mean_finish, spread, and fractional-boundary CVaR10 from shared samples
    score = (1 - risk_aversion) * mean_finish + risk_aversion * CVaR10
rank candidates by ascending score
```

The blend and tail convention are locked in CONTEXT.md D-01/D-02. This does not change the conditional-mean regression target. [VERIFIED: 05-CONTEXT.md D-01/D-02/D-08.]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Ranking only complete schedules and calling it Longstaff-Schwartz | Backward least-squares conditional continuation estimates and pathwise stop/continue decisions | Original method published 2001 | A genuine stopping policy requires decision-time states and future value targets, not only final plan ranks. [CITED: https://academic.oup.com/rfs/article-abstract/14/1/113/1587472] |
| Implicit risk behavior | Explicit D-08 separation of mean-continuation LSM from current-cutoff mean/CVaR action ranking | Phase context clarified 2026-11-13 | Stops dynamic CVaR claims from creeping into MVP descriptions. [VERIFIED: 05-CONTEXT.md D-08.] |

**Deprecated/outdated:** No project stack deprecations found for this phase. Do not import the prior 05-RESEARCH assumptions that formula, default risk value, or the role of CVaR in continuation were undecided; the current context now locks those details. [VERIFIED: current 05-CONTEXT.md D-01/D-02/D-08.]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` / Python runtime | Running tests and Bahrain replay | `uv` was present, but Python child process blocked in the recorded environment audit | `uv 0.13.5`; child-process failure OS error 4551 | Use authorized Python environment or CI; don't mark local tests/replay successful without successful process execution. [VERIFIED: 05-VALIDATION.md environment constraint.] |
| Bahrain 2023 local cache | Manual RPL-02 smoke replay | To confirm during execution | — | CI automated tests; live cache replay remains manual per validation strategy. [VERIFIED: 05-VALIDATION.md Manual-Only Verifications.] |

**Missing dependencies with no fallback:** None known for authoring/planning. A successful authorized Python runtime and race cache are execution prerequisites for the manual replay check.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest `>=9.1,<10` |
| Config file | `pyproject.toml` |
| Quick run command | `uv run python -m pytest -q tests/strategy/test_longstaff.py` |
| Full suite command | `uv run python -m pytest -q` |

Values and commands copied from [VERIFIED: 05-VALIDATION.md — “pytest >=9.1,<10”; “pyproject.toml”; “uv run python -m pytest -q tests/strategy/test_longstaff.py”; “uv run python -m pytest -q”.]

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STR-01 | Synthetic continuation recovery, fallback and StrategyPolicy conformance | unit + conformance | `uv run python -m pytest -q tests/strategy/test_longstaff.py tests/conformance/test_suites.py` | New strategy tests; shared suite exists |
| STR-02 | Mean/spread/CVaR, tail orientation and fractional boundary | unit | `uv run python -m pytest -q tests/strategy/test_longstaff.py -k cvar` | New strategy tests |
| STR-03 | Finite bounded risk, endpoint and rank-change behavior | unit | `uv run python -m pytest -q tests/strategy/test_longstaff.py -k risk` | New strategy tests |
| STR-04 | Deterministic evidence-based reason and friendly refusal | unit | `uv run python -m pytest -q tests/strategy/test_longstaff.py -k reason` | New strategy tests |
| RPL-01 | Full and selected-cutoff reconstruction; future-scramble | integration + guard | `uv run python -m pytest -q tests/test_cli_replay.py tests/guards/test_future_scramble.py` | New replay tests; guard exists |
| RPL-02 | Bahrain driver replay and invalid-input refusal | smoke + manual CLI | `uv run f1si replay bahrain-2023 --driver ALO` | New CLI coverage; local cache/runtime to confirm |

Test mapping copied from [VERIFIED: 05-VALIDATION.md Per-Task Verification Map and Manual-Only Verifications.]

### Sampling Rate

- Per task commit: run the focused command listed in the validation map.
- Per wave merge: run the full pytest suite, Ruff lint/format checks, and strict mypy.
- Phase gate: green CI, replay future-scramble guard, and successful Bahrain replay in an authorized Python environment. [VERIFIED: 05-VALIDATION.md Sampling Rate.]

### Wave 0 Gaps

- [ ] `tests/strategy/test_longstaff.py` — synthetic continuation recovery, fallback, CVaR orientation/fractional boundary, risk endpoints, deterministic reasons.
- [ ] `tests/test_cli_replay.py` — all-cutoff replay, selected-lap equality, driver selection, expected refusals.
- [ ] Register replay as an as-of consumer in `tests/guards/consumers.py`.
- [ ] Extend shared conformance suite to run the new policy.

These gaps are copied from [VERIFIED: 05-VALIDATION.md Wave 0 Requirements.]

## Security Domain

### Applicable ASVS Categories

ASVS is primarily a web-application verification standard; this phase is a local CLI, so most web controls do not apply. The current stable release is ASVS 5.0.0 (published 2025-05-30). [CITED: https://asvs.owasp.org/]

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user authentication in local replay CLI. |
| V3 Session Management | no | No interactive user sessions. |
| V4 Access Control | no | Local command operates on user-selected cached race/driver; validate requested identifiers and respect existing out-of-sample refusal. |
| V5 Input Validation | yes | Validate driver code, lap range, race slug, and finite risk input before simulation; keep expected invalid-input messages friendly. [CITED: https://asvs.owasp.org/] |
| V6 Cryptography | no | No cryptographic operation is introduced. |

### Known Threat Patterns for Python CLI / replay

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed CLI bounds or non-finite risk value | Tampering | Typed parsing plus explicit range/finite checks; test invalid values. |
| Read around as-of accessor / future leakage | Information disclosure | Keep accessor in replay driver; strategy accepts `RaceState`; register consumer and retain future-scramble tests. |
| Shell/path construction from user-provided race or driver string | Tampering | Resolve through existing catalog/argument APIs; do not interpolate raw input into shell or SQL. |

The app-level input and no-look-ahead controls above are phase-specific planning guidance; OWASP ASVS applies as a control reference, not as a certification claim. [CITED: https://asvs.owasp.org/]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The most practical first simulator extension is an opt-in compact checkpoint/resume seam rather than storing every raw draw or all intermediate arrays in each public result. | Pattern 2 | Could require a larger API change or a different memory/performance tradeoff; planner should validate against simulator complexity. |
| A2 | Use a small linear basis with scaled/normalized features and rank-aware fallback before trying richer regressors. | Pattern 1 | Basis may underfit; synthetic recovery and later backtest should reveal it without adding a new dependency now. |
| A3 | A spread statistic such as standard deviation plus a finishing interval will satisfy the unspecified “spread” presentation detail. | Pattern 3 | User-facing uncertainty display may prefer another spread summary; keep reported quantities explicit. |

**Locked details that are not assumptions:** The current-cutoff score formula, 0.5 default, fractional 10% tail, conditional-mean continuation, and explicit exclusion of nested/dynamic CVaR recursion are in D-01/D-02/D-08.

## Open Questions

1. **What exact checkpoint/resume surface fits the simulator best?**
   - What we know: Future path branching must preserve running order, clocks/gaps, per-car tire/stop state, regime state, and common draw identity; terminal outcomes alone and `clock_s` alone are insufficient.
   - What's unclear: Whether to expose a compact optional path history in `SimulationResult`, an internal resume API, or a staged path-batch callback.
   - Recommendation: Planner should choose the smallest seam that permits same-path stop/continue comparisons and keeps full per-lap checkpoint storage opt-in; estimate memory at expected sample count.

2. **What fallback should handle an underdetermined regression?**
   - What we know: NumPy least-squares reports effective rank; rank-deficient basis makes the fit unreliable. [CITED: https://numpy.org/doc/stable/reference/generated/numpy.linalg.lstsq.html]
   - What's unclear: Minimum observation/rank threshold and fallback behavior are discretionary.
   - Recommendation: Start with lower-dimensional basis reduction or a deterministic legal candidate fallback; label thresholds and cover both in synthetic tests.

3. **How should legal candidates behave at race boundaries?**
   - What we know: Candidate set is fixed by context; a requested stop may be illegal when there are fewer than 1–5 laps remaining.
   - What's unclear: Whether to omit illegal choices, collapse them to “stay out,” or explain a refusal.
   - Recommendation: Follow existing plan legality/refusal conventions and make every output row correspond to a genuinely executable action.

## Sources

### Primary (HIGH confidence)

- Longstaff & Schwartz, *Valuing American Options by Simulation: A Simple Least-Squares Approach*, Review of Financial Studies 14(1), 113–147 (2001), DOI 10.1093/rfs/14.1.113 — conditional expected continuation payoff via least squares. [CITED: https://academic.oup.com/rfs/article-abstract/14/1/113/1587472]
- NumPy, `numpy.linalg.lstsq` reference — solution, rank, singular values, and rank tolerance. [CITED: https://numpy.org/doc/stable/reference/generated/numpy.linalg.lstsq.html]
- Rockafellar & Uryasev, *Optimization of Conditional Value-at-Risk* — tail-risk definition/background. [CITED: https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf]
- OWASP ASVS official site — current project/standard overview and stable version. [CITED: https://asvs.owasp.org/]

### Repository sources (verified this session)

- `.planning/phases/05-longstaff-schwartz-strategy-live-replay/05-CONTEXT.md` — all locked strategy/risk/replay decisions, boundaries and integration points.
- `.planning/REQUIREMENTS.md` — Phase 5 requirement wording and IDs.
- `.planning/STATE.md` — ready-to-plan position and project state.
- `.planning/phases/05-longstaff-schwartz-strategy-live-replay/05-VALIDATION.md` — test map, missing tests, runtime limitation and Bahrain manual check.
- `CLAUDE.md` — project instructions.
- `src/f1si/interfaces.py`, `src/f1si/sim/numpy_backend.py`, `src/f1si/sim/kernel.py`, `src/f1si/strategy/free_track.py`, `src/f1si/state.py`, `src/f1si/data/asof.py`, `src/f1si/cli.py`, `pyproject.toml` — current contracts, simulator path arrays, as-of boundary, and installed stack.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — current `pyproject.toml` and phase validation file read.
- LSM algorithm: HIGH — original peer-reviewed paper and official NumPy least-squares documentation.
- Current-cutoff risk semantics: HIGH — explicitly locked in current CONTEXT.md D-01/D-02/D-08.
- Minimal simulator seam: MEDIUM — source code proves the current available/internals; the recommended optional checkpoint/resume shape is an engineering inference to be resolved by planner.
- Replay/no-look-ahead: HIGH — current CONTEXT.md, `AsOfAccessor` documentation, and future-scramble validation requirement.

**Research date:** 2026-11-13
**Valid until:** 2026-12-13 for algorithm and repository design; recheck package/runtime versions when execution is planned.
