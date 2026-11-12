---
phase: 03-monte-carlo-simulator
verified: 2026-11-12T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
human_verification:
  - test: "Push the phase and confirm GitHub Actions is green on Ubuntu and Windows"
    expected: "CI passes (quality gate in CLAUDE.md); the 10 s benchmark holds on the CI runners"
    why_human: "Phase commits are not pushed; CI has not run"
  - test: "Open reports/sim-bahrain-2023-ALO-lap0.png"
    expected: "The finishing-position distribution plot is readable"
    why_human: "Visual check"
  - test: "Review CR-01 (kernel order/clock sweep) and WR-05 (SC stop min-stint) logic changes"
    expected: "Logic is sound; REVIEW-FIX flags both as needing human verification"
    why_human: "Logic changes made after the plans"
---

# Phase 3: Monte Carlo Simulator Verification Report

**Goal:** User can simulate 50,000 continuations of a race from any `RaceState` in under 10 s with a reliable, low-variance result.
**Status:** human_needed (no gaps found)

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Bahrain 2023 RaceState gives a finishing-position distribution for a chosen driver | VERIFIED | `uv run python -m f1si simulate bahrain-2023 --driver ALO` printed P1..P20 shares (P4 75.3%, mean 4.27, 90% interval 4-6). The opt-in real-data test `-m network tests/real/test_simulate_bahrain.py` gave 6 passed. |
| 2 | 50,000 races finish in under 10 s | VERIFIED | `tests/sim/test_benchmark.py::test_50k_races_under_10_seconds` passed in the full suite. The CLI reported 3.4 s for 50,000 races. |
| 3 | Safety cars occur at a per-lap probability and change pit loss and gaps | VERIFIED | `tests/sim/test_sc_frequency.py` (the frequency check, tolerance 0.03 as restored) and `tests/sim/test_safety_car.py` (frozen-order restart gaps, cheap stop under SC, opportunistic stop) pass. The CLI reports an SC in 43.7% of Bahrain races. |
| 4 | Sobol plus antithetic has lower variance than plain MC at equal N | VERIFIED | `tests/sim/test_variance_reduction.py::test_variance_ratios` passes. Measured ratios: finish 3.81, time 11.74, SC share 2.47. The margins (2.1, 6.5, 1.8) were re-baselined by one stated rule (DEC-083); each rejects "no reduction" at p < 0.001. |
| 5 | The same seed reproduces identical results | VERIFIED | `tests/sim/test_reproducibility.py::test_same_seed_is_bit_identical` passes. |

**Score:** 5/5

## Orchestrator corrections checked

- Pass-curve constants `THRESHOLD_S = 0.4` and `SCALE_S = 0.2` are in `src/f1si/sim/constants.py`. Plan 03-03 text matches. DEC-078 exists.
- Benchmark SC-share tolerance is 0.03.
- DEC-083, DEC-086 and DEC-087 are present in DECISIONS.md. The variance-test header states the margin rule.
- CR-01, CR-02, WR-01..05 and IN-01..03 are all reported fixed in 03-REVIEW-FIX.md, and the tests for them are in the passing suite.
- The measured values in the test comments (3.81 / 11.74 / 2.47) match those reported after the CR-02 fix.
- The 03-03 plan text still lists `MAX_RACES = 1_000_000`. The code now uses 200,000 (WR-03, DEC-085). This is a historical plan-text difference, not a gap.

## Spot-checks run

| Command | Result |
|---------|--------|
| `uv run python -m pytest -q` | 802 passed, 19 deselected (158 s) |
| `uv run python -m mypy` | Success: no issues found in 129 source files |
| `uv run ruff check .` | All checks passed |
| `uv run python -m pytest -m network tests/real/test_simulate_bahrain.py -q` | 6 passed |
| `uv run python -m f1si simulate bahrain-2023 --driver ALO` | Distribution printed in 3.4 s; PNG written |

## Requirements Coverage

All four IDs appear in the plan frontmatter and are marked Complete in REQUIREMENTS.md. No orphaned requirements.

| Requirement | Status | Evidence |
|-------------|--------|----------|
| SIM-01 | SATISFIED | Vectorized NumPy backend (`src/f1si/sim/numpy_backend.py`, `kernel.py`) with pit loss, a pass chance from pace gap, and SC events. The CLI run and tests exercise it. |
| SIM-02 | SATISFIED | Benchmark test passes; CLI ran in 3.4 s. |
| SIM-03 | SATISFIED | Variance-ratio test passes with Sobol plus antithetic sampling (`draws.py`). |
| REG-01 | SATISFIED | Per-lap SC probability drives the simulator; frequency and effect tests pass. |

## Anti-patterns

No blockers were found. Mypy and ruff are clean. I did not run a separate TBD/FIXME/XXX scan.

## Human verification required

1. **CI on Ubuntu and Windows.** Nothing is pushed, so the quality gate has not been met by CI. The benchmark margin on a CI runner is also untested.
2. **PNG readability.** Open `reports/sim-bahrain-2023-ALO-lap0.png`.
3. **Logic review of CR-01 and WR-05.** Both change kernel behavior after the plans were written.

## Gaps Summary

No gaps. All five success criteria are verified by tests and a live run. Status is human_needed only because of the items above.

_Verified: 2026-11-12_
_Verifier: Claude (gsd-verifier)_
