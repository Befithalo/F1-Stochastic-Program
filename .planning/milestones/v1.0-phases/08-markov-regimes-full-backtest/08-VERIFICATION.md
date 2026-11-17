---
phase: 08-markov-regimes-full-backtest
verified: 2026-11-17T20:29:19Z
status: human_needed
score: 32/32 must-haves verified
re_verification:
  previous_status: human_needed
  gaps_closed:
    - "Exact-head GitHub Actions run 44163005087 passed on Ubuntu and Windows for SHA 9e2fd7575b29ceb1f1a2b6a8ce8aecd4f1fd919d."
    - "08-VALIDATION.md now records the successful matrix and Nyquist sign-off."
  gaps_remaining: []
  regressions: []
covered_files:
  - .planning/phases/08-markov-regimes-full-backtest/08-01-PLAN.md
  - .planning/phases/08-markov-regimes-full-backtest/08-01-SUMMARY.md
  - .planning/phases/08-markov-regimes-full-backtest/08-02-PLAN.md
  - .planning/phases/08-markov-regimes-full-backtest/08-02-SUMMARY.md
  - .planning/phases/08-markov-regimes-full-backtest/08-03-PLAN.md
  - .planning/phases/08-markov-regimes-full-backtest/08-03-SUMMARY.md
  - .planning/phases/08-markov-regimes-full-backtest/08-04-PLAN.md
  - .planning/phases/08-markov-regimes-full-backtest/08-04-SUMMARY.md
  - .planning/phases/08-markov-regimes-full-backtest/08-05-PLAN.md
  - .planning/phases/08-markov-regimes-full-backtest/08-05-SUMMARY.md
  - .planning/phases/08-markov-regimes-full-backtest/08-06-PLAN.md
  - .planning/phases/08-markov-regimes-full-backtest/08-06-SUMMARY.md
  - .planning/phases/08-markov-regimes-full-backtest/08-VALIDATION.md
  - .planning/M1-BASELINE.md
  - .planning/REQUIREMENTS.md
  - .planning/phases/08-markov-regimes-full-backtest/08-holdout-lock.json
  - .planning/phases/08-markov-regimes-full-backtest/08-in-sample-evaluation-lock.json
  - DECISIONS.md
  - README.md
  - docs/explained/phase-08.md
  - reports/backtest/phase-08-holdout.json
  - reports/backtest/phase-08.json
  - src/f1si/backtest/scoring.py
  - src/f1si/backtest/walk_forward.py
  - src/f1si/cli.py
  - src/f1si/evaluation/__init__.py
  - src/f1si/evaluation/holdout.py
  - src/f1si/regime/markov.py
  - src/f1si/sim/kernel.py
  - src/f1si/sim/numpy_backend.py
  - src/f1si/state.py
  - tests/backtest/test_holdout.py
  - tests/backtest/test_metrics.py
  - tests/backtest/test_walk_forward.py
  - tests/guards/consumers.py
  - tests/guards/import_scan.py
  - tests/guards/test_future_scramble.py
  - tests/regime/test_markov.py
  - tests/sim/test_safety_car.py
  - tests/test_cli_replay.py
  - tests/test_decisions_log.py
  - tests/test_docs.py
  - tests/test_state_builder.py
covered_digest: "v3:sha256:0fa6567fadb175c77b93761fddd5e8f843d4cd2d6896f9e27fea61e97974949e"
behavior_unverified: 0
overrides_applied: 0
unverified_prohibitions:
  - statement: "Do not claim Phase 7 PAC-06 passed or that Bayesian pace is superior."
    verification: judgment
    status: resolved
    flagged: true
    judge_verdict: "appears_honored_non_authoritative"
    disposition: "Non-authoritative autonomous judgment: documents preserve the miss; human review remains recommended by policy."
  - statement: "Do not describe SC or VSC pit-loss discounts as measured stop costs."
    verification: judgment
    status: resolved
    flagged: true
    judge_verdict: "appears_honored_non_authoritative"
    disposition: "Non-authoritative autonomous judgment: DEC-123 and published docs call the discounts assumptions; human review remains recommended by policy."
  - statement: "Do not train or update transitions from any 2026 holdout race or outcome."
    verification: judgment
    status: resolved
    flagged: true
    judge_verdict: "appears_honored_non_authoritative"
    disposition: "Non-authoritative autonomous judgment: the evaluator fits from 2023-2025 RACE_END snapshots and future-scramble/import-guard tests cover the boundary; human review remains recommended by policy."
