---
phase: 05-longstaff-schwartz-strategy-live-replay
verified: 2026-11-14T01:44:14Z
status: human_needed
score: 19/20 must-haves verified
covered_files:
  - .github/workflows/ci.yml
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-01-PLAN.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-01-SUMMARY.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-02-PLAN.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-02-SUMMARY.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-03-PLAN.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-03-SUMMARY.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-04-PLAN.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-04-SUMMARY.md
  - DECISIONS.md
  - README.md
  - docs/explained/phase-05.md
  - src/f1si/cli.py
  - src/f1si/pace/sparse_fallback.py
  - src/f1si/sim/numpy_backend.py
  - src/f1si/strategy/longstaff.py
  - tests/conformance/registry.py
  - tests/conformance/test_suites.py
  - tests/guards/consumers.py
  - tests/guards/scramble.py
  - tests/guards/test_future_scramble.py
  - tests/strategy/test_longstaff.py
  - tests/test_cli_replay.py
  - tests/test_docs.py
covered_digest: "v3:sha256:6698b8002b8e03690be3886ef1928c8e94af187e0fbbe2051fafc748c8c94ba1"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 17/18
  gaps_closed:
    - "Every Bahrain replay cutoff returns a ranked recommendation with uncertainty using cutoff-visible inputs."
  gaps_remaining: []
  regressions: []
decision_coverage:
  honored: 8
  total: 8
  not_honored: []
human_verification:
  - test: "Confirm the replay display is clear enough to support a strategist's pit-timing choice."
    expected: "The ranked metrics, recommendation, reason, and fallback disclosure provide enough context to choose without treating fallback spread as calibrated confidence."
    why_human: "Whether the CLI wording and layout are useful for a real decision requires strategist judgment."
---

# Phase 5: Longstaff-Schwartz Strategy & Live Replay Verification Report

**Phase Goal:** As a strategist, I want to see explained, uncertainty-aware pit rankings per driver and lap, so that I can choose.
**Verified:** 2026-11-14T01:44:14Z
**Status:** human_needed
**Re-verification:** Yes — after closure of the RPL-01 gap and roadmap user-story format repair.

## User Flow Coverage

User story: “As a strategist, I want to see explained, uncertainty-aware pit rankings per driver and lap, so that I can choose.”

