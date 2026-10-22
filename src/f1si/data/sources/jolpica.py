"""Jolpica (the Ergast successor) client: season schedule, race results with grid, pit stops (D-08).

Jolpica gives what OpenF1 does not: the official race classification, grid positions, finishing
status and a complete pit-stop list. All calls go through one `JsonGetter` (in production a
`RateLimitedClient` with 0.5 s spacing and at most 450 calls per hour, because the service allows 4
requests per second burst and 500 per hour), so every payload is cached on disk and a re-run makes
no repeat calls.

Endpoints (all under `https://api.jolpi.ca/ergast/f1`):

* `/{season}.json?limit=100` -> `MRData.RaceTable.Races[]` (schedule; cached for 12 hours)
* `/{season}/{round}/results.json?limit=100` -> `MRData.RaceTable.Races[0].Results[]`
* `/{season}/{round}/pitstops.json?limit=100&offset=N` -> `Races[0].PitStops[]`, paginated until
  `offset >= MRData.total`

Round numbers renumber when a race is cancelled or added, and an event name is not a circuit, so
the schedule carries `circuit_id` and the caller keys races by (season, round) as given here.

Every payload is third-party input: its shape is validated and anything missing raises
`SourceError("Unexpected response from Jolpica for PATH: WHAT")`. Integers come from `int()` of the
API's strings only.
"""

import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pandas as pd

from f1si.data.sources import SourceError
from f1si.data.sources._http import JsonGetter, RateLimitedClient

JOLPICA_BASE_URL: Final = "https://api.jolpi.ca/ergast/f1"
PAGE_LIMIT: Final = 100
MAX_PAGES: Final = 50

_NUMBER: Final = re.compile(r"\d+(?:\.\d+)?")
_WHOLE: Final = re.compile(r"\d+")

RESULT_COLUMNS: Final = (
    "driver_number",
    "driver_id",
    "driver_code",
    "given_name",
    "family_name",
    "team_name",
    "grid",
    "position",
    "position_text",
    "status",
    "points",
    "laps",
    "total_time_s",
)
PIT_STOP_COLUMNS: Final = ("driver_id", "lap", "stop", "duration_s")


@dataclass(frozen=True)
class JolpicaRace:
    """One scheduled race: calendar facts only."""

    season: int
    round: int
    race_name: str
    circuit_id: str
    locality: str
    country: str
    start_utc: datetime


def parse_duration_s(text: str) -> float | None:
    """Seconds from `S.sss`, `M:SS.sss` or `H:MM:SS.sss`; None when the text is not a duration.

    With parts p = (h, m, s) the value is 3600 h + 60 m + s. Examples: "23.456" -> 23.456,
    "1:02.345" -> 62.345, "22:34.567" -> 1354.567.
    """
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3:
        return None
    *head, last = parts
    if not _NUMBER.fullmatch(last) or not all(_WHOLE.fullmatch(p) for p in head):
        return None
    seconds = float(last)
    for unit, part in zip((60.0, 3600.0), reversed(head), strict=False):
        seconds += unit * int(part)
    return seconds


