<!-- GSD:project-start source:PROJECT.md -->
## Project

**F1 Stochastic Intelligence Platform (f1si)**

A Python platform that recommends F1 pit strategy as a full probability distribution, recomputed every lap. It uses quant-finance methods (Monte Carlo pricing, optimal stopping, CVaR, regime switching, Kalman filtering) together with vehicle physics, ML/RL and production engineering. Pit timing is treated as an American option and strategy choice as a risk-adjusted portfolio decision.

Core loop, once per lap: ingest timing data, update car state (tire wear, pace, track regime), simulate 50,000 race continuations, value each pit decision, rank by mean finish and tail risk, show the recommendation with its uncertainty.

Source design docs: `F1 Docs/BUILD_PLAN.md` (full design, data sources, evaluation, risks) and `F1 Docs/MASTER_PROMPT.md` (build brief).

**Core Value:** For any driver at any lap of a replayed race, give a pit-strategy recommendation whose uncertainty is honest: calibrated, free of look-ahead, and verified against synthetic ground truth.

### Constraints

- **Stack**: Python 3.12, uv, NumPy, pandas, SciPy, PyMC, Numba, FastF1, OpenF1, DuckDB, pytest + hypothesis, ruff, mypy strict, GitHub Actions CI; src/ layout, package `f1si`
- **Reproducibility**: explicit `np.random.Generator` everywhere; reproducible by seed
- **No look-ahead**: backtests read data only through one as-of accessor; a test enforces it
- **Model validation**: every model has a synthetic-data recovery test (known parameters recovered)
- **Documentation**: docstrings state the math; DECISIONS.md logs every method choice and why
- **Quality gate**: CI must pass before a phase counts as done
- **Performance**: NumPy simulator under 10 s for 50,000 races
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
