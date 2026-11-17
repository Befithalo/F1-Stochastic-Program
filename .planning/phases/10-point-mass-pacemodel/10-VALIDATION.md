---
phase: "10"
slug: "point-mass-pacemodel"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-17"
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + Hypothesis |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/pace/test_point_mass.py tests/pace/test_point_mass_recovery.py -q` |
| **Full suite command** | `uv run pytest --cov=f1si --cov-report=term` |
| **Estimated runtime** | Target under 60 seconds for focused point-mass tests; full-suite runtime is CI measured. |

## Sampling Rate

- **After every task commit:** Run the focused tests listed in the task's verification.
- **After every plan wave:** Run `uv run pytest tests/pace tests/conformance -q`.
- **Before phase closeout:** Full Ubuntu and Windows CI suites must pass.
- **Max feedback latency:** 60 seconds for focused tests.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-T01 | 01 | 1 | PHY-01 | — | Invalid units, non-finite values, and missing required geometry are rejected. | unit | `uv run pytest tests/pace/test_point_mass.py -q` | ❌ W0 | ⬜ pending |
| 10-01-T02 | 01 | 1 | PHY-01 | — | Prediction preserves the interface, shape, determinism, and immutable cutoff-scoped inputs. | conformance | `uv run pytest tests/pace/test_point_mass.py tests/conformance/test_protocols.py -q` | ❌ W0 | ⬜ pending |
| 10-02-T01 | 02 | 2 | PHY-02 | — | Recovery claims cover only identifiable effective parameters from independently generated synthetic trajectories. | synthetic recovery | `uv run pytest tests/pace/test_point_mass_recovery.py -q` | ❌ W0 | ⬜ pending |
| 10-02-T02 | 02 | 2 | PHY-01, PHY-02 | — | Solver convergence, force/speed bounds, and independent parameter/track sensitivity are reproducible and cutoff-safe. | unit/property | `uv run pytest tests/pace/test_point_mass.py tests/pace/test_point_mass_recovery.py -q` | ❌ W0 | ⬜ pending |
| 10-03-T01 | 03 | 3 | PHY-01, PHY-02 | — | The phase report records solver limits, identifiability, fixed M1 baseline, and verification evidence without opening locked targets. | integration | `uv run pytest tests/pace -q` | ❌ W0 | ⬜ pending |

## Wave 0 Requirements

- [ ] `tests/pace/test_point_mass.py` — behavior and physical invariant coverage for PHY-01/PHY-02.
- [ ] `tests/pace/test_point_mass_recovery.py` — independent synthetic generator and known-identifiable-parameter recovery for PHY-02.
- [ ] Existing `tests/conformance/test_protocols.py` — reuse shared `PaceModel` conformance.

## Manual-Only Verifications

All phase behaviors have automated verification. Human review is limited to confirming that model limitations and the fixed M1 baseline are stated clearly in the phase report.

## Validation Sign-Off

- [ ] All final plan tasks have automated verification or Wave 0 dependencies.
- [ ] Sampling continuity: no three consecutive tasks without automated verification.
- [ ] Wave 0 covers all new point-mass test files.
- [ ] No watch-mode flags.
- [ ] Focused feedback latency stays under 60 seconds.
- [ ] `nyquist_compliant: true` set only after the final task/test map is validated.

**Approval:** pending planning and execution.