class JolpicaClient:
    """Typed access to the three Jolpica endpoints the project needs."""

    def __init__(self, getter: JsonGetter) -> None:
        self._getter = getter

    @classmethod
    def create(
        cls,
        *,
        cache_dir: Path,
        echo: Callable[[str], None] = print,
        sleep: Callable[[float], None] = time.sleep,
    ) -> "JolpicaClient":
        """A client with the production pacing: 0.5 s apart, at most 450 network calls per hour."""
        return cls(
            RateLimitedClient(
                name="Jolpica",
                base_url=JOLPICA_BASE_URL,
                min_interval_s=0.5,
                max_per_hour=450,
                cache_path=cache_dir / "jolpica.sqlite",
                echo=echo,
                sleep=sleep,
            )
        )

    def season_schedule(self, season: int) -> list[JolpicaRace]:
        """All races of `season` in calendar order, with a UTC start (00:00 when no time given)."""
        path = f"/{season}.json"
        races = self._races(
            path, self._getter.get_json(path, {"limit": PAGE_LIMIT}, freshness="short")
        )
        out: list[JolpicaRace] = []
        for race in races:
            circuit = _mapping(race.get("Circuit"), path, "Circuit")
            location = _mapping(circuit.get("Location"), path, "Circuit.Location")
            out.append(
                JolpicaRace(
                    season=_int(race.get("season"), path, "season"),
                    round=_int(race.get("round"), path, "round"),
                    race_name=_text(race.get("raceName"), path, "raceName"),
                    circuit_id=_text(circuit.get("circuitId"), path, "Circuit.circuitId"),
                    locality=_text(location.get("locality"), path, "Location.locality"),
                    country=_text(location.get("country"), path, "Location.country"),
                    start_utc=_start_utc(race, path),
                )
            )
        return out

    def results(self, season: int, round: int) -> pd.DataFrame:
        """Race classification: one row per driver, columns `RESULT_COLUMNS`.

        `position` is NA for drivers who were not classified (positionText "R", "D", "W", ...).
        `grid` 0 means a pit-lane start and is kept as 0.
        """
        path = f"/{season}/{round}/results.json"
        races = self._races(path, self._getter.get_json(path, {"limit": PAGE_LIMIT}))
        if not races:
            raise SourceError(f"Jolpica has no results for {season} round {round} yet")
        raw = races[0].get("Results")
        if not isinstance(raw, list) or not raw:
            raise SourceError(f"Jolpica has no results for {season} round {round} yet")
        rows: list[dict[str, object]] = []
        for item in raw:
            row = _mapping(item, path, "Results[]")
            driver = _mapping(row.get("Driver"), path, "Driver")
            team = _mapping(row.get("Constructor"), path, "Constructor")
            position_text = _text(row.get("positionText"), path, "positionText")
            time_block = row.get("Time")
            millis = (
                _mapping(time_block, path, "Time").get("millis") if time_block is not None else None
            )
            rows.append(
                {
                    "driver_number": _int(row.get("number"), path, "number"),
                    "driver_id": _text(driver.get("driverId"), path, "Driver.driverId"),
                    "driver_code": _optional_text(driver.get("code")),
                    "given_name": _text(driver.get("givenName"), path, "Driver.givenName"),
                    "family_name": _text(driver.get("familyName"), path, "Driver.familyName"),
                    "team_name": _text(team.get("name"), path, "Constructor.name"),
                    "grid": _int(row.get("grid"), path, "grid"),
                    "position": (
                        _int(row.get("position"), path, "position")
                        if _WHOLE.fullmatch(position_text)
                        else None
                    ),
                    "position_text": position_text,
                    "status": _text(row.get("status"), path, "status"),
                    "points": _float(row.get("points"), path, "points"),
                    "laps": _int(row.get("laps"), path, "laps"),
                    "total_time_s": (
                        _int(millis, path, "Time.millis") / 1000.0 if millis is not None else None
                    ),
                }
            )
        frame = pd.DataFrame(rows, columns=list(RESULT_COLUMNS))
        for col in ("driver_number", "grid", "position", "laps"):
            frame[col] = frame[col].astype("Int64")
        frame["points"] = frame["points"].astype("float64")
        frame["total_time_s"] = frame["total_time_s"].astype("float64")
        return frame

    def pit_stops(self, season: int, round: int) -> pd.DataFrame:
        """Every pit stop of the race (all pages), columns `PIT_STOP_COLUMNS`."""
        path = f"/{season}/{round}/pitstops.json"
        rows: list[dict[str, object]] = []
        offset = 0
        for _ in range(MAX_PAGES):
            payload = self._getter.get_json(path, {"limit": PAGE_LIMIT, "offset": offset})
            mr = _mapping(_mapping(payload, path, "root").get("MRData"), path, "MRData")
            total = _int(mr.get("total"), path, "MRData.total")
            races = self._races(path, payload)
            page = 0
            if races:
                stops = races[0].get("PitStops")
                if not isinstance(stops, list):
                    raise _unexpected(path, "PitStops is missing")
                for item in stops:
                    stop = _mapping(item, path, "PitStops[]")
                    rows.append(
                        {
                            "driver_id": _text(stop.get("driverId"), path, "driverId"),
                            "lap": _int(stop.get("lap"), path, "lap"),
                            "stop": _int(stop.get("stop"), path, "stop"),
                            "duration_s": parse_duration_s(
                                _text(stop.get("duration"), path, "duration")
                            ),
                        }
                    )
                    page += 1
            offset += PAGE_LIMIT
            if page == 0 or offset >= total:
                break
        frame = pd.DataFrame(rows, columns=list(PIT_STOP_COLUMNS))
        for col in ("lap", "stop"):
            frame[col] = frame[col].astype("Int64")
        frame["duration_s"] = frame["duration_s"].astype("float64")
        return frame

    @staticmethod
    def _races(path: str, payload: object) -> list[Mapping[str, object]]:
        if payload is None:
            raise SourceError(f"Jolpica returned nothing (HTTP 404) for {path}")
        root = _mapping(payload, path, "root")
        table = _mapping(
            _mapping(root.get("MRData"), path, "MRData").get("RaceTable"), path, "RaceTable"
        )
        races = table.get("Races")
        if not isinstance(races, list):
            raise _unexpected(path, "MRData.RaceTable.Races is missing")
        return [_mapping(r, path, "Races[]") for r in races]


def _unexpected(path: str, what: str) -> SourceError:
    return SourceError(f"Unexpected response from Jolpica for {path}: {what}")


def _mapping(value: object, path: str, what: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise _unexpected(path, f"{what} is not an object")
    return value


def _text(value: object, path: str, what: str) -> str:
    if not isinstance(value, str):
        raise _unexpected(path, f"{what} is missing or not text")
    return value


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int(value: object, path: str, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise _unexpected(path, f"{what} is missing or not a whole number")
    try:
        return int(value)
    except ValueError as exc:
        raise _unexpected(path, f"{what} is not a whole number ({value!r})") from exc


def _float(value: object, path: str, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise _unexpected(path, f"{what} is missing or not a number")
    try:
        return float(value)
    except ValueError as exc:
        raise _unexpected(path, f"{what} is not a number ({value!r})") from exc


def _start_utc(race: Mapping[str, object], path: str) -> datetime:
    day = _text(race.get("date"), path, "date")
    clock = race.get("time")
    stamp = (
        f"{day}T{clock.removesuffix('Z')}"
        if isinstance(clock, str) and clock
        else f"{day}T00:00:00"
    )
    try:
        return datetime.fromisoformat(stamp).replace(tzinfo=UTC)
    except ValueError as exc:
        raise _unexpected(path, f"date/time {stamp!r} is not valid") from exc
