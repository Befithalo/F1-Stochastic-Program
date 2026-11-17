# F1 Stochastic Intelligence Platform (f1si)

A Python platform that recommends F1 pit strategy as a full probability distribution, recomputed every lap. It uses quant-finance methods (Monte Carlo pricing, optimal stopping, CVaR, regime switching, Kalman filtering) together with vehicle physics, ML/RL and production engineering. Pit timing is treated as an American option and strategy choice as a risk-adjusted portfolio decision.

## Status

Phases 1–5 provide the data layer, simulator, wear filter, and cutoff-safe strategy replay. Phase 6 adds a fixed-sample, ten-race walk-forward evaluation and a read-only Streamlit view. Phase 7 adds an optional Bayesian pace model and a locked real-data evaluation; the 15% real-data improvement gate was not met. Phase 8 adds Markov regime inputs, a 20-race in-sample backtest, and a separate nine-race 2026 holdout. The Bayesian pace result remains below its improvement gate, and the 2026 evaluation is pre-registered but retrospectively unblinded because outcome displays were incidentally exposed during schedule research. These results are measurements, not claims of calibrated performance or superiority over teams.

## What Phase 1 gives you

- One command, `uv run f1si load`, downloads every 2023-2025 Grand Prix (70 races) plus the locked 2026 races (17) from OpenF1 and Jolpica into a local DuckDB cache. It is safe to run again: finished races are skipped.
- `uv run f1si plot bahrain-2023` draws lap time by stint for a whole race, one panel per driver, coloured by tyre.
- `uv run f1si wear bahrain-2023` fits fuel-corrected tyre wear per compound and prints it with the fuel effect and the pit loss (it also writes `reports\wear-bahrain-2023.png`).
- `uv run f1si plan bahrain-2023 --driver ALO` prints the fastest free-track 1-stop and 2-stop plans, labelled "Hindsight plan" because it uses the whole race. Add `--lap 30` to plan from only what was known after lap 30. Free-track means no traffic or safety cars, so the time is a lower bound, and the actual strategy is compared against the plan, never said to be beaten by it.
- `uv run f1si simulate bahrain-2023 --driver ALO` prints Alonso's finishing-position distribution from 50,000 simulated continuations of the race, labelled "hindsight simulation" because it uses the whole race. Add `--lap 30` to use only data known after lap 30. The safety-car rate for Bahrain 2023 comes from the prior alone (there are no earlier races), printed as "prior only". It also writes `reports\sim-bahrain-2023-ALO-lap0.png`.
- `uv run f1si wear-filter bahrain-2023 --driver ALO` replays the race and prints, for each of the driver's stints, the tyre wear-rate estimate and its 95% band lap by lap, using only data known at each lap. Tyre state is hidden; the filter infers it. A stint whose starting belief has no data behind it yet is labelled "prior only", and the dashed line in the chart is the Phase 2 "hindsight" estimate. Add `--lap 30` to stop the replay at lap 30. It writes `reportswear-filter-bahrain-2023-ALO.png`.
- `uv run f1si replay bahrain-2023 --driver ALO` prints a ranked pit-action recommendation at every cutoff in the cached race. `uv run f1si replay bahrain-2023 --driver ALO --lap 20` prints only the as-of decision after lap 20. Each row shows ranked options with mean finishing position, spread, worst-decile CVaR10 and their blended score; lower scores rank first. When the visible data cannot identify a dry-tyre pace fit, the row is visibly marked `fallback` and uses cutoff-visible residuals plus generic priors, including an **[ASSUMED] 1.0 s** driver-offset SD. Those recommendations are prior-driven and uncalibrated; their spread is not a calibrated confidence interval. No later laps are used to fill an early row.
- Replay accepts a race slug from the local catalog (for example, `bahrain-2023`) and a three-letter driver code belonging to that race; driver codes are case-insensitive. `--lap N` must be from 0 to one less than the race lap count. Omit it to see all cutoffs. `--n N` must be a positive simulation count up to 200,000 (default 50,000). `--risk-aversion R` (also `--risk R`) must be finite and in `[0, 1]` (default 0.5): 0 ranks by mean finish, 1 by worst-decile CVaR10, and intermediate values blend the two. See [the Phase 5 strategy and replay explanation](docs/explained/phase-05.md) for the method, limitations and file tour.
- No code can read future data: every read goes through one as-of door, guarded in CI by an import scan and a future-scramble test, with deliberately planted leaks to prove the guards work.
- Two-OS CI (ubuntu and Windows), seeded randomness, synthetic races with known ground truth, and a decision log.

## Phase 6 walk-forward results