human_verification:
  - test: "Review the Phase 08-01 prohibition about Phase 7 PAC-06 and Bayesian-superiority claims."
    expected: "Confirm the current disclosure of the unmet PAC-06 gate and the absence of superiority claims."
    why_human: "This is a judgment-tier prohibition; autonomous review is explicitly non-authoritative and must remain flagged."
  - test: "Review the Phase 08-01 prohibition about measured SC/VSC pit-loss discounts."
    expected: "Confirm public and decision-record wording continues to label those discounts as assumptions."
    why_human: "This is a judgment-tier prohibition; autonomous review is explicitly non-authoritative and must remain flagged."
  - test: "Review the Phase 08-01 prohibition about 2026 transition fitting."
    expected: "Confirm the feature-only 2023-2025 fit and protected holdout result boundary remain acceptable."
    why_human: "This is a judgment-tier prohibition; autonomous review is explicitly non-authoritative and must remain flagged."
audit_acknowledged:
  milestone: v1.0
  at: 2026-11-17
  status: human_needed
---

# Phase 8: Markov Regimes & Full Backtest Verification Report

**Phase Goal:** As a race strategist, I want to get regime-aware pit recommendations and assess a locked 20-race, per-era evaluation, so that I can judge the strategy model across changing race conditions.
**Verified:** 2026-11-17T20:29:19Z
**Status:** human_needed
**Re-verification:** Yes — refreshed after the validation record and exact-head CI completed.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | The five-state Markov model replaces the constant SC probability, and synthetic data recovers its transition matrix. | ✓ VERIFIED | `src/f1si/regime/markov.py` implements the ordered five-state estimator; `tests/regime/test_markov.py::test_seeded_synthetic_sequence_recovers_known_transition_rows` exercises recovery. The supplied full-suite run passed. |
| 2 | Pit loss varies by regime, and an SC in replay changes the recommendation. | ✓ VERIFIED | Regime-specific costs flow through `RaceState` and the simulator; `tests/test_cli_replay.py::test_bahrain_2023_controlled_safety_car_changes_top_action` covers the controlled Bahrain replay. Full-suite evidence passed. |
| 3 | The backtest covers at least 20 races and reports metrics separately by regulation era. | ✓ VERIFIED | The locked in-sample evaluation retains 20 race rows in `ground_effect_2022_2025`; the separate nine-race holdout is labeled `reg_2026`. README publishes the report-derived tables and denominators separately. |
| 4 | A holdout is locked, evaluated once, and its result is recorded in README. | ✓ VERIFIED | The 2026-09..17 lock predates scoring. The recorded failed preflight stopped before result access; one successful result-accessing score is recorded. Both read-only report verifiers passed; README carries the required retrospective-unblinding disclosure. |
| 5 | Bahrain 2023 replay works end to end and CI is green. | ✓ VERIFIED | The controlled Bahrain replay regression passed in the full suite. GitHub Actions run [44163005087](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/44163005087) completed successfully for both Ubuntu and Windows at SHA `9e2fd7575b29ceb1f1a2b6a8ce8aecd4f1fd919d`. |
| 6 | Plan 08-01: cutoff replay derives the visible state; transition matrix and costs reach simulation; matched Bahrain fixtures differ; linear pace/default CLI remain usable. | ✓ VERIFIED | Artifact checks 08-01 passed 3/3 and key-link checks 3/3. Code and replay regression are present and wired. |
| 7 | Plan 08-02: transitions are race-local; Dirichlet(1) rows normalize; synthetic recovery and precedence pass; DEC-121..123 are accurate. | ✓ VERIFIED | Artifact checks 08-02 passed 3/3 and key-link checks 2/2. The synthetic recovery, race-boundary, precedence, and cost assertions are covered by the supplied passing suite. |
| 8 | Plan 08-03: exact 20-race sample, precommitted contract, locked settings, per-race/era denominators, and overwrite refusal hold. | ✓ VERIFIED | Artifact checks 08-03 passed 3/3 and key-link checks 3/3. The read-only backtest verifier passed without rescoring. |
| 9 | Plan 08-04: holdout lock precedes result access; only the dedicated evaluator crosses the result door; fit is limited to 2023-2025; predictions freeze first; invalid state fails closed. | ✓ VERIFIED | Artifact checks 08-04 passed 3/3 and key-link checks 3/3. The evaluator/import guard and feature-scramble test are present; supplied full-suite evidence passed. |
| 10 | Plan 08-05: one successful holdout score follows the lock; reports stay separate; README/explainer values are report-derived; no post-score tuning/rescore occurs. | ✓ VERIFIED | Both report verifiers passed read-only. README and explainer identify separate reports and state “pre-registered but retrospectively unblinded”; no report was opened as raw prediction/classification data during verification. |
| 11 | Plan 08-06: DEC-121..125 match locked behavior; thirteen tasks have validation rows; tests and exact-head CI pass; Nyquist is not marked compliant before passing checks; no UI/UX scope was added. | ✓ VERIFIED | DEC records and all thirteen task rows are present. `08-VALIDATION.md` records successful Ubuntu/Windows CI on SHA `9e2fd7575b29ceb1f1a2b6a8ce8aecd4f1fd919d` and sets Nyquist compliant only after that result. No UI/UX scope was introduced. |