| Step | Expected | Evidence in codebase | Status |
|---|---|---|---|
| Run a replay for a supported Bahrain 2023 driver | Replay prints an ordered result for each cutoff | Ran f1si replay bahrain-2023 --driver ALO --n 12 against the local cache: 57 ordered rows, laps 0–56 | ✓ VERIFIED |
| Compare timing options and uncertainty | Each row presents a recommendation and ranked mean, spread, CVaR10, and score | Real output had no unavailable rows; lap 0 rendered 13 numeric options in ascending score order; all 57 rows had metric headings, a recommendation, and a sentence reason | ✓ VERIFIED |
| Use the display to choose a pit timing | The output gives the strategist usable context, including the sparse-data caveat | The output contains that information, but whether its wording and layout support a real choice needs strategist judgment | ? NEEDS HUMAN |
| Outcome: choose based on explained, uncertainty-aware rankings | Rankings and explanations are present at every tested cutoff | Output behavior is verified; decision usefulness is not machine-verifiable | ? NEEDS HUMAN |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A Bahrain replay for a supported driver returns a recommendation with uncertainty at every cutoff using only data visible at that cutoff. | ✓ VERIFIED | Real-cache ALO replay returned 57 ordered rows, including 14 fallback rows and no unavailable rows. The CLI rebuilds each cutoff from AsOfAccessor; fallback no-lookahead is covered by a passing named guard. |
| 2 | Each cutoff compares legal pit-now, next 1–5 lap, and stay-out options on common scenarios, displaying mean, spread, CVaR10, and blended score. | ✓ VERIFIED | Longstaff branches use shared seeded scenarios; the live lap-0 row showed 13 legal options with numeric metrics, sorted by score. CLI formatting reads each RankedOption field. |
| 3 | Risk appetite is bounded from 0 to 1, defaults to 0.5, and can change the ranking between mean-focused and tail-focused choices. | ✓ VERIFIED | Policy and parser validate the range and default. The named controlled-ranking regression passed in the prior verification, and the exact implementation-head CI suite is green. |
| 4 | Each recommendation has a deterministic one-sentence reason; fallback reasons disclose visible evidence, generic priors, the assumed offset scale, and uncalibrated status. | ✓ VERIFIED | The live replay emitted sentence-terminated reasons for all rows. Fallback source appends driver/field clean-lap counts, DEC-091 priors, [ASSUMED] 1.0 s, and uncalibrated status; the focused fallback test passed. |
| 5 | Longstaff-Schwartz passes the shared StrategyPolicy conformance suite. | ✓ VERIFIED | The real policy is registered in the shared suite. Exact-head CI completed successfully on Ubuntu and Windows. |
| 6 | The strategy fits conditional-mean continuation backward and makes pathwise stop-or-continue decisions. | ✓ VERIFIED | longstaff.py builds continuation values from simulated path states and selects pathwise costs; named algorithm tests are included in the successful exact-head CI suite. |
| 7 | The cached Bahrain replay works for a valid driver, and invalid race or driver inputs receive a friendly refusal. | ✓ VERIFIED | Real ALO replay completed from the local cache; parser/catalog validation and refusal tests pass in exact-head CI. |
| 8 | Replay rejects unknown identifiers, invalid lap bounds, invalid simulation counts, and invalid risk before simulation. | ✓ VERIFIED | CLI boundary validation and no-simulation-on-invalid-input regression are present; covered by the exact-head test run. |
| 9 | Boundary actions remain legal, empty outcome samples refuse, and ties use stable ordering. | ✓ VERIFIED | Longstaff filters stop candidates at the legal boundary, rejects empty samples, and sorts ties deterministically; linked tests are included in exact-head CI. |
| 10 | CVaR10 weights exactly the worst ten percent, including fractional boundary mass. | ✓ VERIFIED | _cvar10 validates finite samples and accounts for fractional tail mass; the named value test passed in the prior verification and is in the exact-head CI suite. |
| 11 | Each cutoff rebuilds its snapshot, fit, filter output, and RaceState through AsOfAccessor; the policy receives only the cutoff RaceState. | ✓ VERIFIED | cli.py obtains snapshot/history for the same AsOf value, builds the state, and calls policy.analyze(state). AsOfAccessor routes through guarded snapshot/history queries. |
| 12 | Selected replay output equals the corresponding full-replay row for both fallback and supported cutoffs. | ✓ VERIFIED | Live Bahrain selected laps 0 and 5 matched their full-replay blocks exactly; the regression also checks synthetic laps 0, 5, and supported lap 35. |
| 13 | Future observations do not change supported-cutoff replay output. | ✓ VERIFIED | Existing supported-cutoff future-scramble test is registered and included in the exact-head full suite. |
| 14 | Future observations do not change fallback output at an unsupported-fit cutoff. | ✓ VERIFIED | Ran tests/guards/test_future_scramble.py::test_strategy_replay_fallback_ignores_future_at_sparse_cutoff — 1 passed. It compares fallback status, option evidence, and reason after future-row scrambling. |
| 15 | Sparse fallback values use only cutoff-visible clean residuals plus generic priors, and retain explicit nonzero uncertainty when no clean lap is visible. | ✓ VERIFIED | sparse_fallback.py consumes snapshot.laps, classifies clean rows, computes field-centered residual medians and robust noise, and uses the generic noise floor plus [ASSUMED] 1.0 s offset SD. Named fallback output and no-lookahead checks passed; live lap 0 disclosed zero visible laps. |
| 16 | A supported cutoff with no legal fitted stop compound still ranks the legal stay-out action instead of returning unavailable. | ✓ VERIFIED | Ran tests/strategy/test_longstaff.py::test_policy_ranks_stay_out_when_no_second_compound_is_available — 1 passed; the real Bahrain replay also returned ranked rows at all cutoffs. |
| 17 | Neighboring cutoffs remain independently constructed; unknown races/drivers, empty data, and locked out-of-sample races are refused. | ✓ VERIFIED | AsOfAccessor enforces race and lap bounds and rejects out-of-sample races; the linked refusal and guard tests pass in exact-head CI. |
| 18 | DEC-101, README, and the explainer accurately disclose the fallback basis and limits without changing DEC-091's measurement question. | ✓ VERIFIED | Compared DEC-101 and user-facing documentation with fallback implementation and Phase 5 context. The docs state the cutoff boundary, generic priors, assumed offset scale, and uncalibrated limitation; decision coverage reports 8/8 honored. |
| 19 | Required quality checks and cross-platform CI succeed for the implementation under review. | ✓ VERIFIED | Local Ruff check, Ruff format check, and mypy passed. GHA run 43536333390 reports success for both Windows and Ubuntu and full pytest. Its head is 69184aed02f14a9ba606725bd3c551db890e107c; source, tests, workflow, README, decisions, and explainer are unchanged between that commit and this checkout. [Run details](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43536333390). |
| 20 | The replay presentation is clear enough for a strategist to use when choosing a pit timing. | ? UNCERTAIN | The CLI output is present and complete, but decision usefulness and clarity require a human user-flow review. |

