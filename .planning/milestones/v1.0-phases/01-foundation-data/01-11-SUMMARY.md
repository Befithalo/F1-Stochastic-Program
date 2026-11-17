---
phase: 01-foundation-data
plan: 11
subsystem: docs
tags: [explainer, decisions, ci, push, canary]

requires:
  - phase: 01-10
    provides: full real load, weekly real-data workflow
provides:
  - docs/explained/phase-01.md (UI-03 plain-language explainer, D-17)
  - tests/test_docs.py (keeps the file-by-file tour complete)
  - README quickstart and Phase 1 section; DEC-051 and DEC-049 real-data update
  - Phase 1 pushed to GitHub with CI green on ubuntu and windows
affects: [phase-2]

tech-stack:
  added: []
  patterns:
    - "Every phase ends with docs/explained/phase-NN.md guarded by a completeness test (DEC-051)"

key-files:
  created:
    - docs/explained/phase-01.md
    - tests/test_docs.py
  modified:
    - README.md
    - DECISIONS.md
    - tests/test_decisions_log.py

key-decisions:
  - "DEC-051: a plain-language explainer for every phase, kept complete by a test"

requirements-completed: [UI-03, FND-02, FND-04, DAT-04]

duration: ~50 min
completed: 2026-10-22
---

# Phase 1 Plan 11: Explainer, decision log and the green final push Summary

**The owner now has a plain-language explainer with a test that keeps its file-by-file tour complete, the decision log stands at DEC-001..DEC-051, and the final state is on GitHub with CI green on Linux and Windows, including the canary that proves a planted leak fails the build.**

## Accomplishments

- `docs/explained/phase-01.md`: the four D-17 sections (what was built and why, how the pieces connect with a text diagram, a file-by-file tour of all 22 non-init `src/f1si` modules plus the guards, fixtures, `conftest.py`, both workflows and `DECISIONS.md`, and five interview Q&As) plus "Good to know". It uses measured facts: 87 races cached (70 in-sample, 17 locked 2026), Bahrain 2023 with 20 drivers, 1,058 laps and a VSC on lap 41, the D-08 data-source change (FastF1 401, replaced by OpenF1 and Jolpica), the mutation check where removing the cutoff in `_snapshot.py` made the scramble test fail, and the caveats (3 Bahrain pit in-laps without OpenF1 lap end times, the slug `bahrain-grand-prix-in-malaysia-2026`, OpenF1 access from GitHub runners unverified until the weekly workflow runs).
- `tests/test_docs.py`: headings in order, 3-5 questions each with an answer of at least 40 characters, every `src/f1si/**/*.py` path (except `__init__.py`) in the tour, guards/fixtures/workflows mentioned, README commands and links.
- `README.md`: status, "What Phase 1 gives you", final Quickstart (including the synthetic demo with `--data-dir data/demo`), links to the explainer and `DECISIONS.md`, OpenF1 / Jolpica credit kept.
- `DECISIONS.md`: final pass. Every "Decisions to log" item in 01-02..01-10 was already an entry (matched by title: DEC-015..DEC-050), so only two changes: DEC-049 consequences now record the real-data grid-0 check from 01-10 (4 entries, rule held, `NON_STARTER_STATUSES` unchanged), and DEC-051 (explainer convention) was appended. `MIN_ENTRIES` raised to 51; the new title is checked by title.

## Final gate

- Local: `ruff check`, `ruff format --check`, `mypy` strict clean; full `pytest`: 359 passed, 8 network tests deselected.
- Audit before pushing: `git ls-files` contained nothing under `data/` or `reports/`, no `*.duckdb`, no `desktop.ini`, no `.env`.
- Push: `6fb9e9b..269cf29 main -> main`; `git ls-remote origin main` equalled local HEAD.
- CI run for 269cf29: https://github.com/Befithalo/F1-Stochastic-Program/actions/runs/39808481318 - conclusion **success**.
  - `checks (ubuntu-latest)`: success; step "Canary: a planted leak must fail the import ban (DAT-04)": success.
  - `checks (windows-latest)`: success; the canary step is skipped there by design (`if: runner.os == 'Linux'`).
