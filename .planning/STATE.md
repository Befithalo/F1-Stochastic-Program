---
gsd_state_version: "1.0"
milestone: v1.0
status: Awaiting next milestone
stopped_at: M1 v1.0 closed; M2 Physics planning is next
last_updated: "2026-11-17T20:33:16.275Z"
last_activity: 2026-11-17
last_activity_desc: Milestone v1.0 completed and archived
state_head: 9e2fd7575b29ceb1f1a2b6a8ce8aecd4f1fd919d
progress:
  total_phases: 8
  completed_phases: 8
  total_plans: 55
  completed_plans: 55
milestone_name: milestone
closeout_type: override_closeout
current_phase: 8
current_phase_name: Markov Regimes & Full Backtest (M1 archived)
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-17)

**Core value:** For any driver at any lap of a replayed race, a pit-strategy recommendation whose uncertainty is honest: calibrated, free of look-ahead, verified against synthetic ground truth.
**Current focus:** M2 Physics — requirements and roadmap

## Current Position

Phase: M1 v1.0 archived; preparing M2
Plan: —
Status: Awaiting next milestone
Last activity: 2026-11-17 — Milestone v1.0 completed and archived

## Performance Metrics

**Velocity:**

- Total plans completed: 22
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
| 7 | 5 | - | - |
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 05 P01 | 9min | 2 tasks | 7 files |
| Phase 05 P02 | 25min | 2 tasks | 14 files |
| Phase 05 P04 | 86min | 3 tasks | 14 files |
| Phase 06 P00 | 6min | 2 tasks | 5 files |
| Phase 06 P01 | 27m | 2 tasks | 5 files |
| Phase 06 P03 | 12min | 1 tasks | 2 files |
| Phase 06 P04 | 4h27m | 2 tasks | 16 files |
| Phase 06 P05 | 1h15m | 2 tasks | 12 files |
| Phase 06 P06 | 12min | 2 tasks | 8 files |
| Phase 06 P07 | 7min | 2 tasks | 5 files |
| Phase 06 P09 | 13min | 2 tasks | 5 files |
| Phase 06 P08 | 42m | 3 tasks | 9 files |
| Phase 08 P01 | 27min | 2 tasks | 8 files |
| Phase 08 P02 | 49m | 2 tasks | 6 files |
| Phase 08 P03 | 4h42m | 3 tasks | 21 files |
| Phase 08 P04 | 15min | 2 tasks | 9 files |

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
- [Phase 06]: Ranked options retain podium/top-10 probabilities and inclusive inverted-CDF endpoints from their own finish draws; raw draws remain local to analysis.
- [Phase 06]: Preserve all registered rows, per-row seed derivation, 1,000 simulations, risk 0.5, and bootstrap settings while parallelizing independent cutoffs.
- [Phase 06]: Keep serial execution available and assemble process results in locked race/lap/driver order.
- [Phase 06]: Version only the measured Phase 6 report under reports/; keep other generated report files ignored.
- [Phase 06]: Match each stop to the newest recommendation strictly before its in-lap whose snapshot has not yet exposed the event.
- [Phase 06]: Compare cutoff wear estimates to the existing pace fit after removing the evaluated driver stint; report unavailable proxies explicitly.
- [Phase 06]: The Streamlit page uses the shared cutoff replay builder and a cache keyed by selected inputs, local cache metadata, and model-source identity.
- [Phase 06]: Keep published Phase 6 metrics tied to the fixed report, preserving samples, denominators, and interval conventions.
- [Phase 06]: Describe observed team calls comparatively and wear estimates as retrospective proxy evidence, not proof of superiority or latent ground truth.
- [Phase 06]: D-11's graphite dashboard was rejected after the owner inspected it; D-12 through D-15 supersede its visual choices with a light, editorial, replay-first page and an ex-ante schedule-horizon requirement. Preserve D-07/D-08 data semantics and the one-page scope.
- [Phase 06]: Reserve purple for the recommended strategy; label any overall-best lap Best in neutral fog.
- [Phase 06]: Retain compact same-sample finish quantiles and opt-in selected-driver history; reduce simulation history to percentile bands before UI rendering.
- [Phase 08]: Use green, vsc, sc, red, wet order and Dirichlet(1) smoothing for race-local one-lap transitions.
- [Phase 08]: Keep green pit loss measured; treat VSC at 0.75x and SC at 0.5x as assumptions, with red and wet at green cost.
- [Phase 08]: Require a one-hot cutoff regime when a Markov transition matrix is supplied; legacy states without a matrix retain the existing SC path.
- [Phase 08]: DEC-121: cutoff-visible regimes use explicit control and rainfall precedence
- [Phase 08]: DEC-122: race-local one-lap transitions use Dirichlet(1) smoothing
- [Phase 08]: DEC-123: green pit loss is measured; SC and VSC discounts are assumptions
- [Phase 08]: DEC-124/D-04: Freeze the ordered 20-race 2023–2025 sample and locked linear-pace scoring settings before prediction.
- [Phase 08]: Continuation regression uses two-fold cross-fitting; each scoring fold is excluded from the paths used to fit its regression.
- [Phase 08]: D-05 holdout stays separate; no 2026 outcomes were accessed in Plan 08-03.
- [Phase 08]: Lock the 2026-09 through 2026-17 holdout with linear pace, 1,000 simulations, seed 0, risk 0.5, and CRC32 race/driver/cutoff seeds.
- [Phase 08]: Build Markov transition inputs only from complete 2023-2025 RACE_END feature snapshots; never use a 2026 sequence for fit.
- [Phase 08]: Freeze all holdout predictions before requesting final classifications; verify-existing reads only lock and report.

