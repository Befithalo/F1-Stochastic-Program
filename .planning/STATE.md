---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 03-05-PLAN.md
last_updated: "2026-11-12T18:25:02.385Z"
last_activity: 2026-11-12
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 23
  completed_plans: 21
  percent: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-22)

**Core value:** For any driver at any lap of a replayed race, a pit-strategy recommendation whose uncertainty is honest: calibrated, free of look-ahead, verified against synthetic ground truth.
**Current focus:** Phase 3 — monte-carlo-simulator

## Current Position

Phase: 3 (monte-carlo-simulator) — EXECUTING
Plan: 6 of 7
Status: Ready to execute
Last activity: 2026-11-12

Progress: [█████████░] 91%

## Performance Metrics

**Velocity:**

- Total plans completed: 5
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

### Pending Todos

None yet.

### Blockers/Concerns

- 2026 regulation break: keep 2026 races out-of-sample
- Fuel load and tire wear are hidden variables; state this in README

## Session Continuity

Last session: 2026-11-12T18:25:02.377Z
Stopped at: Completed 03-05-PLAN.md
Resume file: None
