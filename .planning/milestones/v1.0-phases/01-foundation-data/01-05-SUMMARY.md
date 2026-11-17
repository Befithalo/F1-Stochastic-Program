---
phase: 01-foundation-data
plan: 05
subsystem: testing
tags: [ast, import-ban, look-ahead-guard, ci-canary, decisions-log, pytest]

requires:
  - phase: 01-03
    provides: loader, asof.catalog, CLI, CI workflow
provides:
  - AST import scanner with a single POLICY table (tests/guards/import_scan.py)
  - Import-ban guard tests that run on every pytest invocation
  - Planted leaky fixture and a CI canary step that proves the build fails when the leak is inside src/f1si
  - DECISIONS.md with DEC-001..DEC-035 and a structure test
affects: [01-06, 01-07, 01-08, 01-09, 01-10, 01-11]

tech-stack:
  added: []
  patterns:
    - "One POLICY table (protected name -> allowed importer modules) drives the whole import ban"
    - "Guard canary is rehearsed on a temp copy inside pytest, never by writing into the real src/ tree"
    - "DECISIONS.md entries are asserted by title or keyword, never by a number above DEC-014"

key-files:
  created:
    - tests/guards/__init__.py
    - tests/guards/import_scan.py
    - tests/guards/test_import_ban.py
    - tests/fixtures/__init__.py
    - tests/fixtures/leaky_consumer.py
    - DECISIONS.md
    - tests/test_decisions_log.py
  modified:
    - .github/workflows/ci.yml

key-decisions:
  - "AST scan chosen over import-linter (DEC-002): sees importlib/__import__ strings, scans fixtures, no duplicate config"
  - "A protected f1si module may import its own submodules without an explicit allow entry"
  - "The CLI composes the data source; RESEARCH's responsibility map is deliberately deviated from (DEC-015)"

patterns-established:
  - "scan_package(src_root) takes an optional root so the canary can be rehearsed on a copy"
  - "Fixture lives under tests/fixtures and is never imported; it is only parsed or copied"

requirements-completed: [DAT-04, FND-03, FND-04, FND-02]

duration: ~35 min
completed: 2026-10-22
---

# Phase 1 Plan 05: Import Ban, Leak Canary and Decisions Log Summary

**An AST import scanner with one policy table fails the build when code reaches around the data doors (duckdb, sqlite3, raw network, the results and 2026 doors, RNG constructors), a planted leaky fixture proves it in pytest and in a CI canary step, and DECISIONS.md records 35 method choices with a structure test.**

## Performance

- **Tasks:** 2 of 2 complete
- **Tests:** 158 pass (was 114): 34 in `tests/guards/test_import_ban.py` (27 snippet cases plus tree, policy, init, tests-import, fixture and canary-copy tests), 10 in `tests/test_decisions_log.py`
- ruff check, ruff format --check and mypy strict are clean on the whole tree (mypy includes the fixture)

## Accomplishments

- `tests/guards/import_scan.py` exports `Rule`, `Violation`, `POLICY`, `scan`, `scan_package`, `format_violations`. It resolves relative imports, yields `pkg.name` for `from pkg import name`, catches `importlib.import_module`, `import_module` and `__import__` with string literals, and flags `np.random.default_rng`, `RandomState`, `np.random.seed` and bit generators by attribute use. The docstring states the honest limit.
- The real `src/f1si` tree scans clean today; `f1si/data/__init__.py` has no import nodes; `f1si/data/sources/__init__.py` imports no adapter; no src module imports `tests`.
- Every allowed and flagged snippet in the plan's behavior list passes, plus extras (`PCG64`, `from f1si.data import _db`, `_snapshot`, `Generator` attribute and a string containing "import duckdb" are handled correctly).
- `tests/fixtures/leaky_consumer.py` (imports duckdb, averages the whole race) is flagged by the scanner; `test_canary_copy_of_src_tree_is_caught` copies `src/f1si` to a temp dir, adds the fixture as `_canary.py` and sees a duckdb violation for `f1si._canary`.
- CI step "Canary: a planted leak must fail the import ban (DAT-04)" (Linux only, bash) copies the fixture to `src/f1si/_canary.py`, requires the import-ban test to fail, removes the file on both branches, and emits `::error::` if the leak was not caught.
- Local canary rehearsal against the real tree: **canary caught as expected**; `src/f1si/_canary.py` does not exist afterwards and `git status` is clean of it.
- DECISIONS.md: DEC-001..DEC-014 as specified, then DEC-015 (The CLI chooses the data source) and DEC-016..DEC-035 from the plan 01-02, 01-03 and 01-04 "Decisions to log" lists.

