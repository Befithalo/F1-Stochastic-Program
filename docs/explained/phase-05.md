# Phase 5 explained: Longstaff-Schwartz strategy and live replay

This page explains how the strategy ranks pit timing from the information visible at a replay cutoff. It follows the conditional-mean Longstaff-Schwartz method and the current-cutoff CVaR-aware ranking agreed for Phase 5. It does not claim that the recommendation is calibrated on real races; the 10-race walk-forward evaluation belongs to Phase 6.

## What was built and why

**A stopping policy, not a list of fixed plans.** From the current `RaceState`, `LongstaffSchwartzPolicy` simulates comparable race paths. At each future decision time, it works backward: least-squares regression estimates the conditional mean of the later policy's realized finishing position from that path's state, then each path compares continuing with the result of stopping on that path. Finishing position is a cost, so the lower value wins. The regression basis is an intercept plus scaled position, gap, tire age, remaining distance, stops completed and safety-car state. If there are too few paths for that design or the design is rank-deficient, the code falls back to the intercept-only mean. This basis and fallback are labeled **[ASSUMED]** in DEC-096; they are practical starting choices to test in Phase 6.

**Risk affects the live ranking.** The conditional-mean continuation rule stays separate from the current-cutoff score. At the current cutoff, each option reports mean finishing position, standard-deviation spread, worst-decile CVaR10 and a score:

```text
score = (1 - risk_aversion) * mean_finish + risk_aversion * CVaR10
```

Higher finishing-position numbers are worse, so the worst tail is sorted from highest to lowest and fractional weight is used at the 10% boundary. Lower scores rank first. The default `risk_aversion` is 0.5; zero uses only the mean and one uses only the worst-decile CVaR. This is a CVaR-aware current-cutoff ranking; it does not make this dynamically CVaR-optimal. The risk blend is not put back into the regression.

**Actions share the same simulated luck.** The candidate set includes a stop now, stops delayed by up to five laps when legal, and staying out. The choices are run from common simulator paths so traffic and safety-car variation are comparable. Tied scores use a fixed tie order, recorded as an assumption in DEC-099. The reason is deterministic and reports the winning action and its score, mean and CVaR10; it does not invent an undercut, tire cliff or future safety-car story.

**Each replay row is rebuilt as of its lap.** `f1si replay` with no `--lap` emits rows over the race; `--lap N` uses the same builder and formatter for one cutoff. At each cutoff, the CLI makes a fresh snapshot, pace fit, wear-filter output and `RaceState`; the policy receives the state, not the data accessor. A row can be unavailable when the visible data cannot identify a dry-compound pace fit. The full replay does not fill such a row using later laps.

## How the pieces connect

```text
race slug and driver code
          |
          v
CLI replay cutoff N (or each cutoff in order)
          |
fresh AsOfAccessor snapshot -> pace fit -> wear filter -> RaceState
          |
          v
LongstaffSchwartzPolicy: same seeded path checkpoints for each action
          |
backward conditional-mean regression -> pathwise stop / continue values
          |
current-cutoff mean + spread + CVaR10 -> risk blend -> ranked options and reason
          |
full replay row or the selected --lap N row
```

Race distance is read as public metadata (D-21). All observation-derived inputs for a recommendation are reconstructed at that row's cutoff. The future-scramble guard changes future observations and checks that a supported cutoff's output remains the same.

## File-by-file tour

Paths are relative to the repository root. Package marker `__init__.py` files are omitted.

### Strategy and replay

- `src/f1si/strategy/longstaff.py` contains the immutable analysis/result rows, exact fractional-boundary CVaR10, risk validation, conditional-mean least-squares fit and backward pathwise stop/continue recursion. It builds same-seed pit and stay-out candidates, scores them at the current cutoff and generates the score-only reason.
- `src/f1si/sim/numpy_backend.py` owns the private `_PathCheckpoint` and `_branch_paths` seam. It captures enough interaction state to continue the same simulated race from a decision time without changing the public simulation-result contract.
- `src/f1si/cli.py` registers `replay`, validates catalog-backed race and driver inputs and rebuilds every cutoff through the shared selected/full replay builder. Unsupported cutoff-local pace fits are printed as unavailable.

### Tests and guards

