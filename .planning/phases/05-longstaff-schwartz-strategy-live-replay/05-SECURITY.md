---
phase: "05"
slug: "longstaff-schwartz-strategy-live-replay"
status: verified
threats_open: 0
asvs_level: 1
created: "2026-11-13"
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| CLI arguments to replay and policy | Race, driver, lap, risk, seed, and simulation count are user-controlled. | Identifiers and numeric inputs |
| Replay driver to race data | The driver obtains race data through the as-of accessor and passes cutoff-built state to the strategy. | Cutoff-visible snapshots and fitted state |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-05-01 | Tampering | Risk and replay bounds | medium | mitigate | Validate finite risk in [0,1], positive sample count, supported lap range, and race/driver catalog allowlists before state construction or simulation; covered by strategy and CLI tests. | closed |
| T-05-03 | Tampering | CLI race/driver text | high | mitigate | Resolve identifiers through the existing catalog and entrant data; no shell command is constructed from CLI text; refusal paths and replay access are tested. | closed |
| T-05-SC | Tampering | Dependency installation | low | accept | No package installation is planned. Any added package requires the project legitimacy audit and human gate before installation. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` count toward `threats_open`.*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-05-01 | T-05-SC | This phase adds no dependency; future additions remain behind the package legitimacy audit and human approval gate. | Owner-approved plan disposition | 2026-11-13 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-13 | 3 | 3 | 0 | Codex |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-13
