---
phase: 05-longstaff-schwartz-strategy-live-replay
verified: 2026-11-13T22:27:43Z
status: gaps_found
score: 17/18 must-haves verified
covered_files:
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-01-PLAN.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-01-SUMMARY.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-02-PLAN.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-02-SUMMARY.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-03-PLAN.md
  - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-03-SUMMARY.md
  - DECISIONS.md
  - README.md
  - docs/explained/phase-05.md
  - src/f1si/cli.py
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
covered_digest: "v3:sha256:38799e426a13949895db994bc11050fb54070e47f68cbb5e34b2e9a6422d63f1"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "User starts a replay for any Bahrain 2023 driver and steps through every lap, seeing a recommendation each lap using only data up to that lap."
    status: failed
    reason: "Replay emits unavailable rows when a cutoff-visible pace fit is unsupported. The recorded Bahrain ALO run had 16 unavailable cutoffs out of 57, so the user does not receive a ranked recommendation with uncertainty on every lap. This is deliberate behavior, but no accepted override changes the roadmap or RPL-01 contract."
    artifacts:
      - path: "src/f1si/cli.py"
        issue: "_replay_at_cutoff returns unavailable when the cutoff-local fit is unsupported, and the formatter emits Status: unavailable instead of ranked options."
      - path: "tests/test_cli_replay.py"
        issue: "test_full_replay_emits_every_cutoff_and_marks_unsupported_cutoffs asserts unavailable rows."
    missing:
      - "Provide a cutoff-only, uncertainty-aware ranked recommendation for unsupported early laps, or explicitly revise the requirement to accept unavailable rows."
      - "Preserve selected/full replay equivalence and the no-look-ahead guard for any fallback."
---

# Phase 5: Longstaff-Schwartz Strategy & Live Replay Verification Report

**Phase Goal:** User can replay Bahrain 2023 lap by lap for any driver and get a ranked, explained pit recommendation with uncertainty.
**Verified:** 2026-11-13T22:27:43Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | User replays Bahrain for a driver and receives a ranked recommendation with uncertainty on every lap. | ✗ FAILED | The recorded ALO run has 57 cutoffs, 16 explicitly unavailable. This conflicts with roadmap SC1 and RPL-01. The CLI test asserts those unavailable rows. |
| 2 | Longstaff-Schwartz fits conditional-mean continuation backward and makes pathwise stop/continue decisions. | ✓ VERIFIED | longstaff.py implements continuation fitting and backward path decisions; synthetic recovery and pathwise tests are present and current-head CI passed. |
| 3 | Pit now, next five stop laps, and stay out are compared on common scenarios with mean, spread, CVaR10, and blended score. | ✓ VERIFIED | Policy builds the legal actions on seeded branches and records all metrics in RankedOption; CLI assertions cover the output. |
| 4 | Risk aversion in [0,1], default 0.5, can change the action ranking. | ✓ VERIFIED | Validation and blend are implemented. The named controlled-ranking test passed locally (1 passed, 1.20s). |
| 5 | A cutoff recommendation has a deterministic one-sentence reason; policy receives only RaceState. | ✓ VERIFIED | CLI sends cutoff-built RaceState to policy; stable score-grounded reason and no-mutation behavior are tested. |
| 6 | Cached Bahrain replay works for a known driver; invalid inputs receive friendly refusals. | ✓ VERIFIED | Replay command, catalog resolution and refusal tests are present; a cached ALO run was recorded. |
| 7 | Parser, replay-service and policy reject invalid identifiers, bounds, counts and risk before simulation. | ✓ VERIFIED | Checks exist at CLI and policy boundaries; refusal tests are in the passing test set. |
| 8 | Near the last legal stop boundary, unavailable actions are omitted, empty samples refuse, and ties have stable order. | ✓ VERIFIED | Dedicated boundary, empty-sample and stable-tie tests cover these behaviors. |
| 9 | CVaR10 weights exactly the worst ten percent, including a fractional boundary observation. | ✓ VERIFIED | _cvar10 and its fractional-tail value test cover the exact statistic. |
| 10 | Late-race and unsupported-evidence reasons use legal candidates and a stable sentence fallback. | ✓ VERIFIED | Policy reason construction is deterministic; CLI sentence-completes unavailable explanations. |
| 11 | Each cutoff rebuilds snapshot, fit, wear filter and RaceState through AsOfAccessor before policy analysis. | ✓ VERIFIED | _replay_at_cutoff builds from one AsOf snapshot; plan key-link checks and source trace confirm the chain. |
| 12 | Selected --lap N output equals row N of full replay. | ✓ VERIFIED | Both use the same builder and formatter; named equality test and recorded lap-20 cache smoke report exact match. |
| 13 | Scrambling future observations leaves supported replay output unchanged. | ✓ VERIFIED | Registered strategy_replay consumer is included in future-scramble guards; current-head CI passed. |
| 14 | Longstaff passes shared StrategyPolicy conformance. | ✓ VERIFIED | Longstaff is registered and routed through the shared deterministic/legal-action/no-mutation suite; current-head CI passed. |
| 15 | Neighboring cutoffs use separate visible data; unknown race/driver and empty data refuse clearly. | ✓ VERIFIED | Independent AsOf construction, input refusal tests, and scramble guard cover this behavior. |
| 16 | Explanation, README and decision entries accurately describe behavior, assumptions, limits and replay commands. | ✓ VERIFIED | Explainer, README link and DEC-096–DEC-100 are present; documentation tests passed. |
| 17 | Automated checks and CI are separated from cached smoke, and OS error 4551 is never counted as a pass. | ✓ VERIFIED | Plan 05-03 separates these results. Current-head [Actions run 43517435861](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43517435861) succeeded at ed522746306433eb568955a510ca3faa08c3d282 on Ubuntu and Windows. Local pytest had 983 passes and one Hypothesis deadline flake; the isolated reproduction command passed in 0.99s. |
| 18 | Cached Bahrain replay is ordered and selected-lap smoke matches the full row. | ✓ VERIFIED | Recorded smoke: 57 ascending cutoffs; lap 20 matched exactly. It also recorded 16 unavailable rows, which exposes truth 1. |