- `tests/strategy/test_longstaff.py` covers conditional-mean recovery, pathwise decisions, rank fallback, common scenarios, CVaR orientation and boundary mass, risk endpoints, deterministic reasons, legal actions and policy behavior.
- `tests/test_cli_replay.py` covers accepted defaults and help, invalid-input refusals, all-cutoff ordering, unavailable early rows and exact selected/full row equivalence.
- `tests/conformance/registry.py` registers the Longstaff policy; `tests/conformance/test_suites.py` runs it through the shared `StrategyPolicy` contract.
- `tests/guards/consumers.py` registers the replay cutoff builder as an as-of consumer.
- `tests/guards/scramble.py` preserves public race-distance metadata while scrambling observations and ensuring synthetic future rows do not alter that distance.
- `tests/guards/test_future_scramble.py` checks supported replay output after future observations are changed; `tests/guards/test_consumer_registry.py` checks that guarded consumers are registered.
- `tests/test_docs.py` checks the five headings, answered questions, file tour and README replay instructions. `tests/test_decisions_log.py` checks consecutive decision IDs, required labels and references.

### Decisions and user guide

- `DECISIONS.md` records DEC-096 through DEC-100: the assumed regression basis and fallback, current-cutoff risk score, same-path simulator branching, tie order and reason, and the as-of replay/input rules.
- `README.md` gives the full replay and selected-cutoff commands, accepted inputs and defaults, and links to this explainer.
- `docs/explained/phase-05.md` is this owner-facing method, limitations and file-tour page.

## Interview questions

### Q1. What makes this Longstaff-Schwartz instead of just sorting pit plans?

At each future stopping time the code regresses the later policy's realized finish cost on simulated path state, then makes a stop-or-continue choice for each path. Ranking a handful of fixed schedules would not learn that backward conditional-mean stopping rule.

### Q2. Where does CVaR affect the calculation?

CVaR10 is used with the mean to rank the option distributions at the current cutoff. The backward regression still estimates conditional mean finishing position, so the method is not a dynamic CVaR optimizer.

### Q3. Why can an early replay row say unavailable?

The row is built from only its visible laps. If those laps do not identify the dry-compound pace fit required by the simulator, the CLI reports that limit instead of borrowing the later race fit.

### Q4. What does the risk setting do?

`--risk-aversion` ranges from 0 to 1 and defaults to 0.5. Zero ranks by mean finish, one ranks by CVaR10, and values between them blend the two; `--risk` remains a shorter alias.

### Q5. What still needs real-race evidence?

The assumed basis and tie order need walk-forward measurement. Phase 6 also measures how well the calls perform across ten races and revisits the Phase 4 fit-prior double-counting question; Phase 5 makes no calibration claim from one replay.

## Good to know

- **Replay commands.** `uv run f1si replay bahrain-2023 --driver ALO` shows all cutoffs. `uv run f1si replay bahrain-2023 --driver ALO --lap 20` selects one cutoff. `--lap N` is an integer from 0 to one less than the race lap count; omitting it emits every cutoff. A race slug comes from the local catalog, and the three-letter driver code must belong to that race.
- **Sample count and risk.** `--n N` requires a positive integer and defaults to 50,000. `--risk-aversion R` (alias `--risk R`) must be finite in `[0, 1]` and defaults to 0.5. Larger scores are worse; the first row is the lowest blended score.
- **Model limits.** The pace model uses linear tire wear and has hidden fuel and tire state; the simulator does not model tire cliffs, lapping, retirements, VSCs or red flags. Rivals follow the simulator's current plan rules. These are model limits, not evidence about actual team decisions.
- **A carried measurement question.** DEC-091 records that a field-fit wear prior can include a driver's current-stint laps, which are then reused in that driver's filter update. That possible double-counting is documented but not measured or changed in Phase 5; Phase 6 is the planned measurement point.
- **Real Bahrain smoke.** The authorized local Python 3.12 runtime and the Bahrain cache are available. The full and selected-cutoff smoke commands and their observed result are recorded separately in the Plan 05-03 execution summary; no real-race performance metrics are claimed here.
- **Where decisions live.** DEC-096 to DEC-100 in `DECISIONS.md` record the conditional-mean regression and its assumptions, exact CVaR10 ranking, shared branch draws, action boundaries, tie order, and replay validation.
- **What comes next.** Phase 6 adds the ten-race walk-forward backtest and the one-page view; Phase 7 and Phase 8 own the Bayesian pace and Markov regime upgrades.
