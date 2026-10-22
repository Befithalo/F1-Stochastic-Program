---
phase: 01-foundation-data
plan: 06
subsystem: data
tags: [http, rate-limit, requests-cache, jolpica, track-status, race-control, offline-tests]

requires:
  - phase: 01-03
    provides: SourceError / RateLimitedError contract, schema track_status codes
  - phase: 01-05
    provides: import-ban POLICY already allowing _http -> jolpica/openf1 and requests only in _http
provides:
  - RateLimitedClient: the single network door (paced, hourly window, 429/5xx retries, JSON cache)
  - JsonGetter / HttpSession protocols so adapters and tests never depend on requests
  - JolpicaClient (season_schedule, results, pit_stops) and parse_duration_s
  - derive_track_status: race-control messages to track status codes 1/2/4/5/6/7
affects: [01-08]

tech-stack:
  added: []
  patterns:
    - "Network access only via JsonGetter; tests inject a fake session, fake clock and recording sleep"
    - "Third-party payloads are shape-validated and fail as SourceError naming the path"
    - "Track status is a small state machine with documented priority, timed transitions flushed lazily"

key-files:
  created:
    - src/f1si/data/sources/_http.py
    - src/f1si/data/sources/jolpica.py
    - src/f1si/data/sources/track_status_map.py
    - tests/data/test_http.py
    - tests/data/test_jolpica.py
    - tests/data/test_track_status_map.py
  modified: []

key-decisions:
  - "Pacing is applied before sending and measured from the last real network call; cache hits are never recorded"
  - "429 waits honour numeric Retry-After (capped at 3600 s), else 5/15/45/90 s; fifth 429 raises RateLimitedError(retry_after_s=last wait)"
  - "A safety car deployment replaces any active VSC and ends a red flag"

patterns-established:
  - "Constructor injection of echo/sleep/clock/session for every timing-sensitive component"

requirements-completed: [DAT-01]

duration: ~40 min
completed: 2026-10-22
---

# Phase 1 Plan 06: Network Building Blocks Summary

**One rate-limited, JSON-caching HTTP door (OpenF1 at or under 30 calls per minute, Jolpica at or under 450 per hour), a validated Jolpica client for schedule, results with grid and paginated pit stops, and a documented race-control to track-status state machine, all proven offline.**

## Performance

- **Tasks:** 2 of 2 complete
- **Tests:** 226 pass (was 158): 22 in `test_http.py`, 24 in `test_jolpica.py`, 22 in `test_track_status_map.py`; no test takes over 2 s
- ruff check, ruff format --check and mypy strict clean on the whole tree; no real network is touched by any test

## Accomplishments

- `_http.RateLimitedClient` is the only module importing `requests` / `requests_cache` (grep over `src` prints only this file; import-ban guard still green with the existing POLICY entries, no POLICY change needed). The default session is a `CachedSession` on SQLite with `serializer="json"`, `allowable_codes=(200,)`, a User-Agent with the public repo URL, and TLS verification left on.
- Behaviour proven with fakes: minimum spacing, rolling hourly window with a "hourly limit" message, Retry-After (case-insensitive, capped), 4-step 429 backoff then `RateLimitedError(retry_after_s=90.0)`, 5xx backoff 5/15 s then `SourceError`, network errors turned into one line mentioning the internet connection, non-JSON bodies, 404 to None, https-only base URL, path validation, 12 h versus never expiry.
- `JolpicaClient` returns `JolpicaRace` items (UTC start, 00:00 when no time given), a results table with Int64 driver_number/grid/position/laps (grid 0 kept, position NA for "R"), float points and `total_time_s`, and all pit stops across pages with `parse_duration_s`. Every payload is shape-checked; failures name the path.
- `derive_track_status` implements the mapping table in its module docstring, including the priority order, timed VSC-ending and safety-car-in transitions, pit-exit green ignoring, per-sector yellows, and case/whitespace-tolerant matching.

