"""OpenF1 + Jolpica race source (D-05, D-06, D-07, D-08).

OpenF1 supplies the timing data of each Race session (laps, stints, race control, weather, the
driver list); Jolpica supplies what OpenF1 lacks: the round number, circuit id, grid, official
classification and the pit-stop list. FastF1 can be added later as one more `RaceSource` (D-08).

Data credits and terms: OpenF1 (https://openf1.org) data is used for personal, non-commercial
analysis and is never republished; the local cache (`data/`) is gitignored. Jolpica
(https://github.com/jolpica/jolpica-f1) is an Ergast-compatible API; its responses are cached in
the same folder. Both services are free and rate limited, so every call is paced and cached by
`f1si.data.sources._http`.

Race clock (all `*_s` columns): t = 0 is the earliest lap-1 `date_start` of any car, which is
lights out. Then, per driver::

    lap_start_s = date_start - t0            (lap 1 with no date_start: 0.0)
    lap_end_s   = lap_start_s + lap_duration (no duration: the same driver's next lap_start_s)
    lap_time_s  = lap_duration, else lap_end_s - lap_start_s
    tyre_life   = tyre_age_at_start + (lap_number - stint lap_start) + 1

Race-control and weather rows are placed on the same clock, so messages sent before lights out
have negative `t_s`.

Provenance of `entries` (look-ahead guard): entries are visible from lap 0, so each column may use
only facts fixed by lights out. Nothing from the results feed except the grid slot, the driver
identity and the team is used: no status, no laps completed, no position.

* `pit_lane_start` is Jolpica grid 0 AND an OpenF1 lap-1 timing record for the car. A grid-0 car
  that never took the start has no lap-1 record. This is the best signal the two feeds offer, but
  it is honest to say it is not a pre-race one: the record appears during lap 1 (DEC-049, DEC-056).
* `start_compound` and `start_tyre_age` come only from OpenF1 stint number 1 (its `lap_start` may
  be null or 1). If that stint is absent they stay NULL and the fetch prints a note; the second
  stint is never taken for the first (that is the tyre after the first stop).
"""

import time
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final, Literal

import pandas as pd

import f1si
from f1si.data.slugs import event_slug
from f1si.data.sources import NormalizedRace, RaceRef, SourceError
from f1si.data.sources._http import JsonGetter, RateLimitedClient
from f1si.data.sources.jolpica import JolpicaClient, JolpicaRace
from f1si.data.sources.track_status_map import derive_track_status

OPENF1_BASE_URL: Final = "https://api.openf1.org/v1"
MIN_ENTRIES: Final = 18
MAX_ENTRIES: Final = 22
MIN_DRIVERS_WITH_LAP_1: Final = 15
# A race that started less than this long ago may still be running (assumption A7).
COMPLETED_MARGIN: Final = timedelta(hours=6)
FIRST_OPENF1_SEASON: Final = 2023


def _unexpected(path: str, detail: str) -> SourceError:
    return SourceError(f"Unexpected response from OpenF1 for {path}: {detail}")


def _number(value: object, path: str, what: str) -> float | None:
    """A float from a JSON number or numeric text; None for null and NaN."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise _unexpected(path, f"{what} is not a number ({value!r})")
    try:
        number = float(value)
    except ValueError:
        raise _unexpected(path, f"{what} is not a number ({value!r})") from None
    return None if number != number else number


def _whole(value: object, path: str, what: str) -> int | None:
    number = _number(value, path, what)
    if number is None:
        return None
    if number != int(number):
        raise _unexpected(path, f"{what} is not a whole number ({value!r})")
    return int(number)


def _stamp(value: object, path: str, what: str) -> pd.Timestamp | None:
    """A UTC timestamp from ISO 8601 text; None for null."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise _unexpected(path, f"{what} is not a timestamp ({value!r})")
    try:
        parsed = pd.to_datetime(value, utc=True, format="ISO8601")
    except (ValueError, TypeError):
        raise _unexpected(path, f"{what} is not a timestamp ({value!r})") from None
    return None if pd.isna(parsed) else parsed


def _required(row: Mapping[str, object], keys: Sequence[str], path: str) -> None:
    missing = [k for k in keys if k not in row]
    if missing:
        raise _unexpected(path, f"row lacks {', '.join(missing)}")