## DEC numbers actually assigned

| DEC | Title |
|-----|-------|
| 001-014 | As specified in the plan (cutoff, guards, doors, walk-forward, data source, CI data policy, eras, cutoffs, RACE_END, provenance, storage, pandas, seed, lint pins) |
| 015 | The CLI chooses the data source |
| 016 | Cache lock errors are recognised by their text |
| 017 | write_race refuses a partial race |
| 018 | Stored visibility is always recomputed |
| 019 | Views are stored as SELECT bodies |
| 020 | Prose folders are excluded from ruff; data folders are anchored in .gitignore |
| 021 | One random stream per synthetic race |
| 022 | Synthetic noise is drawn up front, in a fixed order |
| 023 | The synthetic generator exposes its ground truth |
| 024 | The catalog returns calendar facts only |
| 025 | Actions are pinned to exact tags when no floating major tag exists |
| 026 | Per-lap track status is a string of codes |
| 027 | Track status codes are a closed set |
| 028 | Derived tables are not supplied by sources |
| 029 | Loader failure policy |
| 030 | Rate-limit waiting |
| 031 | Resume by completion marker |
| 032 | Mixing sources is refused |
| 033 | `--only` matches schedule ids and slugs only |
| 034 | Synthetic weather and safety-car events |
| 035 | UnknownEraError carries the season |

Skipped as already covered: the lap-cutoff item from plan 01-04 (DEC-008) and "no PRIMARY KEY" from plan 01-02 (DEC-011). `MIN_ENTRIES` in `tests/test_decisions_log.py` is 35; plans 01-08, 01-09 and 01-11 append after DEC-035 and should raise it.

## Task Commits

1. **Task 1: AST import scanner, guard tests, planted leaky fixture** - `ebb666e` (feat)
2. **Task 2: CI canary step, DECISIONS.md, structure test** - `aaca770` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixture docstring and one assert line failed ruff (E501, SIM300)**
- **Found during:** Tasks 1 and 2 verification
- **Fix:** Rewrapped the fixture docstring (the required phrase "DELIBERATELY LEAKY test fixture for the D-02 meta-test and CI canary." is kept); rewrote `REQUIRED_REFS <= refs` as `refs >= REQUIRED_REFS`.
- **Commits:** ebb666e, aaca770

**2. [Design addition] Protected f1si modules may import their own submodules**
- `_allowed()` lets `f1si.data.results.x` import `f1si.data.results` without listing itself. Only applies to protected names starting with `f1si.`. No effect on today's tree.

**3. [Design addition] `scan_package(src_root=SRC_ROOT)` takes an optional root** so the canary test can scan a temp copy. Default behavior is the one the plan specifies.

No genuine violation was found in code from earlier plans; no production code under `src/` was changed.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-01-16 (import ban over the whole tree, in every pytest run), T-01-17 (planted leak flagged in a test plus the CI canary), T-01-18 (RNG bypass ban) and T-01-20 (canary file removed on both branches; verified absent after the local rehearsal) are implemented. T-01-19 (determined bypass via getattr/exec) is accepted and documented in DEC-002.

## Next Phase Readiness

Plan 01-07 can reuse `scan_package` and `POLICY` in the combined meta-test and add the future-scramble half; its door modules (`_snapshot`, `results`, `out_of_sample`) are already in the policy. The literal CI canary step has not run on GitHub yet (nothing pushed in this plan); it is to be observed green in the plan 01-11 push.

## Self-Check: PASSED

- Files exist: tests/guards/{__init__,import_scan,test_import_ban}.py, tests/fixtures/{__init__,leaky_consumer}.py, DECISIONS.md, tests/test_decisions_log.py, modified .github/workflows/ci.yml.
- Commits `ebb666e` and `aaca770` exist on main.
- Full suite 158 passed; ruff, ruff format --check, mypy strict clean; `src/f1si/_canary.py` absent.
