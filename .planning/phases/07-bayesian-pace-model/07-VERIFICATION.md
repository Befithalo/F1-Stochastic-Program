---
phase: 07-bayesian-pace-model
verified: 2026-11-17T19:33:19Z
status: passed
score: 4/4 must-haves verified (1 accepted override)
covered_files:
  - .planning/phases/07-bayesian-pace-model/07-01-PLAN.md
  - .planning/phases/07-bayesian-pace-model/07-01-SUMMARY.md
  - .planning/phases/07-bayesian-pace-model/07-02-PLAN.md
  - .planning/phases/07-bayesian-pace-model/07-02-SUMMARY.md
  - .planning/phases/07-bayesian-pace-model/07-03-PLAN.md
  - .planning/phases/07-bayesian-pace-model/07-03-SUMMARY.md
  - .planning/phases/07-bayesian-pace-model/07-04-PLAN.md
  - .planning/phases/07-bayesian-pace-model/07-04-SUMMARY.md
  - .planning/phases/07-bayesian-pace-model/07-05-PLAN.md
  - .planning/phases/07-bayesian-pace-model/07-05-SUMMARY.md
  - .planning/phases/07-bayesian-pace-model/07-05-evaluation-lock.json
  - DECISIONS.md
  - README.md
  - docs/explained/phase-07.md
  - docs/phases/07-bayesian-pace-model.md
  - reports/pace/phase-07.json
  - src/f1si/backtest/pace_evaluation.py
  - src/f1si/backtest/scoring.py
  - src/f1si/backtest/walk_forward.py
  - src/f1si/cli.py
  - src/f1si/pace/bayesian.py
  - src/f1si/pace/training.py
  - src/f1si/state.py
  - tests/backtest/test_bayesian_accuracy.py
  - tests/backtest/test_walk_forward.py
  - tests/guards/consumers.py
  - tests/guards/test_future_scramble.py
  - tests/pace/test_bayesian_model.py
  - tests/pace/test_bayesian_recovery.py
  - tests/pace/test_bayesian_training.py
  - tests/sim/test_bayesian_pace.py
  - tests/test_cli_replay.py
  - tests/test_decisions_log.py
  - tests/test_docs.py
covered_digest: "v3:sha256:6cfe20437586f96cf414894e8b539ae8aaca67621d69208642e9d4d06279178d"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "On held-out laps the Bayesian next-lap error is at least 15% lower than the per-compound linear baseline."
    reason: "The locked score definitively misses the 15% gate, but the user explicitly directed Phase 7 and M1 closeout after the miss was reported. Preserve PAC-06 as unmet, never retune or rescore this holdout, and carry the comparison forward to a separate M2 held-out-stint gate."
    accepted_by: "befit (user-directed M1 closeout)"
    accepted_at: "2026-11-17T19:32:16Z"
re_verification:
  previous_status: gaps_found
  previous_score: 3/4
  gaps_closed:
    - "PAC-06: accepted for M1 administrative closure while remaining measured as unmet and carried into M2; not marked VERIFIED."
    - "Synthetic Bayesian recovery: the named known-truth recovery test passed."
    - "MVP story format: Phase 7 roadmap goal is now a valid user story."
    - "Plan 07-04 artifact declaration now names tests/backtest/test_walk_forward.py."
  gaps_remaining: []
  regressions: []
---

# Phase 7: Bayesian Pace Model Verification Report

**Phase Goal:** As a race strategist, I want to compare a hierarchical Bayesian pace model with the linear model, so that I can judge its uncertainty and next-lap predictions against real data.
**Verified:** 2026-11-17T19:33:19Z
**Status:** passed (with one accepted override)
**Re-verification:** Yes — after the documented closeout decision and verification gaps were addressed.

## User Flow Coverage

User story: “As a race strategist, I want to compare a hierarchical Bayesian pace model with the linear model, so that I can judge its uncertainty and next-lap predictions against real data.”