def _compound(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().upper()
    return None if text in {"", "UNKNOWN"} else text


def _seconds(ts: pd.Timestamp, t0: pd.Timestamp) -> float:
    return float((ts - t0).total_seconds())


@dataclass(frozen=True)
class _RawLap:
    driver: int
    lap: int
    start: pd.Timestamp | None
    duration: float | None
    s1: float | None
    s2: float | None
    s3: float | None
    pit_out: bool


@dataclass(frozen=True)
class _Opening:
    """The tyre a car started the race on (OpenF1 stint number 1)."""

    compound: str | None
    age_at_start: int


@dataclass(frozen=True)
class _RawStint:
    driver: int
    number: int
    compound: str | None
    lap_start: int
    lap_end: int | None
    age_at_start: int


class OpenF1Source:
    """Real races from OpenF1 (timing) and Jolpica (calendar, grid, results, pit stops)."""

    def __init__(
        self,
        *,
        http_cache_dir: Path,
        echo: Callable[[str], None] = print,
        sleep: Callable[[float], None] = time.sleep,
        openf1: JsonGetter | None = None,
        jolpica: JolpicaClient | None = None,
    ) -> None:
        self._echo = echo
        self._openf1: JsonGetter = (
            openf1
            if openf1 is not None
            else RateLimitedClient(
                name="OpenF1",
                base_url=OPENF1_BASE_URL,
                min_interval_s=2.1,  # 30 calls per minute is the limit
                max_per_hour=None,
                cache_path=http_cache_dir / "openf1.sqlite",
                echo=echo,
                sleep=sleep,
            )
        )
        self._jolpica = (
            jolpica
            if jolpica is not None
            else JolpicaClient.create(cache_dir=http_cache_dir, echo=echo, sleep=sleep)
        )

    @property
    def name(self) -> str:
        """Source name stored with each race."""
        return "openf1+jolpica"

    @property
    def version(self) -> str:
        """Source versions stored with each race."""
        return f"openf1-api+jolpica-ergast;f1si-{f1si.__version__}"

    @property
    def default_seasons(self) -> tuple[int, ...]:
        """2023 to 2026: OpenF1 history starts in 2023 (D-05)."""
        return (2023, 2024, 2025, 2026)

    # ------------------------------------------------------------------ calendar

    def list_races(self, season: int, *, now: datetime) -> list[RaceRef]:
        """Grand Prix Race sessions of `season` that have finished, matched to Jolpica rounds."""
        if season < FIRST_OPENF1_SEASON:
            raise SourceError(
                f"OpenF1 history starts in {FIRST_OPENF1_SEASON}; season {season} is not "
                "available (D-05)"
            )
        path = "/sessions"
        rows = self._rows(path, {"year": season, "session_name": "Race"}, freshness="short")
        schedule = self._jolpica.season_schedule(season)
        sessions: list[tuple[pd.Timestamp, Mapping[str, object]]] = []
        for row in rows:
            _required(row, ("session_key", "date_start"), path)
            if row.get("session_type") != "Race" or row.get("session_name") != "Race":
                continue
            if row.get("is_cancelled") is True:
                continue
            started = _stamp(row["date_start"], path, "date_start")
            if started is None or started.to_pydatetime() + COMPLETED_MARGIN > now:
                continue
            sessions.append((started, row))
        sessions.sort(key=lambda item: item[0])

        matched: list[tuple[JolpicaRace, pd.Timestamp, Mapping[str, object]]] = []
        used_rounds: set[int] = set()
        for started, session in sessions:
            race = _closest_round(started, schedule)
            if race is None or race.round in used_rounds:
                self._echo(
                    f"  skipped OpenF1 session {session['session_key']} on {started.date()}: "
                    "no Jolpica round matches it"
                )
                continue
            used_rounds.add(race.round)
            matched.append((race, started, session))

        slugs = [event_slug(race.race_name, season) for race, _, _ in matched]
        refs: list[RaceRef] = []
        for (race, started, session), slug in zip(matched, slugs, strict=True):
            if slugs.count(slug) > 1:
                slug = f"{slug}-r{race.round}"
            meeting = session.get("meeting_key")
            refs.append(
                RaceRef(
                    race_id=f"{season}-{race.round:02d}",
                    season=season,
                    round=race.round,
                    slug=slug,
                    event_name=race.race_name,
                    circuit=race.circuit_id,
                    country=race.country,
                    race_start_utc=started.to_pydatetime(),
                    scheduled_laps=None,
                    source_keys={
                        "session_key": str(session["session_key"]),
                        "meeting_key": "" if meeting is None else str(meeting),
                    },
                )
            )
        return sorted(refs, key=lambda ref: ref.round)

    # ------------------------------------------------------------------ one race

    def fetch(self, ref: RaceRef) -> NormalizedRace:
        """Fetch and normalize one race; incomplete upstream data raises `SourceError`."""
        try:
            session_key = int(ref.source_keys["session_key"])
        except (KeyError, ValueError):
            raise SourceError(f"{ref.slug}: the race reference has no OpenF1 session_key") from None
        params = {"session_key": session_key}
        drivers_raw = self._rows("/drivers", params)
        laps_raw = self._rows("/laps", params)
        stints_raw = self._rows("/stints", params)
        control_raw = self._rows("/race_control", params)
        weather_raw = self._rows("/weather", params)
        results = self._jolpica.results(ref.season, ref.round)
        pit_stops = self._jolpica.pit_stops(ref.season, ref.round)

        laps_in = _parse_laps(laps_raw)
        stints = _parse_stints(stints_raw)
        lap_one = [lap.start for lap in laps_in if lap.lap == 1 and lap.start is not None]
        t0 = min(lap_one) if lap_one else pd.to_datetime(ref.race_start_utc, utc=True)

        openings = _parse_openings(stints_raw)
        started = {lap.driver for lap in laps_in if lap.lap == 1}
        entries = _build_entries(ref, drivers_raw, results, openings, started)
        unknown_tyre = sorted(
            int(n)
            for n in entries.loc[entries["start_compound"].isna(), "driver_number"]
            if int(n) in started
        )
        if unknown_tyre:
            self._echo(
                f"  note: {ref.slug}: starting tyre unknown for driver(s) "
                f"{', '.join(str(n) for n in unknown_tyre)} (OpenF1 has no first stint); "
                "start_compound left empty"
            )
        laps = _build_laps(ref, laps_in, stints, results, pit_stops, t0)
        race_control = _build_race_control(ref, control_raw, t0)
        weather = _build_weather(ref, weather_raw, t0)
        self._check_complete(ref, entries, laps, race_control, weather, results)

        leader_ends = (
            laps.dropna(subset=["lap_end_s"]).groupby("lap_number")["lap_end_s"].min().sort_index()
        )
        track = derive_track_status(
            race_control, leader_lap_end_s=[float(v) for v in leader_ends.tolist()]
        )
        track.insert(0, "race_id", ref.race_id)

        return NormalizedRace(
            ref=ref,
            tables={
                "entries": entries,
                "laps": laps,
                "track_status": track,
                "race_control": race_control,
                "weather": weather,
                "results": _build_results(ref, results),
            },
        )

    # ------------------------------------------------------------------ helpers

    def _rows(
        self,
        path: str,
        params: Mapping[str, str | int],
        *,
        freshness: Literal["forever", "short"] = "forever",
    ) -> list[dict[str, object]]:
        payload = self._openf1.get_json(path, params, freshness=freshness)
        if payload is None or (isinstance(payload, dict) and "detail" in payload):
            return []
        if not isinstance(payload, list):
            raise _unexpected(path, "expected a list of rows")
        rows: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                raise _unexpected(path, "a row is not an object")
            rows.append({str(k): v for k, v in item.items()})
        return rows

    @staticmethod
    def _check_complete(
        ref: RaceRef,
        entries: pd.DataFrame,
        laps: pd.DataFrame,
        race_control: pd.DataFrame,
        weather: pd.DataFrame,
        results: pd.DataFrame,
    ) -> None:
        def incomplete(what: str) -> SourceError:
            return SourceError(
                f"Incomplete data from OpenF1/Jolpica for {ref.slug}: {what}. "
                "It will be retried on the next run."
            )

        if laps.empty:
            raise incomplete("no laps")
        if not MIN_ENTRIES <= len(entries) <= MAX_ENTRIES:
            raise incomplete(f"{len(entries)} entries (expected {MIN_ENTRIES} to {MAX_ENTRIES})")
        if len(results) != len(entries):
            raise incomplete("results and entries differ in length")
        with_lap_one = int(laps.loc[laps["lap_number"] == 1, "driver_number"].nunique())
        if with_lap_one < MIN_DRIVERS_WITH_LAP_1:
            raise incomplete(
                f"only {with_lap_one} drivers have a lap 1 (expected at least "
                f"{MIN_DRIVERS_WITH_LAP_1})"
            )
        if weather.empty:
            raise incomplete("no weather rows")
        if race_control.empty:
            raise incomplete("no race control messages")
        unknown = sorted(set(laps["driver_number"]) - set(entries["driver_number"]))
        if unknown:
            raise incomplete(f"laps for drivers {unknown} who are not in entries")


def _closest_round(started: pd.Timestamp, schedule: Sequence[JolpicaRace]) -> JolpicaRace | None:
    """The Jolpica race whose UTC date is within one day of `started`; the closest wins."""
    best: tuple[int, float, JolpicaRace] | None = None
    for race in schedule:
        days = abs((started.date() - race.start_utc.date()).days)
        if days > 1:
            continue
        gap = abs((started.to_pydatetime() - race.start_utc).total_seconds())
        if best is None or (days, gap) < best[:2]:
            best = (days, gap, race)
    return None if best is None else best[2]


def _parse_laps(rows: Sequence[Mapping[str, object]]) -> list[_RawLap]:
    path = "/laps"
    out: list[_RawLap] = []
    for row in rows:
        _required(row, ("driver_number", "lap_number"), path)
        driver = _whole(row["driver_number"], path, "driver_number")
        lap = _whole(row["lap_number"], path, "lap_number")
        if driver is None or lap is None:
            raise _unexpected(path, "driver_number or lap_number is null")
        out.append(
            _RawLap(
                driver=driver,
                lap=lap,
                start=_stamp(row.get("date_start"), path, "date_start"),
                duration=_number(row.get("lap_duration"), path, "lap_duration"),
                s1=_number(row.get("duration_sector_1"), path, "duration_sector_1"),
                s2=_number(row.get("duration_sector_2"), path, "duration_sector_2"),
                s3=_number(row.get("duration_sector_3"), path, "duration_sector_3"),
                pit_out=bool(row.get("is_pit_out_lap") or False),
            )
        )
    return out


def _parse_stints(rows: Sequence[Mapping[str, object]]) -> list[_RawStint]:
    path = "/stints"
    out: list[_RawStint] = []
    for row in rows:
        _required(row, ("driver_number", "stint_number"), path)
        driver = _whole(row["driver_number"], path, "driver_number")
        number = _whole(row["stint_number"], path, "stint_number")
        lap_start = _whole(row.get("lap_start"), path, "lap_start")
        if driver is None or number is None:
            raise _unexpected(path, "driver_number or stint_number is null")
        if lap_start is None:
            continue  # a stint with no first lap cannot be placed on laps
        out.append(
            _RawStint(
                driver=driver,
                number=number,
                compound=_compound(row.get("compound")),
                lap_start=lap_start,
                lap_end=_whole(row.get("lap_end"), path, "lap_end"),
                age_at_start=_whole(row.get("tyre_age_at_start"), path, "tyre_age_at_start") or 0,
            )
        )
    return sorted(out, key=lambda s: (s.driver, s.number))


def _parse_openings(rows: Sequence[Mapping[str, object]]) -> dict[int, _Opening]:
    """Per driver, the compound and tyre age of OpenF1 stint number 1.

    Stint 1 counts even when its `lap_start` is null (the feed sometimes omits it), but not when
    it says the stint began after lap 1: that row is then not the opening stint.
    """
    path = "/stints"
    out: dict[int, _Opening] = {}
    for row in rows:
        _required(row, ("driver_number", "stint_number"), path)
        driver = _whole(row["driver_number"], path, "driver_number")
        number = _whole(row["stint_number"], path, "stint_number")
        if driver is None or number != 1:
            continue
        lap_start = _whole(row.get("lap_start"), path, "lap_start")
        if lap_start is not None and lap_start > 1:
            continue
        out.setdefault(
            driver,
            _Opening(
                compound=_compound(row.get("compound")),
                age_at_start=_whole(row.get("tyre_age_at_start"), path, "tyre_age_at_start") or 0,
            ),
        )
    return out


def _build_entries(
    ref: RaceRef,
    drivers_raw: Sequence[Mapping[str, object]],
    results: pd.DataFrame,
    openings: Mapping[int, _Opening],
    started: Collection[int],
) -> pd.DataFrame:
    path = "/drivers"
    openf1: dict[int, Mapping[str, object]] = {}
    for row in drivers_raw:
        _required(row, ("driver_number",), path)
        number = _whole(row["driver_number"], path, "driver_number")
        if number is not None:
            openf1[number] = row
    rows: list[dict[str, object]] = []
    for res in results.to_dict("records"):
        number = int(res["driver_number"])
        extra = openf1.get(number, {})
        grid = int(res["grid"])
        jolpica_code = res["driver_code"]
        acronym = extra.get("name_acronym")
        code = (
            jolpica_code
            if isinstance(jolpica_code, str) and jolpica_code
            else acronym
            if isinstance(acronym, str) and acronym
            else str(res["driver_id"])[:3]
        )
        full_name = extra.get("full_name")
        opening = openings.get(number)
        rows.append(
            {
                "race_id": ref.race_id,
                "driver_number": number,
                "driver_code": str(code).upper(),
                "driver_id": str(res["driver_id"]),
                "full_name": (
                    full_name
                    if isinstance(full_name, str) and full_name
                    else f"{res['given_name']} {res['family_name']}"
                ),
                "team_name": str(res["team_name"]),
                "grid_position": grid if grid > 0 else None,
                # No post-race field is used: not the status, not the laps completed (A8).
                "pit_lane_start": grid == 0 and number in started,
                "start_compound": None if opening is None else opening.compound,
                "start_tyre_age": None if opening is None else opening.age_at_start,
            }
        )
    return pd.DataFrame(rows)


def _build_laps(
    ref: RaceRef,
    laps_in: Sequence[_RawLap],
    stints: Sequence[_RawStint],
    results: pd.DataFrame,
    pit_stops: pd.DataFrame,
    t0: pd.Timestamp,
) -> pd.DataFrame:
    by_driver: dict[int, list[_RawLap]] = {}
    for lap in laps_in:
        by_driver.setdefault(lap.driver, []).append(lap)

    number_of = {str(r["driver_id"]): int(r["driver_number"]) for r in results.to_dict("records")}
    pit_in: set[tuple[int, int]] = set()
    pit_duration: dict[tuple[int, int], float] = {}
    for stop in pit_stops.to_dict("records"):
        driver = number_of.get(str(stop["driver_id"]))
        if driver is None:
            continue
        stop_lap = int(stop["lap"])
        pit_in.add((driver, stop_lap))
        if not pd.isna(stop["duration_s"]):
            pit_duration[(driver, stop_lap + 1)] = float(stop["duration_s"])

    stint_by_lap: dict[tuple[int, int], tuple[int, str | None, int]] = {}
    last_lap = {driver: max(lap.lap for lap in laps) for driver, laps in by_driver.items()}
    for stint in stints:  # later stints overwrite earlier ones on overlapping laps
        stint_end = stint.lap_end if stint.lap_end is not None else last_lap.get(stint.driver)
        if stint_end is None:
            continue
        for lap_number in range(stint.lap_start, stint_end + 1):
            stint_by_lap[(stint.driver, lap_number)] = (
                stint.number,
                stint.compound,
                stint.age_at_start + (lap_number - stint.lap_start) + 1,
            )

    rows: list[dict[str, object]] = []
    for driver in sorted(by_driver):
        ordered = sorted(by_driver[driver], key=lambda lap: lap.lap)
        starts: dict[int, float | None] = {}
        for lap in ordered:
            if lap.start is not None:
                starts[lap.lap] = _seconds(lap.start, t0)
            else:
                starts[lap.lap] = 0.0 if lap.lap == 1 else None
        for lap in ordered:
            start = starts[lap.lap]
            if lap.duration is not None:
                end = None if start is None else start + lap.duration
            else:
                end = starts.get(lap.lap + 1)
            lap_time = (
                lap.duration
                if lap.duration is not None
                else (end - start if end is not None and start is not None else None)
            )
            stint_info = stint_by_lap.get((driver, lap.lap))
            rows.append(
                {
                    "race_id": ref.race_id,
                    "driver_number": driver,
                    "lap_number": lap.lap,
                    "lap_start_s": start,
                    "lap_end_s": end,
                    "lap_time_s": lap_time,
                    "s1_s": lap.s1,
                    "s2_s": lap.s2,
                    "s3_s": lap.s3,
                    "is_pit_in_lap": (driver, lap.lap) in pit_in,
                    "is_pit_out_lap": lap.pit_out,
                    "pit_duration_s": pit_duration.get((driver, lap.lap)),
                    "stint": None if stint_info is None else stint_info[0],
                    "compound": None if stint_info is None else stint_info[1],
                    "tyre_life": None if stint_info is None else stint_info[2],
                    "track_status": None,
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "race_id", "driver_number", "lap_number", "lap_start_s", "lap_end_s", "lap_time_s",
            "s1_s", "s2_s", "s3_s", "is_pit_in_lap", "is_pit_out_lap", "pit_duration_s",
            "stint", "compound", "tyre_life", "track_status",
        ],
    )  # fmt: skip


def _build_race_control(
    ref: RaceRef, rows: Sequence[Mapping[str, object]], t0: pd.Timestamp
) -> pd.DataFrame:
    path = "/race_control"
    parsed: list[tuple[pd.Timestamp, int, Mapping[str, object]]] = []
    for index, row in enumerate(rows):
        _required(row, ("date", "category"), path)
        when = _stamp(row["date"], path, "date")
        if when is None:
            raise _unexpected(path, "date is null")
        parsed.append((when, index, row))
    parsed.sort(key=lambda item: (item[0], item[1]))
    out: list[dict[str, object]] = []
    for seq, (when, _, row) in enumerate(parsed):
        category = row["category"]
        if not isinstance(category, str):
            raise _unexpected(path, f"category is not text ({category!r})")
        message = row.get("message")
        flag = row.get("flag")
        scope = row.get("scope")
        out.append(
            {
                "race_id": ref.race_id,
                "seq": seq,
                "t_s": _seconds(when, t0),
                "category": category,
                "flag": flag if isinstance(flag, str) else None,
                "scope": scope if isinstance(scope, str) else None,
                "sector": _whole(row.get("sector"), path, "sector"),
                "driver_number": _whole(row.get("driver_number"), path, "driver_number"),
                "lap_number": _whole(row.get("lap_number"), path, "lap_number"),
                "message": message if isinstance(message, str) else "",
            }
        )
    frame = pd.DataFrame(
        out,
        columns=[
            "race_id", "seq", "t_s", "category", "flag", "scope", "sector", "driver_number",
            "lap_number", "message",
        ],
    )  # fmt: skip
    frame["seq"] = frame["seq"].astype("int64")
    frame["t_s"] = frame["t_s"].astype("float64")
    for col in ("sector", "driver_number", "lap_number"):
        frame[col] = frame[col].astype("Int64")
    return frame


def _build_weather(
    ref: RaceRef, rows: Sequence[Mapping[str, object]], t0: pd.Timestamp
) -> pd.DataFrame:
    path = "/weather"
    parsed: list[tuple[pd.Timestamp, int, Mapping[str, object]]] = []
    for index, row in enumerate(rows):
        _required(row, ("date",), path)
        when = _stamp(row["date"], path, "date")
        if when is None:
            raise _unexpected(path, "date is null")
        parsed.append((when, index, row))
    parsed.sort(key=lambda item: (item[0], item[1]))
    out: list[dict[str, object]] = []
    for seq, (when, _, row) in enumerate(parsed):
        rain = _number(row.get("rainfall"), path, "rainfall")
        out.append(
            {
                "race_id": ref.race_id,
                "seq": seq,
                "t_s": _seconds(when, t0),
                "air_temp_c": _number(row.get("air_temperature"), path, "air_temperature"),
                "track_temp_c": _number(row.get("track_temperature"), path, "track_temperature"),
                "humidity_pct": _number(row.get("humidity"), path, "humidity"),
                "pressure_mbar": _number(row.get("pressure"), path, "pressure"),
                "rainfall": None if rain is None else rain > 0,
                "wind_speed_ms": _number(row.get("wind_speed"), path, "wind_speed"),
                "wind_direction_deg": _number(row.get("wind_direction"), path, "wind_direction"),
            }
        )
    return pd.DataFrame(
        out,
        columns=[
            "race_id", "seq", "t_s", "air_temp_c", "track_temp_c", "humidity_pct",
            "pressure_mbar", "rainfall", "wind_speed_ms", "wind_direction_deg",
        ],
    )  # fmt: skip


def _build_results(ref: RaceRef, results: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for res in results.to_dict("records"):
        text = str(res["position_text"])
        rows.append(
            {
                "race_id": ref.race_id,
                "driver_number": int(res["driver_number"]),
                "final_position": int(res["position"]) if text.isdigit() else None,
                "classified_position": text,
                "status": str(res["status"]),
                "points": float(res["points"]),
                "laps_completed": int(res["laps"]),
                "total_time_s": None
                if pd.isna(res["total_time_s"])
                else float(res["total_time_s"]),
            }
        )
    return pd.DataFrame(rows)
