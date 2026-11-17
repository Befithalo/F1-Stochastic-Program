# Phase 8: Markov Regimes & Full Backtest - Discussion Log

> Audit trail for human review. The recommended defaults were selected autonomously under the owner's instruction to proceed without requiring input.

**Date:** 2026-11-16
**Phase:** 8-Markov Regimes & Full Backtest
**Areas discussed:** Regime labeling, transition fit boundary, regime pit-loss values, backtest and holdout protocol

---

## Regime labeling

| Option | Description | Selected |
|--------|-------------|----------|
| Track-control priority with rainfall as wet when no incident is active | Red > SC > VSC > wet > green; yellow maps to green in the five-state model. | ✓ |
| Infer wetness from tyre choice or preserve overlapping regime probabilities | Requires using a proxy or a non-exclusive state definition. | |

**Choice:** Recommended default auto-selected under the owner's authorization.
**Notes:** The cutoff snapshot supplies the latest visible weather and track-control observations; no future weather or lap is used.

---

## Transition fit boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Earlier completed in-sample races only, with Dirichlet(1) smoothing | The current cutoff determines the observed starting state; no 2026 race updates the matrix. | ✓ |
| Update from each current race's visible prefix | Causal but adds a per-cutoff transition refit and can adapt to the evaluated race. | |

**Choice:** Recommended default auto-selected under the owner's authorization.
**Notes:** A synthetic sequence with a known transition matrix will verify recovery.

---

## Regime pit-loss values

| Option | Description | Selected |
|--------|-------------|----------|
| Measured green baseline plus documented regime assumptions | VSC 0.75× and SC 0.5× green; wet and red use green until comparable evidence supports other values. | ✓ |
| Estimate an empirical cost distribution for every regime | Existing pit-loss measurement excludes slow-status stops, and red/wet observations may be sparse or incomparable. | |

**Choice:** Recommended default auto-selected under the owner's authorization.
**Notes:** Regime discounts will be identified as assumptions, not empirical measurements.

---

## Backtest and holdout protocol

| Option | Description | Selected |
|--------|-------------|----------|
| Lock 20 in-sample calendar races and a second-half 2026 holdout | In-sample split is 7/7/6 across 2023/2024/2025; holdout is 2026 rounds 9–17. Preserve Phase 6 scoring settings and report both groups separately. | ✓ |
| Mix 2026 into the 20-race in-sample set | Would consume holdout data during training and blur in-sample and out-of-sample evidence. | |

**Choice:** Recommended default auto-selected under the owner's authorization.
**Notes:** Keep 1,000 simulations, seed 0, risk 0.5, existing paired-row and metric definitions, and linear pace as default because Phase 7 PAC-06 did not pass.

---

## the agent's Discretion

- Markov matrix representation, fitting implementation and synthetic recovery tolerance.
- Narrow internal changes and runtime optimizations that preserve the frozen score contract.
- No UI/UX modifications.

## Deferred Ideas

Broader physics or machine-learning models, live data, deployment, external odds, and dashboard changes remain out of scope.
