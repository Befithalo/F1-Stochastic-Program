# Phase 5: Longstaff-Schwartz Strategy & Live Replay - Discussion Log

> **Audit trail only.** Decisions are captured in 05-CONTEXT.md; this log records the options considered.

**Date:** 2026-11-13
**Phase:** 5-longstaff-schwartz-strategy-live-replay
**Areas discussed:** Strategy ranking and risk setting, Replay workflow and output, Recommendation reasons

**How the choices were made:** The owner repeatedly asked Claude to choose the recommended option for discussion questions, and asked for discussion, planning, and execution in one go in Phase 4. The Phase 5 recommendations below carry that preference forward. These are agent-recommended defaults for the owner to revise before planning or implementation.

---

## Strategy ranking and risk setting

| Option | Description | Selected |
|--------|-------------|----------|
| Mean/CVaR blend with a protect-points dial | Risk aversion runs from 0 (mean-focused / chase the win) to 1 (worst-decile CVaR / protect points); report both metrics. | ✓ |
| Show mean and CVaR without a combined ranking | Leaves the user to choose an option rather than changing the ranking with the risk setting. | |
| Rank only by CVaR | Does not provide the mean-focused end required by STR-03. | |

**Choice:** Mean/CVaR blend with a protect-points dial.
**Rationale:** Both measures use finishing-position units; exposing each alongside the score makes the risk trade-off understandable.

## Replay workflow and output

| Option | Description | Selected |
|--------|-------------|----------|
| CLI full replay plus a single-lap view | Default prints successive as-of recommendations; --lap N shows one cutoff. Reuses the Phase 4 replay and CLI table patterns. | ✓ |
| Interactive prompt that advances one lap at a time | Adds terminal state and prompt handling without an existing interactive CLI pattern. | |
| Single-lap snapshots only | Requires users to script every lap even though RPL-01 asks for a lap-by-lap replay. | |

**Choice:** CLI full replay plus a single-lap view.
**Rationale:** It supports a complete replay and focused inspection while keeping every cutoff explicit and reproducible.

## Recommendation reasons

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic sentence from as-of inputs and option scores | Names only an evidenced cause; otherwise summarizes why the scored action wins. | ✓ |
| Free-form generated narrative | Can imply causes the model does not observe and is harder to reproduce. | |
| Generic reason on every lap | Avoids unsupported claims but does not explain the model's different calls. | |

**Choice:** Deterministic sentence from as-of inputs and option scores.
**Rationale:** The explanation stays tied to visible evidence and can be reproduced.

## the agent's Discretion

The owner delegated recommendations in prior GSD phases. The regression basis, CVaR estimation details, legality edge cases, output formatting, reason thresholds, and module boundaries remain implementation choices for planning.

## Deferred Ideas

Streamlit dashboard, multi-race backtest, Bayesian pace, Markov regimes, and nonlinear tire wear remain in their existing roadmap phases.
