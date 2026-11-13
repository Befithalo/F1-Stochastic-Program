"""RaceState: the plain-data picture of a race at one lap that policies and simulators consume.

Schema (BUILD_PLAN, D-12)
-------------------------
JSON shape::

    {"lap": 18, "laps_total": 57, "regime": {"green": 1.0}, "pit_loss_s": {"green": 22.0},
     "cars": [{"driver": "VER", "position": 1, "gap_ahead_s": null, "gap_behind_s": 4.1,
               "compound": "MEDIUM", "tire_age": 12, "wear_rate_s_per_lap": 0.07,
               "wear_sd": 0.01, "pace_offset_s": -0.3, "stops_done": 0,
               "compounds_used": ["MEDIUM"], "driver_number": 1, "laps_done": 18}, ...]}

The only additions to the BUILD_PLAN keys are the documented keys `driver_number` (the stable
database key that `PaceModel.predict` takes) and `laps_done` (the laps this car has completed,
which is below `lap` for every car that is not the leader; DEC-073). `laps_done` may be absent in
JSON read back, meaning "same as `lap`". Fields are never removed or renamed later.

State is plain frozen data. It is built from a race snapshot and a fitted `LinearPaceFit` by one
pure builder, `build_race_state`. This module imports NumPy, pandas, the standard library, the
snapshot type and `f1si.pace.linear`; it never touches the data accessor, so model and strategy
code that receives a `RaceState` cannot reach the cache.

Builder rules (D-14, D-21, D-23)
--------------------------------
`laps_total` is an explicit argument (races.scheduled_laps is NULL in the cache). Position and
gap are None when unknown. The gap to the car ahead is the time gap on the last lap both cars
completed, which is what is knowable at the cutoff (leader N laps, others at most N-1, DEC-042).
It is an approximation and is None for the leader, for lapped cars (laps done differ by more than
1), when a lap-end is missing, and when the computed gap is <= 0 (the car ahead finished that lap
later than or together with the car behind, which happens around position swaps in the timing
data). `tire_age` is the laps already on the tyres at the end of the car's own last completed
lap (`CarState.laps_done`); that car's next lap, number `laps_done + 1`, has age `tire_age + 1`.

Regime and pit loss (D-04, D-05)
--------------------------------
`regime` reflects the track status at the cutoff: {"sc": 1.0} while a safety car is out (the
latest visible track-status row is "4"), else {"green": 1.0}. `sc_laps_elapsed` is the number of
leader laps since that safety car was deployed (0 when none; written to JSON only when nonzero).
`pit_loss_s` always carries a "green" value and an "sc" value equal to `SC_PIT_LOSS_RATIO` times
the green one: a documented placeholder until Phase 8 (REG-03) measures it. Virtual safety cars
and red flags are not modelled (D-02), so the regime stays a coarse placeholder for them.

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
import pandas as pd
from numpy.typing import NDArray

from f1si.data.asof import RaceSnapshot
from f1si.pace.kalman import FilterSnapshot
from f1si.pace.linear import LinearPaceFit

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
    "laps_done",
    "pace_offset_sd",
    "wear_source",
)
_OPTIONAL_CAR_KEYS: Final = ("laps_done", "pace_offset_sd", "wear_source")
_WEAR_SOURCES: Final = ("fit", "filter")
_STATE_KEYS: Final = ("lap", "laps_total", "regime", "pit_loss_s", "cars", "sc_laps_elapsed")
_OPTIONAL_STATE_KEYS: Final = ("sc_laps_elapsed",)
SC_PIT_LOSS_RATIO: Final = 0.5
"""SC pit loss as a fraction of the green value: a placeholder until Phase 8 (REG-03, D-04)."""
_OPTIONAL_FLOATS: Final = (
    "gap_ahead_s",
    "gap_behind_s",
    "wear_rate_s_per_lap",
    "wear_sd",
    "pace_offset_s",
    "pace_offset_sd",
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

    `laps_done` is the number of laps this car has completed; None means the same as
    `RaceState.lap` (the leader, or a state built by hand). At a cutoff the leader has `lap`
    laps and every other car at most `lap - 1`, so `compound`, `tire_age` and `stops_done`
    describe the car after `laps_done` laps, not after `lap` (DEC-073).
    `tire_age` is the laps on the current tyres at the end of the car's last completed lap.
    `wear_rate_s_per_lap` and `wear_sd` are the fitted wear slope and its standard error for the
    car's current compound; `pace_offset_s` is the fitted driver offset and `pace_offset_sd` its
    standard error (None when unknown).

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
    laps_done: int | None = None
    pace_offset_sd: float | None = None
    wear_source: str = "fit"

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
        if self.wear_source not in _WEAR_SOURCES:
            raise ValueError(f"wear_source must be 'fit' or 'filter', got {self.wear_source!r}")
        if self.compound is not None and not isinstance(self.compound, str):
            raise ValueError(f"compound must be a string or None, got {self.compound!r}")
        if _check_int("tire_age", self.tire_age) < 0:
            raise ValueError(f"tire_age must be >= 0, got {self.tire_age!r}")
        if _check_int("stops_done", self.stops_done) < 0:
            raise ValueError(f"stops_done must be >= 0, got {self.stops_done!r}")
        if self.laps_done is not None and _check_int("laps_done", self.laps_done) < 0:
            raise ValueError(f"laps_done must be >= 0 or None, got {self.laps_done!r}")
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
    length. `regime` maps track regime to probability and sums to 1 ({"sc": 1.0} while a safety
    car is out, else {"green": 1.0}, D-05). `pit_loss_s` maps regime to the time lost in a stop
    (the "sc" value is a placeholder ratio until Phase 8). `sc_laps_elapsed` is the leader laps
    since the active safety car was deployed (0 when none). `cars` is a tuple of `CarState`.

    Raises:
        ValueError: on a bad lap, regime, pit loss, or duplicate driver codes.
    """

    lap: int
    laps_total: int
    regime: Mapping[str, float]
    pit_loss_s: Mapping[str, float]
    cars: tuple[CarState, ...]
    sc_laps_elapsed: int = 0

    def __post_init__(self) -> None:
        if _check_int("sc_laps_elapsed", self.sc_laps_elapsed) < 0:
            raise ValueError(f"sc_laps_elapsed must be >= 0, got {self.sc_laps_elapsed!r}")
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
        for car in self.cars:
            if car.laps_done is not None and car.laps_done > self.lap:
                raise ValueError(
                    f"{car.driver} has laps_done {car.laps_done}, more than the leader's lap "
                    f"{self.lap}"
                )
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

    def laps_done_of(self, car: CarState) -> int:
        """Laps completed by `car`: its own `laps_done`, or `lap` if that is None."""
        return self.lap if car.laps_done is None else car.laps_done

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
        out: dict[str, Any] = {
            "lap": self.lap,
            "laps_total": self.laps_total,
            "regime": dict(self.regime),
            "pit_loss_s": dict(self.pit_loss_s),
            "cars": [_car_json(c) for c in self.cars],
        }
        if self.sc_laps_elapsed:
            out["sc_laps_elapsed"] = self.sc_laps_elapsed
        return out

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
        _check_keys("RaceState JSON", data, _STATE_KEYS, optional=_OPTIONAL_STATE_KEYS)
        raw_cars = data["cars"]
        if not isinstance(raw_cars, list):
            raise ValueError("RaceState JSON: 'cars' must be a list")
        cars: list[CarState] = []
        for raw in raw_cars:
            if not isinstance(raw, Mapping):
                raise ValueError("RaceState JSON: each car must be an object")
            _check_keys("RaceState JSON car", raw, _CAR_KEYS, optional=_OPTIONAL_CAR_KEYS)
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
                    laps_done=raw.get("laps_done"),
                    pace_offset_sd=raw.get("pace_offset_sd"),
                    wear_source=raw.get("wear_source", "fit"),
                )
            )
        return cls(
            lap=data["lap"],
            laps_total=data["laps_total"],
            regime=data["regime"],
            pit_loss_s=data["pit_loss_s"],
            cars=tuple(cars),
            sc_laps_elapsed=data.get("sc_laps_elapsed", 0),
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


def _car_json(c: CarState) -> dict[str, Any]:
    """JSON dict of one car; `wear_source` is written only for "filter" (old JSON stays stable)."""
    out: dict[str, Any] = {
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
        "laps_done": c.laps_done,
        "pace_offset_sd": c.pace_offset_sd,
    }
    if c.wear_source != "fit":
        out["wear_source"] = c.wear_source
    return out


def _reject_constant(name: str) -> float:
    raise ValueError(f"RaceState JSON: {name} is not allowed; unknown values are null")


def _check_keys(
    where: str,
    data: Mapping[str, Any],
    expected: tuple[str, ...],
    optional: tuple[str, ...] = (),
) -> None:
    for key in expected:
        if key not in data and key not in optional:
            raise ValueError(f"{where}: missing key {key!r}")
    extra = sorted(str(k) for k in data if k not in expected)
    if extra:
        raise ValueError(f"{where}: unknown key(s) {', '.join(extra)}")


def _upper_or_none(value: object) -> str | None:
    return value.upper() if isinstance(value, str) else None


def _gap_ahead(
    ends: Mapping[tuple[int, int], float],
    behind: tuple[int, int],
    ahead: tuple[int, int],
) -> float | None:
    """Time gap on the last lap both cars completed, or None if unknown or not positive."""
    (num_b, done_b), (num_a, done_a) = behind, ahead
    if abs(done_b - done_a) > 1:
        return None
    common = min(done_b, done_a)
    end_b = ends.get((num_b, common))
    end_a = ends.get((num_a, common))
    if end_b is None or end_a is None:
        return None
    gap = end_b - end_a
    return gap if math.isfinite(gap) and gap > 0 else None


def _leader_laps_at(laps: pd.DataFrame, t_s: float) -> int:
    """Leader laps done by second `t_s`: lap numbers whose first lap end (the leader) is <= t_s."""
    ended = laps[laps["lap_end_s"].notna()]
    if ended.empty:
        return 0
    per_lap = ended.groupby("lap_number")["lap_end_s"].min()
    return int((per_lap <= t_s).sum())


def _safety_car_state(snapshot: RaceSnapshot, lap: int) -> tuple[bool, int]:
    """(safety car active at the cutoff, leader laps since its deployment).

    Active iff the latest visible track-status row is "4". Elapsed laps run from the first row of
    that final run of "4" rows: leader laps now minus leader laps at that row, so a deployment
    inside lap L seen at the end of lap L gives 1 (the convention of `f1si.regime.sc_rate`).
    """
    status = snapshot.track_status
    if lap == 0 or len(status) == 0:
        return False, 0
    ordered = status.sort_values(["t_s", "seq"], kind="stable")
    codes = [None if pd.isna(v) else str(v) for v in ordered["status"].tolist()]
    times = [float(v) for v in ordered["t_s"].tolist()]
    if codes[-1] != "4":
        return False, 0
    start = len(codes) - 1
    while start > 0 and codes[start - 1] == "4":
        start -= 1
    laps_now = _leader_laps_at(snapshot.laps, math.inf)
    elapsed = laps_now - _leader_laps_at(snapshot.laps, times[start])
    return True, max(0, elapsed)


def build_race_state(
    snapshot: RaceSnapshot,
    fit: LinearPaceFit,
    *,
    laps_total: int,
    pit_loss_s: float,
    wear_filter: Mapping[int, FilterSnapshot] | None = None,
) -> RaceState:
    """Build the `RaceState` for the cutoff of `snapshot` (pure; reads only its arguments).

    Rules:
      * `lap` is `snapshot.at.lap` when it is an int, else (race end) the maximum laps_done.
        `laps_total` is an argument because races.scheduled_laps is NULL for every cached race
        (D-21); a `laps_total` below `lap` raises ValueError.
      * `regime` is {"sc": 1.0} while the latest visible track-status row is "4" (safety car
        out), else {"green": 1.0}; `sc_laps_elapsed` counts leader laps since the deployment
        (D-05). `pit_loss_s` is {"green": pit_loss_s, "sc": SC_PIT_LOSS_RATIO * pit_loss_s}, the
        "sc" value a placeholder until Phase 8 (REG-03). VSC and red flags are not modelled (D-02).
      * One car per row of `snapshot.cars`, ordered by (position unknown last, position, number).
      * Compound and tire age come from the car's latest visible stint; at lap 0 they come from
        the entry's start compound and start tyre age (0 if unknown). `tire_age` is laps already
        on the tyres. `compounds_used` lists compounds in stint order, start compound first.
      * Wear rate, wear SD and pace offset come from `fit`; they are None when the compound is
        unknown or unfitted, the driver is not in the fit, or the fit is unidentified.
      * Gap to the car ahead: time gap on the last lap both cars completed (see module
        docstring); None for the leader, lapped cars, missing lap ends and gaps <= 0.
        `gap_behind_s` of a car is the next car's `gap_ahead_s`.
      * `wear_filter` (optional, driver number -> FilterSnapshot, D-13): a car with an entry that
        is not `prior_only` and whose compound is known takes `wear_rate_s_per_lap` = rate_mean
        and `wear_sd` = rate_sd from the filter and `wear_source` "filter"; all other cars keep
        the fit values and "fit". An entry whose `compound` is set and differs from the car's
        current compound is ignored (it describes an earlier tyre).
        Without the argument the state is exactly as before.

    Raises:
        ValueError: if `laps_total` is smaller than the lap, or any `wear_filter` entry has a
            `cutoff_lap` different from the lap of this state (stale or look-ahead data).
    """
    cars = snapshot.cars
    at_lap = snapshot.at.lap
    max_done = int(cars["laps_done"].max()) if len(cars) else 0
    lap = at_lap if isinstance(at_lap, int) else max_done
    if laps_total < lap:
        raise ValueError(
            f"laps_total {laps_total} is smaller than the lap {lap}; pass the race distance (D-21)"
        )
    if wear_filter is not None:
        for fnum, fsnap in wear_filter.items():
            if fsnap.cutoff_lap != lap:
                raise ValueError(
                    f"wear_filter entry for driver {fnum} has cutoff_lap {fsnap.cutoff_lap}, "
                    f"but the state is built at lap {lap}"
                )
    entries = snapshot.entries.set_index("driver_number")
    stints = snapshot.stints.sort_values(["driver_number", "stint"])
    stints_by_driver = {int(str(n)): grp for n, grp in stints.groupby("driver_number", sort=True)}
    ended = snapshot.laps[snapshot.laps["lap_end_s"].notna()]
    ends: dict[tuple[int, int], float] = {
        (int(n), int(k)): float(t)
        for n, k, t in zip(
            ended["driver_number"], ended["lap_number"], ended["lap_end_s"], strict=True
        )
    }

    rows: list[dict[str, Any]] = []
    for _, row in cars.iterrows():
        number = int(row["driver_number"])
        position = None if pd.isna(row["position"]) else int(row["position"])
        mine = stints_by_driver.get(number)
        start_compound: str | None = None
        start_age = 0
        if number in entries.index:
            entry = entries.loc[number]
            start_compound = _upper_or_none(entry["start_compound"])
            raw_age = entry["start_tyre_age"]
            start_age = 0 if pd.isna(raw_age) else int(raw_age)
        used: list[str] = []
        if start_compound is not None:
            used.append(start_compound)
        compound: str | None
        if mine is not None and len(mine):
            for value in mine["compound"].astype("object"):
                name = _upper_or_none(value)
                if name is not None and name not in used:
                    used.append(name)
            latest = mine.iloc[-1]
            compound = _upper_or_none(latest["compound"])
            tire_age = 0 if pd.isna(latest["tyre_life_now"]) else int(latest["tyre_life_now"])
        else:
            compound, tire_age = start_compound, start_age
        rows.append(
            {
                "driver": str(row["driver_code"]),
                "number": number,
                "position": position,
                "done": int(row["laps_done"]),
                "compound": compound,
                "tire_age": tire_age,
                "stops": int(row["stops_done"]),
                "used": tuple(used),
            }
        )
    rows.sort(key=lambda r: (r["position"] is None, r["position"] or 0, r["number"]))

    gap_ahead: list[float | None] = []
    for i, r in enumerate(rows):
        prev = rows[i - 1] if i > 0 else None
        if r["position"] is None or prev is None or prev["position"] is None:
            gap_ahead.append(None)
        else:
            gap_ahead.append(
                _gap_ahead(ends, (r["number"], r["done"]), (prev["number"], prev["done"]))
            )

    states: list[CarState] = []
    for i, r in enumerate(rows):
        name = r["compound"]
        wear_rate = None if name is None else fit.wear_rate(name)
        wear_sd = None if name is None else fit.wear_se(name)
        wear_source = "fit"
        flt = None if wear_filter is None or name is None else wear_filter.get(r["number"])
        # A filter entry for another compound is the car's previous tyre (stop near the cutoff,
        # retired car): its rate does not describe the current tyre, so keep the fit values.
        if flt is not None and flt.compound is not None and flt.compound != name:
            flt = None
        if flt is not None and not flt.prior_only:
            wear_rate, wear_sd, wear_source = flt.rate_mean, flt.rate_sd, "filter"
        states.append(
            CarState(
                driver=r["driver"],
                driver_number=r["number"],
                position=r["position"],
                gap_ahead_s=gap_ahead[i],
                gap_behind_s=gap_ahead[i + 1] if i + 1 < len(rows) else None,
                compound=name,
                tire_age=r["tire_age"],
                wear_rate_s_per_lap=wear_rate,
                wear_sd=wear_sd,
                pace_offset_s=fit.pace_offset(r["number"]),
                stops_done=r["stops"],
                compounds_used=r["used"],
                laps_done=r["done"],
                pace_offset_sd=fit.pace_offset_se(r["number"]),
                wear_source=wear_source,
            )
        )
    sc_active, sc_elapsed = _safety_car_state(snapshot, lap)
    return RaceState(
        lap=lap,
        laps_total=laps_total,
        regime={"sc": 1.0} if sc_active else {"green": 1.0},
        pit_loss_s={"green": pit_loss_s, "sc": SC_PIT_LOSS_RATIO * pit_loss_s},
        cars=tuple(states),
        sc_laps_elapsed=sc_elapsed,
    )
