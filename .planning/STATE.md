---
gsd_state_version: "1.0"
milestone: v1.0
current_phase: 06
current_phase_name: MVP Backtest, Streamlit View & README
current_plan: 4
status: executing
stopped_at: Completed 06-02-PLAN.md
last_updated: "2026-11-14T03:56:29Z"
last_activity: 2026-11-14
last_activity_desc: Phase 06 metric primitives completed; Plan 06-03 is next
state_head: 22eb48e2e7ae094cea9414f1ced54c887b580484
progress:
  total_phases: 8
  completed_phases: 4
  total_plans: 40
  completed_plans: 35
milestone_name: milestone
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-22)

**Core value:** For any driver at any lap of a replayed race, a pit-strategy recommendation whose uncertainty is honest: calibrated, free of look-ahead, verified against synthetic ground truth.
**Current focus:** Phase 06 — MVP Backtest, Streamlit View & README

## Current Position

Phase: 06 (MVP Backtest, Streamlit View & README) — EXECUTING
Current Plan: 4
Total Plans in Phase: 8
Plan: 4 of 8
Status: Ready to execute
Last activity: 2026-11-14 — Phase 06 metric primitives completed; Plan 06-03 is next

Progress: [====------] 38%

## Performance Metrics

**Velocity:**

- Total plans completed: 17
- Average duration: -
- Total execution time: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 02 | 5 | - | - |
| Phase 03 P01 | 1h | 3 tasks | 13 files |
| Phase 03 P02 | 1h | 2 tasks | 14 files |
| Phase 03 P03 | ~30m | 2 tasks | 11 files |
| Phase 03 P04 | 40min | 3 tasks | 16 files |
| Phase 03 P06 | 40min | 2 tasks | 7 files |
| Phase 03 P07 | 40min | 2 tasks | 4 files |
| 3 | 7 | - | - |
| Phase 04 P01 | 1h | 3 tasks | 12 files |
| 4 | 5 | - | - |
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 05 P01 | 9min | 2 tasks | 7 files |
| Phase 05 P02 | 25min | 2 tasks | 14 files |
| Phase 05 P04 | 86min | 3 tasks | 14 files |
| Phase 06 P00 | 6min | 2 tasks | 5 files |
| Phase 06 P01 | 27m | 2 tasks | 5 files |

## Accumulated Context

| Phase 01 P01 | multi-session | 3 tasks | 15 files |
| Phase 01 P02 | 40min | 3 tasks | 19 files |
| Phase 01 P03 | 2 sessions | 3 tasks | 11 files |
| Phase 1 P04 | 45min | 2 tasks | 22 files |
| Phase 01 P05 | 35min | 2 tasks | 8 files |
| Phase 01 P06 | 40min | 2 tasks | 6 files |
| Phase 01 P07 | 60min | 2 tasks | 12 files |
| Phase 01 P08 | 45min | 2 tasks | 6 files |
| Phase 01 P09 | 40 min | 2 tasks | 9 files |
| Phase 01 P10 | 35min | 2 tasks | 3 files |
| Phase 01 P11 | 50min | 2 tasks | 5 files |
| Phase 02 P01 | 35min | 3 tasks | 14 files |
| Phase 02 P02 | 35min | 3 tasks | 16 files |
| Phase 02 P03 | 40min | 3 tasks | 11 files |
| Phase 02 P04 | ~1h | 3 tasks | 10 files |
| Phase 02 P05 | 25min | 2 tasks | 4 files |

### Decisions

