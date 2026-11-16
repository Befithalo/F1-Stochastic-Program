# Deferred Items

- `uv run python -m pytest tests/guards/test_import_ban.py -q` has two pre-existing failures: `src/f1si/backtest/scoring.py` imports `numpy.random.default_rng` at lines 205, 238, and 319, contrary to the repository's single-generator factory rule. These paths are outside Plan 06-06; the app introduces no random generator and uses `f1si.rng.make_rng`.
