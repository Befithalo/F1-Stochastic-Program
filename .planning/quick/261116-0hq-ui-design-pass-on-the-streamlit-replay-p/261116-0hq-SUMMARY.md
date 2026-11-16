---
quick_id: 261116-0hq
description: UI design pass on the Streamlit replay page
date: 2026-11-16
status: done, not committed (waiting for the owner)
---

# Summary

The replay page was rebuilt around prototype B, the race strip: answer, finish histogram and a
lap 1 to N strip in the decision band; merged option rows with probability strips; chart headings
that stay with their charts; computed model-report verdicts with small graphics; a glossary with
icons. Copy follows `docs/design/COPY_V2.md`; decisions are in `docs/design/DESIGN_SYSTEM_V2.md`
section 10 and DEC-114 and DEC-115.

## Steps

1. Research: formula1.com and mclaren.com CSS read directly (Taste Engine MCP not installed).
2. Review: ten problems, owner approved the list.
3. Prototype: `docs/design/prototypes/decision-band-prototype.html`; owner chose B.
4. Copy: humanizer pass, owner approved `COPY_V2.md`.
5. Decisions: grilling; owner answered Q1 to Q8 and delegated the rest.
6. Build: `app.py`, `ui_theme.py`, `plots/altair_charts.py`, `plots/replay_charts.py`,
   `dashboard.css`. Screenshots `reports/ui-review/v2-1440.png`, `v2-390.png`; contrast audit
   `reports/ui-review/contrast-v2.md` (23 measured pairs across every 2023 to 2025 team, all pass).
7. Check: two-axis code review (standards and spec), findings fixed; DEC-114 and DEC-115 logged.

## Fixed from the review

- Tyre colors in the race strip lightened per team to 3:1 on the band (raw Soft fell to 2.26:1).
- Close-call note names the optimizer's unmerged runner-up.
- Fan chart follows the N + 0.5 lap geometry; the last lap has full width.
- Model-report verdicts computed from the values; race count from the report.
- Podium and points brackets use the exact chances; the 9-in-10 range uses the exact 5th and
  95th percentile finishes.
- Strip shows the tyre wear line, stop cost and window label; copy aligned with `COPY_V2.md`
  (surname instead of a pronoun).
- Palette code moved to `ui_theme.py`; action labels parsed once; unused parameters, dead CSS
  and a middle-man wrapper removed; docstrings state the math.

## Verification

- ruff, ruff format and mypy strict: clean over `src` and `tests`.
- Full suite: 1,131 passed. Local-only failures are the known `-I` subprocess tests
  (import order, plot import checks, cache lock); CI runs them.
- `test_docs` passes since the owner's regenerated `reports/backtest/phase-06.json` landed.

## Left for the owner

- `tests/real/test_bahrain_2023.py::test_lap_15_replay_ranks_only_distinct_live_choices` still
  expects the pre-stop state at lap 15; the mid-pit-stop change (DEC-112) makes `stay out` and
  `pit now (SOFT)` legal there.
- `test_bahrain_actual_top_five_forecasts_are_within_five_places[ALO]` is a strict xfail that now
  passes.
- Commit and push (CI) not done: the owner's uncommitted data-layer work is in the same tree and
  the new tests depend on it.