### Pending Todos

- Commit and merge the M1 archive, tag v1.0, then run Ubuntu and Windows CI on the final merge commit.

### Blockers/Concerns

- PAC-06 remains unmet: the locked Bayesian pace MAE was 0.538745 s versus 0.364033 s for linear pace. M2 must compare a hybrid model to the data-only Bayesian model on a separately locked held-out-stint set; do not retune or rescore the M1 evaluation.
- Seven UAT, verification, and deferred items were acknowledged in the v1.0 override closeout and are preserved in the Deferred Items table and milestone archive. Phases 1, 5, and 8 still carry human judgment or UAT items.
- The separate 2026 holdout report exists and was scored after its predictions were frozen; it is pre-registered but retrospectively unblinded. Keep it out of the M1 baseline and do not tune on it.
- Fuel load, tire temperature, and tire wear remain hidden or latent variables; disclose assumptions and uncertainty.

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| quick_tasks | 261116-0hq-ui-design-pass-on-the-streamlit-replay-p | completed artifact archived in v1.0 | 2026-11-17 | v1.0 |
| uat_gaps | 01/01-HUMAN-UAT.md | partial; 2 scenarios | 2026-11-17 | v1.0 |
| verification_gaps | 01/01-VERIFICATION.md | human_needed | 2026-11-17 | v1.0 |
| verification_gaps | 05/05-VERIFICATION.md | human_needed | 2026-11-17 | v1.0 |
| verification_gaps | 08/08-VERIFICATION.md | human_needed | 2026-11-17 | v1.0 |
| deferred_items | 05/deferred-items.md: docs verification sequencing note | acknowledged | 2026-11-17 | v1.0 |
| deferred_items | 06/deferred-items.md: pre-existing RNG factory import-ban findings in scoring.py | acknowledged | 2026-11-17 | v1.0 |

## Session Continuity

Last session: 2026-11-17T08:58:39.889Z
Stopped at: M1 v1.0 archived; finish merge and final CI before M2 execution
Resume file: .planning/milestones/v1.0-phases/08-markov-regimes-full-backtest/08-VERIFICATION.md

## Operator Next Steps

- Finish M1 release merge, push, and final Ubuntu/Windows CI.
- Start M2 Physics with GSD after the M1 merge.