| Step | Expected | Evidence | Status |
|---|---|---|---|
| Select a model | Replay and backtest accept linear or Bayesian pace selection while retaining linear as the default. | `src/f1si/cli.py`; `tests/test_cli_replay.py`; `tests/backtest/test_walk_forward.py` | ✓ |
| Compare next-lap predictions | The registered paired evaluation presents linear and Bayesian MAE over the same eligible target rows. | `reports/pace/phase-07.json`; read-only report verification passed. | ✓ |
| Judge the measured outcome | The report shows Bayesian MAE 0.538745 s vs linear 0.364033 s and clearly marks PAC-06 unmet. | Saved locked report, README and Phase 7 explainer. | ✓ |
| Interpret uncertainty and limits | Synthetic recovery is tested; the real report records fit diagnostics and states that one observed era cannot identify a between-era effect. | `tests/pace/test_bayesian_recovery.py`; report `fit_summary` and `era_identifiability`. | ✓ |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | The PyMC model with car/team, driver, tire/compound, fuel and era effects fits real 2023–2025 data and implements `PaceModel`. | ✓ VERIFIED | `BayesianPaceFit.predict` implements the prediction contract; `training.py` assembles earlier history plus cutoff-visible snapshots; the saved evaluation reports 74/74 successful fits. |
| 2 | On synthetic data generated from known parameters the model recovers them within stated tolerance. | ✓ VERIFIED | `uv run pytest tests/pace/test_bayesian_recovery.py::test_seeded_multiera_panel_recovers_pace_effects_and_predictive_coverage -q` passed: 1 passed, one PyTensor warning, 10.92 s. The test asserts fixed-effect tolerances, posterior interval inclusion and predictive coverage. |
| 3 | On held-out laps the next-lap error is at least 15% lower than the per-compound linear baseline. | PASSED (override) | **Measured truth remains unmet:** the frozen 1,348-pair report has linear MAE 0.364033047 s, Bayesian MAE 0.538744808 s and -47.993379% improvement (`pac_06_met: false`). The user-authorized override allows M1 administrative closure only; PAC-06 remains visibly unmet and carried into M2. |
| 4 | Replay and backtest run with the Bayesian model without changes outside the model swap. | ✓ VERIFIED | Model selection is wired through existing replay/backtest composition. The named cutoff-history/cache identity test passed (1 passed, 2.05 s); prior implementation and future-scramble tests remain in the phase evidence. |

**Score:** 4/4 including 1 accepted override; PAC-06 is not counted as a measured pass.

### Override Record

