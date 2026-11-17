# Phase 8: Markov Regimes and Full Backtest

## What was built and why

Phase 8 adds a five-state track-regime model to replay and simulation. The labels are green, virtual safety car, safety car, red flag, and wet. It estimates transitions only from earlier completed in-sample races, with race boundaries preserved and a Dirichlet(1) prior.

The phase has a committed 2023–2025 in-sample report. Its separate 2026 holdout report is pending because the locked evaluation needs an authoritative ex-ante scheduled distance that is unavailable in the local metadata for a locked event. No holdout score or holdout metric has been produced. The phase remains incomplete.

## How the pieces connect

The regime labeler uses only track-control and weather rows visible at the requested cutoff. Each race contributes its own observed transition sequence; separate races are never joined into a synthetic transition. The simulator carries the transition matrix and regime-specific pit-cost vector in race state. Green pit loss is measured, while VSC and safety-car discounts remain explicit assumptions.

The holdout evaluator freezes predictions before the protected results accessor is called. In this execution the required schedule preflight stopped before result access. Since a search snippet and adjacent FIA media-kit classifications incidentally displayed outcome information during schedule research, any future evaluation must be described as pre-registered but retrospectively unblinded.

## File-by-file tour

- `src/f1si/regime/markov.py` labels visible control/weather and estimates race-local transition probabilities.
- `src/f1si/state.py` stores the regime, transition matrix, and regime pit-loss values used by simulation.
- `src/f1si/sim/kernel.py` and `src/f1si/sim/numpy_backend.py` apply the selected regime while simulating a race.
- `src/f1si/evaluation/holdout.py` enforces the locked 2026 holdout protocol, freezes predictions before results, and verifies an existing report without opening data accessors.
- `reports/backtest/phase-08.json` stores the completed in-sample report; no Phase 8 holdout report exists.
- `.planning/phases/08-markov-regimes-full-backtest/08-VALIDATION.md` records completed checks and the pending holdout blocker.
- `DECISIONS.md` records the frozen protocol, assumptions, and the no-guessing decision for unavailable schedule metadata.

## Interview questions

### Q1. What does the Markov model add?

It lets the simulator represent transitions among track-control and weather regimes using only completed earlier races. It does not infer hidden conditions between observations.

### Q2. Are the regime pit costs calibrated?

Only green pit loss is measured as the baseline. The VSC and safety-car multipliers are assumptions; red and wet use the green baseline until defensible measurements exist.

### Q3. Why is the 2026 holdout pending?

The locked evaluation requires a scheduled horizon for every registered event. Its preflight stopped because scheduled race distance was unavailable, including for the locked Sepang event. No horizon was guessed from observed laps, and no holdout report or metrics were produced.

### Q4. Is any eventual holdout evaluation blind?

No. External schedule research incidentally displayed outcome information. The model and lock were already fixed, and no displayed values were used for tuning, code, or lock settings, but any eventual evaluation must be called pre-registered and retrospectively unblinded.

## Good to know

- The Phase 8 holdout is not complete; do not treat the in-sample report as a holdout result.
- No 2026 outcomes were accessed during the failed holdout score preflight.
- The unavailable schedule horizon must come from authoritative ex-ante schedule metadata. It must not be inferred from observed 2026 laps.
- The project makes no Phase 8 holdout performance claim while the report is absent.
