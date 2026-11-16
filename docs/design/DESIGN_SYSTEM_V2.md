# Design system v2: F1 strategy replay

This replaces DESIGN_BRIEF.md. The visual target is `strategy_mockup.html` (open it in a browser) for tokens, type and spacing, and `prototypes/decision-band-prototype.html?variant=B` (the race strip) for the decision band and option rows. Page copy lives in `COPY_V2.md`. Swap in live model values. Section 10 records the decisions taken on 2026-11-16; where it disagrees with an earlier section, section 10 wins.

## 1. What changed and why

The v1 page was clean but read as generic: one purple accent on dark grey, dense tables, and numbers with no explanation. v2 borrows from how F1 and the teams actually present data:

| Reference | What we take |
| --- | --- |
| [Formula1.com results pages](https://www.formula1.com/en/results/2023/races/1141/bahrain/race-result) | Dark blue-grey base, Titillium Web at 16 px, table rows about 57 px tall (measured), bold condensed headings |
| [Mercedes-AMG standings](https://www.mercedesamgf1.com/standings) | Huge bold headings; the team's own rows filled with the team color so they jump out |
| [McLaren standings](https://www.mclaren.com/racing/formula-1/standings/) | Long, well-spaced rows; position chips; own drivers highlighted with team color |
| [Aston Martin](https://www.astonmartinf1.com/en-GB) and [Ferrari](https://www.ferrari.com/en-EN/formula1) | Each team owns one strong color world (racing green, rosso). We tint the page with the selected driver's team color |
| F1 TV graphics ([Motor Sport](https://www.motorsportmagazine.com/articles/single-seaters/f1/formula-1s-tv-graphic-balancing-act)) | Serve casual and hardcore viewers at once; show predictions as best estimates, not certainties |
| F1 Strategy Insight, AWS ([F1](https://www.formula1.com/en/latest/article/f1-to-launch-new-strategy-insight-graphic-powered-by-aws-at-hungarian-grand-prix.3h211Yy2IaW04biHGRY4EM.3h211Yy2IaW04biHGRY4EM.3h211Yy2IaW04biHGRY4EM)) | Explain the call through its drivers: tyre performance, pit window, safety-car risk, rivals |

Do not copy logos, the Formula1 typeface, team marks or photography.

## 2. Principles

1. **Answer first, then explain, then prove.** Page order: the decision, why, the options, the race so far, how sure we are, how good the model is, how to read the page.
2. **Every number gets a plain label and a meaning.** Never show a bare number. Each has a name a fan understands, a unit, and one line of what it means or how it compares.
3. **Color means something.** The selected driver's team color is the page's identity color. Tyre colors mark compounds. Green means better, red means worse, amber means caution. Everything else is neutral.
4. **Space separates; boxes don't.** Long rows with generous padding and one hairline between them. No card grids.
5. **One bold element.** The decision band at the top. Everything else is calm.

## 3. Color tokens

| Token | Hex | Use |
| --- | --- | --- |
| `tarmac` | `#1B1D23` | Page background |
| `pitlane` | `#23262E` | Raised surfaces (rare) |
| `kerb` | `#30343E` | Hairlines, range tracks |
| `chalk` | `#F2F2F0` | Main text |
| `fog` | `#A9AEB8` | Secondary text |
| `team` | from `fastf1.plotting.get_team_color` | Identity color: decision band, recommended option, selected driver's line and stint |
| `better` | `#4ADE80` | Good verdicts, positive deltas |
| `worse` | `#FF6B6B` | Bad verdicts, "places worse" tags |
| `caution` | `#F5C518` | Warnings (shared with medium tyre on purpose) |
| Tyres | soft `#E8323C`, medium `#F5C518`, hard `#F2F2F0`, inter `#43B047`, wet `#2F7FD6` | Compound chips and stint bars only |

- Decision band background: team color mixed 22% into `tarmac`, plus a 6 px solid team-color top rule.
- `team-fill`: team color mixed with black, starting at 70% team color and darkened in 5% steps until white text reaches 4.5:1. Use it behind white text (driver code chip, Recommended tag) so small text clears 4.5:1; the raw team color can fall short (Aston Martin `#358C75` gives white about 4.1:1).
- If a team color is too dark for 3:1 against `tarmac`, lighten it for lines and keep the original for fills.
- Purple is no longer the recommendation color. Use it only for "fastest lap" in timing contexts, if at all.

## 4. Type

- **Saira Condensed 800** (Google Fonts): page headline, section headings, big numbers.
- **Titillium Web 400/600/700** (Google Fonts, the body face Formula1.com uses): everything else.
- Sizes: headline 56–104 px (fluid), section heading 40 px, big stat 44 px, model metric 52 px, option title 24 px, body 16 px, help text 14 px.
- Sentence case everywhere. No all-caps labels, no labels above every heading, no middle-dot strings.
- All numbers use tabular figures. Confirm both fonts render them; if one doesn't, fall back to a face that does for numbers only.

## 5. Layout and spacing

- Content max width 1180 px, left aligned, 32 px side padding (16 px on phone).
- 8 px spacing grid. 72 px between sections. 28 px vertical padding inside each option row.
- Data rows at least 56 px tall (Formula1.com uses about 57 px).
- Phone: everything stacks; stats go two per row; no horizontal scroll.

```
[decision band, team-tinted]
 Race / lap / risk setting
 [ALO] Fernando Alonso, Aston Martin
 STAY OUT FOR NOW              (headline)
 one sentence why
 [close-call note]
 Tyres        | Pit window   | Safety car      (number + meaning each)

Your options          (one long row per distinct option, best first)
 (tyre) Title  [Recommended | 0.3 places worse]
        one-line explanation
        P8.5 Expected | P16.7 Bad-day | 10% Podium | 72% Points
        [P1 ===o====== P20] 9 in 10 finish between P2 and P17

The race so far       (gap to leader, stints so far; takeaway titles)
How sure are we?      (fan chart; takeaway title)
How good is this model?  (5 metrics, each number + verdict + meaning)
How to read this page    (glossary)
```

## 6. Words

| Old | New |
| --- | --- |
| Mean finish | Expected finish |
| Worst 10% average finish / CVaR | Bad-day finish |
| Top-10 chance | Points chance |
| Spread | Drop it; the range bar shows it |
| 90% finish interval | "9 in 10 simulated races finish between P2 and P17" |
| Score | Drop it from the page; keep in the expandable details |
| Risk aversion 0.50 | Risk setting: balanced (0 to 1 slider kept, with "Aggressive", "Balanced", "Cautious" labels) |
| Box in 1 lap | Box next lap |
| Stay out (never stop) | Never stop: not allowed (two-compound rule) |

- Headline verbs: "Box this lap", "Stay out for now", "Box next lap", or "Too close to call".
- Close calls: if the best two options differ by less than 2 standard errors, say "Close call: … is only X places worse on average."
- Chart titles state the finding, generated from data, for example "Alonso drops to P12 after his stop, then recovers to P8". The chart's subject goes in a smaller line below.
- Each model metric gets a verdict in words ("Better than starting order", "Slightly overconfident").

## 7. Components

**Decision band.** Context line, driver chip in team color, headline, why sentence, close-call note, then three reason blocks: tyres (wear rate), pit window (laps where options tie), safety car (chance per lap). Each reason: label, big number with unit, one sentence of meaning.

**Option row.** Tyre chip (ring in compound color with letter), title, tag (Recommended in team color, or "N places worse" in red), one-line explanation, four stats (number, label, help text on the recommended row), range bar on a true P1–P20 scale with the 90% range and a dot at the expected finish, one plain-language range sentence. Recommended row: team-color left border and a faint team tint. Merge options with identical results. Show at most 4 rows; put the full numeric table in a "Show all numbers" expander.

**Charts** (Altair, Streamlit theme):
- Gap to leader: selected driver in team color, closest rival ahead and behind in neutral light grey with labels, everyone else dim grey, no labels.
- Stints so far: every driver labeled; compound colors with letters; selected driver's recommended next stint as a team-color outline inside the axis.
- How sure are we: fan chart in the team color at three opacities (10–90, 25–75, 40–60), labels in `fog` beside the bands, median as a solid line, x axis "Lap" ending at the race distance.
- Finish chances: per-option probability strip for the merged options only.
- No chart titles inside the chart; heading and takeaway sit above it in page type.

**Model report.** Five metrics in a loose grid: big number, verdict in green or amber, one-sentence meaning that includes the raw value.

**Glossary.** Definition list of the terms on the page.

## 8. Do not

- Cards around every section, identical rounded boxes, drop shadows, gradient washes
- All-caps labels, middle-dot meta strings, monospace labels, arrows on links
- Bare numbers without labels, more than one decimal for positions, six-decimal values
- Showing nine identical options
- Purple as a general accent
- Fade-in animations; numbers update instantly when the lap changes

## 9. Streamlit notes

- Build the decision band, option rows, model report and glossary with `st.html` using one shared CSS file. Keep the controls as native Streamlit widgets, styled through `.streamlit/config.toml`.
- Load fonts through the theme config (`font`, `headingFont`) with Google Fonts URLs.
- Hide the toolbar, chart action menus and heading anchor icons.
- If Streamlit can't reach this layout cleanly, say so before working around it.

## 10. Decisions, 2026-11-16

Taken in the UI design pass (quick task 261116-0hq) after the owner chose prototype B and approved `COPY_V2.md`. The owner answered Q1 to Q8 and asked for the recommended answer on the rest.

### Page layout

```
[controls]  Race | Driver | After lap | Risk setting (slider, no number readout)

[decision band, team-tinted]
 Context line                                   | Finish histogram, recommended option
 [ALO] Fernando Alonso, Aston Martin            |  title states the finding
 STAY OUT TO THE FLAG                           |  P1..P20 bars, points bars in team color,
 one or two sentences why                       |  expected-finish marker, podium and
 [close-call note, amber]                       |  points brackets with their shares
 4th 27.5 s behind | P7.5 expected | 76% points |
 ----------------------------------------------------------------------------------
 Race strip, laps 1..N: stints run (solid, compound color), stop markers with their
 cost, "now" at N + 0.5, plan (dashed), pit-window bracket when a stop is planned,
 safety-car footnote; thin-tyre-data note in fog under the current stint

Your options
 Recommended row (full): tyre chip, title, tag, why, four stats with help text,
   P1..P20 probability strip with expected marker, podium and points brackets
 Up to 3 compact rows: chip, title, "N places worse", one-line why, four stats,
   probability strip; no help text
 One "Show all numbers" table for every option

The race so far       gap to leader | stints so far (findings as titles)
How sure are we?      fan chart, full width
How good is this model?  five metrics, each with its small graphic
How to read this page    glossary, icons where a term matches a mark
```

### Decisions

| # | Topic | Decision |
| --- | --- | --- |
| 1 | Pit window | Draw a window only when the recommended plan includes a stop. With no stop planned, the dashed stint runs to the flag and no window appears, even if the model returns a tie window. |
| 2 | Merging options | Merge options whose expected finish, bad-day finish, podium chance and points chance all match at display precision. Keep the more concrete name ("Stay out on Hards") and add "Waiting a lap and deciding then gives the same result." |
| 3 | Other options | Recommended row in full; up to three compact rows below it (title, tag, one-line why, four stats, probability strip, no help text); one "Show all numbers" table at the end. The prototype's one-line "Box again for Hards: 1.1 places worse" comparison is dropped because the compact rows carry it. |
| 4 | Finish chances | The separate finish-chances grid is dropped. Each option row's P1 to P20 probability strip replaces it. "How sure are we?" holds the fan chart alone at full width. |
| 5 | Strip with a stop to come | The dashed plan starts at the planned stop lap in the planned compound's color, with a stop marker showing its cost (green-flag pit loss), and a team-color bracket over the model's tie window when there is one, labelled "any stop here gives about the same finish". |
| 6 | Headline order | 1 "Too close to call" on a close call; 2 "Box this lap" or "Box next lap" when the plan stops then; 3 "Stay out for now" when a stop is planned later; 4 "Stay out to the flag" when no stop is planned and the two-compound rule is met. |
| 7 | White text on team color | Use `team-fill` (section 3) behind white text. Raw team color stays for lines, bars and borders, lightened only below 3:1. |
| 8 | Gap to leader | Keep the full real range; do not clip. No teammate dashes and no leader lines to labels. Every other car is one thin dim grey line. Only the selected driver and the nearest car ahead and behind are labelled, at their line ends, with their gaps. |
| 9 | Model report | Each metric gets the mockup's small graphic: model-versus-grid bars for both Brier scores, a target-zone bar for coverage, dots for team agreement, a band for timing error. |
| 10 | Glossary | Icons only for terms that match a mark on the page (expected-finish dot, bad-day line, 9-in-10 band, podium and points brackets, pit window). No icon for close call or risk setting. |
| 11 | Risk slider | Keep the 0 to 1 slider; hide its number readout and end values with CSS; Aggressive, Balanced and Cautious labels at 14 px with the current one in `chalk`. |
| 12 | Thin tyre data | A plain `fog` note under the current stint in the race strip. Amber stays reserved for the close-call note. |
| 13 | Option tyre chip | The compound the option ends on: the current compound for staying out, the new compound for a stop, both when a merged row covers two. |
| 14 | Dead helpers | Delete `_report_display_values`, `_action_heading`, `_format_strategy_table` and `_strategy_table_html` with their tests; they never reach the page and use the old words. |
| 15 | Lap coordinates | Lap k occupies [k − 0.5, k + 0.5]; "after lap N" is x = N + 0.5 on every lap axis. A stint whose out-lap has started but not finished draws from the stop to N + 0.5 on the new compound. |
| 16 | Fan chart | One team hue at three strengths, the 40th to 60th band strongest and the 10th to 90th weakest, every band at least 3:1 on tarmac; labels "2 in 10", "5 in 10", "8 in 10 races" in `fog` to the right of the last lap; median as a solid chalk line with a tarmac edge, so it reads over the team-colored bands. |
| 17 | Chart headings | Each chart's title and subtitle render in the same column as the chart, so they stay together when columns stack on a phone. |
| 18 | Words | "Tyres" everywhere. Copy follows `COPY_V2.md`. |
| 19 | Small graphics | Streamlit's `st.html` sanitiser removes inline SVG, so the histogram, race strip, model-report graphics and glossary icons are built from HTML boxes styled in `dashboard.css`. |
| 20 | Text on the band | Text inside the decision band uses `--band-fog`: fog lightened toward chalk until it reaches 4.5:1 on that team's band (plain fog drops to 4.31:1 on the 2024 Mercedes band). |
