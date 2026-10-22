# Phase 1 explained: foundation and data

This page is for you, the owner. It explains what Phase 1 built, in plain words, so you can talk about every part of it with confidence. No coding background is assumed. Words in code font, such as `cache`, are names you will see in the files.

## What was built and why

**The big goal of the whole project** is a program that tells you when an F1 driver should pit, and how sure it is. Before anything clever can be built, the program needs two things: trustworthy race data, and proof that it never peeks at the future. Phase 1 builds exactly those two things.

**The repository and the safety gate (CI).** The project lives in a folder of code (a "repository"). Every time code is pushed to GitHub, a robot called CI (continuous integration) runs all the checks on two kinds of computers: Linux (`ubuntu-latest`) and Windows (`windows-latest`). If any check fails, the build goes red. The checks are: ruff (spelling and style for code), mypy in strict mode (checks that the kinds of values match, like a spell checker for types), and pytest (about 350 small programs that test the real programs).

**One command loads the data.** `uv run f1si load` downloads Grand Prix races for 2023, 2024, 2025 and 2026 and saves them on your own computer. The data comes from two free services: OpenF1 (lap times, tyres, weather, race-control messages) and Jolpica (the race calendar, starting grid, final results and pit stops). The original plan used a tool called FastF1, but FastF1 began to need a login (the server answered "401, not allowed"). So the data source was changed to OpenF1 plus Jolpica, which need no login. This is recorded as a decision (DEC-005 in `DECISIONS.md`). Being polite matters: the loader waits between requests so it never hammers these free services, and it remembers every answer so a second run makes no new requests.

**The local cache.** Everything the loader downloads is saved into one file, `data/f1si.duckdb`, using a database called DuckDB. Think of it as a spreadsheet file with many tabs (laps, pit stops, weather and so on). Each race is saved all-or-nothing: if the program is stopped halfway through a race, that race is not saved at all, so you never get a half-finished race. Running the command again only fetches the races that are missing. The real numbers on your machine: **87 races cached**, which is **70 in-sample** (every 2023, 2024 and 2025 Grand Prix: 22 + 24 + 24) and **17 locked 2026 races**, with zero failures.

**The three doors.** The cache is not read directly. There are three doors, each with a different job:

1. The **as-of door** answers "what did we know at lap 15?". It is the only door a strategy will ever use.
2. The **results door** gives final results (who won, points). It is a separate door so a strategy cannot read the winner by accident while it is supposed to be pretending the race is still running. Only the scoring code of a later phase may use it.
3. The **out-of-sample door** opens the 2026 races. The 2026 rules are different (narrower tyres, less grip), so those races are kept locked until the final exam of the project. Asking for a 2026 race at the first two doors gives an error, and there is no switch that unlocks it.

**The leader's clock (a key idea).** "As of lap 15" means "the moment the race leader finished lap 15". At that moment the leader has finished 15 laps, but every other car is still somewhere on lap 15 and has finished **at most 14**. This is how it really is on a pit wall, and the program reproduces it. If the cutoff were instead the finish of each car's own lap 15, then a car that is 20 seconds behind would show information from 20 seconds in the leader's future.

**Two guards against looking into the future.** Writing "no look-ahead" in a document is not enough, because code written later could break it by accident. So two automatic tests run on every push:

- The **import guard** reads the source code without running it and fails if any file imports something it is not allowed to. For example, only one file may talk to the database, only one file may talk to the internet, and only one file may create random numbers.
- The **scramble test** is cleverer. It takes a race, replaces everything after the cutoff with garbage (random numbers, shuffled rows, rows deleted), then runs the code again. If the output changes at all, the code was using the future. This works because an answer that does not change when the future changes cannot depend on the future.

To prove the guards really work, the project plants **deliberate leaks** (files in `tests/fixtures/`) and checks that the guards catch them. CI also has a "canary" step on Linux: it copies a planted leak into the real code and requires the import guard to fail. If the canary ever passed quietly, CI would turn red. I also ran a mutation check: I removed the time cutoff from the real query in `src/f1si/data/_snapshot.py` and the scramble test failed, as it should; then I restored the file.