**Score:** 17/18 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| src/f1si/sim/numpy_backend.py | Private checkpoint and branch seam | ✓ VERIFIED | _PathCheckpoint and NumpySimulator._branch_paths exist and are called by Longstaff. Artifact matcher missed the qualified method export; direct source inspection confirms it. |
| src/f1si/strategy/longstaff.py | Strategy policy and option analysis | ✓ VERIFIED | Substantive backward regression, path decisions, CVaR scoring, ranking, validation and reasons. |
| src/f1si/cli.py | Selected and full replay | ✓ VERIFIED | Parser, checks, as-of builder, ordered cutoff loop and output rendering are wired. Unavailable rows are the gap above. |
| tests/strategy/test_longstaff.py | Algorithm, risk, boundary and reason tests | ✓ VERIFIED | Value and behavioral tests cover the algorithm. |
| tests/test_cli_replay.py | Selected/full replay and input tests | ✓ VERIFIED | Ordering, equivalence, refusals and unavailable cutoffs are covered. |
| tests/guards/consumers.py | Registered replay consumer | ✓ VERIFIED | strategy_replay uses the CLI cutoff builder. |
| tests/guards/scramble.py | Future-row scramble harness | ✓ VERIFIED | Preserves race-distance metadata while scrambling observed values. |
| tests/guards/test_future_scramble.py | Replay future-data guard | ✓ VERIFIED | Supported-cutoff and full-grid guard coverage. |
| tests/conformance/registry.py | Longstaff policy registration | ✓ VERIFIED | Factory constructs real Longstaff policy. |
| tests/conformance/test_suites.py | Shared policy conformance | ✓ VERIFIED | Registration calls check_strategy_policy. |
| DECISIONS.md | Phase method decisions | ✓ VERIFIED | DEC-096–DEC-100 record assumptions, scoring, common paths, boundaries and as-of semantics. |
| README.md | Replay usage | ✓ VERIFIED | Full/selected replay, inputs, defaults and explainer link are documented. |
| docs/explained/phase-05.md | Plain-language explanation | ✓ VERIFIED | Method, data path, assumptions and limitations are explained. |
| tests/test_docs.py | Documentation contract | ✓ VERIFIED | Headings, tour, link and replay text are checked. |

**Artifacts:** 14/14 substantive and wired. verify.artifacts reported 4/5 for Plan 05-01 because its matcher missed NumpySimulator._branch_paths; manual source inspection confirmed the method at line 192 and its caller.

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| numpy_backend.py | longstaff.py | Checkpoint branches and common future draws | ✓ WIRED | Branch method called by strategy; plan pattern check passes. |
| longstaff.py | cli.py | Analysis result to text output | ✓ WIRED | CLI invokes policy and renders options/reason. |
| cli.py | data/asof.py | Snapshot per cutoff | ✓ WIRED | Each cutoff has a new AsOfAccessor snapshot. |
| cli.py | longstaff.py | Cutoff-built state to policy | ✓ WIRED | Policy boundary receives RaceState only. |
| consumers.py | test_future_scramble.py | Registered consumer used by guards | ✓ WIRED | Sampled/full-grid guard references registry. |
| README.md | phase-05.md | Replay guide link | ✓ WIRED | Link present. |
| phase-05.md | DECISIONS.md | Method rationale links | ✓ WIRED | DEC-096 is referenced. |
| test_docs.py | phase-05.md | Documentation assertions | ✓ WIRED | Explainer is included in tests. |

**Wiring:** 8/8 connections verified.

### Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Real data | Status |
|---|---|---|---|---|
| cli.py replay | snapshot/lap history | AsOfAccessor query to local cache at cutoff | Yes | ✓ FLOWING |
| cli.py replay | fit, wear estimate, RaceState | Cutoff-local fit, Kalman filter and state builder | Yes when cutoff evidence supports fit; otherwise explicit unavailable | ✓ FLOWING, with gap above |
| longstaff.py | option distributions | Simulator branch runs from cutoff state with shared seeded scenarios | Yes | ✓ FLOWING |
| CLI output | ranked options/reason | Policy analysis on branch distributions | Yes for supported cutoffs | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command/evidence | Result | Status |
|---|---|---|---|
| Risk endpoints change ranking | uv run --python <signed-python> python -m pytest tests/strategy/test_longstaff.py::test_risk_endpoints_change_ranking_for_controlled_samples -q | 1 passed in 1.20s | ✓ PASS |
| Selected cutoff matches full row | tests/test_cli_replay.py::test_selected_replay_matches_full_replay_cutoff_block and recorded cache smoke | Current-head CI passed; recorded lap-20 smoke exactly matched | ✓ PASS |
| Every replay cutoff is output | tests/test_cli_replay.py::test_full_replay_emits_every_cutoff_and_marks_unsupported_cutoffs and recorded cache smoke | 57 ordered rows; 16 unavailable | ✓ PASS for row coverage; gap for recommendation coverage |
| Future observations do not alter supported output | tests/guards/test_future_scramble.py::test_strategy_replay_ignores_future_at_a_supported_cutoff | Current-head CI passed | ✓ PASS |

### Probe Execution

Not applicable. No phase-declared probe script applies to this strategy/replay phase.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| STR-01 | 05-01/02/03 | Longstaff policy implements StrategyPolicy | ✓ SATISFIED | Algorithm, synthetic tests, shared conformance, CI. |
| STR-02 | 05-01 | Rank timing options by mean and CVaR@10% | ✓ SATISFIED | Option metrics, exact tail statistic, controlled tests. |
| STR-03 | 05-01 | Risk appetite shifts mean/tail ranking | ✓ SATISFIED | Named test passed; CLI supports risk [0,1], default 0.5. |
| STR-04 | 05-01/03 | Each recommendation includes a one-sentence reason | ✓ SATISFIED | Deterministic reason and sentence fallback tests. |
| RPL-01 | 05-02 | Replay any driver and recommend with uncertainty every lap | ✗ BLOCKED | 16/57 Bahrain cutoffs have no recommendation or uncertainty. |
| RPL-02 | 05-01/02/03 | Bahrain replay works end to end | ✓ SATISFIED | Cached full/selected replay ran and lap 20 matched; unavailable rows still block RPL-01. |

**Coverage:** 5/6 requirements satisfied; RPL-01 blocks phase completion.

### Test Quality Audit

| Test File | Linked requirement | Active | Skipped | Circular | Assertion strength | Verdict |
|---|---|---:|---:|---:|---|---|
| tests/strategy/test_longstaff.py | STR-01–04 | Yes | 0 | 0 | Value + behavior | ✓ PASS |
| tests/test_cli_replay.py | STR-02–04, RPL-01/02 | Yes | 0 | 0 | Behavioral; asserts unavailable rows | ✓ PASS as implemented; exposes contract gap |
| tests/guards/test_future_scramble.py | STR-01, RPL-01 | Yes | 0 | 0 | Behavioral equality under scramble | ✓ PASS |
| tests/conformance/test_suites.py | STR-01 | Yes | 0 | 0 | Shared protocol behavior | ✓ PASS |
| tests/test_docs.py | STR-04, RPL-02 | Yes | 0 | 0 | Documentation contract | ✓ PASS |

**Disabled tests:** 0. **Circular patterns:** 0. **Insufficient assertions:** none found. No linked test writes generated expected values. The local full pytest result had one Hypothesis deadline flake; that named test passed isolated and both current-head CI jobs passed.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|

No implementation debt markers, placeholder returns, empty handlers, or hardcoded empty rendered data were found in the phase code and linked tests. Historical “placeholder” mentions in DECISIONS.md describe earlier decisions, not Phase 5 stubs.

### Human Verification Required

None. The remaining issue is an observable contract failure, not a behavior requiring human judgment. Recorded real-data smoke and tests establish which cutoffs are unavailable.

### Gaps Summary

The strategy, risk ranking, option uncertainty metrics, deterministic explanations, as-of reconstruction, future-data guard, shared policy conformance, documentation, and current-head cross-platform CI are present and verified. The phase does not meet the roadmap promise or RPL-01: full Bahrain replay intentionally reports 16 cutoffs as unavailable when cutoff-local fit evidence is insufficient. This behavior is honest about model limits, but the phase contract requires a recommendation every lap. Add a no-look-ahead recommendation path for these cutoffs or revise the acceptance contract with explicit owner approval. Until then, the phase goal is not fully achieved.

---

_Verified: 2026-11-13T22:27:43Z_  
_Verifier: the agent (gsd-verifier)_

