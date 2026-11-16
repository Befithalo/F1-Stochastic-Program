---
phase: 06-mvp-backtest-streamlit-view-readme
verified: 2026-11-16T00:00:00Z
status: passed
score: 7/7 must-haves verified (5 roadmap success criteria + 2 carried-forward checks)
overrides_applied: 0
decision_coverage:
  honored: 11
  total: 11
  not_honored: []
human_verification:
  - test: "Confirm the exact-head CI run for 2759d60 (Ubuntu and Windows ci.yml) is green"
    expected: "Both jobs pass; the 10 locally environment-blocked tests (test_import_order x5, plot import-without-pyplot x4, db lock-held x1) pass on CI"
    why_human: "gh CLI is not installed in this shell; CI for 2759d60 was still running at verification time (0b428bd passed per orchestrator)"
  - test: "Decide whether sparse-fallback (prior-driven, uncalibrated) recommendations need an explicit label on the Streamlit page"
    expected: "Owner either accepts the V2 thin-tyre-data note as sufficient disclosure, or asks for an 'uncalibrated' / 'rough estimate' marker on the decision band when result['fallback'] is true"
    why_human: "Design judgment. The default view (Bahrain 2023, ALO, after lap 15) is a sparse-fallback call (CLI prints '... [ASSUMED] 1.0 s pace-offset SD, uncalibrated'), but the page shows only 'There are only a few laps on this set, so the tyre wear figure is a rough estimate.' (src/f1si/app.py:1083-1084). V2 decision 12 replaced the 06-UI-SPEC 'Uncalibrated' label; whether that covers the pace-fit fallback is the owner's call"
  - test: "Owner acceptance of the redesigned page at desktop and phone widths (Plan 06-10 Task 06-10-02)"
    expected: "Recorded in 06-10-SUMMARY.md by the orchestrator"
    why_human: "Blocking owner checkpoint; the orchestrator records the 2026-11-16 approval. Not a verification gap"
---

# Phase 6: MVP Backtest, Streamlit View & README Verification Report

**Phase Goal:** As a strategist, I want to see ten-race prediction and strategy results in one page, so that I can decide to proceed.
**Mode:** mvp
**Verified:** 2026-11-16
**Status:** passed (human items resolved 2026-11-16; see Resolution)
**Re-verification:** No (initial verification)

## User Flow Coverage

User story: "As a strategist, I want to see ten-race prediction and strategy results in one page, so that I can decide to proceed."