**Regulation eras and the 2026 lock.** Every race is tagged with its rules era: `ground_effect_2022_2025` for 2023 to 2025, and `reg_2026` for 2026, which is marked out-of-sample (a fair exam: models never train on it).

**Seeded randomness.** Whenever the project needs random numbers it uses one function that takes a "seed" (a starting number). The same seed always gives the same random stream, so any result can be reproduced exactly. The project also makes fake (synthetic) races from known settings, so later models can be tested on cases where the right answer is known.

**The stint plot.** `uv run f1si plot bahrain-2023` draws one small chart per driver showing lap time lap by lap, coloured by tyre (red soft, yellow medium, white hard). Pit laps and safety-car laps are faded rather than hidden, and a tyre wearing out shows as lap times drifting upward inside a stint. Real facts for Bahrain 2023: 20 drivers, 1,058 laps, and a virtual safety car on lap 41.

**DECISIONS.md.** Every method choice, with the reasons and the alternatives rejected, is written down in `DECISIONS.md` (51 numbered entries at the end of this phase). It is the project's memory, and the best thing to read before an interview.

## How the pieces connect

```
uv run f1si load
       |
       v
  cli.py  --- chooses the source (real by default, synthetic for demos)
       |
       v
  loader.py  (resumable; waits out rate limits; collects failures)
       |
       v
  sources/openf1.py + sources/jolpica.py  (via sources/_http.py, the one network door)
       |      raw answers  ->  tidy tables on the "lights out = 0 seconds" clock
       v
  schema.py  (validate the whole race first)  +  derive.py  (lap cutoffs, track status)
       |
       v
  _db.py  (one transaction per race, then the "complete" marker)  ->  data/f1si.duckdb
       |
       +--> asof.py / _snapshot.py   -> snapshots for strategy code  (guarded by the scramble test)
       +--> results.py               -> final results, scoring only
       +--> out_of_sample.py         -> locked 2026 races
       +--> plots/stints.py          -> reports/bahrain-2023.png
       |
CI (ci.yml): ruff, mypy, pytest, import guard, canary   |   real-data.yml: weekly real-data check
```

In words: the command picks a source, the loader asks the source for each race, the race is checked and enriched, and the database layer saves it safely. After that, everything that reads data goes through one of the three doors. CI sits around the whole thing and runs the guards on every push.

## File-by-file tour

Paths are relative to the repository folder. `__init__.py` files are empty package markers and are left out.

### The package `src/f1si`

