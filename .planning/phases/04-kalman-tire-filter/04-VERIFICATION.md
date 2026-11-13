---
phase: 04-kalman-tire-filter
verified: 2026-11-13T00:00:00Z
status: human_needed
score: 4/4 must-haves verified (2 with human decision items)
overrides_applied: 0
human_verification:
  - test: "Accept or reject the conditional narrowing assertion in tests/real/test_wear_filter_bahrain.py (lines 108-114)"
    expected: "Owner decides if 'band narrows over the first laps' is honestly met when, with a tight fit prior (SD ~0.03 s/lap, noise ~0.48 s), 7 used laps only narrow the SD by 5-7% (ratios 0.95/0.95/0.93 on ALO). The 0.9 factor is asserted only when prior SD >= 0.05, which ALO never triggers; only 'SD < prior SD' is gated there."
    why_human: "Judgement on whether a conditional, weakened threshold satisfies roadmap criterion 1"
  - test: "Decide on WR-05 (fit prior includes the filtered car's own current-stint laps) versus the honest-band goal"
    expected: "Lap 14 as-of fit gave SOFT +0.255 +/- 0.041 while hindsight is +0.12 to +0.125, so the 95% band excludes the hindsight value. Own laps are 4-6% of the prior's clean laps. Documented only (DEC-091 known limitation, explainer 'Good to know'); no fix."
    why_human: "Method choice belonging to the owner; bears on the 'honest uncertainty band' goal on real data"
  - test: "Confirm CI green on 41d844b (Ubuntu and Windows)"
    expected: "GitHub Actions passes. Last confirmed green was 9c34683. The gh CLI is not available to the verifier."
    why_human: "Cannot query CI from this environment; CLAUDE.md requires CI green before the phase counts as done"
  - test: "Look at reports/wear-filter-bahrain-2023-ALO.png"
    expected: "Estimate line, shaded 95% band, stint boundaries, dashed hindsight line, readable"
    why_human: "Visual appearance"
---

# Phase 4: Kalman Tire Filter Verification Report

**Phase Goal:** User can watch the hidden tire-wear estimate for a car sharpen lap by lap, with an honest uncertainty band
**Status:** human_needed
**Re-verification:** No, initial verification

## Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Filter on a real stint shows a wear-rate estimate with a band narrowing over the first laps | VERIFIED, with human decision item | I ran `python -m f1si wear-filter bahrain-2023 --driver ALO`. It printed per-stint, per-lap tables with 95% low/high. Stint 2 HARD: band width 0.148 at lap 16 narrowing to about 0.087 by lap 23. Stint 1 band narrows only slightly (0.196 to 0.185 from lap 3 to 11) and then rises as the data shows high wear. The real-data test gates strict narrowing (`sds[6] < prior SD`) but the 0.9 factor only when prior SD >= 0.05. Narrowing is real but small under a tight prior. |
| 2 | Synthetic stints: estimate reaches Bayes-optimal accuracy (D-17 restatement); 10% figure reported, not gated | VERIFIED | `tests/pace/test_kalman_recovery.py` contains `test_posterior_sd_matches_closed_form`, `test_filter_equals_regression_oracle` (closed-form match), `test_optimal_accuracy`, `test_accuracy_report`. All passed in my full run. REQUIREMENTS.md PAC-04 carries the owner's restatement. |
| 3 | 95% intervals contain truth about 95% of the time | VERIFIED | `test_coverage` and `test_coverage_with_fuel_prior` (1,000+ seeded stints, binomial band) passed. |
| 4 | Filter mean and sd populate the RaceState fields the simulator reads | VERIFIED | `build_race_state(..., wear_filter=...)` in `src/f1si/state.py` sets `wear_rate_s_per_lap`, `wear_sd`, `wear_source="filter"`. Sim tests (`tests/sim`, Phase 3 reference byte-identity) and state-builder tests passed. |

**Score:** 4/4 verified (criterion 1 carries a human decision).

## Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| PAC-03 | 04-01, 04-02, 04-03, 04-04, 04-05 | SATISFIED | `src/f1si/pace/kalman.py` (WearFilter, adapter), CLI, plot, state wiring. All in the PLAN frontmatter and REQUIREMENTS.md line 33. |
| PAC-04 | 04-02, 04-05 | SATISFIED, as restated by owner (D-17) | Coverage gated and passing; accuracy gated as Bayes-optimal; 10% reported only. |

Both IDs appear in REQUIREMENTS.md (lines 33-34, traceability 114-115, still unchecked as the orchestrator intends). No orphaned requirements for Phase 4.

## Behavioral Spot-Checks and Gate

| Check | Result |
|-------|--------|
| `ruff check .` | pass |
| `ruff format --check .` | 149 files already formatted |
| `mypy` (strict) | no issues in 142 source files |
| Full pytest (default markers) | 933 passed, 25 deselected, 9 failed, 1 error. All 10 are the known environment-only failures (5 test_import_order, 4 `test_module_imports_without_pyplot`, db-lock test, which here also reports `No module named 'duckdb'` in the subprocess). No other failures. |
| `pytest -m network` (real Bahrain) | 25 passed |
| `f1si wear-filter bahrain-2023 --driver ALO` | exit normally; table printed; report PNG exists in `reports/` |

## Probe Execution

None declared. Step skipped.

## Anti-Patterns

I did not run a full marker scan. The REVIEW-FIX report records all ten review findings as fixed, with tests added. The git tree was clean at the start.

## Other Notes

- Phase 3 flag: ALO 90% interval at lap 20 is P4-P8 with and without the filter (taken from the orchestrator and the test's printed output; the test prints this and never gates it).
- The 0.9-factor conditional is a test-side relaxation in a real-data check, not a code stub. The strict SD decrease is still asserted.

## Gaps Summary

No blocking gaps. Four items need a human: the narrowing-threshold conditional, WR-05, CI confirmation on 41d844b, and a visual check of the plot.

_Verified: 2026-11-13_
_Verifier: Claude (gsd-verifier)_
