# Project Retrospective

## Milestone: v1.0 — M1 Core Stochastic Engine

**Shipped:** 2026-11-17
**Phases:** 8 | **Plans:** 55 | **Tasks:** 66

### What Was Built

- A cutoff-safe data pipeline, race simulator, tire filter, strategy policy, replay, backtests, Bayesian pace fit, and Markov race-regime model.
- Locked 10-race and 20-race evaluations with fixed simulation settings, reproducible seeds, and disclosed limitations.
- A plug-in `PaceModel` interface that gives M2 a stable seam for physics-backed pace.

### What Worked

- Synthetic recovery tests and future-scramble checks caught model and look-ahead failures before relying on real data.
- Locked samples, independent continuation paths, and explicit report verification kept model evaluation reproducible.
- Ubuntu and Windows CI both passed on the M1 implementation checkpoint.

### What Was Inefficient

- The phase-verification and closeout records drifted from later completed work. The final archive needed refreshed verification and explicit override documentation.
- Windows CI and the large replay reports take substantial time; progress is easier to track when each locked report and exact commit SHA are recorded promptly.

### Patterns Established

- Preserve scored reports and their lock files; never silently tune or rescore a failed gate.
- Fit and score continuation values on independent paths, split evaluation by race or stint, and keep all training cutoff-safe.
- Record assumptions and gaps in DECISIONS.md and publish baselines with denominators.

### Key Lessons

1. A model can pass synthetic recovery and still miss its real-data gate; carry the failed gate forward explicitly instead of presenting synthetic success as practical validation.
2. Keep holdout protocol state, outcome exposure, and final verification status in sync so historical reports remain interpretable.
3. Commit phase artifacts and closeout records as they are completed, then run CI on the final merged commit.

### Cost Observations

- Token, model-mix, and financial cost data were not tracked, so no cost estimate is available.
- The 20-race and 2026 results remain separate; the 2026 report was pre-registered but retrospectively unblinded.

---

## Cross-Milestone Trends

No later milestone has shipped yet.
