# Phase 6 explained: ten-race evaluation and read-only view

Phase 6 checks the existing cutoff-safe strategy on a fixed sample of ten races from 2023–2025, compares probability forecasts with a simple grid baseline, compares recommendations with observed pit-stop behavior, and publishes a read-only Streamlit view. The measurements answer whether this MVP is promising enough to keep developing. They do not establish calibrated future performance or show that the platform outperforms race teams.

## What was built and why

**A calendar-fixed walk-forward sample.** The evaluation uses the first calendar rounds in each season, with four races from 2023, three from 2024, and three from 2025. Bahrain 2023 is the fixed reference race. The sample is `2023-01`, `2023-02`, `2023-03`, `2023-04`, `2024-01`, `2024-02`, `2024-03`, `2025-01`, `2025-02`, and `2025-03`. The selection does not depend on results or model performance, and 2026 stays out of the sample.

**Each prediction is made from its own cutoff.** For every eligible driver and cutoff, the backtester builds an as-of snapshot and uses only completed races that occurred earlier. Final classifications are opened only in the scoring layer after predictions are frozen. This keeps the prediction process separate from its answers. The fixed report contains 10,942 driver-cutoff observations. It averages observations within each race first, then gives each of the ten races equal weight.

**Probability scores have a past-only reference.** Podium and top-10 probabilities are scored with Brier loss against a grid-position baseline built only from earlier races. The baseline shrinks sparse grid-position rates toward five neutral pseudo-starts; for the first race it uses field-size neutral rates. The model and baseline use the same finite rows. Paired uncertainty resamples whole races, rather than treating drivers or laps from one race as independent races.

**Finishing intervals include discrete endpoints.** Each 90% simulated finishing-position interval uses inclusive empirical inverted-CDF P05/P95 endpoints from the same cutoff's simulated outcomes. The report counts only classified finishers for observed coverage because the simulator has no retirement model. Its coverage therefore has a classified-finisher denominator, not the larger probability-scoring denominator.

**Observed team calls are a comparison point.** Each observed stop is matched once to the latest recommendation strictly before the stop's in-lap. The report summarizes top-action agreement and signed and absolute stop-timing error with race-clustered intervals. It describes comparison with observed team behavior and makes no superiority claim.

**The tire check is a retrospective proxy.** The wear diagnostic compares the cutoff filter with a race-end pace reference after removing the evaluated driver's current stint. That remaining data are a retrospective proxy, not latent ground truth. The report also measures early-fit bias for estimates with at most eight clean laps and records how much of the same-cutoff, same-compound clean-lap evidence comes from the current stint. These observations inform the known overlap concern; they do not justify tuning the filter on the evaluation races.

## How the pieces connect

```text
pre-registered race and cutoff
              |
              v
as-of snapshot + strictly earlier race history
              |
              v
cutoff-safe replay and seeded strategy simulations
              |
              +---- freeze probabilities and finish endpoints
              |
              +---- scoring-only access to final classifications
              |          |
              |          +-- Brier scores vs past-only grid baseline
              |          +-- classified-finisher interval coverage
              |
              +---- match one prior recommendation to each observed stop
              |
              +---- compare cutoff wear bands with leave-stint-out proxy
                         |
                         v
          equal-race summaries and whole-race bootstrap intervals
                         |
                         v
          JSON report, README evidence, and read-only Streamlit view
```