**Score:** 19/20 truths verified (0 present, behavior-unverified)

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| src/f1si/pace/sparse_fallback.py | Cutoff-local generic-prior pace fallback | ✓ EXISTS + SUBSTANTIVE + WIRED | Computes clean residual centers, robust lap-noise SD, generic wear SD, and visible-lap metadata; called from the unsupported-fit branch in cli.py. |
| src/f1si/cli.py | Selected and full replay path | ✓ EXISTS + SUBSTANTIVE + WIRED | Uses a shared cutoff builder and formatter; passes a same-cutoff state through the real policy and prints ranked values/reasons. |
| src/f1si/strategy/longstaff.py | Longstaff-Schwartz strategy analysis | ✓ EXISTS + SUBSTANTIVE + WIRED | Builds legal actions, shared-path branches, ranking metrics, and deterministic reasons. |
| src/f1si/sim/numpy_backend.py | Shared checkpoint and branch simulation | ✓ EXISTS + SUBSTANTIVE + WIRED | _branch_paths exists at line 192 and is called by Longstaff at line 225. The artifact matcher missed the qualified method export, but direct inspection confirmed it. |
| tests/test_cli_replay.py | Replay and sparse-fallback regression coverage | ✓ EXISTS + SUBSTANTIVE + WIRED | Tests lap-zero and sparse output, cutoff residuals, all-cutoff coverage, refusals, and selected/full equality. |
| tests/strategy/test_longstaff.py | Strategy algorithm and policy behavior tests | ✓ EXISTS + SUBSTANTIVE + WIRED | Covers CVaR, risk, legal boundaries, stable ties, stay-out-only behavior, and deterministic reasons. |
| tests/guards/consumers.py | Registered strategy replay consumer | ✓ EXISTS + SUBSTANTIVE + WIRED | Invokes the same _replay_at_cutoff builder as CLI output. |
| tests/guards/scramble.py | Future-row mutation harness | ✓ EXISTS + SUBSTANTIVE + WIRED | Scrambles observations after the requested cutoff while preserving declared public metadata. |
| tests/guards/test_future_scramble.py | No-lookahead replay guard | ✓ EXISTS + SUBSTANTIVE + WIRED | Covers supported and sparse fallback cutoff paths, including full-grid guards. |
| tests/conformance/registry.py and tests/conformance/test_suites.py | Shared StrategyPolicy conformance | ✓ EXISTS + SUBSTANTIVE + WIRED | The real Longstaff policy is registered and passed through the shared suite in CI. |
| DECISIONS.md | Phase assumptions and method decisions | ✓ EXISTS + SUBSTANTIVE | DEC-101 follows DEC-100 and records the fallback assumption and no-lookahead basis. |
| README.md and docs/explained/phase-05.md | User-facing replay guidance | ✓ EXISTS + SUBSTANTIVE + WIRED | README links the explainer; both distinguish fitted and fallback rows and state the uncertainty limits. |
| tests/test_docs.py | Documentation contract checks | ✓ EXISTS + SUBSTANTIVE + WIRED | Checks required guide sections, replay instructions, and tour references; passed in exact-head CI. |
| .github/workflows/ci.yml | Required cross-platform quality gates | ✓ EXISTS + SUBSTANTIVE | Defines Ubuntu/Windows jobs for Ruff, formatting, mypy, full pytest, and the Linux import-ban canary. |

