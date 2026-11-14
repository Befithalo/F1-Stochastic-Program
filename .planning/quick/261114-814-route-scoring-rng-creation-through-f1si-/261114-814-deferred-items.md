# Deferred Items — Quick Task 261114-814

## Open

- **Phase 06, test fixture failure (confirmed on baseline):** `tests/backtest/test_metrics.py:262`, test `test_predictions_freeze_before_first_results_open_and_score`, fails at `src/f1si/backtest/scoring.py:281` because its fake snapshot `entries` has `driver_code` and `grid_position` but no `driver_number`. The exact test fails on pre-fix commit `b731a54` in an isolated detached worktree, confirming this was not caused by the RNG factory change. Tracked as open item 2 in `.planning/WINDOWS.md`; resolve before phase or milestone shipping.

## Resolved

- **Phase 06 scoring RNG import-ban violation:** all three direct `np.random.default_rng` calls in `src/f1si/backtest/scoring.py` now use `f1si.rng.make_rng`. Resolved as Windows ledger item 1 in commit `1c36457`.
