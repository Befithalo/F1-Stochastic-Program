---
phase: 05-longstaff-schwartz-strategy-live-replay
plan: "04"
subsystem: strategy-replay
tags: [python, asof, sparse-pace, longstaff-schwartz, monte-carlo]
requires:
  - phase: 04-kalman-wear-filter
    provides: DEC-091 generic fuel, wear, and lap-noise priors plus cutoff-local wear-filter integration
  - phase: 05-plans-01-03
    provides: Longstaff-Schwartz policy, shared replay builder, documentation, and future-scramble guard
provides:
  - Cutoff-only sparse pace fallback for unsupported replay fits
  - Ranked output with disclosed prior basis and broad offset uncertainty at every tested cutoff
  - Fallback-aware selected/full equivalence and future-scramble coverage
affects: [phase-05-verification, phase-06-walk-forward-calibration]
actuals:
  tokens: 12064.25
  tasks: 3
  commits: 8
plan_head_before: d41b29648b5852d4ad67a6d0a39badbe20dc824a
plan_head_after: 3f979f84f2ae81292230779402635d5b7b077e24
tech-stack:
  added: []
  patterns:
    - Cutoff snapshots supply every sparse residual and fallback count
    - Unsupported-fit model outputs flow through the existing seeded policy
key-files:
  created:
    - src/f1si/pace/sparse_fallback.py
    - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-04-task1-red-evidence.json
    - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-04-task1-red.xml
    - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-04-task3-red-evidence.json
    - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-04-task3-red.xml
  modified:
    - .github/workflows/ci.yml
    - src/f1si/cli.py
    - src/f1si/strategy/longstaff.py
    - tests/test_cli_replay.py
    - tests/test_docs.py
    - tests/strategy/test_longstaff.py
    - tests/guards/consumers.py
    - tests/guards/test_future_scramble.py
    - DECISIONS.md
    - README.md
    - docs/explained/phase-05.md
key-decisions:
  - "DEC-101: use cutoff-visible clean residual medians with existing DEC-091 generic fuel/wear/noise priors and an [ASSUMED] 1.0 s offset SD."
  - "When a supported fit offers no legal second compound, rank stay out as the sole legal action."
patterns-established:
  - "Fallback metadata reports driver and field clean-lap counts in one deterministic, uncalibrated reason."
  - "The replay guard compares status, every ranked metric, and reason across future-row scrambles."
requirements-completed: [RPL-01]
coverage:
  - id: D1
    description: Unsupported cutoffs produce ranked uncertainty evidence from cutoff-only inputs
    requirement: RPL-01
    verification:
      - kind: integration
        ref: "tests/test_cli_replay.py; final full pytest run"
        status: pass
    human_judgment: false
  - id: D2
    description: Fallback output is invariant to future observations and locked races remain refused
    requirement: RPL-01
    verification:
      - kind: integration
        ref: "tests/guards/test_future_scramble.py; tests/guards/test_consumer_registry.py"
        status: pass
    human_judgment: false
  - id: D3
    description: The assumed sparse-data method and its limits are documented
    verification:
      - kind: other
        ref: "tests/test_docs.py tests/test_decisions_log.py: 48 passed"
        status: pass
    human_judgment: false
  - id: D4
    description: Cached Bahrain replay reports every cutoff and selected/full fallback blocks match
    requirement: RPL-01
    verification:
      - kind: manual_procedural
        ref: "Bahrain ALO --n 12: 57 ordered rows, 43 available, 14 fallback, no unavailable rows; selected laps 0 and 5 match full replay"
        status: pass
    human_judgment: false
  - id: D5
    description: Exact-head cross-platform CI matrix
    verification:
      - kind: other
        ref: "GitHub Actions run 43530884555, head 3f979f84f2ae81292230779402635d5b7b077e24"
        status: unknown
    human_judgment: false
duration: 86min
completed: 2026-11-14
status: complete
---

# Phase 05 Plan 04: Sparse Replay Fallback Summary

**Every replay cutoff now receives a ranked result using a cutoff-only, explicitly uncalibrated fallback when the joint pace fit is unsupported.**

## Performance

- **Duration:** about 86 minutes, including exact-head CI monitoring
- **Started:** 2026-11-13T22:54:55Z
- **Completed:** 2026-11-14T00:21:15Z
- **Tasks:** 3
- **Files modified:** 14, including persisted TDD RED evidence

## Accomplishments