| Step | Expected | Evidence | Status |
|------|----------|----------|--------|
| 1. Produce the ten-race results | `f1si backtest --report` freezes every driver/cutoff prediction for the 10 registered races, then scores them | `src/f1si/cli.py:260-285` (parser), `cli.py:1299-1343` (dispatch to `score_registered_sample`); `src/f1si/backtest/walk_forward.py:18-29,264-306`; `src/f1si/backtest/scoring.py:691-760`. Spot-check: `py -m f1si backtest --race 2023-01 --driver ALO --lap 15` printed `2023-01 ALO lap 15: wait and decide next lap` plus the sparse-fallback reason | ✓ |
| 2. Open one page | `streamlit run src/f1si/app.py` lists in-sample 2023-2025 races with a verified lap count, defaulting to Bahrain 2023 / ALO / after lap 15 / risk 0.5 | `app.py:224-256` (`_eligible_catalog`), `app.py:1674-1742` (controls), `app.py:1745-1785` (`main`); test `tests/app/test_app.py::test_page_defaults_to_bahrain_2023_alo_after_lap_15` | ✓ |
| 3. See the strategy call for a driver and lap | Decision band (headline, lede, facts, finish histogram, race strip with safety-car line and tyre line), options rows plus "Show all numbers" table, fan chart | `app.py:987-1116`, `app.py:1221-1275`, `app.py:1336-1393`, `app.py:1396-1407`; tests `test_rendered_selected_replay_shows_band_options_and_three_charts`, `test_fan_chart_uses_recommended_pathwise_policy_history`; network `tests/real/test_bahrain_2023.py` (16 passed incl. lap-15 mid-pit case) | ✓ |
| 4. See the ten-race prediction and strategy results on the same page | "How good is this model?" shows podium and points Brier against the grid, 9-in-10 coverage against its target, team-call agreement and stop-timing error from `reports/backtest/phase-06.json` | `app.py:55` (`REPORT_PATH`), `app.py:1513-1596` (`_model_report_html`), `app.py:1665-1666`, rendered in `main` at `app.py:1779-1780`; test `test_evaluation_uses_five_explained_metrics` | ✓ |
| 5. Decide to proceed | Owner judges the evidence | Owner reviewed the running page 2026-11-16; orchestrator records it in 06-10-SUMMARY.md | ? (orchestrator item) |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User runs the walk-forward backtest on 10 races from 2023-2025 and the look-ahead test still passes | ✓ VERIFIED | `REGISTERED_RACE_IDS` = 4/3/3 races (`walk_forward.py:18-29`); `run_walk_forward` loops every scheduled cutoff and every driver through `cli._replay_at_cutoff` with no results import (`walk_forward.py:264-306`); results are opened only after the trace is validated and frozen (`scoring.py:700-716`). Look-ahead: `walk_forward_cutoff` and `strategy_replay` are registered in `tests/guards/consumers.py:166-182` and exercised on the full synthetic grid (`tests/guards/test_future_scramble.py:259-271`); the scramble harness fails consumers that raise (`tests/guards/scramble.py:23-25`), and the synthetic race IDs 2023-01/2023-02/2024-01 are registered IDs, so the check is not vacuous. Import policy: `f1si.data.results` only reachable from `f1si.backtest.scoring` (`tests/guards/import_scan.py:117-121`). `tests/guards` all passed in this run. Live CLI single-cutoff spot-check passed. |
| 2 | Report shows Brier score for podium and top-10 next to a grid-position baseline, plus 90% finishing-interval coverage | ✓ VERIFIED | `reports/backtest/phase-06.json` metrics: podium model 0.0476 vs baseline 0.0804, diff -0.0328 [-0.0566, -0.0075]; top-10 0.1446 vs 0.1899, diff -0.0453 [-0.0839, -0.0072]; coverage 0.832 [0.761, 0.889], 7,650 of 9,146 classified. Code: `metrics.py:21-69` (paired Brier), `metrics.py:72-99` (past-only grid baseline, 5 pseudo-starts), `metrics.py:102-131` (inclusive inverted-CDF P05/P95). README table `README.md:28-33`. `tests/test_docs.py::test_phase6_published_results_match_completed_report_and_disclosures` asserts every published number equals the JSON. |
| 3 | Report compares platform strategy calls with actual team calls, with confidence intervals | ✓ VERIFIED | `phase-06.json` `team_strategy_comparison`: 388/388 stops matched, agreement 0.175 [0.067, 0.308], signed timing +1.96 [-0.10, 3.24] laps, absolute 3.66 [2.97, 4.65], race-cluster bootstrap 2,000 resamples. Code: `backtest/strategy.py:9-146` (latest recommendation strictly before in-lap; race-resampled intervals); tests `tests/backtest/test_strategy.py` (7 tests). README `README.md:35` ("No superiority claim is made"). |
| 4 | User opens one Streamlit page showing strategy table, finishing fan chart, regime gauge, tire panel, reason line and risk dial for a driver and lap | ✓ VERIFIED (current V2 forms) | Mapping per `docs/design/DESIGN_SYSTEM_V2.md` section 10 and DEC-114/115: **strategy table** = options rows (`app.py:1245-1275`) + "Show all numbers" table with expected/bad-day finish, podium, points, 9-in-10 range for every option (`app.py:1221-1242`); **finishing fan chart** = `build_fan_chart` on the recommended policy's pathwise position history (`app.py:427-436,1383-1393`); **regime gauge** = safety-car line "Safety car: X% per lap, about N in M races before the flag" in race-strip footer and strip sentence (`app.py:1064-1070,1080,1114`), fed by `context.estimate.rate_per_lap` (`app.py:389`). Phase 6 has a single constant SC regime, and the Markov multi-regime model is Phase 8, so a text line covers what exists. **Tire panel** = tyre line "losing about X s a lap, give or take Y s" (`app.py:956-964`) + race strip stints/plan + stint chart (`app.py:1361-1381`); **reason line** = lede (`app.py:1004-1020`) from `_strategist_reason` (`app.py:288-327`); **risk dial** = 0-1 slider with Aggressive/Balanced/Cautious labels (`app.py:1722-1736`) passed into the replay (`app.py:1762-1769`). Driver and lap selectors at `app.py:1707-1721`. 33 tests in `tests/app` + chart tests passed. |
| 5 | README lists measured results only, states hidden-variable assumptions, and credits FastF1/OpenF1 with licensing notes | ✓ VERIFIED (with warning) | Measured-only: every Phase 6 number in `README.md:24-37` equals `phase-06.json` (docs test); line 7 disclaims calibration and superiority. Hidden variables: `README.md:39` ("Fuel load and tire wear are hidden variables ... linear wear ... no retirement model"). Credits: `README.md:65` (OpenF1 personal/non-commercial; Jolpica; FastF1 MIT; not affiliated; raw data not republished). **Warning W-1:** the FastF1 sentence is now inaccurate (see Gaps Summary). |
| 6 | Carry-forward (Phase 3): check 90% finishing-interval coverage | ✓ VERIFIED | Measured 0.832 with 95% race-cluster interval [0.761, 0.889], which excludes 0.90, so the intervals under-cover. Disclosed in README:33 and on the page as "Slightly overconfident" (`app.py:1475-1481`). The ALO reference miss is recorded in `carry_forward_diagnostic` with `tunes_interval_endpoints: false` (`scoring.py:717-727`). |
| 7 | Carry-forward (Phase 4): measure real-data Kalman wear-band coverage before changing the method | ✓ VERIFIED | `wear_band_retrospective_proxy`: 6,382/7,659 = 0.833 for the 1.96-SD band, early-fit bias -0.0072 s/lap (eight or fewer clean laps), own-lap share 0.055 over 5,939; `kalman_parameters_changed: false`, `tuned_on_evaluation_races: false`; 2023-03 and 2025-01 reported unavailable. Code `backtest/wear_diagnostic.py`; README:37. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/f1si/backtest/walk_forward.py` | Fixed-sample cutoff-local predictions | ✓ VERIFIED | 306 lines; serial and 4-worker paths; preflight; 2026 rejected |
| `src/f1si/backtest/scoring.py` | Freeze-then-score report assembly | ✓ VERIFIED | 760 lines; frozen-trace validation before results accessor |
| `src/f1si/backtest/metrics.py` | Brier, grid baseline, interval, cluster bootstrap | ✓ VERIFIED | 173 lines; wired from scoring |
| `src/f1si/backtest/strategy.py` | Team-call matching and intervals | ✓ VERIFIED | 146 lines; wired from scoring |
| `src/f1si/backtest/wear_diagnostic.py` | Retrospective wear-band proxy | ✓ VERIFIED | 199 lines; wired from scoring |
| `reports/backtest/phase-06.json` | Completed measured report | ✓ VERIFIED | Tracked; regenerated in f7b7fba together with the DEC-112/113 code; no backtest-affecting source changed after f7b7fba (0b428bd touched only app/plots/theme, 2759d60 only a test) |
| `src/f1si/app.py` | One-page Streamlit view | ✓ VERIFIED | 1,789 lines; replay via `cli._replay_at_cutoff` and `cli._make_asof_accessor`; no results-door import |
| `README.md` | Measured results, assumptions, credits | ⚠️ VERIFIED with warning | See W-1, W-3 |
| `docs/explained/phase-06.md`, `DECISIONS.md` (DEC-102..115) | Explainer and decision log | ✓ VERIFIED | `test_docs.py` and `test_decisions_log.py` pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli backtest --report` | `score_registered_sample` | `cli.py:1329-1337` | ✓ WIRED | Writes JSON at `cli.py:1338-1343` |
| `run_walk_forward` | strategy replay | `cli._replay_at_cutoff` (`walk_forward.py:186-196`) | ✓ WIRED | Same builder the CLI `replay` and the app use |
| `scoring` | results door | `_new_results_accessor` after `_validate_frozen_trace` | ✓ WIRED | `scoring.py:710-716` |
| `app.py` | replay | `_build_selected_replay` → `cli._replay_at_cutoff` | ✓ WIRED | `app.py:396-407` |
| `app.py` | measured report | `REPORT_PATH` → `_report_summary` → `_model_report_html` | ✓ WIRED | `app.py:55,1665,1779` |
| risk slider | ranking | `risk` → `_build_selected_replay(..., risk, ...)` | ✓ WIRED | `app.py:1762-1769` |
| SC estimate | safety-car line | `context.estimate.rate_per_lap` → `safety_line` | ✓ WIRED | `app.py:389,1064-1070` |
| walk-forward | look-ahead guard | `CONSUMERS["walk_forward_cutoff"]` | ✓ WIRED | `tests/guards/consumers.py:181` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Decision band and options | `result["options"]`, `option_quantiles` | `cutoff.analysis.options` from `_replay_at_cutoff` | Yes (network test on cached Bahrain 2023) | ✓ FLOWING |
| Fan chart | `fan_chart_data` | `analysis.recommended_position_history` → `prepare_fan_chart_data` | Yes | ✓ FLOWING |
| Safety-car line | `safety_car_probability` | `context.estimate.rate_per_lap` (as-of SC estimate) | Yes | ✓ FLOWING |
| Tyre line | `tire_rate`, `tire_sd` | `car.wear_rate_s_per_lap`, `car.wear_sd` from the as-of state | Yes (None handled with "too new to measure") | ✓ FLOWING |
| Model report | `report["metrics"]` | `reports/backtest/phase-06.json` | Yes (measured) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Targeted phase suites | `py -m pytest tests/backtest tests/app tests/plots/test_altair_charts.py tests/plots/test_replay_charts.py tests/test_docs.py tests/test_decisions_log.py tests/guards -q` | 361 passed in 203 s | ✓ PASS |
| Real-data Bahrain tests | `py -m pytest -m network tests/real/test_bahrain_2023.py -q` | 16 passed in 26 s | ✓ PASS |
| Backtest CLI single cutoff | `py -m f1si backtest --race 2023-01 --driver ALO --lap 15` | `wait and decide next lap` + sparse-fallback reason | ✓ PASS |
| Lint, format | `py -m ruff check src tests`; `ruff format --check` | All checks passed; 165 files formatted | ✓ PASS |
| Types | `py -m mypy` | no issues in 165 source files | ✓ PASS |
| Full 10-race regeneration | `f1si backtest --report` | Not rerun (long, full cache); report provenance checked via commit f7b7fba | ? SKIP |
| CI exact head 2759d60 | GitHub Actions | gh not available; orchestrator reports 0b428bd green, 2759d60 running | ? HUMAN |