The pre-registered sample uses the first calendar rounds available in a 4/3/3 split, with Bahrain 2023 fixed as the reference race. The ten races are `2023-01`, `2023-02`, `2023-03`, `2023-04`, `2024-01`, `2024-02`, `2024-03`, `2025-01`, `2025-02`, and `2025-03`. Each prediction uses 1,000 simulations, base seed 0, and risk aversion 0.5. The continuation regression uses two-fold cross-fitting: each scoring fold is excluded from its regression-fit paths. The 2026 races are excluded.

The fixed-engine run produced 10,391 finite driver-cutoff predictions for Brier scoring. Results first average observations within each race, then give the ten races equal weight. Brier comparisons use the same finite model and baseline rows. The baseline uses only earlier races, five neutral pseudo-starts, and field-size neutral rates for the first race. Intervals below are paired 95% percentile-bootstrap intervals over 10 whole-race clusters (2,000 resamples); negative differences favor the model.

| Outcome | Model Brier | Past-only grid baseline Brier | Model minus baseline (mean; 95% race-cluster interval) |
|---|---:|---:|---:|
| Podium | 0.047577115412777045 | 0.08039264027755422 | -0.03281552486477717 [-0.05659808575571115, -0.007513405355438941] |
| Top 10 | 0.14461052617055442 | 0.1899145165444817 | -0.04530399037392725 [-0.08394133716127004, -0.00723574000178926] |

The inclusive empirical inverted-CDF P05/P95 endpoints form each simulated 90% finishing-position interval. Among 9,146 classified finishers, 7,650 fell inside their interval: coverage 0.8321320371253993, with a 95% race-cluster interval of [0.7607317538579549, 0.8887111448658811]. Unclassified starters are excluded because the simulator does not model retirements.

The team-call section is a retrospective comparison with observed team behavior. No superiority claim is made. It matched 388 of 388 observed pit stops across 10 races. Top-action agreement was 0.17538471772651862 [0.0674825915707056, 0.3080644630651049] (mean; 95% race-cluster interval). Signed timing error (planned stop lap minus observed in-lap) averaged 1.957219052615472 laps [-0.10449789603689873, 3.2388810987605736]; mean absolute timing error was 3.659534286401295 laps [2.9675666163901457, 4.650973476402823]. The top action was `wait and decide next lap` in 5,707/10,404 recommendations (54.85%) before the continuation-fit change and 5,624/10,391 (54.12%) after it. The result preserves a distinct next-lap policy while fitting continuation values on paths independent from those scored.

The wear-band diagnostic is a retrospective proxy, not latent ground truth. The filter's 1.96-standard-deviation wear band covered 6,382 of 7,659 available proxy comparisons (0.833268050659355). For estimates using at most eight clean laps, early-fit bias (cutoff posterior mean minus proxy) was -0.007208870207207395 s/lap. Current-stint clean laps made up a mean share of 0.05488478791292842 across 5,939 measurements under the same-cutoff, same-compound definition. No leave-stint-out reference could be estimated for `2023-03` or `2025-01`; these races are reported as unavailable, not misses. The filter was not tuned on these evaluation races.

Fuel load and tire wear are hidden variables. The simulator uses simplified assumptions, including linear wear, the existing historical safety-car probability rather than Phase 8's Markov regime model, and no retirement model. Sparse or prior-driven replay outputs remain uncalibrated; interval coverage here describes this sample and does not establish future calibration. The complete measured report is [`reports/backtest/phase-06.json`](reports/backtest/phase-06.json), and the [Phase 6 explainer](docs/explained/phase-06.md) describes the method and file tour. Run the read-only view with `uv run streamlit run src/f1si/app.py`.

## Phase 7 Bayesian pace evaluation

The optional hierarchical Bayesian model passed the synthetic recovery checks, but it did not improve next-lap error on the single locked real-data holdout. Across the registered 2025-01 to 2025-03 race group, it had 1,348 paired target predictions (1,344 unique driver-target laps). Bayesian MAE was 0.5387 seconds; the linear baseline was 0.3640 seconds. The Bayesian MAE was 48.0% higher, so PAC-06 is **not met**. The first race, 2025-01, remains in the registered group and contributed zero paired targets; 2025-02 contributed 776 and 2025-03 contributed 572.

| Race | Paired predictions | Unique driver-target laps | Linear MAE (s) | Bayesian MAE (s) |
|---|---:|---:|---:|---:|
| 2025-01 | 0 | 0 | — | — |
| 2025-02 | 776 | 773 | 0.4160 | 0.5607 |
| 2025-03 | 572 | 571 | 0.2936 | 0.5090 |
| **Combined** | **1,348** | **1,344** | **0.3640** | **0.5387** |

The score used 74 successful 50,000-iteration cutoff fits with no fit failures. The registered race group and metric were not changed after scoring, and the score was not rerun for tuning. All real training and target rows are from the 2022–2025 ground-effect regulation era, so the evaluation does not identify a real between-era effect. See the [complete report](reports/pace/phase-07.json), [Phase 7 explainer](docs/explained/phase-07.md), and [Phase 7 summary](docs/phases/07-bayesian-pace-model.md).