**Score:** 32/32 truths verified (5 roadmap truths plus 27 plan truths; 0 present, behavior-unverified).

### Prohibition Review

The three Phase 08-01 prohibitions are resolved as judgment-tier (`verification: judgment`). Autonomous non-authoritative judgments found no conflicting claim: the PAC-06 miss is explicit, SC/VSC discounts are labeled assumptions, and holdout transition fitting is limited to 2023-2025 feature snapshots. All three retain prominent human-review flags as required by GSD policy; they are not treated as authoritative passes.

### Evaluation Snapshot

| Evaluation | Scope | Podium Brier | Top-10 Brier | 90% interval coverage | Signed stop-timing error | Team-call agreement |
|---|---|---:|---:|---:|---:|---:|
| In-sample M1 baseline | 20 races, 2023-2025 | 0.055456 (grid 0.073693; 22,213 observations) | 0.144645 (grid 0.169086; 22,213 observations) | 16,508/20,001 (82.26%) | +1.174 laps (695 matched stops) | 17.22% (695 matched stops) |
| Holdout | 9 races, 2026-09..17 | 0.06639 | 0.14948 | 6,947/9,513 (73.03%) | +2.064 laps | 1.87% |

The holdout is **pre-registered but retrospectively unblinded**, not blind. Schedule research incidentally exposed outcome displays before the score; no displayed values were used for the lock, code, metrics, or tuning. The verification only ran read-only `--verify-existing` commands and did not access raw final classifications or external outcome sources. Do not tune or rescore.

Phase 7 PAC-06 remains unmet and is carried into M2 by DEC-130. Phase 8 uses linear pace by default; its results do not establish Bayesian superiority, calibration, or superiority over team calls.

