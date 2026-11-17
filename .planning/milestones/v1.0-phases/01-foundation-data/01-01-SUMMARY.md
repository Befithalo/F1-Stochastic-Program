---
phase: 01-foundation-data
plan: 01
subsystem: infra
tags: [uv, uv_build, ruff, mypy, pytest, github-actions, pre-commit, python-3.12]

requires: []
provides:
  - uv-managed Python 3.12 package f1si (src layout, uv_build backend) with console script f1si
  - ruff, mypy strict and pytest configuration (network-marked tests excluded by default)
  - Two-OS CI gate (ubuntu-latest, windows-latest) using uv sync --locked
  - Pre-commit ruff hooks pinned to the same ruff version as the dev group
  - Repo hygiene (.gitignore, .gitattributes) and committed design docs (D-18)
  - uv 0.13.5 and CPython 3.12.15 installed on the owner's machine
affects: [01-02, 01-03, all later plans]

tech-stack:
  added: [numpy, pandas, duckdb, matplotlib, requests, requests-cache, pytest, hypothesis, ruff, mypy, pandas-stubs, types-requests, pre-commit, pytest-cov]
  patterns:
    - "src/ layout with uv_build; pins in pyproject.toml, lock file arrives in plan 01-02"
    - "pytest default addopts -m 'not network' so push CI never downloads data (D-10)"
    - "ruff NPY rules ban legacy np.random calls (FND-03)"

key-files:
  created:
    - pyproject.toml
    - .python-version
    - .gitignore
    - .gitattributes
    - .pre-commit-config.yaml
    - .github/workflows/ci.yml
    - README.md
    - src/f1si/__init__.py
    - src/f1si/__main__.py
    - src/f1si/cli.py
    - src/f1si/py.typed
    - tests/__init__.py
    - tests/test_smoke.py
    - "F1 Docs/BUILD_PLAN.md"
    - "F1 Docs/MASTER_PROMPT.md"
  modified: []

key-decisions:
  - "pandas stays below 3 so a future FastF1 source remains possible (DEC-012)"
  - "duckdb capped below 2 until 2.0.1 because 2.0 files are unreadable by 1.x (DEC-011)"
  - "ruff pinned exactly (==0.17.1) in pyproject.toml and pre-commit rev v0.17.1; bump both together (D-13)"
  - "CI runs synthetic data only, no artifact upload, permissions contents: read (D-09, T-01-02)"

patterns-established:
  - "Dependency legitimacy gate: package names verified against PyPI before the first install"
  - "Run gsd-sdk as env -u GSD_WORKSTREAM gsd-sdk ... (stale GSD_WORKSTREAM in the agent process)"

requirements-completed: [FND-01, FND-02]

duration: multi-session (two checkpoints)
completed: 2026-10-22
---

# Phase 1 Plan 01: Project Scaffold, CI and Toolchain Summary

**uv_build-based f1si package skeleton with ruff/mypy-strict/pytest config, a two-OS GitHub Actions gate, pre-commit ruff hooks, committed design docs, and uv 0.13.5 plus CPython 3.12.15 installed and verified.**

## Performance

- **Tasks:** 3 of 3 complete (1 auto, 1 human-verify checkpoint, 1 human-action checkpoint)
- **Files created:** 15 (commit 7e68820)

## Accomplishments

- Complete project definition written without running any tool: pyproject.toml, CI workflow, pre-commit config, README, minimal `f1si` package with `--version` CLI, and smoke tests.
- Design docs (`F1 Docs/BUILD_PLAN.md`, `F1 Docs/MASTER_PROMPT.md`) committed per D-18; `desktop.ini` is ignored at any depth and not tracked.
- Dependency list approved before any install, with PyPI evidence recorded below.
- uv and Python 3.12 installed and reachable; plan 01-02 can start with `uv lock` and `uv sync`.

## Task Commits

1. **Task 1: Scaffold, repo hygiene, CI config, F1 Docs** - `7e68820` (chore)
2. **Task 2: Dependency list approval** - no commit (checkpoint:human-verify, approved)
3. **Task 3: uv + Python 3.12 install** - no commit (checkpoint:human-action, done)

## Checkpoint Resolutions

**Task 2 (dependency approval): APPROVED.** The owner delegated the decision ("whatever you recommend, do that"). The orchestrator checked all 14 names in pyproject.toml, spelled exactly as written, against the PyPI JSON API on 2026-10-22. Each exists with a long release history and its official source repository:

| Package | Releases | Source repo |
|---------|----------|-------------|
| numpy | 152 | github.com/numpy/numpy |
| pandas | 119 | github.com/pandas-dev/pandas |
| duckdb | 153 | github.com/duckdb/duckdb-python |
| matplotlib | 143 | matplotlib/matplotlib |
| requests | 163 | github.com/psf/requests |
| requests-cache | 63 | requests-cache/requests-cache |
| pytest | 192 | pytest-dev/pytest |
| hypothesis | 1584 | HypothesisWorks/hypothesis |
| ruff | 428 | github.com/astral-sh/ruff |
| mypy | 142 | github.com/python/mypy |
| pandas-stubs | 141 | github.com/pandas-dev/pandas-stubs |
| types-requests | 143 | typeshed stub_uploader (python/typeshed) |
| pre-commit | 205 | pre-commit/pre-commit |
| pytest-cov | 54 | pytest-dev/pytest-cov |

This closes threat T-01-SC (slopcheck unavailable; manual verification substituted).

**Task 3 (uv + Python): DONE** by the orchestrator under the owner's delegation. uv 0.13.5 installed via the official installer to `C:\Users\befit\.local\bin`; `uv python install 3.12` installed CPython 3.12.15 at `C:\Users\befit\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe` (not WindowsApps). The user-level `GSD_WORKSTREAM` variable was removed (still present in the agent process, so `env -u GSD_WORKSTREAM` remains required). Re-verified by the executor: `uv --version` prints `uv 0.13.5`, `uv python find 3.12` prints the path above.

## Verification

- Task 1 automated check printed OK (F1 Docs tracked, no desktop.ini tracked, desktop.ini ignored at root and in `F1 Docs/`, CI/pyproject/pre-commit/.python-version assertions all pass).
- No `upload-artifact` in ci.yml.
- Task 3 automated check passes (see above).
- No uv or python command was run before Task 3 completed.

## Deviations from Plan

None - plan executed exactly as written. Two notes:

- Checkpoints 2 and 3 were resolved by the orchestrator under the owner's delegation instead of by the owner personally; the evidence for Task 2 is recorded above.
- The literal string "FastF1" appears once in pyproject.toml, inside the DEC-012 comment above the pandas pin that the plan itself requires. It is not a dependency; the acceptance intent (no fastf1 dependency) holds.

## Issues Encountered

None.

## Known Stubs

None. `cli.py` has no subcommands by design; plan 01-03 adds them.

## Threat Flags

None - no new network endpoints, auth paths or trust-boundary file access beyond the plan's threat model.

## Next Phase Readiness

Plan 01-02 can run `uv lock` and `uv sync` (it owns the first sync) to create `uv.lock`, install the pre-commit hook, and turn the CI gate green. CI uses `uv sync --locked`, so it will fail until `uv.lock` is committed by that plan; this is expected.

## Self-Check: PASSED

- Commit 7e68820 exists on main; all 15 listed files tracked.
- uv 0.13.5 and the CPython 3.12 path confirmed in this session.