## Phase 8 regime evaluation

The 20-race, 2023–2025 in-sample report and the separate 2026 holdout are reported independently. The in-sample model produced podium Brier 0.05546 versus a 0.07369 grid baseline, top-10 Brier 0.14465 versus 0.16909, and 90% finishing-interval coverage of 16,508/20,001 (82.26%). Across 695 matched stops, signed stop-timing error was +1.174 laps; top-action agreement with observed team calls was 17.22% (race-cluster 95% intervals: [-1.697, 2.918] laps and [9.40%, 26.80%], respectively).

The locked 2026-09 through 2026-17 holdout used linear pace, 1,000 simulations, seed 0, and risk 0.5. It produced podium Brier 0.06639 (11,282 observations), top-10 Brier 0.14948 (11,282), and 90% interval coverage 6,947/9,513 classified finishers (73.03%). Across 267 matched stops, signed timing error was +2.064 laps and team-call agreement was 1.87%; 378 stop events were observed. The report includes all nine race rows and denominators at [`reports/backtest/phase-08-holdout.json`](reports/backtest/phase-08-holdout.json). The in-sample report is [`reports/backtest/phase-08.json`](reports/backtest/phase-08.json).

This holdout is **pre-registered but retrospectively unblinded**, not blind: schedule research incidentally exposed outcome displays before the score, and no displayed values were used for model, lock, or metric changes. One failed schedule preflight occurred before result access; one successful locked score then produced the report. The report is verified read-only and must not be tuned or rescored. These 2026 results have no matched grid-baseline comparison and do not establish calibration or superiority over teams. See the [Phase 8 explainer](docs/explained/phase-08.md) and [validation record](.planning/phases/08-markov-regimes-full-backtest/08-VALIDATION.md).

Read [docs/explained/phase-05.md](docs/explained/phase-05.md) for the Phase 5 Longstaff-Schwartz and replay tour. Read [docs/explained/phase-04.md](docs/explained/phase-04.md) for the Phase 4 tour (the Kalman tyre-wear filter, its priors, real Bahrain numbers). Read [docs/explained/phase-03.md](docs/explained/phase-03.md) for the Phase 3 tour (the safety-car rate, passing, variance reduction, the simulator). Read [docs/explained/phase-02.md](docs/explained/phase-02.md) for the Phase 2 tour (interfaces, tyre wear, the pit plan). Read [docs/explained/phase-01.md](docs/explained/phase-01.md) for a plain-language tour of everything built (what, why, how the pieces connect, a file-by-file tour and interview questions). Every method choice is logged in [DECISIONS.md](DECISIONS.md).

## Quickstart (Windows PowerShell)

```powershell
uv sync
uv run pre-commit install
uv run f1si --data-dir data/demo load --source synthetic   # offline demo with fake races
uv run f1si --data-dir data/demo races
uv run f1si load                                           # real races, about 15 minutes the first time
uv run f1si backfill-scheduled-laps                        # FastF1 scheduled lap counts; the backtest and page need them
uv run f1si races
uv run f1si plot bahrain-2023                              # writes reports\bahrain-2023.png
uv run f1si wear bahrain-2023                              # writes reports\wear-bahrain-2023.png
uv run f1si plan bahrain-2023 --driver ALO                 # hindsight plan for Alonso
uv run f1si plan bahrain-2023 --driver ALO --lap 30        # plan using only data up to lap 30
uv run f1si simulate bahrain-2023 --driver ALO             # hindsight simulation, writes reports\sim-bahrain-2023-ALO-lap0.png
uv run f1si simulate bahrain-2023 --driver ALO --lap 30    # simulation using only data up to lap 30
uv run f1si wear-filter bahrain-2023 --driver ALO           # as-of wear-rate band, writes reportswear-filter-bahrain-2023-ALO.png
uv run f1si wear-filter bahrain-2023 --driver ALO --lap 30   # replay stopped at lap 30
uv run f1si backtest --report                              # score the ten registered races, writes reports\backtest\phase-06.json
uv run streamlit run src/f1si/app.py                       # the replay page
uv run pytest
```

## Data and credits

The loader uses OpenF1 (openf1.org; personal, non-commercial use) for timing and race data and the Jolpica F1 API (Ergast-compatible) for calendar, grid, results, and pit-stop facts (DEC-005). FastF1 (MIT-licensed) supplies each race's scheduled lap count through `f1si backfill-scheduled-laps`, which the backtest and the replay page need, and the team colors on the page. Fresh FastF1 timing downloads may require an F1 TV Access, Pro, or Premium account (DEC-107); verified cached counts keep working without one. This project is not affiliated with Formula 1. Source terms still apply; raw data is never committed or republished.