### Probe Execution

No `scripts/*/tests/probe-*.sh` declared or present for this phase. Step skipped.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BKT-01 | 06-01, 06-04 | Walk-forward backtester on 2023-2025 with zero look-ahead | ✓ SATISFIED | Truth 1 |
| BKT-02 | 06-02, 06-04 | Brier (podium, top-10) vs grid baseline + 90% coverage | ✓ SATISFIED | Truth 2 |
| BKT-04 | 06-05 | Strategy calls vs team calls with CIs | ✓ SATISFIED | Truth 3 |
| UI-01 | 06-06, 06-08, 06-09, 06-11 | One-page Streamlit view with the six elements | ✓ SATISFIED | Truth 4 (V2 forms) |
| UI-02 | 06-07 | README measured results, hidden-variable assumptions, licensing/credits | ✓ SATISFIED (W-1) | Truth 5 |

No orphaned requirements: REQUIREMENTS.md maps exactly BKT-01, BKT-02, BKT-04, UI-01, UI-02 to Phase 6; BKT-03 and BKT-05 are Phase 8.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/f1si/state.py` | 40, 41, 91, 223, 505 | "placeholder" (SC pit-loss ratio until Phase 8, REG-03) | ℹ️ Info | Pre-existing, documented, tied to Phase 8 requirement |
| `README.md` | 16, 58 | `reportswear-filter-bahrain-2023-ALO.png` (missing `\`) | ℹ️ Info | Pre-existing since 8897690 (Phase 4); cosmetic |

No TBD/FIXME/XXX/TODO/HACK in `src/f1si`. No skipped tests in phase-linked test files (only cache-absent skips in older `tests/real` modules and a platform-specific Phase 3 hash test).

### Decision Coverage

All trackable CONTEXT.md decisions are honored by shipped artifacts (11/11).

### Human Verification Required

#### 1. Exact-head CI for 2759d60
**Test:** Confirm the Ubuntu and Windows `ci.yml` jobs are green on 2759d60.
**Expected:** Both pass, including the 10 tests that cannot run locally because they spawn `python -I`.
**Why human:** `gh` is unavailable in this shell; the run was in progress.

#### 2. Labelling sparse-fallback recommendations on the page
**Test:** Open the default view (Bahrain 2023, ALO, after lap 15) and read the decision band.
**Expected:** Owner decides whether the thin-tyre-data note is enough, or whether a fallback call needs an "uncalibrated" or "rough estimate" marker.
**Why human:** The CLI marks this cutoff `sparse fallback ... [ASSUMED] 1.0 s pace-offset SD, uncalibrated`. The page shows only the tyre note (`app.py:1083-1084`), which describes tyre wear, not the prior-driven pace fit. V2 decision 12 dropped the 06-UI-SPEC "Uncalibrated" label. Whether that was meant to cover pace-fit fallbacks is a design call.

#### 3. Owner acceptance (Plan 06-10 Task 06-10-02)
Orchestrator item: record the 2026-11-16 approval in 06-10-SUMMARY.md. Not a verification gap.

### Gaps Summary

**No blocking gaps.** All five roadmap success criteria and both carried-forward checks hold in the codebase, the tests pass and the measured report is reproducible from tracked code.

**Non-blocking warnings (recommended fixes):**

- **W-1 README misstates FastF1's role.** `README.md:65` says FastF1 "was the original planned source ... the current loader uses OpenF1 and Jolpica instead". However, FastF1 now supplies the scheduled lap counts that both the backtest and the page require (`src/f1si/data/loader.py:354-361,427-467`; `walk_forward._race_laps_total` raises without them). It also supplies team colors (`src/f1si/plots/replay_charts.py:208-220`). OpenF1 writes `scheduled_laps=None` (`src/f1si/data/sources/openf1.py:260`), and DEC-107 records that fresh FastF1 timing downloads now need F1 TV. **Fix:** reword the credits paragraph so it says FastF1 (MIT) provides scheduled race distance via `f1si backfill-scheduled-laps` and team colors, that fresh FastF1 timing downloads may need an F1 TV account (DEC-107), and that F1 timing data stays under Formula 1's terms. Mirror the change in `docs/explained/phase-06.md:101`.
- **W-2 Fallback calls are not marked uncalibrated on the page.** See Human Verification item 2. **Fix if the owner wants it:** when `result["fallback"]` is true, append the COPY_V2-style fog note (for example "Early in the race the model leans on general assumptions, so treat this call as a rough guide.") to `notes` in `_decision_band_html`, and add a test in `tests/app/test_app.py`.
- **W-3 README does not show how to reproduce Phase 6.** Neither README nor the explainer names `f1si backfill-scheduled-laps` or `f1si backtest --report`. After a fresh `f1si load`, the backtest preflight and the page fail with "No race can be replayed" until the backfill runs. **Fix:** add both commands to the Quickstart before `streamlit run`. If `test_readme_commands_and_links` enumerates commands, extend it to cover them.
- **I-1 (info) The page model report shows point estimates only.** Race-cluster intervals are in the JSON and the README, which is where SC2 and SC3 apply. The timing graphic draws a symmetric "X laps early / X laps late" band, so it hides the signed +1.96-lap late bias that the README reports. This is optional copy work.
- **I-2 (info) README:33 places "7,650 of 9,146" next to coverage 0.832.** 0.832 is the equal-race mean; the pooled rate is 0.836. The page states the aggregation correctly (`app.py:1555-1557`).

---

_Verified: 2026-11-16_
_Verifier: Claude (gsd-verifier)_

## Resolution (2026-11-16)

- **Exact-head CI:** the human item named `2759d60`; the final head is `08672fe`, which adds the
  warning fixes on top. CI run 43829374437 passed on Ubuntu and Windows for `08672fe`.
- **Fallback label (owner decision):** resolved with the recommended option. When `fallback` is
  true the decision band now reads "Uncalibrated: there's too little tyre data at this lap, so the
  model falls back to prior estimates. Treat this call as a rough guide." (`08672fe`).
- **Owner acceptance:** recorded in `06-10-SUMMARY.md`; the owner approved the redesigned page at
  desktop and phone widths.
- **W-1 credits and W-3 Quickstart:** README and `docs/explained/phase-06.md` now say FastF1 supplies
  the scheduled lap counts and team colors (fresh timing downloads may need F1 TV, DEC-107), and the
  Quickstart lists `backfill-scheduled-laps`, `backtest --report` and the Streamlit command
  (`08672fe`).