- Vertical MVP structure: phases 1-6 are the lean MVP, 7-8 are upgrades
- Go/no-go check after Phase 6 (simulated finishing distributions roughly match real results across 10 races)
- PyMC vs NumPyro still open (PyMC is the stated stack)
- [Phase 01-01]: pandas <3 (DEC-012), duckdb <2 (DEC-011), ruff pinned ==0.17.1 matching pre-commit v0.17.1 (D-13) — Keep FastF1 option open; avoid DuckDB 2.0 file incompatibility; hook and dev versions must agree
- [Phase 01-01]: Dependency names verified against PyPI JSON for all 14 packages — slopcheck unavailable; legitimacy gate before first install
- [Phase 01-02]: write_race strict (all per-race tables required); lock errors mapped to CacheBusyError by message text; ruff excludes .planning and F1 Docs; .gitignore data dirs anchored to repo root — Completion marker integrity; Windows/Linux lock wording; ruff 0.17 formats markdown; src/f1si/data must be tracked
- [Phase 01-03]: CLI constructs the source; load_races receives it (deviation from RESEARCH map, per SKELETON) — Keeps loader source-agnostic
- [Phase 1]: Plan 04: lap_cutoffs precomputed with reverse cumulative minimum; loader collects per-race failures (exit 2), retries rate limits via injected sleep, refuses mixed sources
- [Phase 01-05]: AST import scan with one POLICY table chosen over import-linter (DEC-002); CLI composes the data source (DEC-015); DECISIONS.md holds DEC-001..DEC-035 — see DECISIONS.md
- [Phase 01-08]: pit_lane_start = Jolpica grid 0 and not a never-started status; laps completed never used (DEC-049)
- [Phase 01]: Stint plot conventions: faded not removed, y-range from clean laps, grid-order panels, no pyplot (DEC-050) — Keeps the true race visible while the wear trend stands out
- [Phase 01-11]: DEC-051 plain-language explainer per phase kept complete by tests/test_docs.py (D-17)
- [Phase 02]: DEC-061: Protocol signatures; RaceState imported under TYPE_CHECKING only
- [Phase 02]: DEC-062: RaceState None-not-NaN JSON; regime and pit_loss_s are placeholders
- [Phase 02]: DEC-063..066: joint OLS fuel/wear fit refuses unidentified parameters; shared clean laps; no compound offset; pit loss from in/out laps
- [Phase 02]: DEC-068 free-track plan rules; DEC-069 plan cutoff policy and analytic ground truth
- [Phase 03]: DEC-074/075: scipy+numba locked; SC rate Beta(3,297) on earlier races, edge-rule deployments, median duration (fallback 4)
- [Phase 03]: DEC-076/077: SC regime at cutoff, shared per-compound wear draw, SimulationResult diagnostics
- [Phase 03]: DEC-078..080: logistic passing with dirty-air hold, SC mechanics, Sobol+antithetic CRN draws
- [Phase 03]: DEC-081/082: forced plans exact, fallback for refused cars, leader-relative start with catch-up lap and borrowed pace — see DECISIONS.md
- [Phase 03]: DEC-083/084: Sobol+antithetic variance ratios 4.5/16.4/3.2; 50k benchmark 1.4 s
- [Phase 03]: DEC-085: simulate command - hindsight rule, bounds, warm-up excluded, limitations printed
- [Phase ?]: [Phase 04-01]: DEC-088..090 three-state wear filter with fuel nuisance state; q=0 default; gate 3.0 SD from the 3rd used lap, never twice in a row
- [Phase 05]: D-01/D-02/D-08: use conditional-mean LSM recursion and the locked current-cutoff mean/CVaR10 score, default risk 0.5.
- [Phase 05]: Use a normalized cutoff-visible basis with intercept-only conditional-mean fallback when data are undersized or rank-deficient.
- [Phase 05]: Keep reasons score-only without supporting visible evidence; enforce the existing five-lap minimum final stint.
- [Phase 05]: Full and selected replay share a cutoff builder and format unavailable results when cutoff-visible pace fit is unsupported.
- [Phase 05]: Replay consumers use the CLI cutoff builder and future-scramble tests preserve D-21 public max-lap metadata while scrambling observations.
- [Phase 05]: DEC-101: cutoff-visible sparse pace fallback uses existing generic priors and an [ASSUMED] 1.0 s driver-offset SD; results remain uncalibrated.
- [Phase 05]: If an identified partial fit has no legal second compound, rank stay out as the sole legal action.
- [Phase 06]: Pre-register the calendar-first 4/3/3 ten-race sample before scoring.
- [Phase 06]: Build each prediction from its cutoff snapshot and strictly earlier history.
- [Phase 06]: Keep result access and scoring outside the prediction runner.

### Pending Todos

- GitHub Actions must run on the current Phase 5 commits on both Ubuntu and Windows before phase closeout. The local branch agent-05-01 is not on origin.

### Blockers/Concerns

- Phase 5 current-branch CI is pending; the latest available main run is for Phase 4 commit fcec2f2, not these commits.
- Keep 2026 races out-of-sample because of the regulation break.
- Fuel load and tire wear are hidden variables; state this in README.
- The prior Windows Application Control OS error 4551 is resolved with verified PSF-signed CPython 3.12.10 at %LOCALAPPDATA%/Programs/Python/Python312/python.exe.

## Session Continuity

Last session: 2026-11-14T03:56:29Z
Stopped at: Completed 06-02-PLAN.md
Resume file: None
