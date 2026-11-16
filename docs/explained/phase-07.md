# Phase 7: Bayesian Pace Model

## What was built and why

Phase 7 adds a Bayesian alternative to the existing linear lap-time model. It estimates car/team, driver, event, regulation-era, compound, tyre-wear and fuel effects from clean laps that were available at a race cutoff. The fit uses PyMC full-rank ADVI for operational runs and reports uncertainty that the simulator can carry as shared race-state effects.

The model is deliberately explicit about its limits. Team is a proxy for car performance, and the available 2023–2025 training rows all belong to one regulation era. Synthetic known-truth tests establish recovery behavior; real held-out race scoring is handled separately after the sample is locked.

The locked 2025 real-data evaluation had 1,348 paired target predictions. Bayesian next-lap MAE was 0.5387 seconds versus 0.3640 seconds for the linear baseline, so Bayesian error was 48.0% higher and the PAC-06 15% improvement gate was not met. The evaluation stays published as scored; its race group and model settings were not changed or rescored.

## How the pieces connect

Earlier race history and the current cutoff snapshot are assembled into a training panel. The Bayesian fit builds centered effects over stable driver, team, event, era and compound categories. It returns a `PaceModel` implementation plus compact coefficient summaries. The state builder places shared pace and tyre uncertainty on each car so the simulator draws those quantities once per race rather than once per lap.

The fit rejects non-finite or unstable ADVI loss before sampling posterior draws. Synthetic tests compare recovered means with fixed truth and run a bounded, independent four-chain NUTS reference on the same model graph.

## File-by-file tour

- reports/pace/phase-07.json records the one-shot, pre-registered 2025 score, per-race denominators, fit diagnostics and model configuration.
- docs/phases/07-bayesian-pace-model.md summarizes the phase outcome and its measured limitation.

- `src/f1si/pace/training.py` joins eligible clean historical laps with cutoff-visible completed laps and assigns stable categories without reading race results.
- `src/f1si/pace/bayesian.py` builds the partially pooled PyMC hierarchy, gates ADVI on its loss trajectory, and exposes compact posterior means, intervals and uncertainty to the existing pace and state contracts.
- `src/f1si/backtest/pace_evaluation.py` runs the pre-registered 2025 next-lap holdout once, fits both models at cutoff snapshots, and reads target laps only after predictions are complete.
- `tests/pace/test_bayesian_training.py` checks panel eligibility, cutoff safety, era assignment and stable category handling.
- `tests/pace/test_bayesian_model.py` checks seeded fit behavior, shared pace-model conformance, sparse-group shrinkage and refusal when ADVI diagnostics fail.
- `tests/pace/test_bayesian_recovery.py` checks multi-era known-truth recovery, predictive coverage and the independent NUTS reference diagnostics.
- `tests/sim/test_bayesian_pace.py` checks that shared posterior pace and tyre uncertainty reach the existing race simulator.

## Interview questions

### Q1. Why use a Bayesian pace model?

Partial pooling lets sparse drivers, teams and compounds borrow information from the population while preserving distinct estimates when enough clean laps are available. The posterior also supplies uncertainty that can be propagated into race simulations.

### Q2. What prevents the fit from seeing future race information?

The panel builder receives earlier history and a race snapshot at the requested cutoff. It joins only eligible completed laps and never reads the eventual results table or laps after that cutoff.

### Q3. What does the ADVI convergence gate establish?

It rejects non-finite loss, insufficient iteration budgets and a loss trajectory that keeps moving across its trailing comparison window. Passing the gate does not prove exact posterior calibration, so synthetic recovery and an independent NUTS reference are checked separately.

### Q4. Did the real-data test show better next-lap predictions?

No. On the locked 2025 group, Bayesian MAE was 0.5387 seconds and linear MAE was 0.3640 seconds. The Bayesian result was 48.0% worse, so PAC-06 remains unmet despite passing synthetic recovery checks.

## Good to know

- The single locked score had 1,348 paired targets: 776 from 2025-02 and 572 from 2025-03. 2025-01 remained in the group and had no paired targets. The complete report is reports/pace/phase-07.json.
- All real rows in this evaluation come from the same regulation era. It cannot establish a real between-era pace effect.

- Operational ADVI has a 50,000-iteration minimum and records its final loss and trailing relative movement.
- The `PaceModel.predict` standard deviation represents residual lap noise. Team/driver and tyre-wear uncertainty is shared through the race state instead of being redrawn independently every lap.
- The real-data ERA limitation is reported: 2023–2025 rows cannot identify a between-era contrast. Synthetic recovery can check the era term, but it does not create missing real-era evidence.
