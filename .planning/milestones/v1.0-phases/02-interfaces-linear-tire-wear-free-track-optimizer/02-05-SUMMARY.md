---
phase: 02-interfaces-linear-tire-wear-free-track-optimizer
plan: 05
subsystem: docs
tags: [docs, explainer, readme, real-data, gate]
requires: ["02-01", "02-02", "02-03", "02-04"]
provides:
  - "docs/explained/phase-02.md complete (4 Q&As, real Bahrain 2023 numbers)"
  - "README wear and plan commands plus Phase 2 link"
  - "tests/real/test_wear_bahrain.py opt-in real-data checks"
key-files:
  created:
    - tests/real/test_wear_bahrain.py
  modified:
    - docs/explained/phase-02.md
    - README.md
    - tests/test_docs.py
key-decisions: []
requirements-completed: [UI-03, INT-03, PAC-01, PAC-02]
completed: 2026-11-11
---

# Phase 2 Plan 05: Explainer, README and real Bahrain checks Summary

Completed the plain-language Phase 2 explainer, README commands, README/phase-02 docs-test needles and an opt-in real Bahrain 2023 test; full gate green.

## Tasks

| Task | Commit | Result |
|------|--------|--------|
| 1: Explainer, docs test needles, README | e325217 | explainer in Phase 1 format with measured numbers (fuel -0.078 s/lap, HARD +0.121, SOFT +0.125, offset +0.26 SE 0.13, ALO 1:34:03.1 vs 1:34:03.9); README wear/plan examples and phase-02 link; phase-02 tour test |
| 2: Opt-in real test + gate | d7187d6 | 5 `network`-marked tests (wear bands, pit loss, RaceState at lap 0/20/end with JSON round trip, ranked ALO plan, `plan` CLI) |

## Gate results (local, Windows)

- `uv run ruff check .` pass
- `uv run ruff format --check .` pass (98 files)
- `uv run python -m mypy` pass (93 source files; `uv run mypy` is blocked by Windows Application Control here)
- `uv run pytest` 655 passed, 13 deselected (network)
- `uv run pytest -m network -v tests/real/test_wear_bahrain.py` 5 passed against the local cache

## Deviations from Plan

None in substance. The generalized docs test already existed from 02-01, so only needles and the phase-02 tour test were added. A mypy typing slip in the new real test (`int | str` for the lap) was fixed before committing.

## For the verifier / owner

- CI (Ubuntu and Windows) must be green after the owner pushes; nothing was pushed.
- Manual-only checks: open `reports\wear-bahrain-2023.png`; run `uv run f1si wear bahrain-2023` and `uv run f1si plan bahrain-2023 --driver ALO`.
- Phase not marked complete in ROADMAP (pending verification and green CI).

## Known Stubs

None.

## Self-Check: PASSED

Files exist (explainer, README, tests/test_docs.py, tests/real/test_wear_bahrain.py); commits e325217 and d7187d6 exist.