The user-authorized PAC-06 override is administrative: it accepts closing M1 with the failed gate preserved in history and carried into M2. It does not change `reports/pace/phase-07.json`, does not mark PAC-06 verified, and does not claim real-data superiority. The locked score was checked read-only; no refit, rescore, or outcome access occurred.

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/f1si/pace/bayesian.py` | Bayesian fit implementing `PaceModel` and state summaries | ✓ VERIFIED | Substantive seeded PyMC implementation with prediction and shared uncertainty summaries. |
| `src/f1si/pace/training.py` | Cutoff-safe clean-lap panel | ✓ VERIFIED | Uses passed `History` and `RaceSnapshot`, enforces chronology and snapshot cutoff, maps stable categories. |
| `tests/pace/test_bayesian_recovery.py` | Synthetic recovery and NUTS evidence | ✓ VERIFIED | Known-truth test directly passed; assertions check effects, intervals and predictive coverage. |
| `src/f1si/cli.py` | Replay model selection and composition | ✓ VERIFIED | Bayesian selector reaches existing state, policy and simulator path; linear remains the default. |
| `src/f1si/backtest/walk_forward.py` | Backtest model selection | ✓ VERIFIED | Selector forwarded into cutoff prediction path. |
| `tests/backtest/test_walk_forward.py` | Backtest model-swap and cutoff regressions | ✓ VERIFIED | Plan now names this concrete file; artifact verification passes. |
| `.planning/phases/07-bayesian-pace-model/07-05-evaluation-lock.json` | Pre-registered race group, target mask and metric | ✓ VERIFIED | Lock is committed before scoring; its digest matches the report. |
| `reports/pace/phase-07.json` | One-shot measured outcome | ✓ VERIFIED | Read-only report verifier validates schema, race rows, metric arithmetic, diagnostics and gate result. |
| `DECISIONS.md`, `README.md`, `docs/phases/07-bayesian-pace-model.md` | Method choices and measured outcome | ✓ VERIFIED | Preserve actual underperformance, unmet PAC-06 and one-era identifiability limit. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `BayesianPaceFit` | `PaceModel` | `predict` signature | WIRED | Shared conformance coverage and recovery/model tests. |
| `build_bayesian_training_panel` | `fit_bayesian_panel` | Indexed cutoff-local rows | WIRED | Current laps clipped at `snapshot.cutoff_s`; history must be earlier than current event. |
| Replay `AsOfAccessor` | Bayesian fit | Same-cutoff snapshot and earlier history | WIRED | `_prepare_replay_context` uses one `AsOf(race_id, lap)` for both inputs; named cache/cutoff test passed. |
| Backtest selector | Cutoff prediction path | `pace_model` forwarding | WIRED | `walk_forward.py` passes selection through to replay/model composition. |
| Locked targets | Saved report | Paired clean-target mask and MAE | WIRED | Report rows reconcile with aggregate counts; read-only verification passed. |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `training.py` | Training panel | As-of history and current snapshot rows | Yes | ✓ FLOWING |
| `bayesian.py` | Posterior summaries and predictions | Real training panel or seeded synthetic arrays | Yes | ✓ FLOWING |
| `pace_evaluation.py` | Paired targets and MAEs | Locked race cache, cutoff predictions and clean target rows | Yes | ✓ FLOWING |
| `reports/pace/phase-07.json` | Frozen evaluation metrics | One-shot evaluator output validated against lock | Saved measured artifact | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Synthetic known-truth recovery | `uv run pytest tests/pace/test_bayesian_recovery.py::test_seeded_multiera_panel_recovers_pace_effects_and_predictive_coverage -q` | 1 passed; one PyTensor warning; 10.92 s | ✓ PASS |
| Replay cutoff history and fit-cache identity | `uv run pytest tests/test_cli_replay.py::test_bayesian_replay_uses_cutoff_history_and_caches_only_matching_fit_identity -q` | 1 passed in 2.05 s (prior verification) | ✓ PASS |
| Saved Phase 7 score verification | `uv run python -m f1si.backtest.pace_evaluation --verify-existing` | Verified existing report for lock `f11423b3249de7794d32ccbce89d299cd361e1758c472ceaa36ce0448572bb48`; read-only | ✓ PASS |
| One-shot and saved-report consistency | `uv run pytest tests/backtest/test_bayesian_accuracy.py::test_one_shot_command_refuses_existing_report_and_verifies_without_scoring -q` | 1 passed in 1.19 s (prior verification) | ✓ PASS |

The orchestrator also reports the full suite passed: 1,243 tests. This re-verification did not rerun the suite.

## Probe Execution

Not applicable; this is not a migration or tooling phase and no probe is declared.

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| PAC-05 | 07-01, 07-02, 07-04, 07-05 | Hierarchical Bayesian pace model with required effects implements `PaceModel` | ✓ SATISFIED | Source, conformance, cutoff-safe training and real fit diagnostics. |
| PAC-06 | 07-03, 07-05 | Synthetic recovery and at least 15% lower real next-lap error | ACCEPTED OVERRIDE — MEASURED UNMET | Synthetic recovery passed. Real comparison remains -47.993379% and does not meet the gate; user-authorized M1 administrative closeout carries it into M2. |
| DAT-03, DAT-04, DAT-05 | 07-02 | As-of access, future-scramble protection and era boundary | ✓ SATISFIED | Cutoff checks and registered future-scramble consumer/tests. |
| RPL-01, BKT-01 | 07-04 | Bayesian replay/backtest path with cutoff safety | ✓ SATISFIED | Model-selection wiring and regression coverage. |
| UI-03 | 07-05 | Plain-language phase explanation | ✓ SATISFIED | Explainer and phase documentation report measured results and limits. |

No orphaned Phase 7 requirement IDs were found.

## Test Quality Audit

| Test File | Linked Requirement | Active | Skipped | Circular | Assertion Level | Verdict |
|---|---|---:|---:|---|---|---|
| `tests/pace/test_bayesian_recovery.py` | PAC-06 | Yes | 0 observed | No generated expected values in recovery assertions | Value/behavior | PASS; direct named test passed |
| `tests/pace/test_bayesian_model.py` | PAC-05/PAC-06 | Yes | 0 observed | No | Value/conformance | Active coverage present |
| `tests/pace/test_bayesian_training.py`, `tests/guards/test_future_scramble.py` | PAC-05, DAT-03/04/05 | Yes | 0 observed | No | Behavioral | Active cutoff and scramble coverage present |
| `tests/test_cli_replay.py`, `tests/backtest/test_walk_forward.py` | PAC-05, RPL-01, BKT-01 | Yes | One cache-gated replay test uses `skipif` | No | Behavioral | Other active coverage exists; named cutoff test passed |
| `tests/backtest/test_bayesian_accuracy.py` | PAC-06 | Yes | 0 observed | No | Value/behavior | One-shot and saved-report consistency test passed |

**Disabled tests on requirements:** 1 cache-gated replay test; active tests cover the same model-selection path.
**Circular patterns detected:** 0 in the inspected recovery/evaluation assertions.
**Insufficient assertions:** None identified.

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|---|---|---|---|
| None | No unresolved `TBD`, `FIXME`, or `XXX` markers in inspected implementation and linked tests | — | No blocker anti-pattern found. |

## Human Verification Required

None. The prior behavior-unverified synthetic recovery item is closed by the named passing test. This is an infrastructure/model phase; no manual UI or external-service check is required.

## Re-verification Changes

- PAC-06 remains objectively unmet but has a user-authorized, narrowly scoped override for M1 administrative closure. The status is shown as `PASSED (override)` and remains distinct from `VERIFIED`.
- The known-truth synthetic recovery test now directly passes.
- The roadmap story validates, and Plan 07-04 now points to the concrete backtest test file.
- The Phase 7 report still verifies read-only; no score was recomputed and no final outcomes were accessed.

---

_Verified: 2026-11-17T19:33:19Z_
_Verifier: the agent (gsd-verifier)_