The refreshed requirement ledger correctly marks PAC-06 as not met/carried to M2 and BKT-05 complete with the retrospective-unblinding disclosure. `.planning/M1-BASELINE.md` records the canonical 20-race baseline from the locked in-sample report without recomputing it.

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/f1si/regime/markov.py`, `src/f1si/state.py`, `src/f1si/sim/kernel.py` | Five-state model and per-regime simulator costs | ✓ VERIFIED | 08-01 artifact query: 3/3 pass. |
| `tests/regime/test_markov.py`, `DECISIONS.md` | Synthetic recovery and recorded model choices | ✓ VERIFIED | 08-02 artifact query: 3/3 pass; decision-coverage gate honored 5/5 context decisions. |
| `08-in-sample-evaluation-lock.json`, `walk_forward.py`, `phase-08.json` | Locked 20-race report | ✓ VERIFIED | 08-03 artifact query: 3/3 pass; read-only report verification passed. |
| `08-holdout-lock.json`, `evaluation/holdout.py`, import guard | Isolated one-time holdout evaluator | ✓ VERIFIED | 08-04 artifact query: 3/3 pass. |
| `phase-08-holdout.json`, `README.md`, `docs/explained/phase-08.md` | Separate report and disclosed limitations | ✓ VERIFIED | 08-05 artifact query: 3/3 pass; read-only holdout report verification passed. |
| `tests/test_decisions_log.py`, `08-VALIDATION.md` | Decision regression and validation map | ✓ VERIFIED | Both files pass artifact checks; the validation record names run 44163005087, its exact SHA, and successful Ubuntu/Windows jobs. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Replay CLI | Markov estimator | Cutoff-safe history | ✓ WIRED | Pattern and behavioral test present. |
| State | Simulator backend/kernel | Validated Markov matrix, regime, and costs | ✓ WIRED | Numeric inputs flow into per-lap simulator. |
| In-sample lock | Scoring/runner/report | Digest validation and frozen predictions | ✓ WIRED | GSD checks verified all three links. |
| Holdout evaluator | As-of/OOS accessors | Feature-only fit and post-freeze result access | ✓ WIRED | GSD checks verified all three links; import/future guards cover the boundary. |
| Holdout lock/report | README | Locked rows and report-derived values | ✓ WIRED | GSD checks verified all three links. |
| Validation record | GitHub Actions | Both matrix results recorded for exact pushed SHA | ✓ WIRED | `08-VALIDATION.md` links run 44163005087 and records both required jobs successful for exact SHA `9e2fd7575b29ceb1f1a2b6a8ce8aecd4f1fd919d`. |

## Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces real data | Status |
|---|---|---|---|---|
| Replay regime | transition matrix | Earlier-race cutoff history passed to `estimate_regime_model` | Yes | ✓ FLOWING |
| Simulator pit loss | active-regime cost | Validated `RaceState` costs and per-lap regime draw | Yes | ✓ FLOWING |
| In-sample evaluation | prediction/scoring rows | Registered race cutoffs, then separate result accessor | Yes | ✓ FLOWING |
| Holdout evaluation | frozen predictions/report | 2023-2025 feature snapshots and each 2026 cutoff snapshot; results requested only after prediction freeze | Yes | ✓ FLOWING |
| Published metrics | README/explainer tables | The two committed report artifacts, asserted by docs tests | Yes | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command/evidence | Result | Status |
|---|---|---|---|
| Synthetic transition recovery | `tests/regime/test_markov.py::test_seeded_synthetic_sequence_recovers_known_transition_rows` | Included in supplied passing Phase 8 suite | ✓ PASS |
| SC changes Bahrain replay action | `tests/test_cli_replay.py::test_bahrain_2023_controlled_safety_car_changes_top_action` | Included in supplied passing Phase 8 suite | ✓ PASS |
| Holdout future-feature isolation | `tests/guards/test_future_scramble.py::test_holdout_fit_and_cutoff_state_ignore_unseen_future_feature_rows` | Included in supplied passing Phase 8 suite | ✓ PASS |
| In-sample locked report | `uv run f1si backtest --report --output reports/backtest/phase-08.json --verify-existing` | Exit 0; read-only | ✓ PASS |
| Holdout locked report | `uv run f1si holdout --verify-existing --output reports/backtest/phase-08-holdout.json` | Exit 0; read-only, no result access or scoring | ✓ PASS |
| Exact-head CI | [GitHub Actions run 44163005087](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/44163005087) | Ubuntu and Windows jobs both concluded success at exact SHA `9e2fd7575b29ceb1f1a2b6a8ce8aecd4f1fd919d` | ✓ PASS |

## Probe Execution

No phase-declared or conventional probe scripts apply to this model/backtest phase.

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| REG-02 | 08-01, 08-02 | Five-state Markov model with synthetic recovery | ✓ SATISFIED | Estimator, seeded recovery, cutoff labeling, and replay wiring. |
| REG-03 | 08-01, 08-02 | Pit loss depends on regime | ✓ SATISFIED | State and simulator cost path; tests assert configured regime cost. |
| BKT-03 | 08-03, 08-05 | At least 20 races with per-era results | ✓ SATISFIED | Locked 20-race in-sample report; nine-race `reg_2026` holdout is separate. |
| BKT-05 | 08-04, 08-05 | Locked holdout touched once at milestone end | ✓ SATISFIED | Requirement ledger now marks complete with disclosure; one successful result-accessing score followed the lock and read-only verifier passed. |

**Orphaned requirements:** None. All four Phase 8 requirement IDs appear in phase plans.

## Test Quality Audit

| Test File | Linked requirement | Active | Skipped | Circular | Assertion level | Verdict |
|---|---|---:|---:|---:|---|---|
| `tests/regime/test_markov.py` | REG-02 | Yes | 0 | No | Value/recovery | PASS |
| `tests/test_cli_replay.py` | REG-02, REG-03 | Yes | 0 in supplied full run | No | Behavioral | PASS |
| `tests/test_state_builder.py`, `tests/sim/test_safety_car.py` | REG-03 | Yes | 0 | No | Value/behavioral | PASS |
| `tests/backtest/test_walk_forward.py`, `tests/backtest/test_metrics.py` | BKT-03 | Yes | 0 | No | Value/behavioral | PASS |
| `tests/backtest/test_holdout.py`, `tests/guards/test_import_ban.py`, `tests/guards/test_future_scramble.py` | BKT-05 | Yes | 0 | No | Value/behavioral | PASS |
| `tests/test_docs.py`, `tests/test_decisions_log.py` | BKT-03, BKT-05 | Yes | 0 | No | Value | PASS |

The repository has one `skipif` in the replay test file for the local race cache being absent; the supplied full run passed, so it did not suppress the replay evidence in that run. No requirement-linked disabled test or circular expected-value generator was identified. Supplied full suite: 1,243 passed, 33 deselected, 8 warnings, 87% coverage, 1,494.58s; Ruff, format, and mypy passed.

## Decision Coverage

All 5 trackable CONTEXT.md decisions are honored by shipped artifacts. This gate is advisory and does not affect status.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|

No unreferenced `TBD`, `FIXME`, or `XXX` markers were found in the phase's listed implementation, test, or documentation files. No UI/UX files were added to the Phase 8 plan scope.

## Human Verification Required

### 1. Review the Phase 08-01 judgment-tier PAC-06 prohibition

**Test:** Review whether the public Phase 7 PAC-06 disclosure remains accurate and avoids claiming Bayesian superiority.
**Expected:** The unmet gate remains explicit and no superiority claim is introduced.
**Why human:** This is a judgment-tier prohibition; autonomous review is non-authoritative and must leave the human-review flag visible.

### 2. Review the Phase 08-01 judgment-tier pit-cost prohibition

**Test:** Review whether public and decision-record language continues to call SC/VSC pit-loss discounts assumptions.
**Expected:** No wording presents those discounts as measured stop costs.
**Why human:** This is a judgment-tier prohibition; autonomous review is non-authoritative and must leave the human-review flag visible.

### 3. Review the Phase 08-01 judgment-tier holdout-isolation prohibition

**Test:** Review the feature-fit boundary and protected result-access path for 2026 holdout evaluation.
**Expected:** Transition fitting remains limited to 2023-2025 RACE_END features and final classifications remain behind the dedicated evaluator.
**Why human:** This is a judgment-tier prohibition; autonomous review is non-authoritative and must leave the human-review flag visible.

## Gaps Summary

All 32 roadmap/plan truths are verified, including successful exact-head Ubuntu and Windows CI. The phase remains `human_needed` because the three judgment-tier prohibitions retain mandatory human-review flags; autonomous judgments are non-authoritative and are not counted as human approval. PAC-06 remains unmet and carried to M2; BKT-05 is complete with the retrospective-unblinding disclosure, and the M1 baseline is recorded. No holdout rescore, raw 2026 prediction-row or classification inspection, or new result access was performed.

---

_Verified: 2026-11-17T20:29:19Z_
_Verifier: the agent (gsd-verifier)_
