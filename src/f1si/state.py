"""RaceState: the plain-data picture of a race at one lap that policies and simulators consume.

Schema (BUILD_PLAN, D-12)
-------------------------
JSON shape::

    {"lap": 18, "laps_total": 57, "regime": {"green": 1.0}, "pit_loss_s": {"green": 22.0},
     "cars": [{"driver": "VER", "position": 1, "gap_ahead_s": null, "gap_behind_s": 4.1,
               "compound": "MEDIUM", "tire_age": 12, "wear_rate_s_per_lap": 0.07,
               "wear_sd": 0.01, "pace_offset_s": -0.3, "stops_done": 0,
               "compounds_used": ["MEDIUM"], "driver_number": 1}, ...]}

The only addition to the BUILD_PLAN keys is the documented key `driver_number` (the stable
database key that `PaceModel.predict` takes). Fields are never removed or renamed later.

State is plain frozen data. It is built from a race snapshot by one pure builder that arrives in
plan 02-03; this module imports only NumPy and the standard library and never touches the data
accessor.

Placeholders (D-13)
-------------------
`regime` is a placeholder, {"green": 1.0}, until Phases 3 and 8 estimate a track regime.
`pit_loss_s` is a placeholder too: it holds only the "green" key until Phase 8 adds pit loss
under safety-car and virtual-safety-car regimes.

Unknown values (D-23)
---------------------
Unknown position, gaps, compound and rates are `None`, never NaN. `to_json` uses
`allow_nan=False`, and a NaN or infinite float is rejected when a `CarState` is built.
`to_arrays()` converts to NaN or -1 only for numerical code.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

_CODE: Final = re.compile(r"^[A-Z]{3}$")
_CAR_KEYS: Final = (
    "driver",
    "position",
    "gap_ahead_s",
    "gap_behind_s",
    "compound",
    "tire_age",
    "wear_rate_s_per_lap",
    "wear_sd",
    "pace_offset_s",
    "stops_done",
    "compounds_used",
    "driver_number",
)
_STATE_KEYS: Final = ("lap", "laps_total", "regime", "pit_loss_s", "cars")
_OPTIONAL_FLOATS: Final = (
    "gap_ahead_s",
    "gap_behind_s",
    "wear_rate_s_per_lap",
    "wear_sd",
    "pace_offset_s",
)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_int(name: str, value: object) -> int:
    if not _is_int(value):
        raise ValueError(f"{name} must be an int, got {value!r}")
    assert isinstance(value, int)
    return value


def _check_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {value!r}")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return out


@dataclass(frozen=True)
class CarState:
    """One car at the start of the state's lap. Unknown values are None (D-23).

    `tire_age` is the laps on the current tyres at the end of the last completed lap.
    `wear_rate_s_per_lap` and `wear_sd` are the fitted wear slope and its standard error for the
    car's current compound; `pace_offset_s` is the fitted driver offset.

    Raises:
        ValueError: if a value is out of range, not finite or of the wrong type.
    """

    driver: str
    driver_number: int
    position: int | None
    gap_ahead_s: float | None
    gap_behind_s: float | None
    compound: str | None
    tire_age: int
    wear_rate_s_per_lap: float | None
    wear_sd: float | None
    pace_offset_s: float | None
    stops_done: int
    compounds_used: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.driver, str) or not _CODE.match(self.driver):
            raise ValueError(f"driver must be a three-letter code like VER, got {self.driver!r}")
        _check_int("driver_number", self.driver_number)
        if self.position is not None and (_check_int("position", self.position) < 1):
            raise ValueError(f"position must be >= 1 or None, got {self.position!r}")
        for name in _OPTIONAL_FLOATS:
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _check_float(name, value))
        if self.compound is not None and not isinstance(self.compound, str):
            raise ValueError(f"compound must be a string or None, got {self.compound!r}")
        if _check_int("tire_age", self.tire_age) < 0:
            raise ValueError(f"tire_age must be >= 0, got {self.tire_age!r}")
        if _check_int("stops_done", self.stops_done) < 0:
            raise ValueError(f"stops_done must be >= 0, got {self.stops_done!r}")
        object.__setattr__(self, "compounds_used", tuple(self.compounds_used))
        for used in self.compounds_used:
            if not isinstance(used, str):
                raise ValueError(f"compounds_used must hold strings, got {used!r}")


@dataclass(frozen=True, eq=False)
class CarArrays:
    """Read-only struct-of-arrays view of `RaceState.cars`, in the same order.

    Float arrays use NaN for None, `position` uses -1 for None, `compound` uses "" for None.
    """

    driver_number: NDArray[np.int64]
    position: NDArray[np.int64]
    gap_ahead_s: NDArray[np.float64]
    gap_behind_s: NDArray[np.float64]
    tire_age: NDArray[np.int64]
    wear_rate_s_per_lap: NDArray[np.float64]
    wear_sd: NDArray[np.float64]
    pace_offset_s: NDArray[np.float64]
    stops_done: NDArray[np.int64]
    compound: NDArray[np.str_]


def _readonly(arr: NDArray[Any]) -> NDArray[Any]:
    arr.flags.writeable = False
    return arr


def _freeze_mapping(name: str, value: Mapping[str, float]) -> Mapping[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping, got {value!r}")
    out: dict[str, float] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{name} keys must be strings, got {key!r}")
        out[key] = _check_float(f"{name}[{key!r}]", item)
    return MappingProxyType(out)


@dataclass(frozen=True)
class RaceState:
    """The race after `lap` laps of the leader have been completed.

    `lap` is the number of completed laps (0 = before the start) and `laps_total` the race
    length. `regime` maps track regime to probability and sums to 1 (placeholder
    {"green": 1.0} until Phases 3 and 8, D-13). `pit_loss_s` maps regime to the time lost in a
    stop (placeholder with only "green" until Phase 8). `cars` is a tuple of `CarState`.

    Raises:
        ValueError: on a bad lap, regime, pit loss, or duplicate driver codes.
    """

    lap: int
    laps_total: int
    regime: Mapping[str, float]
    pit_loss_s: Mapping[str, float]
    cars: tuple[CarState, ...]

    def __post_init__(self) -> None:
        if _check_int("lap", self.lap) < 0:
            raise ValueError(f"lap must be >= 0, got {self.lap}")
        if _check_int("laps_total", self.laps_total) < 1:
            raise ValueError(f"laps_total must be >= 1, got {self.laps_total}")
        if self.lap > self.laps_total:
            raise ValueError(f"lap {self.lap} is beyond laps_total {self.laps_total}")
        regime = _freeze_mapping("regime", self.regime)
        if not regime or abs(sum(regime.values()) - 1.0) > 1e-9 or min(regime.values()) < 0:
            raise ValueError(f"regime must be non-negative and sum to 1, got {dict(regime)!r}")
        pit_loss = _freeze_mapping("pit_loss_s", self.pit_loss_s)
        for key, value in pit_loss.items():
            if value <= 0:
                raise ValueError(f"pit_loss_s[{key!r}] must be > 0, got {value!r}")
        object.__setattr__(self, "regime", regime)
        object.__setattr__(self, "pit_loss_s", pit_loss)
        object.__setattr__(self, "cars", tuple(self.cars))
        codes = [car.driver for car in self.cars]
        dupes = sorted({c for c in codes if codes.count(c) > 1})
        if dupes:
            raise ValueError(f"duplicate driver codes: {', '.join(dupes)}")

    def car(self, code: str) -> CarState:
        """Return the car with three-letter `code`.

        Raises:
            ValueError: if no car has that code (the message lists the valid codes).
        """
        for car in self.cars:
            if car.driver == code:
                return car
        raise ValueError(
            f"Unknown driver code {code!r}. Codes in this state: "
            f"{', '.join(sorted(c.driver for c in self.cars))}"
        )

    def to_arrays(self) -> CarArrays:
        """Read-only struct-of-arrays view in `cars` order (None becomes NaN, -1 or "")."""

        def floats(name: str) -> NDArray[np.float64]:
            return _readonly(
                np.array(
                    [np.nan if getattr(c, name) is None else getattr(c, name) for c in self.cars],
                    dtype=np.float64,
                )
            )

        return CarArrays(
            driver_number=_readonly(np.array([c.driver_number for c in self.cars], dtype=np.int64)),
            position=_readonly(
                np.array([-1 if c.position is None else c.position for c in self.cars], np.int64)
            ),
            gap_ahead_s=floats("gap_ahead_s"),
            gap_behind_s=floats("gap_behind_s"),
            tire_age=_readonly(np.array([c.tire_age for c in self.cars], dtype=np.int64)),
            wear_rate_s_per_lap=floats("wear_rate_s_per_lap"),
            wear_sd=floats("wear_sd"),
            pace_offset_s=floats("pace_offset_s"),
            stops_done=_readonly(np.array([c.stops_done for c in self.cars], dtype=np.int64)),
            compound=_readonly(
                np.array([c.compound or "" for c in self.cars], dtype=np.str_).astype(np.str_)
            ),
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Pure-Python dict in the BUILD_PLAN shape (plus `driver_number`)."""
        return {
            "lap": self.lap,
            "laps_total": self.laps_total,
            "regime": dict(self.regime),
            "pit_loss_s": dict(self.pit_loss_s),
            "cars": [
                {
                    "driver": c.driver,
                    "position": c.position,
                    "gap_ahead_s": c.gap_ahead_s,
                    "gap_behind_s": c.gap_behind_s,
                    "compound": c.compound,
                    "tire_age": c.tire_age,
                    "wear_rate_s_per_lap": c.wear_rate_s_per_lap,
                    "wear_sd": c.wear_sd,
                    "pace_offset_s": c.pace_offset_s,
                    "stops_done": c.stops_done,
                    "compounds_used": list(c.compounds_used),
                    "driver_number": c.driver_number,
                }
                for c in self.cars
            ],
        }

    def to_json(self) -> str:
        """JSON text; NaN is never written (`allow_nan=False`)."""
        return json.dumps(self.to_json_dict(), allow_nan=False, sort_keys=False)

    @classmethod
    def from_json_dict(cls, data: Mapping[str, Any]) -> RaceState:
        """Validate and build a state from a decoded JSON object.

        Raises:
            ValueError: naming the missing key, unknown key or wrong type.
        """
        if not isinstance(data, Mapping):
            raise ValueError(f"RaceState JSON: expected an object, got {type(data).__name__}")
        _check_keys("RaceState JSON", data, _STATE_KEYS)
        raw_cars = data["cars"]
        if not isinstance(raw_cars, list):
            raise ValueError("RaceState JSON: 'cars' must be a list")
        cars: list[CarState] = []
        for raw in raw_cars:
            if not isinstance(raw, Mapping):
                raise ValueError("RaceState JSON: each car must be an object")
            _check_keys("RaceState JSON car", raw, _CAR_KEYS)
            used = raw["compounds_used"]
            if not isinstance(used, list):
                raise ValueError("RaceState JSON car: 'compounds_used' must be a list")
            cars.append(
                CarState(
                    driver=raw["driver"],
                    driver_number=raw["driver_number"],
                    position=raw["position"],
                    gap_ahead_s=raw["gap_ahead_s"],
                    gap_behind_s=raw["gap_behind_s"],
                    compound=raw["compound"],
                    tire_age=raw["tire_age"],
                    wear_rate_s_per_lap=raw["wear_rate_s_per_lap"],
                    wear_sd=raw["wear_sd"],
                    pace_offset_s=raw["pace_offset_s"],
                    stops_done=raw["stops_done"],
                    compounds_used=tuple(used),
                )
            )
        return cls(
            lap=data["lap"],
            laps_total=data["laps_total"],
            regime=data["regime"],
            pit_loss_s=data["pit_loss_s"],
            cars=tuple(cars),
        )

    @classmethod
    def from_json(cls, text: str) -> RaceState:
        """Parse JSON text with `json.loads` (no eval, no pickle) and validate it.

        Raises:
            ValueError: if the text is not valid JSON or fails validation.
        """
        try:
            data = json.loads(text, parse_constant=_reject_constant)
        except json.JSONDecodeError as err:
            raise ValueError(f"RaceState JSON: not valid JSON ({err})") from err
        return cls.from_json_dict(data)


def _reject_constant(name: str) -> float:
    raise ValueError(f"RaceState JSON: {name} is not allowed; unknown values are null")


def _check_keys(where: str, data: Mapping[str, Any], expected: tuple[str, ...]) -> None:
    for key in expected:
        if key not in data:
            raise ValueError(f"{where}: missing key {key!r}")
    extra = sorted(str(k) for k in data if k not in expected)
    if extra:
        raise ValueError(f"{where}: unknown key(s) {', '.join(extra)}")
