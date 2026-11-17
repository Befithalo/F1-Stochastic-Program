"""Immutable, race-scoped values prepared for pace models (D-01, D-07, D-08)."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

import pandas as pd

from f1si.data._snapshot import AsOf, RaceInfo, RaceSnapshot

_TIME_COLUMNS = ("weather", "car_data", "location")
_MIN_CHANNEL_ROWS = 3
_MIN_TIMESTAMP_FRACTION = 0.95
_MAX_P95_GAP_S = {"weather": 180.0, "car_data": 5.0, "location": 5.0}


@dataclass(frozen=True)
class VersionedArtifactRef:
    """Stable reference to an input artifact without granting file or cache access."""

    name: str
    version: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("artifact name and version must be non-empty")
        digest = self.sha256.lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("artifact sha256 must be 64 hexadecimal characters")
        object.__setattr__(self, "sha256", digest)

    @classmethod
    def from_bytes(cls, name: str, version: str, payload: bytes) -> VersionedArtifactRef:
        """Construct an immutable reference from the exact bytes used by a model input."""
        return cls(name=name, version=version, sha256=hashlib.sha256(payload).hexdigest())


@dataclass(frozen=True)
class ChannelCoverage:
    """Measured channel completeness and its explicit fallback decision."""

    status: str
    row_count: int
    valid_timestamp_fraction: float
    sampling_gap_p95_s: float | None
    sampling_gap_status: str
    race_clock_alignment: str
    fallback: str | None


def _copy_snapshot(snapshot: RaceSnapshot) -> RaceSnapshot:
    frames = {
        name: getattr(snapshot, name).copy(deep=True)
        for name in (
            "entries",
            "laps",
            "track_status",
            "race_control",
            "weather",
            "car_data",
            "location",
            "stints",
            "pit_events",
            "cars",
        )
    }
    return replace(snapshot, **frames)


def _cutoff_frame(frame: pd.DataFrame, cutoff_s: float | None) -> pd.DataFrame:
    """Defensively preserve only rows visible at this snapshot's inclusive cutoff."""
    copied = frame.copy(deep=True)
    if cutoff_s is None or "visible_at_s" not in copied.columns:
        return copied.reset_index(drop=True)
    visible = pd.to_numeric(copied["visible_at_s"], errors="coerce")
    return copied.loc[visible.notna() & visible.le(cutoff_s)].reset_index(drop=True)


def _coverage(channel: str, frame: pd.DataFrame) -> ChannelCoverage:
    count = len(frame)
    if not count:
        return ChannelCoverage(
            "unavailable", 0, 0.0, None, "unavailable", "unavailable", "cached_lap_timing"
        )
    if "source_utc" not in frame.columns:
        valid_fraction = 0.0
    else:
        valid_fraction = float(
            pd.to_datetime(frame["source_utc"], utc=True, errors="coerce").notna().mean()
        )
    race_clock = (
        pd.to_numeric(frame["t_s"], errors="coerce")
        if "t_s" in frame
        else pd.Series(float("nan"), index=frame.index, dtype="float64")
    )
    aligned_fraction = float(
        race_clock.map(lambda value: pd.notna(value) and math.isfinite(float(value))).mean()
    )
    gap_groups = (
        [
            group["_race_clock"]
            for _, group in frame.assign(_race_clock=race_clock).groupby(
                "driver_number", dropna=False
            )
        ]
        if "driver_number" in frame
        else [race_clock]
    )
    gaps = pd.concat(
        [group.dropna().sort_values().diff().dropna() for group in gap_groups],
        ignore_index=True,
    )
    p95 = None if gaps.empty else float(gaps.quantile(0.95))
    max_gap = _MAX_P95_GAP_S[channel]
    gap_status = (
        "insufficient" if p95 is None else "within_limit" if p95 <= max_gap else "exceeds_limit"
    )
    aligned = aligned_fraction >= _MIN_TIMESTAMP_FRACTION
    status = (
        "available"
        if count >= _MIN_CHANNEL_ROWS
        and valid_fraction >= _MIN_TIMESTAMP_FRACTION
        and aligned
        and gap_status == "within_limit"
        else "sparse"
    )
    return ChannelCoverage(
        status=status,
        row_count=count,
        valid_timestamp_fraction=valid_fraction,
        sampling_gap_p95_s=p95,
        sampling_gap_status=gap_status,
        race_clock_alignment="mapped" if aligned else "unavailable",
        fallback=None if status == "available" else "cached_lap_timing",
    )