- Workflows API lists "CI" and "Real data (non-blocking)".
- Confirmed through the unauthenticated GitHub API, no owner fallback needed. API requests used for this check: 5 (3 polls spaced 65 s, 1 jobs call, 1 workflows call), well under the 25 limit.

## Full-load counts and upstream gaps (from 01-10)

87 races cached: 2023 22, 2024 24, 2025 24 (70 in-sample, era `ground_effect_2022_2025`) and 17 from 2026 (`reg_2026`, locked). Zero failures, zero upstream gaps; `01-UPSTREAM-GAPS.md` does not exist.

## Task Commits

1. **Task 1: explainer, completeness test, README, DECISIONS** - `269cf29` (docs)
2. **Task 2: final gate and push** - no code change; pushed 269cf29, CI green.

## Deviations from Plan

- The explainer has five Q&As (the plan allowed up to five) and a fifth section "Good to know" as specified. The tour also lists `tests/fixtures/leaky_through_accessor.py` and `tests/guards/consumers.py`, which the plan did not name.
- The planned README "Status" line was changed from "in progress" to "done".
- The plan's final-sha check used a one-line curl; a small polling script in the session scratchpad was used instead (same endpoint, same limits, defensive `.get` parsing).

## Human checks (collected from 01-08, 01-09, 01-10 and this plan)

1. PowerShell: `cd $HOME\Documents\f1si` then `uv run f1si races`. Expect 87 rows (every 2023-2025 Grand Prix with era `ground_effect_2022_2025` and out-of-sample `no`; each 2026 race `reg_2026` and `yes (locked)`), last line "87 races cached (17 out-of-sample and locked)" (01-08, 01-10).
2. Open `reports\bahrain-2023.png` (run `uv run f1si plot bahrain-2023` first if it is missing). Expect 20 panels in 4 rows of 5, VER P1 first; red SOFT, yellow MEDIUM, white HARD with dark edges; lap 1, pit laps and VSC laps faded; pit laps as small up-arrows at the top; dotted lines at stint changes; lap times drifting up inside each stint (01-09).
3. GitHub Actions tab, "Real data (non-blocking)", "Run workflow", then open the finished run. Expect "Real-data check (Bahrain 2023)" with "Result: success". A failure only turns that run red (most likely OpenF1 blocking GitHub's servers) and does not affect CI (01-10, this plan).
4. Read the "Interview questions" in `docs/explained/phase-01.md` and check you can explain in your own words why "as of lap 15" shows 15 laps for the leader and at most 14 for others, and why final results sit behind a separate door (this plan, UI-03).
5. Optional: decide whether the 2026 slug `bahrain-grand-prix-in-malaysia-2026` (upstream event name, circuit `sepang`) should be shortened (01-10).

## Known Stubs

None. `scheduled_laps` is deliberately NULL until Phase 2 (DEC-047).

## Threat Flags

None. T-01-46 (CI claim verified from the Actions API for the exact sha, canary step conclusion recorded), T-01-55 (tracked-file audit before the push) and T-01-56 (polls 65 s apart, 5 requests) were applied.

## Plain-language summary for the owner

Phase 1 is finished and on GitHub. You can now download every 2023, 2024 and 2025 Grand Prix, plus the 2026 races, with one command, `uv run f1si load`, and they are saved on your own computer. `uv run f1si races` lists what you have, and `uv run f1si plot bahrain-2023` draws each driver's lap times by tyre stint. The 2026 races are locked away on purpose so they can be used later as a fair final exam. The most important part is the protection against looking into the future: every read goes through one door that only shows what was known at that lap, and two automatic tests prove it, including a test that scrambles the future and checks nothing changes. On every push, GitHub runs all checks on Linux and Windows, and they are green, including a canary test that plants a deliberate cheat and confirms the build catches it. Every method choice is in `DECISIONS.md`, and `docs/explained/phase-01.md` explains everything in plain words with interview questions. One thing is still unproven: whether the free OpenF1 service lets GitHub's servers in for the weekly real-data check, which you can test from the Actions tab.

## Self-Check: PASSED

- docs/explained/phase-01.md, tests/test_docs.py exist; commit 269cf29 exists on main and on origin/main.
- CI run 39808481318 concluded success for 269cf29.
