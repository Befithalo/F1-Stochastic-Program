---
phase: "09"
slug: "data-and-geometry-readiness"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-17"
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + Hypothesis |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/data/test_physics_input.py tests/data/test_asof.py -q` |
| **Full suite command** | `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest --cov=f1si --cov-report=term` |
| **Estimated runtime** | Under 60 minutes in CI; exact local runtime to be recorded by the executor |

---

## Sampling Rate

- **After every task commit:** Run the narrowest relevant pytest command below.
- **After every plan wave:** Run the full suite command.
- **Before phase closeout:** Require the repository CI matrix to pass on `ubuntu-latest` and `windows-latest`.
- **Max feedback latency:** The CI job timeout is 60 minutes; local targeted test runs should remain under 120 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | DAT-01 | T-09-01 | Exclude rows after cutoff; preserve source timestamp and race-clock mapping | unit + integration | `uv run pytest tests/data/test_physics_input.py tests/data/test_asof.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | GEO-01 | T-09-02 | Reject missing, malformed, or digest-mismatched geometry before model use | unit + integration | `uv run pytest tests/geometry/test_profile.py -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | PAR-01 | T-09-03 | Keep fitted composites distinct from hidden assumptions and serialize evidence, bounds, uncertainty, and sensitivity status | unit + report contract | `uv run pytest tests/parameters/test_register.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/data/test_physics_input.py` — cutoff filtering, UTC source-time preservation, coverage report, and cached-lap fallback.
- [ ] `tests/geometry/test_profile.py` — manifest, digest, units/transform, quality validation, and fail-closed behavior.
- [ ] `tests/parameters/test_register.py` — fitted-versus-assumed classification, evidence, bounds, uncertainty, and sensitivity fields.
- [ ] Assign the placeholder task/plan/wave IDs above once the planner emits the executable plan set.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| File-level redistribution and attribution review for the chosen Sakhir geometry asset | GEO-01 | License metadata and upstream data obligations require source review and cannot be established by a digest test | Record exact asset URL/revision, asset-level terms, attribution, and the bundle-or-external decision in the geometry manifest and `DECISIONS.md`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verification or Wave 0 dependencies.
- [ ] Sampling continuity: no three consecutive tasks without automated verification.
- [ ] Wave 0 covers all missing test references.
- [ ] No watch-mode flags.
- [ ] Feedback latency is within the limits above.
- [ ] Set `nyquist_compliant: true` only after Wave 0 and the phase test map are complete.

**Approval:** pending
