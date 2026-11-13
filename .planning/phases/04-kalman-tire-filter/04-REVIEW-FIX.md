---
phase: 04-kalman-tire-filter
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Source review:** `.planning/phases/04-kalman-tire-filter/04-REVIEW.md`
**Scope:** all findings (WR-01..WR-05, IN-01..IN-05). Commit order below is the order applied.

WR-05 was documented only, as instructed (the method is an owner decision). No existing test was changed or loosened. WR-01 intentionally changed what the CLI table contains, but no existing assertion needed editing. Tests were only added.

## Findings

| ID | What changed | Commit | Test |
|----|--------------|--------|------|
| IN-01 | Module docstring now says the gate applies "once at least GATE_MIN_USED laps have been used (DEC-090)". | 2129ff1 | docstring only |
| IN-02 | `_finite` accepts numpy integer and floating scalars (numpy bool still rejected). | 3cbaf79 | `tests/pace/test_kalman_math.py::test_numpy_scalars_are_accepted_as_numbers` (fails before) |
| WR-03 | `resolve_priors`: a non-finite fuel effect counts as missing. A usable fuel effect with a None or NaN `fuel_se` keeps the fitted mean and uses `GENERIC_FUEL_SD`, labelled "fit (generic SD: fuel SE not available)". No crash. | 410ef57 | `tests/pace/test_kalman_adapter.py::test_missing_or_nonfinite_fuel_se_uses_fit_mean_with_generic_sd` (None, NaN, inf), `::test_nonfinite_fuel_effect_falls_back_to_generic_everything_fuel_related` (fail before) |
| WR-02 | `filter_stints` calls a predict-only `observe(None, "missing lap")` for each race lap absent between two lap rows of a stint. No row is added for the missing lap. | 908c9a6 | `::test_missing_lap_row_equals_the_same_lap_marked_skipped` (fails before) |
| WR-04 | `FilterSnapshot` gains trailing `compound: str | None = None` (positional construction and JSON unaffected). `current_stint_snapshots` fills it. `build_race_state` ignores an entry whose compound is set and differs from the car's current compound (treated as "fit", no error). | 9c3a5fc | `tests/test_state_builder.py::test_wear_filter_entry_for_another_compound_is_ignored` (fails before) |
| IN-03 | `re.fullmatch` for slug and driver checks in `plots/wear_filter.py`. | 3ed66f7 | `tests/plots/test_wear_filter_plot.py::test_trailing_newline_is_unsafe` |
| IN-04 | Generator rejects non-integer or bool keys and non-numeric or bool values of `wear_rate_deviation_s_per_lap` with ValueError. The default (empty mapping) path is untouched; the existing hash tests pass. | 65287fc | `tests/test_synthetic.py::test_wear_deviation_rejects_wrong_key_and_value_types` |
| WR-01 | New pure lookup `kalman.cutoff_rows` (registered as EXEMPT in `tests/guards/consumers.py`). The CLI collects every row that first becomes visible at a cutoff, each computed from that cutoff's snapshot (as-of rule kept). `cutoff_row` is kept for the prior checks. | ebc52cb | `tests/test_cli_wear_filter.py::test_laps_that_appear_several_at_a_time_reach_the_table` (the car's lap 5 appears together with lap 6; fails before), `tests/plots/test_wear_filter_plot.py::test_cutoff_rows_returns_every_visible_row_in_lap_order` |
| IN-05 | The CLI counts gate rejections from the shown rows (`reason == "outlier gate"`), the same rows as used and skipped. | a06064e | `tests/test_cli_wear_filter.py::test_gate_rejection_count_comes_from_the_shown_rows` (fails before) |
| WR-05 | Documented only. DEC-091 gets a "Known limitation" paragraph. Bahrain 2023, ALO, share of the prior's clean laps that are his own current stint: lap 14 SOFT 12 of 193 (6.2%); lap 20 SOFT 12 of 216 (5.6%), HARD 4 of 97 (4.1%); lap 30 SOFT 12 of 259 (4.6%), HARD 14 of 227 (6.2%). It is a share of laps, not a measured bias. `docs/explained/phase-04.md` "Good to know" mentions it as a likely contributor to the lap-14 SOFT bias. No DEC entry added, so `MIN_ENTRIES` is unchanged (95). | 2088b14 | `tests/test_decisions_log.py` and `tests/test_docs.py` still pass |

## Verification

- `ruff check .`: all checks passed. `ruff format --check .`: 149 files formatted. `mypy` (strict): no issues in 142 source files.
- Full suite (default markers): 933 passed, 25 deselected, 9 failed, 1 error. All 10 are the known environment-only failures: `tests/test_import_order.py` (5), the 4 `test_module_imports_without_pyplot` tests in `tests/plots`, and the error in `tests/data/test_db_roundtrip.py::test_lock_held_by_another_process_raises_cache_busy`.
- `-m network`: 25 passed, 943 deselected.
- Phase 3 reference tests and `tests/sim` pass unchanged.

## Notes

- Work was done directly on `main` and not in a separate worktree. The working tree was clean at the start and no foreground session was running. The Bahrain cache and the shim venv are untracked and would not exist in a fresh worktree.
- Windows wrote CRLF into some working-copy files during editing. All touched files were normalised to LF before each commit, and the diffs contain only the intended changes.

_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