The published report uses 1,000 simulations per prediction, base seed 0, and risk aversion 0.5. Brier and finishing-interval summaries use 95% paired or race-cluster percentile-bootstrap intervals as appropriate; the strategy and wear sections retain their own denominators and definitions. The exact values and interval bounds are in [`reports/backtest/phase-06.json`](../../reports/backtest/phase-06.json), and the reader-facing summary is in the [README](../../README.md#phase-6-walk-forward-results).

## File-by-file tour

Paths are relative to the repository root. Package marker `__init__.py` files are omitted.

### Evaluation and view

- `src/f1si/backtest/walk_forward.py` fixes the ten-race sample, creates cutoff-local predictions, and keeps earlier-race history separate from current-race observations.
- `src/f1si/backtest/scoring.py` opens final classifications only after prediction generation and assembles the fixed evaluation report.
- `src/f1si/backtest/metrics.py` calculates Brier scores, the past-only grid baseline, empirical finishing intervals, and equal-race cluster summaries.
- `src/f1si/backtest/strategy.py` pairs each observed pit stop with one strictly earlier recommendation and measures agreement and timing error.
- `src/f1si/backtest/wear_diagnostic.py` compares cutoff wear estimates with a leave-current-stint-out retrospective proxy without changing the filter.
- `src/f1si/app.py` presents the read-only single-page view using the shared cutoff-safe replay builder and selected-input controls.
- `src/f1si/cli.py` exposes the report-building command and the same replay construction used by the view.
- `reports/backtest/phase-06.json` stores the measured ten-race results, denominators, seeds, and uncertainty metadata.

### Tests and decisions

- `tests/backtest/test_walk_forward.py`, `tests/backtest/test_metrics.py`, `tests/backtest/test_strategy.py`, and `tests/backtest/test_wear_diagnostic.py` cover cutoff boundaries, scoring semantics, stop matching, and the proxy diagnostic.
- `tests/app/test_app.py` checks the read-only view's controls, defaults, rendering, and required output states.
- `tests/guards/consumers.py`, `tests/guards/test_future_scramble.py`, and `tests/guards/test_import_ban.py` protect the as-of boundary and result-access boundary.
- `tests/test_docs.py` guards report-linked public claims, assumptions, source credits, and this file tour. `tests/test_decisions_log.py` checks the logged method choices.
- `DECISIONS.md` records DEC-102 through DEC-104, including the fixed sample, scoring semantics, and interpretation of observed calls and the retrospective proxy.

## Interview questions

### Q1. Why report whole-race intervals?

Cutoffs and drivers within the same race share conditions and are not independent race experiments. Resampling whole races reflects that clustering and avoids making the interval artificially narrow by counting every lap as a separate race.

### Q2. Does a lower Brier score prove the strategy is better than teams?

No. The Brier comparison is a probability score against a past-only grid baseline on ten selected races. Team-call metrics separately describe how the recommendations compare with observed decisions. Neither result establishes superiority or future performance.

### Q3. Why does interval coverage use fewer rows than Brier scoring?

The probability score treats unclassified starters as negative outcomes for podium and top-10. Finishing-position coverage is defined only where a classified final position exists, so its denominator is 9,602 classified finishers rather than 10,942 driver-cutoff scoring observations.

### Q4. Is the wear proxy the tire's true wear rate?

No. It is a retrospective reference fit from race-end laps after removing that driver's evaluated stint. It is useful for a diagnostic comparison, but it is not latent ground truth and the filter was not tuned to improve it.

## Good to know

- **Hidden state.** Fuel load and tire wear are hidden variables. The system infers them from available observations and assumptions; neither is directly measured as a complete ground-truth state.
- **Simulator boundaries.** Tire wear is simplified as linear. The current regime view uses the existing historical safety-car probability, not Phase 8's Markov regime model. The simulator does not model retirements, tire cliffs, lapping, VSCs, or red flags.
- **Calibration.** Prior-driven and sparse-fallback estimates are uncalibrated. Ten races are a small MVP evaluation, and the measured coverage is not a guarantee for future races.
- **Source and terms.** The current loader uses OpenF1 and Jolpica; FastF1 was the original planned source, not the current loader. Follow source terms, retain attribution, and do not commit or republish raw data.
- **Open details.** The README publishes the numeric results and denominators. The report JSON is the source of those values; DEC-102 through DEC-104 in `DECISIONS.md` explain why the evaluation uses these rules.
