# Replay page copy, v2

Every user-facing string on the Streamlit replay page, before and after the humanizer pass
(quick task 261116-0hq, step 4). Layout follows prototype B, the race strip. Braces mark values
filled from the model; the examples use Bahrain 2023, Alonso, after lap 15.

Rules: "tyres" everywhere; no dashes in copy; numbers keep their meaning and precision; a chart
title states the finding and a smaller line names the chart; the page names the driver by
surname and never uses a pronoun for them (added in the step 7 review, 2026-11-16).

## Status and error messages

| Where | Before | After |
| --- | --- | --- |
| No eligible races | No eligible races are available because their scheduled lap counts are missing. Refresh the race cache, then choose a supported event. | No race can be replayed: every cached race is missing its scheduled lap count. Refresh the race cache, then reload this page. |
| Race without lap count | This race cannot be replayed because its scheduled lap count is missing. Refresh the race cache or choose another race. | This race has no scheduled lap count, so it can't be replayed. Refresh the race cache or pick another race. |
| Replay failed | Replay could not be built for this selection. Check the local cache and eligible cutoffs, then retry or choose another race. | This replay failed to build. Pick another lap or race; the full error is in the server log. |
| Loading | Building replay... | Simulating the rest of the race... |
| Cutoff unavailable | This cutoff is unavailable. Choose another lap or race. | There's no replay for this lap. Pick another lap or race. |
| No strategy | No strategy is available at this lap. Choose another cutoff or race. | The model has no strategy for this lap. Pick another lap or race. |
| Report missing | The ten-race model report is unavailable. | The model report for the ten test races didn't load. |
| Gap chart empty | No completed lap times are available for this cutoff. | No laps are complete yet, so there's no gap chart. |
| Stint chart empty | No tire stint data is available at this cutoff. | No tyre stints yet at this lap. |
| Fan chart empty | Projected finish is unavailable for this lap. | No projection for this lap. |
| Finish chances empty | Finish chances are unavailable for this lap. | No finish chances for this lap. |

## Decision band

| Where | Before | After |
| --- | --- | --- |
| Context line | Bahrain Grand Prix 2023, after lap 15 of 57, balanced risk setting | unchanged |
| Driver line | Fernando Alonso, Aston Martin | unchanged |
| Headline, no stop planned and allowed | Stay out for now | Stay out to the flag |
| Headline, stop planned later | Stay out for now | Stay out for now |
| Headline, stop now / next lap / close | Box this lap / Box next lap / Too close to call | unchanged |
| Lede, stay out with rule met | Wait and decide next lap: the current Hard set remains the better call for the laps left. | {Alonso} is on fresh {Hards} and has used both compounds, so there's no need to stop again. Another stop costs {1.1} places on average. |
| Lede, stay out without a planned stop (generic) | {Action}: keep the current tires for the laps left. | Keep the current tyres to the flag. |
| Lede, new tyres pay back the stop | {Action}: fresh {Hard} should make back the stop loss as the {Soft} loses pace. | Fresh {Hards} should win back the {24} seconds a stop costs as the {Softs} fade. |
| Lede, run the old set first | {Action}: the {Soft} still has useful pace, so use it through the in-lap before switching to fresh {Hard} for the final stint. | The {Softs} still have pace. Run them to the stop, then fit {Hards} for the last stint. |
| Lede, tied stop window | Stopping between laps {17} and {20} gives a similar result, so keep the current tires and reassess next lap. | Any stop between laps {17} and {20} gives about the same result, so there's no rush. Look again next lap. |
| Close-call note | Close call: {Box this lap (Hard)} is only {0.3} places worse on average. | Close call: {boxing this lap for Hards} is only {0.3} places worse on average. |
| Thin tyre data note | The tire estimate uses limited data at this lap. | Uncalibrated: there's too little tyre data at this lap, so the model falls back to prior estimates. Treat this call as a rough guide. (Shown whenever the call rests on fallback estimates; verifier warning W-2, 2026-11-16.) |
| Fact: position | (not shown) | **{4th}** {27.5} s behind the leader |
| Fact: expected finish | (in option row only) | **{P7.5}** expected finish |
| Fact: points chance | (in option row only) | **{76%}** points chance |

The three text reasons (tyres, pit window, safety car) become the race strip below. Their old
copy, for the record:

