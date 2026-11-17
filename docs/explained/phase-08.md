# Phase 8: Markov Regimes and Full Backtest

## What was built and why

Phase 8 adds a five-state track-regime model to replay and simulation. The labels are green, virtual safety car, safety car, red flag, and wet. It estimates transitions only from earlier completed in-sample races, with race boundaries preserved and a Dirichlet(1) prior.

The phase has a committed 2023–2025 in-sample report and a separate locked 2026 holdout report. The in-sample model's mean podium Brier is 0.05546 versus the 0.07369 grid baseline; top-10 Brier is 0.14465 versus 0.16909; 90% finish-interval coverage is 16,508/20,001 (82.26%). On 695 matched stops, signed timing error is +1.174 laps and top-action agreement is 17.22%.

The 2026 holdout has nine races and 11,282 Brier observations. Podium Brier is 0.06639, top-10 Brier is 0.14948, and 90% finish-interval coverage is 6,947/9,513 classified finishers (73.03%). Among 267 matched stops, signed timing error is +2.064 laps and agreement with observed team calls is 1.87%. These results are not directly compared with the 2023–2025 sample, and they do not establish calibration or superiority over teams.

## How the pieces connect

The regime labeler uses only track-control and weather rows visible at the requested cutoff. Each race contributes its own observed transition sequence; separate races are never joined into a synthetic transition. The simulator carries the transition matrix and regime-specific pit-cost vector in race state. Green pit loss is measured, while VSC and safety-car discounts remain explicit assumptions.

The holdout evaluator freezes all predictions before the protected results accessor is called. Its schedule contract now uses locked ex-ante distances and rejects conflicts with local schedule metadata. One earlier preflight attempt stopped before result access; the one successful score produced the locked report. Since search output and adjacent FIA media-kit classifications incidentally displayed outcome information during schedule research, the evaluation is **pre-registered but retrospectively unblinded**, not blind. No displayed result values were used for modeling or tuning, and the report must not be rescored.

## File-by-file tour

- `src/f1si/regime/markov.py` labels visible control/weather and estimates race-local transition probabilities.
- `src/f1si/state.py` stores the regime, transition matrix, and regime pit-loss values used by simulation.
- `src/f1si/sim/kernel.py` and `src/f1si/sim/numpy_backend.py` apply the selected regime while simulating a race.
- `src/f1si/evaluation/holdout.py` enforces the locked 2026 holdout protocol, freezes predictions before results, and verifies an existing report without opening data accessors.
- `reports/backtest/phase-08.json` stores the separate 20-race in-sample report; `reports/backtest/phase-08-holdout.json` stores the nine-race 2026 holdout with frozen prediction rows.
- `.planning/phases/08-markov-regimes-full-backtest/08-VALIDATION.md` records the two report verifications, local checks, and exact-head Ubuntu/Windows CI.
- `DECISIONS.md` records the frozen protocols, assumptions, schedule provenance, one-score boundary, retrospective-unblinding limitation, and report-verifier extension.

## Interview questions

### Q1. What does the Markov model add?

It lets the simulator represent transitions among track-control and weather regimes using only completed earlier races. It does not infer hidden conditions between observations.

### Q2. Are the regime pit costs calibrated?

Only green pit loss is measured as the baseline. The VSC and safety-car multipliers are assumptions; red and wet use the green baseline until defensible measurements exist.

### Q3. What does the 2026 holdout show?

The nine-race report records 0.06639 podium Brier, 0.14948 top-10 Brier, 73.03% 90% interval coverage, +2.064 laps signed stop-timing error, and 1.87% team-call agreement. It is pre-registered but retrospectively unblinded and is not a claim that the model is calibrated or better than teams.

### Q4. Why is the holdout called retrospectively unblinded?

Schedule research incidentally displayed outcome information before the score. No displayed values were used for the lock, code, metrics, or tuning. Therefore the result is not blind, even though the sample and scoring contract were registered first.

## Good to know

- The 2026 holdout was scored once after an earlier preflight-only failure; do not tune or rescore it.
- The report is verified without opening data access or recomputing predictions.
- The reported holdout has no grid-baseline comparison and does not establish calibration or superiority over teams.
- Preserve its pre-registered but retrospectively unblinded label wherever these figures are published.
