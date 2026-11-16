# F1 Stochastic Intelligence Platform (f1si)

A Python platform that recommends F1 pit strategy as a full probability distribution, recomputed every lap. It uses quant-finance methods (Monte Carlo pricing, optimal stopping, CVaR, regime switching, Kalman filtering) together with vehicle physics, ML/RL and production engineering. Pit timing is treated as an American option and strategy choice as a risk-adjusted portfolio decision.

## Status

Phases 1–5 provide the data layer, simulator, wear filter, and cutoff-safe strategy replay. Phase 6 adds a fixed-sample, ten-race walk-forward evaluation and a read-only Streamlit view. Its results below are an MVP measurement, not a claim of calibrated performance or superiority over teams.

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

The pre-registered sample uses the first calendar rounds available in a 4/3/3 split, with Bahrain 2023 fixed as the reference race. The ten races are `2023-01`, `2023-02`, `2023-03`, `2023-04`, `2024-01`, `2024-02`, `2024-03`, `2025-01`, `2025-02`, and `2025-03`. The evaluation uses 1000 simulations per prediction, base seed 0, and risk aversion 0.5. The 2026 races are excluded.

For each eligible cutoff, the scoring set contains 10,942 driver-cutoff observations. Results first average observations within each race and then weight the ten races equally. Brier-score comparisons use the same finite model/baseline rows. The baseline uses only earlier races, five neutral pseudo-starts, and field-size neutral rates for the first race. Intervals below are paired 95% percentile-bootstrap intervals over 10 whole-race clusters (2,000 resamples); negative model-minus-baseline differences favor the model on Brier score.

| Outcome | Model Brier | Past-only grid baseline Brier | Model minus baseline (mean; 95% race-cluster interval) |
|---|---:|---:|---:|
| Podium | 0.04996303890335588 | 0.08173654492348711 | -0.031773506020131244 [-0.05672358543556256, -0.005363629173093326] |
| Top 10 | 0.14533417363917167 | 0.1909038082417302 | -0.04556963460255854 [-0.08052476306631937, -0.010127941480180428] |

The inclusive empirical inverted-CDF P05/P95 endpoints form each simulated 90% finishing-position interval. Among 9,602 classified finishers, 8,004 fell inside their interval: coverage 0.8295398500926574, with a 95% race-cluster interval of [0.7607601520282031, 0.8843303002979427] over 10 races. Unclassified starters are excluded from this coverage denominator because the simulator does not model retirements.

The team-call section is a retrospective comparison with observed team behavior. No superiority claim is made. It matched 388 of 388 observed pit-stop events across 10 races, using the latest recommendation strictly before each in-lap. Top-action agreement was 0.7899209298533085 [0.7041475831091105, 0.8696134672582672] (mean; 95% race-cluster interval). Signed stop-timing error is planned stop lap minus observed in-lap: its mean was 1.076021920859382 laps [0.5541985817086437, 1.583301885476808]. Mean absolute timing error was 1.4024312868817512 laps [0.9634773987831265, 1.836237109317411]. Both timing intervals are 95% race-cluster intervals over 10 races.

The wear-band diagnostic is a retrospective proxy, not latent ground truth. The filter's 1.96-standard-deviation (nominal 95%) wear band covered 6,398 of 7,678 available proxy comparisons (0.8332899192498047). For estimates using at most eight clean laps, the report's early-fit bias (cutoff posterior mean minus proxy) was -0.006948225533989541 s/lap. Current-stint clean laps made up a mean share of 0.05490457502513985 across 5,958 measurements under the report's same-cutoff, same-compound definition. No leave-stint-out reference could be estimated for `2023-03` or `2025-01`; these races are reported as unavailable rather than treated as misses. The filter was not tuned on these evaluation races.

Fuel load and tire wear are hidden variables. The simulator uses simplified assumptions, including linear wear, the existing historical safety-car probability rather than Phase 8's Markov regime model, and no retirement model. Sparse or prior-driven replay outputs remain uncalibrated; interval coverage here describes this sample and does not establish future calibration. The complete measured report is [`reports/backtest/phase-06.json`](reports/backtest/phase-06.json), and the [Phase 6 explainer](docs/explained/phase-06.md) describes the method and file tour. Run the read-only view with `uv run streamlit run src/f1si/app.py`.

Read [docs/explained/phase-05.md](docs/explained/phase-05.md) for the Phase 5 Longstaff-Schwartz and replay tour. Read [docs/explained/phase-04.md](docs/explained/phase-04.md) for the Phase 4 tour (the Kalman tyre-wear filter, its priors, real Bahrain numbers). Read [docs/explained/phase-03.md](docs/explained/phase-03.md) for the Phase 3 tour (the safety-car rate, passing, variance reduction, the simulator). Read [docs/explained/phase-02.md](docs/explained/phase-02.md) for the Phase 2 tour (interfaces, tyre wear, the pit plan). Read [docs/explained/phase-01.md](docs/explained/phase-01.md) for a plain-language tour of everything built (what, why, how the pieces connect, a file-by-file tour and interview questions). Every method choice is logged in [DECISIONS.md](DECISIONS.md).

## Quickstart (Windows PowerShell)

```powershell
uv sync
uv run pre-commit install
uv run f1si --data-dir data/demo load --source synthetic   # offline demo with fake races
uv run f1si --data-dir data/demo races
uv run f1si load                                           # real races, about 15 minutes the first time
uv run f1si races
uv run f1si plot bahrain-2023                              # writes reports\bahrain-2023.png
uv run f1si wear bahrain-2023                              # writes reports\wear-bahrain-2023.png
uv run f1si plan bahrain-2023 --driver ALO                 # hindsight plan for Alonso
uv run f1si plan bahrain-2023 --driver ALO --lap 30        # plan using only data up to lap 30
uv run f1si simulate bahrain-2023 --driver ALO             # hindsight simulation, writes reports\sim-bahrain-2023-ALO-lap0.png
uv run f1si simulate bahrain-2023 --driver ALO --lap 30    # simulation using only data up to lap 30
uv run f1si wear-filter bahrain-2023 --driver ALO           # as-of wear-rate band, writes reportswear-filter-bahrain-2023-ALO.png
uv run f1si wear-filter bahrain-2023 --driver ALO --lap 30   # replay stopped at lap 30
uv run pytest
```

## Data and credits

The current loader uses OpenF1 (openf1.org; personal, non-commercial use) for timing and race data and the Jolpica F1 API (Ergast-compatible) for calendar, grid, results, and pit-stop facts. FastF1 was the original planned source; it is MIT-licensed, but DEC-005 records why the current loader uses OpenF1 and Jolpica instead. This project is not affiliated with Formula 1. Source terms still apply; raw data is never committed or republished.
