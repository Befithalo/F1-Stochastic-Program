---
phase: 05-longstaff-schwartz-strategy-live-replay
plan: 03
subsystem: strategy
tags: [documentation, cli, replay, cvar10, python312]
requires:
  - phase: 05-01
    provides: Longstaff-Schwartz policy and selected-cutoff replay
  - phase: 05-02
    provides: Full as-of replay and explicit unavailable cutoffs
provides:
  - Phase 5 owner-facing method and file-tour explanation
  - Replay CLI input help, docs and method decision records
  - Default-size Bahrain full and selected-cutoff smoke evidence
affects: [phase-05-verification, phase-06-backtest]
actuals:
  tokens: 10500
  tasks: 2
  commits: 6
tech-stack:
  added: []
  patterns:
    - One cutoff builder and formatter for selected and full replay
    - Sentence-complete unavailable cutoff reasons
key-files:
  created:
    - docs/explained/phase-05.md
  modified:
    - README.md
    - DECISIONS.md
    - src/f1si/cli.py
    - src/f1si/strategy/longstaff.py
    - tests/test_docs.py
    - tests/test_cli_replay.py
    - tests/strategy/test_longstaff.py
    - tests/guards/test_future_scramble.py
    - .planning/phases/05-longstaff-schwartz-strategy-live-replay/05-VALIDATION.md
key-decisions:
  - "DEC-096 through DEC-100 document the assumed continuation basis, exact current-cutoff CVaR10 score, comparable branches, tie order, input rules, and as-of replay behavior."
  - "The current Phase 5 branch remains unverified by GitHub Actions; the plan is halted at this required external gate rather than treating an older main run as current evidence."
patterns-established:
  - "Full and selected replay use identical cutoff construction and output formatting."
  - "Unavailable cutoff reasons are complete sentences and never imply a fitted recommendation."
requirements-completed: [STR-01, STR-04, RPL-02]
coverage:
  - id: D1
    description: Phase 5 explanation, README commands, input rules, and decision records
    requirement: STR-04
    verification:
      - kind: integration
        ref: "tests/test_docs.py tests/test_decisions_log.py tests/test_cli_replay.py (65 passed after final wording fix)"
        status: pass
    human_judgment: false
  - id: D2
    description: Full local lint, format, type and test gate
    verification:
      - kind: other
        ref: "ruff check .; ruff format --check .; mypy (145 files); pytest (983 passed, 25 deselected)"
        status: pass
      - kind: integration
        ref: "tests/test_cli_replay.py::test_full_replay_emits_every_cutoff_and_marks_unsupported_cutoffs after unavailable-reason punctuation fix"
        status: pass
    human_judgment: false
  - id: D3
    description: Cached Bahrain full replay and selected-lap equivalence at the default 50,000 scenarios
    requirement: RPL-02
    verification:
      - kind: manual_procedural
        ref: "Full replay: 57 ordered cutoffs; selected lap 20 exactly matches the full replay block; 41 available and 16 explicitly unavailable cutoffs."
        status: pass
    human_judgment: false
  - id: D4
    description: GitHub Actions verifies the current Phase 5 branch on Ubuntu and Windows
    verification:
      - kind: other
        ref: "No remote agent-05-01 branch or current-commit workflow run exists; latest main run 43390811407 is an earlier Phase 4 commit."
        status: unknown
    human_judgment: true
    rationale: "The local commits have not been pushed, so GitHub Actions cannot have evaluated this branch."
duration: 39min
completed: 2026-11-13
status: halted
---

# Phase 05 Plan 03: Replay Guide and Validation Summary

**The Phase 5 method is documented and the cached Bahrain replay passes locally; current-branch GitHub Actions remains the closeout gate.**

## Performance

- **Duration:** about 39 minutes
- **Started:** 2026-11-13T16:12:00Z
- **Stopped:** 2026-11-13T16:51:28Z
- **Tasks:** 2 (local work and validation complete; current-branch CI pending)
- **Files modified:** 10 before this summary

## Accomplishments

