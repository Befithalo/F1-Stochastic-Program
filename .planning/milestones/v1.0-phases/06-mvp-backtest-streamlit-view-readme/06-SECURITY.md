---
phase: "06"
slug: "mvp-backtest-streamlit-view-readme"
status: verified
threats_open: 0
asvs_level: 1
created: "2026-11-14"
---

# Phase 06 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Provider cache → cutoff predictions | Race data is read through cutoff-specific snapshots and history; future results remain behind the scoring boundary. | Race state, lap history, strategy inputs, and final results. |
| Frozen predictions → scoring | The registered sample is preflighted, predictions are frozen, then results are opened and scored. | Prediction rows and classified race outcomes. |
| Existing report → diagnostics-only update | The probability evidence must match the code-pinned Phase 06 digest before diagnostics run or the report is mutated. | User-selected JSON report, probability metrics, sample metadata, and diagnostics. |
| Cached replay → Streamlit display | Cache identity covers replay source code and selected state; stale output is suppressed and unavailable horizons are labeled. | Race, driver, cutoff, risk, seed, simulation count, data path, and model identity. |
| Measured report → public documentation | Published values are aggregate results checked against the report; raw provider records remain non-redistributable. | Aggregate metrics, denominators, uncertainty, attribution, and license notes. |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-06-01 | Information disclosure | `backtest/walk_forward.py` cutoff inputs | high | mitigate | Build each prediction from cutoff snapshots/history, freeze predictions before scoring, and cover consumers with future-scramble checks. | closed |
| T-06-02 | Tampering | Race IDs and cache completeness | medium | mitigate | Accept only the frozen ten catalog IDs, preflight every race, and fail closed when data is incomplete. | closed |
| T-06-03 | Tampering | `backtest/metrics.py` masks and aggregation | high | mitigate | Use a shared model/baseline mask, past-only priors, classified-finisher denominators, equal-race means, and deterministic paired race-cluster resampling. | closed |
| T-06-04 | Information disclosure | `backtest/scoring.py` results boundary | high | mitigate | Require all-ten preflight and a complete immutable prediction trace before results access or scoring. | closed |
| T-06-05 | Information disclosure | `backtest/strategy.py` event matcher | high | mitigate | Match only strictly earlier recommendations, count each observed event once, and test race-cluster uncertainty. | closed |
| T-06-06 | Tampering | `backtest/wear_diagnostic.py` reference and summary | medium | mitigate | Exclude the evaluated stint, preserve proxy labels and denominators, and keep the diagnostic read-only. | closed |
| T-06-07 | Information disclosure | Streamlit cached replay and state | high | mitigate | Include replay dependencies and selected state in cache identity, suppress stale output, and test state transitions. | closed |
| T-06-08 | Tampering | README and explainer claims | medium | mitigate | Source numeric claims from the finalized report and require exact report-linked documentation assertions. | closed |
| T-06-09 | Information disclosure | README and generated report | medium | mitigate | Publish aggregate metrics and method only, preserve attribution and license terms, and exclude raw race records. | closed |
| T-06-10 | Information disclosure | Backtest and diagnostic test contracts | high | mitigate | Cover prediction freeze, cache completeness, cutoff invariance, results ordering, pre-event alignment, proxy boundaries, and deterministic intervals. | closed |
| T-06-12 | Information disclosure | Streamlit app states | high | mitigate | Test read-only behavior, stale-output suppression, proxy/fallback labels, and empty, loading, error, partial, and layout states. | closed |
| T-06-13 | Tampering | Ranked option distribution summaries | medium | mitigate | Derive probabilities and interval endpoints from the same option draws and pin the behavior with controlled numeric tests. | closed |
| T-06-14 | Tampering | Phase 6 report publication/update | high | mitigate | Bind the complete probability payload, metadata, and carry-forward diagnostic to a code-owned SHA-256 digest; reject altered evidence before diagnostics or mutation; handle invalid JSON roots as concise errors. | closed |
| T-06-SC | Tampering | Streamlit dependency and app inputs | high | mitigate | Lock the reviewed Streamlit release and artifact hash, use `uv sync --locked` in CI, and validate catalog-backed controls. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above the configured threshold count toward `threats_open`.*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party).* 

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-14 | 14 | 13 | 1 | GSD security auditor (initial pass) |
| 2026-11-14 | 14 | 14 | 0 | GSD code review and focused security tests (T-06-14 follow-up) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-14