**Artifacts:** Plan 05-04 artifact query passed 5/5. Plan 05-01's matcher returned 4/5 because it did not recognize the qualified _branch_paths method; direct source and caller inspection verified it. The 05-04 link query could not interpret its descriptive endpoints as file paths, so those three links were traced manually below.

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| numpy_backend.py | longstaff.py | Shared checkpoints and indexed branch draws | ✓ WIRED | _branch_paths is called by Longstaff; plan checker verified the link. |
| longstaff.py | cli.py | Policy analysis and ranked result rendering | ✓ WIRED | CLI invokes analysis and formats option rows and reason. |
| cli.py | AsOfAccessor | Same-cutoff snapshot and history | ✓ WIRED | _replay_at_cutoff builds AsOf(race_id, lap), then requests snapshot/history for that value. |
| cli.py | LongstaffSchwartzPolicy | Cutoff RaceState passed into strategy | ✓ WIRED | Policy receives state and driver, not a data accessor. |
| AsOfAccessor.snapshot | SparsePaceFallback | Visible clean rows produce fallback centers | ✓ WIRED | snapshot is passed to SparsePaceFallback; the model classifies only snapshot.laps. |
| SparsePaceFallback and RaceState | LongstaffSchwartzPolicy | Fallback model, all dry compounds, and uncertainty reach simulator | ✓ WIRED | Fallback model, wear SDs, and assumed pace-offset SD are supplied before analyze(state). |
| CLI replay | tests/guards/consumers.py | Registered consumer invokes production cutoff builder | ✓ WIRED | strategy_replay calls _replay_at_cutoff and returns status, all option metrics, and reason. |
| README.md | phase-05.md | Replay explanation link | ✓ WIRED | Link is present and checked by documentation tests. |
| phase-05.md | DECISIONS.md | Method rationale links | ✓ WIRED | The guide cites the sequential Phase 5 decisions through DEC-101. |
| tests/test_docs.py | phase-05.md | Documentation assertions | ✓ WIRED | Test module checks the guide contract and references the explainer. |

**Wiring:** All listed connections verified. For 05-04, query verify.key-links returned no machine-verified links because plan entries used descriptive prose rather than relative paths; manual source trace confirms all three connections.

## Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces real data | Status |
|---|---|---|---|---|
| CLI replay builder | snapshot/history | AsOfAccessor guarded DuckDB reads at one race cutoff | Yes — real cached race/history | ✓ FLOWING |
| Sparse fallback | clean residuals, driver offsets, sigma_sparse | Clean rows in that cutoff's RaceSnapshot | Yes — snapshot-derived; generic priors are explicit | ✓ FLOWING |
| Longstaff analysis | branch outcomes and option distributions | Seeded NumPy simulator using cutoff RaceState and fallback PaceModel | Yes — simulated from the requested state | ✓ FLOWING |
| CLI formatter | mean, spread, CVaR10, score, recommendation, reason | StrategyAnalysis RankedOption values | Yes — live Bahrain rows printed numeric values | ✓ FLOWING |

No static response or hardcoded-empty rendered values were found. The fallback's generic parameters are declared priors and assumptions, not mock data.

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Sparse fallback renders ranked evidence | .venv\Scripts\python.exe -m pytest tests/test_cli_replay.py::test_sparse_fallback_replay_returns_ranked_options_at_lap_zero_and_fallback_lap -q | 1 passed in 16.65 s | ✓ PASS |
| Fallback no-lookahead invariant | .venv\Scripts\python.exe -m pytest tests/guards/test_future_scramble.py::test_strategy_replay_fallback_ignores_future_at_sparse_cutoff -q | 1 passed in 23.71 s | ✓ PASS |
| Supported stay-out-only boundary | .venv\Scripts\python.exe -m pytest tests/strategy/test_longstaff.py::test_policy_ranks_stay_out_when_no_second_compound_is_available -q | 1 passed in 1.45 s | ✓ PASS |
| Bahrain cached replay | f1si replay bahrain-2023 --driver ALO --n 12 | 57 ascending rows; 14 fallback; no unavailable rows; every row had a recommendation and sentence reason | ✓ PASS |
| Selected/full fallback equivalence | f1si replay bahrain-2023 --driver ALO --lap 0 or --lap 5 --n 12 | Both selected rows exactly matched their full-replay blocks | ✓ PASS |
| Lap-zero numeric option output | f1si replay bahrain-2023 --driver ALO --lap 0 --n 12 | 13 option rows; numeric finite metrics; ascending scores; fallback label, recommendation, and sentence reason | ✓ PASS |

