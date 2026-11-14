---
phase: 06-mvp-backtest-streamlit-view-readme
plan: "04"
subsystem: backtest
tags: [python, duckdb, walk-forward, scoring, multiprocessing, report]
requires:
  - phase: 06
    provides: fixed race set, walk-forward trace, metric primitives, compact strategy summaries
  - phase: 05
    provides: cutoff-safe strategy replay and deterministic per-row analysis
provides:
  - Complete ten-race Phase 6 probability report with shared model/baseline masks and race-cluster uncertainty
  - Bounded ordered parallel prediction batches with serial mode and exact parity tests
  - One shared race/cutoff replay context reused across each cutoff's drivers
affects: [phase-06-plans-05-07, BKT-02, backtest, report]
actuals:
  tokens: 15088
  tasks: 2
  commits: 11
  plan_head_before: fbe79641c6dd460ce12f1164a042611407a285f6
  plan_head_after: cab24eb6574fd17e591a4aee06d726471a12c85d
tech-stack:
  added: []
  patterns: [cutoff-shared replay preparation, bounded process workers with isolated read-only accessors, ordered deterministic trace assembly]
key-files:
  created:
    - reports/backtest/phase-06.json
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-04-03-red.json
    - .planning/phases/06-mvp-backtest-streamlit-view-readme/06-04-04-red.json
  modified:
    - src/f1si/backtest/walk_forward.py
    - src/f1si/backtest/scoring.py
    - src/f1si/cli.py
    - tests/backtest/test_walk_forward.py
    - tests/backtest/test_metrics.py
    - tests/test_cli.py
    - .gitignore
key-decisions:
  - "Preserve all registered rows, per-row seed derivation, 1,000 simulations, risk 0.5, and bootstrap settings while parallelizing independent cutoffs."
  - "Keep serial execution available and assemble process results in locked race/lap/driver order."
  - "Version only the measured Phase 6 report under reports/; keep other generated report files ignored."
patterns-established:
  - "Prepare snapshot, history, pace fit, pit loss, wear state, race state, fallback, and safety-car estimate once per race/cutoff."
  - "Initialize a separate path-backed read-only accessor per process and return compact prediction rows in input order."
requirements-completed: [BKT-02]
coverage:
  - id: D1
    description: "Publish complete ten-race Brier and finish-interval results with denominators and race-cluster uncertainty."
    requirement: BKT-02
    verification:
      - kind: integration
        ref: "uv run f1si backtest --report --workers 4"
        status: pass
      - kind: unit
        ref: "tests/backtest/test_metrics.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Preserve exact prediction summaries between serial and bounded parallel execution."
    verification:
      - kind: integration
        ref: "tests/backtest/test_walk_forward.py#test_serial_and_parallel_full_trace_match_exactly"
        status: pass
      - kind: integration
        ref: "Bahrain 2023 cutoffs 12-15, 80 rows, n=1000: serial/parallel exact equality"
        status: pass
    human_judgment: false
duration: 4h27m
completed: 2026-11-14
status: complete
---

# Phase 06 Plan 04: Freeze-Gated Scoring and Measured Report Summary

**A complete 10-race probability evaluation is published after all 10,942 prediction keys are frozen, with no outcome access during prediction.**

## Performance

- **Duration:** 4h27m from the first RED commit through the completed report
- **Report run:** 1h18m49s using four workers
- **Tasks:** 2 planned tasks, plus approved performance work
- **Files modified:** 9 tracked deliverables and plan evidence files

## Accomplishments

- Added the scoring gate that preflights the exact ten registered races, freezes every eligible driver/cutoff prediction before opening final results, and scores model and past-only baseline on one shared mask.
- Added `f1si backtest --report` with a write-after-success output path and retained the single-cutoff invocation.
- Published [phase-06.json](../../../reports/backtest/phase-06.json) with 10,942 scored rows, 9,602 classified finishers, Brier values, paired race-cluster intervals, 90% finishing-interval coverage, denominators, seeds, resample count, and the carry-forward Bahrain interval miss.
- Reduced repeated cutoff setup by sharing snapshot/history-derived preparation across drivers, then added bounded process execution across independent cutoffs. The CLI defaults to four workers and accepts `--workers 1` for the serial path.

### Measured results

| Metric | Model | Baseline | Model minus baseline, 95% race-cluster interval |
|---|---:|---:|---:|
| Podium Brier | 0.049963 | 0.081737 | -0.031774 [-0.056724, -0.005364] |
| Top-10 Brier | 0.145334 | 0.190904 | -0.045570 [-0.080525, -0.010128] |
| Finish interval coverage | 82.95% (8,004 / 9,602) | — | 95% interval [76.08%, 88.43%] |

The output metadata records base seed 0, 1,000 simulations per prediction, risk 0.5, bootstrap seed 61409, 2,000 race-cluster resamples, and the inclusive inverted-CDF P05/P95 convention. The carry-forward ALO P3 miss is reported without tuning the endpoints.

## Task Commits