| Before | After (where it now lives) |
| --- | --- |
| Tyres: The current {Soft} tire is losing about {0.28} seconds per lap; wear uncertainty is {0.02} seconds per lap. | Note under the strip: Tyres: the {Softs} are losing about {0.28} s a lap, give or take {0.02} s. |
| Tyres: There is not enough tire data to estimate pace loss at this lap. | Note under the strip: Tyres: the {Hards} are too new to measure wear yet. |
| Pit window: Stops in this window give a similar expected finish. | Strip window bracket, labelled: any stop here gives about the same finish |
| Pit window: No tied laps. The model finds different results for each available stop choice. | (no window drawn) |
| Safety car: Historical rate implies about a {34%} chance of one before the flag. | Strip footnote: Safety car: {1.0%} per lap, about {1 in 3} races before the flag |

## Race strip (new, from prototype B)

| Where | After |
| --- | --- |
| Title, no more stops | {Alonso} has made {one} stop and needs no more |
| Title, stop planned | {Alonso} stops this lap / next lap / in {3} laps for {Hards} |
| Title, a stop still required by the two-compound rule | {Alonso} still has to stop once |
| Sub | Laps 1 to {57}. Solid bars are laps already run; the dashed bar is the plan. |
| Stint label | {Softs}, laps {1} to {14} |
| Stop marker | stop, about {24} s (the model's green-flag pit loss) |
| Now marker | now, after lap {15} |
| Planned stint | {Hards} for the last {42} laps |
| Phone text version | {Softs} for laps {1} to {14}, a stop of about {24} seconds, then {Hards} from lap {15} with no further stop: {42} laps to go. |

## Finish histogram (new, from prototype B)

| Where | After |
| --- | --- |
| Title | {Staying out on Hards}, {Alonso} scores points in about {3 in 4} races |
| Sub | Share of {10,000} simulated races ending in each position |
| Marker | expected P{7.5} |
| Brackets | Podium (P1 to P3): {19%} / Points (P1 to P10): {76%} |

## Your options

| Where | Before | After |
| --- | --- | --- |
| Section sub | Best first. Each option uses {10,000} simulated races. | Best first. Each one is {10,000} simulated races from this lap to the flag. |
| Title, stay out (merged with "wait") | Wait and decide next lap | Stay out on {Hards} |
| Title, wait (not merged) | Wait and decide next lap | Stay out for now, decide next lap |
| Title, stop now | Box this lap (Hard) | Box this lap for {Hards} |
| Title, stop in 1 lap | Box in 1 lap (Hard) | Box next lap for {Hards} |
| Title, stop later | Box in {3} laps (Medium) | Box in {3} laps for {Mediums} |
| Why, recommended | This choice gives the strongest balance of expected result and bad-day risk. | Best mix of average result and bad-day risk at this risk setting. |
| Why, recommended and merged | Stopping between laps {17} and {20} gives a similar result, so keep the current tires and reassess next lap. | No more stops. Waiting a lap and deciding then gives the same result. |
| Why, other options | It finishes about {1.1} places behind the recommended choice on average. | (dropped: the tag already says it) Stop now: Another stop costs about {24} seconds in the pits. Stop later: Run {3} more laps on the {Softs}, then fit {Mediums}. |
| Tags | Recommended / {1.1} places worse | unchanged |
| Never-stop row | Never stop. Not allowed. A driver must use two different tire compounds in a dry race. | Never stop. Not allowed. Dry races require two different tyre compounds. |
| Stat labels | Expected finish, Bad-day finish, Podium chance, Points chance | unchanged |
| Help: expected | Average across simulated races | Average over all simulated races |
| Help: bad day | Average of the worst 1 in 10 races | unchanged |
| Help: podium | Finishes in P1 to P3 | Races ending P1 to P3 |
| Help: points | Finishes in the top 10 | Races ending in the top 10 |
| Comparison line (B) | (none) | Box again for {Hards}: {1.1} places worse. For {Mediums}: {2.7} worse. For {Softs}: {4.1} worse. |
| Expander | Show all numbers | unchanged |
| Table headings | Option, Expected finish, Spread, Bad-day finish, Podium chance, Points chance, 9-in-10 range | Option, Expected finish, Bad-day finish, Podium chance, Points chance, 9-in-10 range (Spread dropped, per DESIGN_SYSTEM_V2 section 6) |

## The race so far

| Where | Before | After |
| --- | --- | --- |
| Section sub | (none) | Only laps finished by the end of lap {15} are shown. |
| Gap chart title | Gap to leader | {Alonso} is {4th}, {27.5} s behind {Verstappen} |
| Gap chart sub | Fernando Alonso is 27.5 seconds from the lead after lap 15. | Gap to the leader, laps 1 to {14} |
| Stint chart title | Stints so far | {16} of {20} drivers have stopped; {Alonso} is on {Hards} |
| Stint chart sub | Fernando Alonso has run Soft. The recommended next set is Hard. | Tyre stints so far, in running order |
| Axis: gap | Gap to leader (s) | unchanged |
| Tooltips | Driver, Lap, Gap to leader, Compound, Start lap, Laps completed | unchanged |

## How sure are we?

| Where | Before | After |
| --- | --- | --- |
| Fan chart title | Projected finish by lap | {Alonso} most likely finishes around P{7} |
| Fan chart sub | Fernando Alonso has a median projected finish of P8.0 at lap 57. | Projected position for each lap left. Shaded bands hold 8, 5 and 2 in 10 races. |
| Band labels | 10th–90th, 25th–75th, 40th–60th | 8 in 10 races, 5 in 10, 2 in 10 |
| Finish chances title | Finish chances | Staying out puts him in the points in {76%} of races |
| Finish chances sub | Chance at each finishing position for the ranked options. | Chance of each finishing position, by option |
| Finish chances caption | Shading shows the share of simulated finishes at each position. | Darker means more likely. |
| Row labels | Wait and decide next lap / Box now H / Box +2 lap H | Stay out / Box now, Hards / Box in 2, Mediums |
| Tooltip | Action, Finishing position, Chance | Option, Finishing position, Chance |

## How good is this model?

| Where | Before | After |
| --- | --- | --- |
| Section sub | Ten races, 10,404 driver and cutoff predictions, and 388 observed stops. | Tested on ten 2023 to 2025 races using only what was known at each lap: {10,404} predictions and {388} real pit stops. |
| Podium verdict | Better than starting order | unchanged |
| Podium meaning | Podium Brier: model 0.047 versus grid baseline 0.080; lower is better. | Podium calls score {0.047} against {0.080} for just trusting the grid (Brier score; lower is better). |
| Points verdict | Better than starting order | unchanged |
| Points meaning | Points Brier: model 0.144 versus grid baseline 0.190; lower is better. | Points calls score {0.144} against {0.190} for the grid. |
| Coverage verdict | Below target | Computed: On target (85% to 95%), Slightly overconfident (80% to 85%), Overconfident (below 80%), Slightly cautious or Too cautious (above 95%) |
| Coverage meaning | The 90% finish range covered 83.7% of classified results (7,667 of 9,157). Target: 85% to 95%. | Averaged over the ten races, the 9-in-10 range held the real finish {83%} of the time ({7,667} of {9,157} finishes overall). It should be 85% to 95%. |
| Agreement verdict | Needs work | Computed: Usually (60% or more), Sometimes (30% to 60%) or Rarely matches the pit wall |
| Agreement meaning | Top strategy matched observed team calls in 16.9% of 388 stop events. | The model's top call matched what the team did at about {1 in 6} of the {388} real stops. |
| Timing verdict | Often several laps apart | Computed: Close on timing (1.5 laps or less), A few laps off (up to 3), Often several laps off |
| Timing meaning | The recommended stop differed from the observed stop by 3.69 laps on average. | When a team stopped, the model's suggested lap was {3.7} laps away on average. |

## How to read this page

| Term | Before | After |
| --- | --- | --- |
| Expected finish | Average finishing position across all simulated races. | The average finishing position over all simulated races. |
| Bad-day finish | Average finishing position in the worst 1 in 10 simulated races. | The average finish in the worst 1 in 10 simulated races. It shows how far things can go wrong. |
| Podium chance | Share of simulated races ending in P1, P2, or P3. | The share of simulated races that end in P1, P2 or P3. |
| Points chance | Share of simulated races ending in the top 10. | The share that end in the top 10. |
| 9-in-10 range | Nine of every ten simulated races finish inside this interval. | Nine in ten simulated races finish inside this range. |
| Pit window | Laps where a stop gives about the same expected result. | The laps where stopping gives about the same expected finish, so the exact lap matters little. |
| Close call | The top two options are within two standard errors in the simulation. | The top two options are so close that the simulation can't reliably separate them (less than two standard errors apart). |
| Risk setting | Aggressive favors the average; cautious protects the bad-day result. | Aggressive goes for the best average finish. Cautious protects against a bad day. Balanced weighs both. |
| Footer | Unofficial project, not affiliated with Formula 1. Data: FastF1, OpenF1, and Jolpica. | unchanged |

Unchanged everywhere: page title "F1 strategy replay"; control labels Race, Driver, After lap,
Risk setting; risk labels Aggressive, Balanced, Cautious; section headings.

Not on the page: `_report_display_values`, `_action_heading`, `_format_strategy_table` and
`_strategy_table_html` only feed tests and still use the old words ("Mean finish", "Top-10
chance"). Step 6 removes them with their tests.