@dataclass(frozen=True, eq=False, init=False)
class PhysicsInput:
    """Copy-owning prepared race data; it contains no accessor, database path, or results door."""

    _snapshot: RaceSnapshot
    geometry_ref: VersionedArtifactRef
    parameter_ref: VersionedArtifactRef
    coverage: Mapping[str, ChannelCoverage]

    def __init__(
        self,
        snapshot: RaceSnapshot,
        geometry_ref: VersionedArtifactRef,
        parameter_ref: VersionedArtifactRef,
        coverage: Mapping[str, ChannelCoverage],
    ) -> None:
        object.__setattr__(self, "_snapshot", _copy_snapshot(snapshot))
        object.__setattr__(self, "geometry_ref", geometry_ref)
        object.__setattr__(self, "parameter_ref", parameter_ref)
        object.__setattr__(self, "coverage", MappingProxyType(dict(coverage)))

    @property
    def snapshot(self) -> RaceSnapshot:
        """A defensive copy of the public as-of snapshot."""
        return _copy_snapshot(self._snapshot)

    @property
    def race(self) -> RaceInfo:
        return self._snapshot.race

    @property
    def at(self) -> AsOf:
        return self._snapshot.at

    @property
    def cutoff_s(self) -> float | None:
        return self._snapshot.cutoff_s

    @property
    def entries(self) -> pd.DataFrame:
        return self._snapshot.entries.copy(deep=True)

    @property
    def laps(self) -> pd.DataFrame:
        return self._snapshot.laps.copy(deep=True)

    @property
    def track_status(self) -> pd.DataFrame:
        return self._snapshot.track_status.copy(deep=True)

    @property
    def race_control(self) -> pd.DataFrame:
        return self._snapshot.race_control.copy(deep=True)

    @property
    def weather(self) -> pd.DataFrame:
        return self._snapshot.weather.copy(deep=True)

    @property
    def car_data(self) -> pd.DataFrame:
        return self._snapshot.car_data.copy(deep=True)

    @property
    def location(self) -> pd.DataFrame:
        return self._snapshot.location.copy(deep=True)

    @property
    def stints(self) -> pd.DataFrame:
        return self._snapshot.stints.copy(deep=True)

    @property
    def pit_events(self) -> pd.DataFrame:
        return self._snapshot.pit_events.copy(deep=True)

    @property
    def cars(self) -> pd.DataFrame:
        return self._snapshot.cars.copy(deep=True)


def build_physics_input(
    snapshot: RaceSnapshot,
    geometry_ref: VersionedArtifactRef,
    parameter_ref: VersionedArtifactRef,
) -> PhysicsInput:
    """Prepare immutable values from an in-sample, cutoff-limited `RaceSnapshot` only."""
    if not isinstance(snapshot, RaceSnapshot):
        raise TypeError("PhysicsInput accepts only a RaceSnapshot")
    if not isinstance(geometry_ref, VersionedArtifactRef):
        raise TypeError("geometry_ref must be a validated VersionedArtifactRef")
    if not isinstance(parameter_ref, VersionedArtifactRef):
        raise TypeError("parameter_ref must be a VersionedArtifactRef")
    if snapshot.race.out_of_sample:
        raise ValueError("out-of-sample races cannot build PhysicsInput")
    frames = {
        name: _cutoff_frame(getattr(snapshot, name), snapshot.cutoff_s) for name in _TIME_COLUMNS
    }
    prepared = replace(
        snapshot,
        weather=frames["weather"],
        car_data=frames["car_data"],
        location=frames["location"],
    )
    coverage = {name: _coverage(name, frame) for name, frame in frames.items()}
    return PhysicsInput(prepared, geometry_ref, parameter_ref, coverage)
