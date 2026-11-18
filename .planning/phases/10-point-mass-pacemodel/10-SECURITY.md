---
phase: "10"
slug: "point-mass-pacemodel"
status: verified
threats_open: 0
asvs_level: 1
register_authored_at_plan_time: true
created: "2026-11-18"
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Geometry, PhysicsInput, and parameter artifacts to solver | Validated immutable geometry and cutoff-scoped inputs are bound before prediction. | SI geometry arrays, prepared race snapshot, declared scenario values |
| Training PhysicsInput to fit | Eligible, cutoff-visible clean lap records enter one effective-scale fit. | Lap time, lap number, race identity, visibility timestamp |
| Fit diagnostics to PaceModel | Identifiable estimates and supported uncertainty enter deterministic predictions. | Effective scale, covariance, residual support diagnostics |
| Synthetic generator to production fit | Independent test-only targets exercise recovery without sharing production equations. | Seeded synthetic lap targets and fit metadata |
| Baseline evidence to closeout report | Fixed M1 values and Phase 10 diagnostics are copied into the report. | Locked aggregate metrics and scoped model evidence |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-10-01 | Tampering | GeometryProfile and PointMassParameters construction | medium | mitigate | Validate immutable artifact references, SI units, finite values, and inclusive bounds; boundary tests cover invalid inputs. | closed |
| T-10-02 | Information Disclosure | PhysicsInput and PaceModel construction | high | mitigate | Prediction consumes prepared immutable inputs and performs no cache/results access; cutoff and import-boundary tests enforce the boundary. | closed |
| T-10-03 | Denial of Service | Cyclic numerical solver | medium | mitigate | Cap envelope iterations at 1,000 and raise the named convergence error instead of returning partial output. | closed |
| T-10-04 | Information Disclosure | Effective-scale fit training boundary | high | mitigate | Restrict fitting to in-sample, cutoff-visible clean laps; exact-cutoff and future-row perturbation tests cover the gate. | closed |
| T-10-05 | Tampering | Fit report and parameter covariance | medium | mitigate | Validate support, rank, condition, covariance, units, and registered bounds before applying a fit. | closed |
| T-10-06 | Information Disclosure | Parameter and residual variance reporting | medium | mitigate | Keep parameter and residual uncertainty separate and suppress residual variance below the 30-lap, three-race support floor. | closed |
| T-10-07 | Tampering | Test-side truth generator and recovery fixture | medium | mitigate | Keep truth generation in tests, use independent equations, fixed seed, and recorded tolerance; recovery tests enforce the separation. | closed |
| T-10-08 | Tampering | Parameter and track sensitivity tests | low | mitigate | Perturb one input at a time and assert physical direction, bounds, and geometry immutability. | closed |
| T-10-09 | Information Disclosure | Phase 10 report | high | mitigate | Copy only fixed M1 aggregates and Phase 10 evidence; the report contract excludes the 2026 report and locked targets. | closed |
| T-10-SC (10-01/02/03) | Tampering | Package installation | high | mitigate | Consolidated repeated plan threat ID; dependency manifests and lock files are unchanged and no new package is used. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open.*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party).*

## Accepted Risks Log

No accepted risks.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-18 | 10 | 10 | 0 | Codex secure-phase L1 review |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-18