- Added `SparsePaceFallback`, which centers driver residual medians from clean laps in the supplied snapshot, reuses DEC-091 generic fuel and wear assumptions, floors empirical residual noise at the generic noise level, and supplies generic wear uncertainty to the existing simulator.
- Unsupported replay rows now call the existing Longstaff-Schwartz policy with a broad **[ASSUMED] 1.0 s** driver-offset SD. Their deterministic reason discloses driver and field evidence counts, generic-prior basis, assumed scale, and uncalibrated status.
- Selected and full replay produce identical blocks at fallback laps 0 and 5 and supported lap 35. The future-scramble guard compares fallback status, every option metric, and reason.
- DEC-101, README, and the Phase 5 explainer document the sparse basis and its limits. DEC-091's fit-prior double-counting measurement question remains unchanged.
- Fixed an additional supported-cutoff edge: when a partial identified fit has no legal second compound, the existing two-compound rule leaves “stay out” as the sole legal action; the policy now returns its ranked evidence instead of raising.

## Task Commits

1. **Task 1: Ranked fallback behavior** — `3522656` (RED), `05d2304` (implementation), `c5460a7` (typing cleanup).
2. **Task 2: Decision and user documentation** — `96dc3a6`.
3. **Task 3: Future-scramble coverage and verification** — `fd812dc` (guard), `becc15a` (RED for single-compound stay-out edge), `03e7fe5` (fix), `3f979f8` (correct RED evidence timestamp).

The measured plan commit count is 8 (`d41b296` through `3f979f8`).

## Verification

- `uv run --python <trusted CPython 3.12> python -m pytest tests/test_cli_replay.py -x` — 22 passed.
- `uv run --python <trusted CPython 3.12> python -m pytest tests/test_docs.py tests/test_decisions_log.py -x -q` — 48 passed.
- Focused replay, consumer-registry, and future-scramble gate — 93 passed. After the stay-out edge fix, its strategy suite passed 15 tests and final full pytest reran every guard.
- `uv run --python <trusted CPython 3.12> ruff check .` — passed.
- `uv run --python <trusted CPython 3.12> ruff format --check .` — 154 files already formatted.
- `uv run --python <trusted CPython 3.12> python -m mypy` — no issues in 146 source files.
- Final `uv run --python <trusted CPython 3.12> python -m pytest` at the plan head — **989 passed, 25 deselected**.
- Cached Bahrain ALO replay with `--n 12` — 57 ascending cutoffs; 43 identified-fit rows and 14 fallback rows (laps 0–13); every row has ranked metrics, a recommendation, and a sentence reason. Selected laps 0 and 5 exactly match their full-replay blocks. Laps 14–15 correctly return the sole legal “stay out” option.
- GitHub Actions run [43530884555](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43530884555) is for exact final implementation head `3f979f84f2ae81292230779402635d5b7b077e24`. `checks (ubuntu-latest)` succeeded; `checks (windows-latest)` was cancelled at the workflow's 20-minute job limit while running pytest. Per the plan, the cross-platform result remains **pending**, and no earlier commit's run is counted.

## Verification Follow-up

- Increased `.github/workflows/ci.yml`'s per-platform timeout from 20 to 30 minutes after the exact-head Windows run reached the old limit during pytest (`d08e099`).
- Updated replay CLI help, README, and the Phase 5 explainer to state the enforced maximum of 200,000 simulations. Added documentation and CLI-help assertions; the focused replay/docs/decision suite passed **70 tests**, with Ruff, format, and mypy also passing.
- A new exact-head cross-platform run is required after these follow-up changes; its result will be recorded in the verification report.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Handle supported cutoffs with no legal fitted stop compound**
- **Found during:** Task 3 Bahrain smoke
- **Issue:** At laps 14–15, a partial identified fit had only one fitted compound and the selected driver had not used a second compound. No pit action was legal, but the policy passed empty stop outcomes to the backward continuation routine and returned unavailable.
- **Fix:** When no compound can legally be fitted, remove stopping times from the continuation regression and rank the existing stay-out action.
- **Files modified:** `src/f1si/strategy/longstaff.py`, `tests/strategy/test_longstaff.py`
- **Commit:** `03e7fe5`

**2. [Rule 3 - Blocking issue] Resolve strict typing errors at the pandas boundary**
- **Found during:** Task 3 full local gate
- **Issue:** Strict mypy could not narrow pandas tuple and group-key values, and policy wear-SD mapping types differed.
- **Fix:** Convert snapshot columns to typed NumPy arrays, narrow group keys, and align the fallback mapping annotation.
- **Files modified:** `src/f1si/pace/sparse_fallback.py`, `src/f1si/cli.py`, `tests/test_cli_replay.py`
- **Commit:** `c5460a7`

## Known Stubs

None found in files created or modified by this plan.

## Threat Flags

None. The fallback receives only an `AsOfAccessor` snapshot; no new data-access, authentication, or network surface was added.

## Self-Check: PASSED

The summary file exists, every listed task commit is an ancestor of the plan head, and all listed implementation, documentation, test, and RED-evidence files exist. The pre-existing untracked `05-VERIFICATION.md` remains untouched.