- `src/f1si/__main__.py` lets you run the program with `python -m f1si`; it just calls the command line.
- `src/f1si/cli.py` is the command line: `load` (fill the cache), `races` (list what is cached, with its era) and `plot` (draw the stint chart). It decides which data source to use and turns errors into short messages that say what to do next.
- `src/f1si/eras.py` maps a season to its regulation era (2023-2025 to `ground_effect_2022_2025`, 2026 to `reg_2026`, out-of-sample) and raises a clear error for a season it does not know.
- `src/f1si/paths.py` says where files live (`data/`, the database file, the HTTP answer cache, `reports/`). It creates nothing by itself.
- `src/f1si/rng.py` is the one place random-number generators are made, from a seed, so every result is reproducible.
- `src/f1si/data/schema.py` defines the tables every source must produce (races, entries, laps, stints, pit stops, weather, race control, track status, results), the rule for when each row becomes visible, and the checker that rejects a malformed race before it is saved.
- `src/f1si/data/_db.py` is the only file that talks to DuckDB. It saves each race in one all-or-nothing step, reads tables back, and turns a locked-file problem into a friendly "close the other program" message.
- `src/f1si/data/derive.py` computes things that do not come from any source: the "lap cutoffs" (the leader's finish time for each lap) and the per-lap track status (green, yellow, safety car and so on).
- `src/f1si/data/errors.py` lists the data layer's error types, each with a message that tells you what to do (missing cache, busy cache, unknown race, locked 2026 race, lap out of range).
- `src/f1si/data/slugs.py` turns a race name into a readable id such as `bahrain-2023`.
- `src/f1si/data/loader.py` runs a load: skips races already complete, waits out rate limits, keeps going when one race fails and lists the failures at the end.
- `src/f1si/data/_snapshot.py` builds the "what was known at the cutoff" snapshot: it keeps only rows visible at the leader's lap time and rebuilds stints, pit events and positions from those rows only. It is private; only the two doors import it.
- `src/f1si/data/asof.py` is the public as-of door: `catalog()` for calendar facts, `AsOfAccessor` for a snapshot at lap N or at `RACE_END`, and the history of earlier races.
- `src/f1si/data/results.py` is the results door for final classification, points and times of in-sample races. Only later scoring code may import it.
- `src/f1si/data/out_of_sample.py` is the door for the locked 2026 races, reserved for the final holdout evaluation.
- `src/f1si/data/sources/synthetic_source.py` serves seeded fake races. CI and the demo use it, so no internet is needed.
- `src/f1si/data/sources/_http.py` is the one network door: a polite web client that spaces its requests (OpenF1 2.1 s apart, Jolpica 0.5 s apart and at most 450 an hour, remembered between runs), saves every answer in a safe JSON cache (answers for recent races are kept for hours rather than forever, and a race that came back incomplete has its saved answers thrown away) and retries sensibly.
- `src/f1si/data/sources/jolpica.py` reads the race calendar, grid, official results and pit stops from Jolpica, and refuses answers that do not have the expected shape.
- `src/f1si/data/sources/openf1.py` is the real data source: it combines OpenF1 timing with Jolpica facts into schema-valid races on the lights-out clock, and runs completeness checks (for example, 18 to 22 cars).
- `src/f1si/data/sources/track_status_map.py` rebuilds the track status (green, yellow, safety car, virtual safety car, red flag) from OpenF1's race-control messages, because OpenF1 has no direct feed for it.
- `src/f1si/synthetic/generator.py` makes seeded fake races from a written lap-time formula and keeps the true settings so later models can be checked against known answers.
- `src/f1si/plots/stints.py` prepares the stint-plot data (a plain function of a snapshot, so the scramble test can check it) and draws the chart with matplotlib.

### Guards, fixtures and shared test setup

- `tests/guards/import_scan.py` is the import guard: it reads code without running it and checks every import against one policy table, including tricks like `importlib` and `__import__`, and it judges the private storage modules by identity, so reaching them through any other module (for example `from f1si.data.asof import _db`) is caught too.
- `tests/guards/scramble.py` is the scramble tool: it replaces the future with garbage while leaving everything knowable untouched, and compares outputs exactly.
- `tests/guards/consumers.py` is the list of every piece of code that reads through the as-of door; each one must be registered so the scramble test checks it.
- `tests/fixtures/leaky_consumer.py` is a deliberately leaky file that opens the database directly and averages the whole race. Both guards must catch it.
- `tests/fixtures/leaky_through_accessor.py` holds three leaks that use only the public door (asking for a later lap, for the whole race, for the history of the next race). Only the scramble test can catch these.
- `tests/fixtures/leaky_reexport.py` leaks through a re-exported private module, without naming `duckdb`. The import guard flags it, and at run time it cannot even run because the door modules no longer expose the storage module.
- `tests/conftest.py` builds a seeded fake dataset and a database holding it, shared by many tests.

### Automation and notes

- `.github/workflows/ci.yml` is the safety gate that runs on every push, on Linux and Windows: ruff, ruff format check, mypy strict, pytest with coverage, and on Linux the canary step.
- `.github/workflows/real-data.yml` is the weekly (and manual) check against the real services. It is a separate workflow and not a required check, so a failure turns only that run red.
- `DECISIONS.md` is the decision log: for each choice, the context, decision, reasons, rejected alternatives and consequences.

## Interview questions

### Q1. Why does "as of lap N" use the leader's clock, and what does that do to the other cars?

At lap N the cutoff is the moment the race leader finishes lap N. That is a single moment in time that everyone shares, like a snapshot on the pit wall. At that moment the leader has finished N laps but every other car is still on its way to the line, so it has finished at most N-1 laps. The code reproduces this exactly: it keeps only rows that were knowable by that moment. If it used each car's own lap-N finish instead, a slow car would see data from the leader's future. The cutoffs are worked out once when the race is loaded (the stored cutoff for lap n is the earliest finish time of lap n), so a query never has to look at other cars' future laps to find the cutoff.

### Q2. Why do final results live behind a separate door?

Final results (who won, points, total time) are facts that only exist after the race ends. If they sat in the same place as the lap data, a strategy could use "this car finished P3" while pretending to decide at lap 20, which is a look-ahead leak that makes any backtest look better than reality. By putting them behind their own module that only the scoring code may import (and that the import guard enforces), the strategy side physically cannot read them, and there is no flag on the as-of door to switch them on. The same idea protects the 2026 races: they sit behind a third door until the final exam.

### Q3. How does the scramble test prove that code does not read the future, and what are its limits?

The test takes a race at a cutoff, keeps everything knowable at that moment exactly as it was, and replaces everything after it with garbage: random values, shuffled rows, about a fifth of the rows deleted, and even a junk race from a later year. Then it runs the code on the real database and on the scrambled one and demands exactly the same output. If the future can change the answer, the answer used the future. The test runs on many random races, laps and seeds with the hypothesis library. I proved that it bites: removing the time cutoff from the real query made it fail. The honest limits (DEC-002): Python cannot be sandboxed, so the import guard stops accidents and obvious bypasses, not a determined attacker; asking for a lap beyond the race reveals the race length; and a consumer that only checks whether a later lap exists, without reading its rows, may slip past on some generated examples.

### Q4. Why does CI use synthetic data while real data runs weekly?

CI must be fast, free of internet problems and deterministic, because a red build should mean "my code is wrong", not "a website was slow". Synthetic races are made from a seed, so they are identical every time, and they come with known true settings. The real-data check (`real-data.yml`) runs weekly in a separate, non-required workflow, so it can catch real-world surprises (a changed field, a missing race) without ever blocking a push. One caveat I should state honestly: whether OpenF1 allows requests from GitHub's servers has not been verified yet; it will be known the first time the weekly job runs, and a failure there does not affect CI.

### Q5. What does "out-of-sample era" mean, and why is 2026 locked?

"In-sample" data is what models are built and tuned on; "out-of-sample" data is kept hidden so it can give an honest final score. The 2026 regulations changed the cars (narrower tyres, less grip, more one-stop races), so 2026 is a different world from 2023 to 2025. Mixing it in would blur the models, and peeking at it while tuning would make the final test meaningless. So all 17 loaded 2026 races carry the `reg_2026` tag, show `yes (locked)` in `uv run f1si races`, raise an error at the as-of and results doors, and can only be opened by the holdout door that the final evaluation phase will use once.

## Good to know

- **The weekly real-data job** is a separate workflow named "Real data (non-blocking)". It is not a required check, so if it fails only that run turns red; its result line ("Result: success" or "Result: failure") is on the run's summary page. GitHub may switch off scheduled jobs after 60 days without repository activity. To turn it back on, open the Actions tab, pick the workflow and click "Enable workflow".
- **Unverified**: OpenF1 access from GitHub's servers has not been tested yet. The first run will tell. If it fails, the same tests still run on your own computer (`uv run pytest -m network`).
- **Terms of use**: OpenF1 is free for personal, non-commercial use, and Jolpica is a free community service. The project does not republish the data; `data/` and `reports/` are never committed.
- **Known data caveats.** Three Bahrain 2023 pit in-laps have no OpenF1 lap end time (drivers 16, 31 and 81, laps 40, 42 and 14). They are only visible at the end of the race, and the plot skips them and says how many. The 2026 race in Malaysia has an odd name from the source, `bahrain-grand-prix-in-malaysia-2026`; it is correct for the data and was left as is. The pit-lane start rule was checked against all 4 real cases where a car had no grid slot, and it behaved correctly.
- **Upstream gaps**: none. All 70 in-sample races loaded, so no `01-UPSTREAM-GAPS.md` file exists.
- **Run everything again** from PowerShell, in the project folder:

```powershell
cd $HOME\Documents\f1si
uv sync
uv run f1si load
uv run f1si races
uv run f1si plot bahrain-2023
uv run pytest
```

`uv run f1si load` is safe to run again at any time: finished races are skipped. The plot is written to `reports\bahrain-2023.png`.