- Added the five-section Phase 5 explainer and README instructions for full and selected-cutoff replay.
- Recorded DEC-096 through DEC-100, labeling the discretionary regression basis/fallback and tie policy as assumptions.
- Added `--risk-aversion` as a descriptive alias while preserving `--risk`, documented the accepted catalog, driver, lap, count and risk rules, and made unavailable-row reasons complete sentences.
- Installed and used official PSF-signed per-user CPython 3.12.10 after the prior uv-managed interpreter was blocked by Windows Application Control (OS error 4551).
- Ran the full local suite: **983 passed, 25 deselected** in 519.37 seconds. Ruff check, Ruff format check, and strict mypy passed; final focused docs/decisions/replay tests passed 65 tests.
- Ran the default 50,000-simulation Bahrain replay for ALO. It printed 57 ascending cutoffs (0 through 56), 41 available recommendations and 16 explicit unavailable rows. The selected lap-20 output exactly matched the corresponding full-replay block. After the reason-punctuation fix, a real-cache 12-simulation replay confirmed all 57 reasons ended as sentences and selected/full lap 20 still matched.

## Task Commits

1. **Task 1: Tests for replay rules, explainer and assumptions** — `0987869` (red tests).
2. **Task 1: CLI replay rules and risk alias** — `4b118de`.
3. **Task 1: Phase 5 guide and method decisions** — `7b29035`.
4. **Task 2: Strict typing cleanup exposed by the required full gate** — `bac167c`.
5. **Task 2: Sentence-complete unavailable reasons** — `872bce7` (test), `e609e33` (fix).

The latest observed GitHub Actions run is [43390811407](https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/43390811407), on `main` at Phase 4 commit `fcec2f2`; its Ubuntu and Windows jobs passed. The local Phase 5 branch `agent-05-01` is absent from `origin`, so this run does not validate the Phase 5 commits. No push was made. Plan status is **halted** at this required CI gate; Phase 5 and Phase 6 are not advanced.

## Decisions Made

- DEC-096 documents the normalized linear basis and intercept-only fallback as **[ASSUMED]** choices to revisit using Phase 6 measurements.
- DEC-097 keeps the LSM continuation target conditional-mean while using exact fractional-boundary CVaR10 only in current-cutoff ranking.
- DEC-098 and DEC-099 record common seeded path branches, legal stop boundaries and deterministic tie order.
- DEC-100 records catalog-backed input validation and the no-look-ahead shared replay builder.
- The Phase 4 fit-prior double-counting question remains unchanged and is scheduled for Phase 6 measurement.

## Deviations from Plan

Strict mypy initially found 19 typing errors in the Phase 5 path-checkpoint and test seams; they were fixed and the full mypy gate passed. The real-data smoke exposed missing punctuation on unavailable reasons; a failing regression test was committed first, then the CLI formatter was fixed and both synthetic and real full-cutoff checks passed.

The only incomplete acceptance item is GitHub Actions on the current branch. The last available Ubuntu/Windows run is for an earlier `main` commit and was not misreported as validation of these changes.

## Verification

- `uv run --python <signed-python.exe> python -m ruff check .` — passed.
- `uv run --python <signed-python.exe> python -m ruff format --check .` — 153 files already formatted.
- `uv run --python <signed-python.exe> python -m mypy` — no issues in 145 source files.
- `uv run --python <signed-python.exe> python -m pytest` — **983 passed, 25 deselected** (519.37 seconds).
- `tests/test_docs.py tests/test_decisions_log.py tests/test_cli_replay.py` — **65 passed** after the final output-format fix.
- Default Bahrain full replay and selected lap-20 replay — both exited 0; 57 cutoffs ordered; lap 20 exact match; 41 available and 16 unavailable.
- Post-fix real-cache replay at `--n 12` — 57 ordered rows, all 57 reason lines punctuated, lap 20 exact match.
- GitHub Actions for the current Phase 5 branch — **pending**. Latest `main` run passed both operating systems but predates this branch.

## User Setup Required

None. The trusted local Python runtime and Bahrain cache are available.

## Next Phase Readiness

Documentation, local automated validation, and the Bahrain smoke are complete. Current-branch GitHub Actions is still required before Phase 5 can be closed and Phase 6 can begin. No remote push was made.

---
*Phase: 05-longstaff-schwartz-strategy-live-replay*
*Plan: 03*
*Stopped: 2026-11-13*