Two focused pytest checks exceeded the verifier's preferred 10-second spot-check target in this Windows environment; both completed successfully. The full test suite was not rerun locally because the exact implementation-head CI run ran it on both operating systems.

## Probe Execution

Not applicable. This phase does not declare probe-based verification, no probe path appears in the plans or summaries, and the repository has no scripts directory.

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| STR-01 | 05-01, 05-02, 05-04 | Longstaff-Schwartz policy implements StrategyPolicy | ✓ SATISFIED | Algorithm implementation, shared conformance registration, exact-head CI. |
| STR-02 | 05-01 | Options ranked by mean and CVaR10 with spread | ✓ SATISFIED | RankedOption metrics and real output; exact fractional-tail regression. |
| STR-03 | 05-01 | Risk setting shifts mean/tail ranking | ✓ SATISFIED | Bounded risk blend and controlled ranking test in exact-head CI. |
| STR-04 | 05-01, 05-03 | Recommendation includes a one-sentence reason | ✓ SATISFIED | Policy reason construction and all 57 live rows had sentence-terminated reasons. |
| RPL-01 | 05-02, 05-04 | Recommendation with uncertainty at every replay cutoff | ✓ SATISFIED | Sparse fallback closes the prior 16/57 unavailable-row gap; live run returned 57/57 ranked rows. |
| RPL-02 | 05-01, 05-02, 05-03 | Live Bahrain replay works end to end | ✓ SATISFIED | Real ALO cache replay and selected-lap equivalence completed. |

**Coverage:** 6/6 requirements satisfied. No phase-assigned requirement was orphaned from the plans.

### Decision Coverage

The decision-coverage gate evaluated the Phase 5 context and found all 8 trackable decisions honored by shipped artifacts. This gate is non-blocking.

### Test Quality Audit

| Test File | Linked Requirement | Active | Skipped | Circular | Assertion Level | Verdict |
|---|---|---|---|---|---|---|
| tests/test_cli_replay.py | RPL-01, RPL-02, STR-02–04 | Yes | 0 | 0 | Behavioral and value assertions | ✓ PASS |
| tests/guards/test_future_scramble.py | RPL-01 | Yes | 0 | 0 | Behavioral equality after future-row mutation | ✓ PASS |
| tests/strategy/test_longstaff.py | STR-01–04 | Yes | 0 | 0 | Numerical values and policy behavior | ✓ PASS |
| tests/conformance/test_suites.py | STR-01 | Yes | 0 | 0 | Shared contract behavior | ✓ PASS |
| tests/test_docs.py | STR-04, RPL-02 | Yes | 0 | 0 | Documentation contract assertions | ✓ PASS |

**Disabled requirement tests:** 0. **Circular expected-value generation:** 0. **Insufficient assertions:** none found. Tests compare against explicit formulas or changed future data; no linked test writes system-generated output as its own oracle.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|

No active TODO/FIXME/TBD/XXX markers, placeholder implementations, empty handlers, or hardcoded empty rendered data were found in Phase 5 code and linked tests. Historical “placeholder” references in DECISIONS.md describe earlier decisions, not unfinished Phase 5 behavior.

### Advisory (New Scope, Unevidenced)

None.

### Human Verification Required

### 1. Confirm the CLI supports a strategist's choice

**Test:** Run f1si replay bahrain-2023 --driver ALO --n 12 and review the ranking, sentence reason, and fallback disclosure. Decide whether they provide enough context to choose a pit timing.

**Expected:** The options are understandable and the uncertainty/basis is clear enough to support a choice; fallback spread is not mistaken for calibrated confidence.

**Why human:** Decision usefulness and wording clarity are user-experience judgments; code and assertions can establish the displayed content but cannot determine if it is useful to a strategist.

### Gaps Summary

The carried RPL-01 gap is closed: the real Bahrain replay now returns ranked recommendations with uncertainty on all 57 cutoffs, including 14 explicitly labeled fallback rows. Selected laps 0 and 5 match their full-replay rows. Cutoff-only construction, fallback future-scramble invariance, the supported stay-out boundary, requirements, documentation, and cross-platform quality gates are verified. No blocking implementation gaps remain. The strategist's judgment that the CLI display supports an actual pit-timing choice is the one outstanding human check.

---

_Verified: 2026-11-14T01:44:14Z_  
_Verifier: the agent (gsd-verifier)_
