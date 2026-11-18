# Phase 09 Review Disposition

Review: [09-REVIEW.md](09-REVIEW.md)  
Implementation decision: [DEC-144](../../../DECISIONS.md#dec-144--quarantine-optional-telemetry-and-fail-closed-on-incomplete-evidence)

| Finding | Severity | Disposition | Evidence |
|---------|----------|-------------|----------|
| CR-01 | Blocker | Fixed | Optional OpenF1 channel fetch/normalization is isolated and quarantined; race completeness no longer requires weather. Covered by `tests/data/test_openf1.py` missing, malformed, and transport-failure cases. |
| WR-01 | Warning | Fixed | Probe usability counts only parseable timestamps in the inclusive 0–600 second window and emits per-endpoint status/reason. Covered by `tests/data/test_coverage_audit.py::test_probe_counts_only_rows_inside_the_requested_clock_window`. |
| WR-02 | Warning | Fixed | Probe requires explicit race/year/country identity and a positive numeric session key before requesting lap or telemetry rows. Covered by the identity and session-key tests in `tests/data/test_coverage_audit.py`. |
| WR-03 | Warning | Fixed | Endpoint partial results and failure reasons are retained in JSON and rendered in the closeout for all overall probe statuses. Covered by `tests/data/test_coverage_audit.py::test_probe_keeps_partial_endpoint_evidence_when_later_request_fails` and `tests/parameters/test_register.py::test_closeout_renders_partial_probe_endpoint_evidence_and_reasons`. |
| WR-04 | Warning | Fixed | The geometry loader requires repository, rights conclusion, validation version, passed status, and outcome. Covered by manifest evidence tests in `tests/geometry/test_profile.py`. |
| WR-05 | Warning | Fixed | Missing transform rotation is converted to `GeometryProfileError`. Covered by `tests/geometry/test_profile.py::test_missing_transform_rotation_uses_public_profile_error`. |
| WR-06 | Warning | Fixed | The probe pads OpenF1's strict `date>` / `date<` fetch range by one microsecond and retains the exact inclusive local race-clock filter. Covered by bounded-filter and exact-boundary rows in `tests/data/test_coverage_audit.py`. |
| WR-07 | Warning | Fixed | Optional segment and curvature quality values pass through `_number()` and raise `GeometryProfileError` when malformed. Covered by `tests/geometry/test_profile.py::test_manifest_rejects_nonnumeric_optional_quality_values`. |
| WR-08 | Warning | Fixed | Attribution must be a nonblank string before it is stored in the typed manifest. Covered by `tests/geometry/test_profile.py::test_manifest_requires_nonblank_string_attribution`. |

Final disposition: all eight warnings and the original blocker are fixed. The current standard code review is clean (0 blockers, 0 warnings). The focused Phase 9 implementation suite passed 108 tests before the final probe-bound refinement; the latest coverage-audit suite then passed 10 tests. The full suite passed 1,315 tests with 33 deselected in 33m31s on Windows/Python 3.12. Repository Ruff, formatting, and mypy checks passed. The Nyquist audit filled one catalog-count assertion gap, and the security audit closed all high-severity threats with the planned low package-installation risk accepted. Phase verifier and Ubuntu/Windows CI remain pending.