1. **Task 1 RED: frozen scoring contract** — `3410354`
2. **Task 1 GREEN: score frozen ten-race trace** — `070c975`
3. **Task 2 RED: report CLI contract** — `89fd4cf`
4. **Task 2 GREEN: fixed-sample report CLI** — `a4658aa`
5. **Task 2 fix: handle absent schedule metadata** — `8d2a90b`
6. **Optimization RED: one replay context per cutoff** — `e9f562e`
7. **Optimization GREEN: share replay preparation** — `67efab4`
8. **Parallel RED: bounded worker and exact trace contract** — `ffaf139`
9. **Parallel GREEN: ordered cutoff process batches** — `27b664b`
10. **Measured report artifact and narrow ignore exception** — `3a792de`
11. **Keep other generated reports ignored** — `cab24eb`

**Plan metadata commit:** recorded after the summary self-check.

## Verification

- `uv run python -m pytest tests/backtest/test_metrics.py tests/backtest/test_walk_forward.py tests/test_cli.py -x -q` — **48 passed**.
- `uv run ruff check ...` — passed for all changed Python files.
- `uv run ruff format --check ...` — passed for all changed Python files.
- TDD RED evidence for replay sharing and worker controls both returned `RED_EVIDENCE_OK` and failed on their intended behavior assertions.
- The full report command exited 0. Metadata checks confirmed all ten locked race IDs, 10,942 scored rows, 1,000 simulations, risk 0.5, base seed 0, bootstrap seed 61409, 2,000 resamples, 9,602 classified finishers, and 8,004 covered intervals.
- Serial/shared replay parity passed on the deterministic 57-lap synthetic fixture at identical seeds.
- Serial and two-worker full traces matched exactly for all 80 keys in a deterministic ten-race fixture.
- Representative Bahrain cutoffs 12–15 at 1,000 simulations: serial **170.036s**, four workers **83.739s** (**2.03× speedup**), exact prediction-row equality. Worker RSS was approximately 240–290 MB per process during measurements.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 - Blocking issue] Resolve missing scheduled distance from observed race-end laps**
- **Found during:** Task 2 report execution
- **Issue:** Some cached OpenF1 races omit scheduled lap count, preventing the registered report from determining its eligible cutoff horizon.
- **Fix:** Use the maximum observed race-end lap only as the finite evaluation horizon; each prediction still uses its cutoff-local snapshot and prior-only history.
- **Files modified:** `src/f1si/backtest/walk_forward.py`, `src/f1si/backtest/scoring.py`
- **Commit:** `8d2a90b`

**2. [Approved performance work] Share cutoff preparation and add bounded parallel execution**
- **Found during:** Full-report runtime profiling
- **Issue:** The original walk-forward path repeated the same snapshot/history, fit, pit, wear, state, fallback, and safety-car preparation for each driver at a cutoff; the 10,942-row default report was too slow to finish promptly.
- **Fix:** Build this data once per cutoff, preserve a serial path, and parallelize independent race/cutoff batches with four isolated read-only accessor processes. Every driver still receives one analysis with unchanged seed, risk, and simulation count.
- **Verification:** Exact serial/parallel prediction parity; representative n=1000 benchmark improved from 170.036s to 83.739s.
- **Files modified:** `src/f1si/backtest/walk_forward.py`, `src/f1si/backtest/scoring.py`, `src/f1si/cli.py`, associated tests.
- **Commits:** `e9f562e`, `67efab4`, `ffaf139`, `27b664b`

**3. [Plan output] Track the completed evaluation report while retaining generated-output ignores**
- **Issue:** `/reports/` ignored the required report artifact.
- **Fix:** Add a narrow `.gitignore` exception for `reports/backtest/phase-06.json`; other generated plots remain ignored.
- **Commits:** `3a792de`, `cab24eb`

## TDD Gate Compliance

- RED evidence: `06-04-03-red.json` and `06-04-04-red.json` each passed `gsd-tools query check tdd-red-evidence` with `RED_EVIDENCE_OK` before their GREEN commits.
- Original scorer and report CLI RED/GREEN commit pairs are preserved in order (`3410354` → `070c975`, `89fd4cf` → `a4658aa`).
- The complete focused verification passed after the final code changes.

## Issues Encountered

- The first full serial report attempt was interrupted before producing an artifact. It was not reused or treated as complete. The bounded four-worker run subsequently completed and published the report only after scoring succeeded.
- No authentication gates or user setup are required.

## Known Stubs

None. No skipped tests or unrun plan verifications remain.

## Threat Flags

None. Parallel workers use the existing read-only AsOfAccessor boundary; the results accessor remains in the scoring layer and is constructed only after complete trace validation.

## Next Phase Readiness

Plan 06-05 can consume the frozen report and its race/cutoff prediction contract. The report excludes 2026 and records the locked ten-race sample and uncertainty method.

## Self-Check: PASSED

- Summary and report artifact exist at their required paths.
- All 11 measured plan commits are ancestors of the current HEAD.
- Report metadata and denominators match the published JSON.

---
*Phase: 06-mvp-backtest-streamlit-view-readme*
*Completed: 2026-11-14*