## Task Commits

1. **Task 1: Rate-limited caching HTTP client** - `53dd02b` (feat)
2. **Task 2: Jolpica client and track-status mapping** - `154ab27` (feat)

## Deviations from Plan

None in scope. `pyproject.toml` was not changed: `requests_cache` ships type information, so no mypy override was needed. The `HttpSession` protocol is satisfied by `CachedSession` directly (no cast).

Design notes where the plan was silent:

- Pacing is checked before sending, because whether a response is cached is only known after the call. A cache hit therefore can wait out the remaining interval if it directly follows a network call, but it is never recorded, so it neither delays later calls nor uses hourly quota. Cost: at most one short wait per cached call after a real one.
- Driver-scope flags (blue, black and white) and any Flag message containing "PIT EXIT" are ignored; a SAFETY CAR DEPLOYED clears an active VSC state; "SAFETY CAR IN THIS LAP" with no later leader lap end leaves the safety car on until a Track-scope green.
- `RateLimitedClient.close()` was added (closes the SQLite cache the client created).

## Decisions to log (plan 01-08 or the next DECISIONS.md owner; next free number after DEC-035)

- **HTTP pacing, caching and retries:** OpenF1 spacing 2.1 s (set in 01-08), Jolpica 0.5 s plus 450 network calls per rolling hour (limits are 4/s and 500/h); only real network calls are paced or counted; cache hits are free. Retry 429 up to four times (Retry-After if numeric, capped at 3600 s, else 5/15/45/90 s) then `RateLimitedError`; retry 5xx twice (5 s, 15 s); network errors are a single-line `SourceError`; HTTP 404 returns None.
- **Cache format:** SQLite via requests-cache with the JSON serializer (never pickle), only HTTP 200 stored, historical data never expires, schedule responses expire after 12 h. Reason: a restored/swapped cache must not be able to execute code.
- **One network door:** `requests`/`requests_cache` only in `_http.py`, enforced by the import-ban POLICY; adapters depend on the `JsonGetter` protocol so tests are offline.
- **Track status derived from OpenF1 race control:** priority red 5 > SC 4 > VSC deployed 6 > VSC ending 7 > yellow 2 > green 1; VSC ending reverts at next Track green/clear or after 15 s; safety car "in this lap" ends at the first leader lap end strictly after the message (or earlier Track green); pit-exit green and driver-scope flags ignored; SC deployed replaces VSC and ends red; first row appears at first change (implicit green start). Lower fidelity than the official feed; the 15 s and lap-end timings are assumptions.
- **Jolpica payloads are untrusted:** shape validated, ints only via `int()` of API strings, `SourceError("Unexpected response from Jolpica for PATH: WHAT")`.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-01-21 (payload validation), T-01-22 (JSON serializer, 200 only), T-01-23 (pacing and bounded backoff), T-01-24 (https-only base URL, verification on) and T-01-25 (path validation, params passed separately) are implemented and tested.

## Next Phase Readiness

Plan 01-08 can build the OpenF1 source on `RateLimitedClient(min_interval_s=2.1, max_per_hour=None)`, `JolpicaClient.create(...)` and `derive_track_status(race_control, leader_lap_end_s=...)`, using the leader lap end times from the lap table. The literal cache file location is chosen by the caller via `cache_dir`.

## Self-Check: PASSED

- Files exist: `_http.py`, `jolpica.py`, `track_status_map.py` in `src/f1si/data/sources/`; `test_http.py`, `test_jolpica.py`, `test_track_status_map.py` in `tests/data/`.
- Commits `53dd02b` and `154ab27` exist on main.
- Full suite 226 passed; ruff, ruff format --check and mypy strict clean; `_http.py` has `serializer="json"`, `allowable_codes=(200,)`, `Retry-After`, `NEVER_EXPIRE`, `RateLimitedError`, and no `verify=False` or `pickle`.
