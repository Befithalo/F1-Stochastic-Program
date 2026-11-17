# Phase 1: Foundation & Data - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-22
**Phase:** 01-foundation-data
**Areas discussed:** Look-ahead guard, What gets cached, CI test data, Commands/plot/walkthrough

---

## Look-ahead guard

### Where does the "as of lap N" cutoff fall?

| Option | Description | Selected |
|--------|-------------|----------|
| Leader's clock | Cut at the session time the leader finishes lap N; never leaks; matches `RaceState.lap` | ✓ |
| Lap number | All rows with lap ≤ N; lapped cars leak a little future | |
| Each driver's own clock | Per-driver cutoff; can't share one RaceState across the field | |
| You decide | Claude picks | |

**User's choice:** Leader's clock

### How does the build prove nothing reads future data?

| Option | Description | Selected |
|--------|-------------|----------|
| Both checks | Import ban + future-scramble test + planted leaky function both must catch | ✓ |
| Scramble test only | Misses code that goes around the accessor | |
| Import ban only | Misses bugs inside the accessor | |

**User's choice:** Both checks

### How are whole-race facts kept from strategy code?

| Option | Description | Selected |
|--------|-------------|----------|
| Two separate doors | As-of accessor never serves whole-race facts; separate results accessor only the scorer may import | ✓ |
| One accessor with a flag | `include_results=True`; one careless flag is an uncaught leak | |
| You decide | Claude picks | |

**User's choice:** Two separate doors

### Does the accessor also govern other races (walk-forward)?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, one accessor | Earlier races in full + pre-race facts + this race to cutoff; later races invisible; 2026 locked | ✓ |
| Within-race only for now | Cross-race handled separately in Phase 6 | |
| You decide | Claude picks | |

**User's choice:** Yes, one accessor

---

## What gets cached

### Seasons

| Option | Description | Selected |
|--------|-------------|----------|
| 2023-25 + 2026 locked | Matches DAT-01; 2026 loaded, tagged out-of-sample, locked | ✓ |
| 2022-25 + 2026 locked | Adds first ground-effect year; FastF1-only, early-era quirks | |
| 2023-2025 only | 2026 added in Phase 8 | |

**User's choice:** 2023-25 + 2026 locked

### Sessions

| Option | Description | Selected |
|--------|-------------|----------|
| Grand Prix only | Covers Phases 1-6; grid from results | ✓ |
| GP + qualifying | Pace prior for Phase 7; ~2x download | |
| GP + qualifying + sprints | Sprints have almost no pit stops | |

**User's choice:** Grand Prix only

### Extra race context

| Option | Description | Selected |
|--------|-------------|----------|
| Track status + weather | Needed by Phase 3 SC rate and Phase 8 regimes; same download | ✓ |
| Track status only | Weather re-pulled in Phase 8 | |
| Bare minimum | Only DAT-01 list | |

**User's choice:** Track status + weather

### Data source

| Option | Description | Selected |
|--------|-------------|----------|
| FastF1 only | Covers everything needed; one set of quirks; OpenF1 later | ✓ |
| FastF1 + OpenF1 cross-check | Catches data errors; ~2x loader work | |
| OpenF1 primary | Live-feed format; no pre-2023 data | |

**User's choice:** FastF1 only

---

## CI test data

### Test data

| Option | Description | Selected |
|--------|-------------|----------|
| Synthetic + weekly real | Synthetic on every push; weekly/manual Bahrain 2023 job, not a gate | ✓ |
| Synthetic only | Real-data tests local only | |
| Commit a real excerpt | Republishes raw data | |
| Download on every push | Flaky on FastF1 outages | |

**User's choice:** Synthetic + weekly real

### CI operating systems

| Option | Description | Selected |
|--------|-------------|----------|
| Linux + Windows | Catches Windows path/locking bugs | ✓ |
| Linux only | Faster | |

**User's choice:** Linux + Windows

### GitHub repo

| Option | Description | Selected |
|--------|-------------|----------|
| Public | Portfolio visibility, unlimited CI minutes | |
| Private for now | 2,000 min/month, Windows 2x | |
| I already have one | Connect to existing repo | ✓ |

**User's choice:** I already have one: `https://github.com/Befithalo/F1-Stochastic-Program`
**Notes:** User asked "is this it?". Verified with `git ls-remote`: the repo exists, is public (no auth needed) and is empty (no refs). A nonexistent-repo control returned "Repository not found".

### Local hooks

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-commit hooks | ruff auto-fix on commit; mypy/tests in CI | ✓ |
| CI only | Nothing local | |

**User's choice:** Pre-commit hooks

---

## Commands, plot, walkthrough

### How to run loader and plot

| Option | Description | Selected |
|--------|-------------|----------|
| One f1si CLI | `uv run f1si load` / `plot`; resumable, retries, progress, failure list | ✓ |
| Separate scripts | Options drift apart | |
| Jupyter notebook | Hard to test | |

**User's choice:** One f1si CLI

### Plot format

| Option | Description | Selected |
|--------|-------------|----------|
| Static PNG | matplotlib to reports/; README-ready | ✓ |
| Interactive HTML | plotly hover | |
| Both | Two code paths | |

**User's choice:** Static PNG

### Plot content

| Option | Description | Selected |
|--------|-------------|----------|
| Grid, slow laps faded | Panel per driver, colored by compound, slow laps faded not removed, `--drivers` filter | ✓ |
| Chosen drivers, one chart | Overlay, slow laps removed | |
| You decide | Claude picks | |

**User's choice:** Grid, slow laps faded

### Walkthrough location (UI-03)

| Option | Description | Selected |
|--------|-------------|----------|
| File in repo + chat | `docs/explained/phase-01.md` with file tour + interview Q&A; chat summary | ✓ |
| File in repo, no Q&A | Explanation and tour only | |
| Chat only | Nothing saved | |

**User's choice:** File in repo + chat

---

## Post-research revisions (2026-10-22, during plan-phase)

Research found that F1's live-timing archive returns HTTP 401 without an F1 TV login. This was independently confirmed by curl: 401 for `static/2023/Index.json` and the Bahrain 2023 race stream. OpenF1 and Jolpica both returned 200.

| Question | Options | Selected |
|----------|---------|----------|
| Data source (revises D-08, D-10) | OpenF1 + Jolpica / FastF1 3.9.0a0 + F1 TV account / Decide later | OpenF1 + Jolpica |
| Do earlier races "in full" include final results? (D-04) | Yes / No | Yes |
| Plot cutoff (D-16) | Race-end cutoff in the as-of door / Final-lap cutoff as written | Race-end cutoff |
| Commit `F1 Docs/` to the public repo? (new D-18) | Commit / Keep local | Commit |

---

## Claude's Discretion

- Era tag granularity (suggested one 2022–2025 ground-effect era + 2026 out-of-sample, keep `season`)
- Pre-race facts list, DuckDB schema, file locations
- Import-ban mechanism (AST test vs import-linter); 2026 unlock door form
- Seed convention (rng argument, ruff NPY002)
- DECISIONS.md format; coverage reporting; .gitignore contents

## Deferred Ideas

- Qualifying as pace prior (Phase 7)
- 2022 season (Phase 7, if needed)
- OpenF1 source/cross-check (M6)
- Interactive plot (Phase 6 Streamlit)
- Paper notes in DECISIONS.md (user reading task)
